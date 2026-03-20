#!/usr/bin/env python3
"""Analyze vLLM sweep results and compare with Ollama V1 baseline.

Usage:
    uv run python scripts/analyze_vllm_sweep.py --sweep-dir outputs/sweeps/vllm_5mode_v2_*
    uv run python scripts/analyze_vllm_sweep.py --sweep-dir outputs/sweeps/vllm_5mode_v2_* --live
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def load_predictions(pred_path: Path) -> list[dict]:
    """Load predictions from a sweep condition directory."""
    with open(pred_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("predictions", [])


def parent_code(code: str) -> str:
    """Normalize to parent code (F32.1 -> F32, F41.1 -> F41)."""
    if not code:
        return ""
    parts = code.split(".")
    if len(parts) >= 2 and parts[0].startswith("F"):
        base = parts[0]
        if len(base) == 2:
            return base
        if len(base) == 3:
            return base
    return code


def analyze_condition(pred_path: Path, gold_map: dict[str, list[str]] | None = None) -> dict:
    """Analyze a single condition's predictions."""
    preds = load_predictions(pred_path)

    IN_TARGET = {"F32", "F33", "F41", "F42", "F43"}

    results = {
        "n_cases": len(preds),
        "correct": 0,
        "abstained": 0,
        "per_disorder": defaultdict(lambda: {"total": 0, "correct": 0}),
        "confusion": defaultdict(int),
        "confidence_correct": [],
        "confidence_wrong": [],
        "f41_detail": [],
        "in_target_correct": 0,
        "in_target_total": 0,
        "out_target_correct_abstain": 0,
        "out_target_total": 0,
    }

    for p in preds:
        case_id = p.get("case_id", "")
        gold_codes = gold_map.get(case_id, []) if gold_map else p.get("gold_diagnoses", [])
        if not gold_codes:
            continue

        gold = parent_code(gold_codes[0]) if gold_codes else ""
        pred_raw = p.get("primary_diagnosis") or ""
        pred = parent_code(pred_raw)
        conf = p.get("confidence", 0.0)

        is_in_target = gold in IN_TARGET

        if not pred or pred == "":
            results["abstained"] += 1
            if not is_in_target:
                results["out_target_total"] += 1
                results["out_target_correct_abstain"] += 1
            continue

        results["per_disorder"][gold]["total"] += 1

        if is_in_target:
            results["in_target_total"] += 1
            if pred == gold:
                results["in_target_correct"] += 1
        else:
            results["out_target_total"] += 1

        if pred == gold:
            results["correct"] += 1
            results["per_disorder"][gold]["correct"] += 1
            results["confidence_correct"].append(conf)
        else:
            results["confusion"][f"{gold}->{pred}"] += 1
            results["confidence_wrong"].append(conf)

        if gold == "F41":
            results["f41_detail"].append({
                "case_id": case_id,
                "pred": pred,
                "conf": conf,
                "correct": pred == "F41",
            })

    diagnosed = results["n_cases"] - results["abstained"]
    results["accuracy"] = results["correct"] / diagnosed if diagnosed else 0
    results["abstain_rate"] = results["abstained"] / results["n_cases"] if results["n_cases"] else 0

    avg_conf_correct = sum(results["confidence_correct"]) / len(results["confidence_correct"]) if results["confidence_correct"] else 0
    avg_conf_wrong = sum(results["confidence_wrong"]) / len(results["confidence_wrong"]) if results["confidence_wrong"] else 0
    results["avg_conf_correct"] = avg_conf_correct
    results["avg_conf_wrong"] = avg_conf_wrong
    results["conf_gap"] = avg_conf_correct - avg_conf_wrong

    results["in_target_accuracy"] = (
        results["in_target_correct"] / results["in_target_total"]
        if results["in_target_total"] else 0
    )
    results["out_target_accuracy"] = (
        results["out_target_correct_abstain"] / results["out_target_total"]
        if results["out_target_total"] else 0
    )

    return results


def print_summary(sweep_dir: Path) -> None:
    """Print sweep summary."""
    conditions = sorted(sweep_dir.iterdir())

    # Load gold labels from case_list.json
    case_list_path = sweep_dir / "case_list.json"
    gold_map = {}
    if case_list_path.exists():
        with open(case_list_path, encoding="utf-8") as f:
            case_list = json.load(f)
        gold_map = {c["case_id"]: c["diagnoses"] for c in case_list["cases"]}

    print("=" * 90)
    print(f"SWEEP ANALYSIS: {sweep_dir.name}")
    print("=" * 90)

    # Overall comparison table
    print(f"\n{'Condition':<35} {'Top-1':>7} {'n':>4} {'Abst':>5} {'F32':>6} {'F41':>6} {'ConfGap':>8} {'s/case':>7}")
    print("-" * 90)

    all_results = {}
    for cond_dir in conditions:
        if not cond_dir.is_dir():
            continue
        pred_file = cond_dir / "predictions.json"
        if not pred_file.exists():
            continue

        results = analyze_condition(pred_file, gold_map=gold_map)
        all_results[cond_dir.name] = results

        f32 = results["per_disorder"].get("F32", {"total": 0, "correct": 0})
        f41 = results["per_disorder"].get("F41", {"total": 0, "correct": 0})
        f32_acc = f"{f32['correct']}/{f32['total']}" if f32["total"] else "n/a"
        f41_acc = f"{f41['correct']}/{f41['total']}" if f41["total"] else "n/a"

        # Load timing from metrics
        metrics_file = cond_dir / "metrics.json"
        s_per_case = 0
        if metrics_file.exists():
            with open(metrics_file, encoding="utf-8") as f:
                m = json.load(f)
            s_per_case = m.get("avg_seconds_per_case", 0)

        print(f"{cond_dir.name:<35} {results['accuracy']:>6.1%} {results['n_cases']:>4} "
              f"{results['abstained']:>5} {f32_acc:>6} {f41_acc:>6} "
              f"{results['conf_gap']:>+7.3f} {s_per_case:>7.1f}")

    # In-target vs out-of-target accuracy table
    print(f"\n{'=' * 90}")
    print("IN-TARGET vs OUT-OF-TARGET ACCURACY  (in-target: F32 F33 F41 F42 F43)")
    print(f"{'=' * 90}")
    print(f"\n{'Condition':<35} {'InTgt':>7} {'(n)':>5} {'OutTgt':>8} {'(n)':>5}")
    print("-" * 65)
    for name, results in all_results.items():
        in_acc = results["in_target_accuracy"]
        in_n = results["in_target_total"]
        out_acc = results["out_target_accuracy"]
        out_n = results["out_target_total"]
        in_str = f"{in_acc:.1%}" if in_n else "n/a"
        out_str = f"{out_acc:.1%}" if out_n else "n/a"
        print(f"{name:<35} {in_str:>7} {in_n:>5} {out_str:>8} {out_n:>5}")

    # F41 detail for each condition
    print(f"\n{'=' * 90}")
    print("F41 DISCRIMINATION DETAIL")
    print(f"{'=' * 90}")

    for name, results in all_results.items():
        if results["f41_detail"]:
            f41_correct = sum(1 for d in results["f41_detail"] if d["correct"])
            f41_total = len(results["f41_detail"])
            print(f"\n{name}: {f41_correct}/{f41_total} F41 correct")
            f41_preds = Counter(d["pred"] for d in results["f41_detail"])
            for pred, count in f41_preds.most_common():
                print(f"  -> {pred}: {count}")

    # Confusion patterns
    print(f"\n{'=' * 90}")
    print("TOP CONFUSION PATTERNS")
    print(f"{'=' * 90}")

    for name, results in all_results.items():
        if results["confusion"]:
            print(f"\n{name}:")
            for pair, count in sorted(results["confusion"].items(), key=lambda x: -x[1])[:5]:
                print(f"  {pair}: {count}")

    # V1 comparison
    print(f"\n{'=' * 90}")
    print("COMPARISON WITH OLLAMA V1 BASELINE")
    print(f"{'=' * 90}")

    # Load actual V1 results for paired comparison
    v1_dir = Path("outputs/exp_50case_v1")
    v1_results = {}
    if v1_dir.exists():
        for mode_file in v1_dir.glob("*_predictions.json"):
            mode = mode_file.stem.replace("_predictions", "")
            with open(mode_file, encoding="utf-8") as f:
                v1_data = json.load(f)
            v1_correct = 0
            v1_total = 0
            for p in v1_data.get("predictions", []):
                cid = p.get("case_id", "")
                golds = gold_map.get(cid, [])
                if not golds:
                    continue
                pred = p.get("primary_diagnosis") or ""
                gold = golds[0]
                pp = parent_code(pred) if pred else ""
                gp = parent_code(gold)
                v1_total += 1
                if pp == gp:
                    v1_correct += 1
            if v1_total:
                v1_results[mode] = {"accuracy": v1_correct / v1_total, "n": v1_total}
    else:
        # Fallback to hardcoded numbers if V1 directory not found
        v1_results = {
            "debate": {"accuracy": 0.56, "n": 0},
            "hied": {"accuracy": 0.50, "n": 0},
            "single": {"accuracy": 0.50, "n": 0},
            "specialist": {"accuracy": 0.48, "n": 0},
        }

    print(f"\n{'Mode':<15} {'V1 (Ollama)':>12} {'V2 (vLLM)':>12} {'Delta':>8}")
    print("-" * 50)
    for mode in ["hied", "single", "psycot", "specialist", "debate"]:
        v2_key = f"{mode}_no_evidence"
        v2_acc = all_results.get(v2_key, {}).get("accuracy", 0)
        v1_acc = v1_results.get(mode, {}).get("accuracy", 0)
        delta = v2_acc - v1_acc if v1_acc else 0
        v1_str = f"{v1_acc:.1%}" if v1_acc else "n/a"
        v2_str = f"{v2_acc:.1%}" if v2_acc else "pending"
        delta_str = f"{delta:+.1%}" if v1_acc and v2_acc else ""
        print(f"{mode:<15} {v1_str:>12} {v2_str:>12} {delta_str:>8}")


def main():
    parser = argparse.ArgumentParser(description="Analyze vLLM sweep results")
    parser.add_argument("--sweep-dir", type=str, required=True)
    parser.add_argument("--live", action="store_true", help="Live monitoring mode")
    args = parser.parse_args()

    sweep_dir = Path(args.sweep_dir)
    if not sweep_dir.exists():
        # Try glob
        import glob
        matches = sorted(glob.glob(args.sweep_dir))
        if matches:
            sweep_dir = Path(matches[-1])
        else:
            print(f"No sweep directory found: {args.sweep_dir}")
            sys.exit(1)

    print_summary(sweep_dir)


if __name__ == "__main__":
    main()
