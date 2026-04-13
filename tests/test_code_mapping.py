"""Tests for evaluation code mapping helpers."""
from culturedx.eval.code_mapping import (
    AMBIGUOUS_MAP,
    EXACT_MAP,
    EXCLUDED_CODES,
    is_correct_prediction,
    map_code_list,
    map_dataset_code,
)


def test_exact_mapping() -> None:
    assert EXACT_MAP["F32"] == "F32"
    assert map_dataset_code("F32") == ["F32"]


def test_paper_excluded_codes_are_empty() -> None:
    assert EXCLUDED_CODES == set()


def test_ambiguous_mapping() -> None:
    assert AMBIGUOUS_MAP["F41"] == ["F41.0", "F41.1"]
    assert map_dataset_code("F41") == ["F41.0", "F41.1"]
    assert map_dataset_code("F41.1") == ["F41.1"]


def test_paper_unsupported_parent_codes_map_to_others() -> None:
    assert "F39" in EXACT_MAP
    assert "F98" in EXACT_MAP
    assert "F22" not in EXACT_MAP
    assert "F33" not in EXACT_MAP
    assert "F40" not in EXACT_MAP
    assert map_dataset_code("F22") == ["Others"]
    assert map_dataset_code("F33") == ["Others"]
    assert map_dataset_code("F40") == ["Others"]
    assert map_dataset_code("Z71") == ["Others"]


def test_map_code_list_keeps_others_bucket_and_deduplicates() -> None:
    assert map_code_list(["F39", "Others", "F39", "Z71"]) == ["F39", "Others"]


def test_unmapped_code_falls_back_to_others() -> None:
    assert map_dataset_code("F99") == ["Others"]


def test_is_correct_prediction_accepts_ambiguous_gold_child_prediction() -> None:
    assert is_correct_prediction(["F41.1"], ["F41"])


def test_is_correct_prediction_rejects_sibling_subcodes() -> None:
    assert not is_correct_prediction(["F41.0"], ["F41.1"])


def test_is_correct_prediction_accepts_parent_child_equivalence() -> None:
    assert is_correct_prediction(["F20.0"], ["F20"])
