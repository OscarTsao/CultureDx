"""Tests for MASMode orchestrator."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from culturedx.core.models import (
    ClinicalCase,
    CriterionEvidence,
    DisorderEvidence,
    EvidenceBrief,
    SymptomSpan,
    Turn,
)
from culturedx.modes.mas import MASMode


@dataclass
class MockLLM:
    """Mock LLM that returns different responses based on prompt content."""
    model: str = "test-model"
    responses: dict = field(default_factory=dict)
    default_response: str = '{"criteria": []}'

    @staticmethod
    def compute_prompt_hash(text: str) -> str:
        return "testhash"

    def generate(self, prompt: str, prompt_hash: str = "", language: str = "zh") -> str:
        # Differential prompts start with "Differential:" or "鉴别:" — use those
        # keys first so they win over disorder codes that also appear in the prompt.
        _DIFF_MARKERS = ("Differential:", "鉴别:")
        is_differential = any(prompt.lstrip().startswith(m) for m in _DIFF_MARKERS)
        if is_differential:
            for marker in _DIFF_MARKERS:
                if marker in self.responses:
                    return self.responses[marker]
            return self.default_response
        # Criterion checker calls: match by disorder code key
        for key, response in sorted(self.responses.items(), key=lambda kv: len(kv[0]), reverse=True):
            if key in prompt:
                return response
        return self.default_response


@pytest.fixture
def prompts_dir(tmp_path):
    """Create minimal Jinja templates for both agents."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    # Criterion checker templates
    (agents_dir / "criterion_checker_en.jinja").write_text(
        "Evaluate {{ disorder_code }} {{ disorder_name }}\n"
        "{% for k, v in criteria.items() %}{{ k }}{% endfor %}\n"
        "{{ transcript_text }}\n"
        "{% if evidence_summary %}{{ evidence_summary }}{% endif %}\n"
    )
    (agents_dir / "criterion_checker_zh.jinja").write_text(
        "评估 {{ disorder_code }} {{ disorder_name }}\n"
        "{% for k, v in criteria.items() %}{{ k }}{% endfor %}\n"
        "{{ transcript_text }}\n"
        "{% if evidence_summary %}{{ evidence_summary }}{% endif %}\n"
    )
    # Differential templates
    (agents_dir / "differential_en.jinja").write_text(
        "Differential: {% for r in checker_results %}{{ r.disorder }}{% endfor %}\n"
        "{{ transcript_summary }}\n"
    )
    (agents_dir / "differential_zh.jinja").write_text(
        "鉴别: {% for r in checker_results %}{{ r.disorder }}{% endfor %}\n"
        "{{ transcript_summary }}\n"
    )
    return agents_dir


def _make_case(case_id: str = "test-001", language: str = "en") -> ClinicalCase:
    return ClinicalCase(
        case_id=case_id,
        transcript=[
            Turn(speaker="doctor", text="How are you feeling?", turn_id=0),
            Turn(speaker="patient", text="I feel sad and tired all the time.", turn_id=1),
            Turn(speaker="doctor", text="How long has this been going on?", turn_id=2),
            Turn(speaker="patient", text="About three weeks now.", turn_id=3),
        ],
        language=language,
        dataset="test",
    )


def _make_evidence(case_id: str = "test-001") -> EvidenceBrief:
    return EvidenceBrief(
        case_id=case_id,
        language="en",
        disorder_evidence=[
            DisorderEvidence(
                disorder_code="F32",
                disorder_name="Depressive episode",
                criteria_evidence=[
                    CriterionEvidence(
                        criterion_id="B1",
                        spans=[SymptomSpan(text="feel sad", turn_id=1, symptom_type="emotional")],
                        confidence=0.9,
                    ),
                    CriterionEvidence(
                        criterion_id="B3",
                        spans=[SymptomSpan(text="tired all the time", turn_id=1, symptom_type="somatic")],
                        confidence=0.85,
                    ),
                ],
            ),
        ],
    )


class TestMASMode:
    def test_full_pipeline_with_evidence(self, prompts_dir):
        """Test full MAS pipeline: evidence -> checker -> differential."""
        checker_resp = json.dumps({
            "criteria": [
                {"criterion_id": "B1", "status": "met", "evidence": "feels sad", "confidence": 0.9},
                {"criterion_id": "B2", "status": "not_met", "evidence": None, "confidence": 0.1},
                {"criterion_id": "B3", "status": "met", "evidence": "tired", "confidence": 0.85},
                {"criterion_id": "C1", "status": "met", "evidence": "low self-esteem", "confidence": 0.7},
                {"criterion_id": "C6", "status": "met", "evidence": "insomnia", "confidence": 0.8},
            ]
        })
        diff_resp = json.dumps({
            "primary_diagnosis": "F32",
            "comorbid_diagnoses": [],
            "confidence": 0.88,
            "reasoning": "F32 meets 4/4 required criteria",
        })
        llm = MockLLM(responses={
            "F32": checker_resp,
            "Differential": diff_resp,
            "鉴别": diff_resp,
        }, default_response=diff_resp)
        
        mode = MASMode(llm_client=llm, prompts_dir=prompts_dir, target_disorders=["F32"])
        case = _make_case()
        evidence = _make_evidence()
        
        result = mode.diagnose(case, evidence=evidence)
        
        assert result.case_id == "test-001"
        assert result.primary_diagnosis == "F32"
        assert result.decision == "diagnosis"
        assert result.mode == "mas"
        assert len(result.criteria_results) == 1
        assert result.criteria_results[0].disorder == "F32"

    def test_no_candidates_abstain(self, prompts_dir):
        """Test that no candidates leads to abstain."""
        llm = MockLLM()
        mode = MASMode(llm_client=llm, prompts_dir=prompts_dir, target_disorders=[])
        case = _make_case()
        
        result = mode.diagnose(case)
        assert result.decision == "abstain"
        assert result.primary_diagnosis is None

    def test_unsupported_language_abstain(self, prompts_dir):
        """Test unsupported language returns abstain."""
        llm = MockLLM()
        mode = MASMode(llm_client=llm, prompts_dir=prompts_dir)
        case = _make_case(language="fr")
        
        result = mode.diagnose(case)
        assert result.decision == "abstain"
        assert result.mode == "mas"

    def test_candidates_from_evidence(self, prompts_dir):
        """Test that candidates come from evidence when no target_disorders."""
        checker_resp = json.dumps({
            "criteria": [
                {"criterion_id": "B1", "status": "met", "evidence": "test", "confidence": 0.8},
            ]
        })
        diff_resp = json.dumps({
            "primary_diagnosis": "F32",
            "comorbid_diagnoses": [],
            "confidence": 0.75,
            "reasoning": "test",
        })
        llm = MockLLM(responses={"F32": checker_resp}, default_response=diff_resp)
        
        mode = MASMode(llm_client=llm, prompts_dir=prompts_dir)
        case = _make_case()
        evidence = _make_evidence()  # Has F32 in disorder_evidence
        
        result = mode.diagnose(case, evidence=evidence)
        # Should have checked F32 from evidence
        assert result.mode == "mas"

    def test_multiple_disorders(self, prompts_dir):
        """Test checking multiple disorders with comorbidity."""
        f32_resp = json.dumps({
            "criteria": [
                {"criterion_id": "B1", "status": "met", "evidence": "sad", "confidence": 0.9},
                {"criterion_id": "B3", "status": "met", "evidence": "tired", "confidence": 0.8},
                {"criterion_id": "C1", "status": "met", "evidence": "low esteem", "confidence": 0.7},
                {"criterion_id": "C6", "status": "met", "evidence": "insomnia", "confidence": 0.75},
            ]
        })
        f41_resp = json.dumps({
            "criteria": [
                {"criterion_id": "A", "status": "met", "evidence": "worry", "confidence": 0.85},
                {"criterion_id": "B1", "status": "met", "evidence": "tense", "confidence": 0.7},
                {"criterion_id": "B3", "status": "met", "evidence": "cant focus", "confidence": 0.6},
                {"criterion_id": "B4", "status": "met", "evidence": "insomnia", "confidence": 0.75},
            ]
        })
        diff_resp = json.dumps({
            "primary_diagnosis": "F32",
            "comorbid_diagnoses": ["F41.1"],
            "confidence": 0.82,
            "reasoning": "Both meet thresholds",
        })
        llm = MockLLM(responses={
            "F32": f32_resp,
            "F41.1": f41_resp,
        }, default_response=diff_resp)
        
        mode = MASMode(llm_client=llm, prompts_dir=prompts_dir, target_disorders=["F32", "F41.1"])
        case = _make_case()
        
        result = mode.diagnose(case)
        assert result.primary_diagnosis == "F32"
        assert "F41.1" in result.comorbid_diagnoses
        assert len(result.criteria_results) == 2

    def test_build_transcript_text(self, prompts_dir):
        """Test transcript text building."""
        llm = MockLLM()
        mode = MASMode(llm_client=llm, prompts_dir=prompts_dir)
        case = _make_case()
        text = mode._build_transcript_text(case)
        assert "Doctor: How are you feeling?" in text
        assert "Patient: I feel sad and tired all the time." in text

    def test_build_evidence_map(self, prompts_dir):
        """Test evidence map building from EvidenceBrief."""
        llm = MockLLM()
        mode = MASMode(llm_client=llm, prompts_dir=prompts_dir)
        evidence = _make_evidence()
        emap = mode._build_evidence_map(evidence)
        assert "F32" in emap
        assert "feel sad" in emap["F32"]
        assert "tired all the time" in emap["F32"]

    def test_chinese_pipeline(self, prompts_dir):
        """Test full pipeline with Chinese language."""
        checker_resp = json.dumps({
            "criteria": [
                {"criterion_id": "B1", "status": "met", "evidence": "情绪低落", "confidence": 0.9},
                {"criterion_id": "B3", "status": "met", "evidence": "疲乏", "confidence": 0.8},
                {"criterion_id": "C1", "status": "met", "evidence": "自卑", "confidence": 0.7},
                {"criterion_id": "C6", "status": "met", "evidence": "失眠", "confidence": 0.75},
            ]
        })
        diff_resp = json.dumps({
            "primary_diagnosis": "F32",
            "comorbid_diagnoses": [],
            "confidence": 0.85,
            "reasoning": "符合F32标准",
        })
        llm = MockLLM(responses={"F32": checker_resp}, default_response=diff_resp)
        
        mode = MASMode(llm_client=llm, prompts_dir=prompts_dir, target_disorders=["F32"])
        case = _make_case(language="zh")
        
        result = mode.diagnose(case)
        assert result.language_used == "zh"
        assert result.primary_diagnosis == "F32"
