#!/usr/bin/env python3
"""Offline re-ranking of existing predictions using pairwise ranker.

Reads predictions.json, re-ranks confirmed disorders using trained pairwise model,
writes reranked predictions to a sibling directory. NO LLM calls.

Usage:
    uv run python scripts/rerank_predictions.py \
        --predictions outputs/sweeps/v10_lingxidiag_20260320_222603/hied_no_evidence/predictions.json \
        --weights outputs/ranker_features/pairwise_ranker_weights.json
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.diagnosis.pairwise_ranker import PairwiseRanker


def rerank_prediction(pred: dict, ranker: PairwiseRanker) -> tuple[dict, str | None]:
    """Re-rank a single prediction. Returns (new_pred, flip_description or None)."""
    new_pred = copy.deepcopy(pred)

    primary = pred.get("primary_diagnosis")
    comorbid = pred.get("comorbid_diagnoses", [])
    criteria_results = pred.get("criteria_results", [])

    if not primary or not criteria_results:
        return new_pred, None

    confirmed = [primary] + [c for c in comorbid if c]
    if len(confirmed) < 2:
        return new_pred, None

    reranked = ranker.rerank_from_criteria_results(confirmed, criteria_results)

    if reranked[0] == primary:
        # No change to primary
        new_pred["comorbid_diagnoses"] = reranked[1:]
        return new_pred, None

    # Primary changed
    old_primary = primary
    new_pred["primary_diagnosis"] = reranked[0]
    new_pred["comorbid_diagnoses"] = reranked[1:]
    return new_pred, f"{old_primary} -> {reranked[0]}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline re-ranking of predictions")
    parser.add_argument("--predictions", required=True, help="Path to predictions.json")
    parser.add_argument("--weights", required=True, help="Path to pairwise_ranker_weights.json")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: sibling *_reranked/)")
    args = parser.parse_args()

    pred_path = Path(args.predictions)
    weights_path = Path(args.weights)

    # Load
    with open(pred_path, encoding="utf-8") as f:
        data = json.load(f)

    predictions = data.get("predictions", data if isinstance(data, list) else [])
    is_wrapped = isinstance(data, dict) and "predictions" in data

    ranker = PairwiseRanker(weights_path)
    print(f"Loaded ranker: dim={ranker.feature_dim}, identity={ranker.include_identity}")
    print(f"Loaded {len(predictions)} predictions from {pred_path}")

    # Re-rank
    new_predictions = []
    flips = []
    for pred in predictions:
        new_pred, flip = rerank_prediction(pred, ranker)
        new_predictions.append(new_pred)
        if flip:
            flips.append((pred["case_id"], flip))

    print(f"\nRe-ranked: {len(flips)} primary flips out of {len(predictions)} cases")
    for cid, flip_desc in flips:
        print(f"  {cid:20s}  {flip_desc}")

    # Determine output path
    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        # Create sibling directory: hied_no_evidence -> hied_no_evidence_reranked
        parent = pred_path.parent
        out_dir = parent.parent / f"{parent.name}_reranked"

    out_dir.mkdir(parents=True, exist_ok=True)

    # Write output
    if is_wrapped:
        out_data = copy.deepcopy(data)
        out_data["predictions"] = new_predictions
        out_data["condition"] = data.get("condition", "") + "_reranked"
        out_data["reranker"] = {
            "method": "pairwise_logistic_regression",
            "weights_file": str(weights_path),
            "n_flips": len(flips),
        }
    else:
        out_data = new_predictions

    out_path = out_dir / "predictions.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2, ensure_ascii=False)
    print(f"\nSaved reranked predictions to {out_path}")

    # Also copy metrics.json if it exists (for reference)
    metrics_src = pred_path.parent / "metrics.json"
    if metrics_src.exists():
        import shutil
        shutil.copy2(metrics_src, out_dir / "original_metrics.json")
        print(f"Copied original metrics to {out_dir / 'original_metrics.json'}")


if __name__ == "__main__":
    main()
