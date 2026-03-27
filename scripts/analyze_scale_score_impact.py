#!/usr/bin/env python3
"""Analyze scale score impact on E-DAIC results.

Compares old (no scale score) vs new (with scale score) sweep results.
"""
import json
import sys
from pathlib import Path


def load_metrics(sweep_dir: Path) -> dict:
    """Load metrics from all conditions in a sweep directory."""
    results = {}
    for cond_dir in sorted(sweep_dir.iterdir()):
        metrics_file = cond_dir / "metrics.json"
        if metrics_file.exists():
            with open(metrics_file, encoding="utf-8") as f:
                results[cond_dir.name] = json.load(f)
    return results


def main():
    old_dir = Path("outputs/sweeps/evidence_edaic_20260323_011113")

    # Find newest scale_score_edaic directory
    sweep_base = Path("outputs/sweeps")
    new_dirs = sorted(sweep_base.glob("scale_score_edaic_*"))
    if not new_dirs:
        print("ERROR: No scale_score_edaic sweep found.")
        sys.exit(1)
    new_dir = new_dirs[-1]

    print(f"Old sweep: {old_dir}")
    print(f"New sweep: {new_dir}")

    old_metrics = load_metrics(old_dir)
    new_metrics = load_metrics(new_dir)

    print("\n" + "=" * 80)
    print("SCALE SCORE IMPACT ANALYSIS (E-DAIC, N=217)")
    print("=" * 80)

    # Compare conditions
    comparison = []
    for cond in ["hied_no_evidence", "hied_bge-m3_evidence", "hied_bge-m3_no_somatization"]:
        old = old_metrics.get(cond, {}).get("diagnosis", {})
        new = new_metrics.get(cond, {}).get("diagnosis", {})

        if not new:
            continue

        old_t1 = old.get("top1_accuracy", 0) * 100
        old_t3 = old.get("top3_accuracy", 0) * 100
        old_f1 = old.get("macro_f1", 0) * 100
        new_t1 = new.get("top1_accuracy", 0) * 100
        new_t3 = new.get("top3_accuracy", 0) * 100
        new_f1 = new.get("macro_f1", 0) * 100

        comparison.append({
            "condition": cond,
            "old_top1": old_t1, "new_top1": new_t1, "delta_top1": new_t1 - old_t1,
            "old_top3": old_t3, "new_top3": new_t3, "delta_top3": new_t3 - old_t3,
            "old_f1": old_f1, "new_f1": new_f1, "delta_f1": new_f1 - old_f1,
        })

        print(f"\n{cond}:")
        print(f"  Top-1 Acc: {old_t1:.1f}% -> {new_t1:.1f}% ({new_t1 - old_t1:+.1f}pp)")
        print(f"  Top-3 Acc: {old_t3:.1f}% -> {new_t3:.1f}% ({new_t3 - old_t3:+.1f}pp)")
        print(f"  Macro F1:  {old_f1:.1f}% -> {new_f1:.1f}% ({new_f1 - old_f1:+.1f}pp)")

    # PHQ-8 severity breakdown (from predictions)
    print("\n" + "=" * 80)
    print("PHQ-8 SEVERITY BREAKDOWN")
    print("=" * 80)

    # Load predictions and cases
    data = json.load(open("data/raw/daic_explain/edaic_processed.json"))
    phq8_map = {str(item["case_id"]): item["phq8_total"] for item in data}

    for cond_name in ["hied_no_evidence", "hied_bge-m3_evidence"]:
        pred_file = new_dir / cond_name / "predictions.jsonl"
        if not pred_file.exists():
            continue

        preds = []
        with open(pred_file) as f:
            for line in f:
                preds.append(json.loads(line))

        # Severity buckets
        buckets = {
            "none (0-4)": (0, 4),
            "mild (5-9)": (5, 9),
            "moderate (10-14)": (10, 14),
            "mod-severe (15-19)": (15, 19),
            "severe (20+)": (20, 100),
        }

        print(f"\n{cond_name}:")
        for bucket_name, (lo, hi) in buckets.items():
            bucket_preds = [
                p for p in preds
                if lo <= phq8_map.get(p.get("case_id", ""), 0) <= hi
            ]
            if not bucket_preds:
                continue
            n = len(bucket_preds)
            correct = sum(1 for p in bucket_preds
                         if "F32" in (p.get("primary_diagnosis") or "")
                         and phq8_map.get(p.get("case_id", ""), 0) >= 10)
            correct += sum(1 for p in bucket_preds
                          if "F32" not in (p.get("primary_diagnosis") or "")
                          and phq8_map.get(p.get("case_id", ""), 0) < 10)
            print(f"  {bucket_name}: {n} cases, accuracy={correct/n*100:.1f}%")

    # Save comparison
    output = {
        "old_sweep": str(old_dir),
        "new_sweep": str(new_dir),
        "comparison": comparison,
    }
    out_path = Path("outputs/scale_score_impact.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nSaved comparison to {out_path}")


if __name__ == "__main__":
    main()
