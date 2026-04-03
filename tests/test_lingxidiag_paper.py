"""Tests for LingxiDiagBench Table 4 paper-aligned evaluation helpers."""
from __future__ import annotations

import culturedx.eval.lingxidiag_paper as lingxidiag_paper

from culturedx.eval.lingxidiag_paper import (
    classify_2class_from_raw,
    classify_4class_from_raw,
    compute_table4_metrics,
    gold_to_parent_list,
    pred_to_parent_list,
    to_paper_parent,
)


def test_to_paper_parent_matches_table4_label_space() -> None:
    assert to_paper_parent("F41.1") == "F41"
    assert to_paper_parent("F41.0") == "F41"
    assert to_paper_parent("F43.2") == "F43"
    assert to_paper_parent("F32.900") == "F32"
    assert to_paper_parent("F39") == "F39"
    assert to_paper_parent("F98") == "F98"
    assert to_paper_parent("Z71.9") == "Z71"
    assert to_paper_parent("F22") == "Others"
    assert to_paper_parent("F33") == "Others"
    assert to_paper_parent("F40") == "Others"
    assert to_paper_parent("garbage") == "Others"


def test_gold_to_parent_list_extracts_multilabel_codes() -> None:
    assert gold_to_parent_list("F32.100;F41.000") == ["F32", "F41"]
    assert gold_to_parent_list("Z71") == ["Z71"]
    assert gold_to_parent_list("") == ["Others"]
    assert gold_to_parent_list("F99.999") == ["Others"]


def test_binary_and_four_class_classification_match_paper_rules() -> None:
    assert classify_2class_from_raw("F32.100") == "Depression"
    assert classify_2class_from_raw("F41.000") == "Anxiety"
    assert classify_2class_from_raw("F32.100;F41.000") is None
    assert classify_2class_from_raw("F41.200") is None
    assert classify_2class_from_raw("F20.000") is None

    assert classify_4class_from_raw("F32.100") == "Depression"
    assert classify_4class_from_raw("F41.000") == "Anxiety"
    assert classify_4class_from_raw("F32.100;F41.000") == "Mixed"
    assert classify_4class_from_raw("F41.200") == "Mixed"
    assert classify_4class_from_raw("F20.000") == "Others"


def test_pred_to_parent_list_collapses_children_and_unknowns() -> None:
    assert pred_to_parent_list(["F41.1", "F32"]) == ["F41", "F32"]
    assert pred_to_parent_list(["F22"]) == ["Others"]
    assert pred_to_parent_list([]) == ["Others"]


def test_compute_table4_metrics_returns_full_metric_row() -> None:
    cases = [
        {"DiagnosisCode": "F32.100", "pred": ["F32"]},
        {"DiagnosisCode": "F41.000", "pred": ["F41"]},
        {"DiagnosisCode": "F32.100;F41.000", "pred": ["F32", "F41"]},
    ]

    metrics = compute_table4_metrics(cases, lambda case: case["pred"])

    assert metrics["2class_Acc"] == 1.0
    assert metrics["2class_F1_macro"] == 1.0
    assert metrics["2class_F1_weighted"] == 1.0
    assert metrics["4class_Acc"] == 1.0
    assert metrics["4class_F1_macro"] == 1.0
    assert metrics["4class_F1_weighted"] == 1.0
    assert metrics["12class_Acc"] == 1.0
    assert metrics["12class_Top1"] == 1.0
    assert metrics["12class_Top3"] == 1.0
    assert metrics["12class_F1_macro"] == 2.0 / 12.0
    assert metrics["12class_F1_weighted"] == 1.0
    assert metrics["2class_n"] == 2
    assert metrics["4class_n"] == 3
    assert metrics["12class_n"] == 3
    assert metrics["Overall"] == (10.0 + (2.0 / 12.0)) / 11.0


def test_compute_table4_metrics_binary_non_target_predictions_stay_outside_label_space(
    monkeypatch,
) -> None:
    captured: dict[str, list[str]] = {}
    original = lingxidiag_paper.compute_singlelabel_metrics

    def capture_singlelabel_metrics(
        y_true: list[str],
        y_pred: list[str],
        labels: list[str],
    ) -> dict[str, float | int]:
        if labels == lingxidiag_paper.PAPER_2_CLASSES:
            captured["y_true"] = list(y_true)
            captured["y_pred"] = list(y_pred)
        return original(y_true, y_pred, labels)

    monkeypatch.setattr(
        lingxidiag_paper,
        "compute_singlelabel_metrics",
        capture_singlelabel_metrics,
    )

    cases = [
        {"DiagnosisCode": "F32.100", "pred": ["F20"]},
        {"DiagnosisCode": "F41.000", "pred": ["F45"]},
    ]

    compute_table4_metrics(cases, lambda case: case["pred"])

    assert captured["y_true"] == ["Depression", "Anxiety"]
    assert captured["y_pred"] == ["Other", "Other"]
