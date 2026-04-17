#!/usr/bin/env python3
"""T4-F1-OPT: per-class score-offset calibration to maximise 12-class F1_macro.

Pipeline (100 % CPU, no GPU):
1.  Load per-class scores from three systems
    - factorial_b  (met_ratio from raw_checker_outputs)
    - dtv05        (met_ratio from raw_checker_outputs)
    - TF-IDF       (proba_scores aligned to ranked_codes)
2.  RRF-fuse the three score vectors per case -> 12-dim score vector
3.  Split validation 500 / 500 (seed=42): calibration / held-out
4.  Coordinate descent on calibration set:
    For each parent class, sweep offset in a grid; pick the offset that
    maximises F1_macro.  Repeat for up to 5 epochs until convergence.
5.  Apply best offsets to held-out set; evaluate.
6.  If held-out F1_macro improves >= 2 pp, apply to full N=1000.

Usage:
    uv run python scripts/f1_macro_offset_sweep.py
"""
from __future__ import annotations

import json
import logging
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score
from sklearn.preprocessing import MultiLabelBinarizer

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.eval.lingxidiag_paper import (
    PAPER_12_CLASSES,
    compute_table4_metrics,
    gold_to_parent_list,
    pred_to_parent_list,
    to_paper_parent,
)

import pyarrow.parquet as pq

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "raw" / "lingxidiag16k" / "data"
RESULTS_DIR = ROOT / "results" / "validation"
OUT_DIR = RESULTS_DIR / "t4_f1_opt"

PARENT_CLASSES = list(PAPER_12_CLASSES)       # 12 classes
CLASS_TO_IDX = {c: i for i, c in enumerate(PARENT_CLASSES)}

# RRF k that was best for T2/T3
RRF_K = 30

# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def load_dataset_cases(data_dir: Path) -> dict[str, dict]:
    """Load original validation dataset."""
    parquet_files = sorted(data_dir.glob("validation-*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No validation parquet in {data_dir}")
    table = pq.read_table(parquet_files)
    cases = {}
    for i in range(table.num_rows):
        row = {col: table.column(col)[i].as_py() for col in table.column_names}
        pid = str(row.get("patient_id", ""))
        if pid:
            cases[pid] = row
    logger.info("Loaded %d dataset cases", len(cases))
    return cases


def _parent(code: str) -> str:
    """Collapse a disorder_code to its 12-class parent."""
    return to_paper_parent(code)


def load_dtv_scores(path: Path) -> dict[str, np.ndarray]:
    """Load DtV predictions -> {case_id: 12-dim met_ratio vector}."""
    out: dict[str, np.ndarray] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line.strip())
            cid = rec.get("case_id", "")
            if not cid:
                continue
            vec = np.zeros(12, dtype=np.float64)
            rco = rec.get("decision_trace", {}).get("raw_checker_outputs", [])
            # For sub-codes that map to the same parent, take the max met_ratio
            for item in rco:
                if not isinstance(item, dict):
                    continue
                code = item.get("disorder_code", "")
                parent = _parent(code)
                if parent not in CLASS_TO_IDX:
                    continue
                idx = CLASS_TO_IDX[parent]
                mr = float(item.get("met_ratio", 0.0))
                vec[idx] = max(vec[idx], mr)
            out[cid] = vec
    return out


def load_tfidf_scores(path: Path) -> dict[str, np.ndarray]:
    """Load TF-IDF predictions -> {case_id: 12-dim proba vector}."""
    out: dict[str, np.ndarray] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line.strip())
            cid = rec.get("case_id", "")
            if not cid:
                continue
            vec = np.zeros(12, dtype=np.float64)
            ranked = rec.get("ranked_codes", [])
            probas = rec.get("proba_scores", [])
            for code, p in zip(ranked, probas):
                parent = _parent(code)
                if parent not in CLASS_TO_IDX:
                    continue
                idx = CLASS_TO_IDX[parent]
                vec[idx] = max(vec[idx], float(p))
            out[cid] = vec
    return out


# ---------------------------------------------------------------------------
# RRF fusion on score vectors
# ---------------------------------------------------------------------------

def rrf_fuse_vectors(
    score_dicts: list[dict[str, np.ndarray]],
    weights: list[float],
    k: int = 60,
) -> dict[str, np.ndarray]:
    """RRF-fuse multiple per-case score vectors into one per-case vector.

    For each system i and case c:
      - Sort the 12 classes by score (descending) -> ranking
      - For each class at rank r (1-indexed):
            rrf_score[class] += weight_i / (k + r)
    """
    # Intersect case ids
    common = set(score_dicts[0].keys())
    for sd in score_dicts[1:]:
        common &= set(sd.keys())

    fused: dict[str, np.ndarray] = {}
    for cid in common:
        result = np.zeros(12, dtype=np.float64)
        for sd, w in zip(score_dicts, weights):
            vec = sd[cid]
            # Rank: highest score gets rank 1
            order = np.argsort(-vec)  # indices sorted by descending score
            for rank_0, idx in enumerate(order):
                rank_1 = rank_0 + 1
                result[idx] += w / (k + rank_1)
        fused[cid] = result
    return fused


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def _predict_from_scores(
    scores: np.ndarray,
    offsets: np.ndarray | None = None,
    max_labels: int = 1,
) -> list[str]:
    """Pick top-1 (or top-k) parent classes from adjusted score vector."""
    s = scores.copy()
    if offsets is not None:
        s += offsets
    order = np.argsort(-s)
    primary = PARENT_CLASSES[order[0]]
    result = [primary]
    if max_labels > 1:
        top_score = s[order[0]]
        for i in range(1, len(order)):
            if top_score > 0 and s[order[i]] / top_score > 0.5:
                result.append(PARENT_CLASSES[order[i]])
            if len(result) >= max_labels:
                break
    return result


def compute_12class_f1_macro(
    case_ids: list[str],
    fused_scores: dict[str, np.ndarray],
    gold_map: dict[str, list[str]],
    offsets: np.ndarray | None = None,
    max_labels: int = 1,
) -> float:
    """Quick F1_macro computation for the 12-class multilabel task."""
    mlb = MultiLabelBinarizer(classes=PARENT_CLASSES)
    y_true = []
    y_pred = []
    for cid in case_ids:
        gold = gold_map.get(cid)
        if gold is None:
            continue
        pred = _predict_from_scores(fused_scores[cid], offsets, max_labels)
        y_true.append(gold)
        y_pred.append(pred)
    if not y_true:
        return 0.0
    y_true_bin = mlb.fit_transform(y_true)
    y_pred_bin = mlb.transform(y_pred)
    return float(f1_score(y_true_bin, y_pred_bin, average="macro", zero_division=0))


def compute_full_table4(
    case_ids: list[str],
    fused_scores: dict[str, np.ndarray],
    dataset_cases: dict[str, dict],
    offsets: np.ndarray | None = None,
    max_labels: int = 1,
) -> dict:
    """Run the full 11-metric Table 4 evaluation."""
    joined = []
    for cid in case_ids:
        ds = dataset_cases.get(cid)
        if ds is None:
            continue
        pred = _predict_from_scores(fused_scores[cid], offsets, max_labels)
        joined.append({
            "case_id": cid,
            "DiagnosisCode": ds.get("DiagnosisCode", ""),
            "_primary_diagnosis": pred[0],
            "_comorbid_diagnoses": pred[1:],
            "_pred_codes": pred,
        })

    def _get_pred(case: dict) -> list[str]:
        return pred_to_parent_list(case.get("_pred_codes", []))

    return compute_table4_metrics(joined, _get_pred)


# ---------------------------------------------------------------------------
# Coordinate descent
# ---------------------------------------------------------------------------

def coordinate_descent(
    case_ids: list[str],
    fused_scores: dict[str, np.ndarray],
    gold_map: dict[str, list[str]],
    max_epochs: int = 5,
    grid: list[float] | None = None,
    max_labels: int = 1,
) -> tuple[np.ndarray, float, list[dict]]:
    """Coordinate descent to find per-class offsets maximising F1_macro."""
    if grid is None:
        grid = [-0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5]

    offsets = np.zeros(12, dtype=np.float64)
    history: list[dict] = []

    base_f1 = compute_12class_f1_macro(case_ids, fused_scores, gold_map, offsets, max_labels)
    logger.info("Coordinate descent start: F1_macro=%.6f", base_f1)
    history.append({"epoch": 0, "f1_macro": base_f1, "offsets": offsets.tolist()})

    for epoch in range(1, max_epochs + 1):
        improved = False
        for cls_idx in range(12):
            best_val = offsets[cls_idx]
            best_f1 = compute_12class_f1_macro(case_ids, fused_scores, gold_map, offsets, max_labels)
            for delta in grid:
                offsets[cls_idx] = delta
                f1 = compute_12class_f1_macro(case_ids, fused_scores, gold_map, offsets, max_labels)
                if f1 > best_f1 + 1e-9:
                    best_f1 = f1
                    best_val = delta
                    improved = True
            offsets[cls_idx] = best_val

        epoch_f1 = compute_12class_f1_macro(case_ids, fused_scores, gold_map, offsets, max_labels)
        logger.info("Epoch %d: F1_macro=%.6f  offsets=%s", epoch, epoch_f1,
                     [round(o, 2) for o in offsets.tolist()])
        history.append({"epoch": epoch, "f1_macro": epoch_f1, "offsets": offsets.tolist()})

        if not improved:
            logger.info("Converged at epoch %d", epoch)
            break

    final_f1 = compute_12class_f1_macro(case_ids, fused_scores, gold_map, offsets, max_labels)
    return offsets, final_f1, history


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Paths
    factorial_b_path = RESULTS_DIR / "factorial_b_improved_noevidence" / "predictions.jsonl"
    dtv05_path = RESULTS_DIR / "05_dtv_v2_rag" / "predictions.jsonl"
    tfidf_path = ROOT / "outputs" / "tfidf_baseline" / "predictions.jsonl"

    for p in [factorial_b_path, dtv05_path, tfidf_path]:
        if not p.exists():
            logger.error("MISSING: %s", p)
            sys.exit(1)

    # 1. Load per-class scores
    logger.info("Loading per-class scores...")
    fb_scores = load_dtv_scores(factorial_b_path)
    dtv_scores = load_dtv_scores(dtv05_path)
    tfidf_scores = load_tfidf_scores(tfidf_path)
    logger.info("factorial_b: %d cases, dtv05: %d cases, tfidf: %d cases",
                len(fb_scores), len(dtv_scores), len(tfidf_scores))

    # 2. RRF-fuse (same weights/k as T3: equal weights, k=30, with TF-IDF boosted)
    # T3 config: k=30 w=tfidf++ max=1  =>  tfidf gets higher weight
    weights = [1.0, 1.0, 1.5]  # fb, dtv, tfidf (tfidf++)
    fused = rrf_fuse_vectors([fb_scores, dtv_scores, tfidf_scores], weights, k=RRF_K)
    logger.info("RRF-fused %d cases (intersection)", len(fused))

    # Load dataset for evaluation
    dataset_cases = load_dataset_cases(DATA_DIR)

    # Build gold label map  {case_id -> [parent labels]}
    gold_map: dict[str, list[str]] = {}
    for cid, ds in dataset_cases.items():
        raw = str(ds.get("DiagnosisCode", "") or "")
        gold_map[cid] = gold_to_parent_list(raw)

    # Only keep cases present in fused
    all_ids = sorted(fused.keys())
    logger.info("Total fused case_ids: %d", len(all_ids))

    # 3. Split 500/500
    rng = np.random.RandomState(42)
    perm = rng.permutation(len(all_ids))
    calib_ids = [all_ids[i] for i in perm[:500]]
    held_ids = [all_ids[i] for i in perm[500:1000]]
    logger.info("Calibration: %d, Held-out: %d", len(calib_ids), len(held_ids))

    # Baseline: no offsets
    baseline_calib_f1 = compute_12class_f1_macro(calib_ids, fused, gold_map, max_labels=1)
    baseline_held_f1 = compute_12class_f1_macro(held_ids, fused, gold_map, max_labels=1)
    baseline_full_f1 = compute_12class_f1_macro(all_ids, fused, gold_map, max_labels=1)
    logger.info("Baseline F1_macro => calib=%.4f held=%.4f full=%.4f",
                baseline_calib_f1, baseline_held_f1, baseline_full_f1)

    # Baseline full Table4
    baseline_table4 = compute_full_table4(all_ids, fused, dataset_cases, max_labels=1)
    logger.info("Baseline Overall (full): %.4f", baseline_table4.get("Overall", 0))

    # 4. Coordinate descent on calibration set
    print(f"\n{'='*70}")
    print("T4-F1-OPT: Coordinate Descent on Calibration Set (N=500)")
    print(f"{'='*70}")

    offsets, calib_f1, history = coordinate_descent(
        calib_ids, fused, gold_map,
        max_epochs=5,
        max_labels=1,
    )

    print(f"\nLearned offsets:")
    for i, cls in enumerate(PARENT_CLASSES):
        print(f"  {cls:8s}: {offsets[i]:+.2f}")
    print(f"\nCalibration F1_macro: {baseline_calib_f1:.4f} -> {calib_f1:.4f} ({calib_f1 - baseline_calib_f1:+.4f})")

    # 5. Apply to held-out
    held_f1 = compute_12class_f1_macro(held_ids, fused, gold_map, offsets, max_labels=1)
    print(f"\nHeld-out F1_macro:    {baseline_held_f1:.4f} -> {held_f1:.4f} ({held_f1 - baseline_held_f1:+.4f})")

    improvement_pp = (held_f1 - baseline_held_f1) * 100
    print(f"Improvement: {improvement_pp:+.1f} pp")

    # 6. If >= 2pp improvement, apply to full N=1000
    apply_full = improvement_pp >= 2.0
    final_offsets = offsets if apply_full else np.zeros(12, dtype=np.float64)
    label = "CALIBRATED" if apply_full else "UNCALIBRATED (improvement < 2pp)"

    print(f"\n{'='*70}")
    print(f"Applying to full N=1000: {label}")
    print(f"{'='*70}")

    full_f1 = compute_12class_f1_macro(all_ids, fused, gold_map, final_offsets, max_labels=1)
    full_table4 = compute_full_table4(all_ids, fused, dataset_cases, final_offsets, max_labels=1)

    print(f"\nFull N=1000 results (with {'offsets' if apply_full else 'no offsets'}):")
    print(f"  12class_F1_macro:  {baseline_full_f1:.4f} -> {full_f1:.4f} ({full_f1 - baseline_full_f1:+.4f})")
    print(f"  Overall:           {baseline_table4.get('Overall', 0):.4f} -> {full_table4.get('Overall', 0):.4f}")

    print(f"\nFull Table 4 metrics:")
    for key, value in full_table4.items():
        if key.endswith("_n"):
            print(f"  {key:25s}: {value}")
        elif value is not None:
            print(f"  {key:25s}: {value:.4f}")
        else:
            print(f"  {key:25s}: None")

    # Per-class breakdown
    print(f"\n{'='*70}")
    print("Per-class F1 breakdown (full N=1000, with offsets)")
    print(f"{'='*70}")
    mlb = MultiLabelBinarizer(classes=PARENT_CLASSES)
    y_true_all, y_pred_all = [], []
    for cid in all_ids:
        y_true_all.append(gold_map.get(cid, ["Others"]))
        y_pred_all.append(_predict_from_scores(fused[cid], final_offsets, max_labels=1))
    y_true_bin = mlb.fit_transform(y_true_all)
    y_pred_bin = mlb.transform(y_pred_all)
    per_class_f1 = f1_score(y_true_bin, y_pred_bin, average=None, zero_division=0)
    for i, cls in enumerate(PARENT_CLASSES):
        # Count support
        support = int(y_true_bin[:, i].sum())
        pred_count = int(y_pred_bin[:, i].sum())
        print(f"  {cls:8s}: F1={per_class_f1[i]:.4f}  support={support:4d}  predicted={pred_count:4d}  offset={final_offsets[i]:+.2f}")

    # Save results
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Save predictions
    pred_out = OUT_DIR / "predictions.jsonl"
    with open(pred_out, "w", encoding="utf-8") as f:
        for cid in all_ids:
            pred = _predict_from_scores(fused[cid], final_offsets, max_labels=1)
            ds = dataset_cases.get(cid, {})
            rec = {
                "case_id": cid,
                "gold_diagnoses": gold_map.get(cid, []),
                "primary_diagnosis": pred[0],
                "comorbid_diagnoses": pred[1:],
                "decision_trace": {
                    "fused_scores": {PARENT_CLASSES[j]: round(float(fused[cid][j]), 6) for j in range(12)},
                    "offsets": {PARENT_CLASSES[j]: round(float(final_offsets[j]), 4) for j in range(12)},
                    "adjusted_scores": {PARENT_CLASSES[j]: round(float(fused[cid][j] + final_offsets[j]), 6) for j in range(12)},
                },
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    logger.info("Saved predictions to %s", pred_out)

    # Save metrics
    metrics_out = OUT_DIR / "metrics.json"
    result = {
        "table4": full_table4,
        "baseline_table4": baseline_table4,
        "offsets": {PARENT_CLASSES[i]: round(float(final_offsets[i]), 4) for i in range(12)},
        "calibration": {
            "baseline_f1_macro": baseline_calib_f1,
            "optimized_f1_macro": calib_f1,
            "delta_pp": round((calib_f1 - baseline_calib_f1) * 100, 2),
        },
        "held_out": {
            "baseline_f1_macro": baseline_held_f1,
            "optimized_f1_macro": held_f1,
            "delta_pp": round((held_f1 - baseline_held_f1) * 100, 2),
        },
        "full": {
            "baseline_f1_macro": baseline_full_f1,
            "optimized_f1_macro": full_f1,
            "delta_pp": round((full_f1 - baseline_full_f1) * 100, 2),
        },
        "applied_offsets": apply_full,
        "convergence_history": history,
        "ensemble_config": {
            "systems": ["factorial_b", "dtv05", "tfidf"],
            "weights": weights,
            "rrf_k": RRF_K,
        },
        "per_class_f1": {PARENT_CLASSES[i]: round(float(per_class_f1[i]), 4) for i in range(12)},
    }
    with open(metrics_out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    logger.info("Saved metrics to %s", metrics_out)

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    t3_overall = 0.535
    t3_f1_macro = 0.233
    new_overall = full_table4.get("Overall", 0)
    new_f1 = full_table4.get("12class_F1_macro", 0)
    print(f"  T3-TFIDF-STACK baseline:  Overall={t3_overall:.3f}  F1_macro={t3_f1_macro:.3f}")
    print(f"  T4-F1-OPT result:         Overall={new_overall:.4f}  F1_macro={new_f1:.4f}")
    print(f"  Delta Overall:  {new_overall - t3_overall:+.4f}")
    print(f"  Delta F1_macro: {new_f1 - t3_f1_macro:+.4f}")
    print(f"{'='*70}")
    print(f"\nResults saved to: {OUT_DIR}")


if __name__ == "__main__":
    main()
