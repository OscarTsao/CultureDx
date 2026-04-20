"""TF-IDF + Logistic Regression baseline for LingxiDiag-16K 12-class task.

Clean-eval-discipline version. This replaces the earlier train-on-train /
eval-on-val version from main-v2.4-refactor.

Training and evaluation respect the three-way split defined in
configs/splits/lingxidiag16k_v2_5.yaml:

    rag_pool   (~14k from train, minus dev_hpo)   -> training
    dev_hpo    (1k stratified from train)          -> stacker features, HPO
    test_final (1k = LingxiDiag-16K validation)    -> paper number (touch once)

Usage:

    # Train on rag_pool, predict on dev_hpo (stacker features)
    uv run python scripts/train_tfidf_baseline.py --eval-split dev_hpo

    # Paper number — touch test_final exactly once
    uv run python scripts/train_tfidf_baseline.py --eval-split test_final

Outputs land in outputs/tfidf_baseline/{eval_split}/:

    predictions.jsonl   — per-case primary/ranked/proba
    metrics.json        — Table-4 metrics (12c Top-1/Top-3, F1-macro, etc.)
    model/              — pickled vectorizer, OneVsRest, MultiLabelBinarizer

The training artifacts are deterministic given the same rag_pool split and
random_state=20260420. See configs/splits/lingxidiag16k_v2_5.yaml for the
committed split.
"""
from __future__ import annotations

import argparse
import json
import logging
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
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from culturedx.eval.lingxidiag_paper import (  # noqa: E402
    PAPER_12_CLASSES,
    compute_table4_metrics,
    gold_to_parent_list,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

RANDOM_STATE = 20260420  # keep in sync with scripts/generate_splits.py


# --------------------------------------------------------------------------- #
# Split loading
# --------------------------------------------------------------------------- #
def _data_dir(root: Path) -> Path:
    d = root / "data" / "raw" / "lingxidiag16k"
    if (d / "data").is_dir():
        d = d / "data"
    return d


def _load_parquet(root: Path, split_prefix: str) -> pd.DataFrame:
    """Load the native LingxiDiag-16K parquet shards for `train` or `validation`."""
    data_dir = _data_dir(root)
    files = sorted(data_dir.glob(f"{split_prefix}-*.parquet"))
    if not files:
        raise FileNotFoundError(
            f"No parquet files for {split_prefix}-* in {data_dir}. "
            f"Put LingxiDiag-16K under data/raw/lingxidiag16k/."
        )
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def _load_split_ids(root: Path) -> dict[str, list[str]]:
    """Return {'dev_hpo': [...], 'rag_pool': [...]} from the committed split yaml."""
    import yaml  # local import — not every environment has it installed

    path = root / "configs" / "splits" / "lingxidiag16k_v2_5.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Split manifest missing: {path}. "
            f"Run scripts/generate_splits.py first."
        )
    with path.open(encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    return {
        "dev_hpo": [str(x) for x in spec["splits"]["dev_hpo"]["case_ids"]],
        "rag_pool": [str(x) for x in spec["splits"]["rag_pool"]["case_ids"]],
    }


def load_logical_split(root: Path, name: str) -> pd.DataFrame:
    """Load a logical split from the v2.5 discipline.

    Accepts: "rag_pool", "dev_hpo", "test_final".
    """
    if name == "test_final":
        df = _load_parquet(root, "validation")
    elif name in {"rag_pool", "dev_hpo"}:
        train_df = _load_parquet(root, "train")
        ids = _load_split_ids(root)[name]
        id_set = set(ids)
        df = train_df[train_df["patient_id"].astype(str).isin(id_set)].reset_index(drop=True)
        if len(df) != len(ids):
            logger.warning(
                "Split %s: yaml lists %d ids but parquet matched %d. "
                "Check split manifest freshness.",
                name, len(ids), len(df),
            )
    else:
        raise ValueError(f"Unknown logical split: {name}")

    df["gold_parents"] = df["DiagnosisCode"].apply(lambda c: gold_to_parent_list(str(c)))
    return df


# --------------------------------------------------------------------------- #
# Train / predict
# --------------------------------------------------------------------------- #
def build_multilabel_targets(
    gold_parents_series: pd.Series, classes: list[str]
) -> tuple[np.ndarray, MultiLabelBinarizer]:
    mlb = MultiLabelBinarizer(classes=classes)
    return mlb.fit_transform(gold_parents_series), mlb


def train_tfidf_lr(train_df: pd.DataFrame) -> tuple[TfidfVectorizer, OneVsRestClassifier, MultiLabelBinarizer]:
    logger.info("Fitting TF-IDF (char_wb, 1-2gram, 10k feats, sublinear_tf)...")
    tfidf = TfidfVectorizer(
        max_features=10_000,
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
        analyzer="char_wb",
        sublinear_tf=True,
    )
    X_train = tfidf.fit_transform(train_df["cleaned_text"])
    logger.info("X_train shape: %s  Vocab: %d", X_train.shape, len(tfidf.vocabulary_))

    y_train, mlb = build_multilabel_targets(train_df["gold_parents"], PAPER_12_CLASSES)
    logger.info("y_train shape: %s", y_train.shape)

    logger.info("Training OneVsRest(LogReg, C=1.0, class_weight=balanced)...")
    clf = OneVsRestClassifier(
        LogisticRegression(
            max_iter=2000,
            C=1.0,
            solver="lbfgs",
            class_weight="balanced",
            random_state=RANDOM_STATE,
        ),
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)
    return tfidf, clf, mlb


def predict(
    tfidf: TfidfVectorizer,
    clf: OneVsRestClassifier,
    mlb: MultiLabelBinarizer,
    eval_df: pd.DataFrame,
) -> list[dict]:
    X_eval = tfidf.transform(eval_df["cleaned_text"])
    proba = clf.predict_proba(X_eval)
    classes = list(mlb.classes_)

    records = []
    for idx in range(len(eval_df)):
        row = eval_df.iloc[idx]
        case_id = str(row["patient_id"])
        gold = row["gold_parents"]
        scores = proba[idx]

        ranked_indices = np.argsort(-scores)
        ranked_codes = [classes[i] for i in ranked_indices]
        ranked_scores = [round(float(scores[i]), 6) for i in ranked_indices]

        primary = ranked_codes[0]
        comorbid = []
        if len(ranked_codes) > 1 and ranked_scores[1] >= 0.3:
            comorbid.append(ranked_codes[1])

        records.append({
            "case_id": case_id,
            "gold_diagnoses": gold,
            "primary_diagnosis": primary,
            "comorbid_diagnoses": comorbid,
            "ranked_codes": ranked_codes,
            "proba_scores": ranked_scores,
        })
    return records


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--eval-split",
        choices=["dev_hpo", "test_final"],
        default="dev_hpo",
        help="Which held-out split to predict on. Training is always on rag_pool.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Override output directory (default: outputs/tfidf_baseline/<eval_split>/)",
    )
    args = parser.parse_args()

    out_dir = args.out_dir or (ROOT / "outputs" / "tfidf_baseline" / args.eval_split)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "model").mkdir(exist_ok=True)

    logger.info("=" * 60)
    logger.info("TF-IDF + LR  (train=rag_pool, eval=%s)", args.eval_split)
    logger.info("=" * 60)

    # Load
    logger.info("[1/5] Loading rag_pool (training)...")
    train_df = load_logical_split(ROOT, "rag_pool")
    logger.info("  rag_pool: %d cases", len(train_df))

    logger.info("[2/5] Loading %s (eval)...", args.eval_split)
    eval_df = load_logical_split(ROOT, args.eval_split)
    logger.info("  %s: %d cases", args.eval_split, len(eval_df))

    # Integrity check: no overlap
    overlap = set(train_df["patient_id"].astype(str)) & set(eval_df["patient_id"].astype(str))
    if overlap:
        raise RuntimeError(
            f"LEAKAGE: {len(overlap)} overlapping case_ids between rag_pool and "
            f"{args.eval_split}. First 5: {list(overlap)[:5]}"
        )

    # Train
    logger.info("[3/5] Training TF-IDF + LR on rag_pool...")
    tfidf, clf, mlb = train_tfidf_lr(train_df)

    with open(out_dir / "model" / "tfidf_vectorizer.pkl", "wb") as f:
        pickle.dump(tfidf, f)
    with open(out_dir / "model" / "ovr_logreg.pkl", "wb") as f:
        pickle.dump(clf, f)
    with open(out_dir / "model" / "mlb.pkl", "wb") as f:
        pickle.dump(mlb, f)
    logger.info("  Model saved to %s/model/", out_dir)

    # Predict
    logger.info("[4/5] Predicting on %s...", args.eval_split)
    records = predict(tfidf, clf, mlb, eval_df)
    pred_path = out_dir / "predictions.jsonl"
    with pred_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    logger.info("  %d predictions -> %s", len(records), pred_path)

    # Evaluate
    logger.info("[5/5] Computing Table-4 metrics...")
    case_dicts = []
    for idx in range(len(eval_df)):
        row = eval_df.iloc[idx]
        case_dicts.append({
            "case_id": str(row["patient_id"]),
            "DiagnosisCode": str(row["DiagnosisCode"]),
            "diagnoses": [str(row["DiagnosisCode"])],
            "diagnosis_code_full": str(row["DiagnosisCode"]),
            "four_class_label": row.get("four_class_label"),
        })

    pred_map = {r["case_id"]: r for r in records}
    def get_prediction(case: dict) -> list[str]:
        rec = pred_map.get(case["case_id"])
        if rec is None:
            return []
        return [rec["primary_diagnosis"]] + rec.get("comorbid_diagnoses", [])

    table4 = compute_table4_metrics(case_dicts, get_prediction)
    metrics_path = out_dir / "metrics.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump({
            "eval_split": args.eval_split,
            "n_train": len(train_df),
            "n_eval": len(eval_df),
            "random_state": RANDOM_STATE,
            "table4": table4,
        }, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"RESULTS  (eval_split={args.eval_split}, n={len(eval_df)})")
    print("=" * 60)
    for k in ["12class_Top1", "12class_Top3", "12class_F1_macro",
              "12class_F1_weighted", "4class_Acc", "2class_Acc", "Overall"]:
        v = table4.get(k)
        if v is not None:
            print(f"  {k:25s}: {v:.4f}")
    print()
    print(f"Full metrics: {metrics_path}")


if __name__ == "__main__":
    main()
