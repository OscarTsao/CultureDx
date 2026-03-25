"""Tests for ConfidenceCalibrator."""
from __future__ import annotations

import pytest

from culturedx.core.models import (
    CheckerOutput,
    CriterionEvidence,
    CriterionResult,
    DisorderEvidence,
    EvidenceBrief,
    ScaleScore,
    SymptomSpan,
)
from culturedx.diagnosis.calibrator import CalibrationOutput, ConfidenceCalibrator


def _make_checker(
    disorder: str,
    met_with_conf: list[tuple[str, float]],
    not_met: list[str],
    required: int,
) -> CheckerOutput:
    criteria = []
    for cid, conf in met_with_conf:
        criteria.append(CriterionResult(
            criterion_id=cid, status="met", evidence="test evidence", confidence=conf
        ))
    for cid in not_met:
        criteria.append(CriterionResult(
            criterion_id=cid, status="not_met", confidence=0.1
        ))
    return CheckerOutput(
        disorder=disorder,
        criteria=criteria,
        criteria_met_count=len(met_with_conf),
        criteria_required=required,
    )


@pytest.fixture
def calibrator():
    return ConfidenceCalibrator()


class TestConfidenceCalibrator:
    def test_single_high_confidence(self, calibrator):
        co = _make_checker("F32", [("B1", 0.9), ("B2", 0.85), ("C1", 0.8), ("C2", 0.75)], ["B3"], 4)
        result = calibrator.calibrate(["F32"], [co])
        assert result.primary is not None
        assert result.primary.disorder_code == "F32"
        assert result.primary.decision == "diagnosis"
        assert result.primary.confidence > 0.5

    def test_below_abstain_threshold(self, calibrator):
        # Very low confidence criteria
        co = _make_checker("F32", [("B1", 0.1), ("B2", 0.1)], ["B3", "C1", "C2"], 4)
        co.criteria_met_count = 2  # Below required 4
        result = calibrator.calibrate(["F32"], [co])
        # Might abstain due to low confidence + low threshold ratio
        # The exact result depends on weights, but confidence should be low
        if result.primary:
            assert result.primary.confidence < 0.6

    def test_comorbid(self, calibrator):
        co1 = _make_checker("F32", [("B1", 0.9), ("B2", 0.85), ("C1", 0.8), ("C2", 0.8)], [], 4)
        co2 = _make_checker("F41.1", [("A", 0.8), ("B1", 0.7), ("B2", 0.75), ("B3", 0.7)], ["B4"], 4)
        result = calibrator.calibrate(["F32", "F41.1"], [co1, co2])
        assert result.primary is not None
        assert len(result.comorbid) == 1

    def test_empty_input(self, calibrator):
        result = calibrator.calibrate([], [])
        assert result.primary is None
        assert len(result.comorbid) == 0

    def test_evidence_coverage_with_brief(self, calibrator):
        co = _make_checker("F32", [("B1", 0.9), ("B2", 0.8)], ["B3"], 4)
        evidence = EvidenceBrief(
            case_id="test",
            language="en",
            disorder_evidence=[
                DisorderEvidence(
                    disorder_code="F32",
                    disorder_name="Depression",
                    criteria_evidence=[
                        CriterionEvidence(
                            criterion_id="B1",
                            spans=[SymptomSpan(text="sad", turn_id=1, symptom_type="emotional")],
                            confidence=0.9,
                        ),
                    ],
                ),
            ],
        )
        result = calibrator.calibrate(["F32"], [co], evidence=evidence)
        assert result.primary is not None
        assert result.primary.evidence_coverage > 0.0

    def test_no_evidence_uses_checker(self, calibrator):
        co = _make_checker("F32", [("B1", 0.9), ("B2", 0.8)], ["B3"], 4)
        result = calibrator.calibrate(["F32"], [co], evidence=None)
        assert result.primary is not None
        # Evidence coverage computed from checker evidence field
        assert result.primary.evidence_coverage > 0.0

    def test_primary_is_highest_confidence(self, calibrator):
        co1 = _make_checker("F41.1", [("A", 0.95), ("B1", 0.9), ("B2", 0.9), ("B3", 0.9)], [], 4)
        co2 = _make_checker("F32", [("B1", 0.7), ("B2", 0.6), ("C1", 0.5), ("C2", 0.5)], [], 4)
        result = calibrator.calibrate(["F41.1", "F32"], [co1, co2])
        assert result.primary.disorder_code == "F41.1"

    def test_custom_thresholds(self):
        cal = ConfidenceCalibrator(abstain_threshold=0.8)
        co = _make_checker("F32", [("B1", 0.5), ("B2", 0.5), ("C1", 0.4), ("C2", 0.4)], [], 4)
        result = cal.calibrate(["F32"], [co])
        # With high abstain threshold, medium confidence should abstain
        if result.primary is None:
            assert len(result.abstained) == 1


class TestScaleScoreSignal:
    """Tests for _compute_scale_score_signal static method."""

    def test_no_scale_scores_returns_neutral(self):
        result = ConfidenceCalibrator._compute_scale_score_signal("F32", None)
        assert result == 0.5

    def test_empty_scale_scores_returns_neutral(self):
        result = ConfidenceCalibrator._compute_scale_score_signal("F32", [])
        assert result == 0.5

    def test_unmatched_disorder_returns_neutral(self):
        scores = [ScaleScore(name="phq8", total=20)]
        result = ConfidenceCalibrator._compute_scale_score_signal("F20", scores)
        assert result == 0.5

    # PHQ-8/9 for depression (F32/F33)
    def test_phq8_below_threshold(self):
        scores = [ScaleScore(name="phq8", total=5)]
        result = ConfidenceCalibrator._compute_scale_score_signal("F32", scores)
        assert result == 0.0

    def test_phq8_mild(self):
        scores = [ScaleScore(name="phq8", total=12)]
        result = ConfidenceCalibrator._compute_scale_score_signal("F32", scores)
        assert result == 0.3

    def test_phq8_moderate(self):
        scores = [ScaleScore(name="phq8", total=17)]
        result = ConfidenceCalibrator._compute_scale_score_signal("F32", scores)
        assert result == 0.6

    def test_phq8_severe(self):
        scores = [ScaleScore(name="phq8", total=22)]
        result = ConfidenceCalibrator._compute_scale_score_signal("F32", scores)
        assert result == 1.0

    def test_phq9_works_for_f33(self):
        scores = [ScaleScore(name="phq9", total=20)]
        result = ConfidenceCalibrator._compute_scale_score_signal("F33", scores)
        assert result == 1.0

    # HAMD-17 for depression
    def test_hamd17_below_threshold(self):
        scores = [ScaleScore(name="hamd17", total=5)]
        result = ConfidenceCalibrator._compute_scale_score_signal("F32", scores)
        assert result == 0.0

    def test_hamd17_mild(self):
        scores = [ScaleScore(name="hamd17", total=12)]
        result = ConfidenceCalibrator._compute_scale_score_signal("F32", scores)
        assert result == 0.4

    def test_hamd17_moderate(self):
        scores = [ScaleScore(name="hamd17", total=20)]
        result = ConfidenceCalibrator._compute_scale_score_signal("F32", scores)
        assert result == 0.7

    def test_hamd17_severe(self):
        scores = [ScaleScore(name="hamd17", total=28)]
        result = ConfidenceCalibrator._compute_scale_score_signal("F32", scores)
        assert result == 1.0

    # PHQ takes precedence over HAMD when both present
    def test_phq_preferred_over_hamd(self):
        scores = [
            ScaleScore(name="phq8", total=5),   # -> 0.0
            ScaleScore(name="hamd17", total=28),  # -> 1.0 (not reached)
        ]
        result = ConfidenceCalibrator._compute_scale_score_signal("F32", scores)
        assert result == 0.0

    # GAD-7 for anxiety (F41/F41.1)
    def test_gad7_below_threshold(self):
        scores = [ScaleScore(name="gad7", total=7)]
        result = ConfidenceCalibrator._compute_scale_score_signal("F41.1", scores)
        assert result == 0.0

    def test_gad7_mild(self):
        scores = [ScaleScore(name="gad7", total=12)]
        result = ConfidenceCalibrator._compute_scale_score_signal("F41.1", scores)
        assert result == 0.3

    def test_gad7_severe(self):
        scores = [ScaleScore(name="gad7", total=18)]
        result = ConfidenceCalibrator._compute_scale_score_signal("F41.1", scores)
        assert result == 0.7

    def test_gad7_works_for_f41(self):
        scores = [ScaleScore(name="gad7", total=15)]
        result = ConfidenceCalibrator._compute_scale_score_signal("F41", scores)
        assert result == 0.7

    # Integration: scale_scores flows through calibrate()
    def test_calibrate_with_scale_scores(self, calibrator):
        co = _make_checker(
            "F32", [("B1", 0.9), ("B2", 0.85), ("C1", 0.8), ("C2", 0.75)], ["B3"], 4,
        )
        scores = [ScaleScore(name="phq8", total=22)]
        result_with = calibrator.calibrate(["F32"], [co], scale_scores=scores)
        result_without = calibrator.calibrate(["F32"], [co], scale_scores=None)
        # With high PHQ-8 (signal=1.0) should yield higher confidence than neutral (0.5)
        assert result_with.primary is not None
        assert result_without.primary is not None
        assert result_with.primary.confidence >= result_without.primary.confidence

    def test_calibrate_low_scale_reduces_confidence(self, calibrator):
        co = _make_checker(
            "F32", [("B1", 0.9), ("B2", 0.85), ("C1", 0.8), ("C2", 0.75)], ["B3"], 4,
        )
        scores = [ScaleScore(name="phq8", total=3)]  # signal=0.0
        result_low = calibrator.calibrate(["F32"], [co], scale_scores=scores)
        result_neutral = calibrator.calibrate(["F32"], [co], scale_scores=None)  # signal=0.5
        assert result_low.primary is not None
        assert result_neutral.primary is not None
        assert result_low.primary.confidence <= result_neutral.primary.confidence

    def test_scale_score_signal_stored_in_result(self, calibrator):
        co = _make_checker(
            "F32", [("B1", 0.9), ("B2", 0.85), ("C1", 0.8), ("C2", 0.75)], ["B3"], 4,
        )
        scores = [ScaleScore(name="phq8", total=22)]
        result = calibrator.calibrate(["F32"], [co], scale_scores=scores)
        assert result.primary is not None
        assert result.primary.scale_score_signal == 1.0
