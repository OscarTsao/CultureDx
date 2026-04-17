#!/usr/bin/env python3
"""T2-RRF Reciprocal Rank Fusion ensemble: grid sweep + best combo selection.

Fuses predictions from multiple systems using RRF, sweeps hyperparameters,
evaluates with Table 4 metrics, and saves the best configuration.

Usage:
    uv run python scripts/run_ensemble.py
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.ensemble.rrf import ensemble_predictions
from culturedx.eval.lingxidiag_paper import compute_table4_metrics, pred_to_parent_list

import pyarrow.parquet as pq

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "raw" / "lingxidiag16k" / "data"
RESULTS_DIR = ROOT / "results" / "validation"
OUT_DIR = RESULTS_DIR / "t2_rrf"


def load_dataset_cases(data_dir: Path) -> dict[str, dict]:
    """Load original validation dataset to get raw DiagnosisCode per case."""
    parquet_files = sorted(data_dir.glob("validation-*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No validation parquet files in {data_dir}")

    table = pq.read_table(parquet_files)
    cases = {}
    for i in range(table.num_rows):
        row = {col: table.column(col)[i].as_py() for col in table.column_names}
        pid = str(row.get("patient_id", ""))
        if pid:
            cases[pid] = row
    logger.info("Loaded %d dataset cases from %s", len(cases), data_dir)
    return cases


def build_table4_cases(
    predictions: list[dict],
    dataset_cases: dict[str, dict],
) -> list[dict]:
    """Join predictions with dataset cases for Table 4 evaluation."""
    joined = []
    for pred in predictions:
        cid = pred.get("case_id", "")
        ds_row = dataset_cases.get(cid)
        if ds_row is None:
            continue
        case = {
            "case_id": cid,
            "DiagnosisCode": ds_row.get("DiagnosisCode", ""),
            "_primary_diagnosis": pred.get("primary_diagnosis"),
            "_comorbid_diagnoses": pred.get("comorbid_diagnoses", []),
            "_pred_codes": [pred.get("primary_diagnosis", "")] + pred.get("comorbid_diagnoses", []),
        }
        joined.append(case)
    return joined


def get_prediction(case: dict) -> list[str]:
    """Extract parent-level predictions from a joined case dict."""
    primary = case.get("_primary_diagnosis")
    comorbid = case.get("_comorbid_diagnoses", [])
    codes = []
    if primary:
        codes.append(primary)
    codes.extend(comorbid)
    return pred_to_parent_list(codes)


def main():
    # Discover prediction files
    pred_paths: list[str] = []
    path_labels: list[str] = []

    p1 = RESULTS_DIR / "factorial_b_improved_noevidence" / "predictions.jsonl"
    p2 = RESULTS_DIR / "05_dtv_v2_rag" / "predictions.jsonl"
    p3 = RESULTS_DIR / "multi_backbone" / "8b_bf16_dtv" / "predictions.jsonl"
    p3_alt = RESULTS_DIR / "multi_backbone" / "qwen3_8b_single" / "predictions.jsonl"

    for p, label in [(p1, "factorial_b"), (p2, "05_dtv_v2_rag")]:
        if p.exists():
            pred_paths.append(str(p))
            path_labels.append(label)
            logger.info("Found: %s", p)
        else:
            logger.error("MISSING required predictions: %s", p)
            sys.exit(1)

    # 3rd system (optional)
    if p3.exists():
        pred_paths.append(str(p3))
        path_labels.append("8b_bf16_dtv")
        logger.info("Found 3rd system: %s", p3)
    elif p3_alt.exists():
        pred_paths.append(str(p3_alt))
        path_labels.append("qwen3_8b_single")
        logger.info("Found 3rd system (alt): %s", p3_alt)
    else:
        logger.info("No 3rd system found; running 2-system ensemble")

    n_systems = len(pred_paths)
    logger.info("Ensemble will fuse %d systems: %s", n_systems, path_labels)

    # Load dataset for eval
    dataset_cases = load_dataset_cases(DATA_DIR)

    # Grid sweep
    k_values = [30, 60, 100]
    if n_systems == 3:
        weight_configs = [
            [1.0, 1.0, 1.0],
            [1.5, 1.0, 1.0],
            [1.0, 1.5, 1.0],
            [1.0, 1.0, 1.5],
        ]
    else:
        weight_configs = [
            [1.0, 1.0],
            [1.5, 1.0],
            [1.0, 1.5],
        ]

    best_overall = -1.0
    best_config = None
    best_metrics = None
    best_preds = None

    print(f"\n{'='*70}")
    print(f"T2-RRF Grid Sweep: {n_systems} systems, {len(k_values)} k x {len(weight_configs)} weight combos")
    print(f"{'='*70}\n")

    for k in k_values:
        for weights in weight_configs:
            # Run fusion
            fused_preds = ensemble_predictions(
                pred_paths=pred_paths,
                weights=weights,
                k=k,
                max_labels=2,
            )

            # Evaluate
            joined = build_table4_cases(fused_preds, dataset_cases)
            if not joined:
                logger.warning("k=%d weights=%s => 0 joined cases, skip", k, weights)
                continue

            metrics = compute_table4_metrics(joined, get_prediction)
            overall = metrics.get("Overall")
            if overall is None:
                continue

            tag = f"k={k:3d} w={[round(w,1) for w in weights]}"
            print(f"  {tag:40s}  Overall={overall:.4f}  (n={len(joined)})")

            if overall > best_overall:
                best_overall = overall
                best_config = {"k": k, "weights": weights}
                best_metrics = metrics
                best_preds = fused_preds

    if best_preds is None:
        logger.error("No valid configuration found!")
        sys.exit(1)

    # Save best
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pred_out = OUT_DIR / "predictions.jsonl"
    with open(pred_out, "w", encoding="utf-8") as f:
        for rec in best_preds:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    logger.info("Saved %d predictions to %s", len(best_preds), pred_out)

    metrics_out = OUT_DIR / "metrics.json"
    output = {
        "table4": best_metrics,
        "ensemble_config": best_config,
        "systems": path_labels,
        "n_systems": n_systems,
    }
    with open(metrics_out, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    logger.info("Saved metrics to %s", metrics_out)

    # Print summary
    baseline_overall = 0.527
    print(f"\n{'='*70}")
    print(f"BEST CONFIG: k={best_config['k']}, weights={best_config['weights']}")
    print(f"{'='*70}")
    for key, value in best_metrics.items():
        if key.endswith("_n"):
            print(f"  {key:25s}: {value}")
        elif value is not None:
            print(f"  {key:25s}: {value:.4f}")
        else:
            print(f"  {key:25s}: None")
    print(f"{'='*70}")
    print(f"  Overall (11-metric avg) : {best_overall:.4f}")
    delta = best_overall - baseline_overall
    direction = "+" if delta >= 0 else ""
    print(f"  vs baseline (0.527)     : {direction}{delta:.4f}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
