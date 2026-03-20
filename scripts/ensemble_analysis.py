"""
Ensemble strategy analysis for LingxiDiag diagnostic modes.

Compares 7 ensemble strategies across V10 HiED, V10 PsyCoT, and Baseline Single
predictions to find combinations that exceed V10 HiED's 41.5% Top-1 accuracy.

Parent-code matching: first 3 characters of ICD code (F32.x -> F32, F41.x -> F41, etc.)
"""

import json
import os
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = "/home/user/YuNing/CultureDx"
HIED_PATH    = f"{BASE}/outputs/sweeps/v10_lingxidiag_20260320_222603/hied_no_evidence/predictions.json"
PSYCOT_PATH  = f"{BASE}/outputs/sweeps/v10_lingxidiag_20260320_222603/psycot_no_evidence/predictions.json"
SINGLE_PATH  = f"{BASE}/outputs/sweeps/lingxidiag_3mode_crossval_20260320_195057/single_no_evidence/predictions.json"
CASES_PATH   = f"{BASE}/outputs/sweeps/v10_lingxidiag_20260320_222603/case_list.json"


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def load_predictions(path: str) -> Dict[str, dict]:
    """Load predictions keyed by case_id."""
    with open(path) as f:
        data = json.load(f)
    preds = data["predictions"]
    return {p["case_id"]: p for p in preds}


def load_ground_truth(path: str) -> Dict[str, str]:
    """Load ground truth labels keyed by case_id."""
    with open(path) as f:
        data = json.load(f)
    return {c["case_id"]: c["diagnoses"][0] for c in data["cases"]}


def parent_code(code: Optional[str]) -> Optional[str]:
    """Return first 3 characters of an ICD code, or None for abstains."""
    if code is None:
        return None
    return code[:3]


def get_pred_info(pred: Optional[dict]) -> Tuple[Optional[str], float]:
    """Return (parent_code, confidence) for a prediction record."""
    if pred is None:
        return None, 0.0
    if pred.get("decision") == "abstain" or pred.get("primary_diagnosis") is None:
        return None, 0.0
    return parent_code(pred["primary_diagnosis"]), pred.get("confidence", 0.0)


# ---------------------------------------------------------------------------
# Ensemble strategy implementations
# ---------------------------------------------------------------------------

def strategy_majority_vote(hied: dict, psycot: dict, single: dict) -> Optional[str]:
    """
    If 2+ modes agree on parent code, use that.
    If all 3 disagree, use the mode with highest confidence.
    """
    ph, ch = get_pred_info(hied)
    pp, cp = get_pred_info(psycot)
    ps, cs = get_pred_info(single)

    votes = [ph, pp, ps]
    # Count non-None votes
    non_none = [(v, c) for v, c in zip([ph, pp, ps], [ch, cp, cs]) if v is not None]

    if not non_none:
        return None

    vote_counts = Counter(v for v, _ in non_none)
    # Majority: any code with 2+ votes
    for code, count in vote_counts.most_common():
        if count >= 2:
            return code

    # All 3 disagree (or only 1 non-None): use highest confidence
    best_code, _ = max(non_none, key=lambda x: x[1])
    return best_code


def strategy_agreement_based(hied: dict, psycot: dict, single: dict) -> Optional[str]:
    """
    When HiED and PsyCoT agree -> use their answer.
    When they disagree -> fall back to Single.
    """
    ph, ch = get_pred_info(hied)
    pp, cp = get_pred_info(psycot)
    ps, cs = get_pred_info(single)

    if ph is not None and pp is not None and ph == pp:
        return ph
    # They disagree or one abstained -> use Single
    return ps


def strategy_confidence_weighted(hied: dict, psycot: dict, single: dict) -> Optional[str]:
    """
    Use the prediction with the highest confidence across all 3 modes.
    """
    ph, ch = get_pred_info(hied)
    pp, cp = get_pred_info(psycot)
    ps, cs = get_pred_info(single)

    candidates = [(code, conf) for code, conf in [(ph, ch), (pp, cp), (ps, cs)] if code is not None]
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[1])[0]


def strategy_hied_primary(hied: dict, psycot: dict, single: dict) -> Optional[str]:
    """
    Use HiED; if HiED abstains, fall back to Single.
    """
    ph, ch = get_pred_info(hied)
    ps, cs = get_pred_info(single)

    if ph is not None:
        return ph
    return ps


def strategy_conditional(hied: dict, psycot: dict, single: dict) -> Optional[str]:
    """
    If HiED confidence > 0.85, use HiED.
    Elif PsyCoT confidence > 0.85, use PsyCoT.
    Otherwise use Single.
    """
    ph, ch = get_pred_info(hied)
    pp, cp = get_pred_info(psycot)
    ps, cs = get_pred_info(single)

    if ph is not None and ch > 0.85:
        return ph
    if pp is not None and cp > 0.85:
        return pp
    return ps


def strategy_anti_correlation(hied: dict, psycot: dict, single: dict) -> Optional[str]:
    """
    For each case: if HiED and PsyCoT disagree AND one is F32 while the other is F41,
    use PsyCoT (which checks all criteria exhaustively).
    Otherwise use HiED (falling back to Single if abstain).
    """
    ph, ch = get_pred_info(hied)
    pp, cp = get_pred_info(psycot)
    ps, cs = get_pred_info(single)

    f32_f41_pair = {ph, pp} == {"F32", "F41"} if (ph and pp) else False

    if f32_f41_pair:
        # Prefer PsyCoT when the ambiguity is specifically F32 vs F41
        return pp

    # Default: HiED primary, Single fallback
    if ph is not None:
        return ph
    return ps


def strategy_oracle(hied: dict, psycot: dict, single: dict, gt: str) -> Optional[str]:
    """
    Upper-bound oracle: correct if ANY mode is correct.
    Returns the ground-truth parent code if any mode gets it right,
    else returns the HiED prediction (arbitrary loser choice).
    """
    ph, _ = get_pred_info(hied)
    pp, _ = get_pred_info(psycot)
    ps, _ = get_pred_info(single)
    gt_p = parent_code(gt)

    for pred in [ph, pp, ps]:
        if pred == gt_p:
            return pred
    # None correct — return HiED or Single
    return ph if ph is not None else ps


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def evaluate_predictions(
    case_ids: List[str],
    ensemble_preds: Dict[str, Optional[str]],
    ground_truth: Dict[str, str],
    strategy_name: str,
    individual_preds: Dict[str, Dict[str, Optional[str]]],
) -> dict:
    """
    Compute metrics for a set of ensemble predictions.

    Returns a dict with:
      - top1_acc: Top-1 accuracy (parent-code match)
      - f41_recall: recall for F41 ground-truth cases
      - f32_recall: recall for F32 ground-truth cases
      - f41_to_f32_rate: among predicted F32, fraction where GT is F41
      - n_differ_from_best: cases where ensemble differs from the best individual
      - n_total: total cases
    """
    n_total = len(case_ids)
    n_correct = 0
    n_f41_gt = 0
    n_f41_correct = 0
    n_f32_gt = 0
    n_f32_correct = 0
    n_pred_f32 = 0
    n_pred_f32_but_gt_f41 = 0
    n_differ_from_best = 0

    for cid in case_ids:
        gt = ground_truth[cid]
        gt_p = parent_code(gt)
        pred = ensemble_preds[cid]

        # Top-1 correctness
        if pred == gt_p:
            n_correct += 1

        # F41 recall
        if gt_p == "F41":
            n_f41_gt += 1
            if pred == "F41":
                n_f41_correct += 1

        # F32 recall
        if gt_p == "F32":
            n_f32_gt += 1
            if pred == "F32":
                n_f32_correct += 1

        # F41->F32 confusion
        if pred == "F32":
            n_pred_f32 += 1
            if gt_p == "F41":
                n_pred_f32_but_gt_f41 += 1

        # Differs from best individual
        # "Best individual" = whichever individual was correct; if none correct,
        # compare against HiED (primary mode)
        any_individual_correct = any(
            individual_preds[mode].get(cid) == gt_p
            for mode in individual_preds
        )
        # Ensemble differs from best = ensemble is wrong but someone was right,
        # OR ensemble is right but everyone else was wrong (improvement)
        best_ind_pred = None
        for mode in ["hied", "psycot", "single"]:
            if individual_preds[mode].get(cid) == gt_p:
                best_ind_pred = gt_p
                break
        if best_ind_pred is None:
            # No individual was right; use HiED as reference
            best_ind_pred = individual_preds["hied"].get(cid)

        if pred != best_ind_pred:
            n_differ_from_best += 1

    top1 = n_correct / n_total if n_total else 0.0
    f41_recall = n_f41_correct / n_f41_gt if n_f41_gt else 0.0
    f32_recall = n_f32_correct / n_f32_gt if n_f32_gt else 0.0
    f41_to_f32_rate = n_pred_f32_but_gt_f41 / n_pred_f32 if n_pred_f32 else 0.0

    return {
        "strategy": strategy_name,
        "top1_acc": top1,
        "n_correct": n_correct,
        "f41_recall": f41_recall,
        "f41_correct": n_f41_correct,
        "f41_gt": n_f41_gt,
        "f32_recall": f32_recall,
        "f32_correct": n_f32_correct,
        "f32_gt": n_f32_gt,
        "f41_to_f32_rate": f41_to_f32_rate,
        "n_pred_f32_but_gt_f41": n_pred_f32_but_gt_f41,
        "n_pred_f32": n_pred_f32,
        "n_differ_from_best": n_differ_from_best,
        "n_total": n_total,
    }


def print_metrics(m: dict) -> None:
    """Pretty-print a metrics dict."""
    delta = m["top1_acc"] - 0.415  # vs V10 HiED baseline
    delta_str = f"  ({delta:+.1%} vs HiED baseline)" if m["strategy"] != "Individual: HiED" else ""
    print(f"\n  Strategy          : {m['strategy']}")
    print(f"  Top-1 Accuracy    : {m['top1_acc']:.1%}  ({m['n_correct']}/{m['n_total']}){delta_str}")
    print(f"  F41 Recall        : {m['f41_recall']:.1%}  ({m['f41_correct']}/{m['f41_gt']} GT-F41 cases)")
    print(f"  F32 Recall        : {m['f32_recall']:.1%}  ({m['f32_correct']}/{m['f32_gt']} GT-F32 cases)")
    print(f"  F41->F32 confusion: {m['f41_to_f32_rate']:.1%}  "
          f"({m['n_pred_f32_but_gt_f41']} of {m['n_pred_f32']} predicted F32 are actually F41)")
    print(f"  Differs from best : {m['n_differ_from_best']} cases")


# ---------------------------------------------------------------------------
# Per-case disagreement analysis
# ---------------------------------------------------------------------------

def disagreement_analysis(
    case_ids: List[str],
    hied_map: Dict[str, dict],
    psycot_map: Dict[str, dict],
    single_map: Dict[str, dict],
    ground_truth: Dict[str, str],
    ensemble_results: Dict[str, Dict[str, Optional[str]]],
) -> None:
    """Print breakdown of cases where modes disagree and show ensemble outcomes."""
    print("\n" + "=" * 70)
    print("DISAGREEMENT ANALYSIS")
    print("=" * 70)

    total_3way_disagree = 0
    total_hied_psycot_disagree = 0
    total_f32_f41_ambiguous = 0

    for cid in case_ids:
        ph, _ = get_pred_info(hied_map.get(cid))
        pp, _ = get_pred_info(psycot_map.get(cid))
        ps, _ = get_pred_info(single_map.get(cid))

        if ph != pp:
            total_hied_psycot_disagree += 1
        if len({ph, pp, ps}) == 3:
            total_3way_disagree += 1
        if {ph, pp} == {"F32", "F41"}:
            total_f32_f41_ambiguous += 1

    print(f"  HiED vs PsyCoT disagreements  : {total_hied_psycot_disagree}/200")
    print(f"  3-way full disagreements       : {total_3way_disagree}/200")
    print(f"  F32 vs F41 ambiguous (H vs P)  : {total_f32_f41_ambiguous}/200")

    # Among F32/F41 ambiguous cases, show which strategy wins
    print(f"\n  F32-F41 ambiguous case outcomes (HiED vs PsyCoT disagree on F32/F41):")
    print(f"  {'case_id':>12}  {'GT':>5}  {'HiED':>5}  {'PsyCoT':>6}  {'Single':>6}  ", end="")
    for s in ["majority", "agreement", "conf_weighted", "anti_corr"]:
        print(f"  {s[:9]:>9}", end="")
    print()

    n_shown = 0
    for cid in case_ids:
        ph, _ = get_pred_info(hied_map.get(cid))
        pp, _ = get_pred_info(psycot_map.get(cid))
        ps, _ = get_pred_info(single_map.get(cid))

        if {ph, pp} == {"F32", "F41"}:
            gt_p = parent_code(ground_truth[cid])
            row = f"  {cid:>12}  {gt_p:>5}  {ph or 'None':>5}  {pp or 'None':>6}  {ps or 'None':>6}  "
            for s in ["majority", "agreement", "conf_weighted", "anti_corr"]:
                v = ensemble_results[s].get(cid, "?")
                mark = "*" if v == gt_p else " "
                row += f"  {(v or 'None'):>8}{mark}"
            print(row)
            n_shown += 1

    print(f"\n  (shown {n_shown} F32/F41 ambiguous cases; * = correct)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("ENSEMBLE STRATEGY ANALYSIS — LingxiDiag (N=200)")
    print("Baseline: V10 HiED Top-1 = 41.5%")
    print("=" * 70)

    # Load data
    hied_map   = load_predictions(HIED_PATH)
    psycot_map = load_predictions(PSYCOT_PATH)
    single_map = load_predictions(SINGLE_PATH)
    ground_truth = load_ground_truth(CASES_PATH)

    case_ids = list(ground_truth.keys())
    n = len(case_ids)

    print(f"\nLoaded {n} cases")
    print(f"  HiED predictions  : {len(hied_map)}")
    print(f"  PsyCoT predictions: {len(psycot_map)}")
    print(f"  Single predictions: {len(single_map)}")

    # Verify all case IDs are present
    missing_hied = [c for c in case_ids if c not in hied_map]
    missing_psycot = [c for c in case_ids if c not in psycot_map]
    missing_single = [c for c in case_ids if c not in single_map]
    if missing_hied or missing_psycot or missing_single:
        print(f"WARNING: missing cases — HiED:{len(missing_hied)}, "
              f"PsyCoT:{len(missing_psycot)}, Single:{len(missing_single)}")

    # Ground-truth parent distribution
    gt_dist = Counter(parent_code(v) for v in ground_truth.values())
    print(f"\nGround-truth parent-code distribution:")
    for code, cnt in sorted(gt_dist.items(), key=lambda x: -x[1]):
        print(f"  {code}: {cnt}")

    # Build individual parent-code prediction maps
    individual_preds: Dict[str, Dict[str, Optional[str]]] = {
        "hied":   {cid: get_pred_info(hied_map.get(cid))[0] for cid in case_ids},
        "psycot": {cid: get_pred_info(psycot_map.get(cid))[0] for cid in case_ids},
        "single": {cid: get_pred_info(single_map.get(cid))[0] for cid in case_ids},
    }

    # ---------------------------------------------------------------------------
    # Run all strategies
    # ---------------------------------------------------------------------------
    strategy_funcs = {
        "majority":       lambda h, p, s: strategy_majority_vote(h, p, s),
        "agreement":      lambda h, p, s: strategy_agreement_based(h, p, s),
        "conf_weighted":  lambda h, p, s: strategy_confidence_weighted(h, p, s),
        "hied_primary":   lambda h, p, s: strategy_hied_primary(h, p, s),
        "conditional":    lambda h, p, s: strategy_conditional(h, p, s),
        "anti_corr":      lambda h, p, s: strategy_anti_correlation(h, p, s),
    }

    # Build ensemble prediction maps
    ensemble_results: Dict[str, Dict[str, Optional[str]]] = {}
    for name, fn in strategy_funcs.items():
        preds_map = {}
        for cid in case_ids:
            preds_map[cid] = fn(
                hied_map.get(cid),
                psycot_map.get(cid),
                single_map.get(cid),
            )
        ensemble_results[name] = preds_map

    # Oracle
    oracle_map = {}
    for cid in case_ids:
        oracle_map[cid] = strategy_oracle(
            hied_map.get(cid),
            psycot_map.get(cid),
            single_map.get(cid),
            ground_truth[cid],
        )
    ensemble_results["oracle"] = oracle_map

    # ---------------------------------------------------------------------------
    # Individual baselines
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("INDIVIDUAL MODE BASELINES")
    print("=" * 70)

    individual_display = [
        ("Individual: HiED",   individual_preds["hied"]),
        ("Individual: PsyCoT", individual_preds["psycot"]),
        ("Individual: Single", individual_preds["single"]),
    ]
    all_metrics = []
    for display_name, pred_map in individual_display:
        m = evaluate_predictions(
            case_ids, pred_map, ground_truth, display_name, individual_preds
        )
        print_metrics(m)
        all_metrics.append(m)

    # ---------------------------------------------------------------------------
    # Ensemble strategies
    # ---------------------------------------------------------------------------
    strategy_display_names = {
        "majority":      "1. Majority Vote",
        "agreement":     "2. Agreement-Based (HiED+PsyCoT agree -> use them, else Single)",
        "conf_weighted": "3. Confidence-Weighted (max confidence wins)",
        "hied_primary":  "4. HiED-Primary (HiED; fallback Single on abstain)",
        "conditional":   "5. Conditional (HiED>0.85 -> HiED; PsyCoT>0.85 -> PsyCoT; else Single)",
        "anti_corr":     "6. Anti-Correlation (F32/F41 disagreement -> prefer PsyCoT)",
        "oracle":        "7. Oracle (upper bound — any mode correct = correct)",
    }

    print("\n" + "=" * 70)
    print("ENSEMBLE STRATEGIES")
    print("=" * 70)

    for key, display_name in strategy_display_names.items():
        m = evaluate_predictions(
            case_ids,
            ensemble_results[key],
            ground_truth,
            display_name,
            individual_preds,
        )
        print_metrics(m)
        all_metrics.append(m)

    # ---------------------------------------------------------------------------
    # Summary table
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("SUMMARY TABLE (sorted by Top-1 Accuracy)")
    print("=" * 70)
    print(f"\n{'Strategy':<52} {'Top-1':>6}  {'F41 Rec':>7}  {'F32 Rec':>7}  {'F41>F32':>7}  {'Diff':>5}")
    print("-" * 90)

    for m in sorted(all_metrics, key=lambda x: -x["top1_acc"]):
        name = m["strategy"]
        delta = m["top1_acc"] - 0.415
        delta_mark = "+" if delta > 0.001 else (" " if abs(delta) <= 0.001 else "-")
        print(
            f"  {name:<50} {m['top1_acc']:>5.1%}  "
            f"{m['f41_recall']:>6.1%}  "
            f"{m['f32_recall']:>6.1%}  "
            f"{m['f41_to_f32_rate']:>6.1%}  "
            f"{m['n_differ_from_best']:>4}"
        )

    # ---------------------------------------------------------------------------
    # Key insight: cases where ensemble improves over ALL individuals
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("IMPROVEMENT ANALYSIS: Cases where ensemble beats all 3 individuals")
    print("=" * 70)

    for key, display_name in strategy_display_names.items():
        if key == "oracle":
            continue
        gains = []
        losses = []
        for cid in case_ids:
            gt_p = parent_code(ground_truth[cid])
            ens_pred = ensemble_results[key][cid]
            ind_correct = any(individual_preds[m][cid] == gt_p for m in individual_preds)
            ind_any = individual_preds["hied"][cid] or individual_preds["single"][cid]

            if ens_pred == gt_p and not ind_correct:
                gains.append(cid)
            if ens_pred != gt_p and ind_correct:
                losses.append(cid)

        short = display_name.split("(")[0].strip()
        print(f"\n  {short}")
        print(f"    Gains (ensemble correct, all individuals wrong): {len(gains)}")
        print(f"    Losses (ensemble wrong, at least one individual correct): {len(losses)}")
        print(f"    Net cases changed: {len(gains) - len(losses):+d}")

    # ---------------------------------------------------------------------------
    # Disagreement / ambiguity analysis
    # ---------------------------------------------------------------------------
    disagreement_analysis(
        case_ids, hied_map, psycot_map, single_map,
        ground_truth, ensemble_results
    )

    # ---------------------------------------------------------------------------
    # Deep dive: F41 cases where HiED fails but PsyCoT/Single succeed
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("F41 CASE DEEP DIVE")
    print("=" * 70)

    f41_cases = [cid for cid in case_ids if parent_code(ground_truth[cid]) == "F41"]
    print(f"\n  Total F41 GT cases: {len(f41_cases)}")
    print(f"\n  {'case_id':>12}  {'GT':>5}  {'HiED':>5}  {'PsyCoT':>6}  {'Single':>6}  "
          f"{'Majority':>8}  {'Agree':>6}  {'AntiC':>6}  {'Oracle':>7}")
    n_hied_right = n_psycot_right = n_single_right = 0
    n_hied_wrong_psycot_right = 0
    for cid in sorted(f41_cases):
        gt_p = parent_code(ground_truth[cid])
        ph, _ = get_pred_info(hied_map.get(cid))
        pp, _ = get_pred_info(psycot_map.get(cid))
        ps, _ = get_pred_info(single_map.get(cid))

        if ph == gt_p: n_hied_right += 1
        if pp == gt_p: n_psycot_right += 1
        if ps == gt_p: n_single_right += 1
        if ph != gt_p and pp == gt_p: n_hied_wrong_psycot_right += 1

        maj  = ensemble_results["majority"][cid]
        agr  = ensemble_results["agreement"][cid]
        anti = ensemble_results["anti_corr"][cid]
        orc  = ensemble_results["oracle"][cid]

        # Markers
        def m(v): return f"{v or '---':>5}{'*' if v == gt_p else ' '}"
        print(f"  {cid:>12}  {gt_p:>5}  {m(ph)}  {m(pp)}  {m(ps)}  "
              f"{m(maj)}  {m(agr)}  {m(anti)}  {m(orc)}")

    print(f"\n  F41 correct counts: HiED={n_hied_right}, PsyCoT={n_psycot_right}, Single={n_single_right}")
    print(f"  Cases where HiED wrong but PsyCoT right: {n_hied_wrong_psycot_right}")

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
