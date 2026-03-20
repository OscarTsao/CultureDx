#!/usr/bin/env python3
"""V11-on-V10 Simulation: replay V10 HiED checker outputs through V11 logic + calibrator.

No new LLM calls. Tests whether V11 calibrator/logic engine changes help
ON TOP of V10's already-improved checker outputs (B1/B2 criterion detection).

Also tests a second variant: "anxiety-specificity guard" -- for F41.1,
require at least 1 anxiety-specific criterion (A, B1, or B2) to be MET
for confirmation. This would filter false positives that only meet shared
criteria (B3/B4).
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from culturedx.core.models import CheckerOutput, CriterionResult
from culturedx.diagnosis.calibrator import ConfidenceCalibrator
from culturedx.diagnosis.comorbidity import ComorbidityResolver
from culturedx.diagnosis.logic_engine import DiagnosticLogicEngine
from culturedx.ontology.icd10 import get_disorder_criteria, get_disorder_threshold

# --- Paths ---
V10_DIR = ROOT / "outputs" / "sweeps" / "v10_lingxidiag_20260320_222603"
PRED_PATH = V10_DIR / "hied_no_evidence" / "predictions.json"
CASE_PATH = V10_DIR / "case_list.json"


def parent_code(code: str | None) -> str:
    """F32.1 -> F32, None/ABSTAIN -> ''."""
    if not code or code in ("None", "ABSTAIN"):
        return ""
    return code.split(".")[0]


def load_data():
    with open(PRED_PATH, encoding="utf-8") as f:
        pred_data = json.load(f)
    with open(CASE_PATH, encoding="utf-8") as f:
        case_data = json.load(f)
    gold_map = {str(c["case_id"]): c["diagnoses"] for c in case_data["cases"]}
    return pred_data["predictions"], gold_map


def criteria_to_checker_output(disorder: str, criteria_list: list[dict]) -> CheckerOutput:
    """Convert raw criteria dict from predictions.json to CheckerOutput model."""
    results = []
    met_count = 0
    for cr in criteria_list:
        status = cr["status"]
        if status == "met":
            met_count += 1
        results.append(CriterionResult(
            criterion_id=cr["criterion_id"],
            status=status,
            evidence=cr.get("evidence"),
            confidence=cr.get("confidence", 0.5),
        ))

    # Compute required from ontology
    threshold = get_disorder_threshold(disorder)
    if "min_total" in threshold:
        required = threshold["min_total"]
    elif "min_symptoms" in threshold:
        required = threshold["min_symptoms"]
    elif threshold.get("all_required"):
        criteria_def = get_disorder_criteria(disorder)
        required = len(criteria_def) if criteria_def else met_count
    else:
        required = met_count  # fallback

    return CheckerOutput(
        disorder=disorder,
        criteria=results,
        criteria_met_count=met_count,
        criteria_required=required,
    )


def rebuild_checker_outputs(pred: dict) -> list[CheckerOutput]:
    """Rebuild CheckerOutput list from a prediction's criteria_results."""
    outputs = []
    for cr_result in pred.get("criteria_results", []):
        co = criteria_to_checker_output(cr_result["disorder"], cr_result["criteria"])
        outputs.append(co)
    return outputs


def run_v10_baseline(predictions: list[dict], gold_map: dict) -> list[dict]:
    """Extract original V10 predictions as baseline."""
    results = []
    for pred in predictions:
        case_id = str(pred["case_id"])
        golds = gold_map.get(case_id, [])
        gold_parents = {parent_code(g) for g in golds}
        bl_pred = parent_code(pred.get("primary_diagnosis"))
        bl_correct = bl_pred in gold_parents if bl_pred else False
        results.append({
            "case_id": case_id,
            "gold": golds[0] if golds else "",
            "gold_parent": parent_code(golds[0]) if golds else "",
            "pred": bl_pred,
            "pred_raw": pred.get("primary_diagnosis", ""),
            "correct": bl_correct,
            "comorbids": [parent_code(c) for c in pred.get("comorbid_diagnoses", [])],
        })
    return results


def run_v11_simulation(
    predictions: list[dict],
    gold_map: dict,
    anxiety_guard: bool = False,
) -> list[dict]:
    """Replay V10 checker outputs through V11 logic engine + calibrator.

    If anxiety_guard=True, additionally require at least one anxiety-specific
    criterion (A, B1, or B2) for F41.1 confirmation.
    """
    engine = DiagnosticLogicEngine()
    calibrator = ConfidenceCalibrator(version=2)
    comorbidity = ComorbidityResolver()

    results = []
    for pred in predictions:
        case_id = str(pred["case_id"])
        golds = gold_map.get(case_id, [])
        gold_parents = {parent_code(g) for g in golds}

        checker_outputs = rebuild_checker_outputs(pred)
        if not checker_outputs:
            results.append({
                "case_id": case_id,
                "gold": golds[0] if golds else "",
                "gold_parent": parent_code(golds[0]) if golds else "",
                "pred": "",
                "pred_raw": "",
                "correct": False,
                "confidence": 0.0,
                "confirmed_codes": [],
                "comorbids": [],
            })
            continue

        # 1. Logic engine
        logic_output = engine.evaluate(checker_outputs)

        # 1b. Anxiety-specificity guard
        if anxiety_guard:
            filtered_confirmed = []
            for r in logic_output.confirmed:
                if r.disorder_code == "F41.1":
                    # Check if any anxiety-specific criterion is met
                    co = next(
                        (c for c in checker_outputs if c.disorder == "F41.1"), None
                    )
                    if co:
                        anxiety_specific = {"A", "B1", "B2"}
                        met_ids = {
                            cr.criterion_id for cr in co.criteria
                            if cr.status == "met"
                        }
                        if not (met_ids & anxiety_specific):
                            # No anxiety-specific criterion met -> reject
                            logic_output.rejected.append(r)
                            continue
                filtered_confirmed.append(r)
            logic_output.confirmed = filtered_confirmed

        # 2. Calibrator
        confirmation_types = {
            r.disorder_code: r.confirmation_type
            for r in logic_output.confirmed
        }
        cal_output = calibrator.calibrate(
            confirmed_disorders=logic_output.confirmed_codes,
            checker_outputs=checker_outputs,
            confirmation_types=confirmation_types,
        )

        # 3. Comorbidity resolution
        all_confirmed = []
        all_confs = {}
        if cal_output.primary:
            all_confirmed.append(cal_output.primary.disorder_code)
            all_confs[cal_output.primary.disorder_code] = cal_output.primary.confidence
        for c in cal_output.comorbid:
            all_confirmed.append(c.disorder_code)
            all_confs[c.disorder_code] = c.confidence

        if all_confirmed:
            comorb_result = comorbidity.resolve(all_confirmed, all_confs)
            final_primary = parent_code(comorb_result.primary)
            final_comorbids = [parent_code(c) for c in comorb_result.comorbid]
        elif cal_output.primary:
            final_primary = parent_code(cal_output.primary.disorder_code)
            final_comorbids = []
        else:
            final_primary = ""
            final_comorbids = []

        conf = cal_output.primary.confidence if cal_output.primary else 0.0
        sim_correct = final_primary in gold_parents if final_primary else False

        results.append({
            "case_id": case_id,
            "gold": golds[0] if golds else "",
            "gold_parent": parent_code(golds[0]) if golds else "",
            "pred": final_primary,
            "pred_raw": cal_output.primary.disorder_code if cal_output.primary else "",
            "correct": sim_correct,
            "confidence": conf,
            "confirmed_codes": logic_output.confirmed_codes,
            "comorbids": final_comorbids,
        })

    return results


def compute_class_metrics(results: list[dict], classes: list[str]) -> dict:
    """Compute per-class precision, recall, F1."""
    metrics = {}
    for cls in classes:
        tp = sum(1 for r in results if r["pred"] == cls and r["gold_parent"] == cls)
        fp = sum(1 for r in results if r["pred"] == cls and r["gold_parent"] != cls)
        fn = sum(1 for r in results if r["pred"] != cls and r["gold_parent"] == cls)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * recall / (prec + recall) if (prec + recall) > 0 else 0.0
        metrics[cls] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": prec, "recall": recall, "f1": f1,
            "support": tp + fn,
        }
    return metrics


def print_confusion_pair(results: list[dict], pred_cls: str, gold_cls: str) -> int:
    """Count cases where gold=gold_cls but pred=pred_cls."""
    cases = [r for r in results if r["gold_parent"] == gold_cls and r["pred"] == pred_cls]
    return len(cases)


def compare_results(
    baseline: list[dict],
    sim: list[dict],
    label: str,
    n: int,
):
    """Compare baseline vs simulation results and print report."""
    bl_acc = sum(r["correct"] for r in baseline) / n
    sim_acc = sum(r["correct"] for r in sim) / n

    # Transition analysis
    gains = losses = stayed_correct = stayed_wrong = 0
    gain_details = []
    loss_details = []

    for bl, s in zip(baseline, sim):
        if bl["correct"] and s["correct"]:
            stayed_correct += 1
        elif not bl["correct"] and not s["correct"]:
            stayed_wrong += 1
        elif not bl["correct"] and s["correct"]:
            gains += 1
            gain_details.append((bl, s))
        else:
            losses += 1
            loss_details.append((bl, s))

    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    print(f"\n  Overall accuracy (Top-1, parent-code matching):")
    print(f"    V10 baseline:  {bl_acc:.1%} ({sum(r['correct'] for r in baseline)}/{n})")
    print(f"    Simulated:     {sim_acc:.1%} ({sum(r['correct'] for r in sim)}/{n})")
    print(f"    Delta:         {(sim_acc-bl_acc)*100:+.1f}pp")

    print(f"\n  Transition matrix:")
    print(f"    Stayed correct:  {stayed_correct}")
    print(f"    Stayed wrong:    {stayed_wrong}")
    print(f"    Gains (+):       {gains}")
    print(f"    Losses (-):      {losses}")
    print(f"    Net:             {gains-losses:+d}")

    # Per-class recall
    classes = sorted(set(r["gold_parent"] for r in baseline if r["gold_parent"]))
    bl_metrics = compute_class_metrics(baseline, classes)
    sim_metrics = compute_class_metrics(sim, classes)

    print(f"\n  Per-class recall changes:")
    print(f"    {'Class':<10} {'V10':>12} {'Sim':>12} {'Delta':>8}")
    print(f"    {'-'*10} {'-'*12} {'-'*12} {'-'*8}")
    for cls in classes:
        bl_m = bl_metrics.get(cls, {})
        sm_m = sim_metrics.get(cls, {})
        bl_r = bl_m.get("recall", 0.0)
        sm_r = sm_m.get("recall", 0.0)
        bl_sup = bl_m.get("support", 0)
        sm_sup = sm_m.get("support", 0)
        delta = (sm_r - bl_r) * 100
        print(f"    {cls:<10} {bl_m.get('tp',0):>3}/{bl_sup:<3} ({bl_r:.1%}) "
              f"{sm_m.get('tp',0):>3}/{sm_sup:<3} ({sm_r:.1%}) {delta:>+6.1f}pp")

    # Per-class precision
    print(f"\n  Per-class precision changes:")
    print(f"    {'Class':<10} {'V10':>12} {'Sim':>12} {'Delta':>8}")
    print(f"    {'-'*10} {'-'*12} {'-'*12} {'-'*8}")
    for cls in classes:
        bl_m = bl_metrics.get(cls, {})
        sm_m = sim_metrics.get(cls, {})
        bl_p = bl_m.get("precision", 0.0)
        sm_p = sm_m.get("precision", 0.0)
        bl_tp = bl_m.get("tp", 0)
        bl_fp = bl_m.get("fp", 0)
        sm_tp = sm_m.get("tp", 0)
        sm_fp = sm_m.get("fp", 0)
        delta = (sm_p - bl_p) * 100
        print(f"    {cls:<10} {bl_tp:>3}/{bl_tp+bl_fp:<3} ({bl_p:.1%}) "
              f"{sm_tp:>3}/{sm_tp+sm_fp:<3} ({sm_p:.1%}) {delta:>+6.1f}pp")

    # F41<->F32 confusion rate
    bl_f41_as_f32 = print_confusion_pair(baseline, "F32", "F41")
    sim_f41_as_f32 = print_confusion_pair(sim, "F32", "F41")
    bl_f32_as_f41 = print_confusion_pair(baseline, "F41", "F32")
    sim_f32_as_f41 = print_confusion_pair(sim, "F41", "F32")
    f41_total = sum(1 for r in baseline if r["gold_parent"] == "F41")
    f32_total = sum(1 for r in baseline if r["gold_parent"] == "F32")

    print(f"\n  F41<->F32 confusion:")
    print(f"    F41->F32 (gold=F41, pred=F32): V10={bl_f41_as_f32}/{f41_total} -> "
          f"Sim={sim_f41_as_f32}/{f41_total}")
    print(f"    F32->F41 (gold=F32, pred=F41): V10={bl_f32_as_f41}/{f32_total} -> "
          f"Sim={sim_f32_as_f41}/{f32_total}")

    # Case-by-case gains
    if gain_details:
        print(f"\n  Gains ({gains} cases):")
        for bl, s in gain_details:
            print(f"    Case {bl['case_id']}: gold={bl['gold']} "
                  f"V10={bl['pred']}({bl['pred_raw']}) -> Sim={s['pred']}({s['pred_raw']}) "
                  f"(conf={s.get('confidence', 0):.2f})")

    # Case-by-case losses
    if loss_details:
        print(f"\n  Losses ({losses} cases):")
        for bl, s in loss_details:
            print(f"    Case {bl['case_id']}: gold={bl['gold']} "
                  f"V10={bl['pred']}({bl['pred_raw']}) -> Sim={s['pred']}({s['pred_raw']}) "
                  f"(conf={s.get('confidence', 0):.2f})")

    return bl_acc, sim_acc


def main():
    print("Loading V10 predictions and case list...")
    predictions, gold_map = load_data()
    n = len(predictions)
    print(f"Loaded {n} cases from V10 LingxiDiag sweep.\n")

    # Distribution
    gold_dist = Counter(parent_code(gold_map[str(p["case_id"])][0])
                        for p in predictions if str(p["case_id"]) in gold_map)
    print("Gold label distribution:")
    for cls, count in sorted(gold_dist.items()):
        print(f"  {cls}: {count} ({count/n:.1%})")

    # --- Variant 1: V11 logic + calibrator (standard) ---
    baseline = run_v10_baseline(predictions, gold_map)
    v11_sim = run_v11_simulation(predictions, gold_map, anxiety_guard=False)
    bl_acc, v11_acc = compare_results(
        baseline, v11_sim, "V11 sim: V11 logic+calibrator on V10 outputs", n
    )

    # --- Variant 2: V11 + anxiety-specificity guard ---
    v11_guard = run_v11_simulation(predictions, gold_map, anxiety_guard=True)
    _, guard_acc = compare_results(
        baseline, v11_guard, "V11+guard: + anxiety-specificity guard for F41.1", n
    )

    # --- Summary ---
    print(f"\n{'='*70}")
    print(f"  SUMMARY")
    print(f"{'='*70}")
    print(f"  V10 baseline:              {bl_acc:.1%}")
    print(f"  V11 sim (logic+cal):       {v11_acc:.1%}  ({(v11_acc-bl_acc)*100:+.1f}pp)")
    print(f"  V11+guard (anxiety gate):  {guard_acc:.1%}  ({(guard_acc-bl_acc)*100:+.1f}pp)")
    print()

    # Detailed: what V11 changes do
    print("  V11 changes tested:")
    print("    1. Soft confirmation (1 short + insufficient_evidence)")
    print("    2. Extra-soft confirmation (F41.1: 2 short + anxiety criterion)")
    print("    3. Conditional proportion-based threshold_ratio (contested F32/F41.1)")
    print("    4. Confirmation type penalties (soft=0.85x, extra_soft=0.70x)")
    print("    5. Comorbidity resolution (F33 supersedes F32, etc.)")
    print()
    print("  Anxiety-specificity guard:")
    print("    For F41.1, require >= 1 of {A, B1, B2} met (not just B3/B4)")
    print("    Targets false positives where only shared criteria are met")


if __name__ == "__main__":
    main()
