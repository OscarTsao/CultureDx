"""Generate the v2.5 three-way split for LingxiDiag-16K.

Splits:
    rag_pool   = train \\ dev_hpo     (~14k, RAG training pool, TF-IDF training)
    dev_hpo    = 1000 stratified      (HPO, stacker training, prompt iteration)
    test_final = validation (1000)    (paper number, touched once at submission)

Determinism: seed=20260420. Stratified by ICD-10 parent label
(the 12-class schema from LingxiDiagBench Table 4).

Usage:
    uv run python scripts/generate_splits.py
    # writes configs/splits/lingxidiag16k_v2_5.yaml

The output yaml is committed to git so every reviewer gets the same split.
Regenerating is only necessary if the upstream LingxiDiag-16K parquet changes.
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import yaml
from sklearn.model_selection import train_test_split

from culturedx.eval.lingxidiag_paper import PAPER_12_CLASSES, gold_to_parent_list

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

RANDOM_STATE = 20260420
DEV_HPO_SIZE = 1000
SPLIT_YAML = ROOT / "configs" / "splits" / "lingxidiag16k_v2_5.yaml"


def _data_dir() -> Path:
    d = ROOT / "data" / "raw" / "lingxidiag16k"
    if (d / "data").is_dir():
        d = d / "data"
    return d


def _load_train() -> pd.DataFrame:
    files = sorted(_data_dir().glob("train-*.parquet"))
    if not files:
        raise FileNotFoundError(
            f"No train-*.parquet in {_data_dir()}. Fetch LingxiDiag-16K first."
        )
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def _load_validation() -> pd.DataFrame:
    files = sorted(_data_dir().glob("validation-*.parquet"))
    if not files:
        raise FileNotFoundError(
            f"No validation-*.parquet in {_data_dir()}. Fetch LingxiDiag-16K first."
        )
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def _primary_parent(codes_str: str) -> str:
    """Get the primary (first) parent class for stratification."""
    parents = gold_to_parent_list(codes_str)
    if not parents:
        return "Others"
    # Prefer the first paper-12 class; fall back to "Others"
    for p in parents:
        if p in PAPER_12_CLASSES:
            return p
    return "Others"


def _hash_ids(ids: list[str]) -> str:
    m = hashlib.sha256()
    for x in sorted(ids):
        m.update(x.encode("utf-8"))
        m.update(b"\n")
    return m.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true",
                        help="Overwrite an existing split yaml")
    args = parser.parse_args()

    if SPLIT_YAML.exists() and not args.force:
        logger.warning(
            "%s already exists. Pass --force to regenerate (this will "
            "invalidate every downstream result that used the old split).",
            SPLIT_YAML,
        )
        return

    logger.info("Loading LingxiDiag-16K train split...")
    train_df = _load_train()
    logger.info("  train: %d cases", len(train_df))

    logger.info("Loading LingxiDiag-16K validation split (== test_final)...")
    val_df = _load_validation()
    logger.info("  validation: %d cases", len(val_df))

    train_df["patient_id"] = train_df["patient_id"].astype(str)
    val_df["patient_id"] = val_df["patient_id"].astype(str)
    train_df["strat_label"] = train_df["DiagnosisCode"].apply(
        lambda c: _primary_parent(str(c))
    )

    # Report class distribution pre-split
    logger.info("Stratification label distribution on train:")
    for lbl, count in train_df["strat_label"].value_counts().items():
        logger.info("  %-8s  %5d  (%.2f%%)", lbl, count, 100 * count / len(train_df))

    # Stratified carve-out of dev_hpo from train
    logger.info("Carving %d dev_hpo cases (stratified, seed=%d)...",
                DEV_HPO_SIZE, RANDOM_STATE)
    rag_pool_df, dev_hpo_df = train_test_split(
        train_df,
        test_size=DEV_HPO_SIZE,
        stratify=train_df["strat_label"],
        random_state=RANDOM_STATE,
    )

    rag_ids = sorted(rag_pool_df["patient_id"].tolist())
    dev_ids = sorted(dev_hpo_df["patient_id"].tolist())
    test_ids = sorted(val_df["patient_id"].tolist())

    # Sanity: no overlap
    rag_set, dev_set, test_set = set(rag_ids), set(dev_ids), set(test_ids)
    assert not (rag_set & dev_set), "rag_pool / dev_hpo overlap"
    # train and validation are distinct shards already; assert anyway:
    assert not (rag_set & test_set), "rag_pool / test_final overlap"
    assert not (dev_set & test_set), "dev_hpo / test_final overlap"

    # Write yaml
    SPLIT_YAML.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": "v2.5",
        "dataset": "lingxidiag16k",
        "created_at_seed": RANDOM_STATE,
        "random_state": RANDOM_STATE,
        "dev_hpo_size": DEV_HPO_SIZE,
        "stratification": "primary parent class from DiagnosisCode (12-class paper schema)",
        "splits": {
            "rag_pool": {
                "n_cases": len(rag_ids),
                "source": "train parquet minus dev_hpo",
                "sha256": _hash_ids(rag_ids),
                "case_ids": rag_ids,
            },
            "dev_hpo": {
                "n_cases": len(dev_ids),
                "source": "train parquet, stratified sample",
                "sha256": _hash_ids(dev_ids),
                "case_ids": dev_ids,
            },
            "test_final": {
                "n_cases": len(test_ids),
                "source": "validation parquet (unchanged)",
                "sha256": _hash_ids(test_ids),
                "case_ids": test_ids,
            },
        },
    }
    with SPLIT_YAML.open("w", encoding="utf-8") as f:
        yaml.safe_dump(manifest, f, sort_keys=False, allow_unicode=True,
                       default_flow_style=False, width=120)

    logger.info("Wrote %s", SPLIT_YAML)
    logger.info("  rag_pool:   %d cases  sha256=%s",
                len(rag_ids), manifest["splits"]["rag_pool"]["sha256"][:16])
    logger.info("  dev_hpo:    %d cases  sha256=%s",
                len(dev_ids), manifest["splits"]["dev_hpo"]["sha256"][:16])
    logger.info("  test_final: %d cases  sha256=%s",
                len(test_ids), manifest["splits"]["test_final"]["sha256"][:16])

    # Post-hoc: check dev_hpo class distribution mirrors train
    logger.info("\nDev_hpo class distribution:")
    for lbl, count in dev_hpo_df["strat_label"].value_counts().items():
        logger.info("  %-8s  %4d  (%.2f%%)", lbl, count, 100 * count / len(dev_hpo_df))


if __name__ == "__main__":
    main()
