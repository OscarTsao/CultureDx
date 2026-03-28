"""Tests for TriageAgent."""
from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from culturedx.agents.base import AgentInput
from culturedx.agents.triage import CATEGORY_DISORDERS, TriageAgent
from culturedx.agents.triage_routing import (
    TriageCalibrationArtifact,
    TriageCalibrationExample,
    evaluate_triage_calibration,
    fit_temperature_scaling,
)


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
        assert output.parsed["routing_mode"] == "heuristic_fallback"
        assert output.parsed["calibration_status"] == "fallback"
        assert output.parsed["raw_category_scores"]["mood"] == 0.9
        assert output.parsed["calibrated_category_scores"]["mood"] == 0.9

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
        assert output.parsed["selected_categories"][0] == "mood"
        assert output.parsed["candidate_disorder_codes"] == [
            "F31",
            "F32",
            "F33",
            "F40",
            "F41.0",
            "F41.1",
            "F42",
        ]

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
        assert len(output.parsed["categories"]) == 4
        assert len(output.parsed["selected_categories"]) == 3
        assert output.parsed["uncertainty"] == pytest.approx(0.6)

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
        assert "anxiety" in cats
        assert output.parsed["selected_categories"] == ["mood"]
        assert output.parsed["open_set_score"] == pytest.approx(0.1)

    def test_unparseable_activates_all(self, prompts_dir):
        agent = TriageAgent(llm_client=MockLLM(response="I cannot classify"), prompts_dir=prompts_dir)
        output = agent.run(AgentInput(transcript_text="test", language="en"))
        # Should activate all categories as fallback
        assert len(output.parsed["disorder_codes"]) > 0
        assert output.parsed["fallback_reason"] == "no_valid_categories"

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

    def test_calibration_artifact_changes_routing(self, prompts_dir, tmp_path):
        artifact = TriageCalibrationArtifact(
            method="temperature_scaling",
            temperature=2.0,
            categories=["mood", "anxiety"],
        )
        artifact_path = tmp_path / "triage_calibration.json"
        artifact.save(artifact_path)

        resp = json.dumps({"categories": [
            {"category": "mood", "confidence": 0.8},
            {"category": "anxiety", "confidence": 0.3},
        ]})
        agent = TriageAgent(
            llm_client=MockLLM(response=resp),
            prompts_dir=prompts_dir,
            calibration_artifact_path=artifact_path,
        )
        output = agent.run(AgentInput(transcript_text="test", language="en"))
        assert output.parsed["routing_mode"] == "calibrated"
        assert output.parsed["calibration_status"] == "loaded"
        assert output.parsed["calibration_temperature"] == 2.0
        assert output.parsed["calibrated_category_scores"]["mood"] != pytest.approx(
            output.parsed["raw_category_scores"]["mood"]
        )
        assert output.parsed["categories"][0]["confidence"] == output.parsed["calibrated_category_scores"]["mood"]

    def test_missing_artifact_uses_safe_fallback(self, prompts_dir, tmp_path):
        missing = tmp_path / "does_not_exist.json"
        resp = json.dumps({"categories": [
            {"category": "mood", "confidence": 0.9},
        ]})
        agent = TriageAgent(
            llm_client=MockLLM(response=resp),
            prompts_dir=prompts_dir,
            calibration_artifact_path=missing,
        )
        output = agent.run(AgentInput(transcript_text="test", language="en"))
        assert output.parsed["routing_mode"] == "heuristic_fallback"
        assert output.parsed["calibration_status"] == "fallback"
        assert output.parsed["fallback_reason"] == "no_calibration_artifact"

    def test_fit_and_evaluate_helpers(self):
        examples = [
            TriageCalibrationExample(
                example_id="ex-1",
                gold_categories=["mood"],
                raw_category_scores={"mood": 0.92, "anxiety": 0.10, "sleep": 0.05},
            ),
            TriageCalibrationExample(
                example_id="ex-2",
                gold_categories=["anxiety"],
                raw_category_scores={"mood": 0.15, "anxiety": 0.81, "sleep": 0.08},
            ),
        ]
        artifact = fit_temperature_scaling(examples)
        metrics = evaluate_triage_calibration(examples, artifact)
        assert artifact.method == "temperature_scaling"
        assert artifact.temperature > 0.0
        assert "recall_at_k" in metrics
        assert "ece" in metrics
        assert "brier" in metrics
        assert metrics["candidate_set_size"]["max"] >= 1.0

    def test_category_disorder_mapping(self):
        """Verify all expected categories exist in the mapping."""
        assert set(CATEGORY_DISORDERS.keys()) == {
            "mood", "anxiety", "stress", "somatoform", "psychotic", "sleep"
        }
        # Verify specific mappings
        assert "F32" in CATEGORY_DISORDERS["mood"]
        assert "F41.1" in CATEGORY_DISORDERS["anxiety"]
        assert "F20" in CATEGORY_DISORDERS["psychotic"]
