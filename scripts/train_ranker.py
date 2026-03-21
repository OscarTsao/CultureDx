#!/usr/bin/env python3
"""Train learned ranker with cross-dataset validation.

Train on MDD-5k features, test on LingxiDiag (and vice versa).

Usage:
    uv run python scripts/train_ranker.py \
        --train outputs/ranker_features/mdd5k_hied.csv \
        --test outputs/ranker_features/lingxidiag_hied.csv
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

FEATURE_COLS = [
    "threshold_ratio",
    "avg_confidence",
    "n_criteria_met",
    "n_criteria_total",
    "criteria_required",
    "margin",
    "evidence_coverage",
    "has_comorbid",
]


def load_features(path: str) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """Load CSV -> (X, y, raw_rows)."""
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    X = np.array([[float(row[c]) for c in FEATURE_COLS] for row in rows])
    y = np.array([int(row["is_correct"]) for row in rows])
    return X, y, rows


def evaluate_ranking(
    rows: list[dict], scores: np.ndarray
) -> dict[str, float | int]:
    """Evaluate ranking: for each case, does highest-scored disorder match gold?"""
    by_case: dict[str, list[tuple[float, dict]]] = defaultdict(list)
    for row, score in zip(rows, scores):
        by_case[row["case_id"]].append((score, row))

    correct = 0
    total = 0
    for case_id, entries in by_case.items():
        entries.sort(key=lambda x: -x[0])  # highest score first
        best = entries[0][1]
        total += 1
        if best["is_correct"] == "1" or best["is_correct"] == 1:
            correct += 1

    return {
        "top1_accuracy": correct / total if total > 0 else 0.0,
        "n_cases": total,
        "n_correct": correct,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", required=True)
    parser.add_argument("--test", required=True)
    parser.add_argument(
        "--output", default=None, help="Output path for results JSON"
    )
    args = parser.parse_args()

    # Load data
    X_train, y_train, rows_train = load_features(args.train)
    X_test, y_test, rows_test = load_features(args.test)

    print(f"Train: {len(X_train)} rows, {y_train.sum()} positive")
    print(f"Test:  {len(X_test)} rows, {y_test.sum()} positive")

    # Baseline: use existing calibrator confidence as ranking score
    conf_train = np.array(
        [float(r["confidence"]) for r in rows_train]
    )
    conf_test = np.array(
        [float(r["confidence"]) for r in rows_test]
    )

    baseline_train = evaluate_ranking(rows_train, conf_train)
    baseline_test = evaluate_ranking(rows_test, conf_test)
    print("\nBaseline (calibrator confidence):")
    print(f"  Train: top1={baseline_train['top1_accuracy']:.3f}")
    print(f"  Test:  top1={baseline_test['top1_accuracy']:.3f}")

    # Train logistic regression
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
    model.fit(X_train_scaled, y_train)

    # Evaluate
    scores_train = model.predict_proba(X_train_scaled)[:, 1]
    scores_test = model.predict_proba(X_test_scaled)[:, 1]

    learned_train = evaluate_ranking(rows_train, scores_train)
    learned_test = evaluate_ranking(rows_test, scores_test)
    print("\nLearned ranker:")
    print(f"  Train: top1={learned_train['top1_accuracy']:.3f}")
    print(f"  Test:  top1={learned_test['top1_accuracy']:.3f}")

    delta = learned_test["top1_accuracy"] - baseline_test["top1_accuracy"]
    print(f"\n  Delta: {delta:+.3f} ({delta * 100:+.1f}pp)")

    # Feature importance
    print("\nFeature coefficients:")
    for feat, coef in sorted(
        zip(FEATURE_COLS, model.coef_[0]), key=lambda x: -abs(x[1])
    ):
        print(f"  {feat:25s}: {coef:+.4f}")

    # Save model info
    result = {
        "train_file": args.train,
        "test_file": args.test,
        "baseline_test_top1": baseline_test["top1_accuracy"],
        "learned_test_top1": learned_test["top1_accuracy"],
        "delta_pp": round(delta * 100, 1),
        "features": FEATURE_COLS,
        "coefficients": {
            f: round(c, 4)
            for f, c in zip(FEATURE_COLS, model.coef_[0])
        },
        "intercept": round(float(model.intercept_[0]), 4),
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
    }
    out = (
        Path(args.output)
        if args.output
        else Path(args.train).parent
        / f"ranker_result_{Path(args.train).stem}_to_{Path(args.test).stem}.json"
    )
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
