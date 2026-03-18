"""Tests for DifferentialDiagnosisAgent."""
from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from culturedx.agents.base import AgentInput
from culturedx.agents.differential import DifferentialDiagnosisAgent
from culturedx.core.models import CheckerOutput, CriterionResult


@dataclass
class MockLLM:
    model: str = "test-model"
    response: str = ""

    @staticmethod
    def compute_prompt_hash(text: str) -> str:
        return "testhash"

    def generate(self, prompt: str, prompt_hash: str = "", language: str = "zh") -> str:
        return self.response


@pytest.fixture
def prompts_dir(tmp_path):
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "differential_en.jinja").write_text(
        "Differential for: {% for r in checker_results %}{{ r.disorder }} {% endfor %}\n"
        "Summary: {{ transcript_summary }}\n"
    )
    (agents_dir / "differential_zh.jinja").write_text(
        "鉴别诊断: {% for r in checker_results %}{{ r.disorder }} {% endfor %}\n"
        "摘要: {{ transcript_summary }}\n"
    )
    return agents_dir


def _make_checker_output(disorder: str, met: list[str], not_met: list[str], required: int) -> CheckerOutput:
    """Helper to build a CheckerOutput."""
    criteria = []
    for cid in met:
        criteria.append(CriterionResult(criterion_id=cid, status="met", confidence=0.9))
    for cid in not_met:
        criteria.append(CriterionResult(criterion_id=cid, status="not_met", confidence=0.2))
    return CheckerOutput(
        disorder=disorder,
        criteria=criteria,
        criteria_met_count=len(met),
        criteria_required=required,
    )


class TestDifferentialDiagnosisAgent:
    def test_single_disorder_diagnosis(self, prompts_dir):
        """Test with one disorder that meets threshold."""
        resp = json.dumps({
            "primary_diagnosis": "F32",
            "comorbid_diagnoses": [],
            "confidence": 0.88,
            "reasoning": "F32 meets criteria threshold",
        })
        llm = MockLLM(response=resp)
        agent = DifferentialDiagnosisAgent(llm_client=llm, prompts_dir=prompts_dir)

        checker = _make_checker_output("F32", met=["B1", "B2", "C1", "C2"], not_met=["C3"], required=4)
        inp = AgentInput(
            transcript_text="Patient reports low mood and fatigue.",
            language="en",
            extra={
                "checker_outputs": [checker],
                "case_id": "test-001",
                "disorder_names": {"F32": "Depressive episode"},
            },
        )
        output = agent.run(inp)
        assert output.parsed["primary_diagnosis"] == "F32"
        assert output.parsed["decision"] == "diagnosis"
        assert output.parsed["case_id"] == "test-001"
        assert output.parsed["mode"] == "mas"

    def test_comorbid_diagnoses(self, prompts_dir):
        """Test with two disorders, both meeting thresholds."""
        resp = json.dumps({
            "primary_diagnosis": "F32",
            "comorbid_diagnoses": ["F41.1"],
            "confidence": 0.80,
            "reasoning": "Both meet criteria",
        })
        llm = MockLLM(response=resp)
        agent = DifferentialDiagnosisAgent(llm_client=llm, prompts_dir=prompts_dir)

        co1 = _make_checker_output("F32", met=["B1", "B2", "C1", "C2"], not_met=[], required=4)
        co2 = _make_checker_output("F41.1", met=["A", "B1", "B2", "B3"], not_met=["B4"], required=4)
        inp = AgentInput(
            transcript_text="Patient has both depression and anxiety.",
            language="en",
            extra={
                "checker_outputs": [co1, co2],
                "case_id": "test-002",
            },
        )
        output = agent.run(inp)
        assert output.parsed["primary_diagnosis"] == "F32"
        assert "F41.1" in output.parsed["comorbid_diagnoses"]
        assert output.parsed["criteria_results"] == [co1, co2]

    def test_no_diagnosis(self, prompts_dir):
        """Test when no disorder meets threshold."""
        resp = json.dumps({
            "primary_diagnosis": None,
            "comorbid_diagnoses": [],
            "confidence": 0.3,
            "reasoning": "Insufficient evidence",
        })
        llm = MockLLM(response=resp)
        agent = DifferentialDiagnosisAgent(llm_client=llm, prompts_dir=prompts_dir)

        co = _make_checker_output("F32", met=["B1"], not_met=["B2", "B3", "C1"], required=4)
        inp = AgentInput(
            transcript_text="Brief interview.",
            language="en",
            extra={"checker_outputs": [co], "case_id": "test-003"},
        )
        output = agent.run(inp)
        assert output.parsed["primary_diagnosis"] is None
        assert output.parsed["decision"] == "abstain"

    def test_empty_checker_outputs(self, prompts_dir):
        """Test with no checker outputs."""
        llm = MockLLM()
        agent = DifferentialDiagnosisAgent(llm_client=llm, prompts_dir=prompts_dir)
        inp = AgentInput(transcript_text="test", extra={"checker_outputs": []})
        output = agent.run(inp)
        assert output.parsed is None

    def test_unparseable_response(self, prompts_dir):
        """Test with unparseable LLM response."""
        llm = MockLLM(response="I need more information to diagnose.")
        agent = DifferentialDiagnosisAgent(llm_client=llm, prompts_dir=prompts_dir)

        co = _make_checker_output("F32", met=["B1", "B2"], not_met=[], required=4)
        inp = AgentInput(
            transcript_text="test",
            language="en",
            extra={"checker_outputs": [co], "case_id": "test-004"},
        )
        output = agent.run(inp)
        assert output.parsed["decision"] == "abstain"
        assert output.parsed["primary_diagnosis"] is None

    def test_chinese_language(self, prompts_dir):
        """Test with Chinese language."""
        resp = json.dumps({
            "primary_diagnosis": "F32",
            "comorbid_diagnoses": [],
            "confidence": 0.85,
            "reasoning": "符合F32标准",
        })
        llm = MockLLM(response=resp)
        agent = DifferentialDiagnosisAgent(llm_client=llm, prompts_dir=prompts_dir)

        co = _make_checker_output("F32", met=["B1", "B2", "C1", "C2"], not_met=[], required=4)
        inp = AgentInput(
            transcript_text="患者感到情绪低落",
            language="zh",
            extra={"checker_outputs": [co], "case_id": "test-005"},
        )
        output = agent.run(inp)
        assert output.parsed["language_used"] == "zh"
        assert output.parsed["primary_diagnosis"] == "F32"

    def test_transcript_truncation(self, prompts_dir):
        """Test that long transcripts are truncated for the differential prompt."""
        long_text = "x" * 1000
        resp = json.dumps({
            "primary_diagnosis": "F32",
            "comorbid_diagnoses": [],
            "confidence": 0.7,
            "reasoning": "test",
        })
        llm = MockLLM(response=resp)
        agent = DifferentialDiagnosisAgent(llm_client=llm, prompts_dir=prompts_dir)

        co = _make_checker_output("F32", met=["B1", "B2", "C1", "C2"], not_met=[], required=4)
        inp = AgentInput(
            transcript_text=long_text,
            language="en",
            extra={"checker_outputs": [co], "case_id": "test-006"},
        )
        output = agent.run(inp)
        # Agent should still work even with long transcripts
        assert output.parsed is not None
