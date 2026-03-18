"""Tests for TriageAgent."""
from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from culturedx.agents.base import AgentInput
from culturedx.agents.triage import CATEGORY_DISORDERS, TriageAgent


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
    (agents_dir / "triage_en.jinja").write_text(
        "Triage: {{ transcript_text }}\n"
        "{% if evidence_summary %}Evidence: {{ evidence_summary }}{% endif %}\n"
    )
    (agents_dir / "triage_zh.jinja").write_text(
        "分诊: {{ transcript_text }}\n"
        "{% if evidence_summary %}证据: {{ evidence_summary }}{% endif %}\n"
    )
    return agents_dir


class TestTriageAgent:
    def test_single_category_high_confidence(self, prompts_dir):
        resp = json.dumps({"categories": [
            {"category": "mood", "confidence": 0.9}
        ]})
        agent = TriageAgent(llm_client=MockLLM(response=resp), prompts_dir=prompts_dir)
        output = agent.run(AgentInput(transcript_text="Patient is depressed", language="en"))
        assert output.parsed["categories"][0]["category"] == "mood"
        assert set(output.parsed["disorder_codes"]) == {"F31", "F32", "F33"}

    def test_multiple_categories(self, prompts_dir):
        resp = json.dumps({"categories": [
            {"category": "mood", "confidence": 0.8},
            {"category": "anxiety", "confidence": 0.6},
        ]})
        agent = TriageAgent(llm_client=MockLLM(response=resp), prompts_dir=prompts_dir)
        output = agent.run(AgentInput(transcript_text="test", language="en"))
        codes = output.parsed["disorder_codes"]
        assert "F32" in codes
        assert "F41.1" in codes

    def test_low_confidence_takes_top3(self, prompts_dir):
        resp = json.dumps({"categories": [
            {"category": "mood", "confidence": 0.4},
            {"category": "anxiety", "confidence": 0.3},
            {"category": "sleep", "confidence": 0.2},
            {"category": "psychotic", "confidence": 0.1},
        ]})
        agent = TriageAgent(llm_client=MockLLM(response=resp), prompts_dir=prompts_dir)
        output = agent.run(AgentInput(transcript_text="test", language="en"))
        # Top-1 is 0.4 (< 0.7), so takes top 3
        assert len(output.parsed["categories"]) == 3

    def test_activation_threshold_filter(self, prompts_dir):
        resp = json.dumps({"categories": [
            {"category": "mood", "confidence": 0.9},
            {"category": "anxiety", "confidence": 0.15},
        ]})
        agent = TriageAgent(llm_client=MockLLM(response=resp), prompts_dir=prompts_dir)
        output = agent.run(AgentInput(transcript_text="test", language="en"))
        # Top-1 >= 0.7, so filter by activation_threshold (0.2)
        # anxiety (0.15) is below 0.2, should be excluded
        cats = [c["category"] for c in output.parsed["categories"]]
        assert "mood" in cats
        assert "anxiety" not in cats

    def test_unparseable_activates_all(self, prompts_dir):
        agent = TriageAgent(llm_client=MockLLM(response="I cannot classify"), prompts_dir=prompts_dir)
        output = agent.run(AgentInput(transcript_text="test", language="en"))
        # Should activate all categories as fallback
        assert len(output.parsed["disorder_codes"]) > 0

    def test_invalid_category_ignored(self, prompts_dir):
        resp = json.dumps({"categories": [
            {"category": "mood", "confidence": 0.9},
            {"category": "invalid_cat", "confidence": 0.5},
        ]})
        agent = TriageAgent(llm_client=MockLLM(response=resp), prompts_dir=prompts_dir)
        output = agent.run(AgentInput(transcript_text="test", language="en"))
        cats = [c["category"] for c in output.parsed["categories"]]
        assert "invalid_cat" not in cats

    def test_chinese_language(self, prompts_dir):
        resp = json.dumps({"categories": [
            {"category": "mood", "confidence": 0.85}
        ]})
        agent = TriageAgent(llm_client=MockLLM(response=resp), prompts_dir=prompts_dir)
        output = agent.run(AgentInput(transcript_text="患者情绪低落", language="zh"))
        assert output.parsed["categories"][0]["category"] == "mood"

    def test_confidence_clamped(self, prompts_dir):
        resp = json.dumps({"categories": [
            {"category": "mood", "confidence": 1.5}
        ]})
        agent = TriageAgent(llm_client=MockLLM(response=resp), prompts_dir=prompts_dir)
        output = agent.run(AgentInput(transcript_text="test", language="en"))
        assert output.parsed["categories"][0]["confidence"] <= 1.0

    def test_category_disorder_mapping(self):
        """Verify all expected categories exist in the mapping."""
        assert set(CATEGORY_DISORDERS.keys()) == {
            "mood", "anxiety", "stress", "somatoform", "psychotic", "sleep"
        }
        # Verify specific mappings
        assert "F32" in CATEGORY_DISORDERS["mood"]
        assert "F41.1" in CATEGORY_DISORDERS["anxiety"]
        assert "F20" in CATEGORY_DISORDERS["psychotic"]
