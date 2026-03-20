#!/usr/bin/env python3
"""Post-experiment analysis: multi-mode comparison + V2 calibrator simulation.

Usage:
    uv run python scripts/analyze_results.py --predictions-dir outputs/exp_50case_v1
    uv run python scripts/analyze_results.py --predictions-dir outputs/exp_50case_v1 --save-csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def parent_code(code: str | None) -> str:
    if code is None or code == "None":
        return "abstain"
    return code.split(".")[0]


def load_predictions(pred_dir: Path) -> dict[str, dict]:
    modes = {}
    for f in sorted(pred_dir.glob("*_predictions.json")):
        mode_name = f.stem.replace("_predictions", "")
        with open(f, "r", encoding="utf-8") as fh:
            modes[mode_name] = json.load(fh)
    return modes


def extract_gold_from_log(pred_dir: Path) -> dict[str, list[str]]:
    log_path = pred_dir.parent / f"{pred_dir.name}_log.txt"
    if not log_path.exists():
        log_candidates = list(pred_dir.parent.glob("*_log.txt"))
        log_path = log_candidates[0] if log_candidates else None
    if not log_path or not log_path.exists():
        return {}
    gold = {}
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            m = re.search(
                r'\[(?:hied|single|specialist|debate|psycot)\]\s+\d+/\d+\s+case=(\S+)\s+pred=\S+\s+gold=\[([^\]]+)\]',
                line,
            )
            if m and m.group(1) not in gold:
                golds = [g.strip().strip("'\"") for g in m.group(2).split(",")]
                gold[m.group(1)] = golds
    return gold


def reconstruct_checker_outputs(pred: dict):
    from culturedx.core.models import CheckerOutput, CriterionResult

    cos = []
    for cr in pred.get("criteria_results", []):
        criteria = [
            CriterionResult(
                criterion_id=c["criterion_id"],
                status=c["status"],
                evidence=c.get("evidence"),
                confidence=c.get("confidence", 0.5),
            )
            for c in cr.get("criteria", [])
        ]
        cos.append(
            CheckerOutput(
                disorder=cr["disorder"],
                criteria=criteria,
                criteria_met_count=cr["criteria_met_count"],
                criteria_required=cr["criteria_required"],
            )
        )
    return cos


def simulate_v2(predictions: list[dict], gold_map: dict) -> dict:
    from culturedx.diagnosis.calibrator import ConfidenceCalibrator
    from culturedx.diagnosis.logic_engine import DiagnosticLogicEngine

    cal = ConfidenceCalibrator(abstain_threshold=0.3, comorbid_threshold=0.5, version=2)
    logic = DiagnosticLogicEngine()

    results = []
    for pred in predictions:
        case_id = pred["case_id"]
        gold = gold_map.get(case_id, [])
        gold_p = parent_code(gold[0]) if gold else "?"

        checker_outputs = reconstruct_checker_outputs(pred)
        logic_out = logic.evaluate(checker_outputs)

        if not logic_out.confirmed:
            v2_pred = "abstain"
            v2_conf = 0.0
        else:
            v2_cal = cal.calibrate(
                confirmed_disorders=logic_out.confirmed_codes,
                checker_outputs=checker_outputs,
            )
            if v2_cal.primary:
                v2_pred = parent_code(v2_cal.primary.disorder_code)
                v2_conf = v2_cal.primary.confidence
            else:
                v2_pred = "abstain"
                v2_conf = 0.0

        results.append({
            "case_id": case_id,
            "gold": gold_p,
            "v1_pred": parent_code(pred["primary_diagnosis"]),
            "v2_pred": v2_pred,
            "v2_conf": v2_conf,
        })
    return results


def compute_mode_metrics(predictions: list[dict], gold_map: dict) -> dict:
    correct = 0
    total = 0
    by_gold = defaultdict(lambda: [0, 0])
    by_pred = Counter()
    abstain = 0

    for p in predictions:
        pred = parent_code(p["primary_diagnosis"])
        gold = gold_map.get(p["case_id"], [])
        gold_p = parent_code(gold[0]) if gold else "?"

        by_pred[pred] += 1
        if pred == "abstain":
            abstain += 1
        by_gold[gold_p][1] += 1
        if pred == gold_p:
            correct += 1
            by_gold[gold_p][0] += 1
        total += 1

    return {
        "correct": correct,
        "total": total,
        "accuracy": correct / total if total > 0 else 0,
        "by_gold": dict(by_gold),
        "by_pred": dict(by_pred),
        "abstain": abstain,
    }


def print_summary(modes_data: dict, gold_map: dict, pred_dir: Path):
    print("=" * 80)
    print(f"EXPERIMENT RESULTS: {pred_dir.name}")
    print("=" * 80)

    all_metrics = {}
    for mode_name, data in modes_data.items():
        metrics = compute_mode_metrics(data["predictions"], gold_map)
        all_metrics[mode_name] = metrics

    # Summary table
    print(f"\n{'Mode':<12} {'Top-1':>8} {'F32':>10} {'F41':>10} {'Other':>8} {'Abstain':>8} {'s/case':>8}")
    print("-" * 70)
    for mode_name, data in modes_data.items():
        m = all_metrics[mode_name]
        bg = m["by_gold"]
        f32_c, f32_t = bg.get("F32", [0, 0])
        f41_c, f41_t = bg.get("F41", [0, 0])
        other_c = m["correct"] - f32_c - f41_c
        other_t = m["total"] - f32_t - f41_t
        spc = data.get("avg_seconds_per_case", "?")
        print(
            f"{mode_name:<12} {m['accuracy']*100:>7.1f}% "
            f"{f32_c}/{f32_t}={'N/A' if f32_t==0 else f'{f32_c/f32_t*100:.0f}%':>4} "
            f"{f41_c}/{f41_t}={'N/A' if f41_t==0 else f'{f41_c/f41_t*100:.0f}%':>4} "
            f"{other_c:>3}/{other_t:<3} "
            f"{m['abstain']:>8} "
            f"{spc:>8}"
        )

    # V2 simulation for HiED
    if "hied" in modes_data:
        hied_preds = modes_data["hied"]["predictions"]
        if hied_preds and hied_preds[0].get("criteria_results"):
            print(f"\n{'='*80}")
            print("V2 CALIBRATOR SIMULATION (HiED only)")
            print("=" * 80)
            v2_results = simulate_v2(hied_preds, gold_map)
            v1_correct = sum(1 for r in v2_results if r["v1_pred"] == r["gold"])
            v2_correct = sum(1 for r in v2_results if r["v2_pred"] == r["gold"])
            n = len(v2_results)
            print(f"V1 actual:    {v1_correct}/{n} = {v1_correct/n*100:.1f}%")
            print(f"V2 simulated: {v2_correct}/{n} = {v2_correct/n*100:.1f}%")

            # Per-disorder
            for label in ["F32", "F41"]:
                v1_c = sum(1 for r in v2_results if r["gold"] == label and r["v1_pred"] == label)
                v2_c = sum(1 for r in v2_results if r["gold"] == label and r["v2_pred"] == label)
                t = sum(1 for r in v2_results if r["gold"] == label)
                if t > 0:
                    print(f"  {label}: V1={v1_c}/{t}({v1_c/t*100:.0f}%) V2={v2_c}/{t}({v2_c/t*100:.0f}%)")

            # Changed cases
            changed = [r for r in v2_results if r["v1_pred"] != r["v2_pred"]]
            fixed = sum(1 for r in changed if r["v2_pred"] == r["gold"] and r["v1_pred"] != r["gold"])
            regressed = sum(1 for r in changed if r["v1_pred"] == r["gold"] and r["v2_pred"] != r["gold"])
            print(f"\nChanged: {len(changed)} cases, Fixed: {fixed}, Regressed: {regressed}, Net: +{fixed-regressed}")

    # Confusion matrix
    print(f"\n{'='*80}")
    print("PER-MODE PREDICTION DISTRIBUTION")
    print("=" * 80)
    for mode_name, data in modes_data.items():
        m = all_metrics[mode_name]
        print(f"  {mode_name}: {dict(m['by_pred'])}")


def save_csv(modes_data: dict, gold_map: dict, output_path: Path):
    rows = []
    for mode_name, data in modes_data.items():
        for p in data["predictions"]:
            gold = gold_map.get(p["case_id"], [])
            rows.append({
                "mode": mode_name,
                "case_id": p["case_id"],
                "gold": gold[0] if gold else "",
                "gold_parent": parent_code(gold[0]) if gold else "",
                "pred": p["primary_diagnosis"] or "abstain",
                "pred_parent": parent_code(p["primary_diagnosis"]),
                "confidence": p.get("confidence", 0),
                "decision": p.get("decision", ""),
                "match": parent_code(p["primary_diagnosis"]) == parent_code(gold[0]) if gold else False,
            })
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nCSV saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Post-experiment analysis")
    parser.add_argument("--predictions-dir", "-d", type=str, required=True)
    parser.add_argument("--save-csv", action="store_true")
    args = parser.parse_args()

    pred_dir = Path(args.predictions_dir)
    modes_data = load_predictions(pred_dir)
    if not modes_data:
        print(f"No prediction files found in {pred_dir}")
        return

    gold_map = extract_gold_from_log(pred_dir)
    if not gold_map:
        print("No gold labels found, loading dataset...")
        from culturedx.data.adapters import get_adapter
        adapter = get_adapter("mdd5k_raw", "data/raw/mdd5k_repo")
        all_cases = adapter.load()
        gold_map = {c.case_id: c.diagnoses for c in all_cases}

    print_summary(modes_data, gold_map, pred_dir)

    if args.save_csv:
        save_csv(modes_data, gold_map, pred_dir / "analysis.csv")


if __name__ == "__main__":
    main()
