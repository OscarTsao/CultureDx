"""Evaluate frozen stacker on test_final. Touches test_final exactly once.

Reports Top-1, Top-3, F1-macro, F1-weighted, and the full Table-4 metrics.
Adds bootstrap 95% CI (1000 resamples, seed=20260420) and McNemar p-values
for the two most important baselines:
    H0_1: stacker Top-1 accuracy == TF-IDF Top-1 accuracy
    H0_2: stacker Top-1 accuracy == DtV primary Top-1 accuracy

If either H0 is rejected (p < 0.05), the stacker is a statistically
significant improvement over that baseline.

Usage:
    uv run python scripts/stacker/eval_stacker.py \\
        --features     outputs/stacker_features/test_final/features.jsonl \\
        --model        outputs/stacker/stacker_lr.pkl \\
        --tfidf-pred   outputs/tfidf_baseline/test_final/predictions.jsonl \\
        --dtv-pred     results/rebase_v2.5/B0_dtv/predictions.jsonl \\
        --out-dir      results/rebase_v2.5/stacker_lr/
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import pickle
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from culturedx.eval.lingxidiag_paper import (  # noqa: E402
    PAPER_12_CLASSES,
    compute_table4_metrics,
    to_paper_parent,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

BOOTSTRAP_SEED = 20260420
BOOTSTRAP_N = 1000


def _load_feature_jsonl(path: Path, required_split: str = "test_final") -> list[dict]:
    """Load features; refuse to eval on anything other than test_final."""
    recs = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("eval_split") != required_split:
                raise RuntimeError(
                    f"SAFETY STOP: feature record has eval_split="
                    f"{r.get('eval_split')!r}, expected {required_split!r}. "
                    f"Wrong split in evaluation."
                )
            recs.append(r)
    return recs


def _load_pred_jsonl(path: Path) -> dict[str, dict]:
    out = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            cid = str(r.get("case_id", ""))
            if cid:
                out[cid] = r
    return out


def _predict_with_model(model_bundle: dict, X: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """Return (proba 2d array shape (n,12), class_order)."""
    model = model_bundle["model"]
    le = model_bundle["label_encoder"]
    class_order = [str(label) for label in le.classes_]

    # LR or LGBM?
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(X)
    else:
        # LightGBM Booster
        proba = model.predict(X)
        if proba.ndim == 1:  # shouldn't happen for multiclass
            raise RuntimeError("LGBM returned 1-d probabilities")
    return proba, class_order


def _ranked_from_proba(proba_row: np.ndarray, class_order: list[str]) -> tuple[list[str], list[float]]:
    order = np.argsort(-proba_row)
    ranked_codes = [class_order[i] for i in order]
    ranked_scores = [float(proba_row[i]) for i in order]
    return ranked_codes, ranked_scores


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #
def _top1_correct(pred: str, gold_parents: list[str]) -> bool:
    return pred in set(gold_parents)


def _topk_correct(ranked: list[str], gold_parents: list[str], k: int) -> bool:
    gold_set = set(gold_parents)
    return any(r in gold_set for r in ranked[:k])


def bootstrap_ci(correct: list[int], n_resamples: int = BOOTSTRAP_N,
                 seed: int = BOOTSTRAP_SEED) -> tuple[float, float, float]:
    """Return (mean, lo95, hi95) for a 0/1 correctness vector."""
    arr = np.array(correct, dtype=np.int32)
    n = len(arr)
    if n == 0:
        return 0.0, 0.0, 0.0
    rng = np.random.RandomState(seed)
    resampled = np.empty(n_resamples)
    for i in range(n_resamples):
        idx = rng.randint(0, n, n)
        resampled[i] = arr[idx].mean()
    mean = float(arr.mean())
    lo, hi = np.percentile(resampled, [2.5, 97.5])
    return mean, float(lo), float(hi)


def mcnemar_p(a_correct: list[int], b_correct: list[int]) -> float:
    """McNemar's exact test. Returns two-sided p-value.

    a_correct, b_correct are aligned 0/1 vectors for the same cases.
    Tests H0: both classifiers have equal accuracy.
    """
    assert len(a_correct) == len(b_correct)
    # Discordant counts
    b_wins = sum(1 for a, b in zip(a_correct, b_correct) if (not a) and b)
    a_wins = sum(1 for a, b in zip(a_correct, b_correct) if a and (not b))
    n = a_wins + b_wins
    if n == 0:
        return 1.0
    k = min(a_wins, b_wins)
    # Two-sided exact binomial p with p=0.5
    p = 0.0
    for i in range(k + 1):
        p += math.comb(n, i) * (0.5 ** n)
    return min(1.0, 2.0 * p)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--features", type=Path, required=True,
                        help="test_final features.jsonl")
    parser.add_argument("--model", type=Path, required=True,
                        help="Frozen stacker model (.pkl)")
    parser.add_argument("--tfidf-pred", type=Path, required=True,
                        help="TF-IDF predictions on the same split (for McNemar)")
    parser.add_argument("--dtv-pred", type=Path, required=True,
                        help="DtV predictions on the same split (for McNemar)")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading test_final features: %s", args.features)
    feats = _load_feature_jsonl(args.features, required_split="test_final")
    logger.info("  %d records", len(feats))

    logger.info("Loading stacker model: %s", args.model)
    with args.model.open("rb") as f:
        bundle = pickle.load(f)

    # Feature matrix
    X = np.array([r["features"] for r in feats], dtype=np.float64)
    case_ids = [r["case_id"] for r in feats]
    gold_map = {r["case_id"]: r["gold_parents"] for r in feats}

    logger.info("Running stacker inference...")
    proba, class_order = _predict_with_model(bundle, X)
    if set(class_order) != set(PAPER_12_CLASSES):
        raise RuntimeError(
            "Model class set mismatch: "
            f"{class_order} vs expected {PAPER_12_CLASSES}"
        )

    # Per-case prediction records
    stacker_preds: dict[str, dict] = {}
    for cid, row in zip(case_ids, proba):
        ranked, scores = _ranked_from_proba(row, class_order)
        stacker_preds[cid] = {
            "case_id": cid,
            "gold_diagnoses": gold_map[cid],
            "primary_diagnosis": ranked[0],
            "comorbid_diagnoses": (
                [ranked[1]] if scores[1] >= 0.3 else []
            ),
            "ranked_codes": ranked,
            "proba_scores": [round(s, 6) for s in scores],
        }

    # Write predictions
    pred_path = args.out_dir / "predictions.jsonl"
    with pred_path.open("w", encoding="utf-8") as f:
        for rec in stacker_preds.values():
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    logger.info("Wrote predictions -> %s", pred_path)

    # --------------------------- Aggregate metrics -------------------------- #
    # Build compute_table4_metrics inputs
    case_dicts = []
    for cid in case_ids:
        gold = gold_map[cid]
        case_dicts.append({
            "case_id": cid,
            "DiagnosisCode": ",".join(gold),
            "diagnoses": gold,
            "diagnosis_code_full": ",".join(gold),
            "four_class_label": None,
        })
    def get_stacker_pred(case: dict) -> list[str]:
        rec = stacker_preds.get(case["case_id"])
        if rec is None:
            return []
        return [rec["primary_diagnosis"]] + rec.get("comorbid_diagnoses", [])

    logger.info("Computing Table-4 metrics...")
    table4 = compute_table4_metrics(case_dicts, get_stacker_pred)

    # Top-1 correctness per case (for bootstrap + McNemar)
    stacker_correct = [
        1 if _top1_correct(stacker_preds[cid]["primary_diagnosis"], gold_map[cid]) else 0
        for cid in case_ids
    ]
    stacker_top3 = [
        1 if _topk_correct(stacker_preds[cid]["ranked_codes"], gold_map[cid], 3) else 0
        for cid in case_ids
    ]

    # Baselines for comparison
    logger.info("Loading TF-IDF predictions: %s", args.tfidf_pred)
    tfidf_preds = _load_pred_jsonl(args.tfidf_pred)
    logger.info("Loading DtV predictions: %s", args.dtv_pred)
    dtv_preds = _load_pred_jsonl(args.dtv_pred)

    def _align_top1(pred_map: dict) -> list[int]:
        out = []
        for cid in case_ids:
            p = pred_map.get(cid)
            if not p:
                out.append(0)  # treat missing as wrong
                continue
            pred_parent = to_paper_parent(p.get("primary_diagnosis", ""))
            out.append(1 if _top1_correct(pred_parent,
                                          gold_map[cid]) else 0)
        return out

    tfidf_correct = _align_top1(tfidf_preds)
    dtv_correct = _align_top1(dtv_preds)

    # Bootstrap CIs
    stacker_mean, stacker_lo, stacker_hi = bootstrap_ci(stacker_correct)
    stacker_top3_mean, stacker_top3_lo, stacker_top3_hi = bootstrap_ci(stacker_top3)
    tfidf_mean, tfidf_lo, tfidf_hi = bootstrap_ci(tfidf_correct)
    dtv_mean, dtv_lo, dtv_hi = bootstrap_ci(dtv_correct)

    p_vs_tfidf = mcnemar_p(tfidf_correct, stacker_correct)
    p_vs_dtv = mcnemar_p(dtv_correct, stacker_correct)

    # Stacker feature-ordering analysis (LR only — LGBM has its own path)
    model = bundle["model"]
    feature_analysis = None
    if hasattr(model, "coef_"):
        # Per-class coefficient sums (abs) to identify most influential features
        feat_names = json.loads(
            (args.model.parent / "feature_names.json").read_text(encoding="utf-8")
        ) if (args.model.parent / "feature_names.json").exists() else [
            f"f{i}" for i in range(X.shape[1])
        ]
        abs_coefs = np.abs(model.coef_).sum(axis=0)
        top_ranked = sorted(
            zip(feat_names, abs_coefs.tolist()),
            key=lambda kv: -kv[1],
        )[:10]
        feature_analysis = {
            "top10_influential_features": [
                {"name": n, "summed_abs_coef": round(v, 4)} for n, v in top_ranked
            ],
        }

    # Write summary
    summary = {
        "split": "test_final",
        "n": len(case_ids),
        "stacker_model": str(args.model),
        "table4": table4,
        "top1_stacker": {"mean": stacker_mean, "ci95": [stacker_lo, stacker_hi]},
        "top3_stacker": {"mean": stacker_top3_mean, "ci95": [stacker_top3_lo, stacker_top3_hi]},
        "top1_tfidf_baseline": {"mean": tfidf_mean, "ci95": [tfidf_lo, tfidf_hi]},
        "top1_dtv_baseline": {"mean": dtv_mean, "ci95": [dtv_lo, dtv_hi]},
        "mcnemar_stacker_vs_tfidf_p": p_vs_tfidf,
        "mcnemar_stacker_vs_dtv_p": p_vs_dtv,
        "bootstrap_config": {
            "n_resamples": BOOTSTRAP_N,
            "seed": BOOTSTRAP_SEED,
        },
    }
    if feature_analysis:
        summary["feature_importance"] = feature_analysis

    summary_path = args.out_dir / "metrics.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                            encoding="utf-8")

    # Human-readable report
    print("\n" + "=" * 72)
    print("STACKER EVALUATION ON test_final")
    print("=" * 72)
    print(f"{'Metric':<30s} {'Mean':>8s} {'95% CI':>20s}")
    print("-" * 72)
    print(f"{'Stacker Top-1':<30s} {stacker_mean:>8.4f}  "
          f"[{stacker_lo:.4f}, {stacker_hi:.4f}]")
    print(f"{'Stacker Top-3':<30s} {stacker_top3_mean:>8.4f}  "
          f"[{stacker_top3_lo:.4f}, {stacker_top3_hi:.4f}]")
    print(f"{'TF-IDF alone Top-1':<30s} {tfidf_mean:>8.4f}  "
          f"[{tfidf_lo:.4f}, {tfidf_hi:.4f}]")
    print(f"{'DtV alone Top-1':<30s} {dtv_mean:>8.4f}  "
          f"[{dtv_lo:.4f}, {dtv_hi:.4f}]")
    print()
    sig_tfidf = "SIGNIFICANT" if p_vs_tfidf < 0.05 else "not sig"
    sig_dtv = "SIGNIFICANT" if p_vs_dtv < 0.05 else "not sig"
    print(f"McNemar stacker vs TF-IDF:  p = {p_vs_tfidf:.4f}  ({sig_tfidf})")
    print(f"McNemar stacker vs DtV:     p = {p_vs_dtv:.4f}  ({sig_dtv})")
    print()
    print(f"F1-macro:     {table4.get('12class_F1_macro', 'n/a')}")
    print(f"F1-weighted:  {table4.get('12class_F1_weighted', 'n/a')}")
    print(f"Overall:      {table4.get('Overall', 'n/a')}")
    if feature_analysis:
        print()
        print("Top-10 influential features (summed |coef| across classes):")
        for item in feature_analysis["top10_influential_features"]:
            print(f"  {item['name']:<35s} {item['summed_abs_coef']:.4f}")
    print()
    print(f"Full metrics written to: {summary_path}")


if __name__ == "__main__":
    main()
