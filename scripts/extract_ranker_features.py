#!/usr/bin/env python3
"""Extract ranker training features from existing predictions.

For each case, each confirmed disorder becomes a row with features:
- threshold_ratio, avg_confidence, core_score, evidence_coverage, margin_score
- n_criteria_total, n_criteria_met, has_comorbid, confidence, is_correct (target)

Usage:
    uv run python scripts/extract_ranker_features.py \
        --sweep-dir outputs/sweeps/v10_lingxidiag_20260320_222603 \
        --condition hied_no_evidence \
        --output outputs/ranker_features/lingxidiag_features.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.eval.metrics import normalize_icd_code


def extract_features(
    predictions: list[dict], gold_map: dict[str, list[str]]
) -> list[dict]:
    """Extract per-(case, disorder) feature rows from predictions."""
    rows: list[dict] = []
    for pred in predictions:
        case_id = pred["case_id"]
        gold = gold_map.get(case_id, [])
        gold_parent = {normalize_icd_code(g) for g in gold}

        primary = pred.get("primary_diagnosis")
        comorbid = pred.get("comorbid_diagnoses", [])
        all_dx = [primary] + comorbid if primary else comorbid

        criteria_results = pred.get("criteria_results", [])
        if not criteria_results:
            continue

        cr_map = {cr["disorder"]: cr for cr in criteria_results}

        for rank, dx in enumerate(all_dx):
            if not dx:
                continue
            cr = cr_map.get(dx, {})
            criteria = cr.get("criteria", [])
            met = [c for c in criteria if c.get("status") == "met"]

            avg_conf = (
                sum(c.get("confidence", 0) for c in met) / len(met)
                if met
                else 0.0
            )
            n_met = len(met)
            n_total = len(criteria)
            required = cr.get("criteria_required", 1)
            threshold_ratio = (
                min(1.0, n_met / required) if required > 0 else 0.0
            )
            margin = (
                max(0, n_met - required) / max(n_total - required, 1)
                if n_total > required
                else 0.0
            )
            has_evidence = (
                sum(
                    1
                    for c in met
                    if c.get("evidence") and c["evidence"].strip()
                )
                / len(met)
                if met
                else 0.0
            )

            dx_parent = normalize_icd_code(dx)
            is_correct = 1 if dx_parent in gold_parent else 0

            rows.append({
                "case_id": case_id,
                "disorder": dx,
                "rank": rank,
                "is_primary": 1 if rank == 0 else 0,
                "threshold_ratio": round(threshold_ratio, 4),
                "avg_confidence": round(avg_conf, 4),
                "n_criteria_met": n_met,
                "n_criteria_total": n_total,
                "criteria_required": required,
                "margin": round(margin, 4),
                "evidence_coverage": round(has_evidence, 4),
                "has_comorbid": 1 if len(all_dx) > 1 else 0,
                "confidence": round(pred.get("confidence", 0), 4),
                "is_correct": is_correct,
            })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sweep-dir", required=True)
    parser.add_argument("--condition", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    sweep_dir = Path(args.sweep_dir)

    # Load gold
    with open(sweep_dir / "case_list.json", encoding="utf-8") as f:
        gold_data = json.load(f)
    gold_map: dict[str, list[str]] = {
        c["case_id"]: c["diagnoses"] for c in gold_data["cases"]
    }

    # Load predictions
    pred_path = sweep_dir / args.condition / "predictions.json"
    with open(pred_path, encoding="utf-8") as f:
        preds = json.load(f)["predictions"]

    rows = extract_features(preds, gold_map)
    print(f"Extracted {len(rows)} feature rows from {len(preds)} cases")

    if not rows:
        print(
            "WARNING: No feature rows extracted. "
            "predictions may lack criteria_results."
        )
        return

    # Save
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved to {out}")

    # Stats
    correct = sum(r["is_correct"] for r in rows)
    primary_correct = sum(
        r["is_correct"] for r in rows if r["is_primary"]
    )
    primary_total = sum(1 for r in rows if r["is_primary"])
    print(
        f"Correct labels: {correct}/{len(rows)} "
        f"({correct / len(rows):.1%})"
    )
    if primary_total > 0:
        print(
            f"Primary correct: {primary_correct}/{primary_total} "
            f"({primary_correct / primary_total:.1%})"
        )


if __name__ == "__main__":
    main()
