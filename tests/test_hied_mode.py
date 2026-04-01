"""Tests for HiED mode orchestrator."""
from __future__ import annotations

import json
import pytest

from culturedx.core.models import (
    CheckerOutput,
    ClinicalCase,
    CriterionEvidence,
    CriterionResult,
    DiagnosisResult,
    DisorderEvidence,
    EvidenceBrief,
    SymptomSpan,
    Turn,
)
from culturedx.agents.base import AgentOutput
from culturedx.modes.hied import HiEDMode


class FakeLLM:
    """Fake LLM client for testing."""

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


def make_case(
    case_id: str = "test-001",
    language: str = "zh",
    diagnoses: list[str] | None = None,
) -> ClinicalCase:
    return ClinicalCase(
        case_id=case_id,
        transcript=[
            Turn(speaker="doctor", text="你好，今天来看什么问题？", turn_id=1),
            Turn(speaker="patient", text="我最近情绪很低落，睡不好，没有食欲。", turn_id=2),
            Turn(speaker="doctor", text="持续多久了？", turn_id=3),
            Turn(speaker="patient", text="差不多三个月了。", turn_id=4),
        ],
        language=language,
        dataset="test",
        diagnoses=diagnoses or [],
    )


def make_triage_response(categories: list[dict]) -> str:
    return json.dumps({"categories": categories})


def make_checker_response(disorder: str, criteria_met: int, total: int) -> str:
    """Create a checker response using real ontology IDs where possible."""
    from culturedx.ontology.icd10 import get_disorder_criteria

    real_criteria = get_disorder_criteria(disorder)
    if real_criteria:
        real_ids = list(real_criteria.keys())
    else:
        real_ids = [f"A{i+1}" for i in range(total)]

    # Pad if test requests more than real criteria
    while len(real_ids) < total:
        real_ids.append(f"X{len(real_ids)}")
    real_ids = real_ids[:total]

    criteria = []
    for i, cid in enumerate(real_ids):
        status = "met" if i < criteria_met else "not_met"
        criteria.append({
            "criterion_id": cid,
            "status": status,
            "evidence": f"test evidence {cid}" if status == "met" else None,
            "confidence": 0.85 if status == "met" else 0.3,
        })
    return json.dumps({
        "criteria": criteria,
    })


class TestHiEDMode:
    """Tests for HiEDMode orchestrator."""

    def test_basic_pipeline_with_target_disorders(self):
        """HiED with target_disorders runs in explicit manual benchmark scope."""
        responses = [
            # Criterion checker for F32 (meets threshold: 5 of 9 met, 2 core needed)
            make_checker_response("F32", 6, 9),
        ]
        llm = FakeLLM(responses)
        mode = HiEDMode(
            llm_client=llm,
            target_disorders=["F32"],
            abstain_threshold=0.1,
        )
        case = make_case()
        result = mode.diagnose(case)

        assert result.case_id == "test-001"
        assert result.mode == "hied"
        assert result.language_used == "zh"
        assert result.scope_policy == "manual"
        assert result.routing_mode == "benchmark_manual_scope"
        assert result.candidate_disorders == ["F32"]

    def test_triage_activates_disorders(self):
        """HiED with no target_disorders runs triage in production/open-set mode."""
        responses = [
            # Triage response
            make_triage_response([
                {"category": "mood", "confidence": 0.9},
                {"category": "anxiety", "confidence": 0.3},
            ]),
            # Criterion checkers for mood disorders: F31, F32, F33
            make_checker_response("F31", 1, 5),
            make_checker_response("F32", 6, 9),
            make_checker_response("F33", 2, 9),
            # Criterion checkers for anxiety disorders (activated because 0.3 >= 0.2)
            make_checker_response("F40", 1, 4),
            make_checker_response("F41.0", 1, 6),
            make_checker_response("F41.1", 2, 6),
            make_checker_response("F42", 1, 5),
        ]
        llm = FakeLLM(responses)
        mode = HiEDMode(llm_client=llm, abstain_threshold=0.1)
        case = make_case()
        result = mode.diagnose(case)

        assert result.mode == "hied"
        # Should have checked multiple disorders
        assert len(result.criteria_results) > 0
        assert result.scope_policy == "triage"
        assert result.routing_mode == "production_open_set"

    def test_unsupported_language_abstains(self):
        """HiED abstains for unsupported languages."""
        llm = FakeLLM()
        mode = HiEDMode(llm_client=llm)
        case = make_case(language="fr")
        result = mode.diagnose(case)

        assert result.decision == "abstain"
        assert result.confidence == 0.0
        assert result.mode == "hied"

    def test_no_confirmed_disorders_abstains(self):
        """When logic engine confirms nothing, HiED abstains."""
        responses = [
            # Checker for F32: only 1 criterion met (below threshold)
            make_checker_response("F32", 1, 9),
        ]
        llm = FakeLLM(responses)
        mode = HiEDMode(
            llm_client=llm,
            target_disorders=["F32"],
        )
        case = make_case()
        result = mode.diagnose(case)

        assert result.decision == "abstain"
        assert result.primary_diagnosis is None

    def test_calibrator_abstain_low_confidence(self):
        """Calibrator abstains when confidence below threshold."""
        responses = [
            # Checker for F32: 3 met (borderline)
            make_checker_response("F32", 3, 9),
        ]
        llm = FakeLLM(responses)
        mode = HiEDMode(
            llm_client=llm,
            target_disorders=["F32"],
            abstain_threshold=0.9,  # Very high threshold
        )
        case = make_case()
        result = mode.diagnose(case)
        # Logic engine likely rejects with only 3/9
        assert result.decision == "abstain"

    def test_with_evidence(self):
        """HiED uses evidence brief when provided."""
        responses = [
            make_checker_response("F32", 6, 9),
        ]
        llm = FakeLLM(responses)
        mode = HiEDMode(
            llm_client=llm,
            target_disorders=["F32"],
            abstain_threshold=0.1,
        )
        case = make_case()
        evidence = EvidenceBrief(
            case_id="test-001",
            language="zh",
            symptom_spans=[
                SymptomSpan(text="情绪低落", turn_id=2, symptom_type="emotional"),
            ],
            disorder_evidence=[
                DisorderEvidence(
                    disorder_code="F32",
                    disorder_name="Depressive episode",
                    criteria_evidence=[
                        CriterionEvidence(
                            criterion_id="A1",
                            spans=[SymptomSpan(text="情绪低落", turn_id=2, symptom_type="emotional")],
                            confidence=0.9,
                        ),
                    ],
                ),
            ],
        )
        result = mode.diagnose(case, evidence=evidence)

        assert result.mode == "hied"
        assert result.case_id == "test-001"

    def test_comorbid_diagnoses(self):
        """HiED detects comorbidity when multiple disorders confirmed."""
        responses = [
            # F32: 6/9 met (confirmed)
            make_checker_response("F32", 6, 9),
            # F41.1: all met (also confirmed)
            make_checker_response("F41.1", 6, 6),
        ]
        llm = FakeLLM(responses)
        mode = HiEDMode(
            llm_client=llm,
            target_disorders=["F32", "F41.1"],
            abstain_threshold=0.1,
        )
        case = make_case()
        result = mode.diagnose(case)

        assert result.mode == "hied"
        # Primary should be set
        assert result.primary_diagnosis is not None

    def test_empty_candidates(self):
        """HiED reports a scope failure when manual scope has no candidates."""
        llm = FakeLLM()
        mode = HiEDMode(llm_client=llm, target_disorders=[])
        case = make_case()
        result = mode.diagnose(case)

        assert result.decision == "abstain"
        assert result.failure is not None
        assert result.failure.code == "scope_resolution_failed"

    def test_build_transcript_text(self):
        """Transcript builder produces expected format."""
        case = make_case()
        text = HiEDMode._build_transcript_text(case)
        assert "Doctor:" in text
        assert "Patient:" in text

    def test_build_evidence_map(self):
        """Evidence map builder extracts per-disorder summaries."""
        evidence = EvidenceBrief(
            case_id="test",
            language="zh",
            disorder_evidence=[
                DisorderEvidence(
                    disorder_code="F32",
                    disorder_name="Depressive episode",
                    criteria_evidence=[
                        CriterionEvidence(
                            criterion_id="A1",
                            spans=[SymptomSpan(text="low mood", turn_id=1, symptom_type="emotional")],
                            confidence=0.9,
                        ),
                    ],
                ),
            ],
        )
        emap = HiEDMode._build_evidence_map(evidence)
        assert "F32" in emap
        assert "A1" in emap["F32"]

    def test_production_mode_rejects_manual_targets(self):
        llm = FakeLLM()
        mode = HiEDMode(
            llm_client=llm,
            target_disorders=["F32"],
            execution_mode="production_open_set",
        )
        result = mode.diagnose(make_case())
        assert result.decision == "abstain"
        assert result.failure is not None
        assert result.failure.code == "scope_resolution_failed"

    def test_triage_failure_is_machine_readable(self):
        llm = FakeLLM()
        mode = HiEDMode(llm_client=llm, abstain_threshold=0.1)
        mode.triage.run = lambda _input: AgentOutput(
            raw_response="{}",
            parsed=None,
            model_name="test-model",
            prompt_hash="test-hash",
        )
        result = mode.diagnose(make_case())
        assert result.failures
        assert any(f.code == "triage_failed" for f in result.failures)
