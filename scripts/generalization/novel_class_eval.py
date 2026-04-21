"""Evaluate MDD-5k novel-class recall before and after ontology expansion."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BASELINE = ROOT / "results/external/mdd5k_t1_seed42/predictions.jsonl"
DEFAULT_EXPANDED = ROOT / "results/generalization/mdd5k_novel_expanded/predictions.jsonl"
DEFAULT_OUTPUT = ROOT / "results/generalization/novel_class_analysis.json"

NOVEL_CLASSES = ("G47", "F50", "F34", "F30", "F90")
EXISTING_SCOPE_PARENTS = (
    "F20",
    "F31",
    "F32",
    "F39",
    "F41",
    "F42",
    "F43",
    "F45",
    "F51",
    "F98",
    "Z71",
)


def parent(code: str | None) -> str | None:
    if not code:
        return None
    return str(code).strip().upper().split(".")[0] or None


def load_predictions(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            case_id = str(record["case_id"])
            if case_id in records:
                raise ValueError(f"Duplicate case_id {case_id} in {path}")
            records[case_id] = record
    if not records:
        raise ValueError(f"No predictions found in {path}")
    return records


def gold_parents(record: dict[str, Any]) -> set[str]:
    return {p for p in (parent(code) for code in (record.get("gold_diagnoses") or [])) if p}


def top1_parent(record: dict[str, Any]) -> str | None:
    return parent(record.get("primary_diagnosis"))


def compute_recall(case_ids: list[str], records: dict[str, dict[str, Any]], code: str) -> dict[str, Any]:
    total = len(case_ids)
    hits = sum(1 for case_id in case_ids if top1_parent(records[case_id]) == code)
    recall = hits / total if total else 0.0
    return {
        "cases": total,
        "hits": hits,
        "recall": recall,
    }


def compare_gold_labels(
    baseline: dict[str, dict[str, Any]],
    expanded: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    baseline_ids = set(baseline)
    expanded_ids = set(expanded)
    common_ids = sorted(baseline_ids & expanded_ids)

    mismatched_gold: list[str] = []
    for case_id in common_ids:
        if gold_parents(baseline[case_id]) != gold_parents(expanded[case_id]):
            mismatched_gold.append(case_id)

    return {
        "baseline_only_case_ids": sorted(baseline_ids - expanded_ids),
        "expanded_only_case_ids": sorted(expanded_ids - baseline_ids),
        "gold_mismatch_case_ids": mismatched_gold,
        "common_case_count": len(common_ids),
    }


def build_analysis(
    baseline: dict[str, dict[str, Any]],
    expanded: dict[str, dict[str, Any]],
    baseline_path: Path,
    expanded_path: Path,
) -> dict[str, Any]:
    gold_check = compare_gold_labels(baseline, expanded)
    common_ids = sorted(set(baseline) & set(expanded))
    if not common_ids:
        raise ValueError("No overlapping case IDs between baseline and expanded runs")

    if gold_check["gold_mismatch_case_ids"]:
        raise ValueError(
            "Gold labels differ between baseline and expanded runs for "
            f"{len(gold_check['gold_mismatch_case_ids'])} cases"
        )

    novel_results: dict[str, Any] = {}
    gold_by_case = {case_id: gold_parents(expanded[case_id]) for case_id in common_ids}
    novel_set = set(NOVEL_CLASSES)
    existing_set = set(EXISTING_SCOPE_PARENTS)

    for code in NOVEL_CLASSES:
        positive_case_ids = [case_id for case_id, golds in gold_by_case.items() if code in golds]
        before = compute_recall(positive_case_ids, baseline, code)
        after = compute_recall(positive_case_ids, expanded, code)
        novel_results[code] = {
            "gold_cases": len(positive_case_ids),
            "before": before,
            "after": after,
            "delta_recall": after["recall"] - before["recall"],
        }

    existing_case_ids = [
        case_id
        for case_id, golds in gold_by_case.items()
        if golds
        and golds.issubset(existing_set)
        and golds.isdisjoint(novel_set)
    ]
    before_correct = sum(
        1 for case_id in existing_case_ids if top1_parent(baseline[case_id]) in gold_by_case[case_id]
    )
    after_correct = sum(
        1 for case_id in existing_case_ids if top1_parent(expanded[case_id]) in gold_by_case[case_id]
    )
    denom = len(existing_case_ids)
    before_acc = before_correct / denom if denom else 0.0
    after_acc = after_correct / denom if denom else 0.0

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline_predictions": str(baseline_path.relative_to(ROOT)),
        "expanded_predictions": str(expanded_path.relative_to(ROOT)),
        "novel_classes": novel_results,
        "existing_scope_top1": {
            "eligible_case_count": denom,
            "before_accuracy": before_acc,
            "after_accuracy": after_acc,
            "before_correct": before_correct,
            "after_correct": after_correct,
            "delta_accuracy": after_acc - before_acc,
            "not_regressed": after_acc >= before_acc,
        },
        "case_alignment": gold_check,
    }


def print_summary(analysis: dict[str, Any]) -> None:
    print("Novel-class recall (Top-1)")
    print("class\tgold_n\tbefore\tafter\tdelta")
    for code in NOVEL_CLASSES:
        row = analysis["novel_classes"][code]
        print(
            f"{code}\t{row['gold_cases']}\t"
            f"{row['before']['recall']:.3f} ({row['before']['hits']}/{row['before']['cases']})\t"
            f"{row['after']['recall']:.3f} ({row['after']['hits']}/{row['after']['cases']})\t"
            f"{row['delta_recall']:+.3f}"
        )

    existing = analysis["existing_scope_top1"]
    print()
    print("Existing-scope Top-1")
    print(
        f"eligible={existing['eligible_case_count']} "
        f"before={existing['before_accuracy']:.3f} ({existing['before_correct']}/{existing['eligible_case_count']}) "
        f"after={existing['after_accuracy']:.3f} ({existing['after_correct']}/{existing['eligible_case_count']}) "
        f"delta={existing['delta_accuracy']:+.3f} "
        f"not_regressed={existing['not_regressed']}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--expanded", type=Path, default=DEFAULT_EXPANDED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    baseline = load_predictions(args.baseline)
    expanded = load_predictions(args.expanded)
    analysis = build_analysis(baseline, expanded, args.baseline, args.expanded)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(analysis, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print_summary(analysis)
    print(f"\nSaved analysis to {args.output}")


if __name__ == "__main__":
    main()
