"""Tests for Debate-MAS mode."""
from __future__ import annotations

import json
import pytest

from culturedx.core.models import ClinicalCase, DiagnosisResult, Turn
from culturedx.modes.debate import DebateMode
from culturedx.agents.perspective import PerspectiveAgent, PERSPECTIVES


class FakeLLM:
    def __init__(self, responses: list[str] | None = None):
        self.model = "test-model"
        self.responses = responses or []
        self._call_idx = 0

    def generate(self, prompt: str, **kwargs) -> str:
        if self._call_idx < len(self.responses):
            resp = self.responses[self._call_idx]
            self._call_idx += 1
            return resp
        return "{}"

    def compute_prompt_hash(self, template_source: str) -> str:
        return "test-hash"


def make_case(language: str = "zh") -> ClinicalCase:
    return ClinicalCase(
        case_id="test-001",
        transcript=[
            Turn(speaker="doctor", text="你好", turn_id=1),
            Turn(speaker="patient", text="我情绪低落", turn_id=2),
        ],
        language=language,
        dataset="test",
    )


def make_perspective_response(perspective: str, disorder: str = "F32", conf: float = 0.8) -> str:
    return json.dumps({
        "perspective": perspective,
        "diagnoses": [{"disorder_code": disorder, "confidence": conf}],
        "confidence": conf,
        "reasoning": f"From {perspective} perspective",
    })


class TestPerspectiveAgent:
    def test_valid_perspectives(self):
        assert len(PERSPECTIVES) == 4
        assert "cultural" in PERSPECTIVES

    def test_invalid_perspective_raises(self):
        llm = FakeLLM()
        with pytest.raises(ValueError, match="Invalid perspective"):
            PerspectiveAgent(llm, "invalid")


class TestDebateMode:
    def test_mode_name(self):
        # 2 rounds x 4 perspectives + 1 judge = 9 LLM calls
        responses = []
        for _ in range(2):
            for p in PERSPECTIVES:
                responses.append(make_perspective_response(p))
        responses.append(json.dumps({
            "primary_diagnosis": "F32",
            "comorbid_diagnoses": [],
            "confidence": 0.85,
            "decision": "diagnosis",
            "reasoning": "Consensus",
        }))
        llm = FakeLLM(responses)
        mode = DebateMode(llm_client=llm)
        result = mode.diagnose(make_case())

        assert result.mode == "debate"
        assert result.primary_diagnosis == "F32"

    def test_unsupported_language(self):
        llm = FakeLLM()
        mode = DebateMode(llm_client=llm)
        result = mode.diagnose(make_case(language="fr"))
        assert result.decision == "abstain"
        assert result.mode == "debate"

    def test_two_rounds(self):
        """Debate mode runs exactly 2 rounds by default."""
        responses = []
        for _ in range(2):
            for p in PERSPECTIVES:
                responses.append(make_perspective_response(p))
        responses.append(json.dumps({
            "primary_diagnosis": "F32",
            "confidence": 0.8,
            "decision": "diagnosis",
        }))
        llm = FakeLLM(responses)
        mode = DebateMode(llm_client=llm)
        result = mode.diagnose(make_case())

        # 8 perspective calls + 1 judge = 9
        assert llm._call_idx == 9

    def test_single_round(self):
        """Debate with 1 round uses 4 perspective + 1 judge = 5 calls."""
        responses = []
        for p in PERSPECTIVES:
            responses.append(make_perspective_response(p))
        responses.append(json.dumps({
            "primary_diagnosis": "F32",
            "confidence": 0.8,
            "decision": "diagnosis",
        }))
        llm = FakeLLM(responses)
        mode = DebateMode(llm_client=llm, num_rounds=1)
        result = mode.diagnose(make_case())
        assert llm._call_idx == 5
        assert result.mode == "debate"

    def test_judge_abstains(self):
        responses = []
        for _ in range(2):
            for p in PERSPECTIVES:
                responses.append(make_perspective_response(p, conf=0.2))
        responses.append(json.dumps({
            "primary_diagnosis": None,
            "confidence": 0.1,
            "decision": "abstain",
        }))
        llm = FakeLLM(responses)
        mode = DebateMode(llm_client=llm)
        result = mode.diagnose(make_case())
        assert result.decision == "abstain"
