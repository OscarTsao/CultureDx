#!/usr/bin/env python3
"""MLP/GNN feasibility probe for comorbidity prediction.

Tests whether a learned model can outperform the deterministic
ComorbidityResolver for multi-label diagnosis prediction.

Features: 8 features × 13 disorders = 104-dim per-case vector
(from checker outputs: threshold_ratio, avg_confidence, n_met, n_total,
 required, margin, evidence_coverage, confirmation_status)

Target: multi-label binary vector (13 disorders)

Baseline: deterministic ComorbidityResolver (rules-based)

Usage:
    uv run python scripts/probe_comorbidity_model.py \
        --pred outputs/sweeps/v10_mdd5k_20260320_233729/hied_no_evidence/predictions.json \
               outputs/sweeps/v10_lingxidiag_20260320_222603/hied_no_evidence/predictions.json \
        --cases outputs/sweeps/v10_mdd5k_20260320_233729/case_list.json \
                outputs/sweeps/v10_lingxidiag_20260320_222603/case_list.json \
        --dataset mdd5k lingxidiag
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import f1_score, accuracy_score
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from culturedx.eval.metrics import normalize_icd_code

# All disorders in the ontology (sorted for consistent indexing)
ALL_DISORDERS = [
    "F20", "F22", "F31", "F32", "F33", "F40",
    "F41.0", "F41.1", "F42", "F43.1", "F43.2", "F45", "F51",
]
DISORDER_TO_IDX = {d: i for i, d in enumerate(ALL_DISORDERS)}
N_DISORDERS = len(ALL_DISORDERS)

# Feature columns per disorder
N_FEATURES_PER = 8  # threshold_ratio, avg_conf, n_met, n_total, required, margin, ev_cov, confirmed


def parent_code(code: str | None) -> str | None:
    return code.split(".", 1)[0] if code else None


def extract_case_features(pred: dict) -> np.ndarray:
    """Extract 104-dim feature vector from a prediction.

    8 features for each of 13 disorders. If a disorder wasn't checked,
    features are all zero.
    """
    features = np.zeros(N_DISORDERS * N_FEATURES_PER)
    criteria_results = pred.get("criteria_results", [])
    cr_map = {cr["disorder"]: cr for cr in criteria_results}

    primary = pred.get("primary_diagnosis")
    comorbid = pred.get("comorbid_diagnoses", [])
    confirmed_set = set([primary] + comorbid) if primary else set(comorbid)

    for disorder, idx in DISORDER_TO_IDX.items():
        cr = cr_map.get(disorder)
        if cr is None:
            continue

        criteria = cr.get("criteria", [])
        met = [c for c in criteria if c.get("status") == "met"]
        required = cr.get("criteria_required", 1)
        n_met = len(met)
        n_total = len(criteria)

        avg_conf = sum(c.get("confidence", 0) for c in met) / len(met) if met else 0.0
        threshold_ratio = min(1.0, n_met / required) if required > 0 else 0.0
        margin = max(0, n_met - required) / max(n_total - required, 1) if n_total > required else 0.0
        ev_cov = sum(1 for c in met if c.get("evidence", "").strip()) / len(met) if met else 0.0
        confirmed = 1.0 if disorder in confirmed_set else 0.0

        offset = idx * N_FEATURES_PER
        features[offset:offset + N_FEATURES_PER] = [
            threshold_ratio, avg_conf, n_met, n_total,
            required, margin, ev_cov, confirmed,
        ]

    return features


def extract_gold_labels(gold_codes: list[str]) -> np.ndarray:
    """Convert gold diagnoses to multi-label binary vector."""
    labels = np.zeros(N_DISORDERS)
    for code in gold_codes:
        # Try exact match first, then parent code
        if code in DISORDER_TO_IDX:
            labels[DISORDER_TO_IDX[code]] = 1.0
        else:
            # Try matching parent (e.g., F41 → F41.1)
            p = parent_code(code)
            for disorder, idx in DISORDER_TO_IDX.items():
                if parent_code(disorder) == p:
                    labels[idx] = 1.0
    return labels


def extract_pred_labels(pred: dict) -> np.ndarray:
    """Convert prediction to multi-label binary vector (deterministic baseline)."""
    labels = np.zeros(N_DISORDERS)
    primary = pred.get("primary_diagnosis")
    comorbid = pred.get("comorbid_diagnoses", [])
    all_dx = [primary] + comorbid if primary else comorbid

    for dx in all_dx:
        if dx in DISORDER_TO_IDX:
            labels[DISORDER_TO_IDX[dx]] = 1.0
        else:
            p = parent_code(dx)
            for disorder, idx in DISORDER_TO_IDX.items():
                if parent_code(disorder) == p:
                    labels[idx] = 1.0
    return labels


class MLPComorbidity(nn.Module):
    """Simple MLP for multi-label comorbidity prediction."""

    def __init__(self, input_dim: int, hidden_dim: int = 64, output_dim: int = 13):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim // 2, output_dim),
        )

    def forward(self, x):
        return self.net(x)


def train_mlp(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    epochs: int = 100,
    lr: float = 0.001,
    seed: int = 42,
) -> dict:
    """Train MLP and evaluate."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    device = torch.device("cpu")  # Small data, CPU is fine
    model = MLPComorbidity(X_train.shape[1], hidden_dim=64, output_dim=y_train.shape[1]).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    criterion = nn.BCEWithLogitsLoss()

    X_tr = torch.FloatTensor(X_train).to(device)
    y_tr = torch.FloatTensor(y_train).to(device)
    X_te = torch.FloatTensor(X_test).to(device)
    y_te = torch.FloatTensor(y_test).to(device)

    best_f1 = 0.0
    best_epoch = 0
    patience = 20
    no_improve = 0

    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        logits = model(X_tr)
        loss = criterion(logits, y_tr)
        loss.backward()
        optimizer.step()

        # Evaluate
        model.eval()
        with torch.no_grad():
            test_logits = model(X_te)
            test_preds = (torch.sigmoid(test_logits) > 0.5).float().cpu().numpy()
            test_gold = y_te.cpu().numpy()

            f1 = f1_score(test_gold, test_preds, average="micro", zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_epoch = epoch
                no_improve = 0
            else:
                no_improve += 1

            if no_improve >= patience:
                break

    # Final evaluation
    model.eval()
    with torch.no_grad():
        test_logits = model(X_te)
        test_preds = (torch.sigmoid(test_logits) > 0.5).float().cpu().numpy()
        test_gold = y_te.cpu().numpy()

    f1_micro = f1_score(test_gold, test_preds, average="micro", zero_division=0)
    f1_macro = f1_score(test_gold, test_preds, average="macro", zero_division=0)
    f1_samples = f1_score(test_gold, test_preds, average="samples", zero_division=0)
    subset_acc = accuracy_score(test_gold, test_preds)  # exact match

    return {
        "f1_micro": f1_micro,
        "f1_macro": f1_macro,
        "f1_samples": f1_samples,
        "subset_accuracy": subset_acc,
        "best_epoch": best_epoch,
        "epochs_trained": epoch + 1,
    }


def evaluate_baseline(pred_labels: np.ndarray, gold_labels: np.ndarray) -> dict:
    """Evaluate deterministic baseline."""
    f1_micro = f1_score(gold_labels, pred_labels, average="micro", zero_division=0)
    f1_macro = f1_score(gold_labels, pred_labels, average="macro", zero_division=0)
    f1_samples = f1_score(gold_labels, pred_labels, average="samples", zero_division=0)
    subset_acc = accuracy_score(gold_labels, pred_labels)

    return {
        "f1_micro": f1_micro,
        "f1_macro": f1_macro,
        "f1_samples": f1_samples,
        "subset_accuracy": subset_acc,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pred", nargs="+", required=True)
    parser.add_argument("--cases", nargs="+", required=True)
    parser.add_argument("--dataset", nargs="+", required=True)
    parser.add_argument("--output", default="outputs/comorbidity_probe_results.json")
    args = parser.parse_args()

    if len(args.pred) != len(args.cases) or len(args.pred) != len(args.dataset):
        parser.error("--pred, --cases, --dataset must have same length")

    # Load data
    X_all = []
    y_all = []
    baseline_preds = []
    case_ids = []

    for pred_path, case_path, ds_name in zip(args.pred, args.cases, args.dataset):
        print(f"Loading {ds_name}")
        with open(pred_path, encoding="utf-8") as f:
            data = json.load(f)
        preds = data["predictions"] if isinstance(data, dict) else data

        with open(case_path, encoding="utf-8") as f:
            cl = json.load(f)
        gold_map = {c["case_id"]: c["diagnoses"] for c in cl["cases"]}

        for pred in preds:
            cid = pred["case_id"]
            if cid not in gold_map or not gold_map[cid]:
                continue

            X_all.append(extract_case_features(pred))
            y_all.append(extract_gold_labels(gold_map[cid]))
            baseline_preds.append(extract_pred_labels(pred))
            case_ids.append(cid)

    X = np.array(X_all)
    y = np.array(y_all)
    bl = np.array(baseline_preds)

    print(f"\nTotal: {len(X)} cases, feature dim={X.shape[1]}, labels dim={y.shape[1]}")

    # Label distribution
    print(f"\nGold label distribution:")
    for i, d in enumerate(ALL_DISORDERS):
        count = int(y[:, i].sum())
        if count > 0:
            print(f"  {d}: {count} ({count/len(y)*100:.1f}%)")

    # Baseline evaluation
    print(f"\n{'='*60}")
    print("DETERMINISTIC BASELINE (ComorbidityResolver)")
    bl_metrics = evaluate_baseline(bl, y)
    for k, v in bl_metrics.items():
        print(f"  {k}: {v:.4f}")

    # 5-fold CV for MLP
    print(f"\n{'='*60}")
    print("MLP 5-FOLD CV")

    # Use primary gold label for stratification
    primary_labels = np.argmax(y, axis=1)
    # Handle cases with no gold label in our disorder set
    for i in range(len(primary_labels)):
        if y[i].sum() == 0:
            primary_labels[i] = N_DISORDERS  # dummy class

    kf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    fold_results = []

    for fold, (train_idx, test_idx) in enumerate(kf.split(X, primary_labels)):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        result = train_mlp(X_train, y_train, X_test, y_test, epochs=200, seed=42 + fold)
        fold_results.append(result)
        print(f"  Fold {fold+1}: f1_micro={result['f1_micro']:.4f}, "
              f"f1_samples={result['f1_samples']:.4f}, "
              f"subset_acc={result['subset_accuracy']:.4f}, "
              f"epochs={result['epochs_trained']}")

    # Aggregate
    print(f"\n  MLP Average:")
    for metric in ["f1_micro", "f1_macro", "f1_samples", "subset_accuracy"]:
        vals = [r[metric] for r in fold_results]
        mean = np.mean(vals)
        std = np.std(vals)
        bl_val = bl_metrics[metric]
        delta = mean - bl_val
        print(f"    {metric:20s}: {mean:.4f} ± {std:.4f} (baseline: {bl_val:.4f}, delta: {delta:+.4f})")

    # Decision
    mlp_f1 = np.mean([r["f1_micro"] for r in fold_results])
    bl_f1 = bl_metrics["f1_micro"]
    print(f"\n{'='*60}")
    if mlp_f1 > bl_f1 + 0.01:
        print(f"MLP BEATS BASELINE: +{(mlp_f1 - bl_f1)*100:.1f}pp f1_micro")
        print("→ Proceed to GNN with shared-criteria graph")
    elif mlp_f1 > bl_f1:
        print(f"MLP MARGINAL: +{(mlp_f1 - bl_f1)*100:.1f}pp f1_micro")
        print("→ Borderline — GNN unlikely to help much")
    else:
        print(f"MLP FAILS: {(mlp_f1 - bl_f1)*100:+.1f}pp f1_micro")
        print("→ STOP: deterministic rules are sufficient, no need for GNN")

    # Save
    output = {
        "n_cases": len(X),
        "feature_dim": int(X.shape[1]),
        "n_disorders": N_DISORDERS,
        "baseline": bl_metrics,
        "mlp_cv": {
            "mean": {m: float(np.mean([r[m] for r in fold_results]))
                     for m in ["f1_micro", "f1_macro", "f1_samples", "subset_accuracy"]},
            "std": {m: float(np.std([r[m] for r in fold_results]))
                    for m in ["f1_micro", "f1_macro", "f1_samples", "subset_accuracy"]},
            "folds": fold_results,
        },
        "conclusion": "MLP beats baseline" if mlp_f1 > bl_f1 + 0.01 else "Deterministic is sufficient",
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=lambda o: float(o) if isinstance(o, np.floating) else o)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
