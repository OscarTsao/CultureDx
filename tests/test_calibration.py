"""Tests for confidence calibration analysis."""
from __future__ import annotations

import pytest

from culturedx.eval.calibration import (
    CalibrationResult,
    compute_calibration,
    format_calibration_table,
    format_reliability_diagram_data,
)


class TestComputeCalibration:
    def test_perfect_calibration(self):
        """Perfectly calibrated: confidence matches accuracy in each bin."""
        # 10 predictions, each with confidence = actual accuracy
        confidences = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        correct = [False, False, False, False, True, True, True, True, True, True]
        result = compute_calibration(confidences, correct, n_bins=5, mode="test")
        # ECE should be low (not necessarily 0 due to binning)
        assert result.ece < 0.3
        assert result.n_samples == 10

    def test_overconfident(self):
        """All predictions at 0.95 confidence but only 50% correct → high ECE."""
        confidences = [0.95] * 20
        correct = [True] * 10 + [False] * 10
        result = compute_calibration(confidences, correct, n_bins=10, mode="overconf")
        assert result.ece > 0.3  # Should be ~0.45
        assert result.avg_confidence > 0.9
        assert abs(result.overall_accuracy - 0.5) < 0.01

    def test_empty_input(self):
        result = compute_calibration([], [], mode="empty")
        assert result.ece == 0.0
        assert result.n_samples == 0

    def test_length_mismatch(self):
        with pytest.raises(ValueError, match="Length mismatch"):
            compute_calibration([0.5], [True, False])

    def test_mce_is_max_bin_error(self):
        """MCE should be the maximum calibration error across bins."""
        confidences = [0.1] * 5 + [0.9] * 5
        correct = [True] * 5 + [False] * 5
        result = compute_calibration(confidences, correct, n_bins=10)
        # Bin 1 (0.0-0.1): conf=0.1, acc=1.0, error=0.9
        # Bin 9 (0.8-0.9): conf=0.9, acc=0.0, error=0.9
        assert result.mce >= 0.8

    def test_single_prediction(self):
        result = compute_calibration([0.8], [True], mode="single")
        assert result.n_samples == 1
        assert result.ece == pytest.approx(0.2)  # |0.8 - 1.0| = 0.2


class TestFormatting:
    def test_table_format(self):
        result = CalibrationResult(
            mode="hied", ece=0.294, mce=0.45, n_samples=200,
            overall_accuracy=0.515, avg_confidence=0.82,
        )
        table = format_calibration_table([result])
        assert "hied" in table
        assert "0.294" in table
        assert "Mode" in table

    def test_diagram_data(self):
        from culturedx.eval.calibration import CalibrationBin
        result = CalibrationResult(
            mode="test", ece=0.1, mce=0.2,
            bins=[CalibrationBin(0.0, 0.5, 0.25, 0.30, 50)],
        )
        data = format_reliability_diagram_data(result)
        assert "Reliability Diagram" in data
        assert "0.25" in data


class TestPlattCalibrator:
    """Tests for PlattCalibrator post-hoc calibration."""

    def test_fit_transform_roundtrip(self):
        """Fit on synthetic data and verify transform produces valid probabilities."""
        from culturedx.eval.calibration import PlattCalibrator

        # Create data: high confidence correct, low confidence wrong
        confidences = [0.9, 0.85, 0.8, 0.75, 0.7, 0.3, 0.25, 0.2, 0.15, 0.1]
        correct = [True, True, True, True, True, False, False, False, False, False]

        cal = PlattCalibrator()
        cal.fit(confidences, correct)

        assert cal.fitted
        assert cal.a != 0.0  # Should learn non-trivial slope

        # Transform should produce values in [0, 1]
        for c in confidences:
            t = cal.transform(c)
            assert 0.0 <= t <= 1.0

        # High confidence should map to higher calibrated value than low
        assert cal.transform(0.9) > cal.transform(0.1)

    def test_transform_batch(self):
        from culturedx.eval.calibration import PlattCalibrator

        confidences = [0.9, 0.8, 0.5, 0.2, 0.1]
        correct = [True, True, True, False, False]

        cal = PlattCalibrator()
        cal.fit(confidences, correct)

        batch = cal.transform_batch([0.3, 0.7])
        assert len(batch) == 2
        assert all(0.0 <= v <= 1.0 for v in batch)

    def test_save_load_roundtrip(self, tmp_path):
        from culturedx.eval.calibration import PlattCalibrator

        cal = PlattCalibrator()
        cal.a = 2.5
        cal.b = -1.3
        cal.optimal_threshold = 0.42
        cal.fitted = True

        save_path = tmp_path / "platt.json"
        cal.save(save_path)

        loaded = PlattCalibrator.load(save_path)
        assert loaded.a == pytest.approx(2.5)
        assert loaded.b == pytest.approx(-1.3)
        assert loaded.optimal_threshold == pytest.approx(0.42)
        assert loaded.fitted

        # Transform should match
        assert cal.transform(0.5) == pytest.approx(loaded.transform(0.5))

    def test_unfitted_returns_identity(self):
        from culturedx.eval.calibration import PlattCalibrator

        cal = PlattCalibrator()
        # Unfitted: a=0, b=0 → sigmoid(0) = 0.5 for all inputs
        result = cal.transform(0.8)
        assert result == pytest.approx(0.5)


class TestRiskCoverageCurve:
    """Tests for compute_risk_coverage_curve."""

    def test_perfect_ordering(self):
        """5 correct at top, 5 wrong at bottom → 100% accuracy at 50% coverage."""
        from culturedx.eval.calibration import compute_risk_coverage_curve

        confidences = [0.95, 0.9, 0.85, 0.8, 0.75, 0.25, 0.2, 0.15, 0.1, 0.05]
        correct = [True, True, True, True, True, False, False, False, False, False]

        curve = compute_risk_coverage_curve(confidences, correct, n_points=10)
        assert len(curve) == 10

        # At 50% coverage (top 5), accuracy should be 1.0
        at_50 = next(p for p in curve if p["coverage"] == pytest.approx(0.5, abs=0.05))
        assert at_50["accuracy"] == pytest.approx(1.0)
        assert at_50["risk"] == pytest.approx(0.0)

        # At 100% coverage, accuracy should be 0.5
        at_100 = curve[-1]
        assert at_100["coverage"] == pytest.approx(1.0)
        assert at_100["accuracy"] == pytest.approx(0.5)

    def test_empty_input(self):
        from culturedx.eval.calibration import compute_risk_coverage_curve

        curve = compute_risk_coverage_curve([], [], n_points=10)
        assert curve == []

    def test_all_correct(self):
        from culturedx.eval.calibration import compute_risk_coverage_curve

        confidences = [0.9, 0.8, 0.7, 0.6, 0.5]
        correct = [True, True, True, True, True]

        curve = compute_risk_coverage_curve(confidences, correct, n_points=5)
        # All points should have accuracy 1.0
        for point in curve:
            assert point["accuracy"] == pytest.approx(1.0)
            assert point["risk"] == pytest.approx(0.0)

    def test_monotonically_increasing_coverage(self):
        from culturedx.eval.calibration import compute_risk_coverage_curve

        confidences = [0.9, 0.7, 0.5, 0.3, 0.1]
        correct = [True, False, True, False, True]

        curve = compute_risk_coverage_curve(confidences, correct, n_points=5)
        coverages = [p["coverage"] for p in curve]
        assert coverages == sorted(coverages)
