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


def test_ambiguous_mapping() -> None:
    assert AMBIGUOUS_MAP["F41"] == ["F41.0", "F41.1"]
    assert map_dataset_code("F41") == ["F41.0", "F41.1"]


def test_excluded_code_maps_to_empty_list() -> None:
    assert "Others" in EXCLUDED_CODES
    assert map_dataset_code("Others") == []


def test_map_code_list_drops_excluded_and_deduplicates() -> None:
    assert map_code_list(["F39", "Others", "F39"]) == ["F39"]


def test_is_correct_prediction_accepts_ambiguous_gold_child_prediction() -> None:
    assert is_correct_prediction(["F41.1"], ["F41"])


def test_is_correct_prediction_rejects_sibling_subcodes() -> None:
    assert not is_correct_prediction(["F41.0"], ["F41.1"])


def test_is_correct_prediction_accepts_parent_child_equivalence() -> None:
    assert is_correct_prediction(["F20.0"], ["F20"])
