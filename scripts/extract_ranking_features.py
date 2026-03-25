#!/usr/bin/env python3
"""Extract evidence-aware ranking features from predictions.

For each case, each confirmed disorder becomes a row with rich features:
1. Checker features: criteria_met_count, criteria_required, avg_confidence,
   threshold_ratio, core_score
2. Evidence features: n_evidence_spans, avg_span_confidence,
   n_disorders_with_evidence, evidence_coverage
3. Somatization features: n_somatic_mappings, somatic_criteria_met (B1, B2)
4. Cross-disorder features: confidence_margin, rank_position, n_confirmed_disorders
5. Label: 1 if this disorder is the gold primary, 0 otherwise

Outputs a parquet DataFrame to outputs/ranker_features/ranking_features.parquet.

Usage:
    uv run python scripts/extract_ranking_features.py
    uv run python scripts/extract_ranking_features.py \
        --sweep-dirs outputs/sweeps/final_mdd5k_20260324_120113 \
                     outputs/sweeps/final_lingxidiag_20260323_131847 \
        --conditions hied_no_evidence hied_bge-m3_evidence \
        --output outputs/ranker_features/ranking_features.parquet
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd

from culturedx.eval.metrics import normalize_icd_code
from culturedx.ontology.icd10 import (
    get_disorder_criteria,
    get_disorder_threshold,
)
from culturedx.ontology.symptom_map import load_somatization_map

# Somatization criteria IDs that indicate somatic presentation (B1, B2 type)
SOMATIC_CRITERION_IDS = {"B1", "B2"}

# Somatic group criteria (F45)
SOMATIC_GROUP_IDS = {"C1", "C2", "C3"}


def _compute_required(disorder_code: str, criteria_required_fallback: int) -> int:
    """Compute required criteria count from ICD-10 threshold (mirrors calibrator)."""
    threshold = get_disorder_threshold(disorder_code)
    if not threshold:
        return max(criteria_required_fallback, 1)
    if "min_total" in threshold:
        return max(threshold["min_total"], threshold.get("min_core", 0))
    if "min_symptoms" in threshold:
        return threshold["min_symptoms"]
    if threshold.get("all_required"):
        criteria = get_disorder_criteria(disorder_code)
        return len(criteria) if criteria else criteria_required_fallback
    if "min_first_rank" in threshold and "min_other" in threshold:
        return threshold["min_first_rank"]
    if "min_additional" in threshold:
        criteria = get_disorder_criteria(disorder_code) or {}
        core_count = sum(1 for v in criteria.values() if v.get("type") == "core")
        return core_count + threshold["min_additional"]
    if "min_symptoms_per_attack" in threshold:
        criteria = get_disorder_criteria(disorder_code) or {}
        core_count = sum(1 for v in criteria.values() if v.get("type") == "core")
        return core_count + threshold["min_symptoms_per_attack"]
    if "min_episodes" in threshold:
        return 2
    if "distress_required" in threshold:
        return 3
    if "frequency_per_week" in threshold:
        return 2
    if "trauma_required" in threshold:
        criteria = get_disorder_criteria(disorder_code) or {}
        return len(criteria) if criteria else 3
    if "min_somatic_groups" in threshold:
        return threshold["min_somatic_groups"] + 1
    if "onset_within_month" in threshold:
        criteria = get_disorder_criteria(disorder_code) or {}
        return len(criteria) if criteria else 2
    return max(criteria_required_fallback, 1)


def _compute_core_score(criteria_list: list[dict], disorder_code: str) -> float:
    """Weighted criterion score: core 1.5x, duration 1.3x, first_rank 1.5x."""
    criteria_def = get_disorder_criteria(disorder_code) or {}
    TYPE_WEIGHTS = {"core": 1.5, "duration": 1.3, "first_rank": 1.5, "exclusion": 1.2}
    weighted_sum = 0.0
    max_possible = 0.0
    for cr in criteria_list:
        cdef = criteria_def.get(cr["criterion_id"], {})
        ctype = cdef.get("type", "")
        w = TYPE_WEIGHTS.get(ctype, 1.0)
        max_possible += w
        if cr.get("status") == "met":
            weighted_sum += w * cr.get("confidence", 0.0)
    return weighted_sum / max_possible if max_possible > 0 else 0.0


def _compute_variance_penalty(met_criteria: list[dict]) -> float:
    """Penalty for high variance in criterion confidence. Returns [0, 1]."""
    if len(met_criteria) <= 1:
        return 1.0
    confs = [cr.get("confidence", 0.0) for cr in met_criteria]
    mean = sum(confs) / len(confs)
    variance = sum((c - mean) ** 2 for c in confs) / len(confs)
    normalized_var = min(1.0, variance / 0.25)
    return 1.0 - normalized_var


def _compute_info_content(met_count: int) -> float:
    """Info content: rewards more met criteria in absolute terms."""
    return min(1.0, math.log1p(met_count) / math.log1p(10))


def _count_somatic_mappings(disorder_code: str, met_criteria: list[dict]) -> int:
    """Count how many met criteria have somatization map entries for this disorder."""
    try:
        som_map = load_somatization_map()
    except Exception:
        return 0
    count = 0
    for entry in som_map.values():
        mapped_criteria = entry.get("criteria", [])
        for mc in mapped_criteria:
            # Entries like "F32.C6" or "F41.1.B1"
            parts = mc.rsplit(".", 1)
            if len(parts) == 2:
                d_code, c_id = parts[0], parts[1]
                if d_code == disorder_code:
                    # Check if this criterion is met
                    if any(cr["criterion_id"] == c_id and cr.get("status") == "met"
                           for cr in met_criteria):
                        count += 1
                        break  # Count each somatization entry once
    return count


def _somatic_criteria_met(criteria_list: list[dict]) -> int:
    """Count how many of B1, B2 type criteria are met (somatization indicators)."""
    return sum(
        1 for cr in criteria_list
        if cr.get("status") == "met" and cr["criterion_id"] in SOMATIC_CRITERION_IDS
    )


def extract_features_from_predictions(
    predictions: list[dict],
    gold_map: dict[str, list[str]],
    dataset_name: str,
    condition_name: str,
) -> list[dict]:
    """Extract per-(case, disorder) feature rows from predictions."""
    rows: list[dict] = []

    for pred in predictions:
        case_id = pred["case_id"]
        gold = gold_map.get(case_id, [])
        gold_primary_norm = normalize_icd_code(gold[0]) if gold else ""
        gold_all_norm = {normalize_icd_code(g) for g in gold}

        primary = pred.get("primary_diagnosis")
        comorbid = pred.get("comorbid_diagnoses", [])
        all_dx = [primary] + comorbid if primary else comorbid
        all_dx = [d for d in all_dx if d]

        criteria_results = pred.get("criteria_results", [])
        if not criteria_results:
            continue

        cr_map = {cr["disorder"]: cr for cr in criteria_results}
        n_confirmed = len(all_dx)

        # Pre-compute all confidences for cross-disorder features
        dx_confidences: dict[str, float] = {}
        for dx in all_dx:
            cr = cr_map.get(dx, {})
            criteria = cr.get("criteria", [])
            met = [c for c in criteria if c.get("status") == "met"]
            avg_c = sum(c.get("confidence", 0) for c in met) / len(met) if met else 0.0
            dx_confidences[dx] = avg_c

        for rank, dx in enumerate(all_dx):
            if not dx:
                continue

            cr = cr_map.get(dx, {})
            criteria = cr.get("criteria", [])
            met = [c for c in criteria if c.get("status") == "met"]

            # --- 1. Checker features ---
            n_met = len(met)
            n_total = len(criteria)
            criteria_required = cr.get("criteria_required", 1)
            required = _compute_required(dx, criteria_required)

            avg_conf = (
                sum(c.get("confidence", 0) for c in met) / len(met)
                if met else 0.0
            )
            threshold_ratio = (
                min(1.0, n_met / required) if required > 0 else 0.0
            )
            core_score = _compute_core_score(criteria, dx)
            variance_penalty = _compute_variance_penalty(met)
            info_content = _compute_info_content(n_met)

            # Margin: how far criteria met exceeds minimum threshold (normalized)
            if required > 0 and n_total > required:
                excess = max(0, n_met - required)
                max_excess = max(n_total - required, 1)
                excess_ratio = excess / max_excess
                margin = min(1.0, math.log1p(excess_ratio * 7) / math.log(8))
            else:
                margin = 0.5 if n_met > 0 and required <= 0 else 0.0

            # Min/max/std of met criterion confidences
            met_confs = [c.get("confidence", 0.0) for c in met]
            min_conf = min(met_confs) if met_confs else 0.0
            max_conf = max(met_confs) if met_confs else 0.0
            std_conf = (
                (sum((c - avg_conf) ** 2 for c in met_confs) / len(met_confs)) ** 0.5
                if len(met_confs) > 1 else 0.0
            )

            # --- 2. Evidence features ---
            n_evidence_spans = sum(
                1 for c in met
                if c.get("evidence") and c["evidence"].strip()
            )
            evidence_coverage = (
                n_evidence_spans / len(met) if met else 0.0
            )
            # Average span confidence (only for criteria with evidence)
            ev_confs = [
                c.get("confidence", 0.0) for c in met
                if c.get("evidence") and c["evidence"].strip()
            ]
            avg_span_confidence = (
                sum(ev_confs) / len(ev_confs) if ev_confs else 0.0
            )
            # How many disorders in this case have evidence
            n_disorders_with_evidence = 0
            for other_dx in all_dx:
                other_cr = cr_map.get(other_dx, {})
                other_criteria = other_cr.get("criteria", [])
                if any(c.get("evidence") and c["evidence"].strip()
                       for c in other_criteria if c.get("status") == "met"):
                    n_disorders_with_evidence += 1

            # Insufficient evidence count
            n_insufficient = sum(
                1 for c in criteria
                if c.get("status") == "insufficient_evidence"
            )
            insufficient_ratio = n_insufficient / n_total if n_total > 0 else 0.0

            # --- 3. Somatization features ---
            n_somatic_mappings = _count_somatic_mappings(dx, met)
            somatic_criteria_met = _somatic_criteria_met(criteria)

            # --- 4. Cross-disorder features ---
            # Confidence margin: gap to next-highest disorder confidence
            other_confs = sorted(
                [v for k, v in dx_confidences.items() if k != dx],
                reverse=True,
            )
            if other_confs:
                confidence_margin = avg_conf - other_confs[0]
            else:
                confidence_margin = 0.0

            # Rank position (0-indexed, primary = 0)
            rank_position = rank

            # --- 5. Label ---
            dx_parent = normalize_icd_code(dx)
            is_gold_primary = 1 if dx_parent == gold_primary_norm else 0
            is_gold_any = 1 if dx_parent in gold_all_norm else 0

            rows.append({
                "case_id": case_id,
                "dataset": dataset_name,
                "condition": condition_name,
                "disorder": dx,
                "disorder_parent": dx_parent,
                # Checker features
                "criteria_met_count": n_met,
                "criteria_total": n_total,
                "criteria_required": required,
                "avg_confidence": round(avg_conf, 4),
                "threshold_ratio": round(threshold_ratio, 4),
                "core_score": round(core_score, 4),
                "margin": round(margin, 4),
                "variance_penalty": round(variance_penalty, 4),
                "info_content": round(info_content, 4),
                "min_confidence": round(min_conf, 4),
                "max_confidence": round(max_conf, 4),
                "std_confidence": round(std_conf, 4),
                # Evidence features
                "n_evidence_spans": n_evidence_spans,
                "evidence_coverage": round(evidence_coverage, 4),
                "avg_span_confidence": round(avg_span_confidence, 4),
                "n_disorders_with_evidence": n_disorders_with_evidence,
                "n_insufficient": n_insufficient,
                "insufficient_ratio": round(insufficient_ratio, 4),
                # Somatization features
                "n_somatic_mappings": n_somatic_mappings,
                "somatic_criteria_met": somatic_criteria_met,
                # Cross-disorder features
                "confidence_margin": round(confidence_margin, 4),
                "rank_position": rank_position,
                "n_confirmed_disorders": n_confirmed,
                # Calibrator confidence (from prediction output)
                "calibrator_confidence": round(pred.get("confidence", 0.0), 4),
                # Labels
                "is_gold_primary": is_gold_primary,
                "is_gold_any": is_gold_any,
            })

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract evidence-aware ranking features from sweep predictions."
    )
    parser.add_argument(
        "--sweep-dirs",
        nargs="+",
        default=[
            "outputs/sweeps/final_mdd5k_20260324_120113",
            "outputs/sweeps/final_lingxidiag_20260323_131847",
        ],
        help="Sweep directories to process",
    )
    parser.add_argument(
        "--conditions",
        nargs="+",
        default=["hied_no_evidence", "hied_bge-m3_evidence"],
        help="Conditions (subdirectories) within each sweep",
    )
    parser.add_argument(
        "--output",
        default="outputs/ranker_features/ranking_features.parquet",
        help="Output parquet path",
    )
    args = parser.parse_args()

    all_rows: list[dict] = []

    for sweep_dir_str in args.sweep_dirs:
        sweep_dir = Path(sweep_dir_str)
        if not sweep_dir.exists():
            print(f"WARNING: sweep dir {sweep_dir} does not exist, skipping")
            continue

        # Infer dataset name from sweep dir
        name = sweep_dir.name
        if "mdd5k" in name:
            dataset_name = "mdd5k"
        elif "lingxidiag" in name or "lingxi" in name:
            dataset_name = "lingxidiag"
        elif "edaic" in name:
            dataset_name = "edaic"
        else:
            dataset_name = name

        # Load gold labels
        case_list_path = sweep_dir / "case_list.json"
        if not case_list_path.exists():
            print(f"WARNING: {case_list_path} not found, skipping")
            continue
        with open(case_list_path, encoding="utf-8") as f:
            gold_data = json.load(f)
        gold_map: dict[str, list[str]] = {
            c["case_id"]: c["diagnoses"] for c in gold_data["cases"]
        }

        for condition in args.conditions:
            pred_path = sweep_dir / condition / "predictions.json"
            if not pred_path.exists():
                print(f"  Skipping {dataset_name}/{condition}: no predictions.json")
                continue

            with open(pred_path, encoding="utf-8") as f:
                pred_data = json.load(f)

            predictions = pred_data.get("predictions", [])
            rows = extract_features_from_predictions(
                predictions, gold_map, dataset_name, condition,
            )
            print(
                f"  {dataset_name}/{condition}: "
                f"{len(rows)} feature rows from {len(predictions)} cases"
            )
            all_rows.extend(rows)

    if not all_rows:
        print("ERROR: No feature rows extracted. Check sweep dirs and conditions.")
        return

    df = pd.DataFrame(all_rows)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    print(f"\nSaved {len(df)} rows to {out_path}")

    # Summary statistics
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"  Total rows: {len(df)}")
    print(f"  Datasets: {df['dataset'].unique().tolist()}")
    print(f"  Conditions: {df['condition'].unique().tolist()}")
    print(f"  Disorders: {sorted(df['disorder_parent'].unique().tolist())}")
    print(f"  Cases: {df['case_id'].nunique()}")
    print(f"  Gold primary labels: {df['is_gold_primary'].sum()} / {len(df)} "
          f"({df['is_gold_primary'].mean():.1%})")
    print(f"  Gold any labels: {df['is_gold_any'].sum()} / {len(df)} "
          f"({df['is_gold_any'].mean():.1%})")

    # Calibrator baseline Top-1 accuracy
    # For each (case_id, dataset, condition), the rank=0 disorder is the calibrator's pick
    grouped = df.groupby(["case_id", "dataset", "condition"])
    calibrator_correct = 0
    total_cases = 0
    for (cid, ds, cond), group in grouped:
        primary_row = group[group["rank_position"] == 0]
        if not primary_row.empty:
            total_cases += 1
            if primary_row.iloc[0]["is_gold_primary"] == 1:
                calibrator_correct += 1
    if total_cases > 0:
        print(f"\n  Calibrator baseline Top-1: {calibrator_correct}/{total_cases} "
              f"({calibrator_correct/total_cases:.1%})")

    # Feature statistics
    feature_cols = [
        "criteria_met_count", "criteria_total", "criteria_required",
        "avg_confidence", "threshold_ratio", "core_score", "margin",
        "variance_penalty", "info_content", "min_confidence", "max_confidence",
        "std_confidence", "n_evidence_spans", "evidence_coverage",
        "avg_span_confidence", "n_disorders_with_evidence",
        "n_insufficient", "insufficient_ratio",
        "n_somatic_mappings", "somatic_criteria_met",
        "confidence_margin", "rank_position", "n_confirmed_disorders",
        "calibrator_confidence",
    ]
    print(f"\n  Feature stats (mean +/- std):")
    for col in feature_cols:
        if col in df.columns:
            print(f"    {col:30s}: {df[col].mean():.4f} +/- {df[col].std():.4f}")


if __name__ == "__main__":
    main()
