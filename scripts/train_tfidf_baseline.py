"""TF-IDF + Logistic Regression baseline for LingxiDiag-16K 12-class task.

Trains on train split, evaluates on validation split, and produces
predictions.jsonl compatible with CultureDx ensemble fusion.
"""
from __future__ import annotations

import json
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer

# -- Project imports --
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.culturedx.eval.lingxidiag_paper import (
    PAPER_12_CLASSES,
    compute_table4_metrics,
    gold_to_parent_list,
    to_paper_parent,
)

# ---------- paths ----------
ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "data/raw/lingxidiag16k/data/train-00000-of-00001.parquet"
VAL_PATH = ROOT / "data/raw/lingxidiag16k/data/validation-00000-of-00001.parquet"
OUT_DIR = ROOT / "outputs/tfidf_baseline"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_split(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    # Derive 12-class multi-label targets from DiagnosisCode
    df["gold_parents"] = df["DiagnosisCode"].apply(
        lambda c: gold_to_parent_list(str(c))
    )
    return df


def build_multilabel_targets(
    gold_parents_series: pd.Series, classes: list[str]
) -> np.ndarray:
    mlb = MultiLabelBinarizer(classes=classes)
    return mlb.fit_transform(gold_parents_series), mlb


def main() -> None:
    print("=" * 60)
    print("TF-IDF + LogReg Baseline  (12-class multi-label)")
    print("=" * 60)

    # ---- Load data ----
    print("\n[1/5] Loading data ...")
    train_df = load_split(TRAIN_PATH)
    val_df = load_split(VAL_PATH)
    print(f"  Train: {len(train_df)} rows   Val: {len(val_df)} rows")

    # ---- TF-IDF ----
    print("\n[2/5] Fitting TF-IDF vectorizer ...")
    tfidf = TfidfVectorizer(
        max_features=10_000,
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
        analyzer="char_wb",   # char n-grams work well for Chinese
        sublinear_tf=True,
    )
    X_train = tfidf.fit_transform(train_df["cleaned_text"])
    X_val = tfidf.transform(val_df["cleaned_text"])
    print(f"  Vocabulary size: {len(tfidf.vocabulary_)}")
    print(f"  X_train shape: {X_train.shape}   X_val shape: {X_val.shape}")

    # ---- Multi-label targets ----
    y_train, mlb = build_multilabel_targets(train_df["gold_parents"], PAPER_12_CLASSES)
    y_val, _ = build_multilabel_targets(val_df["gold_parents"], PAPER_12_CLASSES)
    print(f"  Label matrix shape: {y_train.shape}")

    # ---- Train ----
    print("\n[3/5] Training OneVsRest(LogisticRegression) ...")
    clf = OneVsRestClassifier(
        LogisticRegression(
            max_iter=2000,
            C=1.0,
            solver="lbfgs",
            class_weight="balanced",
        ),
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)
    print("  Done.")

    # ---- Save model artefacts ----
    print("\n[4/5] Saving model to", OUT_DIR)
    with open(OUT_DIR / "tfidf_vectorizer.pkl", "wb") as f:
        pickle.dump(tfidf, f)
    with open(OUT_DIR / "ovr_logreg.pkl", "wb") as f:
        pickle.dump(clf, f)
    with open(OUT_DIR / "mlb.pkl", "wb") as f:
        pickle.dump(mlb, f)
    print("  Saved tfidf_vectorizer.pkl, ovr_logreg.pkl, mlb.pkl")

    # ---- Predict on validation ----
    print("\n[5/5] Predicting on validation split ...")
    # decision_function gives raw scores per class — convert to probabilities
    # For OneVsRest(LogReg), predict_proba works if the base estimator supports it
    proba = clf.predict_proba(X_val)  # shape: (n, 12)

    classes = list(mlb.classes_)
    records = []
    for idx in range(len(val_df)):
        row = val_df.iloc[idx]
        case_id = str(row["patient_id"])
        gold = row["gold_parents"]
        scores = proba[idx]

        # Rank classes by probability descending
        ranked_indices = np.argsort(-scores)
        ranked_codes = [classes[i] for i in ranked_indices]
        ranked_scores = [round(float(scores[i]), 6) for i in ranked_indices]

        # Primary = argmax
        primary = ranked_codes[0]

        # Comorbid = 2nd class if its proba >= 0.3
        comorbid = []
        if len(ranked_codes) > 1 and ranked_scores[1] >= 0.3:
            comorbid.append(ranked_codes[1])

        records.append(
            {
                "case_id": case_id,
                "gold_diagnoses": gold,
                "primary_diagnosis": primary,
                "comorbid_diagnoses": comorbid,
                "ranked_codes": ranked_codes,
                "proba_scores": ranked_scores,
            }
        )

    pred_path = OUT_DIR / "predictions.jsonl"
    with open(pred_path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"  Wrote {len(records)} predictions to {pred_path}")

    # ---- Evaluate with paper metrics ----
    print("\n" + "=" * 60)
    print("EVALUATION  (Table 4 paper-aligned)")
    print("=" * 60)

    # Build case dicts for compute_table4_metrics
    case_dicts = []
    for idx in range(len(val_df)):
        row = val_df.iloc[idx]
        case_dicts.append(
            {
                "DiagnosisCode": str(row["DiagnosisCode"]),
                "_pred_idx": idx,
            }
        )

    def get_prediction(case: dict) -> list[str]:
        rec = records[case["_pred_idx"]]
        # Return primary + comorbid as the prediction list
        result = [rec["primary_diagnosis"]] + rec["comorbid_diagnoses"]
        return result

    metrics = compute_table4_metrics(case_dicts, get_prediction)

    print()
    for key, val in metrics.items():
        if val is None:
            print(f"  {key:24s}  N/A")
        elif key.endswith("_n"):
            print(f"  {key:24s}  {int(val)}")
        else:
            print(f"  {key:24s}  {val:.4f}")

    # Save metrics
    metrics_path = OUT_DIR / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\n  Metrics saved to {metrics_path}")

    # ---- Quick per-class breakdown ----
    print("\n" + "-" * 40)
    print("Per-class prediction distribution (val):")
    from collections import Counter

    primary_counts = Counter(r["primary_diagnosis"] for r in records)
    gold_counts = Counter(g for r in records for g in r["gold_diagnoses"])
    print(f"  {'Class':8s} {'Gold':>6s} {'Pred':>6s}")
    for cls in PAPER_12_CLASSES:
        print(f"  {cls:8s} {gold_counts.get(cls,0):6d} {primary_counts.get(cls,0):6d}")

    print("\nDone.")


if __name__ == "__main__":
    main()
