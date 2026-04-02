#!/usr/bin/env python3
"""Re-score validation predictions using trained calibrator.

Uses raw_checker_outputs (all 12 disorders) to re-rank candidates.
Reports Table 4 metrics for max_labels=1 and max_labels=2.
NO GPU needed.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pickle

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from culturedx.eval.lingxidiag_paper import (
    PAPER_12_CLASSES,
    compute_table4_metrics,
    pred_to_parent_list,
    to_paper_parent,
)

MODEL_PATH = PROJECT_ROOT / "outputs" / "calibrator_model" / "calibrator_lr.pkl"

FEATURE_NAMES = [
    "met_count", "total_count", "met_ratio",
    "avg_criterion_confidence",
    "n_met_criteria", "n_notmet_criteria", "n_insufficient_criteria",
    "max_criterion_conf", "min_criterion_conf", "conf_range",
]


def extract_features(co: dict) -> list[float]:
    """Same as training — must match exactly."""
    met = co.get("criteria_met_count", 0)
    total = co.get("criteria_total_count", 1)
    met_ratio = co.get("met_ratio", met / total if total > 0 else 0.0)

    per_crit = co.get("per_criterion", [])
    confs = [c.get("confidence", 0.0) for c in per_crit]
    statuses = [c.get("status", "not_met") for c in per_crit]

    n_met = sum(1 for s in statuses if s == "met")
    n_notmet = sum(1 for s in statuses if s == "not_met")
    n_insuf = sum(1 for s in statuses if s == "insufficient_evidence")

    avg_conf = float(np.mean(confs)) if confs else 0.0
    max_conf = max(confs) if confs else 0.0
    min_conf = min(confs) if confs else 0.0

    return [
        met, total, met_ratio, avg_conf,
        n_met, n_notmet, n_insuf,
        max_conf, min_conf, max_conf - min_conf,
    ]


def rescore_case(case: dict, clf, scaler) -> dict:
    """Re-rank ALL candidates using calibrator probabilities."""
    trace = case.get("decision_trace", {})
    raw_outputs = trace.get("raw_checker_outputs", [])

    if not raw_outputs:
        return case

    scored = []
    for co in raw_outputs:
        features = extract_features(co)
        X = scaler.transform([features])
        prob = float(clf.predict_proba(X)[0][1])
        scored.append({
            "disorder_code": co.get("disorder_code", ""),
            "calibrated_score": prob,
            "met_ratio": co.get("met_ratio", 0.0),
        })

    scored.sort(key=lambda x: x["calibrated_score"], reverse=True)

    rescored = dict(case)
    rescored["rescored_ranked"] = [s["disorder_code"] for s in scored]
    rescored["rescored_scores"] = {s["disorder_code"]: s["calibrated_score"] for s in scored}
    return rescored


def fmt(v, w=7):
    if v is None:
        return " " * w
    if isinstance(v, int):
        return f"{v:>{w}}"
    return f"{v:>{w}.3f}"


def main():
    with open(MODEL_PATH, "rb") as f:
        model_data = pickle.load(f)
    clf = model_data["clf"]
    scaler = model_data["scaler"]
    print(f"Loaded calibrator from {MODEL_PATH}\n")

    # Find validation results with raw_checker_outputs
    val_dir = PROJECT_ROOT / "outputs" / "eval" / "calibrator_validation"
    if not val_dir.exists():
        print(f"Validation dir not found: {val_dir}")
        print("Run HiED on validation split first to generate raw_checker_outputs.")
        return

    conditions = ["hied-baseline", "hied-evidence"]
    header = [
        "2c_Acc", "2c_F1m", "2c_F1w",
        "4c_Acc", "4c_F1m", "4c_F1w",
        "12c_Acc", "12c_T1", "12c_T3", "12c_F1m", "12c_F1w",
        "Overall", "avg_lbl",
    ]

    for mode_label, use_calibrator in [("ORIGINAL", False), ("CALIBRATED", True)]:
        for max_k in [1, 2]:
            print(f"\n{'='*120}")
            print(f"  {mode_label} | max_labels={max_k}")
            print(f"{'='*120}")
            print(f"  {'Condition':<22}", "  ".join(f"{m:>7}" for m in header))
            print("  " + "-" * 130)

            for cond in conditions:
                jsonl_path = val_dir / cond / "results_lingxidiag.jsonl"
                if not jsonl_path.exists():
                    # Try legacy dir
                    jsonl_path = PROJECT_ROOT / "outputs" / "eval" / "rescore_gate_only_20260402_223720" / cond / "results_lingxidiag.jsonl"
                if not jsonl_path.exists():
                    continue

                cases = []
                with open(jsonl_path, encoding="utf-8") as fh:
                    for line in fh:
                        if line.strip():
                            cases.append(json.loads(line))

                if use_calibrator:
                    has_raw = any(c.get("decision_trace", {}).get("raw_checker_outputs") for c in cases)
                    if not has_raw:
                        print(f"  {cond:<22}  (no raw_checker_outputs)")
                        continue
                    rescored = [rescore_case(c, clf, scaler) for c in cases]
                else:
                    rescored = cases

                def get_pred(case, mk=max_k, use_cal=use_calibrator):
                    if use_cal and "rescored_ranked" in case:
                        return pred_to_parent_list(case["rescored_ranked"][:mk])
                    preds = []
                    p = case.get("primary_diagnosis")
                    if p:
                        preds.append(p)
                    preds.extend(case.get("comorbid_diagnoses", []))
                    return pred_to_parent_list(preds[:mk])

                t = compute_table4_metrics(rescored, get_pred)

                total_lbl = sum(
                    len(get_pred(c)) for c in rescored
                )
                avg_lbl = total_lbl / len(rescored) if rescored else 0

                vals = [
                    t.get("2class_Acc"), t.get("2class_F1_macro"), t.get("2class_F1_weighted"),
                    t.get("4class_Acc"), t.get("4class_F1_macro"), t.get("4class_F1_weighted"),
                    t.get("12class_Acc"), t.get("12class_Top1"), t.get("12class_Top3"),
                    t.get("12class_F1_macro"), t.get("12class_F1_weighted"),
                    t.get("Overall"), avg_lbl,
                ]
                print(f"  {cond:<22}", "  ".join(fmt(v) for v in vals))

    # Also show single-baseline for comparison (no calibrator, always original)
    print(f"\n{'='*120}")
    print(f"  SINGLE-BASELINE (reference, no calibrator)")
    print(f"{'='*120}")
    print(f"  {'Condition':<22} {'max':>3}", "  ".join(f"{m:>7}" for m in header))
    print("  " + "-" * 130)

    for max_k in [1]:
        jsonl_path = PROJECT_ROOT / "outputs" / "eval" / "rescore_gate_only_20260402_223720" / "single-baseline" / "results_lingxidiag.jsonl"
        if jsonl_path.exists():
            cases = []
            with open(jsonl_path, encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        cases.append(json.loads(line))

            def get_pred_single(case, mk=max_k):
                preds = []
                p = case.get("primary_diagnosis")
                if p:
                    preds.append(p)
                preds.extend(case.get("comorbid_diagnoses", []))
                return pred_to_parent_list(preds[:mk])

            t = compute_table4_metrics(cases, get_pred_single)
            total_lbl = sum(len(get_pred_single(c)) for c in cases)
            avg_lbl = total_lbl / len(cases) if cases else 0
            vals = [
                t.get("2class_Acc"), t.get("2class_F1_macro"), t.get("2class_F1_weighted"),
                t.get("4class_Acc"), t.get("4class_F1_macro"), t.get("4class_F1_weighted"),
                t.get("12class_Acc"), t.get("12class_Top1"), t.get("12class_Top3"),
                t.get("12class_F1_macro"), t.get("12class_F1_weighted"),
                t.get("Overall"), avg_lbl,
            ]
            print(f"  {'single-baseline':<22} {max_k:>3}", "  ".join(fmt(v) for v in vals))


if __name__ == "__main__":
    main()
