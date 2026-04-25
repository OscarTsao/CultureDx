#!/usr/bin/env python3
"""Recompute dual-standard Table 4 metrics from existing predictions.

This script performs no model inference. It reads predictions.jsonl, joins raw
LingxiDiag DiagnosisCode values from parquet, applies the v2 evaluation
contract, updates metrics.json, and verifies the regenerated contract.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from culturedx.eval.lingxidiag_paper import (  # noqa: E402
    compute_table4_metrics_v2,
    to_paper_parent,
    verify_evaluation_contract,
)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise RuntimeError(f"Predictions file not found: {path}")
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_raw_codes(path: Path) -> dict[str, str]:
    if not path.exists():
        raise RuntimeError(
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
            "Required for F41.2 raw-code evaluation contract."
        )

    out: dict[str, str] = {}
    for row_idx in range(table.num_rows):
        cid = str(table["patient_id"][row_idx].as_py())
        raw_code = table["DiagnosisCode"][row_idx].as_py() or ""
        out[cid] = str(raw_code)
    return out


def _extract_ranked(prediction: dict[str, Any]) -> list[str]:
    trace = prediction.get("decision_trace") or {}
    diagnostician = trace.get("diagnostician") or {}
    ranked = (
        trace.get("diagnostician_ranked")
        or (diagnostician.get("ranked_codes") if isinstance(diagnostician, dict) else None)
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
        cid = str(prediction["case_id"])
        cases.append(
            {
                "case_id": cid,
                "raw_gold_code": raw_codes_by_id[cid],
                "primary_diagnosis": prediction.get("primary_diagnosis"),
                "ranked_codes": _extract_ranked(prediction),
                "comorbid_diagnoses": list(prediction.get("comorbid_diagnoses") or []),
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--raw-parquet", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-two-class-n", type=int, default=473)
    args = parser.parse_args()

    predictions = _load_jsonl(args.predictions)
    print(f"Loaded {len(predictions)} predictions from {args.predictions}")
    raw_codes_by_id = _load_raw_codes(args.raw_parquet)
    print(f"Loaded {len(raw_codes_by_id)} raw codes from {args.raw_parquet}")

    cases = _build_cases(predictions, raw_codes_by_id)
    print(f"Raw code coverage: {len(cases)}/{len(predictions)}")

    table4 = _compute_table4(cases)
    if table4["12class_Top3"] < table4["12class_Top1"] - 1e-6:
        raise RuntimeError(
            f"Top-3 ({table4['12class_Top3']}) < Top-1 ({table4['12class_Top1']})"
        )
    if len(cases) == 1000 and table4["2class_n"] != args.expected_two_class_n:
        raise RuntimeError(
            f"Expected 2class_n={args.expected_two_class_n}, got {table4['2class_n']}"
        )

    f41_2_count = sum(1 for case in cases if "F41.2" in str(case["raw_gold_code"]))
    print(f"F41.2 count in gold: {f41_2_count}")

    metrics = json.loads(args.out.read_text(encoding="utf-8")) if args.out.exists() else {}
    metrics["table4"] = table4
    metrics["metric_definitions"] = {
        "12class_Top1_source": "primary_diagnosis (paper-parent)",
        "12class_Top3_source": "[primary] + (ranked_codes - {primary})[:2] (paper-parent)",
        "12class_F1_source": "primary + threshold-gated comorbid_diagnoses (paper-parent multilabel)",
        "12class_exact_match_source": "same as F1 (multilabel)",
        "2class_gold_source": "raw DiagnosisCode (F41.2 excluded)",
        "2class_pred_source": "primary_diagnosis (paper-parent)",
        "4class_gold_source": "raw DiagnosisCode (F41.2 -> Mixed)",
        "4class_pred_source": "primary + raw_pred_codes for F41.2 detection",
        "Overall_source": "mean(non-_n metrics)",
        "post_fix_version": "v4 (eval_contract_repair_2026_04_25)",
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    verify_evaluation_contract(args.out)

    print(f"Wrote {args.out}")
    print(f"  Top-1:   {table4['12class_Top1']:.3f}")
    print(f"  Top-3:   {table4['12class_Top3']:.3f}")
    print(f"  F1_m:    {table4['12class_F1_macro']:.3f}")
    print(f"  2c_n:    {table4['2class_n']}")
    print(f"  Overall: {table4['Overall']:.4f}")


if __name__ == "__main__":
    main()
