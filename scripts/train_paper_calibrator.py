#!/usr/bin/env python3
"""Train a disorder-agnostic calibrator on train split checker features.

Uses raw_checker_outputs (all 12 candidate disorders per case) from the
JSONL. The calibrator learns: given a candidate disorder's checker feature
vector, how likely is it to be the correct diagnosis?

CRITICAL: Features must NOT include disorder_code identity.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pickle
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from culturedx.eval.lingxidiag_paper import to_paper_parent

TRAIN_JSONL = PROJECT_ROOT / "outputs" / "eval" / "calibrator_train_data" / "results_lingxidiag.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "calibrator_model"

FEATURE_NAMES = [
    "met_count",
    "total_count",
    "met_ratio",
    "avg_criterion_confidence",
    "n_met_criteria",
    "n_notmet_criteria",
    "n_insufficient_criteria",
    "max_criterion_conf",
    "min_criterion_conf",
    "conf_range",
]


def extract_features(co: dict) -> list[float]:
    """Extract disorder-agnostic features from raw_checker_output."""
    met = co.get("criteria_met_count", 0)
    total = co.get("criteria_total_count", 1)
    met_ratio = co.get("met_ratio", met / total if total > 0 else 0.0)

    per_crit = co.get("per_criterion", [])
    confs = [c.get("confidence", 0.0) for c in per_crit]
    statuses = [c.get("status", "not_met") for c in per_crit]

    n_met = sum(1 for s in statuses if s == "met")
    n_notmet = sum(1 for s in statuses if s == "not_met")
    n_insuf = sum(1 for s in statuses if s == "insufficient_evidence")

    avg_conf = np.mean(confs) if confs else 0.0
    max_conf = max(confs) if confs else 0.0
    min_conf = min(confs) if confs else 0.0

    return [
        met,
        total,
        met_ratio,
        float(avg_conf),
        n_met,
        n_notmet,
        n_insuf,
        max_conf,
        min_conf,
        max_conf - min_conf,
    ]


def load_training_data(jsonl_path: Path):
    """Load and flatten raw_checker_outputs into (features, labels)."""
    X_rows: list[list[float]] = []
    y_rows: list[int] = []
    n_cases = 0
    n_no_raw = 0

    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            case = json.loads(line.strip())
            n_cases += 1
            raw_code = str(case.get("diagnosis_code_full", "") or "")

            # Build gold parent set
            gold_parents: set[str] = set()
            if raw_code:
                for part in re.split(r"[;,]", raw_code.strip().upper()):
                    part = part.strip()
                    if part:
                        parent = to_paper_parent(part)
                        if parent != "Others":
                            gold_parents.add(parent)

            trace = case.get("decision_trace", {})
            raw_outputs = trace.get("raw_checker_outputs", [])

            if not raw_outputs:
                n_no_raw += 1
                continue

            for co in raw_outputs:
                features = extract_features(co)
                disorder_code = co.get("disorder_code", "")
                pred_parent = to_paper_parent(disorder_code)

                is_correct = 1 if pred_parent in gold_parents else 0
                X_rows.append(features)
                y_rows.append(is_correct)

    print(f"Cases: {n_cases}, without raw_checker_outputs: {n_no_raw}")
    return np.array(X_rows), np.array(y_rows)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading training data from {TRAIN_JSONL}")
    X, y = load_training_data(TRAIN_JSONL)
    print(f"Training samples: {len(X)} (positive: {int(y.sum())}, negative: {int((1-y).sum())})")
    print(f"Positive rate: {y.mean():.3f}")

    if len(X) == 0:
        print("ERROR: No training data found.")
        return

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    clf = LogisticRegression(
        class_weight="balanced",
        max_iter=1000,
        random_state=42,
    )
    clf.fit(X_scaled, y)

    print("\nFeature weights (by |weight|):")
    for name, weight in sorted(
        zip(FEATURE_NAMES, clf.coef_[0]), key=lambda x: abs(x[1]), reverse=True
    ):
        print(f"  {name:30s}: {weight:+.4f}")

    y_pred = clf.predict(X_scaled)
    print(f"\nTraining classification report:")
    print(classification_report(y, y_pred, target_names=["wrong", "correct"]))

    # Also check calibrated probabilities
    y_proba = clf.predict_proba(X_scaled)[:, 1]
    print(f"Predicted probability stats:")
    print(f"  positive samples: mean={y_proba[y==1].mean():.3f}, std={y_proba[y==1].std():.3f}")
    print(f"  negative samples: mean={y_proba[y==0].mean():.3f}, std={y_proba[y==0].std():.3f}")

    model_path = OUTPUT_DIR / "calibrator_lr.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(
            {"clf": clf, "scaler": scaler, "feature_names": FEATURE_NAMES},
            f,
        )
    print(f"\nModel saved to {model_path}")


if __name__ == "__main__":
    main()
