"""Tests for cross-lingual evaluation metrics."""
from __future__ import annotations

import pytest

from culturedx.eval.cross_lingual import (
    aurc,
    evidence_delta,
    paired_bootstrap_test,
    selective_accuracy,
)


class TestEvidenceDelta:
    def test_positive_delta(self):
        # Evidence helps: with > without
        golds = [1, 0, 1, 1, 0, 1, 0, 1]
        with_ev = [1, 0, 1, 1, 0, 1, 0, 1]  # Perfect
        without = [1, 0, 0, 1, 1, 1, 0, 0]  # Worse
        delta = evidence_delta(with_ev, without, golds)
        assert delta > 0

    def test_negative_delta(self):
        # Evidence hurts
        golds = [1, 0, 1, 1, 0]
        with_ev = [0, 1, 0, 1, 0]  # Worse
        without = [1, 0, 1, 1, 0]  # Perfect
        delta = evidence_delta(with_ev, without, golds)
        assert delta < 0

    def test_zero_delta(self):
        golds = [1, 0, 1, 0]
        preds = [1, 0, 1, 0]
        delta = evidence_delta(preds, preds, golds)
        assert delta == 0.0

    def test_macro_f1_metric(self):
        golds = [0, 1, 2, 0, 1, 2]
        with_ev = [0, 1, 2, 0, 1, 2]
        without = [0, 0, 0, 0, 0, 0]
        delta = evidence_delta(with_ev, without, golds, metric="macro_f1")
        assert delta > 0


class TestPairedBootstrap:
    def test_significant_gap(self):
        # Chinese: evidence helps a lot
        cn_gold = [1, 0, 1, 1, 0, 1, 0, 1, 1, 0] * 5
        cn_with = [1, 0, 1, 1, 0, 1, 0, 1, 1, 0] * 5  # Perfect
        cn_without = [1, 1, 0, 1, 0, 0, 0, 1, 0, 0] * 5  # Poor

        # English: evidence doesn't help
        en_gold = [1, 0, 1, 1, 0, 1, 0, 1, 1, 0] * 5
        en_with = [1, 0, 0, 1, 0, 1, 0, 1, 0, 0] * 5
        en_without = [1, 0, 0, 1, 0, 1, 0, 1, 0, 0] * 5  # Same

        result = paired_bootstrap_test(
            cn_with, cn_without, cn_gold,
            en_with, en_without, en_gold,
            n_resamples=1000, seed=42,
        )
        assert result["delta_cn"] > result["delta_en"]
        assert result["observed_gap"] > 0
        assert "p_value" in result
        assert "ci_95_lower" in result

    def test_no_gap(self):
        golds = [1, 0, 1, 0, 1] * 10
        preds = [1, 0, 1, 0, 1] * 10
        result = paired_bootstrap_test(
            preds, preds, golds,
            preds, preds, golds,
            n_resamples=100, seed=42,
        )
        assert result["observed_gap"] == 0.0


class TestAURC:
    def test_perfect_predictions(self):
        confidences = [0.9, 0.8, 0.7, 0.6]
        correct = [True, True, True, True]
        score = aurc(confidences, correct)
        assert score == pytest.approx(0.0, abs=0.01)

    def test_worst_predictions(self):
        confidences = [0.9, 0.8, 0.7, 0.6]
        correct = [False, False, False, False]
        score = aurc(confidences, correct)
        assert score > 0.5

    def test_empty(self):
        assert aurc([], []) == 1.0

    def test_mixed_ordering_matters(self):
        # Good: high confidence = correct
        good_conf = [0.9, 0.8, 0.3, 0.2]
        good_correct = [True, True, False, False]
        
        # Bad: high confidence = incorrect
        bad_conf = [0.9, 0.8, 0.3, 0.2]
        bad_correct = [False, False, True, True]
        
        assert aurc(good_conf, good_correct) < aurc(bad_conf, bad_correct)


class TestSelectiveAccuracy:
    def test_full_coverage(self):
        result = selective_accuracy(
            confidences=[0.9, 0.8, 0.7, 0.6],
            correct=[True, True, False, True],
            coverage_target=1.0,
        )
        assert result["accuracy"] == 0.75
        assert result["n_selected"] == 4

    def test_partial_coverage(self):
        result = selective_accuracy(
            confidences=[0.9, 0.8, 0.3, 0.2],
            correct=[True, True, False, False],
            coverage_target=0.5,
        )
        # Top 50% by confidence = [0.9, 0.8] = both correct
        assert result["accuracy"] == 1.0
        assert result["n_selected"] == 2

    def test_empty(self):
        result = selective_accuracy([], [], 0.8)
        assert result["accuracy"] == 0.0
