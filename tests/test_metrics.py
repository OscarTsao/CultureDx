# tests/test_metrics.py
"""Tests for evaluation metrics."""
import pytest
from culturedx.eval.metrics import (
    top_k_accuracy,
    macro_f1,
    binary_f1,
    mae,
    rmse,
    pearson_r,
    compute_diagnosis_metrics,
    compute_severity_metrics,
)


class TestDiagnosisMetrics:
    def test_top1_accuracy_perfect(self):
        preds = [["F32"], ["F41.1"], ["F32"]]
        golds = [["F32"], ["F41.1"], ["F32"]]
        assert top_k_accuracy(preds, golds, k=1) == 1.0

    def test_top1_accuracy_half(self):
        preds = [["F32"], ["F41.1"]]
        golds = [["F32"], ["F32"]]
        assert top_k_accuracy(preds, golds, k=1) == 0.5

    def test_top3_accuracy(self):
        preds = [["F41.1", "F32", "F43.1"]]
        golds = [["F32"]]
        assert top_k_accuracy(preds, golds, k=3) == 1.0

    def test_topk_uses_primary_gold_not_any_gold(self):
        preds = [["F41.1", "F32"]]
        golds = [["F32", "F41.1"]]
        assert top_k_accuracy(preds, golds, k=1) == 0.0
        assert top_k_accuracy(preds, golds, k=3) == 1.0

    def test_macro_f1(self):
        preds = ["F32", "F32", "F41.1", "F41.1"]
        golds = ["F32", "F41.1", "F41.1", "F41.1"]
        f1 = macro_f1(preds, golds)
        assert 0.0 < f1 < 1.0


class TestSeverityMetrics:
    def test_mae_perfect(self):
        preds = [10.0, 5.0, 15.0]
        golds = [10.0, 5.0, 15.0]
        assert mae(preds, golds) == 0.0

    def test_mae_known(self):
        preds = [10.0, 5.0]
        golds = [12.0, 3.0]
        assert mae(preds, golds) == 2.0

    def test_rmse_known(self):
        preds = [10.0, 5.0]
        golds = [12.0, 3.0]
        assert abs(rmse(preds, golds) - 2.0) < 1e-6

    def test_pearson_r_perfect(self):
        preds = [1.0, 2.0, 3.0, 4.0, 5.0]
        golds = [1.0, 2.0, 3.0, 4.0, 5.0]
        r = pearson_r(preds, golds)
        assert abs(r - 1.0) < 1e-6

    def test_binary_f1(self):
        preds = [1, 1, 0, 0]
        golds = [1, 0, 0, 1]
        f1 = binary_f1(preds, golds)
        assert 0.0 < f1 < 1.0


class TestComputeHelpers:
    def test_compute_diagnosis_metrics(self):
        preds = [["F32"], ["F41.1"]]
        golds = [["F32"], ["F41.1"]]
        metrics = compute_diagnosis_metrics(preds, golds)
        assert "accuracy" in metrics
        assert "top1_accuracy" in metrics
        assert "macro_f1" in metrics
        assert "weighted_f1" in metrics
        assert "overall" in metrics
        assert metrics["accuracy"] == 1.0
        assert metrics["top1_accuracy"] == 1.0

    def test_compute_diagnosis_metrics_matches_primary_label_methodology(self):
        preds = [["F41.1", "F32"], ["F32"]]
        golds = [["F32", "F41.1"], ["F32"]]
        metrics = compute_diagnosis_metrics(preds, golds)
        assert metrics["accuracy"] == pytest.approx(0.5)
        assert metrics["top1_accuracy"] == pytest.approx(0.5)
        assert metrics["top3_accuracy"] == pytest.approx(1.0)
        assert metrics["macro_f1"] == pytest.approx(1 / 3)
        assert metrics["weighted_f1"] == pytest.approx(2 / 3)
        assert metrics["overall"] == pytest.approx(0.6)

    def test_compute_diagnosis_metrics_accuracy_is_ordered_exact_match(self):
        preds = [["F32", "F41.1"], ["F41.1"]]
        golds = [["F32"], ["F41.1"]]
        metrics = compute_diagnosis_metrics(preds, golds)
        assert metrics["accuracy"] == pytest.approx(0.5)
        assert metrics["top1_accuracy"] == pytest.approx(1.0)

    def test_compute_severity_metrics(self):
        preds = [10.0, 5.0]
        golds = [12.0, 3.0]
        metrics = compute_severity_metrics(preds, golds)
        assert "mae" in metrics
        assert "rmse" in metrics
        assert "pearson_r" in metrics
