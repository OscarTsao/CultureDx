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
