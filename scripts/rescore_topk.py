#!/usr/bin/env python3
"""Re-score existing JSONL predictions with max_output_labels=K.

Takes only top-K predictions (by original confidence ranking),
recomputes all 11 Table 4 metrics. No GPU needed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from culturedx.eval.lingxidiag_paper import (
    PAPER_12_CLASSES,
    compute_table4_metrics,
    pred_to_parent_list,
)


def load_cases(jsonl_path: Path) -> list[dict]:
    cases = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def truncate_predictions(case: dict, max_labels: int) -> list[str]:
    """Get top-K raw disorder codes from a case, preserving confidence ranking."""
    all_preds: list[str] = []
    primary = case.get("primary_diagnosis")
    if primary:
        all_preds.append(primary)
    comorbid = case.get("comorbid_diagnoses") or []
    all_preds.extend(comorbid)
    return all_preds[:max_labels]


def rescore(jsonl_path: Path, max_labels: int) -> dict:
    cases = load_cases(jsonl_path)
    if not cases:
        return {}

    def get_prediction(case: dict) -> list[str]:
        raw_codes = truncate_predictions(case, max_labels)
        return pred_to_parent_list(raw_codes)

    table4 = compute_table4_metrics(cases, get_prediction)

    # Also compute avg predicted labels
    total_pred = 0
    for case in cases:
        raw_codes = truncate_predictions(case, max_labels)
        parents = pred_to_parent_list(raw_codes)
        total_pred += len(parents)
    table4["avg_pred_labels"] = total_pred / len(cases) if cases else 0

    return table4


def fmt(v, width=7):
    if v is None:
        return " " * width
    if isinstance(v, int):
        return f"{v:>{width}}"
    return f"{v:>{width}.3f}"


def main():
    base_dir = PROJECT_ROOT / "outputs" / "eval" / "rescore_gate_only_20260402_223720"
    conditions = ["single-baseline", "hied-baseline", "hied-evidence"]

    for max_k in [1, 2]:
        print(f"\n{'='*80}")
        print(f"  max_output_labels = {max_k}")
        print(f"{'='*80}")

        header_metrics = [
            "2c_Acc", "2c_F1m", "2c_F1w",
            "4c_Acc", "4c_F1m", "4c_F1w",
            "12c_Acc", "12c_T1", "12c_T3", "12c_F1m", "12c_F1w",
            "Overall", "avg_lbl",
        ]
        print(f"{'Condition':<20}", "  ".join(f"{m:>7}" for m in header_metrics))
        print("-" * 130)

        for cond in conditions:
            jsonl_path = base_dir / cond / "results_lingxidiag.jsonl"
            if not jsonl_path.exists():
                print(f"{cond:<20}  MISSING")
                continue

            t = rescore(jsonl_path, max_k)
            vals = [
                t.get("2class_Acc"), t.get("2class_F1_macro"), t.get("2class_F1_weighted"),
                t.get("4class_Acc"), t.get("4class_F1_macro"), t.get("4class_F1_weighted"),
                t.get("12class_Acc"), t.get("12class_Top1"), t.get("12class_Top3"),
                t.get("12class_F1_macro"), t.get("12class_F1_weighted"),
                t.get("Overall"), t.get("avg_pred_labels"),
            ]
            print(f"{cond:<20}", "  ".join(fmt(v) for v in vals))

    # Also show the original (no truncation) for comparison
    print(f"\n{'='*80}")
    print(f"  Original (no truncation)")
    print(f"{'='*80}")
    header_metrics = [
        "2c_Acc", "2c_F1m", "2c_F1w",
        "4c_Acc", "4c_F1m", "4c_F1w",
        "12c_Acc", "12c_T1", "12c_T3", "12c_F1m", "12c_F1w",
        "Overall", "avg_lbl",
    ]
    print(f"{'Condition':<20}", "  ".join(f"{m:>7}" for m in header_metrics))
    print("-" * 130)

    for cond in conditions:
        jsonl_path = base_dir / cond / "results_lingxidiag.jsonl"
        if not jsonl_path.exists():
            continue
        t = rescore(jsonl_path, max_labels=99)
        vals = [
            t.get("2class_Acc"), t.get("2class_F1_macro"), t.get("2class_F1_weighted"),
            t.get("4class_Acc"), t.get("4class_F1_macro"), t.get("4class_F1_weighted"),
            t.get("12class_Acc"), t.get("12class_Top1"), t.get("12class_Top3"),
            t.get("12class_F1_macro"), t.get("12class_F1_weighted"),
            t.get("Overall"), t.get("avg_pred_labels"),
        ]
        print(f"{cond:<20}", "  ".join(fmt(v) for v in vals))


if __name__ == "__main__":
    main()
