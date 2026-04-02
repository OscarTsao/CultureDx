"""Evaluate DtV results using Table 4 metrics with full diagnostician ranking."""
import json
import sys
sys.path.insert(0, "/home/user/YuNing/CultureDx/src")

from culturedx.eval.lingxidiag_paper import (
    compute_table4_metrics,
    pred_to_parent_list,
    to_paper_parent,
)


def load_results(path: str) -> list[dict]:
    results = []
    with open(path) as f:
        for line in f:
            results.append(json.loads(line))
    return results


def get_prediction_dtv(case: dict) -> list[str]:
    """Use diagnostician ranking for full ranked prediction."""
    trace = case.get("decision_trace", {})
    ranked = trace.get("diagnostician_ranked", [])
    if ranked:
        # Convert ICD-10 codes to parent-level, dedup preserving order
        parents = []
        seen = set()
        for code in ranked:
            parent = to_paper_parent(code)
            if parent not in seen:
                seen.add(parent)
                parents.append(parent)
        return parents if parents else ["Others"]
    # Fallback to primary_diagnosis
    primary = case.get("primary_diagnosis", "")
    comorbid = case.get("comorbid_diagnoses", [])
    return pred_to_parent_list([primary] + comorbid)


def get_prediction_primary_only(case: dict) -> list[str]:
    """Use only primary_diagnosis (no ranking info)."""
    primary = case.get("primary_diagnosis", "")
    comorbid = case.get("comorbid_diagnoses", [])
    return pred_to_parent_list([primary] + comorbid)


def print_table4(label: str, metrics: dict):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  2-class  Acc={metrics.get('2class_Acc', 'N/A'):.3f}  "
          f"F1m={metrics.get('2class_F1_macro', 'N/A'):.3f}  "
          f"F1w={metrics.get('2class_F1_weighted', 'N/A'):.3f}  "
          f"(n={metrics.get('2class_n', 0)})")
    print(f"  4-class  Acc={metrics.get('4class_Acc', 'N/A'):.3f}  "
          f"F1m={metrics.get('4class_F1_macro', 'N/A'):.3f}  "
          f"F1w={metrics.get('4class_F1_weighted', 'N/A'):.3f}  "
          f"(n={metrics.get('4class_n', 0)})")
    print(f"  12-class Acc={metrics.get('12class_Acc', 'N/A'):.3f}  "
          f"Top1={metrics.get('12class_Top1', 'N/A'):.3f}  "
          f"Top3={metrics.get('12class_Top3', 'N/A'):.3f}  "
          f"F1m={metrics.get('12class_F1_macro', 'N/A'):.3f}  "
          f"F1w={metrics.get('12class_F1_weighted', 'N/A'):.3f}  "
          f"(n={metrics.get('12class_n', 0)})")
    print(f"  Overall={metrics.get('Overall', 'N/A'):.3f}")


if __name__ == "__main__":
    dtv_path = "/home/user/YuNing/CultureDx/outputs/eval/hied_dtv_validation/results_lingxidiag.jsonl"
    dtv_cases = load_results(dtv_path)
    print(f"Loaded {len(dtv_cases)} DtV results")

    # DtV with full diagnostician ranking (proper top-3)
    m_dtv_ranked = compute_table4_metrics(dtv_cases, get_prediction_dtv)
    print_table4("DtV (diagnostician ranking)", m_dtv_ranked)

    # DtV with primary-only (no ranking, for comparison)
    m_dtv_primary = compute_table4_metrics(dtv_cases, get_prediction_primary_only)
    print_table4("DtV (primary only, no ranking)", m_dtv_primary)

    # Reference baselines (if available)
    for label, path in [
        ("HiED-orig", "/home/user/YuNing/CultureDx/outputs/eval/calibrator_validation/results_lingxidiag.jsonl"),
        ("Single-baseline", "/home/user/YuNing/CultureDx/outputs/eval/rescore_gate_only_20260402_223720/single-baseline/results_lingxidiag.jsonl"),
    ]:
        try:
            cases = load_results(path)
            m = compute_table4_metrics(cases, get_prediction_primary_only)
            print_table4(f"{label} (n={len(cases)})", m)
        except FileNotFoundError:
            print(f"\n  {label}: file not found, skipping")

    # Veto stats
    dtv_count = sum(1 for c in dtv_cases if c.get("decision_trace", {}).get("dtv_mode"))
    veto_count = sum(1 for c in dtv_cases if c.get("decision_trace", {}).get("veto_applied"))
    print(f"\n  DtV mode: {dtv_count}/{len(dtv_cases)}")
    print(f"  Veto applied: {veto_count}/{len(dtv_cases)} ({veto_count/max(len(dtv_cases),1):.1%})")
