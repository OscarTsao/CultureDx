#!/usr/bin/env python3
"""Criterion checker false-negative analysis.

Analyzes checker outputs against gold labels to identify which (disorder, criterion)
pairs have the highest false-negative rates. A "false negative" here means:
  - The gold label includes disorder D (at parent-code level)
  - The checker evaluated D's criteria
  - A specific criterion was marked "not_met" or "insufficient"

This helps identify which criteria the checker systematically misses,
guiding prompt improvements (Track 3.2).

Usage:
    uv run python scripts/analyze_checker_fn.py \
        --pred outputs/sweeps/v10_mdd5k_20260320_233729/hied_no_evidence/predictions.json \
        --cases outputs/sweeps/v10_mdd5k_20260320_233729/case_list.json \
        --dataset mdd5k

    # Combined analysis across both datasets:
    uv run python scripts/analyze_checker_fn.py \
        --pred outputs/sweeps/v10_mdd5k_20260320_233729/hied_no_evidence/predictions.json \
               outputs/sweeps/v10_lingxidiag_20260320_222603/hied_no_evidence/predictions.json \
        --cases outputs/sweeps/v10_mdd5k_20260320_233729/case_list.json \
                outputs/sweeps/v10_lingxidiag_20260320_222603/case_list.json \
        --dataset mdd5k lingxidiag
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def parent_code(code: str | None) -> str | None:
    """F32.1 -> F32, F41.1 -> F41, etc."""
    return code.split(".", 1)[0] if code else None


def load_gold_map(case_list_path: str) -> dict[str, list[str]]:
    """Load case_list.json -> {case_id: [gold_codes]}."""
    with open(case_list_path, encoding="utf-8") as f:
        data = json.load(f)
    return {c["case_id"]: c["diagnoses"] for c in data["cases"]}


def load_predictions(pred_path: str) -> list[dict]:
    """Load predictions.json -> list of prediction dicts."""
    with open(pred_path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "predictions" in data:
        return data["predictions"]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unknown format: {pred_path}")


def analyze_fn(
    predictions: list[dict],
    gold_map: dict[str, list[str]],
    dataset_name: str,
) -> dict:
    """Analyze false negatives per (disorder, criterion_id).

    For each prediction where the gold includes disorder D:
    - Find the checker output for D (if triage selected it)
    - For each criterion: track met/not_met/insufficient counts
    - A "false negative" = criterion marked not_met when gold says D is present

    Also tracks:
    - Triage misses: gold D but triage didn't select D for checking
    - Logic engine misses: checker ran but didn't meet threshold
    """
    # Per-(disorder, criterion) stats
    criterion_stats: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "met": 0, "not_met": 0, "insufficient": 0, "partial": 0,
            "total_evaluated": 0,
            "avg_confidence_when_met": [],
            "avg_confidence_when_not_met": [],
            "evidence_samples_not_met": [],
        }
    )

    # Per-disorder stats
    disorder_stats: dict[str, dict] = defaultdict(
        lambda: {
            "gold_count": 0,          # how many cases have this as gold
            "triage_selected": 0,      # how many times triage picked this
            "checker_ran": 0,          # how many times checker actually evaluated
            "threshold_met": 0,        # how many times logic engine confirmed
            "triage_miss_cases": [],   # case_ids where triage missed gold
        }
    )

    # Track overall error categories
    error_categories = {
        "triage_miss": 0,           # gold D but triage didn't select
        "checker_fn": 0,            # triage selected, checker criteria FN
        "threshold_miss": 0,        # criteria partially met but below threshold
        "correct_detection": 0,     # gold D and checker confirmed
        "total_gold_instances": 0,
    }

    for pred in predictions:
        case_id = pred["case_id"]
        if case_id not in gold_map:
            continue

        gold_codes = gold_map[case_id]
        gold_parents = {parent_code(g) for g in gold_codes if g}

        # Build checker output index: parent_code -> CheckerOutput
        checker_index: dict[str, dict] = {}
        for cr in pred.get("criteria_results", []):
            p = parent_code(cr["disorder"])
            checker_index[p] = cr

        # Primary + comorbid as predicted set
        pred_primary = parent_code(pred.get("primary_diagnosis"))
        pred_comorbid = [parent_code(c) for c in pred.get("comorbid_diagnoses", [])]
        pred_set = {c for c in [pred_primary] + pred_comorbid if c}

        for gold_p in gold_parents:
            disorder_stats[gold_p]["gold_count"] += 1
            error_categories["total_gold_instances"] += 1

            if gold_p not in checker_index:
                # Triage missed this disorder entirely
                disorder_stats[gold_p]["triage_miss_cases"].append(case_id)
                error_categories["triage_miss"] += 1
                continue

            disorder_stats[gold_p]["triage_selected"] += 1
            disorder_stats[gold_p]["checker_ran"] += 1
            co = checker_index[gold_p]

            if gold_p in pred_set:
                disorder_stats[gold_p]["threshold_met"] += 1
                error_categories["correct_detection"] += 1
            else:
                # Checker ran but didn't make it to final diagnosis
                error_categories["threshold_miss"] += 1

            # Analyze each criterion
            for crit in co.get("criteria", []):
                cid = crit["criterion_id"]
                status = crit["status"]
                conf = crit.get("confidence", 0.0)
                evidence = crit.get("evidence", "")
                key = (gold_p, cid)

                stats = criterion_stats[key]
                stats["total_evaluated"] += 1

                if status == "met":
                    stats["met"] += 1
                    stats["avg_confidence_when_met"].append(conf)
                elif status == "not_met":
                    stats["not_met"] += 1
                    stats["avg_confidence_when_not_met"].append(conf)
                    if evidence and len(stats["evidence_samples_not_met"]) < 5:
                        stats["evidence_samples_not_met"].append({
                            "case_id": case_id,
                            "evidence": evidence[:200],
                            "confidence": conf,
                        })
                elif status == "insufficient":
                    stats["insufficient"] += 1
                    stats["avg_confidence_when_not_met"].append(conf)
                elif status == "partial":
                    stats["partial"] += 1
                    stats["avg_confidence_when_met"].append(conf)

    return {
        "dataset": dataset_name,
        "criterion_stats": criterion_stats,
        "disorder_stats": disorder_stats,
        "error_categories": error_categories,
    }


def print_report(results: list[dict], output_path: str | None = None) -> None:
    """Print and optionally save the FN analysis report."""
    # Merge criterion_stats across datasets
    merged_crit: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "met": 0, "not_met": 0, "insufficient": 0, "partial": 0,
            "total_evaluated": 0,
            "avg_confidence_when_met": [],
            "avg_confidence_when_not_met": [],
            "evidence_samples_not_met": [],
        }
    )
    merged_disorder: dict[str, dict] = defaultdict(
        lambda: {
            "gold_count": 0, "triage_selected": 0, "checker_ran": 0,
            "threshold_met": 0, "triage_miss_cases": [],
        }
    )
    merged_errors = Counter()

    for r in results:
        for key, stats in r["criterion_stats"].items():
            m = merged_crit[key]
            for k in ("met", "not_met", "insufficient", "partial", "total_evaluated"):
                m[k] += stats[k]
            m["avg_confidence_when_met"].extend(stats["avg_confidence_when_met"])
            m["avg_confidence_when_not_met"].extend(stats["avg_confidence_when_not_met"])
            m["evidence_samples_not_met"].extend(stats["evidence_samples_not_met"])

        for code, stats in r["disorder_stats"].items():
            m = merged_disorder[code]
            for k in ("gold_count", "triage_selected", "checker_ran", "threshold_met"):
                m[k] += stats[k]
            m["triage_miss_cases"].extend(stats["triage_miss_cases"])

        merged_errors.update(r["error_categories"])

    datasets = ", ".join(r["dataset"] for r in results)
    lines = []

    def pr(s=""):
        print(s)
        lines.append(s)

    pr(f"{'='*80}")
    pr(f"CRITERION CHECKER FALSE-NEGATIVE ANALYSIS")
    pr(f"Datasets: {datasets}")
    pr(f"{'='*80}")

    # 1. Error category breakdown
    pr(f"\n## Error Category Breakdown")
    total = merged_errors["total_gold_instances"]
    pr(f"  Total gold disorder instances: {total}")
    pr(f"  Correct detection:   {merged_errors['correct_detection']:4d} ({merged_errors['correct_detection']/total*100:5.1f}%)")
    pr(f"  Triage miss:         {merged_errors['triage_miss']:4d} ({merged_errors['triage_miss']/total*100:5.1f}%)")
    pr(f"  Threshold miss:      {merged_errors['threshold_miss']:4d} ({merged_errors['threshold_miss']/total*100:5.1f}%)")
    pr(f"  Checker criterion FN:{merged_errors['checker_fn']:4d} ({merged_errors['checker_fn']/total*100:5.1f}%)")

    # 2. Per-disorder summary
    pr(f"\n## Per-Disorder Summary")
    pr(f"  {'Disorder':<10} {'Gold':>5} {'Triage':>7} {'Checked':>8} {'Confirmed':>10} {'Triage%':>8} {'Confirm%':>9}")
    pr(f"  {'-'*10} {'-'*5} {'-'*7} {'-'*8} {'-'*10} {'-'*8} {'-'*9}")
    for code in sorted(merged_disorder, key=lambda c: -merged_disorder[c]["gold_count"]):
        d = merged_disorder[code]
        triage_pct = d["triage_selected"] / d["gold_count"] * 100 if d["gold_count"] > 0 else 0
        confirm_pct = d["threshold_met"] / d["gold_count"] * 100 if d["gold_count"] > 0 else 0
        pr(f"  {code:<10} {d['gold_count']:>5} {d['triage_selected']:>7} {d['checker_ran']:>8} {d['threshold_met']:>10} {triage_pct:>7.1f}% {confirm_pct:>8.1f}%")

    # 3. Per-criterion FN rates (sorted by not_met rate)
    pr(f"\n## Per-Criterion FN Rates (sorted by not_met rate, min 5 evaluations)")
    pr(f"  {'Disorder':<8} {'Crit':<5} {'Eval':>5} {'Met':>5} {'NotMet':>7} {'Insuf':>6} {'FN%':>7} {'AvgConf_Met':>12} {'AvgConf_NM':>11}")
    pr(f"  {'-'*8} {'-'*5} {'-'*5} {'-'*5} {'-'*7} {'-'*6} {'-'*7} {'-'*12} {'-'*11}")

    # Sort by FN rate (not_met + insufficient) / total
    sorted_criteria = []
    for (disorder, crit_id), stats in merged_crit.items():
        if stats["total_evaluated"] < 5:
            continue
        fn_count = stats["not_met"] + stats["insufficient"]
        fn_rate = fn_count / stats["total_evaluated"]
        avg_conf_met = (
            sum(stats["avg_confidence_when_met"]) / len(stats["avg_confidence_when_met"])
            if stats["avg_confidence_when_met"] else 0.0
        )
        avg_conf_nm = (
            sum(stats["avg_confidence_when_not_met"]) / len(stats["avg_confidence_when_not_met"])
            if stats["avg_confidence_when_not_met"] else 0.0
        )
        sorted_criteria.append((disorder, crit_id, stats, fn_rate, avg_conf_met, avg_conf_nm))

    sorted_criteria.sort(key=lambda x: -x[3])

    for disorder, crit_id, stats, fn_rate, avg_conf_met, avg_conf_nm in sorted_criteria:
        fn_count = stats["not_met"] + stats["insufficient"]
        pr(
            f"  {disorder:<8} {crit_id:<5} {stats['total_evaluated']:>5} "
            f"{stats['met']:>5} {stats['not_met']:>7} {stats['insufficient']:>6} "
            f"{fn_rate*100:>6.1f}% {avg_conf_met:>11.3f} {avg_conf_nm:>10.3f}"
        )

    # 4. Top-10 worst criteria with evidence samples
    pr(f"\n## Top-10 Worst Criteria (highest FN rate, min 5 evaluations)")
    for i, (disorder, crit_id, stats, fn_rate, _, _) in enumerate(sorted_criteria[:10]):
        pr(f"\n  [{i+1}] {disorder} / {crit_id}: FN rate = {fn_rate*100:.1f}% "
           f"({stats['not_met']}+{stats['insufficient']} / {stats['total_evaluated']})")
        samples = stats["evidence_samples_not_met"][:3]
        for s in samples:
            pr(f"      Case {s['case_id']} (conf={s['confidence']:.2f}): {s['evidence'][:120]}")

    # 5. Triage miss analysis
    pr(f"\n## Triage Miss Analysis")
    for code in sorted(merged_disorder, key=lambda c: -len(merged_disorder[c]["triage_miss_cases"])):
        d = merged_disorder[code]
        if not d["triage_miss_cases"]:
            continue
        n_miss = len(d["triage_miss_cases"])
        pr(f"  {code}: {n_miss} triage misses / {d['gold_count']} gold "
           f"({n_miss/d['gold_count']*100:.1f}%)")
        pr(f"    Cases: {d['triage_miss_cases'][:10]}")

    # 6. Somatization-related criteria analysis
    # These are the criteria most likely affected by Chinese somatization
    somatic_criteria = {
        ("F32", "C4"),  # sleep disturbance
        ("F32", "C5"),  # appetite/weight change
        ("F32", "C6"),  # fatigue/energy loss
        ("F33", "C4"),
        ("F33", "C5"),
        ("F33", "C6"),
        ("F41", "B2"),  # autonomic arousal (palpitations, sweating, trembling)
        ("F41", "B3"),  # chest/abdominal symptoms
        ("F45", "A"),   # somatic symptoms
    }
    pr(f"\n## Somatization-Related Criteria")
    pr(f"  (Criteria most likely to involve somatic expressions)")
    for disorder, crit_id, stats, fn_rate, avg_conf_met, avg_conf_nm in sorted_criteria:
        if (disorder, crit_id) in somatic_criteria:
            pr(f"  {disorder}/{crit_id}: FN={fn_rate*100:.1f}% "
               f"(met={stats['met']}, not_met={stats['not_met']}, insuf={stats['insufficient']})")

    # Save JSON report
    if output_path:
        report = {
            "datasets": datasets,
            "error_categories": dict(merged_errors),
            "disorder_summary": {
                code: {k: v for k, v in stats.items() if k != "triage_miss_cases"}
                for code, stats in merged_disorder.items()
            },
            "criterion_fn_rates": [
                {
                    "disorder": d,
                    "criterion_id": c,
                    "total_evaluated": s["total_evaluated"],
                    "met": s["met"],
                    "not_met": s["not_met"],
                    "insufficient": s["insufficient"],
                    "fn_rate": fn,
                    "avg_confidence_met": cm,
                    "avg_confidence_not_met": cnm,
                    "evidence_samples": s["evidence_samples_not_met"][:3],
                }
                for d, c, s, fn, cm, cnm in sorted_criteria
            ],
            "triage_misses": {
                code: {
                    "count": len(stats["triage_miss_cases"]),
                    "gold_count": stats["gold_count"],
                    "rate": len(stats["triage_miss_cases"]) / stats["gold_count"]
                    if stats["gold_count"] > 0 else 0,
                    "cases": stats["triage_miss_cases"][:20],
                }
                for code, stats in merged_disorder.items()
                if stats["triage_miss_cases"]
            },
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nSaved JSON report to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Criterion checker FN analysis")
    parser.add_argument(
        "--pred", nargs="+", required=True,
        help="Path(s) to predictions.json",
    )
    parser.add_argument(
        "--cases", nargs="+", required=True,
        help="Path(s) to case_list.json (same order as --pred)",
    )
    parser.add_argument(
        "--dataset", nargs="+", required=True,
        help="Dataset name(s) (same order as --pred)",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output path for JSON report",
    )
    args = parser.parse_args()

    if len(args.pred) != len(args.cases) or len(args.pred) != len(args.dataset):
        parser.error("--pred, --cases, --dataset must have the same number of arguments")

    results = []
    for pred_path, cases_path, ds_name in zip(args.pred, args.cases, args.dataset):
        print(f"Loading {ds_name}: {pred_path}")
        preds = load_predictions(pred_path)
        gold_map = load_gold_map(cases_path)
        print(f"  {len(preds)} predictions, {len(gold_map)} gold labels")
        r = analyze_fn(preds, gold_map, ds_name)
        results.append(r)

    print_report(results, args.output)


if __name__ == "__main__":
    main()
