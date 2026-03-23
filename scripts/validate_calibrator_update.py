#!/usr/bin/env python3
"""Offline validation of calibrator weight update.

Re-computes calibrator scores using OLD and NEW weights on existing predictions.
No LLM calls — pure offline recomputation.

Usage:
    uv run python scripts/validate_calibrator_update.py
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.core.models import CheckerOutput, CriterionResult
from culturedx.diagnosis.calibrator import ConfidenceCalibrator

OLD_WEIGHTS = {
    "core_score": 0.30,
    "avg_confidence": 0.207,
    "threshold_ratio": 0.207,
    "evidence_coverage": 0.207,
    "uniqueness": 0.00,
    "margin": 0.08,
    "variance": 0.00,
    "info_content": 0.00,
}

NEW_WEIGHTS = {
    "core_score": 0.05,
    "avg_confidence": 0.207,
    "threshold_ratio": 0.35,
    "evidence_coverage": 0.207,
    "uniqueness": 0.00,
    "margin": 0.08,
    "variance": 0.10,
    "info_content": 0.05,
}

SWEEP_PATHS = [
    ("v10_lingxidiag", "outputs/sweeps/v10_lingxidiag_20260320_222603"),
    ("v10_mdd5k", "outputs/sweeps/v10_mdd5k_20260320_233729"),
    ("n200_3mode", "outputs/sweeps/n200_3mode_20260320_131920"),
    ("lingxidiag_crossval", "outputs/sweeps/lingxidiag_3mode_crossval_20260320_195057"),
    ("evidence_lingxidiag", "outputs/sweeps/evidence_lingxidiag_20260321_222749"),
    ("evidence_mdd5k", "outputs/sweeps/evidence_mdd5k_20260322_154253"),
]


def load_data(sweep_dir: Path) -> tuple[dict, list[dict]] | None:
    """Load gold labels and hied predictions from a sweep directory."""
    case_list = sweep_dir / "case_list.json"
    if not case_list.exists():
        return None

    with open(case_list, encoding="utf-8") as f:
        case_data = json.load(f)

    if isinstance(case_data, dict) and "cases" in case_data:
        gold = {str(c["case_id"]): c["diagnoses"] for c in case_data["cases"]}
    else:
        return None

    # Try hied_no_evidence first, then hied_bge-m3_evidence
    for cond in ["hied_no_evidence", "hied_bge-m3_evidence"]:
        pred_path = sweep_dir / cond / "predictions.json"
        if pred_path.exists():
            with open(pred_path, encoding="utf-8") as f:
                raw = json.load(f)
            preds = raw["predictions"] if isinstance(raw, dict) else raw
            return gold, preds

    return None


def reconstruct_checker_outputs(pred: dict) -> list[CheckerOutput]:
    """Reconstruct CheckerOutput objects from prediction criteria_results."""
    outputs = []
    criteria_results = pred.get("criteria_results", [])

    for cr_data in criteria_results:
        # Handle both dict and already-serialized formats
        if isinstance(cr_data, dict):
            criteria = []
            for c in cr_data.get("criteria", []):
                criteria.append(CriterionResult(
                    criterion_id=c.get("criterion_id", ""),
                    status=c.get("status", "not_met"),
                    confidence=c.get("confidence", 0.0),
                    evidence=c.get("evidence", ""),
                ))
            outputs.append(CheckerOutput(
                disorder=cr_data.get("disorder", ""),
                criteria=criteria,
                criteria_met_count=cr_data.get("criteria_met_count", 0),
                criteria_required=cr_data.get("criteria_required", 0),
            ))

    return outputs


def run_calibrator(checker_outputs: list[CheckerOutput], weights: dict) -> str | None:
    """Run calibrator with given weights, return primary diagnosis code."""
    from culturedx.diagnosis.logic_engine import DiagnosticLogicEngine

    engine = DiagnosticLogicEngine()
    logic_output = engine.evaluate(checker_outputs)

    if not logic_output.confirmed:
        return None

    cal = ConfidenceCalibrator(abstain_threshold=0.3, comorbid_threshold=0.5)
    cal.v2_weights = dict(weights)

    confirmation_types = {
        r.disorder_code: r.confirmation_type for r in logic_output.confirmed
    }

    cal_output = cal.calibrate(
        confirmed_disorders=logic_output.confirmed_codes,
        checker_outputs=checker_outputs,
        evidence=None,
        confirmation_types=confirmation_types,
    )

    if cal_output.primary is None:
        return None

    return cal_output.primary.disorder_code


def is_correct(pred_code: str | None, gold_codes: list[str]) -> bool:
    """Check if prediction matches gold using parent-code matching."""
    if pred_code is None:
        return False
    if not gold_codes:
        return False
    pred_parent = pred_code.split(".")[0]
    gold_parents = {g.split(".")[0] for g in gold_codes}
    return pred_parent in gold_parents


def main() -> None:
    print("=" * 70)
    print("CALIBRATOR WEIGHT UPDATE VALIDATION")
    print("=" * 70)
    print(f"\nOLD weights: {OLD_WEIGHTS}")
    print(f"NEW weights: {NEW_WEIGHTS}")

    all_results = []

    for label, sweep_path in SWEEP_PATHS:
        sweep_dir = Path(sweep_path)
        data = load_data(sweep_dir)
        if data is None:
            print(f"\n  SKIP: {label} (not found or bad format)")
            continue

        gold, preds = data
        print(f"\n{'─' * 60}")
        print(f"Dataset: {label}  ({len(preds)} predictions, {len(gold)} gold)")
        print(f"{'─' * 60}")

        old_correct = 0
        new_correct = 0
        old_primary_list = []
        new_primary_list = []
        total = 0
        flips_good = []
        flips_bad = []
        flips_neutral = []
        skipped = 0

        for pred in preds:
            case_id = str(pred["case_id"])
            if case_id not in gold:
                skipped += 1
                continue

            gold_codes = gold[case_id]
            checker_outputs = reconstruct_checker_outputs(pred)

            if not checker_outputs:
                skipped += 1
                continue

            old_primary = run_calibrator(checker_outputs, OLD_WEIGHTS)
            new_primary = run_calibrator(checker_outputs, NEW_WEIGHTS)

            old_ok = is_correct(old_primary, gold_codes)
            new_ok = is_correct(new_primary, gold_codes)

            total += 1
            if old_ok:
                old_correct += 1
            if new_ok:
                new_correct += 1

            old_primary_list.append(old_primary)
            new_primary_list.append(new_primary)

            if old_primary != new_primary:
                flip = {
                    "case_id": case_id,
                    "old": old_primary,
                    "new": new_primary,
                    "gold": gold_codes,
                    "old_correct": old_ok,
                    "new_correct": new_ok,
                }
                if new_ok and not old_ok:
                    flips_good.append(flip)
                elif not new_ok and old_ok:
                    flips_bad.append(flip)
                else:
                    flips_neutral.append(flip)

        if total == 0:
            print("  No valid predictions to evaluate")
            continue

        old_acc = old_correct / total
        new_acc = new_correct / total
        delta = new_acc - old_acc

        print(f"\n  Old Top-1: {old_acc:.4f} ({old_correct}/{total})")
        print(f"  New Top-1: {new_acc:.4f} ({new_correct}/{total})")
        print(f"  Delta:     {delta:+.4f} ({delta*100:+.1f}pp)")
        print(f"  Skipped:   {skipped}")

        print(f"\n  Flips: {len(flips_good)} good, {len(flips_bad)} bad, "
              f"{len(flips_neutral)} neutral")
        print(f"  Net:   {len(flips_good) - len(flips_bad):+d}")

        if flips_good:
            print(f"\n  GOOD flips (old wrong → new correct):")
            for f in flips_good[:10]:
                print(f"    {f['case_id']:20s}  {f['old']} → {f['new']}  "
                      f"(gold: {f['gold']})")

        if flips_bad:
            print(f"\n  BAD flips (old correct → new wrong):")
            for f in flips_bad[:10]:
                print(f"    {f['case_id']:20s}  {f['old']} → {f['new']}  "
                      f"(gold: {f['gold']})")

        # Per-disorder-pair analysis
        pair_counts = defaultdict(lambda: {"good": 0, "bad": 0, "neutral": 0})
        for f in flips_good + flips_bad + flips_neutral:
            pair = f"{f['old']}→{f['new']}"
            if f in flips_good:
                pair_counts[pair]["good"] += 1
            elif f in flips_bad:
                pair_counts[pair]["bad"] += 1
            else:
                pair_counts[pair]["neutral"] += 1

        if pair_counts:
            print(f"\n  Flip pairs:")
            print(f"  {'Pair':20s} {'Good':>5s} {'Bad':>5s} {'Neutral':>8s} {'Net':>5s}")
            for pair, counts in sorted(pair_counts.items(),
                                       key=lambda x: -(x[1]["good"] - x[1]["bad"])):
                net = counts["good"] - counts["bad"]
                print(f"  {pair:20s} {counts['good']:5d} {counts['bad']:5d} "
                      f"{counts['neutral']:8d} {net:+5d}")

        all_results.append({
            "dataset": label,
            "n": total,
            "old_accuracy": round(old_acc, 4),
            "new_accuracy": round(new_acc, 4),
            "delta": round(delta, 4),
            "delta_pp": round(delta * 100, 1),
            "flips_good": len(flips_good),
            "flips_bad": len(flips_bad),
            "flips_neutral": len(flips_neutral),
            "flip_details": [
                {
                    "case_id": f["case_id"],
                    "old": f["old"],
                    "new": f["new"],
                    "gold": f["gold"],
                    "type": "good" if f in flips_good else "bad" if f in flips_bad else "neutral",
                }
                for f in flips_good + flips_bad + flips_neutral
            ],
        })

    # Save results
    out_path = Path("outputs/calibrator_update_validation.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")

    # Summary table
    print(f"\n{'=' * 70}")
    print(f"SUMMARY")
    print(f"{'=' * 70}")
    print(f"{'Dataset':25s} | {'Old Top-1':>10s} | {'New Top-1':>10s} | "
          f"{'Delta':>7s} | {'Good/Bad Flips':>15s}")
    print(f"{'-'*25} | {'-'*10} | {'-'*10} | {'-'*7} | {'-'*15}")
    for r in all_results:
        print(f"{r['dataset']:25s} | {r['old_accuracy']:9.1%} | "
              f"{r['new_accuracy']:9.1%} | {r['delta_pp']:+5.1f}pp | "
              f"{r['flips_good']:3d}/{r['flips_bad']:<3d}")


if __name__ == "__main__":
    main()
