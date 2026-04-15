#!/usr/bin/env python3
"""Compute paper-official Table 4 metrics (2c/4c/12c + Overall) from predictions.

Reads predictions.jsonl from a completed run directory and the original dataset,
then computes the 11-metric Table 4 using the paper-aligned evaluation module.
Saves table4_metrics.json alongside the existing metrics.json.

This gives every ablation config the same 11-metric Overall formula used by the
research branch (0.527), ensuring cross-branch consistency.

Usage:
    uv run python scripts/compute_table4.py --run-dir outputs/eval/ablation_02_hied_dtv_1000
    uv run python scripts/compute_table4.py --run-dir outputs/eval/single_1000 --data-path data/raw/lingxidiag16k
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure src/ is importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.eval.lingxidiag_paper import (
    compute_table4_metrics,
    pred_to_parent_list,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def load_predictions(run_dir: Path) -> list[dict]:
    """Load prediction records from predictions.jsonl."""
    pred_path = run_dir / "predictions.jsonl"
    if not pred_path.exists():
        raise FileNotFoundError(f"No predictions.jsonl in {run_dir}")

    records = []
    with open(pred_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    logger.info("Loaded %d prediction records from %s", len(records), pred_path)
    return records


def load_dataset_cases(data_path: Path) -> dict[str, dict]:
    """Load original dataset to get raw DiagnosisCode per case.

    Returns a dict mapping case_id -> row dict with at least DiagnosisCode.
    """
    import pyarrow.parquet as pq

    data_dir = data_path
    if (data_dir / "data").is_dir():
        data_dir = data_dir / "data"

    parquet_files = sorted(data_dir.glob("validation-*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No parquet files found in {data_dir}")

    table = pq.read_table(parquet_files)
    cases = {}
    for i in range(table.num_rows):
        row = {col: table.column(col)[i].as_py() for col in table.column_names}
        patient_id = str(row.get("patient_id", ""))
        if patient_id:
            cases[patient_id] = row
    logger.info("Loaded %d dataset cases from %s", len(cases), data_dir)
    return cases


def build_table4_cases(
    predictions: list[dict],
    dataset_cases: dict[str, dict],
) -> list[dict]:
    """Join predictions with dataset cases for Table 4 evaluation.

    Returns a list of dicts with DiagnosisCode (from dataset) and predicted
    codes (from predictions.jsonl), suitable for compute_table4_metrics.
    """
    joined = []
    skipped = 0
    for pred in predictions:
        case_id = pred.get("case_id", "")
        dataset_row = dataset_cases.get(case_id)
        if dataset_row is None:
            skipped += 1
            continue

        # Build the joined case dict that compute_table4_metrics expects
        case = {
            "case_id": case_id,
            "DiagnosisCode": dataset_row.get("DiagnosisCode", ""),
            # Store prediction info for the getter function
            "_primary_diagnosis": pred.get("primary_diagnosis"),
            "_comorbid_diagnoses": pred.get("comorbid_diagnoses", []),
        }
        joined.append(case)

    if skipped:
        logger.warning(
            "Skipped %d predictions with no matching dataset case", skipped
        )
    logger.info("Joined %d cases for Table 4 evaluation", len(joined))
    return joined


def get_prediction(case: dict) -> list[str]:
    """Extract parent-level predictions from a joined case dict.

    This is the callback for compute_table4_metrics.
    """
    primary = case.get("_primary_diagnosis")
    comorbid = case.get("_comorbid_diagnoses", [])
    codes = []
    if primary:
        codes.append(primary)
    codes.extend(comorbid)
    return pred_to_parent_list(codes)


def main():
    parser = argparse.ArgumentParser(
        description="Compute Table 4 metrics from predictions.jsonl"
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="Path to the run output directory containing predictions.jsonl",
    )
    parser.add_argument(
        "--data-path",
        type=Path,
        default=Path("data/raw/lingxidiag16k"),
        help="Path to the original dataset directory",
    )
    args = parser.parse_args()

    # Load predictions and dataset
    predictions = load_predictions(args.run_dir)
    dataset_cases = load_dataset_cases(args.data_path)

    # Join and compute
    joined = build_table4_cases(predictions, dataset_cases)
    if not joined:
        logger.error("No cases to evaluate after joining. Exiting.")
        sys.exit(1)

    table4 = compute_table4_metrics(joined, get_prediction)

    # Save
    out_path = args.run_dir / "table4_metrics.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(table4, f, indent=2, ensure_ascii=False)

    # Also update existing metrics.json to include table4
    metrics_path = args.run_dir / "metrics.json"
    if metrics_path.exists():
        with open(metrics_path, encoding="utf-8") as f:
            metrics = json.load(f)
        metrics["table4"] = table4
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        logger.info("Updated metrics.json with table4 block")

    # Print summary
    print(f"\n{'='*60}")
    print(f"Table 4 Metrics: {args.run_dir.name}")
    print(f"{'='*60}")
    for key, value in table4.items():
        if key.endswith("_n"):
            print(f"  {key:25s}: {value}")
        elif value is not None:
            print(f"  {key:25s}: {value:.4f}")
        else:
            print(f"  {key:25s}: None")
    print(f"{'='*60}")
    overall = table4.get("Overall")
    if overall is not None:
        print(f"  Overall (11-metric avg) : {overall:.4f}")
    print()


if __name__ == "__main__":
    main()
