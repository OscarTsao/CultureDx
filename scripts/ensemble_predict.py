#!/usr/bin/env python3
"""Confidence-weighted mode ensemble from existing predictions.

Usage:
    uv run python scripts/ensemble_predict.py \
        --sweep-dir outputs/sweeps/n200_3mode_20260320_131920 \
        --modes hied_no_evidence,psycot_no_evidence,single_no_evidence \
        --weights 1.0,0.9,0.8
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.eval.metrics import compute_diagnosis_metrics


def ensemble_predict(
    predictions_by_mode: dict[str, list[dict]],
    weights: dict[str, float],
) -> list[dict]:
    """Weighted vote ensemble: highest weighted confidence wins."""
    # Index by case_id
    by_case: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for mode_name, preds in predictions_by_mode.items():
        for p in preds:
            by_case[p["case_id"]].append((mode_name, p))

    results: list[dict] = []
    for case_id, mode_preds in by_case.items():
        scores: dict[str, float] = defaultdict(float)
        for mode_name, p in mode_preds:
            dx = p.get("primary_diagnosis")
            if dx:
                w = weights.get(mode_name, 1.0)
                scores[dx] += p.get("confidence", 0.5) * w

        if scores:
            best = max(scores, key=scores.__getitem__)
            # Collect all predictions for this case
            all_dx: set[str] = set()
            for _, p in mode_preds:
                if p.get("primary_diagnosis"):
                    all_dx.add(p["primary_diagnosis"])
                for c in p.get("comorbid_diagnoses", []):
                    all_dx.add(c)
            comorbid = [d for d in all_dx if d != best]
        else:
            best = None
            comorbid = []

        results.append({
            "case_id": case_id,
            "primary_diagnosis": best,
            "comorbid_diagnoses": comorbid,
            "confidence": scores[best] if best else 0.0,
            "decision": "diagnosis" if best else "abstain",
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mode ensemble from existing predictions"
    )
    parser.add_argument("--sweep-dir", required=True)
    parser.add_argument(
        "--modes", required=True, help="Comma-separated condition names"
    )
    parser.add_argument(
        "--weights", default=None,
        help="Comma-separated weights (same order as modes)",
    )
    args = parser.parse_args()

    sweep_dir = Path(args.sweep_dir)
    mode_names = args.modes.split(",")
    if args.weights:
        weight_vals = [float(w) for w in args.weights.split(",")]
    else:
        weight_vals = [1.0] * len(mode_names)
    weights = dict(zip(mode_names, weight_vals))

    # Load predictions
    predictions_by_mode: dict[str, list[dict]] = {}
    for mode_name in mode_names:
        pred_path = sweep_dir / mode_name / "predictions.json"
        if not pred_path.exists():
            print(f"WARNING: {pred_path} not found", file=sys.stderr)
            continue
        with open(pred_path, encoding="utf-8") as f:
            data = json.load(f)
        predictions_by_mode[mode_name] = data["predictions"]
        print(f"Loaded {len(data['predictions'])} predictions from {mode_name}")

    # Load gold labels
    case_list = sweep_dir / "case_list.json"
    with open(case_list, encoding="utf-8") as f:
        gold_data = json.load(f)
    gold_map: dict[str, list[str]] = {
        c["case_id"]: c["diagnoses"] for c in gold_data["cases"]
    }

    # Run ensemble
    ensemble = ensemble_predict(predictions_by_mode, weights)
    print(f"\nEnsemble: {len(ensemble)} cases")

    # Evaluate
    preds: list[list[str]] = []
    golds: list[list[str]] = []
    for r in ensemble:
        gold = gold_map.get(r["case_id"])
        if gold:
            pred_dx = (
                [r["primary_diagnosis"]] if r["primary_diagnosis"] else ["unknown"]
            )
            pred_dx += r.get("comorbid_diagnoses", [])
            preds.append(pred_dx)
            golds.append(gold)

    metrics = compute_diagnosis_metrics(preds, golds, normalize="parent")
    print("\nEnsemble metrics (parent-normalized):")
    for k, v in metrics.items():
        print(f"  {k}: {v:.3f}")

    # Compare with individual modes
    print("\nIndividual mode metrics:")
    for mode_name, mode_preds in predictions_by_mode.items():
        mp: list[list[str]] = []
        mg: list[list[str]] = []
        for p in mode_preds:
            gold = gold_map.get(p["case_id"])
            if gold:
                pd = (
                    [p["primary_diagnosis"]]
                    if p["primary_diagnosis"]
                    else ["unknown"]
                )
                pd += p.get("comorbid_diagnoses", [])
                mp.append(pd)
                mg.append(gold)
        m = compute_diagnosis_metrics(mp, mg, normalize="parent")
        print(
            f"  {mode_name}: top1={m['top1_accuracy']:.3f} "
            f"top3={m['top3_accuracy']:.3f}"
        )


if __name__ == "__main__":
    main()
