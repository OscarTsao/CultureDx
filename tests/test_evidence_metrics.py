"""Tests for evidence quality metrics."""
import pytest

from culturedx.core.models import (
    CriterionEvidence,
    DisorderEvidence,
    EvidenceBrief,
    SymptomSpan,
)
from culturedx.eval.evidence_metrics import (
    criterion_coverage,
    evidence_precision,
    compute_evidence_quality_metrics,
)


def _make_span(text: str = "test", turn_id: int = 1) -> SymptomSpan:
    return SymptomSpan(text=text, turn_id=turn_id, symptom_type="retrieved")


class TestCriterionCoverage:
    def test_full_coverage(self):
        brief = EvidenceBrief(
            case_id="t",
            language="zh",
            disorder_evidence=[
                DisorderEvidence(
                    disorder_code="F32",
                    disorder_name="Depressive episode",
                    criteria_evidence=[
                        CriterionEvidence(
                            criterion_id="F32.B1",
                            spans=[_make_span()],
                            confidence=0.9,
                        ),
                        CriterionEvidence(
                            criterion_id="F32.B2",
                            spans=[_make_span()],
                            confidence=0.8,
                        ),
                    ],
                ),
            ],
        )
        gold = {"F32": ["B1", "B2"]}
        assert criterion_coverage(brief, gold) == 1.0

    def test_partial_coverage(self):
        brief = EvidenceBrief(
            case_id="t",
            language="zh",
            disorder_evidence=[
                DisorderEvidence(
                    disorder_code="F32",
                    disorder_name="Depressive episode",
                    criteria_evidence=[
                        CriterionEvidence(
                            criterion_id="F32.B1",
                            spans=[_make_span()],
                            confidence=0.9,
                        ),
                        CriterionEvidence(
                            criterion_id="F32.B2",
                            spans=[],  # No spans
                            confidence=0.1,
                        ),
                    ],
                ),
            ],
        )
        gold = {"F32": ["B1", "B2"]}
        assert criterion_coverage(brief, gold) == 0.5

    def test_empty_brief(self):
        brief = EvidenceBrief(case_id="t", language="zh")
        gold = {"F32": ["B1", "B2"]}
        assert criterion_coverage(brief, gold) == 0.0


class TestEvidencePrecision:
    def test_all_relevant(self):
        brief = EvidenceBrief(
            case_id="t",
            language="zh",
            disorder_evidence=[
                DisorderEvidence(
                    disorder_code="F32",
                    disorder_name="Depressive episode",
                    criteria_evidence=[
                        CriterionEvidence(
                            criterion_id="F32.B1",
                            spans=[_make_span()],
                            confidence=0.9,
                        ),
                    ],
                ),
            ],
        )
        gold = {"F32": ["B1"]}
        assert evidence_precision(brief, gold) == 1.0

    def test_no_gold(self):
        brief = EvidenceBrief(case_id="t", language="zh")
        assert evidence_precision(brief, {}) == 0.0


class TestComputeEvidenceQuality:
    def test_returns_both_metrics(self):
        brief = EvidenceBrief(
            case_id="t",
            language="zh",
            disorder_evidence=[
                DisorderEvidence(
                    disorder_code="F32",
                    disorder_name="Depressive episode",
                    criteria_evidence=[
                        CriterionEvidence(
                            criterion_id="F32.B1",
                            spans=[_make_span()],
                            confidence=0.9,
                        ),
                    ],
                ),
            ],
        )
        gold = {"F32": ["B1", "B2"]}
        metrics = compute_evidence_quality_metrics(brief, gold)
        assert "criterion_coverage" in metrics
        assert "evidence_precision" in metrics
        assert metrics["criterion_coverage"] == 0.5
        assert metrics["evidence_precision"] == 1.0
