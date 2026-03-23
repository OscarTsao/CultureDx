"""Tests for demographic prior computation."""
from __future__ import annotations

import pytest

from culturedx.ontology.demographic_priors import compute_demographic_prior


class TestDemographicPrior:
    def test_female_depression_in_range(self):
        """Female, age 30, F32 → should be > 0.5 (female bias + in age range)."""
        score = compute_demographic_prior("F32", age=30, gender="女")
        assert score > 0.5

    def test_male_schizophrenia_in_range(self):
        """Male, age 25, F20 → should be > 0.5 (male bias + in age range)."""
        score = compute_demographic_prior("F20", age=25, gender="男")
        assert score > 0.5

    def test_no_info_neutral(self):
        """No age, no gender → exactly 0.5."""
        score = compute_demographic_prior("F32", age=None, gender=None)
        assert score == pytest.approx(0.5)

    def test_male_outside_range_depression(self):
        """Male, age 80, F32 → should be < 0.5 (male + outside age range)."""
        score = compute_demographic_prior("F32", age=80, gender="男")
        assert score < 0.5

    def test_gender_string_variants(self):
        """All female string variants produce the same result."""
        variants = ["女", "female", "Female", "F", "f"]
        scores = [compute_demographic_prior("F32", gender=g) for g in variants]
        for s in scores:
            assert s == pytest.approx(scores[0])

    def test_unknown_gender_neutral(self):
        """Unknown gender string → gender factor is 0.5."""
        score = compute_demographic_prior("F32", age=None, gender="其他")
        assert score == pytest.approx(0.5)

    def test_unknown_disorder_neutral(self):
        """Unknown disorder code → ratio=1.0, neutral."""
        score = compute_demographic_prior("F99", age=None, gender="女")
        assert score == pytest.approx(0.5)

    def test_age_only(self):
        """Age only, no gender → uses age factor alone."""
        in_range = compute_demographic_prior("F20", age=25, gender=None)
        out_range = compute_demographic_prior("F20", age=60, gender=None)
        assert in_range > out_range

    def test_gender_only(self):
        """Gender only, no age → uses gender factor alone."""
        female = compute_demographic_prior("F41.1", age=None, gender="女")
        male = compute_demographic_prior("F41.1", age=None, gender="男")
        assert female > male  # F41.1 ratio 1.8 = more common in females

    def test_score_bounded(self):
        """Score should always be in [0, 1]."""
        for code in ["F32", "F20", "F41.1", "F42", "F51"]:
            for age in [5, 15, 30, 50, 80, None]:
                for gender in ["女", "男", None]:
                    score = compute_demographic_prior(code, age=age, gender=gender)
                    assert 0.0 <= score <= 1.0

    def test_ocd_gender_neutral(self):
        """F42 has ratio 1.0 → gender doesn't affect score."""
        female = compute_demographic_prior("F42", age=None, gender="女")
        male = compute_demographic_prior("F42", age=None, gender="男")
        assert female == pytest.approx(male)
