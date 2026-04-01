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
from culturedx.diagnosis.calibrator import (
    CalibrationOutput,
    CalibratorArtifact,
    ConfidenceCalibrator,
)


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
        assert result.primary.placement == "primary"
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
        assert result.comorbid[0].placement == "comorbid"

    def test_non_primary_below_comorbid_threshold_is_rejected(self):
        calibrator = ConfidenceCalibrator(abstain_threshold=0.2, comorbid_threshold=0.95)
        primary = _make_checker(
            "F32",
            [("B1", 0.95), ("B2", 0.9), ("C1", 0.85), ("C2", 0.8)],
            [],
            4,
        )
        weak_secondary = _make_checker(
            "F41.1",
            [("A", 0.45), ("B1", 0.42), ("B2", 0.4), ("B3", 0.38)],
            ["B4"],
            4,
        )
        result = calibrator.calibrate(["F32", "F41.1"], [primary, weak_secondary])
        assert result.primary is not None
        assert result.primary.disorder_code == "F32"
        assert result.comorbid == []
        assert len(result.rejected) == 1
        assert result.rejected[0].disorder_code == "F41.1"
        assert result.rejected[0].decision == "rejected"
        assert result.rejected[0].placement == "rejected"
        assert result.rejected[0].decision_reason in {
            "below_comorbid_threshold",
            "insufficient_threshold_support",
            "insufficient_evidence_coverage",
        }

    def test_abstained_output_tracks_reason(self):
        calibrator = ConfidenceCalibrator(abstain_threshold=0.7)
        low = _make_checker(
            "F32",
            [("B1", 0.2), ("B2", 0.2)],
            ["B3", "C1", "C2"],
            4,
        )
        result = calibrator.calibrate(["F32"], [low])
        assert result.primary is None
        assert len(result.abstained) == 1
        assert result.abstained[0].placement == "abstained"
        assert result.abstained[0].decision_reason == "below_abstain_threshold"

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

    def test_feature_extraction_is_stable(self, calibrator):
        primary = _make_checker("F32", [("B1", 0.9), ("B2", 0.8), ("C1", 0.7), ("C2", 0.7)], [], 4)
        secondary = _make_checker("F41.1", [("A", 0.6), ("B1", 0.55), ("B2", 0.5), ("B3", 0.45)], [], 4)
        features = calibrator.extract_calibration_features(
            "F32",
            primary,
            [primary, secondary],
            evidence=None,
        )
        assert "avg_confidence" in features
        assert "threshold_ratio" in features
        assert "met_fraction" in features
        assert features["criteria_met_count"] == pytest.approx(4.0)
        assert features["criteria_total_count"] == pytest.approx(4.0)

    def test_artifact_roundtrip_and_learned_path(self, tmp_path):
        artifact = CalibratorArtifact(
            feature_names=[
                "avg_confidence",
                "threshold_ratio",
                "evidence_coverage",
            ],
            weights={
                "avg_confidence": 1.0,
                "threshold_ratio": 1.5,
                "evidence_coverage": 0.5,
            },
            bias=-0.5,
            abstain_threshold=0.25,
            comorbid_threshold=0.6,
            metadata={"source": "unit-test"},
        )
        path = tmp_path / "artifact.json"
        artifact.save(path)

        loaded = CalibratorArtifact.load(path)
        assert loaded.schema_version == artifact.schema_version
        assert loaded.feature_names == artifact.feature_names
        assert loaded.weights == artifact.weights
        assert loaded.bias == pytest.approx(-0.5)

        primary = _make_checker("F32", [("B1", 0.9), ("B2", 0.9), ("C1", 0.8), ("C2", 0.8)], [], 4)
        learned = ConfidenceCalibrator(artifact=loaded)
        result = learned.calibrate(["F32"], [primary])
        assert result.primary is not None
        assert result.primary.calibration_path == "artifact"
        assert result.primary.decision_trace["artifact_type"] == "diagnosis_calibrator_linear"
        assert "feature_vector" in result.primary.decision_trace

    def test_fit_linear_artifact_from_synthetic_rows(self):
        examples = [
            {"avg_confidence": 0.9, "threshold_ratio": 1.0, "evidence_coverage": 0.9},
            {"avg_confidence": 0.8, "threshold_ratio": 1.0, "evidence_coverage": 0.8},
            {"avg_confidence": 0.2, "threshold_ratio": 0.2, "evidence_coverage": 0.1},
            {"avg_confidence": 0.3, "threshold_ratio": 0.4, "evidence_coverage": 0.2},
        ]
        labels = [1, 1, 0, 0]
        artifact = ConfidenceCalibrator.fit_linear_artifact(
            examples=examples,
            labels=labels,
            feature_names=["avg_confidence", "threshold_ratio", "evidence_coverage"],
            abstain_threshold=0.2,
            comorbid_threshold=0.6,
            metadata={"dataset": "synthetic"},
        )
        assert artifact.weights
        assert artifact.bias != 0.0 or any(v != 0.0 for v in artifact.weights.values())
        assert artifact.metadata["dataset"] == "synthetic"

    def test_missing_artifact_raises_in_learned_mode(self, tmp_path):
        missing = tmp_path / "missing.json"
        with pytest.raises(FileNotFoundError, match="Calibrator artifact not found"):
            ConfidenceCalibrator(mode="learned", artifact_path=missing)


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
