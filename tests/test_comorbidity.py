"""Tests for comorbidity resolver."""
from __future__ import annotations

import pytest

from culturedx.diagnosis.comorbidity import (
    ComorbidityResolver,
    EXCLUSION_RULES,
)


class TestComorbidityResolver:
    def test_single_disorder(self):
        resolver = ComorbidityResolver()
        result = resolver.resolve(["F32"])
        assert result.primary == "F32"
        assert result.comorbid == []
        assert result.excluded == []

    def test_empty_confirmed(self):
        resolver = ComorbidityResolver()
        result = resolver.resolve([])
        assert result.primary == ""

    def test_f33_excludes_f32(self):
        resolver = ComorbidityResolver()
        result = resolver.resolve(["F32", "F33"], confidences={"F33": 0.9, "F32": 0.8})
        assert result.primary == "F33"
        assert "F32" in result.excluded
        assert "F32" not in result.comorbid

    def test_f31_excludes_f32_and_f33(self):
        resolver = ComorbidityResolver()
        result = resolver.resolve(
            ["F31", "F32", "F33"],
            confidences={"F31": 0.9, "F32": 0.7, "F33": 0.8},
        )
        assert result.primary == "F31"
        assert "F32" in result.excluded
        assert "F33" in result.excluded

    def test_valid_comorbidity(self):
        resolver = ComorbidityResolver()
        result = resolver.resolve(
            ["F32", "F41.1"],
            confidences={"F32": 0.9, "F41.1": 0.8},
        )
        assert result.primary == "F32"
        assert "F41.1" in result.comorbid
        assert len(result.excluded) == 0

    def test_max_comorbid_limit(self):
        resolver = ComorbidityResolver(max_comorbid=2)
        result = resolver.resolve(
            ["F32", "F41.1", "F42", "F51"],
            confidences={"F32": 0.9, "F41.1": 0.8, "F42": 0.7, "F51": 0.6},
        )
        assert result.primary == "F32"
        assert len(result.comorbid) <= 2

    def test_exclusion_reasons_populated(self):
        resolver = ComorbidityResolver()
        result = resolver.resolve(
            ["F33", "F32"],
            confidences={"F33": 0.9, "F32": 0.8},
        )
        assert len(result.exclusion_reasons) > 0
        assert "F33 excludes F32" in result.exclusion_reasons

    def test_confidence_ordering(self):
        """Higher confidence disorder becomes primary."""
        resolver = ComorbidityResolver()
        result = resolver.resolve(
            ["F41.1", "F32"],
            confidences={"F41.1": 0.7, "F32": 0.9},
        )
        assert result.primary == "F32"

    def test_schizophrenia_excludes_delusional(self):
        resolver = ComorbidityResolver()
        result = resolver.resolve(
            ["F20", "F22"],
            confidences={"F20": 0.9, "F22": 0.8},
        )
        assert result.primary == "F20"
        assert "F22" in result.excluded

    def test_no_exclusion_between_independent_disorders(self):
        resolver = ComorbidityResolver()
        result = resolver.resolve(
            ["F40", "F51"],
            confidences={"F40": 0.8, "F51": 0.7},
        )
        assert result.primary == "F40"
        assert "F51" in result.comorbid
        assert len(result.excluded) == 0

    def test_default_ratio_no_filtering(self):
        """ratio=0.0 (default) keeps all comorbid — backward compatible."""
        resolver = ComorbidityResolver(comorbid_min_ratio=0.0)
        result = resolver.resolve(
            ["F32", "F41.1", "F42"],
            confidences={"F32": 0.8, "F41.1": 0.5, "F42": 0.3},
        )
        assert result.primary == "F32"
        assert "F41.1" in result.comorbid
        assert "F42" in result.comorbid

    def test_ratio_excludes_low_confidence(self):
        """ratio=0.7: F41.1 (0.5) < 0.7 * 0.8 = 0.56 → excluded."""
        resolver = ComorbidityResolver(comorbid_min_ratio=0.7)
        result = resolver.resolve(
            ["F32", "F41.1"],
            confidences={"F32": 0.8, "F41.1": 0.5},
        )
        assert result.primary == "F32"
        assert "F41.1" not in result.comorbid

    def test_ratio_keeps_sufficient_confidence(self):
        """ratio=0.5: F41.1 (0.5) >= 0.5 * 0.8 = 0.40 → kept."""
        resolver = ComorbidityResolver(comorbid_min_ratio=0.5)
        result = resolver.resolve(
            ["F32", "F41.1"],
            confidences={"F32": 0.8, "F41.1": 0.5},
        )
        assert result.primary == "F32"
        assert "F41.1" in result.comorbid

    def test_exclusion_rules_still_work(self):
        """F33+F32 → F32 excluded by ICD-10 rule regardless of ratio."""
        resolver = ComorbidityResolver(comorbid_min_ratio=0.0)
        result = resolver.resolve(
            ["F33", "F32"],
            confidences={"F33": 0.9, "F32": 0.85},
        )
        assert result.primary == "F33"
        assert "F32" in result.excluded
        assert "F32" not in result.comorbid

    def test_empty_input(self):
        """No confirmed disorders → empty result."""
        resolver = ComorbidityResolver(comorbid_min_ratio=0.5)
        result = resolver.resolve([])
        assert result.primary == ""
        assert result.comorbid == []
        assert result.excluded == []
