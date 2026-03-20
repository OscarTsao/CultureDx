#!/usr/bin/env python3
"""Analyze evidence ablation results across sweeps.

Compare: no-evidence vs BGE-M3 evidence vs BGE-M3 no-somatization vs mock evidence.
Focus on F41 discrimination and somatization boost effect.

Usage:
    uv run python scripts/analyze_evidence_ablation.py \
        --v3-dir outputs/sweeps/vllm_v3_fixes_evidence_20260320_034418 \
        --bgem3-dir outputs/sweeps/vllm_v3_bgem3_*
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def parent_code(code: str) -> str:
    """Normalize to parent code (F32.1 -> F32, F41.1 -> F41)."""
    if not code:
        return ""
    return code.split(".")[0] if "." in code else code


def load_predictions(pred_path: Path) -> list[dict]:
    """Load predictions from a condition directory."""
    with open(pred_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("predictions", [])


def load_gold_map(sweep_dir: Path) -> dict[str, str]:
    """Load gold labels from case_list.json."""
    case_list_path = sweep_dir / "case_list.json"
    if not case_list_path.exists():
        return {}
    with open(case_list_path, encoding="utf-8") as f:
        case_list = json.load(f)
    return {c["case_id"]: c["diagnoses"][0] for c in case_list["cases"]}


def analyze_condition(preds: list[dict], gold_map: dict[str, str]) -> dict:
    """Compute detailed metrics for a single condition."""
    results = {
        "n_cases": len(preds),
        "correct": 0,
        "abstained": 0,
        "per_disorder": defaultdict(lambda: {"total": 0, "correct": 0}),
        "confusion": Counter(),
        "case_results": {},  # case_id -> {gold, pred, correct, conf}
        "confs_correct": [],
        "confs_wrong": [],
    }

    for p in preds:
        cid = p.get("case_id", "")
        gold = parent_code(gold_map.get(cid, ""))
        pred = parent_code(p.get("primary_diagnosis") or "")
        conf = p.get("confidence", 0.0)
        comorbid = [parent_code(c) for c in (p.get("comorbid_diagnoses") or [])]

        if not gold:
            continue

        if not pred:
            results["abstained"] += 1
            results["case_results"][cid] = {
                "gold": gold, "pred": "", "correct": False,
                "conf": conf, "comorbid": comorbid,
            }
            continue

        correct = pred == gold
        results["per_disorder"][gold]["total"] += 1
        if correct:
            results["correct"] += 1
            results["per_disorder"][gold]["correct"] += 1
            results["confs_correct"].append(conf)
        else:
            results["confusion"][f"{gold}->{pred}"] += 1
            results["confs_wrong"].append(conf)

        results["case_results"][cid] = {
            "gold": gold, "pred": pred, "correct": correct,
            "conf": conf, "comorbid": comorbid,
        }

    diagnosed = results["n_cases"] - results["abstained"]
    results["accuracy"] = results["correct"] / diagnosed if diagnosed else 0
    results["abstain_rate"] = results["abstained"] / results["n_cases"] if results["n_cases"] else 0

    return results


def print_comparison(conditions: dict[str, dict]) -> None:
    """Print head-to-head comparison across conditions."""
    names = list(conditions.keys())
    if not names:
        print("No conditions to compare.")
        return

    # Overview table
    print("=" * 90)
    print("EVIDENCE ABLATION COMPARISON")
    print("=" * 90)
    print(f"\n{'Condition':<35} {'Acc':>7} {'n':>4} {'Abst':>5} {'F32':>8} {'F41':>8} {'ConfGap':>8}")
    print("-" * 80)

    for name, res in conditions.items():
        f32 = res["per_disorder"].get("F32", {"total": 0, "correct": 0})
        f41 = res["per_disorder"].get("F41", {"total": 0, "correct": 0})
        f32_str = f"{f32['correct']}/{f32['total']}" if f32["total"] else "n/a"
        f41_str = f"{f41['correct']}/{f41['total']}" if f41["total"] else "n/a"
        avg_c = sum(res["confs_correct"]) / len(res["confs_correct"]) if res["confs_correct"] else 0
        avg_w = sum(res["confs_wrong"]) / len(res["confs_wrong"]) if res["confs_wrong"] else 0
        gap = avg_c - avg_w
        print(f"{name:<35} {res['accuracy']:>6.1%} {res['n_cases']:>4} "
              f"{res['abstained']:>5} {f32_str:>8} {f41_str:>8} {gap:>+7.3f}")

    # Head-to-head flip analysis
    if len(names) >= 2:
        baseline_name = [n for n in names if "no_evidence" in n]
        if baseline_name:
            baseline_name = baseline_name[0]
        else:
            baseline_name = names[0]

        baseline = conditions[baseline_name]

        for name, res in conditions.items():
            if name == baseline_name:
                continue

            print(f"\n{'=' * 70}")
            print(f"FLIPS: {baseline_name} -> {name}")
            print(f"{'=' * 70}")

            better = worse = same_correct = same_wrong = 0
            flip_details = []

            for cid in baseline["case_results"]:
                if cid not in res["case_results"]:
                    continue
                b = baseline["case_results"][cid]
                c = res["case_results"][cid]

                if b["correct"] and c["correct"]:
                    same_correct += 1
                elif not b["correct"] and not c["correct"]:
                    same_wrong += 1
                elif not b["correct"] and c["correct"]:
                    better += 1
                    flip_details.append(
                        f"  FIXED: {cid} gold={b['gold']} "
                        f"base={b['pred'] or 'abs'} -> new={c['pred']} "
                        f"conf {b['conf']:.3f}->{c['conf']:.3f}"
                    )
                else:
                    worse += 1
                    flip_details.append(
                        f"  BROKE: {cid} gold={b['gold']} "
                        f"base={b['pred'] or 'abs'} -> new={c['pred'] or 'abs'} "
                        f"conf {b['conf']:.3f}->{c['conf']:.3f}"
                    )

            total = better + worse + same_correct + same_wrong
            print(f"  Same correct: {same_correct}  Same wrong: {same_wrong}")
            print(f"  FIXED: {better}  BROKE: {worse}  Net: {better - worse:+d}")
            for d in sorted(flip_details):
                print(d)

    # F41 detailed comparison
    print(f"\n{'=' * 70}")
    print("F41 DISCRIMINATION DETAIL")
    print(f"{'=' * 70}")

    # Get all F41 case IDs
    all_case_results = {}
    for name, res in conditions.items():
        all_case_results[name] = res["case_results"]

    f41_cases = set()
    for name, cr in all_case_results.items():
        for cid, info in cr.items():
            if info["gold"] == "F41":
                f41_cases.add(cid)

    if f41_cases:
        header = f"{'Case':<16} {'Gold':<6}"
        for name in names:
            short = name.replace("hied_", "").replace("_evidence", "ev").replace("_no_", "no_")
            header += f" {short:>12}"
        print(header)
        print("-" * (22 + 13 * len(names)))

        for cid in sorted(f41_cases):
            row = f"{cid:<16} {'F41':<6}"
            for name in names:
                cr = all_case_results.get(name, {}).get(cid)
                if cr:
                    mark = "OK" if cr["correct"] else (cr["pred"] or "abs")
                    row += f" {mark:>12}"
                else:
                    row += f" {'---':>12}"
            print(row)

    # Confusion patterns comparison
    print(f"\n{'=' * 70}")
    print("CONFUSION PATTERNS")
    print(f"{'=' * 70}")

    for name, res in conditions.items():
        if res["confusion"]:
            print(f"\n{name}:")
            for pair, count in res["confusion"].most_common(5):
                print(f"  {pair}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Evidence ablation analysis")
    parser.add_argument("--v3-dir", type=str, help="V3 mock sweep directory")
    parser.add_argument("--bgem3-dir", type=str, help="BGE-M3 sweep directory (glob ok)")
    parser.add_argument("--dirs", type=str, nargs="+", help="Multiple sweep dirs")
    args = parser.parse_args()

    # Collect all condition directories
    all_conditions: dict[str, list[dict]] = {}
    gold_map: dict[str, str] = {}

    sweep_dirs = []
    if args.v3_dir:
        sweep_dirs.append(Path(args.v3_dir))
    if args.bgem3_dir:
        matches = sorted(glob.glob(args.bgem3_dir))
        if matches:
            sweep_dirs.append(Path(matches[-1]))
    if args.dirs:
        for d in args.dirs:
            matches = sorted(glob.glob(d))
            for m in matches:
                sweep_dirs.append(Path(m))

    if not sweep_dirs:
        print("No sweep directories specified.")
        sys.exit(1)

    for sweep_dir in sweep_dirs:
        if not sweep_dir.exists():
            print(f"Warning: {sweep_dir} does not exist, skipping")
            continue

        # Load gold labels
        gm = load_gold_map(sweep_dir)
        if gm:
            gold_map.update(gm)

        # Load conditions
        for cond_dir in sorted(sweep_dir.iterdir()):
            if not cond_dir.is_dir():
                continue
            pred_file = cond_dir / "predictions.json"
            if not pred_file.exists():
                continue
            preds = load_predictions(pred_file)
            all_conditions[cond_dir.name] = preds

    if not all_conditions:
        print("No conditions found.")
        sys.exit(1)

    # Analyze all conditions
    analyzed = {}
    for name, preds in all_conditions.items():
        analyzed[name] = analyze_condition(preds, gold_map)

    print_comparison(analyzed)


if __name__ == "__main__":
    main()
