#!/usr/bin/env python3
"""Calibrator V2 weight tuning via optimization.

Optimizes the 8 calibrator feature weights to maximize Top-1 accuracy
on existing predictions. Uses differential_evolution with leave-one-dataset-out CV.

The 8 features (3 currently zeroed):
  1. core_score      (0.30)  — weighted criterion score (core/duration 1.5x)
  2. avg_confidence   (0.207) — average confidence of met criteria
  3. threshold_ratio  (0.207) — met_count / required_count
  4. evidence_coverage(0.207) — fraction of met criteria with evidence
  5. uniqueness       (0.00)  — evidence uniqueness vs other disorders  ← ZEROED
  6. margin           (0.08)  — how far above threshold
  7. variance         (0.00)  — penalty for high confidence variance   ← ZEROED
  8. info_content     (0.00)  — absolute met criteria count reward     ← ZEROED

Usage:
    uv run python scripts/tune_calibrator_weights.py \
        --pred outputs/sweeps/v10_mdd5k_20260320_233729/hied_no_evidence/predictions.json \
               outputs/sweeps/v10_lingxidiag_20260320_222603/hied_no_evidence/predictions.json \
        --cases outputs/sweeps/v10_mdd5k_20260320_233729/case_list.json \
                outputs/sweeps/v10_lingxidiag_20260320_222603/case_list.json \
        --dataset mdd5k lingxidiag
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import differential_evolution

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from culturedx.eval.metrics import normalize_icd_code


FEATURE_NAMES = [
    "core_score",
    "avg_confidence",
    "threshold_ratio",
    "evidence_coverage",
    "uniqueness",
    "margin",
    "variance",
    "info_content",
]

CURRENT_WEIGHTS = np.array([0.30, 0.207, 0.207, 0.207, 0.00, 0.08, 0.00, 0.00])


def parent_code(code: str | None) -> str | None:
    return code.split(".", 1)[0] if code else None


def load_dataset(pred_path: str, case_path: str) -> list[dict]:
    """Load predictions + gold labels, extract per-case feature vectors.

    Returns list of dicts, one per case:
      {case_id, gold_parents, disorders: [{code, features: [8], is_primary}]}
    """
    with open(pred_path, encoding="utf-8") as f:
        data = json.load(f)
    preds = data["predictions"] if isinstance(data, dict) else data

    with open(case_path, encoding="utf-8") as f:
        cl = json.load(f)
    gold_map = {c["case_id"]: c["diagnoses"] for c in cl["cases"]}

    cases = []
    for pred in preds:
        cid = pred["case_id"]
        if cid not in gold_map:
            continue

        gold_parents = {normalize_icd_code(g) for g in gold_map[cid]}
        criteria_results = pred.get("criteria_results", [])
        if not criteria_results:
            continue

        cr_map = {cr["disorder"]: cr for cr in criteria_results}
        primary = pred.get("primary_diagnosis")
        comorbid = pred.get("comorbid_diagnoses", [])
        all_dx = [primary] + comorbid if primary else comorbid

        disorders = []
        for dx in all_dx:
            if not dx or dx not in cr_map:
                continue
            features = extract_calibrator_features(dx, cr_map[dx], criteria_results)
            disorders.append({
                "code": dx,
                "parent": parent_code(dx),
                "features": features,
                "is_primary": dx == primary,
            })

        if disorders:
            cases.append({
                "case_id": cid,
                "gold_parents": gold_parents,
                "disorders": disorders,
            })

    return cases


def extract_calibrator_features(
    disorder_code: str,
    checker_output: dict,
    all_outputs: list[dict],
) -> np.ndarray:
    """Extract the 8 calibrator features from a checker output dict.

    Replicates the logic in ConfidenceCalibrator._compute_calibrated_v2.
    """
    criteria = checker_output.get("criteria", [])
    met = [c for c in criteria if c.get("status") == "met"]
    required = checker_output.get("criteria_required", 1)

    # 1. core_score — simplified (no type weights, approximate with confidence)
    # We'd need ICD-10 criteria types, but for optimization we use available data
    from culturedx.ontology.icd10 import get_disorder_criteria
    criteria_def = get_disorder_criteria(disorder_code) or {}
    TYPE_WEIGHTS = {"core": 1.5, "duration": 1.3, "first_rank": 1.5, "exclusion": 1.2}
    weighted_sum = 0.0
    max_possible = 0.0
    for c in criteria:
        cdef = criteria_def.get(c["criterion_id"], {})
        w = TYPE_WEIGHTS.get(cdef.get("type", ""), 1.0)
        max_possible += w
        if c["status"] == "met":
            weighted_sum += w * c.get("confidence", 0)
    core_score = weighted_sum / max_possible if max_possible > 0 else 0.0

    # 2. avg_confidence
    avg_conf = (
        sum(c.get("confidence", 0) for c in met) / len(met) if met else 0.0
    )

    # 3. threshold_ratio
    n_met = len(met)
    threshold_ratio = min(1.0, n_met / required) if required > 0 else 0.0

    # 4. evidence_coverage (fraction of met criteria with evidence text)
    has_ev = sum(1 for c in met if c.get("evidence", "").strip()) if met else 0
    evidence_coverage = has_ev / len(met) if met else 0.0

    # 5. uniqueness (evidence overlap with other confirmed disorders)
    other_evidence = set()
    for co in all_outputs:
        if co["disorder"] == disorder_code:
            continue
        for c in co.get("criteria", []):
            if c.get("status") == "met" and c.get("evidence", "").strip():
                other_evidence.add(c["evidence"].strip().lower())
    if not other_evidence or not met:
        uniqueness = 1.0 if met else 0.0
    else:
        unique = 0
        total_ev = 0
        for c in met:
            ev = c.get("evidence", "").strip()
            if ev:
                total_ev += 1
                norm = ev.lower()
                shared = any(norm in o or o in norm for o in other_evidence)
                if not shared:
                    unique += 1
        uniqueness = unique / total_ev if total_ev > 0 else 0.5

    # 6. margin
    total_criteria = len(criteria)
    excess = n_met - required
    if excess <= 0 or required <= 0:
        margin = 0.0
    else:
        max_excess = max(total_criteria - required, 1)
        excess_ratio = excess / max_excess
        margin = min(1.0, math.log1p(excess_ratio * 7) / math.log(8))

    # 7. variance penalty
    if len(met) <= 1:
        variance = 1.0
    else:
        confs = [c.get("confidence", 0) for c in met]
        mean_c = sum(confs) / len(confs)
        var = sum((x - mean_c) ** 2 for x in confs) / len(confs)
        variance = 1.0 - min(1.0, var / 0.25)

    # 8. info_content
    info_content = min(1.0, math.log1p(n_met) / math.log1p(10))

    return np.array([
        core_score, avg_conf, threshold_ratio, evidence_coverage,
        uniqueness, margin, variance, info_content,
    ])


def compute_confidence(features: np.ndarray, weights: np.ndarray) -> float:
    """Compute calibrated confidence from feature vector and weights."""
    return float(np.clip(np.dot(features, weights), 0.0, 1.0))


def evaluate_weights(
    weights: np.ndarray,
    cases: list[dict],
    soft_penalty: float = 0.85,
) -> float:
    """Evaluate Top-1 accuracy for a given weight vector.

    For each case, the disorder with the highest calibrated confidence
    is the predicted primary. Check if it matches any gold parent code.
    Returns negative accuracy (for minimization).
    """
    correct = 0
    total = 0

    for case in cases:
        gold = case["gold_parents"]
        best_code = None
        best_conf = -1.0

        for d in case["disorders"]:
            conf = compute_confidence(d["features"], weights)
            if conf > best_conf:
                best_conf = conf
                best_code = d["parent"]

        total += 1
        if best_code in gold:
            correct += 1

    return correct / total if total > 0 else 0.0


def optimize_weights(
    train_cases: list[dict],
    test_cases: list[dict] | None = None,
    seed: int = 42,
) -> dict:
    """Optimize calibrator weights using differential evolution."""

    def objective(w_raw):
        # Normalize weights to sum to 1
        w = np.abs(w_raw)
        w = w / w.sum() if w.sum() > 0 else np.ones(8) / 8
        return -evaluate_weights(w, train_cases)

    # Bounds: each weight in [0, 1]
    bounds = [(0.0, 1.0)] * 8

    result = differential_evolution(
        objective,
        bounds,
        seed=seed,
        maxiter=500,
        popsize=30,
        tol=1e-6,
        mutation=(0.5, 1.5),
        recombination=0.9,
    )

    # Normalize result
    w_opt = np.abs(result.x)
    w_opt = w_opt / w_opt.sum()

    train_acc = evaluate_weights(w_opt, train_cases)
    test_acc = evaluate_weights(w_opt, test_cases) if test_cases else None

    return {
        "weights": w_opt,
        "train_accuracy": train_acc,
        "test_accuracy": test_acc,
        "converged": result.success,
        "iterations": result.nit,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrator V2 weight tuning")
    parser.add_argument("--pred", nargs="+", required=True)
    parser.add_argument("--cases", nargs="+", required=True)
    parser.add_argument("--dataset", nargs="+", required=True)
    parser.add_argument("--output", default="outputs/calibrator_tuning_results.json")
    args = parser.parse_args()

    if len(args.pred) != len(args.cases) or len(args.pred) != len(args.dataset):
        parser.error("--pred, --cases, --dataset must have same length")

    # Load all datasets
    all_datasets = {}
    for pred_path, case_path, ds_name in zip(args.pred, args.cases, args.dataset):
        print(f"Loading {ds_name}: {pred_path}")
        cases = load_dataset(pred_path, case_path)
        print(f"  {len(cases)} cases with checker outputs")
        all_datasets[ds_name] = cases

    # Baseline: current weights
    all_cases = []
    for cases in all_datasets.values():
        all_cases.extend(cases)

    baseline_total = evaluate_weights(CURRENT_WEIGHTS, all_cases)
    print(f"\n{'='*60}")
    print(f"BASELINE (current V2 weights): Top-1 = {baseline_total*100:.1f}%")
    for ds_name, cases in all_datasets.items():
        acc = evaluate_weights(CURRENT_WEIGHTS, cases)
        print(f"  {ds_name}: {acc*100:.1f}%")

    # Feature importance: compute single-feature accuracy
    print(f"\n{'='*60}")
    print("SINGLE-FEATURE ACCURACY (each feature alone)")
    for i, fname in enumerate(FEATURE_NAMES):
        w = np.zeros(8)
        w[i] = 1.0
        acc = evaluate_weights(w, all_cases)
        print(f"  {fname:25s}: {acc*100:.1f}%")

    # Leave-one-dataset-out CV
    print(f"\n{'='*60}")
    print("LEAVE-ONE-DATASET-OUT OPTIMIZATION")
    results = {}
    for test_ds in all_datasets:
        train_cases = []
        for ds_name, cases in all_datasets.items():
            if ds_name != test_ds:
                train_cases.extend(cases)
        test_cases = all_datasets[test_ds]

        if not train_cases:
            print(f"  Skipping {test_ds} (only 1 dataset)")
            continue

        print(f"\n  Train on {'|'.join(d for d in all_datasets if d != test_ds)}, test on {test_ds}")
        opt = optimize_weights(train_cases, test_cases)
        results[f"loo_{test_ds}"] = {
            "weights": {n: float(w) for n, w in zip(FEATURE_NAMES, opt["weights"])},
            "train_accuracy": opt["train_accuracy"],
            "test_accuracy": opt["test_accuracy"],
            "converged": opt["converged"],
        }

        baseline_test = evaluate_weights(CURRENT_WEIGHTS, test_cases)
        delta = opt["test_accuracy"] - baseline_test
        print(f"  Optimized: train={opt['train_accuracy']*100:.1f}%, test={opt['test_accuracy']*100:.1f}%")
        print(f"  Baseline test: {baseline_test*100:.1f}%, delta: {delta*100:+.1f}pp")
        print(f"  Weights: " + ", ".join(f"{n}={w:.3f}" for n, w in zip(FEATURE_NAMES, opt["weights"])))

    # Pooled optimization (train on all, test on all)
    print(f"\n{'='*60}")
    print("POOLED OPTIMIZATION (train+test on all datasets)")
    pooled = optimize_weights(all_cases, all_cases)
    results["pooled"] = {
        "weights": {n: float(w) for n, w in zip(FEATURE_NAMES, pooled["weights"])},
        "train_accuracy": pooled["train_accuracy"],
        "converged": pooled["converged"],
    }
    delta = pooled["train_accuracy"] - baseline_total
    print(f"  Optimized: {pooled['train_accuracy']*100:.1f}% (delta: {delta*100:+.1f}pp)")
    print(f"  Weights: " + ", ".join(f"{n}={w:.3f}" for n, w in zip(FEATURE_NAMES, pooled["weights"])))

    # Per-dataset evaluation of pooled weights
    print(f"\n  Per-dataset with pooled weights:")
    for ds_name, cases in all_datasets.items():
        acc_opt = evaluate_weights(pooled["weights"], cases)
        acc_bl = evaluate_weights(CURRENT_WEIGHTS, cases)
        print(f"    {ds_name}: {acc_opt*100:.1f}% (baseline: {acc_bl*100:.1f}%, delta: {(acc_opt-acc_bl)*100:+.1f}pp)")

    # Check zeroed features
    print(f"\n{'='*60}")
    print("ZEROED FEATURE ANALYSIS")
    zeroed = ["uniqueness", "variance", "info_content"]
    for fname in zeroed:
        idx = FEATURE_NAMES.index(fname)
        w_with = CURRENT_WEIGHTS.copy()
        # Give it some weight by stealing from others proportionally
        donate = 0.05
        w_with[idx] = donate
        active_mask = CURRENT_WEIGHTS > 0
        active_mask[idx] = False
        if active_mask.sum() > 0:
            w_with[active_mask] *= (1 - donate) / w_with[active_mask].sum()
        acc_with = evaluate_weights(w_with, all_cases)
        print(f"  {fname} at 0.05: {acc_with*100:.1f}% (baseline: {baseline_total*100:.1f}%, delta: {(acc_with-baseline_total)*100:+.1f}pp)")

    # Save results
    output = {
        "baseline_weights": {n: float(w) for n, w in zip(FEATURE_NAMES, CURRENT_WEIGHTS)},
        "baseline_total_accuracy": baseline_total,
        "per_dataset_baseline": {
            ds: evaluate_weights(CURRENT_WEIGHTS, cases) for ds, cases in all_datasets.items()
        },
        "optimization_results": results,
        "feature_names": FEATURE_NAMES,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nSaved results to {out_path}")


if __name__ == "__main__":
    main()
