"""Train the MAS-conditioned stacker on dev_hpo features.

Two variants trained side-by-side:
    - LogisticRegression (multinomial, L2, class_weight=balanced)
    - LightGBM (optional; gracefully skipped if lightgbm not installed)

Both are multi-class over the 12 paper classes. Multi-label support is
delegated to eval_stacker.py via a probability threshold.

The trainer is STRICTLY dev_hpo-only. It refuses to load features labeled
with eval_split=test_final to prevent accidental leakage.

Output:
    outputs/stacker/
        stacker_lr.pkl
        stacker_lgbm.pkl        (only if lightgbm available)
        feature_names.json
        train_manifest.json     (hash of training data, sklearn version,
                                 random_state, hyperparameters)

Usage:
    uv run python scripts/stacker/train_stacker.py \\
        --features outputs/stacker_features/dev_hpo/features.jsonl \\
        --out-dir  outputs/stacker/
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import pickle
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from culturedx.eval.lingxidiag_paper import PAPER_12_CLASSES  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

RANDOM_STATE = 20260420


def _load_features(path: Path) -> tuple[np.ndarray, list[str], list[str], list[str], list[str]]:
    """Return (X, y_primary, case_ids, feature_names, gold_lists_json)."""
    X_rows, y_primary, case_ids, gold_lists = [], [], [], []
    feature_names: list[str] | None = None

    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("eval_split") == "test_final":
                raise RuntimeError(
                    "SAFETY STOP: features.jsonl contains records labeled "
                    "eval_split=test_final. Stacker training must use dev_hpo "
                    "only. Fix your feature pipeline."
                )
            if feature_names is None:
                feature_names = rec["feature_names"]
            else:
                assert rec["feature_names"] == feature_names, (
                    "feature_names mismatch across records"
                )

            X_rows.append(rec["features"])
            case_ids.append(rec["case_id"])
            golds = rec.get("gold_parents") or []
            gold_lists.append(json.dumps(golds, ensure_ascii=False))
            # Training target = first (primary) gold class, fallback Others
            primary = golds[0] if golds else "Others"
            if primary not in PAPER_12_CLASSES:
                primary = "Others"
            y_primary.append(primary)

    if not X_rows:
        raise RuntimeError(f"No records loaded from {path}")
    return np.array(X_rows, dtype=np.float64), y_primary, case_ids, feature_names, gold_lists


def _hash_training(X: np.ndarray, y: list[str]) -> str:
    h = hashlib.sha256()
    h.update(X.tobytes())
    for label in y:
        h.update(label.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def train_lr(X: np.ndarray, y_enc: np.ndarray) -> LogisticRegression:
    logger.info("Training LogisticRegression (multinomial, L2, C=1.0, balanced)...")
    clf = LogisticRegression(
        C=1.0,
        solver="lbfgs",
        class_weight="balanced",
        max_iter=5000,
        random_state=RANDOM_STATE,
    )
    clf.fit(X, y_enc)
    return clf


def train_lgbm(X: np.ndarray, y_enc: np.ndarray, n_classes: int):
    """Train LightGBM. Returns None if lightgbm is not available."""
    try:
        import lightgbm as lgb
    except ImportError:
        logger.warning("lightgbm not installed — skipping LGBM stacker.")
        return None

    logger.info("Training LightGBM (multiclass, 400 rounds, lr=0.05)...")
    dtrain = lgb.Dataset(X, label=y_enc)
    params = {
        "objective": "multiclass",
        "num_class": n_classes,
        "learning_rate": 0.05,
        "num_leaves": 31,
        "min_data_in_leaf": 10,
        "feature_fraction": 0.9,
        "bagging_fraction": 0.9,
        "bagging_freq": 5,
        "verbose": -1,
        "seed": RANDOM_STATE,
    }
    model = lgb.train(params, dtrain, num_boost_round=400)
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--features", type=Path, required=True,
                        help="Path to dev_hpo features.jsonl")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading training features from %s", args.features)
    X, y_primary, case_ids, feature_names, gold_lists = _load_features(args.features)
    logger.info("  X=%s  y distribution:", X.shape)
    from collections import Counter
    for cls, count in Counter(y_primary).most_common():
        logger.info("    %-8s  %4d", cls, count)

    # Encode to 12-class indices
    le = LabelEncoder()
    le.fit(PAPER_12_CLASSES)
    y_enc = le.transform(y_primary)

    # Train both variants
    lr_model = train_lr(X, y_enc)

    # Sanity — LR train accuracy (not a real metric, just to flag bugs)
    lr_train_acc = (lr_model.predict(X) == y_enc).mean()
    logger.info("  LR train accuracy: %.3f", lr_train_acc)

    lgbm_model = train_lgbm(X, y_enc, n_classes=len(PAPER_12_CLASSES))

    # Persist
    with (args.out_dir / "stacker_lr.pkl").open("wb") as f:
        pickle.dump({"model": lr_model, "label_encoder": le}, f)
    logger.info("Saved LR stacker -> %s", args.out_dir / "stacker_lr.pkl")

    if lgbm_model is not None:
        with (args.out_dir / "stacker_lgbm.pkl").open("wb") as f:
            pickle.dump({"model": lgbm_model, "label_encoder": le}, f)
        logger.info("Saved LGBM stacker -> %s", args.out_dir / "stacker_lgbm.pkl")

    (args.out_dir / "feature_names.json").write_text(
        json.dumps(feature_names, indent=2), encoding="utf-8",
    )

    manifest = {
        "random_state": RANDOM_STATE,
        "n_train": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "feature_names_sha256": hashlib.sha256(
            json.dumps(feature_names).encode("utf-8")
        ).hexdigest(),
        "training_data_sha256": _hash_training(X, y_primary),
        "models_trained": ["lr"] + (["lgbm"] if lgbm_model is not None else []),
        "class_order": PAPER_12_CLASSES,
        "lr_train_accuracy": float(lr_train_acc),
    }
    (args.out_dir / "train_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8",
    )
    logger.info("Wrote train_manifest.json")


if __name__ == "__main__":
    main()
