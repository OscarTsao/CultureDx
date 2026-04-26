#!/usr/bin/env python3
"""Compute paper-official Table 4 metrics using the v4 evaluation contract.

Reads predictions.jsonl from a completed run directory, joins the raw
DiagnosisCode from the source parquet, and computes the 11-metric Table 4 with
explicit prediction-source contracts via compute_table4_metrics_v2.

Usage:
    uv run python scripts/compute_table4.py \
        --run-dir outputs/eval/ablation_02_hied_dtv_1000 \
        --raw-parquet data/raw/lingxidiag16k/data/validation-00000-of-00001.parquet
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from culturedx.eval.lingxidiag_paper import (  # noqa: E402
    compute_table4_metrics_v2,
    to_paper_parent,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"predictions.jsonl not found: {path}")

    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _resolve_raw_parquet(raw_parquet: Path | None, data_path: Path | None) -> Path:
    if raw_parquet is not None:
        return raw_parquet

    if data_path is None:
        data_path = Path("data/raw/lingxidiag16k")

    data_dir = data_path / "data" if (data_path / "data").is_dir() else data_path
    parquet_files = sorted(data_dir.glob("validation-*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(
            f"No validation parquet found under {data_dir}. Pass --raw-parquet "
            "explicitly so raw DiagnosisCode values are available."
        )
    return parquet_files[0]


def _load_raw_codes(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(
            f"Raw parquet not found: {path}. Required for F41.2 raw-code "
            "2c/4c contract. No parent-gold fallback is allowed."
        )

    import pyarrow.parquet as pq

    table = pq.read_table(path)
    required = {"patient_id", "DiagnosisCode"}
    missing = required - set(table.column_names)
    if missing:
        raise RuntimeError(
            f"Raw parquet {path} missing columns {sorted(missing)}. "
            "Required for Table 4 raw-code evaluation."
        )

    raw_codes_by_id: dict[str, str] = {}
    for row_idx in range(table.num_rows):
        case_id = str(table["patient_id"][row_idx].as_py())
        raw_code = table["DiagnosisCode"][row_idx].as_py() or ""
        raw_codes_by_id[case_id] = str(raw_code)
    return raw_codes_by_id


def _extract_ranked(prediction: dict[str, Any]) -> list[str]:
    trace = prediction.get("decision_trace") or {}
    diagnostician = trace.get("diagnostician") or {}
    ranked = (
        trace.get("diagnostician_ranked")
        or (
            diagnostician.get("ranked_codes")
            if isinstance(diagnostician, dict)
            else None
        )
        or trace.get("ranked_codes")
        or prediction.get("ranked_codes")
        or prediction.get("candidate_disorders")
        or []
    )
    if not ranked and prediction.get("primary_diagnosis"):
        ranked = [prediction["primary_diagnosis"]]
    return [str(code) for code in ranked if code]


def _build_cases(
    predictions: list[dict[str, Any]],
    raw_codes_by_id: dict[str, str],
) -> list[dict[str, Any]]:
    missing = [
        str(prediction.get("case_id"))
        for prediction in predictions
        if str(prediction.get("case_id")) not in raw_codes_by_id
    ]
    if missing:
        raise RuntimeError(
            f"Raw DiagnosisCode missing for {len(missing)} cases: {missing[:5]}... "
            "NO silent fallback to parent-collapsed gold."
        )

    cases: list[dict[str, Any]] = []
    for prediction in predictions:
        case_id = str(prediction["case_id"])
        cases.append(
            {
                "case_id": case_id,
                "raw_gold_code": raw_codes_by_id[case_id],
                "primary_diagnosis": prediction.get("primary_diagnosis"),
                "ranked_codes": _extract_ranked(prediction),
                "comorbid_diagnoses": list(
                    prediction.get("comorbid_diagnoses") or []
                ),
            }
        )
    return cases


def _compute_table4(cases: list[dict[str, Any]]) -> dict[str, float | int | None]:
    def _primary(case: dict[str, Any]) -> str:
        return to_paper_parent(case["primary_diagnosis"])

    def _ranked(case: dict[str, Any]) -> list[str]:
        return [to_paper_parent(code) for code in case["ranked_codes"]]

    def _multilabel(case: dict[str, Any]) -> list[str]:
        codes = [case["primary_diagnosis"]]
        codes.extend(case["comorbid_diagnoses"])
        return [to_paper_parent(code) for code in codes if code]

    def _raw_gold(case: dict[str, Any]) -> str:
        return str(case["raw_gold_code"])

    def _raw_pred(case: dict[str, Any]) -> list[str]:
        codes = [case["primary_diagnosis"]]
        codes.extend(case["comorbid_diagnoses"])
        return [str(code) for code in codes if code]

    return compute_table4_metrics_v2(
        cases=cases,
        get_primary_prediction=_primary,
        get_ranked_prediction=_ranked,
        get_multilabel_prediction=_multilabel,
        get_raw_gold_code=_raw_gold,
        get_raw_pred_codes=_raw_pred,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute Table 4 metrics from predictions.jsonl"
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="Run output directory containing predictions.jsonl",
    )
    parser.add_argument(
        "--raw-parquet",
        type=Path,
        default=None,
        help="Parquet file with patient_id and DiagnosisCode columns",
    )
    parser.add_argument(
        "--data-path",
        type=Path,
        default=None,
        help="Backward-compatible dataset root; validation parquet is resolved from it",
    )
    parser.add_argument(
        "--out-name",
        default="table4_metrics.json",
        help="Output filename inside --run-dir",
    )
    args = parser.parse_args()

    predictions = _load_jsonl(args.run_dir / "predictions.jsonl")
    raw_parquet = _resolve_raw_parquet(args.raw_parquet, args.data_path)
    raw_codes_by_id = _load_raw_codes(raw_parquet)
    cases = _build_cases(predictions, raw_codes_by_id)
    table4 = _compute_table4(cases)

    out_path = args.run_dir / args.out_name
    out_path.write_text(
        json.dumps({"table4": table4}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    logger.info("Loaded %d predictions from %s", len(predictions), args.run_dir)
    logger.info("Loaded %d raw codes from %s", len(raw_codes_by_id), raw_parquet)
    logger.info("Wrote %s", out_path)
    logger.info(
        "Top-1: %.3f  Top-3: %.3f  F1_m: %.3f  2c_n: %s  Overall: %.4f",
        table4["12class_Top1"],
        table4["12class_Top3"],
        table4["12class_F1_macro"],
        table4["2class_n"],
        table4["Overall"],
    )


if __name__ == "__main__":
    main()
