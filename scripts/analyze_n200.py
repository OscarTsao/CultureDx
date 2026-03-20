#!/usr/bin/env python3
"""N=200 3-mode statistical analysis with McNemar's test and bootstrap CI."""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
import math

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def parent_code(code):
    if code is None or code == "None":
        return "abstain"
    return code.split(".")[0]


def load_sweep(sweep_dir):
    """Load all conditions from a sweep directory."""
    sweep_dir = Path(sweep_dir)
    conditions = {}
    for subdir in sorted(sweep_dir.iterdir()):
        if not subdir.is_dir():
            continue
        pred_path = subdir / "predictions.json"
        if pred_path.exists():
            with open(pred_path, encoding="utf-8") as f:
                data = json.load(f)
            conditions[subdir.name] = data
    return conditions


def compute_metrics(predictions, gold_map):
    """Compute comprehensive metrics."""
    correct = 0
    diagnosed = 0
    total = len(predictions)
    per_disorder = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "total": 0})

    for p in predictions:
        case_id = p["case_id"]
        gold = gold_map.get(case_id, [])
        gold_parents = [g.split(".")[0] for g in gold]
        pred = p.get("primary_diagnosis")
        decision = p.get("decision", "diagnosis")

        for gp in gold_parents:
            per_disorder[gp]["total"] += 1

        if decision == "abstain" or pred is None:
            for gp in gold_parents:
                per_disorder[gp]["fn"] += 1
            continue

        diagnosed += 1
        pred_parent = parent_code(pred)

        if pred_parent in gold_parents:
            correct += 1
            per_disorder[pred_parent]["tp"] += 1
        else:
            per_disorder[pred_parent]["fp"] += 1
            for gp in gold_parents:
                per_disorder[gp]["fn"] += 1

    overall_acc = correct / total if total > 0 else 0
    diag_acc = correct / diagnosed if diagnosed > 0 else 0
    abstain_count = total - diagnosed

    # Macro F1
    f1_scores = []
    for disorder, counts in per_disorder.items():
        tp = counts["tp"]
        fp = counts["fp"]
        fn = counts["fn"]
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
        f1_scores.append(f1)

    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0

    return {
        "overall_acc": overall_acc,
        "diag_acc": diag_acc,
        "macro_f1": macro_f1,
        "correct": correct,
        "total": total,
        "diagnosed": diagnosed,
        "abstain": abstain_count,
        "per_disorder": dict(per_disorder),
    }


def mcnemar_test(preds_a, preds_b, gold_map):
    """McNemar's test for paired comparison."""
    a_right_b_wrong = 0
    a_wrong_b_right = 0

    for pa, pb in zip(preds_a, preds_b):
        assert pa["case_id"] == pb["case_id"]
        case_id = pa["case_id"]
        gold = gold_map.get(case_id, [])
        gold_parents = [g.split(".")[0] for g in gold]

        pred_a = parent_code(pa.get("primary_diagnosis"))
        pred_b = parent_code(pb.get("primary_diagnosis"))
        dec_a = pa.get("decision", "diagnosis")
        dec_b = pb.get("decision", "diagnosis")

        a_ok = pred_a in gold_parents and dec_a != "abstain"
        b_ok = pred_b in gold_parents and dec_b != "abstain"

        if a_ok and not b_ok:
            a_right_b_wrong += 1
        elif b_ok and not a_ok:
            a_wrong_b_right += 1

    # McNemar's test statistic (with continuity correction)
    n = a_right_b_wrong + a_wrong_b_right
    if n == 0:
        return {"chi2": 0, "p_value": 1.0, "a_right_b_wrong": 0, "a_wrong_b_right": 0, "n_discordant": 0}

    chi2 = (abs(a_right_b_wrong - a_wrong_b_right) - 1) ** 2 / n

    # Approximate p-value using chi-squared with 1 df
    # For exact computation, use scipy if available
    try:
        from scipy.stats import chi2 as chi2_dist
        p_value = 1 - chi2_dist.cdf(chi2, df=1)
    except ImportError:
        # Rough approximation
        if chi2 > 10.83:
            p_value = 0.001
        elif chi2 > 6.63:
            p_value = 0.01
        elif chi2 > 3.84:
            p_value = 0.05
        elif chi2 > 2.71:
            p_value = 0.10
        else:
            p_value = 0.5  # Not significant

    return {
        "chi2": chi2,
        "p_value": p_value,
        "a_right_b_wrong": a_right_b_wrong,
        "a_wrong_b_right": a_wrong_b_right,
        "n_discordant": n,
    }


def bootstrap_ci(predictions, gold_map, n_bootstrap=10000, seed=42):
    """Bootstrap 95% CI for overall accuracy."""
    import random
    rng = random.Random(seed)

    accs = []
    n = len(predictions)
    for _ in range(n_bootstrap):
        sample = [rng.choice(predictions) for _ in range(n)]
        correct = 0
        for p in sample:
            gold = gold_map.get(p["case_id"], [])
            gold_parents = [g.split(".")[0] for g in gold]
            pred_parent = parent_code(p.get("primary_diagnosis"))
            dec = p.get("decision", "diagnosis")
            if pred_parent in gold_parents and dec != "abstain":
                correct += 1
        accs.append(correct / n)

    accs.sort()
    lo = accs[int(0.025 * n_bootstrap)]
    hi = accs[int(0.975 * n_bootstrap)]
    return lo, hi


def main():
    parser = argparse.ArgumentParser(description="N=200 3-mode analysis")
    parser.add_argument("sweep_dir", type=str, help="Sweep output directory")
    parser.add_argument("--bootstrap", action="store_true", help="Run bootstrap CIs (slow)")
    args = parser.parse_args()

    sweep_dir = Path(args.sweep_dir)
    conditions = load_sweep(sweep_dir)

    # Load gold labels
    with open(sweep_dir / "case_list.json", encoding="utf-8") as f:
        case_data = json.load(f)
    gold_map = {c["case_id"]: c["diagnoses"] for c in case_data["cases"]}

    print(f"=== N={len(gold_map)} 3-Mode Analysis ===")
    print(f"Sweep: {sweep_dir.name}\n")

    # Distribution
    dist = Counter()
    for gold in gold_map.values():
        for g in gold:
            dist[g.split(".")[0]] += 1
    print("Gold distribution:")
    for d, cnt in dist.most_common():
        print(f"  {d}: {cnt}")
    print()

    # Compute metrics for each condition
    results = {}
    for cond_name, data in sorted(conditions.items()):
        preds = data["predictions"]
        metrics = compute_metrics(preds, gold_map)
        results[cond_name] = {"metrics": metrics, "predictions": preds}

    # Print comparison table
    print(f"{'Condition':<25} {'Overall':>8} {'Diag.Acc':>9} {'Macro-F1':>9} {'Correct':>8} {'Abstain':>8}")
    print("-" * 75)
    for cond_name, r in sorted(results.items()):
        m = r["metrics"]
        print(
            f"{cond_name:<25} {m['overall_acc']*100:>7.1f}% {m['diag_acc']*100:>8.1f}% "
            f"{m['macro_f1']*100:>8.1f}% {m['correct']:>7d} {m['abstain']:>7d}"
        )

    # Per-disorder breakdown for each mode
    for cond_name, r in sorted(results.items()):
        m = r["metrics"]
        print(f"\n--- {cond_name} per-disorder ---")
        for disorder in sorted(m["per_disorder"].keys(), key=lambda x: -m["per_disorder"][x]["total"]):
            d = m["per_disorder"][disorder]
            rec = d["tp"] / d["total"] if d["total"] > 0 else 0
            print(f"  {disorder}: {d['tp']}/{d['total']} recall={rec*100:.0f}%, FP={d['fp']}")

    # Pairwise McNemar tests
    cond_names = sorted(results.keys())
    if len(cond_names) > 1:
        print("\n=== Pairwise McNemar Tests ===")
        for i, a_name in enumerate(cond_names):
            for b_name in cond_names[i + 1:]:
                test = mcnemar_test(
                    results[a_name]["predictions"],
                    results[b_name]["predictions"],
                    gold_map,
                )
                sig = "***" if test["p_value"] < 0.001 else (
                    "**" if test["p_value"] < 0.01 else (
                        "*" if test["p_value"] < 0.05 else "ns"))
                print(
                    f"  {a_name} vs {b_name}: "
                    f"chi2={test['chi2']:.2f} p={test['p_value']:.4f} {sig} "
                    f"({a_name}+={test['a_right_b_wrong']}, {b_name}+={test['a_wrong_b_right']})"
                )

    # Bootstrap CIs
    if args.bootstrap:
        print("\n=== Bootstrap 95% CIs (10000 resamples) ===")
        for cond_name, r in sorted(results.items()):
            lo, hi = bootstrap_ci(r["predictions"], gold_map)
            print(f"  {cond_name}: [{lo*100:.1f}%, {hi*100:.1f}%]")


if __name__ == "__main__":
    main()
