#!/usr/bin/env python3
"""
confusion_analysis.py
=====================
Per-mode confusion matrices and error taxonomy analysis for the CultureDx paper.

Uses parent-code matching (first 3 chars of ICD code).

Analyses:
  1. Confusion matrix (parent-code) — V10 HiED on LingxiDiag
  2. Confusion matrix (parent-code) — Baseline HiED on MDD-5k
  3. Error taxonomy — V10 HiED on LingxiDiag
  4. Error taxonomy — Baseline HiED on MDD-5k
  5. Detection ceiling analysis — both datasets, all modes
"""

import json
import os
from collections import Counter, defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE = Path("/home/user/YuNing/CultureDx/outputs/sweeps")

DATASETS = {
    "LingxiDiag_Baseline": {
        "dir": BASE / "lingxidiag_3mode_crossval_20260320_195057",
        "modes": ["hied_no_evidence", "psycot_no_evidence", "single_no_evidence"],
    },
    "LingxiDiag_V10": {
        "dir": BASE / "v10_lingxidiag_20260320_222603",
        "modes": ["hied_no_evidence", "psycot_no_evidence"],
    },
    "MDD5k_Baseline": {
        "dir": BASE / "n200_3mode_20260320_131920",
        "modes": ["hied_no_evidence", "psycot_no_evidence", "single_no_evidence"],
    },
}

# Canonical parent codes for confusion matrix rows/cols
LINGXI_CODES   = ["F32", "F41", "F42", "F43", "F51", "F98", "Others", "ABSTAIN"]
MDD5K_CODES    = ["F32", "F41", "F42", "F43", "F51", "F98", "Others", "ABSTAIN"]

# F33 maps to F32 parent group for prediction normalisation
F33_REMAP = {"F33": "F32"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parent(code: str | None) -> str:
    """Return first 3 characters of an ICD code, or ABSTAIN if None."""
    if code is None:
        return "ABSTAIN"
    return code[:3]


def normalise_pred(raw: str | None) -> str:
    """
    Return parent code for a predicted label.
    F33 -> F32; None -> ABSTAIN.
    """
    p = parent(raw)
    return F33_REMAP.get(p, p)


def load_cases(dataset_dir: Path) -> dict[str, str]:
    """
    Return {case_id: gold_parent_code}.
    Gold = first diagnosis in the case list (primary).
    """
    with open(dataset_dir / "case_list.json") as f:
        cl = json.load(f)
    result = {}
    for c in cl["cases"]:
        cid = c["case_id"]
        diags = c.get("diagnoses", [])
        gold = parent(diags[0]) if diags else "ABSTAIN"
        result[cid] = gold
    return result


def load_predictions(pred_path: Path) -> dict[str, dict]:
    """Return {case_id: prediction_record}."""
    with open(pred_path) as f:
        preds = json.load(f)
    return {p["case_id"]: p for p in preds["predictions"]}


def bucket(code: str, canonical: list[str]) -> str:
    """Map a parent code to the canonical label or 'Others'."""
    if code in canonical:
        return code
    return "Others"


# ---------------------------------------------------------------------------
# Confusion matrix
# ---------------------------------------------------------------------------

def build_confusion_matrix(
    gold_map: dict[str, str],
    pred_map: dict[str, dict],
    canonical: list[str],
) -> tuple[dict, int, int, int]:
    """
    Build confusion matrix: cm[gold_bucket][pred_bucket] = count.
    Also returns (n_correct, n_errors, n_abstain).
    """
    cm = defaultdict(Counter)
    n_correct = n_errors = n_abstain = 0

    for cid, gold_raw in gold_map.items():
        gold = bucket(gold_raw, canonical)

        pred_rec = pred_map.get(cid)
        if pred_rec is None:
            pred_raw = None
        else:
            pred_raw = pred_rec.get("primary_diagnosis")

        pred = normalise_pred(pred_raw)
        pred_b = bucket(pred, canonical)

        cm[gold][pred_b] += 1

        if pred_b == "ABSTAIN":
            n_abstain += 1
        elif gold == pred_b:
            n_correct += 1
        else:
            n_errors += 1

    return cm, n_correct, n_errors, n_abstain


def print_confusion_matrix(cm, canonical, title):
    # Determine which cols are actually used
    all_pred_codes = set()
    for pred_counts in cm.values():
        all_pred_codes.update(pred_counts.keys())
    cols = [c for c in canonical if c in all_pred_codes]
    # Add any extra cols not in canonical
    extra = sorted(all_pred_codes - set(canonical))
    cols = cols + extra

    # Determine rows present
    rows = [r for r in canonical if r in cm]

    col_w = max(max((len(c) for c in cols), default=4), 6)
    row_w = max(max((len(r) for r in rows), default=4), 9)

    header = f"\n{'=' * 60}\n{title}\n{'=' * 60}"
    print(header)

    # Header row
    hdr = f"{'Gold \\ Pred':<{row_w}}"
    for c in cols:
        hdr += f"  {c:>{col_w}}"
    hdr += f"  {'ROW_SUM':>{col_w}}"
    print(hdr)
    print("-" * len(hdr))

    for r in rows:
        row_counts = cm[r]
        row_sum = sum(row_counts.values())
        line = f"{r:<{row_w}}"
        for c in cols:
            v = row_counts.get(c, 0)
            line += f"  {v:>{col_w}}"
        line += f"  {row_sum:>{col_w}}"
        print(line)

    # Column totals
    print("-" * len(hdr))
    totals_line = f"{'COL_SUM':<{row_w}}"
    for c in cols:
        col_sum = sum(cm[r].get(c, 0) for r in rows)
        totals_line += f"  {col_sum:>{col_w}}"
    grand = sum(sum(cm[r].values()) for r in rows)
    totals_line += f"  {grand:>{col_w}}"
    print(totals_line)


# ---------------------------------------------------------------------------
# Per-class accuracy
# ---------------------------------------------------------------------------

def print_per_class_accuracy(cm, canonical):
    print("\nPer-class accuracy (correct / gold_total):")
    for r in canonical:
        if r not in cm:
            continue
        row_counts = cm[r]
        gold_total = sum(row_counts.values())
        correct = row_counts.get(r, 0)
        acc = correct / gold_total if gold_total > 0 else 0.0
        print(f"  {r:<8}  {correct:>3}/{gold_total:<3}  ({acc:.1%})")


# ---------------------------------------------------------------------------
# Error taxonomy
# ---------------------------------------------------------------------------

TAXONOMY_RULES = [
    ("F41→F32",           lambda g, p: g == "F41" and p in ("F32", "F33")),
    ("F32→F41",           lambda g, p: g == "F32" and p == "F41"),
    ("F32→Other",         lambda g, p: g == "F32" and p not in ("F32", "F41", "ABSTAIN")),
    ("F41→Other",         lambda g, p: g == "F41" and p not in ("F32", "F41", "ABSTAIN")),
    ("Other→F32",         lambda g, p: g not in ("F32", "F41") and p in ("F32", "F33")),
    ("Other→F41",         lambda g, p: g not in ("F32", "F41") and p == "F41"),
    ("Other→Other_wrong", lambda g, p: g not in ("F32", "F41") and
                                       p not in ("F32", "F33", "F41", "ABSTAIN") and g != p),
    ("Abstain",           lambda g, p: p == "ABSTAIN"),
]


def error_taxonomy(gold_map, pred_map):
    """
    Returns (tax_counts, total_errors, n_total) where tax_counts is {label: count}.
    """
    tax_counts = Counter()
    total_errors = 0
    n_total = len(gold_map)

    for cid, gold_raw in gold_map.items():
        gold_p = parent(gold_raw)
        pred_rec = pred_map.get(cid)
        pred_raw = None if pred_rec is None else pred_rec.get("primary_diagnosis")
        pred_p = normalise_pred(pred_raw)

        if pred_p == "ABSTAIN":
            tax_counts["Abstain"] += 1
            total_errors += 1
            continue

        if gold_p == pred_p:
            # Correct — not an error
            continue

        # Classify error
        matched = False
        for label, rule in TAXONOMY_RULES:
            if label == "Abstain":
                continue
            if rule(gold_p, pred_p):
                tax_counts[label] += 1
                matched = True
                break
        if not matched:
            tax_counts["Other_unclassified"] += 1
        total_errors += 1

    return tax_counts, total_errors, n_total


def print_error_taxonomy(tax_counts, total_errors, n_total, title):
    print(f"\n{'=' * 60}")
    print(f"Error Taxonomy: {title}")
    print(f"{'=' * 60}")
    print(f"Total cases: {n_total}  |  Total errors (incl. abstain): {total_errors}  |  Accuracy: {(n_total - total_errors) / n_total:.1%}")
    print()

    order = [r[0] for r in TAXONOMY_RULES] + ["Other_unclassified"]
    for label in order:
        cnt = tax_counts.get(label, 0)
        pct_of_errors = cnt / total_errors * 100 if total_errors > 0 else 0
        pct_of_total  = cnt / n_total  * 100 if n_total  > 0 else 0
        print(f"  {label:<25}  {cnt:>4}  ({pct_of_errors:5.1f}% of errors  /  {pct_of_total:5.1f}% of total)")


# ---------------------------------------------------------------------------
# Detection ceiling analysis
# ---------------------------------------------------------------------------

def detection_ceiling(gold_map, pred_map):
    """
    For each case, check whether ANY disorder in criteria_results has:
      - parent code matching gold parent code
      - criteria_met_count >= criteria_required

    Returns (n_detected, n_total, top1_correct, abstain_count).
    """
    n_detected = 0
    top1_correct = 0
    abstain_count = 0
    n_total = len(gold_map)

    for cid, gold_raw in gold_map.items():
        gold_p = parent(gold_raw)

        pred_rec = pred_map.get(cid)
        if pred_rec is None:
            continue

        # Top-1 accuracy
        pred_raw = pred_rec.get("primary_diagnosis")
        pred_p   = normalise_pred(pred_raw)
        if pred_p == "ABSTAIN":
            abstain_count += 1
        elif pred_p == gold_p:
            top1_correct += 1

        # Detection: any disorder in criteria_results that matches gold and meets threshold
        criteria_results = pred_rec.get("criteria_results", [])
        detected = False
        for cr in criteria_results:
            disorder_p = parent(cr.get("disorder", ""))
            if F33_REMAP.get(disorder_p, disorder_p) == gold_p:
                met   = cr.get("criteria_met_count", 0)
                req   = cr.get("criteria_required", 999)
                if met >= req:
                    detected = True
                    break
        if detected:
            n_detected += 1

    return n_detected, n_total, top1_correct, abstain_count


def print_detection_ceiling(results_by_mode, title):
    print(f"\n{'=' * 60}")
    print(f"Detection Ceiling Analysis: {title}")
    print(f"{'=' * 60}")
    print(f"{'Mode':<30}  {'Detected':>10}  {'Det%':>7}  {'Top-1':>7}  {'Top1%':>7}  {'Gap':>7}  {'Abstain':>8}")
    print("-" * 82)
    for mode, (n_det, n_tot, top1, n_abs) in results_by_mode.items():
        det_pct  = n_det  / n_tot * 100 if n_tot > 0 else 0
        top1_pct = top1   / n_tot * 100 if n_tot > 0 else 0
        gap      = det_pct - top1_pct
        print(f"  {mode:<28}  {n_det:>10}  {det_pct:>6.1f}%  {top1:>6}  {top1_pct:>6.1f}%  {gap:>+6.1f}%  {n_abs:>8}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # -----------------------------------------------------------------------
    # 1 & 2: Confusion matrices
    # -----------------------------------------------------------------------
    print("\n" + "#" * 70)
    print("# SECTION 1 & 2: CONFUSION MATRICES (Parent-Code)")
    print("#" * 70)

    # --- V10 LingxiDiag HiED ---
    v10_ld_dir   = DATASETS["LingxiDiag_V10"]["dir"]
    v10_gold_map = load_cases(v10_ld_dir)
    v10_pred_map = load_predictions(v10_ld_dir / "hied_no_evidence" / "predictions.json")

    cm_v10, n_corr_v10, n_err_v10, n_abs_v10 = build_confusion_matrix(
        v10_gold_map, v10_pred_map, LINGXI_CODES
    )
    print_confusion_matrix(
        cm_v10, LINGXI_CODES,
        "Confusion Matrix — V10 HiED on LingxiDiag (N=200)"
    )
    print(f"\n  Correct: {n_corr_v10}  |  Errors: {n_err_v10}  |  Abstains: {n_abs_v10}  |  Accuracy: {n_corr_v10/200:.1%}")
    print_per_class_accuracy(cm_v10, LINGXI_CODES)

    # --- Baseline MDD-5k HiED ---
    mdd_dir      = DATASETS["MDD5k_Baseline"]["dir"]
    mdd_gold_map = load_cases(mdd_dir)
    mdd_pred_map = load_predictions(mdd_dir / "hied_no_evidence" / "predictions.json")

    cm_mdd, n_corr_mdd, n_err_mdd, n_abs_mdd = build_confusion_matrix(
        mdd_gold_map, mdd_pred_map, MDD5K_CODES
    )
    print_confusion_matrix(
        cm_mdd, MDD5K_CODES,
        "Confusion Matrix — Baseline HiED on MDD-5k (N=200)"
    )
    print(f"\n  Correct: {n_corr_mdd}  |  Errors: {n_err_mdd}  |  Abstains: {n_abs_mdd}  |  Accuracy: {n_corr_mdd/200:.1%}")
    print_per_class_accuracy(cm_mdd, MDD5K_CODES)

    # -----------------------------------------------------------------------
    # 3 & 4: Error taxonomies
    # -----------------------------------------------------------------------
    print("\n" + "#" * 70)
    print("# SECTION 3 & 4: ERROR TAXONOMY")
    print("#" * 70)

    # V10 LingxiDiag HiED
    tax_v10, total_err_v10, n_tot_v10 = error_taxonomy(v10_gold_map, v10_pred_map)
    print_error_taxonomy(tax_v10, total_err_v10, n_tot_v10,
                         "V10 HiED on LingxiDiag")

    # Baseline MDD-5k HiED
    tax_mdd, total_err_mdd, n_tot_mdd = error_taxonomy(mdd_gold_map, mdd_pred_map)
    print_error_taxonomy(tax_mdd, total_err_mdd, n_tot_mdd,
                         "Baseline HiED on MDD-5k")

    # Side-by-side comparison table
    print(f"\n{'=' * 70}")
    print("Error Taxonomy Comparison (% of total errors)")
    print(f"{'=' * 70}")
    order = [r[0] for r in TAXONOMY_RULES] + ["Other_unclassified"]
    print(f"  {'Category':<25}  {'V10 LingxiDiag':>16}  {'Baseline MDD-5k':>16}")
    print("-" * 64)
    for label in order:
        c1 = tax_v10.get(label, 0)
        c2 = tax_mdd.get(label, 0)
        p1 = c1 / total_err_v10 * 100 if total_err_v10 > 0 else 0
        p2 = c2 / total_err_mdd * 100 if total_err_mdd > 0 else 0
        print(f"  {label:<25}  {c1:>4} ({p1:5.1f}%)     {c2:>4} ({p2:5.1f}%)")
    print(f"  {'TOTAL ERRORS':<25}  {total_err_v10:>4}              {total_err_mdd:>4}")

    # -----------------------------------------------------------------------
    # 5: Detection ceiling analysis
    # -----------------------------------------------------------------------
    print("\n" + "#" * 70)
    print("# SECTION 5: DETECTION CEILING ANALYSIS")
    print("#" * 70)

    # LingxiDiag — all available sweeps
    for ds_name, ds_cfg in DATASETS.items():
        ds_dir      = ds_cfg["dir"]
        gold_map    = load_cases(ds_dir)
        results_by_mode = {}
        for mode in ds_cfg["modes"]:
            pred_path = ds_dir / mode / "predictions.json"
            if not pred_path.exists():
                print(f"  [SKIP] {ds_name}/{mode} — predictions.json not found")
                continue
            pm = load_predictions(pred_path)
            n_det, n_tot, top1, n_abs = detection_ceiling(gold_map, pm)
            results_by_mode[mode] = (n_det, n_tot, top1, n_abs)
        print_detection_ceiling(results_by_mode, ds_name)

    # -----------------------------------------------------------------------
    # Bonus: Detection ceiling detail — V10 LingxiDiag HiED deep-dive
    # -----------------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("Detection Ceiling Deep-dive: V10 HiED on LingxiDiag")
    print(f"{'=' * 60}")
    print("\nCases where correct disorder detected but NOT ranked Top-1:")
    gap_cases = []
    for cid, gold_raw in v10_gold_map.items():
        gold_p = parent(gold_raw)
        pred_rec = v10_pred_map.get(cid)
        if pred_rec is None:
            continue
        pred_raw = pred_rec.get("primary_diagnosis")
        pred_p   = normalise_pred(pred_raw)

        # Detected?
        crs = pred_rec.get("criteria_results", [])
        detected = any(
            F33_REMAP.get(parent(cr.get("disorder", "")), parent(cr.get("disorder", ""))) == gold_p
            and cr.get("criteria_met_count", 0) >= cr.get("criteria_required", 999)
            for cr in crs
        )
        if detected and pred_p != gold_p:
            gap_cases.append((cid, gold_p, pred_p))

    print(f"  Count: {len(gap_cases)}")
    print(f"\n  {'case_id':<20}  {'Gold':>6}  {'Predicted':>10}")
    print("  " + "-" * 40)
    for cid, g, p in sorted(gap_cases):
        print(f"  {cid:<20}  {g:>6}  {p:>10}")

    # -----------------------------------------------------------------------
    # Summary table
    # -----------------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print("SUMMARY: Key Metrics")
    print(f"{'=' * 70}")
    print(f"  {'Dataset/Mode':<40}  {'Top-1 Acc':>10}  {'Det Rate':>10}  {'Gap':>6}")
    print("-" * 72)
    for ds_name, ds_cfg in DATASETS.items():
        ds_dir   = ds_cfg["dir"]
        gold_map = load_cases(ds_dir)
        for mode in ds_cfg["modes"]:
            pred_path = ds_dir / mode / "predictions.json"
            if not pred_path.exists():
                continue
            pm = load_predictions(pred_path)
            n_det, n_tot, top1, n_abs = detection_ceiling(gold_map, pm)
            det_pct  = n_det / n_tot * 100
            top1_pct = top1  / n_tot * 100
            gap      = det_pct - top1_pct
            label    = f"{ds_name} / {mode}"
            print(f"  {label:<40}  {top1_pct:>9.1f}%  {det_pct:>9.1f}%  {gap:>+5.1f}%")


if __name__ == "__main__":
    main()
