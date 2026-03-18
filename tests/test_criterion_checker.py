"""Tests for CriterionCheckerAgent."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from culturedx.agents.base import AgentInput
from culturedx.agents.criterion_checker import CriterionCheckerAgent, _compute_required


@dataclass
class MockLLM:
    """Mock LLM client for testing."""
    model: str = "test-model"
    response: str = ""

    @staticmethod
    def compute_prompt_hash(text: str) -> str:
        return "testhash"

    def generate(self, prompt: str, prompt_hash: str = "", language: str = "zh") -> str:
        return self.response


@pytest.fixture
def prompts_dir(tmp_path):
    """Create temp prompts with minimal templates."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    # Minimal English template
    (agents_dir / "criterion_checker_en.jinja").write_text(
        "Evaluate {{ disorder_code }} {{ disorder_name }}\n"
        "Criteria: {% for k, v in criteria.items() %}{{ k }}{% endfor %}\n"
        "Transcript: {{ transcript_text }}\n"
        "{% if evidence_summary %}Evidence: {{ evidence_summary }}{% endif %}\n"
    )
    # Minimal Chinese template
    (agents_dir / "criterion_checker_zh.jinja").write_text(
        "评估 {{ disorder_code }} {{ disorder_name }}\n"
        "标准: {% for k, v in criteria.items() %}{{ k }}{% endfor %}\n"
        "对话: {{ transcript_text }}\n"
        "{% if evidence_summary %}证据: {{ evidence_summary }}{% endif %}\n"
    )
    return agents_dir


class TestComputeRequired:
    def test_all_required(self):
        criteria = {"A": {}, "B": {}, "C": {}}
        assert _compute_required("F22", criteria, {"all_required": True}) == 3

    def test_min_total(self):
        criteria = {"B1": {}, "B2": {}, "C1": {}}
        assert _compute_required("F32", criteria, {"min_total": 4}) == 4

    def test_min_symptoms(self):
        criteria = {"A": {}, "B1": {}, "B2": {}}
        assert _compute_required("F41.1", criteria, {"min_symptoms": 4}) == 4

    def test_first_rank_plus_other(self):
        criteria = {"A1": {}, "A2": {}, "B1": {}, "B2": {}}
        assert _compute_required("F20", criteria, {"min_first_rank": 1, "min_other": 2}) == 3

    def test_core_plus_additional(self):
        criteria = {"A": {"type": "core"}, "B": {"type": "core"}, "C1": {"type": "behavioral"}}
        assert _compute_required("F40", criteria, {"core_required": True, "min_additional": 1}) == 3

    def test_attacks_threshold(self):
        criteria = {"A": {}, "B1": {}, "B2": {}, "B3": {}, "B4": {}}
        assert _compute_required("F41.0", criteria, {"attacks_per_month": 3, "min_symptoms_per_attack": 4}) == 4

    def test_fallback_all(self):
        criteria = {"A": {}, "B": {}}
        assert _compute_required("X99", criteria, {"unknown_key": True}) == 2


class TestCriterionCheckerAgent:
    def test_run_valid_response(self, prompts_dir):
        """Test agent with a valid JSON LLM response."""
        llm = MockLLM(response='{"criteria": [{"criterion_id": "B1", "status": "met", "evidence": "low mood", "confidence": 0.9}, {"criterion_id": "B2", "status": "not_met", "evidence": null, "confidence": 0.1}]}')
        agent = CriterionCheckerAgent(llm_client=llm, prompts_dir=prompts_dir)

        inp = AgentInput(
            transcript_text="Patient reports feeling sad.",
            language="en",
            extra={"disorder_code": "F32"},
        )
        output = agent.run(inp)

        assert output.model_name == "test-model"
        assert output.parsed is not None
        assert output.parsed["disorder"] == "F32"
        assert len(output.parsed["criteria"]) == 2
        assert output.parsed["criteria"][0].status == "met"
        assert output.parsed["criteria_met_count"] == 1

    def test_run_no_disorder_code(self, prompts_dir):
        """Test agent returns empty when no disorder_code provided."""
        llm = MockLLM()
        agent = CriterionCheckerAgent(llm_client=llm, prompts_dir=prompts_dir)
        inp = AgentInput(transcript_text="test", extra={})
        output = agent.run(inp)
        assert output.parsed is None

    def test_run_unknown_disorder(self, prompts_dir):
        """Test agent returns empty for unknown disorder code."""
        llm = MockLLM()
        agent = CriterionCheckerAgent(llm_client=llm, prompts_dir=prompts_dir)
        inp = AgentInput(transcript_text="test", extra={"disorder_code": "X99"})
        output = agent.run(inp)
        assert output.parsed is None

    def test_run_unparseable_response(self, prompts_dir):
        """Test agent handles unparseable LLM output gracefully."""
        llm = MockLLM(response="I cannot evaluate this patient.")
        agent = CriterionCheckerAgent(llm_client=llm, prompts_dir=prompts_dir)
        inp = AgentInput(
            transcript_text="test",
            language="en",
            extra={"disorder_code": "F32"},
        )
        output = agent.run(inp)
        # Should fallback to insufficient_evidence for all criteria
        assert output.parsed is not None
        assert output.parsed["criteria_met_count"] == 0
        assert all(r.status == "insufficient_evidence" for r in output.parsed["criteria"])

    def test_run_chinese_language(self, prompts_dir):
        """Test agent works with Chinese language."""
        llm = MockLLM(response='{"criteria": [{"criterion_id": "B1", "status": "met", "evidence": "情绪低落", "confidence": 0.85}]}')
        agent = CriterionCheckerAgent(llm_client=llm, prompts_dir=prompts_dir)
        inp = AgentInput(
            transcript_text="患者表示情绪低落",
            language="zh",
            extra={"disorder_code": "F32"},
        )
        output = agent.run(inp)
        assert output.parsed["criteria"][0].evidence == "情绪低落"

    def test_run_with_evidence(self, prompts_dir):
        """Test agent passes evidence summary to prompt."""
        llm = MockLLM(response='{"criteria": [{"criterion_id": "B1", "status": "met", "evidence": "test", "confidence": 0.8}]}')
        agent = CriterionCheckerAgent(llm_client=llm, prompts_dir=prompts_dir)
        inp = AgentInput(
            transcript_text="test transcript",
            language="en",
            evidence={"evidence_summary": "Somatic symptoms: headache, insomnia"},
            extra={"disorder_code": "F32"},
        )
        output = agent.run(inp)
        assert output.parsed is not None

    def test_invalid_status_normalized(self, prompts_dir):
        """Test that invalid status values are normalized to insufficient_evidence."""
        llm = MockLLM(response='{"criteria": [{"criterion_id": "B1", "status": "maybe", "confidence": 0.5}]}')
        agent = CriterionCheckerAgent(llm_client=llm, prompts_dir=prompts_dir)
        inp = AgentInput(
            transcript_text="test",
            language="en",
            extra={"disorder_code": "F32"},
        )
        output = agent.run(inp)
        # "maybe" should be normalized to "insufficient_evidence"
        parsed_criteria = [r for r in output.parsed["criteria"] if r.criterion_id == "B1"]
        assert parsed_criteria[0].status == "insufficient_evidence"
