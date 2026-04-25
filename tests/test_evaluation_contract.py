"""Unit tests for the LingxiDiag paper evaluation contract."""
from __future__ import annotations

from culturedx.eval.lingxidiag_paper import (
    PAPER_12_CLASSES,
    classify_2class_from_raw,
    compute_table4_metrics_v2,
    to_paper_parent,
)


class TestPaperParent:
    def test_f32_subcodes(self) -> None:
        for code in ["F32", "F32.0", "F32.1", "F32.2", "F32.9"]:
            assert to_paper_parent(code) == "F32"

    def test_f41_subcodes(self) -> None:
        for code in ["F41", "F41.0", "F41.1", "F41.2", "F41.9"]:
            assert to_paper_parent(code) == "F41"

    def test_f33_collapses_to_others(self) -> None:
        for code in ["F33", "F33.0", "F33.1"]:
            assert to_paper_parent(code) == "Others"

    def test_none_returns_others(self) -> None:
        assert to_paper_parent(None) == "Others"

    def test_empty_returns_others(self) -> None:
        assert to_paper_parent("") == "Others"


class Test2ClassF412:
    def test_pure_f32(self) -> None:
        assert classify_2class_from_raw("F32") == "Depression"

    def test_pure_f41(self) -> None:
        assert classify_2class_from_raw("F41") == "Anxiety"

    def test_f41_2_excluded(self) -> None:
        assert classify_2class_from_raw("F41.2") is None

    def test_f32_f41_comorbid_excluded(self) -> None:
        assert classify_2class_from_raw("F32,F41") is None


class TestPaperTaxonomy:
    def test_f33_not_included(self) -> None:
        assert "F33" not in PAPER_12_CLASSES

    def test_size_12(self) -> None:
        assert len(PAPER_12_CLASSES) == 12


class TestEvaluationContractV2:
    def test_top1_subset_of_top3_invariant(self) -> None:
        cases = [
            {
                "case_id": "1",
                "raw_gold": "F32",
                "primary": "F32",
                "ranked": ["F41", "F32", "F39"],
                "ml": ["F32"],
            },
        ]

        result = compute_table4_metrics_v2(
            cases,
            get_primary_prediction=lambda c: c["primary"],
            get_ranked_prediction=lambda c: c["ranked"],
            get_multilabel_prediction=lambda c: c["ml"],
            get_raw_gold_code=lambda c: c["raw_gold"],
        )

        assert result["12class_Top1"] == 1.0
        assert result["12class_Top3"] == 1.0
        assert result["12class_Top3"] >= result["12class_Top1"]

    def test_f41_2_in_raw_gold_triggers_2c_exclusion(self) -> None:
        cases = [
            {"raw_gold": "F32", "primary": "F32", "ranked": ["F32"], "ml": ["F32"]},
            {"raw_gold": "F41", "primary": "F41", "ranked": ["F41"], "ml": ["F41"]},
            {"raw_gold": "F41.2", "primary": "F41", "ranked": ["F41"], "ml": ["F41"]},
        ]

        result = compute_table4_metrics_v2(
            cases,
            get_primary_prediction=lambda c: c["primary"],
            get_ranked_prediction=lambda c: c["ranked"],
            get_multilabel_prediction=lambda c: c["ml"],
            get_raw_gold_code=lambda c: c["raw_gold"],
        )

        assert result["2class_n"] == 2

    def test_ranked_and_multilabel_views_are_separate(self) -> None:
        cases = [
            {
                "raw_gold": "F42",
                "primary": "F32",
                "ranked": ["F41", "F42", "F39"],
                "ml": ["F32"],
            },
        ]

        result = compute_table4_metrics_v2(
            cases,
            get_primary_prediction=lambda c: c["primary"],
            get_ranked_prediction=lambda c: c["ranked"],
            get_multilabel_prediction=lambda c: c["ml"],
            get_raw_gold_code=lambda c: c["raw_gold"],
        )

        assert result["12class_Top1"] == 0.0
        assert result["12class_Top3"] == 1.0
        assert result["12class_Acc"] == 0.0

    def test_raw_pred_codes_preserve_mixed_detection(self) -> None:
        cases = [
            {
                "raw_gold": "F41.2",
                "primary": "F41",
                "ranked": ["F41"],
                "ml": ["F41"],
                "raw_pred": ["F41.2"],
            },
        ]

        result = compute_table4_metrics_v2(
            cases,
            get_primary_prediction=lambda c: c["primary"],
            get_ranked_prediction=lambda c: c["ranked"],
            get_multilabel_prediction=lambda c: c["ml"],
            get_raw_gold_code=lambda c: c["raw_gold"],
            get_raw_pred_codes=lambda c: c["raw_pred"],
        )

        assert result["4class_Acc"] == 1.0
