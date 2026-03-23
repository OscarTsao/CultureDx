#!/usr/bin/env python3
"""Pairwise learned ranker: train on disorder-pair preferences.

For each case with multiple confirmed disorders, generates pairwise instances:
    (disorder_A, disorder_B) -> label: 1 if A is correct, 0 if B is correct.
Features = diff(A_features, B_features) + ratio features + disorder identity.

This captures the relative signal between competing disorders (e.g., F32 vs F41.1)
that pointwise features miss.

Usage:
    uv run python scripts/train_ranker_pairwise.py \
        --train outputs/ranker_features/mdd5k_hied.csv \
        --test outputs/ranker_features/lingxidiag_hied.csv
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

# Original pointwise feature columns
POINTWISE_COLS = [
    "threshold_ratio",
    "avg_confidence",
    "n_criteria_met",
    "n_criteria_total",
    "criteria_required",
    "margin",
    "evidence_coverage",
    "has_comorbid",
]

# Disorder codes for one-hot identity features
DISORDER_IDS = {
    "F32": 0, "F33": 1, "F41.1": 2, "F42": 3, "F43.1": 4,
    "F39": 5, "F45": 6, "F51": 7, "F20": 8, "F31": 9,
}
N_DISORDERS = len(DISORDER_IDS)


def load_pointwise(path: str) -> dict[str, list[dict]]:
    """Load pointwise CSV, group rows by case_id."""
    by_case: dict[str, list[dict]] = defaultdict(list)
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            by_case[row["case_id"]].append(row)
    return by_case


def row_to_features(row: dict) -> np.ndarray:
    """Extract pointwise feature vector from a CSV row."""
    return np.array([float(row[c]) for c in POINTWISE_COLS])


def disorder_onehot(code: str) -> np.ndarray:
    """One-hot encoding for disorder identity."""
    vec = np.zeros(N_DISORDERS)
    idx = DISORDER_IDS.get(code)
    if idx is not None:
        vec[idx] = 1.0
    return vec


def build_pairwise_instances(
    by_case: dict[str, list[dict]], include_identity: bool = True
) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """Build pairwise training instances from pointwise features.

    For each case with 2+ disorders, generate a pair for every (A, B) combo.
    Feature = diff(A, B) + abs_diff + disorder_identity_A + disorder_identity_B.
    Label = 1 if A is correct (in gold), 0 if B is correct.
    Skip pairs where both or neither are correct.
    """
    X_list = []
    y_list = []
    meta_list = []

    for case_id, rows in by_case.items():
        if len(rows) < 2:
            continue

        for row_a, row_b in combinations(rows, 2):
            a_correct = int(row_a["is_correct"])
            b_correct = int(row_b["is_correct"])

            # Skip pairs where both or neither are correct (no preference signal)
            if a_correct == b_correct:
                continue

            feat_a = row_to_features(row_a)
            feat_b = row_to_features(row_b)

            # Difference features: A - B
            diff = feat_a - feat_b
            # Absolute difference (magnitude of gap)
            abs_diff = np.abs(diff)
            # Ratio features for key signals (avoid div by zero)
            eps = 1e-6
            ratio_threshold = feat_a[0] / max(feat_b[0], eps)
            ratio_confidence = feat_a[1] / max(feat_b[1], eps)
            ratio_met = feat_a[2] / max(feat_b[2], eps)
            ratios = np.array([ratio_threshold, ratio_confidence, ratio_met])

            parts = [diff, abs_diff, ratios]

            if include_identity:
                parts.append(disorder_onehot(row_a["disorder"]))
                parts.append(disorder_onehot(row_b["disorder"]))

            features = np.concatenate(parts)

            # Label: 1 if A is the correct one
            label = 1 if a_correct > b_correct else 0

            X_list.append(features)
            y_list.append(label)
            meta_list.append({
                "case_id": case_id,
                "disorder_a": row_a["disorder"],
                "disorder_b": row_b["disorder"],
                "a_correct": a_correct,
                "b_correct": b_correct,
            })

    if not X_list:
        return np.array([]), np.array([]), []

    return np.array(X_list), np.array(y_list), meta_list


def apply_pairwise_ranker(
    model, scaler, by_case: dict[str, list[dict]], include_identity: bool = True
) -> dict[str, float]:
    """Score each disorder via pairwise wins, return case_id -> {disorder: score}."""
    case_scores: dict[str, dict[str, float]] = {}

    for case_id, rows in by_case.items():
        scores = {row["disorder"]: 0.0 for row in rows}

        if len(rows) < 2:
            # Single disorder — use pointwise confidence
            scores[rows[0]["disorder"]] = float(rows[0].get("confidence", 0.5))
            case_scores[case_id] = scores
            continue

        for row_a, row_b in combinations(rows, 2):
            feat_a = row_to_features(row_a)
            feat_b = row_to_features(row_b)

            diff = feat_a - feat_b
            abs_diff = np.abs(diff)
            eps = 1e-6
            ratios = np.array([
                feat_a[0] / max(feat_b[0], eps),
                feat_a[1] / max(feat_b[1], eps),
                feat_a[2] / max(feat_b[2], eps),
            ])

            parts = [diff, abs_diff, ratios]
            if include_identity:
                parts.append(disorder_onehot(row_a["disorder"]))
                parts.append(disorder_onehot(row_b["disorder"]))

            features = np.concatenate(parts).reshape(1, -1)
            features_scaled = scaler.transform(features)
            prob_a_wins = model.predict_proba(features_scaled)[0, 1]

            # Accumulate win probabilities
            scores[row_a["disorder"]] += prob_a_wins
            scores[row_b["disorder"]] += (1 - prob_a_wins)

        case_scores[case_id] = scores

    return case_scores


def evaluate_ranking_from_scores(
    by_case: dict[str, list[dict]], case_scores: dict[str, dict[str, float]]
) -> dict:
    """Evaluate top-1 accuracy from pairwise scores."""
    correct = 0
    total = 0
    flips_good = 0
    flips_bad = 0
    flip_details = []

    for case_id, rows in by_case.items():
        if case_id not in case_scores:
            continue

        scores = case_scores[case_id]
        # Original ranking: first row is primary
        original_best = rows[0]["disorder"]
        original_correct = int(rows[0]["is_correct"])

        # New ranking: highest pairwise score
        new_best = max(scores, key=scores.get)
        new_correct = any(
            int(r["is_correct"]) for r in rows if r["disorder"] == new_best
        )

        total += 1
        if new_correct:
            correct += 1

        # Track flips
        if new_best != original_best:
            if new_correct and not original_correct:
                flips_good += 1
                flip_details.append({
                    "case_id": case_id,
                    "flip": f"{original_best} -> {new_best}",
                    "type": "GOOD",
                })
            elif not new_correct and original_correct:
                flips_bad += 1
                flip_details.append({
                    "case_id": case_id,
                    "flip": f"{original_best} -> {new_best}",
                    "type": "BAD",
                })

    return {
        "top1_accuracy": correct / total if total else 0,
        "n_cases": total,
        "n_correct": correct,
        "flips_good": flips_good,
        "flips_bad": flips_bad,
        "flip_details": flip_details,
    }


def evaluate_baseline(by_case: dict[str, list[dict]]) -> dict:
    """Baseline: use original ranking (primary_diagnosis first)."""
    correct = 0
    total = 0
    for case_id, rows in by_case.items():
        total += 1
        if int(rows[0]["is_correct"]):
            correct += 1
    return {
        "top1_accuracy": correct / total if total else 0,
        "n_cases": total,
        "n_correct": correct,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", required=True, help="Pointwise features CSV (train)")
    parser.add_argument("--test", required=True, help="Pointwise features CSV (test)")
    parser.add_argument("--output", default=None, help="Output path for results JSON")
    parser.add_argument("--no-identity", action="store_true",
                        help="Exclude disorder identity features (ablation)")
    args = parser.parse_args()

    include_identity = not args.no_identity

    # Load pointwise features grouped by case
    train_by_case = load_pointwise(args.train)
    test_by_case = load_pointwise(args.test)
    print(f"Train: {sum(len(v) for v in train_by_case.values())} rows, "
          f"{len(train_by_case)} cases")
    print(f"Test:  {sum(len(v) for v in test_by_case.values())} rows, "
          f"{len(test_by_case)} cases")

    # Baseline
    baseline_train = evaluate_baseline(train_by_case)
    baseline_test = evaluate_baseline(test_by_case)
    print(f"\nBaseline (original ranking):")
    print(f"  Train: top1={baseline_train['top1_accuracy']:.3f} "
          f"({baseline_train['n_correct']}/{baseline_train['n_cases']})")
    print(f"  Test:  top1={baseline_test['top1_accuracy']:.3f} "
          f"({baseline_test['n_correct']}/{baseline_test['n_cases']})")

    # Build pairwise instances
    X_train, y_train, meta_train = build_pairwise_instances(
        train_by_case, include_identity)
    X_test_pw, y_test_pw, meta_test = build_pairwise_instances(
        test_by_case, include_identity)

    print(f"\nPairwise instances:")
    print(f"  Train: {len(X_train)} pairs, {y_train.sum()} A-wins, "
          f"{len(y_train) - y_train.sum()} B-wins")
    print(f"  Test:  {len(X_test_pw)} pairs")
    print(f"  Feature dim: {X_train.shape[1] if len(X_train) > 0 else 0}")
    if include_identity:
        print(f"  (includes {N_DISORDERS}×2 disorder identity features)")

    if len(X_train) == 0:
        print("ERROR: No pairwise instances generated. Need cases with multiple disorders.")
        return

    # Train logistic regression on pairwise data
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    model = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
    model.fit(X_train_scaled, y_train)

    # Pairwise classification accuracy (sanity check)
    train_acc = model.score(X_train_scaled, y_train)
    if len(X_test_pw) > 0:
        X_test_pw_scaled = scaler.transform(X_test_pw)
        test_acc = model.score(X_test_pw_scaled, y_test_pw)
    else:
        test_acc = 0.0
    print(f"\nPairwise classification accuracy:")
    print(f"  Train: {train_acc:.3f}")
    print(f"  Test:  {test_acc:.3f}")

    # Apply pairwise ranker to get case-level rankings
    train_scores = apply_pairwise_ranker(model, scaler, train_by_case, include_identity)
    test_scores = apply_pairwise_ranker(model, scaler, test_by_case, include_identity)

    learned_train = evaluate_ranking_from_scores(train_by_case, train_scores)
    learned_test = evaluate_ranking_from_scores(test_by_case, test_scores)

    print(f"\nPairwise learned ranker (case-level Top-1):")
    print(f"  Train: top1={learned_train['top1_accuracy']:.3f} "
          f"({learned_train['n_correct']}/{learned_train['n_cases']})")
    print(f"  Test:  top1={learned_test['top1_accuracy']:.3f} "
          f"({learned_test['n_correct']}/{learned_test['n_cases']})")

    delta = learned_test["top1_accuracy"] - baseline_test["top1_accuracy"]
    print(f"\n  Delta: {delta:+.3f} ({delta * 100:+.1f}pp)")
    print(f"  Good flips: {learned_test['flips_good']}")
    print(f"  Bad flips:  {learned_test['flips_bad']}")
    print(f"  Net flips:  {learned_test['flips_good'] - learned_test['flips_bad']:+d}")

    if learned_test["flip_details"]:
        print(f"\n  Flip details:")
        for fd in learned_test["flip_details"]:
            print(f"    {fd['case_id']:20s}  {fd['flip']:20s}  [{fd['type']}]")

    # Feature importance (pairwise feature names)
    pw_feat_names = []
    for prefix in ["diff_", "absdiff_"]:
        pw_feat_names.extend([f"{prefix}{c}" for c in POINTWISE_COLS])
    pw_feat_names.extend(["ratio_threshold", "ratio_confidence", "ratio_met"])
    if include_identity:
        for side in ["A_", "B_"]:
            pw_feat_names.extend([f"{side}{d}" for d in DISORDER_IDS])

    print(f"\nTop features (by |coefficient|):")
    coefs = model.coef_[0]
    ranked = sorted(zip(pw_feat_names, coefs), key=lambda x: -abs(x[1]))
    for name, coef in ranked[:15]:
        print(f"  {name:30s}: {coef:+.4f}")

    # Save results
    result = {
        "method": "pairwise_logistic_regression",
        "include_identity": include_identity,
        "train_file": args.train,
        "test_file": args.test,
        "baseline_test_top1": baseline_test["top1_accuracy"],
        "learned_test_top1": learned_test["top1_accuracy"],
        "delta_pp": round(delta * 100, 1),
        "flips_good": learned_test["flips_good"],
        "flips_bad": learned_test["flips_bad"],
        "n_train_pairs": len(X_train),
        "n_test_pairs": len(X_test_pw),
        "pairwise_test_accuracy": round(test_acc, 4),
        "flip_details": learned_test["flip_details"],
        "top_features": [
            {"name": n, "coefficient": round(c, 4)}
            for n, c in ranked[:15]
        ],
    }
    out = (
        Path(args.output) if args.output
        else Path(args.train).parent
        / f"pairwise_ranker_{Path(args.train).stem}_to_{Path(args.test).stem}.json"
    )
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
