"""Tests for statistical_tests module."""
from __future__ import annotations

import pytest

from culturedx.eval.statistical_tests import (
    McNemarResult,
    mcnemar_test,
    pairwise_mcnemar,
    format_mcnemar_table,
)


class TestMcNemarTest:
    def test_identical_classifiers(self):
        correct = [True, True, False, True, False]
        result = mcnemar_test(correct, correct)
        assert result["statistic"] == 0.0
        assert result["p_value"] == 1.0
        assert not result["significant"]

    def test_clearly_different(self):
        # Mode A: correct on 80 cases, wrong on 20
        # Mode B: correct on 20 cases, wrong on 80
        # Discordant: A-only=60, B-only=0 (extreme case)
        a = [True] * 80 + [False] * 20
        b = [True] * 20 + [False] * 80
        result = mcnemar_test(a, b)
        assert result["n_a_only"] == 60
        assert result["n_b_only"] == 0
        assert result["p_value"] < 0.001
        assert result["significant"]

    def test_symmetric(self):
        a = [True, False, True, False, True]
        b = [False, True, True, False, True]
        r1 = mcnemar_test(a, b)
        r2 = mcnemar_test(b, a)
        assert r1["statistic"] == r2["statistic"]
        assert r1["p_value"] == r2["p_value"]

    def test_length_mismatch(self):
        with pytest.raises(ValueError, match="Lengths must match"):
            mcnemar_test([True, False], [True])

    def test_no_discordant(self):
        # All agree
        a = [True, True, False, False]
        b = [True, True, False, False]
        result = mcnemar_test(a, b)
        assert result["p_value"] == 1.0

    def test_small_sample(self):
        a = [True, False, True, True, False, True, True, False, True, True]
        b = [True, True, False, True, True, False, True, True, False, True]
        result = mcnemar_test(a, b)
        assert 0.0 <= result["p_value"] <= 1.0
        assert result["statistic"] >= 0.0


class TestPairwiseMcNemar:
    def test_three_modes(self):
        results = pairwise_mcnemar({
            "hied": [True, True, False, True, False, True],
            "single": [True, False, True, True, False, True],
            "psycot": [False, True, True, False, True, True],
        })
        assert len(results) == 3  # 3 choose 2
        # Check Bonferroni correction: alpha/3
        for r in results:
            assert abs(r.corrected_alpha - 0.05 / 3) < 1e-10

    def test_single_mode(self):
        results = pairwise_mcnemar({"hied": [True, False]})
        assert len(results) == 0

    def test_format_table(self):
        results = pairwise_mcnemar({
            "hied": [True, False, True],
            "single": [False, True, True],
        })
        table = format_mcnemar_table(results)
        assert "Mode A" in table
        assert "hied" in table
        assert "single" in table
