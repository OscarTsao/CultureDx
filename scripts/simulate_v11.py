#!/usr/bin/env python3
"""V11 Simulation: replay baseline checker outputs through V11 logic + calibrator.

No new LLM calls. Tests the impact of calibrator/logic engine changes only.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from culturedx.core.models import CheckerOutput, CriterionResult
from culturedx.diagnosis.calibrator import ConfidenceCalibrator
from culturedx.diagnosis.logic_engine import DiagnosticLogicEngine

SWEEPS = ROOT / "outputs" / "sweeps"


def parent_code(code: str | None) -> str:
    if not code or code in ("None", "ABSTAIN"):
        return ""
    return code.split(".")[0]


def load_sweep(sweep_dir: Path, mode: str = "hied_no_evidence"):
    preds_path = sweep_dir / mode / "predictions.json"
    cases_path = sweep_dir / "case_list.json"

    with open(preds_path, encoding="utf-8") as f:
        pred_data = json.load(f)
    with open(cases_path, encoding="utf-8") as f:
        case_data = json.load(f)

    gold_map = {str(c["case_id"]): c["diagnoses"] for c in case_data["cases"]}
    return pred_data["predictions"], gold_map


def criteria_to_checker_output(disorder: str, criteria_list: list[dict]) -> CheckerOutput:
    """Convert raw criteria dict to CheckerOutput model."""
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
    from culturedx.ontology.icd10 import get_disorder_threshold
    threshold = get_disorder_threshold(disorder)
    if "min_total" in threshold:
        required = threshold["min_total"]
    elif "min_symptoms" in threshold:
        required = threshold["min_symptoms"]
    elif threshold.get("all_required"):
        from culturedx.ontology.icd10 import get_disorder_criteria
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


def simulate(sweep_dir: Path, label: str):
    predictions, gold_map = load_sweep(sweep_dir)

    engine = DiagnosticLogicEngine()
    calibrator = ConfidenceCalibrator(version=2)

    baseline_results = []
    v11_results = []

    for pred in predictions:
        case_id = str(pred["case_id"])
        golds = gold_map.get(case_id, [])
        gold_parents = {parent_code(g) for g in golds}

        # Baseline result
        bl_pred = parent_code(pred.get("primary_diagnosis"))
        bl_correct = bl_pred in gold_parents if bl_pred else False
        baseline_results.append({
            "case_id": case_id,
            "gold": golds[0] if golds else "",
            "pred": bl_pred,
            "correct": bl_correct,
        })

        # V11 simulation: replay through logic engine + calibrator
        checker_outputs = []
        for cr_result in pred.get("criteria_results", []):
            co = criteria_to_checker_output(
                cr_result["disorder"], cr_result["criteria"]
            )
            checker_outputs.append(co)

        if not checker_outputs:
            v11_results.append({
                "case_id": case_id,
                "gold": golds[0] if golds else "",
                "pred": "",
                "correct": False,
            })
            continue

        # Logic engine
        logic_output = engine.evaluate(checker_outputs)

        # Calibrator
        confirmation_types = {
            r.disorder_code: r.confirmation_type
            for r in logic_output.confirmed
        }
        cal_output = calibrator.calibrate(
            confirmed_disorders=logic_output.confirmed_codes,
            checker_outputs=checker_outputs,
            confirmation_types=confirmation_types,
        )

        if cal_output.primary:
            v11_pred = parent_code(cal_output.primary.disorder_code)
            v11_conf = cal_output.primary.confidence
        else:
            v11_pred = ""
            v11_conf = 0.0

        v11_correct = v11_pred in gold_parents if v11_pred else False
        v11_results.append({
            "case_id": case_id,
            "gold": golds[0] if golds else "",
            "pred": v11_pred,
            "correct": v11_correct,
            "conf": v11_conf,
        })

    # Compare
    n = len(baseline_results)
    bl_acc = sum(r["correct"] for r in baseline_results) / n
    v11_acc = sum(r["correct"] for r in v11_results) / n

    gains = losses = stayed_correct = stayed_wrong = 0
    gain_details = []
    loss_details = []

    for bl, v11 in zip(baseline_results, v11_results):
        if bl["correct"] and v11["correct"]:
            stayed_correct += 1
        elif not bl["correct"] and not v11["correct"]:
            stayed_wrong += 1
        elif not bl["correct"] and v11["correct"]:
            gains += 1
            gain_details.append(bl)
        else:
            losses += 1
            loss_details.append(bl)

    print(f"\n{'='*60}")
    print(f"V11 SIMULATION: {label} (N={n})")
    print(f"{'='*60}")
    print(f"Baseline accuracy: {bl_acc:.1%} ({sum(r['correct'] for r in baseline_results)}/{n})")
    print(f"V11 accuracy:      {v11_acc:.1%} ({sum(r['correct'] for r in v11_results)}/{n})")
    print(f"Delta:             {(v11_acc-bl_acc)*100:+.1f}pp")
    print(f"\nStayed correct: {stayed_correct}")
    print(f"Stayed wrong:   {stayed_wrong}")
    print(f"Gains:          +{gains}")
    print(f"Losses:         -{losses}")
    print(f"Net:            {gains-losses:+d}")

    # By gold disorder
    gain_golds = Counter(parent_code(g["gold"]) for g in gain_details)
    loss_golds = Counter(parent_code(g["gold"]) for g in loss_details)
    if gain_golds:
        print(f"\nGains by gold: {dict(gain_golds.most_common())}")
    if loss_golds:
        print(f"Losses by gold: {dict(loss_golds.most_common())}")

    # F41 recall
    f41_bl = [r for r in baseline_results if parent_code(r["gold"]) == "F41"]
    f41_v11 = [r for r in v11_results if parent_code(r["gold"]) == "F41"]
    if f41_bl:
        print(f"\nF41 recall: baseline={sum(r['correct'] for r in f41_bl)}/{len(f41_bl)} "
              f"({sum(r['correct'] for r in f41_bl)/len(f41_bl):.1%}) "
              f"-> V11={sum(r['correct'] for r in f41_v11)}/{len(f41_v11)} "
              f"({sum(r['correct'] for r in f41_v11)/len(f41_v11):.1%})")

    # F32 recall
    f32_bl = [r for r in baseline_results if parent_code(r["gold"]) == "F32"]
    f32_v11 = [r for r in v11_results if parent_code(r["gold"]) == "F32"]
    if f32_bl:
        print(f"F32 recall: baseline={sum(r['correct'] for r in f32_bl)}/{len(f32_bl)} "
              f"({sum(r['correct'] for r in f32_bl)/len(f32_bl):.1%}) "
              f"-> V11={sum(r['correct'] for r in f32_v11)}/{len(f32_v11)} "
              f"({sum(r['correct'] for r in f32_v11)/len(f32_v11):.1%})")


if __name__ == "__main__":
    # LingxiDiag baseline
    lingxi_dir = SWEEPS / "lingxidiag_3mode_crossval_20260320_195057"
    if lingxi_dir.exists():
        simulate(lingxi_dir, "LingxiDiag HiED (baseline checker outputs)")

    # MDD-5k baseline
    mdd_dir = SWEEPS / "n200_3mode_20260320_131920"
    if mdd_dir.exists():
        simulate(mdd_dir, "MDD-5k HiED (baseline checker outputs)")
