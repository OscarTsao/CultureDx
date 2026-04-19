#!/usr/bin/env python3
"""Final combined pipeline: stack all zero-GPU improvements on top of a DtV run.

Takes a DtV pipeline output (e.g. t1_diag_topk predictions.jsonl) and applies:
  Stage 2: Comorbid cap (drop_all by default)
  Stage 3: RRF ensemble with TF-IDF baseline
  Stage 4: F1-OPT per-class offset calibration
  Stage 5: Top-3 reporting fix using ranked_codes

Produces final combined predictions and metrics.

Usage:
  # On LingxiDiag validation
  python3 scripts/run_final_combined.py \
    --dtv-run results/validation/t1_diag_topk \
    --tfidf-run results/validation/tfidf_baseline \
    --output-dir results/validation/final_combined \
    --fit-offsets

  # On MDD-5k (apply LingxiDiag-fit offsets for fair OOD eval)
  python3 scripts/run_final_combined.py \
    --dtv-run results/external/mdd5k_t1_diag_topk \
    --tfidf-run results/external/mdd5k_tfidf_baseline \
    --output-dir results/external/mdd5k_final_combined \
    --offsets-from results/validation/final_combined/offsets.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import copy
from pathlib import Path
from collections import Counter

import numpy as np
from sklearn.metrics import f1_score
from sklearn.preprocessing import MultiLabelBinarizer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from culturedx.eval.lingxidiag_paper import (
    PAPER_12_CLASSES,
    pred_to_parent_list,
    gold_to_parent_list,
    to_paper_parent,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# =========================================================================
# I/O
# =========================================================================

def load_predictions(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def save_predictions(records: list[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def extract_ranked_codes(rec: dict) -> list[str]:
    dt = rec.get("decision_trace") or {}
    if isinstance(dt, dict):
        diag = dt.get("diagnostician")
        if isinstance(diag, dict):
            r = diag.get("ranked_codes")
            if r: return [c for c in r if c]
        r = dt.get("diagnostician_ranked")
        if r: return [c for c in r if c]
    for key in ("ranked_codes", "ranked_diagnoses"):
        v = rec.get(key)
        if v:
            if isinstance(v[0], str):
                return [c for c in v if c]
            if isinstance(v[0], dict):
                return [item.get("code", "") for item in v if item.get("code")]
    return []


# =========================================================================
# Stage 2: Comorbid cap
# =========================================================================

def apply_comorbid_cap(records: list[dict], strategy: str = "drop_all") -> list[dict]:
    """Apply comorbid cap strategy (default: drop all comorbid)."""
    out = []
    for rec in records:
        new = copy.deepcopy(rec)
        if strategy == "drop_all":
            new["comorbid_diagnoses"] = []
        out.append(new)
    return out


# =========================================================================
# Stage 3: RRF ensemble
# =========================================================================

def rrf_fuse_records(
    dtv_records: list[dict],
    tfidf_records: list[dict],
    weights: tuple[float, float] = (1.0, 0.7),
    k: int = 30,
) -> list[dict]:
    """Fuse DtV + TF-IDF using RRF; return new records with primary/comorbid updated."""
    tfidf_map = {r.get("case_id", ""): r for r in tfidf_records}

    fused = []
    for dtv in dtv_records:
        cid = dtv.get("case_id", "")
        tfidf = tfidf_map.get(cid)

        # DtV ranked: primary + ranked_codes + comorbid
        dtv_primary = dtv.get("primary_diagnosis")
        dtv_ranked = extract_ranked_codes(dtv)
        dtv_comorbid = dtv.get("comorbid_diagnoses") or []
        dtv_ordered = []
        if dtv_primary: dtv_ordered.append(dtv_primary)
        for r in dtv_ranked:
            if r not in dtv_ordered:
                dtv_ordered.append(r)
        for c in dtv_comorbid:
            if c not in dtv_ordered:
                dtv_ordered.append(c)

        # TF-IDF ranked
        tfidf_ordered = []
        if tfidf:
            tfidf_ranked = extract_ranked_codes(tfidf)
            if tfidf_ranked:
                tfidf_ordered = tfidf_ranked
            else:
                tp = tfidf.get("primary_diagnosis")
                tc = tfidf.get("comorbid_diagnoses") or []
                if tp: tfidf_ordered.append(tp)
                tfidf_ordered.extend(tc)

        # RRF fuse
        scores = Counter()
        for rank, code in enumerate(dtv_ordered):
            parent = to_paper_parent(code)
            scores[parent] += weights[0] / (k + rank + 1)
        for rank, code in enumerate(tfidf_ordered):
            parent = to_paper_parent(code)
            scores[parent] += weights[1] / (k + rank + 1)

        # Sort by fused score
        sorted_codes = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        new_rec = copy.deepcopy(dtv)
        if sorted_codes:
            new_rec["primary_diagnosis"] = sorted_codes[0][0]
            new_rec["comorbid_diagnoses"] = []  # stay single-label for Acc
            # Store fused scores for Stage 4 offset calibration
            new_rec["_fused_scores"] = dict(scores)
            # Rebuild ranked_codes from fused order (for Top-3)
            new_rec["_ranked_by_fusion"] = [c for c, _ in sorted_codes]
        fused.append(new_rec)

    return fused


# =========================================================================
# Stage 4: F1-OPT coordinate descent
# =========================================================================

def compute_f1_macro(records: list[dict], offsets: dict[str, float] | None = None) -> float:
    y_true = []
    y_pred = []
    for rec in records:
        golds_raw = rec.get("gold_diagnoses") or []
        golds = gold_to_parent_list(",".join(str(g) for g in golds_raw if g)) or ["Others"]
        y_true.append(golds)

        scores = rec.get("_fused_scores", {})
        if offsets:
            scores = {c: s + offsets.get(c, 0.0) for c, s in scores.items()}
        if scores:
            best = max(scores.items(), key=lambda x: x[1])[0]
        else:
            best = to_paper_parent(rec.get("primary_diagnosis") or "Others")
        y_pred.append([best])

    mlb = MultiLabelBinarizer(classes=PAPER_12_CLASSES)
    yt_bin = mlb.fit_transform(y_true)
    yp_bin = mlb.transform(y_pred)
    return float(f1_score(yt_bin, yp_bin, average="macro", zero_division=0))


def fit_f1_offsets(
    records: list[dict],
    grid: list[float] | None = None,
    n_epochs: int = 5,
) -> tuple[dict[str, float], float]:
    """Coordinate descent on per-class offsets to maximize F1_macro."""
    if grid is None:
        # Grid is ~0.1-sigma scaled around RRF score range (small; RRF scores ~0-0.1)
        base_offset = 0.00227676
        grid = [-4*base_offset, -2*base_offset, -base_offset, 0.0,
                base_offset, 2*base_offset, 4*base_offset]

    offsets = {c: 0.0 for c in PAPER_12_CLASSES}
    best_f1 = compute_f1_macro(records, offsets)
    logger.info(f"F1-OPT start: F1_m = {best_f1:.4f}")

    for epoch in range(n_epochs):
        improved = False
        for cls in PAPER_12_CLASSES:
            best_delta = 0.0
            for delta in grid:
                trial_offsets = dict(offsets)
                trial_offsets[cls] = offsets[cls] + delta
                f1 = compute_f1_macro(records, trial_offsets)
                if f1 > best_f1 + 1e-6:
                    best_f1 = f1
                    best_delta = delta
                    improved = True
            if best_delta != 0.0:
                offsets[cls] += best_delta
        logger.info(f"  epoch {epoch+1}: F1_m = {best_f1:.4f}")
        if not improved:
            break

    return offsets, best_f1


def apply_f1_offsets(records: list[dict], offsets: dict[str, float]) -> list[dict]:
    """Apply offsets, update primary_diagnosis."""
    out = []
    for rec in records:
        new = copy.deepcopy(rec)
        scores = rec.get("_fused_scores", {})
        if scores:
            adjusted = {c: s + offsets.get(c, 0.0) for c, s in scores.items()}
            best = max(adjusted.items(), key=lambda x: x[1])
            new["primary_diagnosis"] = best[0]
            # Re-rank for Top-3
            sorted_codes = sorted(adjusted.items(), key=lambda x: (-x[1], x[0]))
            new["_ranked_by_fusion"] = [c for c, _ in sorted_codes]
            new["_offsets_applied"] = offsets
        out.append(new)
    return out


# =========================================================================
# Stage 5: Top-3 reporting fix (in-memory version)
# =========================================================================

def compute_top3_with_ranked(records: list[dict]) -> float:
    hits = 0
    n = 0
    for rec in records:
        golds_raw = rec.get("gold_diagnoses") or []
        golds = set(gold_to_parent_list(",".join(str(g) for g in golds_raw if g)))
        if not golds: golds = {"Others"}

        # Prefer _ranked_by_fusion (Stage 3/4), fallback to ranked_codes, then primary+comorbid
        codes = rec.get("_ranked_by_fusion")
        if not codes:
            codes = extract_ranked_codes(rec)
            if not codes:
                primary = rec.get("primary_diagnosis")
                comorbid = rec.get("comorbid_diagnoses") or []
                codes = ([primary] if primary else []) + list(comorbid)
        parent_codes = pred_to_parent_list(codes)
        if not parent_codes:
            parent_codes = ["Others"]
        if set(parent_codes[:3]) & golds:
            hits += 1
        n += 1
    return hits / n if n else 0.0


# =========================================================================
# Final metrics computation
# =========================================================================

def compute_all_metrics(records: list[dict]) -> dict:
    """Compute Table-4 metrics: 12c Acc/Top-1/Top-3/F1_macro/F1_weighted + Overall."""
    y_true = []
    y_pred = []
    exact = 0
    top1 = 0

    for rec in records:
        golds_raw = rec.get("gold_diagnoses") or []
        golds = gold_to_parent_list(",".join(str(g) for g in golds_raw if g))
        if not golds: golds = ["Others"]

        primary = rec.get("primary_diagnosis")
        comorbid = rec.get("comorbid_diagnoses") or []
        pred_codes = pred_to_parent_list(([primary] if primary else []) + list(comorbid))
        if not pred_codes: pred_codes = ["Others"]

        y_true.append(golds)
        y_pred.append(pred_codes)

        if set(pred_codes) == set(golds):
            exact += 1
        if pred_codes[0] in set(golds):
            top1 += 1

    n = len(records)
    mlb = MultiLabelBinarizer(classes=PAPER_12_CLASSES)
    yt = mlb.fit_transform(y_true)
    yp = mlb.transform(y_pred)

    f1_m = float(f1_score(yt, yp, average="macro", zero_division=0))
    f1_w = float(f1_score(yt, yp, average="weighted", zero_division=0))
    top3 = compute_top3_with_ranked(records)

    table4 = {
        "12class_Acc": exact / n,
        "12class_Top1": top1 / n,
        "12class_Top3": top3,
        "12class_F1_macro": f1_m,
        "12class_F1_weighted": f1_w,
        "12class_n": n,
    }
    # Overall for just 12c metrics (no 2c/4c since we don't have parquet)
    vals = [v for k, v in table4.items() if not k.endswith("_n") and v is not None]
    table4["Overall_12c_only"] = sum(vals) / len(vals) if vals else 0.0
    return table4


# =========================================================================
# Main pipeline
# =========================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dtv-run", type=Path, required=True,
                    help="Path to DtV run dir with predictions.jsonl (e.g. t1_diag_topk)")
    ap.add_argument("--tfidf-run", type=Path, required=True,
                    help="Path to TF-IDF baseline run dir")
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--comorbid-strategy", default="drop_all",
                    choices=["drop_all", "keep"])
    ap.add_argument("--rrf-k", type=int, default=30)
    ap.add_argument("--rrf-weights", type=float, nargs=2, default=[1.0, 0.7],
                    metavar=("DTV_W", "TFIDF_W"))
    ap.add_argument("--fit-offsets", action="store_true",
                    help="Fit F1-OPT offsets on these records (for in-distribution)")
    ap.add_argument("--offsets-from", type=Path, default=None,
                    help="Load pre-fit offsets from JSON (for OOD eval)")
    args = ap.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Stage 1: Load DtV run (assumes already exists from GPU run)
    logger.info(f"Stage 1: Loading DtV run from {args.dtv_run}")
    dtv_records = load_predictions(args.dtv_run / "predictions.jsonl")
    logger.info(f"  Loaded {len(dtv_records)} DtV predictions")
    metrics_before = compute_all_metrics(dtv_records)
    logger.info(f"  DtV baseline: Top-1={metrics_before['12class_Top1']:.3f}, "
                f"Top-3={metrics_before['12class_Top3']:.3f}, "
                f"Acc={metrics_before['12class_Acc']:.3f}, "
                f"F1_m={metrics_before['12class_F1_macro']:.3f}")

    # Stage 2: Comorbid cap
    logger.info(f"Stage 2: Applying comorbid cap ({args.comorbid_strategy})")
    stage2 = apply_comorbid_cap(dtv_records, args.comorbid_strategy)
    metrics_s2 = compute_all_metrics(stage2)
    logger.info(f"  After: Acc={metrics_s2['12class_Acc']:.3f}, "
                f"F1_m={metrics_s2['12class_F1_macro']:.3f}")

    # Stage 3: RRF ensemble
    logger.info(f"Stage 3: RRF ensemble with TF-IDF (k={args.rrf_k}, "
                f"weights={args.rrf_weights})")
    tfidf_records = load_predictions(args.tfidf_run / "predictions.jsonl")
    stage3 = rrf_fuse_records(
        stage2, tfidf_records,
        weights=tuple(args.rrf_weights), k=args.rrf_k,
    )
    metrics_s3 = compute_all_metrics(stage3)
    logger.info(f"  After RRF: Top-1={metrics_s3['12class_Top1']:.3f}, "
                f"F1_m={metrics_s3['12class_F1_macro']:.3f}")

    # Stage 4: F1-OPT
    if args.fit_offsets:
        logger.info("Stage 4: Fitting F1-OPT offsets (coordinate descent)")
        offsets, _ = fit_f1_offsets(stage3)
        # Save offsets for downstream OOD use
        with (args.output_dir / "offsets.json").open("w") as f:
            json.dump(offsets, f, indent=2)
        logger.info(f"  Saved offsets to {args.output_dir / 'offsets.json'}")
    elif args.offsets_from:
        logger.info(f"Stage 4: Loading F1-OPT offsets from {args.offsets_from}")
        with args.offsets_from.open() as f:
            offsets = json.load(f)
    else:
        logger.info("Stage 4: Skipping F1-OPT (no --fit-offsets or --offsets-from)")
        offsets = None

    if offsets:
        stage4 = apply_f1_offsets(stage3, offsets)
        metrics_s4 = compute_all_metrics(stage4)
        logger.info(f"  After F1-OPT: F1_m={metrics_s4['12class_F1_macro']:.3f}")
    else:
        stage4 = stage3
        metrics_s4 = metrics_s3

    # Stage 5: Top-3 fix is baked into compute_all_metrics (uses _ranked_by_fusion)
    logger.info("Stage 5: Top-3 fix (baked into final metrics)")

    # Save final outputs
    # Strip internal fields from saved predictions
    saved = []
    for rec in stage4:
        clean = {k: v for k, v in rec.items() if not k.startswith("_")}
        saved.append(clean)
    save_predictions(saved, args.output_dir / "predictions.jsonl")
    logger.info(f"Saved {len(saved)} final predictions to {args.output_dir}")

    # Save final metrics (includes all stages for comparison)
    final_metrics = {
        "pipeline_stages": ["dtv_baseline", "comorbid_cap", "rrf_ensemble",
                           "f1_opt" if offsets else "skip_f1_opt", "top3_fix"],
        "config": {
            "comorbid_strategy": args.comorbid_strategy,
            "rrf_k": args.rrf_k,
            "rrf_weights": args.rrf_weights,
            "f1_opt_mode": "fit" if args.fit_offsets else ("load" if args.offsets_from else "skip"),
        },
        "metrics_per_stage": {
            "stage_1_dtv_baseline": metrics_before,
            "stage_2_comorbid_cap": metrics_s2,
            "stage_3_rrf_ensemble": metrics_s3,
            "stage_4_f1_opt": metrics_s4,
        },
        "table4": metrics_s4,
        "offsets": offsets or {},
    }
    with (args.output_dir / "metrics_combined.json").open("w") as f:
        json.dump(final_metrics, f, indent=2, ensure_ascii=False)

    print("\n" + "="*72)
    print("FINAL COMBINED PIPELINE RESULTS")
    print("="*72)
    print(f"{'Stage':<30} {'Acc':>7} {'Top-1':>7} {'Top-3':>7} {'F1_m':>7} {'F1_w':>7}")
    for stage_name, m in final_metrics["metrics_per_stage"].items():
        print(f"{stage_name:<30} "
              f"{m['12class_Acc']:>7.3f} "
              f"{m['12class_Top1']:>7.3f} "
              f"{m['12class_Top3']:>7.3f} "
              f"{m['12class_F1_macro']:>7.3f} "
              f"{m['12class_F1_weighted']:>7.3f}")
    print(f"\nOverall (12c mean): {metrics_s4['Overall_12c_only']:.4f}")
    print("(Run scripts/compute_table4.py with parquet data for full 2c/4c Overall)\n")


if __name__ == "__main__":
    main()
