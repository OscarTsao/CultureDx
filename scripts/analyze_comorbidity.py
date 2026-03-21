#!/usr/bin/env python3
"""Retrospective comorbidity evaluation for existing sweep predictions.

Loads predictions.json + case_list.json from sweep directories, computes:
1. Comorbidity metrics (7 metrics from compute_comorbidity_metrics)
2. LingxiDiag 4-class accuracy (Depression/Anxiety/Mixed/Other)

Usage:
    uv run python scripts/analyze_comorbidity.py \
        --sweep-dirs outputs/sweeps/v10_lingxidiag_* \
        --dataset lingxidiag16k

    uv run python scripts/analyze_comorbidity.py \
        --sweep-dirs outputs/sweeps/contrastive_*_lingxidiag_* \
        --dataset lingxidiag16k --four-class
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.eval.metrics import compute_comorbidity_metrics


# ---------------------------------------------------------------------------
# 4-class mapping (LingxiDiag task)
# ---------------------------------------------------------------------------

def predict_four_class(primary: str | None, comorbid: list[str]) -> str:
    """Map prediction to LingxiDiag 4-class label.

    Rules (validated against raw LingxiDiag data):
      Depression: F32.x or F33.x only
      Anxiety:    F40.x or F41.x only (NOT F42/F43)
      Mixed:      Both depression AND anxiety codes present
      Other:      Everything else (F42, F43, F39, F45, F51, F98, ...)
    """
    all_codes = [c for c in [primary] + (comorbid or []) if c]
    has_dep = any(c.startswith("F32") or c.startswith("F33") for c in all_codes)
    has_anx = any(c.startswith("F40") or c.startswith("F41") for c in all_codes)
    if has_dep and has_anx:
        return "Mixed"
    if has_dep:
        return "Depression"
    if has_anx:
        return "Anxiety"
    return "Other"


def gold_four_class(diagnoses: list[str]) -> str:
    """Map gold diagnoses to LingxiDiag 4-class label.

    Gold labels use parent codes (F32, F41, etc.).
    F41.2 in raw data maps to "Mixed" in the 4-class scheme.
    """
    codes = [c.split(".")[0] for c in diagnoses]
    has_dep = any(c in ("F32", "F33") for c in codes)
    has_anx = any(c in ("F40", "F41") for c in codes)
    # F41.2 = mixed anxiety-depressive disorder
    if any(d.startswith("F41.2") for d in diagnoses):
        return "Mixed"
    if has_dep and has_anx:
        return "Mixed"
    if has_dep:
        return "Depression"
    if has_anx:
        return "Anxiety"
    return "Other"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_sweep(sweep_dir: Path) -> tuple[list[dict], dict[str, list[str]]]:
    """Load case_list.json gold labels and find condition dirs.

    Returns:
        (condition_list, gold_map)
        condition_list: list of {"name": str, "predictions": list[dict]}
        gold_map: {case_id: [diagnoses]}
    """
    case_list_path = sweep_dir / "case_list.json"
    if not case_list_path.exists():
        print(f"  WARNING: {case_list_path} not found, skipping", file=sys.stderr)
        return [], {}

    with open(case_list_path, encoding="utf-8") as f:
        case_data = json.load(f)

    gold_map = {c["case_id"]: c["diagnoses"] for c in case_data["cases"]}

    conditions = []
    for sub in sorted(sweep_dir.iterdir()):
        pred_path = sub / "predictions.json"
        if not pred_path.exists():
            continue
        with open(pred_path, encoding="utf-8") as f:
            pred_data = json.load(f)
        preds = pred_data.get("predictions", [])
        conditions.append({"name": sub.name, "predictions": preds})

    return conditions, gold_map


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze_condition(
    name: str,
    predictions: list[dict],
    gold_map: dict[str, list[str]],
    four_class: bool = False,
) -> dict:
    """Compute comorbidity + optional 4-class metrics for one condition."""
    preds_lists = []
    golds_lists = []

    for p in predictions:
        case_id = p["case_id"]
        gold = gold_map.get(case_id)
        if gold is None:
            continue
        pred_dx = [p["primary_diagnosis"]] if p["primary_diagnosis"] else ["unknown"]
        pred_dx += p.get("comorbid_diagnoses", [])
        preds_lists.append(pred_dx)
        golds_lists.append(gold)

    result = {"condition": name, "n_cases": len(preds_lists)}

    # Comorbidity metrics
    comorbid = compute_comorbidity_metrics(preds_lists, golds_lists)
    result["comorbidity"] = comorbid

    # 4-class metrics
    if four_class:
        pred_classes = []
        gold_classes = []
        for p, g in zip(predictions, [gold_map.get(p["case_id"], []) for p in predictions]):
            if not g:
                continue
            pred_classes.append(predict_four_class(
                p["primary_diagnosis"], p.get("comorbid_diagnoses", []),
            ))
            gold_classes.append(gold_four_class(g))

        if pred_classes:
            from sklearn.metrics import (
                accuracy_score,
                classification_report,
                confusion_matrix,
            )

            labels = ["Depression", "Anxiety", "Mixed", "Other"]
            acc = accuracy_score(gold_classes, pred_classes)
            report = classification_report(
                gold_classes, pred_classes, labels=labels,
                output_dict=True, zero_division=0,
            )
            cm = confusion_matrix(gold_classes, pred_classes, labels=labels)

            result["four_class"] = {
                "accuracy": acc,
                "per_class": {
                    lab: {
                        "precision": report[lab]["precision"],
                        "recall": report[lab]["recall"],
                        "f1": report[lab]["f1-score"],
                        "support": report[lab]["support"],
                    }
                    for lab in labels
                },
                "confusion_matrix": cm.tolist(),
                "labels": labels,
                "macro_f1": report["macro avg"]["f1-score"],
            }

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Retrospective comorbidity analysis")
    parser.add_argument(
        "--sweep-dirs", nargs="+", required=True,
        help="Sweep output directories (supports glob via shell expansion)",
    )
    parser.add_argument(
        "--dataset", default=None,
        help="Dataset name (for context in output)",
    )
    parser.add_argument(
        "--four-class", action="store_true",
        help="Compute LingxiDiag 4-class metrics (Depression/Anxiety/Mixed/Other)",
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Save comorbidity_metrics.json next to each predictions.json",
    )
    args = parser.parse_args()

    all_results = []

    for sweep_dir_str in args.sweep_dirs:
        sweep_dir = Path(sweep_dir_str)
        if not sweep_dir.is_dir():
            print(f"WARNING: {sweep_dir} not a directory, skipping", file=sys.stderr)
            continue

        print(f"\n{'='*70}")
        print(f"Sweep: {sweep_dir.name}")
        print(f"{'='*70}")

        conditions, gold_map = load_sweep(sweep_dir)
        if not conditions:
            print("  No conditions found.")
            continue

        for cond in conditions:
            result = analyze_condition(
                name=f"{sweep_dir.name}/{cond['name']}",
                predictions=cond["predictions"],
                gold_map=gold_map,
                four_class=args.four_class,
            )
            all_results.append(result)

            # Print summary
            cm = result["comorbidity"]
            print(f"\n  {cond['name']} (n={result['n_cases']})")
            print(f"    hamming_acc={cm['hamming_accuracy']:.3f}  "
                  f"subset_acc={cm['subset_accuracy']:.3f}  "
                  f"comorbid_f1={cm['comorbidity_detection_f1']:.3f}")
            print(f"    label_coverage={cm['label_coverage']:.3f}  "
                  f"label_precision={cm['label_precision']:.3f}  "
                  f"avg_pred={cm['avg_predicted_labels']:.2f}  "
                  f"avg_gold={cm['avg_gold_labels']:.2f}")

            if "four_class" in result:
                fc = result["four_class"]
                print(f"    4-class accuracy={fc['accuracy']:.3f}  "
                      f"macro_f1={fc['macro_f1']:.3f}")
                for lab in fc["labels"]:
                    pc = fc["per_class"][lab]
                    print(f"      {lab:12s}  P={pc['precision']:.3f}  "
                          f"R={pc['recall']:.3f}  F1={pc['f1']:.3f}  "
                          f"n={pc['support']}")

            # Save per-condition
            if args.save:
                cond_dir = sweep_dir / cond["name"].split("/")[-1]
                save_path = cond_dir / "comorbidity_metrics.json"
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"    Saved: {save_path}")

    # Summary table
    if len(all_results) > 1:
        print(f"\n{'='*70}")
        print("SUMMARY TABLE")
        print(f"{'='*70}")
        header = f"{'Condition':45s} {'hamm':>5s} {'sub':>5s} {'cmF1':>5s} {'cov':>5s} {'prec':>5s}"
        if args.four_class:
            header += f" {'4cl':>5s} {'4mF1':>5s}"
        print(header)
        print("-" * len(header))

        for r in all_results:
            cm = r["comorbidity"]
            row = (f"{r['condition']:45s} "
                   f"{cm['hamming_accuracy']:5.3f} "
                   f"{cm['subset_accuracy']:5.3f} "
                   f"{cm['comorbidity_detection_f1']:5.3f} "
                   f"{cm['label_coverage']:5.3f} "
                   f"{cm['label_precision']:5.3f}")
            if args.four_class and "four_class" in r:
                fc = r["four_class"]
                row += f" {fc['accuracy']:5.3f} {fc['macro_f1']:5.3f}"
            print(row)


if __name__ == "__main__":
    main()
