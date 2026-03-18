"""Tests for PsyCoT mode orchestrator."""
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
from culturedx.modes.psycot import PsyCoTMode


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


def make_case(
    case_id: str = "test-001",
    language: str = "zh",
) -> ClinicalCase:
    return ClinicalCase(
        case_id=case_id,
        transcript=[
            Turn(speaker="doctor", text="你好", turn_id=1),
            Turn(speaker="patient", text="我情绪低落三个月了", turn_id=2),
        ],
        language=language,
        dataset="test",
    )


def make_checker_response(met: int, total: int, disorder: str = "F32") -> str:
    """Create a checker response using real ontology IDs where possible."""
    from culturedx.ontology.icd10 import get_disorder_criteria
    real_criteria = get_disorder_criteria(disorder)
    if real_criteria:
        real_ids = list(real_criteria.keys())
    else:
        real_ids = [f"A{i+1}" for i in range(total)]

    while len(real_ids) < total:
        real_ids.append(f"X{len(real_ids)}")
    real_ids = real_ids[:total]

    criteria = []
    for i, cid in enumerate(real_ids):
        status = "met" if i < met else "not_met"
        criteria.append({
            "criterion_id": cid,
            "status": status,
            "evidence": f"evidence {cid}" if status == "met" else None,
            "confidence": 0.85 if status == "met" else 0.3,
        })
    return json.dumps({"criteria": criteria})


class TestPsyCoTMode:
    def test_mode_name_is_psycot(self):
        llm = FakeLLM([make_checker_response(6, 9)])
        mode = PsyCoTMode(llm_client=llm, target_disorders=["F32"], abstain_threshold=0.1)
        result = mode.diagnose(make_case())
        assert result.mode == "psycot"

    def test_no_triage_call(self):
        """PsyCoT should NOT call triage — goes straight to checkers."""
        responses = [make_checker_response(6, 9)]
        llm = FakeLLM(responses)
        mode = PsyCoTMode(llm_client=llm, target_disorders=["F32"], abstain_threshold=0.1)
        result = mode.diagnose(make_case())
        # Only 1 LLM call (checker), NOT 2 (triage + checker)
        assert llm._call_idx == 1

    def test_unsupported_language_abstains(self):
        llm = FakeLLM()
        mode = PsyCoTMode(llm_client=llm)
        result = mode.diagnose(make_case(language="fr"))
        assert result.decision == "abstain"
        assert result.mode == "psycot"

    def test_no_confirmed_abstains(self):
        """When logic engine confirms nothing, PsyCoT abstains."""
        responses = [make_checker_response(1, 9)]
        llm = FakeLLM(responses)
        mode = PsyCoTMode(llm_client=llm, target_disorders=["F32"])
        result = mode.diagnose(make_case())
        assert result.decision == "abstain"

    def test_empty_target_disorders(self):
        llm = FakeLLM()
        mode = PsyCoTMode(llm_client=llm, target_disorders=[])
        result = mode.diagnose(make_case())
        assert result.decision == "abstain"

    def test_comorbidity_detection(self):
        """PsyCoT detects comorbid conditions."""
        responses = [
            make_checker_response(6, 9, disorder="F32"),  # F32 confirmed
            make_checker_response(4, 4, disorder="F41.1"),  # F41.1 confirmed
        ]
        llm = FakeLLM(responses)
        mode = PsyCoTMode(
            llm_client=llm,
            target_disorders=["F32", "F41.1"],
            abstain_threshold=0.1,
        )
        result = mode.diagnose(make_case())
        assert result.primary_diagnosis is not None
        assert result.mode == "psycot"

    def test_with_evidence(self):
        responses = [make_checker_response(6, 9)]
        llm = FakeLLM(responses)
        mode = PsyCoTMode(llm_client=llm, target_disorders=["F32"], abstain_threshold=0.1)

        evidence = EvidenceBrief(
            case_id="test-001",
            language="zh",
            disorder_evidence=[
                DisorderEvidence(
                    disorder_code="F32",
                    disorder_name="Depressive episode",
                    criteria_evidence=[
                        CriterionEvidence(
                            criterion_id="A1",
                            spans=[SymptomSpan(text="低落", turn_id=2, symptom_type="emotional")],
                            confidence=0.9,
                        ),
                    ],
                ),
            ],
        )
        result = mode.diagnose(make_case(), evidence=evidence)
        assert result.mode == "psycot"

    def test_build_transcript_text(self):
        case = make_case()
        text = PsyCoTMode._build_transcript_text(case)
        assert "Doctor:" in text
        assert "Patient:" in text
