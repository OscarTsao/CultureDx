"""Tests for Specialist-MAS mode."""
from __future__ import annotations

import json
import pytest

from culturedx.core.models import ClinicalCase, DiagnosisResult, Turn
from culturedx.modes.specialist import SpecialistMode


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


class TestSpecialistMode:
    def test_mode_name(self):
        responses = [
            # Specialist for F32
            json.dumps({
                "disorder_code": "F32",
                "diagnosis_likely": True,
                "confidence": 0.8,
                "reasoning": "Low mood",
                "key_symptoms": ["depressed mood"],
            }),
            # Judge
            json.dumps({
                "primary_diagnosis": "F32",
                "comorbid_diagnoses": [],
                "confidence": 0.8,
                "decision": "diagnosis",
                "reasoning": "Clear depression",
            }),
        ]
        llm = FakeLLM(responses)
        mode = SpecialistMode(llm_client=llm, target_disorders=["F32"])
        result = mode.diagnose(make_case())

        assert result.mode == "specialist"
        assert result.primary_diagnosis == "F32"

    def test_unsupported_language(self):
        llm = FakeLLM()
        mode = SpecialistMode(llm_client=llm)
        result = mode.diagnose(make_case(language="fr"))
        assert result.decision == "abstain"
        assert result.mode == "specialist"

    def test_empty_candidates(self):
        llm = FakeLLM()
        mode = SpecialistMode(llm_client=llm, target_disorders=[])
        result = mode.diagnose(make_case())
        assert result.decision == "abstain"

    def test_judge_abstains(self):
        responses = [
            json.dumps({
                "disorder_code": "F32",
                "diagnosis_likely": False,
                "confidence": 0.2,
                "reasoning": "Insufficient evidence",
                "key_symptoms": [],
            }),
            json.dumps({
                "primary_diagnosis": None,
                "confidence": 0.1,
                "decision": "abstain",
            }),
        ]
        llm = FakeLLM(responses)
        mode = SpecialistMode(llm_client=llm, target_disorders=["F32"])
        result = mode.diagnose(make_case())
        assert result.decision == "abstain"

    def test_multiple_specialists(self):
        responses = [
            json.dumps({
                "disorder_code": "F32",
                "diagnosis_likely": True,
                "confidence": 0.9,
                "reasoning": "Strong depression",
                "key_symptoms": ["low mood"],
            }),
            json.dumps({
                "disorder_code": "F41.1",
                "diagnosis_likely": True,
                "confidence": 0.7,
                "reasoning": "Anxiety symptoms",
                "key_symptoms": ["worry"],
            }),
            json.dumps({
                "primary_diagnosis": "F32",
                "comorbid_diagnoses": ["F41.1"],
                "confidence": 0.85,
                "decision": "diagnosis",
                "reasoning": "Comorbid",
            }),
        ]
        llm = FakeLLM(responses)
        mode = SpecialistMode(llm_client=llm, target_disorders=["F32", "F41.1"])
        result = mode.diagnose(make_case())
        assert result.primary_diagnosis == "F32"
        assert "F41.1" in result.comorbid_diagnoses
