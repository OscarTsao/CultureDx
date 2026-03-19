#!/usr/bin/env python3
"""Analyze pilot experiment results and generate comparison tables.

Usage:
    uv run python scripts/analyze_results.py outputs/pilot_v4/pilot_report.json
    uv run python scripts/analyze_results.py outputs/pilot_v4/pilot_report.json --latex
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def load_report(path: str) -> dict:
    """Load pilot report JSON."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def print_mode_comparison(report: dict) -> None:
    """Print mode comparison table."""
    print("\n" + "=" * 80)
    print("MODE COMPARISON")
    print("=" * 80)
    header = f"{'Mode':<12} {'Top-1':>8} {'Top-3':>8} {'F1':>8} {'Time(s)':>10} {'s/case':>8} {'Dx':>5} {'Abs':>5}"
    print(header)
    print("-" * 80)
    for mode_name, ev in report.items():
        m = ev.get("metrics_parent_normalized", {})
        n = ev.get("n_cases", 0)
        t = ev.get("total_seconds", 0)
        dx = sum(1 for d in ev.get("case_details", []) if d.get("decision") == "diagnosis")
        ab = sum(1 for d in ev.get("case_details", []) if d.get("decision") == "abstain")
        print(
            f"{mode_name:<12} "
            f"{m.get('top1_accuracy', 0):>8.3f} "
            f"{m.get('top3_accuracy', 0):>8.3f} "
            f"{m.get('macro_f1', 0):>8.3f} "
            f"{t:>10.1f} "
            f"{t/n if n else 0:>8.1f} "
            f"{dx:>5} "
            f"{ab:>5}"
        )


def print_confusion_matrix(report: dict) -> None:
    """Print confusion matrix per mode."""
    for mode_name, ev in report.items():
        details = ev.get("case_details", [])
        if not details:
            continue

        print(f"\n{'=' * 60}")
        print(f"CONFUSION MATRIX: {mode_name}")
        print(f"{'=' * 60}")

        # Build confusion counts
        confusion = defaultdict(Counter)
        all_golds = set()
        all_preds = set()
        for d in details:
            gold = d.get("gold_parent", "?")
            pred = d.get("pred_parent", "?")
            confusion[gold][pred] += 1
            all_golds.add(gold)
            all_preds.add(pred)

        labels = sorted(all_golds | all_preds)
        # Header
        header = f"{'Gold\\Pred':<10}" + "".join(f"{l:>8}" for l in labels) + f"{'Total':>8}"
        print(header)
        print("-" * len(header))

        for gold in sorted(all_golds):
            row = f"{gold:<10}"
            total = 0
            for pred in labels:
                c = confusion[gold][pred]
                total += c
                row += f"{c:>8}"
            row += f"{total:>8}"
            print(row)


def print_error_analysis(report: dict) -> None:
    """Print per-case error analysis."""
    for mode_name, ev in report.items():
        details = ev.get("case_details", [])
        errors = [d for d in details if not d.get("match_parent", False)]
        if not errors:
            print(f"\n{mode_name}: No errors!")
            continue

        correct = sum(1 for d in details if d.get("match_parent", False))
        total = len(details)
        print(f"\n{'=' * 70}")
        print(f"ERROR ANALYSIS: {mode_name} ({correct}/{total} correct, {len(errors)} errors)")
        print(f"{'=' * 70}")

        for d in errors:
            print(
                f"  {d['case_id']:15s} "
                f"gold={d.get('gold_parent', '?'):6s} "
                f"pred={d.get('pred_parent', '?'):8s} "
                f"conf={d.get('confidence', 0):.3f} "
                f"decision={d.get('decision', '?')}"
            )

        # Error pattern summary
        error_patterns = Counter()
        for d in errors:
            pattern = f"{d.get('gold_parent', '?')} -> {d.get('pred_parent', '?')}"
            error_patterns[pattern] += 1
        print(f"\n  Error patterns:")
        for pattern, count in error_patterns.most_common():
            print(f"    {pattern}: {count}")


def print_latex_table(report: dict) -> None:
    """Print LaTeX-formatted comparison table."""
    print("\n% LaTeX table")
    print("\\begin{table}[h]")
    print("\\centering")
    print("\\caption{Pilot experiment results on MDD-5k (n=20)}")
    print("\\begin{tabular}{lcccc}")
    print("\\toprule")
    print("Mode & Top-1 Acc & Top-3 Acc & Macro F1 & Time (s/case) \\\\")
    print("\\midrule")
    for mode_name, ev in report.items():
        m = ev.get("metrics_parent_normalized", {})
        n = ev.get("n_cases", 0)
        t = ev.get("total_seconds", 0)
        print(
            f"{mode_name} & "
            f"{m.get('top1_accuracy', 0):.3f} & "
            f"{m.get('top3_accuracy', 0):.3f} & "
            f"{m.get('macro_f1', 0):.3f} & "
            f"{t/n if n else 0:.1f} \\\\"
        )
    print("\\bottomrule")
    print("\\end{tabular}")
    print("\\end{table}")


def main():
    parser = argparse.ArgumentParser(description="Analyze pilot experiment results")
    parser.add_argument("report_path", help="Path to pilot_report.json")
    parser.add_argument("--latex", action="store_true", help="Generate LaTeX table")
    args = parser.parse_args()

    report = load_report(args.report_path)

    print_mode_comparison(report)
    print_confusion_matrix(report)
    print_error_analysis(report)

    if args.latex:
        print_latex_table(report)

    print("\nAnalysis complete.")


if __name__ == "__main__":
    main()
