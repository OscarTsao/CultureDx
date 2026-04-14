"""LingxiDiagBench Table 4 paper-aligned evaluation.

All definitions are aligned to the official static benchmark:
github.com/Lingxi-mental-health/LingxiDiagBench/evaluation/static/
"""
from __future__ import annotations

import re
from typing import Callable, Optional

import numpy as np
from sklearn.metrics import accuracy_score, f1_score
from sklearn.preprocessing import MultiLabelBinarizer

PAPER_12_CLASSES: list[str] = [
    "F20",
    "F31",
    "F32",
    "F39",
    "F41",
    "F42",
    "F43",
    "F45",
    "F51",
    "F98",
    "Z71",
    "Others",
]
_PAPER_PARENT_SET = {code for code in PAPER_12_CLASSES if code != "Others"}

PAPER_2_CLASSES: list[str] = ["Depression", "Anxiety"]
PAPER_4_CLASSES: list[str] = ["Depression", "Anxiety", "Mixed", "Others"]


def to_paper_parent(code: str) -> str:
    """Collapse any ICD-10 code to the paper's parent-level label set."""
    normalized = code.strip().upper()
    if not normalized:
        return "Others"

    if "Z71" in normalized:
        return "Z71"

    match = re.search(r"F(\d{2})", normalized)
    if not match:
        return "Others"

    parent = f"F{match.group(1)}"
    return parent if parent in _PAPER_PARENT_SET else "Others"


def gold_to_parent_list(diagnosis_code: str) -> list[str]:
    """Extract deduplicated parent-level gold labels from raw DiagnosisCode."""
    if not diagnosis_code:
        return ["Others"]

    extracted: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[;,]", diagnosis_code.strip().upper()):
        part = part.strip().rstrip(",")
        if not part:
            continue
        parent = to_paper_parent(part)
        if parent not in seen and parent != "Others":
            seen.add(parent)
            extracted.append(parent)

    return extracted if extracted else ["Others"]


def pred_to_parent_list(predicted_codes: list[str]) -> list[str]:
    """Collapse CultureDx predictions to the paper's parent-level labels."""
    if not predicted_codes:
        return ["Others"]

    result: list[str] = []
    seen: set[str] = set()
    for code in predicted_codes:
        parent = to_paper_parent(code)
        if parent not in seen and parent != "Others":
            seen.add(parent)
            result.append(parent)
    return result if result else ["Others"]


def classify_2class(gold_parents: list[str]) -> Optional[str]:
    """Binary task on parent-level labels: pure F32 vs pure F41 only."""
    has_f32 = "F32" in gold_parents
    has_f41 = "F41" in gold_parents
    if has_f32 and has_f41:
        return None
    if has_f32 and not has_f41:
        return "Depression"
    if has_f41 and not has_f32:
        return "Anxiety"
    return None


def classify_2class_from_raw(diagnosis_code: str) -> Optional[str]:
    """Binary classification from raw DiagnosisCode, including F41.2 exclusion."""
    if not diagnosis_code:
        return None
    code = diagnosis_code.strip().upper()

    has_f32 = bool(re.search(r"F32", code))
    has_f41 = bool(re.search(r"F41", code))
    has_f41_2 = bool(re.search(r"F41\.2", code))

    if has_f41_2 or (has_f32 and has_f41):
        return None
    if has_f32 and not has_f41:
        return "Depression"
    if has_f41 and not has_f32:
        return "Anxiety"
    return None


def classify_4class_from_raw(diagnosis_code: str) -> str:
    """4-class classification from raw DiagnosisCode."""
    if not diagnosis_code:
        return "Others"
    code = diagnosis_code.strip().upper()

    has_f32 = bool(re.search(r"F32", code))
    has_f41 = bool(re.search(r"F41", code))
    has_f41_2 = bool(re.search(r"F41\.2", code))

    if has_f41_2 or (has_f32 and has_f41):
        return "Mixed"
    if has_f32 and not has_f41:
        return "Depression"
    if has_f41 and not has_f32:
        return "Anxiety"
    return "Others"


def classify_2class_prediction(pred_primary: str) -> str:
    """Map a primary parent-level prediction into the paper's binary task.

    Non-F32/F41 predictions stay outside the 2-class label space as ``Other``.
    The paper metrics still score these correctly because ``accuracy_score``
    and ``f1_score(..., labels=PAPER_2_CLASSES)`` penalize them against the
    gold Depression/Anxiety labels without inventing a target-class confusion.
    """
    if pred_primary == "F32":
        return "Depression"
    if pred_primary == "F41":
        return "Anxiety"
    return "Other"


def compute_singlelabel_metrics(
    y_true: list[str],
    y_pred: list[str],
    labels: list[str],
) -> dict[str, float | int]:
    """Single-label metrics for 2-class and 4-class tasks."""
    present_labels = [label for label in labels if label in set(y_true) or label in set(y_pred)]
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(
            f1_score(
                y_true,
                y_pred,
                labels=present_labels,
                average="macro",
                zero_division=0,
            )
        ),
        "weighted_f1": float(
            f1_score(
                y_true,
                y_pred,
                labels=present_labels,
                average="weighted",
                zero_division=0,
            )
        ),
        "n": len(y_true),
    }


def compute_multilabel_metrics(
    y_true: list[list[str]],
    y_pred: list[list[str]],
    labels: list[str],
) -> dict[str, float | int]:
    """Multi-label metrics for the paper's 12-class task."""
    n = len(y_true)
    if n == 0:
        return {
            "accuracy": 0.0,
            "top1_accuracy": 0.0,
            "top3_accuracy": 0.0,
            "macro_f1": 0.0,
            "weighted_f1": 0.0,
            "n": 0,
        }

    mlb = MultiLabelBinarizer(classes=labels)
    y_true_bin = mlb.fit_transform(y_true)
    y_pred_bin = mlb.transform(y_pred)

    exact_match = sum(1 for truth, pred in zip(y_true, y_pred) if set(truth) == set(pred)) / n
    top1 = sum(1 for truth, pred in zip(y_true, y_pred) if pred and pred[0] in set(truth)) / n
    top3 = sum(1 for truth, pred in zip(y_true, y_pred) if set(pred[:3]) & set(truth)) / n

    return {
        "accuracy": float(exact_match),
        "top1_accuracy": float(top1),
        "top3_accuracy": float(top3),
        "macro_f1": float(f1_score(y_true_bin, y_pred_bin, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y_true_bin, y_pred_bin, average="weighted", zero_division=0)),
        "n": n,
    }


def compute_table4_metrics(
    cases: list[dict],
    get_prediction: Callable[[dict], list[str]],
) -> dict[str, float | int | None]:
    """Compute all 11 Table 4 metrics plus the paper-style overall score."""
    gold_12_all: list[list[str]] = []
    pred_12_all: list[list[str]] = []
    gold_2_all: list[str] = []
    pred_2_all: list[str] = []
    gold_4_all: list[str] = []
    pred_4_all: list[str] = []

    for case in cases:
        raw_code = str(case.get("DiagnosisCode", "") or "")
        gold_parents = gold_to_parent_list(raw_code)
        pred_parents = get_prediction(case)

        gold_12_all.append(gold_parents)
        pred_12_all.append(pred_parents)

        gold_4 = classify_4class_from_raw(raw_code)
        pred_primary = pred_parents[0] if pred_parents else "Others"
        pred_parent_set = set(pred_parents)
        # Also check raw predictions for F41.2 (mixed anxiety-depression)
        raw_pred_codes = case.get("_pred_codes", pred_parents)
        has_pred_f41_2 = any("F41.2" in str(c) for c in raw_pred_codes)
        if has_pred_f41_2 or ("F32" in pred_parent_set and "F41" in pred_parent_set):
            pred_4 = "Mixed"
        elif pred_primary == "F32":
            pred_4 = "Depression"
        elif pred_primary == "F41":
            pred_4 = "Anxiety"
        else:
            pred_4 = "Others"
        gold_4_all.append(gold_4)
        pred_4_all.append(pred_4)

        gold_2 = classify_2class_from_raw(raw_code)
        if gold_2 is not None:
            pred_2 = classify_2class_prediction(pred_primary)
            gold_2_all.append(gold_2)
            pred_2_all.append(pred_2)

    m2 = compute_singlelabel_metrics(gold_2_all, pred_2_all, PAPER_2_CLASSES) if gold_2_all else {}
    m4 = compute_singlelabel_metrics(gold_4_all, pred_4_all, PAPER_4_CLASSES)
    m12 = compute_multilabel_metrics(gold_12_all, pred_12_all, PAPER_12_CLASSES)

    table4 = {
        "2class_Acc": m2.get("accuracy"),
        "2class_F1_macro": m2.get("macro_f1"),
        "2class_F1_weighted": m2.get("weighted_f1"),
        "4class_Acc": m4.get("accuracy"),
        "4class_F1_macro": m4.get("macro_f1"),
        "4class_F1_weighted": m4.get("weighted_f1"),
        "12class_Acc": m12.get("accuracy"),
        "12class_Top1": m12.get("top1_accuracy"),
        "12class_Top3": m12.get("top3_accuracy"),
        "12class_F1_macro": m12.get("macro_f1"),
        "12class_F1_weighted": m12.get("weighted_f1"),
        "2class_n": m2.get("n", 0),
        "4class_n": m4.get("n", 0),
        "12class_n": m12.get("n", 0),
    }
    metric_values = [
        float(value)
        for key, value in table4.items()
        if not key.endswith("_n") and value is not None
    ]
    table4["Overall"] = float(np.mean(metric_values)) if metric_values else None
    return table4


__all__ = [
    "PAPER_12_CLASSES",
    "PAPER_2_CLASSES",
    "PAPER_4_CLASSES",
    "classify_2class",
    "classify_2class_from_raw",
    "classify_2class_prediction",
    "classify_4class_from_raw",
    "compute_multilabel_metrics",
    "compute_singlelabel_metrics",
    "compute_table4_metrics",
    "gold_to_parent_list",
    "pred_to_parent_list",
    "to_paper_parent",
]
