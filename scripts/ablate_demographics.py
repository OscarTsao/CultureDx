#!/usr/bin/env python3
"""Offline demographics ablation: test demographic prior at varying weights.

Re-scores existing predictions with demographic_prior weight at 0, 0.05, 0.10, 0.15.
Includes fairness check per (gender, age_group) bucket.
Zero LLM cost — offline re-ranking only.

Usage:
    uv run python scripts/ablate_demographics.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.core.models import CheckerOutput, CriterionResult
from culturedx.diagnosis.calibrator import ConfidenceCalibrator
from culturedx.diagnosis.logic_engine import DiagnosticLogicEngine

# LingxiDiag sweeps that have demographics in metadata
SWEEP_PATHS = [
    ("v10_lingxidiag", "outputs/sweeps/v10_lingxidiag_20260320_222603"),
    ("lingxidiag_crossval", "outputs/sweeps/lingxidiag_3mode_crossval_20260320_195057"),
]

# Need LingxiDiag adapter to get demographics
LINGXIDIAG_DATA_PATH = "data/raw/lingxidiag16k"

WEIGHTS_TO_TEST = [0.00, 0.05, 0.10, 0.15]


def load_demographics(data_path: str) -> dict[str, dict]:
    """Load age/gender from LingxiDiag adapter."""
    from culturedx.data.adapters import get_adapter
    adapter = get_adapter("lingxidiag16k", data_path)
    cases = adapter.load()
    return {
        c.case_id: {
            "age": (c.metadata or {}).get("age"),
            "gender": (c.metadata or {}).get("gender"),
        }
        for c in cases
    }


def load_sweep(sweep_dir: Path) -> tuple[dict, list[dict]] | None:
    """Load gold labels and hied predictions."""
    case_list = sweep_dir / "case_list.json"
    if not case_list.exists():
        return None

    with open(case_list, encoding="utf-8") as f:
        case_data = json.load(f)

    if not isinstance(case_data, dict) or "cases" not in case_data:
        return None

    gold = {str(c["case_id"]): c["diagnoses"] for c in case_data["cases"]}

    pred_path = sweep_dir / "hied_no_evidence" / "predictions.json"
    if not pred_path.exists():
        return None

    with open(pred_path, encoding="utf-8") as f:
        raw = json.load(f)
    preds = raw["predictions"] if isinstance(raw, dict) else raw
    return gold, preds


def reconstruct_checker_outputs(pred: dict) -> list[CheckerOutput]:
    """Reconstruct CheckerOutput objects from prediction criteria_results."""
    outputs = []
    for cr_data in pred.get("criteria_results", []):
        if isinstance(cr_data, dict):
            criteria = [
                CriterionResult(
                    criterion_id=c.get("criterion_id", ""),
                    status=c.get("status", "not_met"),
                    confidence=c.get("confidence", 0.0),
                    evidence=c.get("evidence", ""),
                )
                for c in cr_data.get("criteria", [])
            ]
            outputs.append(CheckerOutput(
                disorder=cr_data.get("disorder", ""),
                criteria=criteria,
                criteria_met_count=cr_data.get("criteria_met_count", 0),
                criteria_required=cr_data.get("criteria_required", 0),
            ))
    return outputs


def run_with_weight(
    checker_outputs: list[CheckerOutput],
    demographics: dict | None,
    demo_weight: float,
) -> str | None:
    """Run calibrator with given demographic weight, return primary code."""
    engine = DiagnosticLogicEngine()
    logic_output = engine.evaluate(checker_outputs)

    if not logic_output.confirmed:
        return None

    cal = ConfidenceCalibrator(abstain_threshold=0.3, comorbid_threshold=0.5)
    cal.v2_weights["demographic_prior"] = demo_weight

    confirmation_types = {
        r.disorder_code: r.confirmation_type for r in logic_output.confirmed
    }

    cal_output = cal.calibrate(
        confirmed_disorders=logic_output.confirmed_codes,
        checker_outputs=checker_outputs,
        evidence=None,
        confirmation_types=confirmation_types,
        demographics=demographics if demo_weight > 0 else None,
    )

    return cal_output.primary.disorder_code if cal_output.primary else None


def is_correct(pred_code: str | None, gold_codes: list[str]) -> bool:
    if pred_code is None or not gold_codes:
        return False
    return pred_code.split(".")[0] in {g.split(".")[0] for g in gold_codes}


def age_group(age) -> str:
    if age is None:
        return "unknown"
    try:
        age = int(age)
    except (ValueError, TypeError):
        return "unknown"
    if age < 25:
        return "<25"
    if age < 35:
        return "25-34"
    if age < 45:
        return "35-44"
    if age < 55:
        return "45-54"
    return "55+"


def main() -> None:
    # Load demographics
    demo_path = Path(LINGXIDIAG_DATA_PATH)
    if not demo_path.exists():
        print(f"ERROR: LingxiDiag data not found at {demo_path}")
        sys.exit(1)

    demo_map = load_demographics(str(demo_path))
    print(f"Loaded demographics for {len(demo_map)} cases")

    # Count available demographics
    has_age = sum(1 for d in demo_map.values() if d.get("age") is not None)
    has_gender = sum(1 for d in demo_map.values() if d.get("gender") is not None)
    print(f"  With age: {has_age}, with gender: {has_gender}")

    all_results = []

    for label, sweep_path in SWEEP_PATHS:
        sweep_dir = Path(sweep_path)
        data = load_sweep(sweep_dir)
        if data is None:
            print(f"\n  SKIP: {label}")
            continue

        gold, preds = data
        print(f"\n{'=' * 70}")
        print(f"Dataset: {label} ({len(preds)} predictions)")
        print(f"{'=' * 70}")

        # For each weight, compute accuracy
        weight_results = {}
        for w in WEIGHTS_TO_TEST:
            correct_count = 0
            total = 0
            per_bucket = defaultdict(lambda: {"correct": 0, "total": 0})

            for pred in preds:
                case_id = str(pred["case_id"])
                if case_id not in gold:
                    continue

                gold_codes = gold[case_id]
                checker_outputs = reconstruct_checker_outputs(pred)
                if not checker_outputs:
                    continue

                demographics = demo_map.get(case_id)
                primary = run_with_weight(checker_outputs, demographics, w)
                ok = is_correct(primary, gold_codes)

                total += 1
                if ok:
                    correct_count += 1

                # Bucket by gender + age group
                if demographics:
                    g = demographics.get("gender", "unknown") or "unknown"
                    a = age_group(demographics.get("age"))
                    bucket = f"{g}_{a}"
                else:
                    bucket = "no_demo"

                per_bucket[bucket]["total"] += 1
                if ok:
                    per_bucket[bucket]["correct"] += 1

            acc = correct_count / total if total else 0
            weight_results[w] = {
                "accuracy": round(acc, 4),
                "correct": correct_count,
                "total": total,
                "per_bucket": dict(per_bucket),
            }

        # Print weight comparison
        baseline = weight_results[0.0]["accuracy"]
        print(f"\n  {'Weight':>8s} | {'Top-1 Acc':>10s} | {'Delta':>7s} | {'N':>5s}")
        print(f"  {'-'*8} | {'-'*10} | {'-'*7} | {'-'*5}")
        for w in WEIGHTS_TO_TEST:
            r = weight_results[w]
            delta = r["accuracy"] - baseline
            marker = " (baseline)" if w == 0.0 else ""
            print(f"  {w:8.2f} | {r['accuracy']:9.1%} | "
                  f"{delta*100:+5.1f}pp | {r['total']:5d}{marker}")

        # Flip analysis between baseline and best weight
        best_w = max(WEIGHTS_TO_TEST[1:],
                     key=lambda w: weight_results[w]["accuracy"])
        if weight_results[best_w]["accuracy"] > baseline:
            print(f"\n  Best non-zero weight: {best_w}")

            # Detailed flip analysis
            flips_good = []
            flips_bad = []
            for pred in preds:
                case_id = str(pred["case_id"])
                if case_id not in gold:
                    continue
                gold_codes = gold[case_id]
                checker_outputs = reconstruct_checker_outputs(pred)
                if not checker_outputs:
                    continue

                demographics = demo_map.get(case_id)
                p0 = run_with_weight(checker_outputs, demographics, 0.0)
                pb = run_with_weight(checker_outputs, demographics, best_w)

                if p0 != pb:
                    ok0 = is_correct(p0, gold_codes)
                    okb = is_correct(pb, gold_codes)
                    flip = {
                        "case_id": case_id,
                        "old": p0,
                        "new": pb,
                        "gold": gold_codes,
                        "demographics": demographics,
                    }
                    if okb and not ok0:
                        flips_good.append(flip)
                    elif not okb and ok0:
                        flips_bad.append(flip)

            print(f"  Good flips: {len(flips_good)}, Bad flips: {len(flips_bad)}, "
                  f"Net: {len(flips_good) - len(flips_bad):+d}")
            for f in flips_good[:5]:
                d = f["demographics"] or {}
                print(f"    GOOD: {f['case_id']:20s} {f['old']}→{f['new']} "
                      f"(gold:{f['gold']}, {d.get('gender','?')}/{d.get('age','?')})")
            for f in flips_bad[:5]:
                d = f["demographics"] or {}
                print(f"    BAD:  {f['case_id']:20s} {f['old']}→{f['new']} "
                      f"(gold:{f['gold']}, {d.get('gender','?')}/{d.get('age','?')})")

        # Fairness check
        print(f"\n  Fairness check (subgroup accuracy at weight={best_w} vs baseline):")
        print(f"  {'Bucket':20s} {'N':>5s} {'Acc@0.0':>8s} {'Acc@{:.2f}'.format(best_w):>10s} "
              f"{'Δ':>7s} {'FLAG':>5s}")
        print(f"  {'-'*20} {'-'*5} {'-'*8} {'-'*10} {'-'*7} {'-'*5}")

        base_buckets = weight_results[0.0]["per_bucket"]
        best_buckets = weight_results[best_w]["per_bucket"]

        for bucket in sorted(set(list(base_buckets.keys()) + list(best_buckets.keys()))):
            b0 = base_buckets.get(bucket, {"correct": 0, "total": 0})
            bb = best_buckets.get(bucket, {"correct": 0, "total": 0})
            n = b0["total"]
            if n == 0:
                continue
            acc0 = b0["correct"] / n
            accb = bb["correct"] / bb["total"] if bb["total"] > 0 else 0
            delta = accb - acc0
            flag = "⚠" if delta < -0.03 else ""
            print(f"  {bucket:20s} {n:5d} {acc0:7.1%} {accb:9.1%} "
                  f"{delta*100:+5.1f}pp {flag}")

        all_results.append({
            "dataset": label,
            "weight_results": {
                str(w): {
                    "accuracy": weight_results[w]["accuracy"],
                    "correct": weight_results[w]["correct"],
                    "total": weight_results[w]["total"],
                }
                for w in WEIGHTS_TO_TEST
            },
            "baseline": baseline,
            "best_weight": best_w,
            "best_accuracy": weight_results[best_w]["accuracy"],
        })

    # Save
    out_path = Path("outputs/demographics_ablation.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
