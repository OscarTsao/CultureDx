#!/usr/bin/env python3
"""Exploratory dev-split comparison for MAS vs TF-IDF predictions."""
from __future__ import annotations

from collections import defaultdict

from _common import (
    compute_metrics,
    correct_flags,
    build_oracle_records,
    load_prediction_maps,
    load_split,
    primary_gold_label,
    subset_records,
)


def main() -> None:
    split = load_split()
    dev_ids = split["dev"]
    mas_map, tfidf_map = load_prediction_maps()
    mas_records = subset_records(mas_map, dev_ids)
    tfidf_records = subset_records(tfidf_map, dev_ids)
    oracle_records = build_oracle_records(dev_ids, mas_map, tfidf_map)

    mas_flags = correct_flags(mas_records)
    tfidf_flags = correct_flags(tfidf_records)

    bucket_totals = {
        "mas_only": 0,
        "tfidf_only": 0,
        "both_right": 0,
        "both_wrong": 0,
    }
    class_breakdown: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "n": 0,
            "mas_only": 0,
            "tfidf_only": 0,
            "both_right": 0,
            "both_wrong": 0,
            "mas_right": 0,
            "tfidf_right": 0,
        }
    )

    for mas_record, tfidf_record, mas_ok, tfidf_ok in zip(
        mas_records,
        tfidf_records,
        mas_flags,
        tfidf_flags,
        strict=True,
    ):
        gold_class = primary_gold_label(mas_record)
        stats = class_breakdown[gold_class]
        stats["n"] += 1
        stats["mas_right"] += int(mas_ok)
        stats["tfidf_right"] += int(tfidf_ok)

        if mas_ok and tfidf_ok:
            stats["both_right"] += 1
            bucket_totals["both_right"] += 1
        elif mas_ok:
            stats["mas_only"] += 1
            bucket_totals["mas_only"] += 1
        elif tfidf_ok:
            stats["tfidf_only"] += 1
            bucket_totals["tfidf_only"] += 1
        else:
            stats["both_wrong"] += 1
            bucket_totals["both_wrong"] += 1

    mas_metrics = compute_metrics(mas_records)
    tfidf_metrics = compute_metrics(tfidf_records)
    oracle_metrics = compute_metrics(oracle_records)

    print("DEV split exploratory analysis")
    print("=" * 88)
    print(f"Cases: {len(dev_ids)}")
    print(
        "Outcome buckets: "
        f"MAS-only={bucket_totals['mas_only']}, "
        f"TF-IDF-only={bucket_totals['tfidf_only']}, "
        f"both-right={bucket_totals['both_right']}, "
        f"both-wrong={bucket_totals['both_wrong']}"
    )
    print()
    print(
        f"MAS    : top1={mas_metrics['top1']:.4f} "
        f"f1_macro={mas_metrics['f1_macro']:.4f} "
        f"f1_weighted={mas_metrics['f1_weighted']:.4f}"
    )
    print(
        f"TF-IDF : top1={tfidf_metrics['top1']:.4f} "
        f"f1_macro={tfidf_metrics['f1_macro']:.4f} "
        f"f1_weighted={tfidf_metrics['f1_weighted']:.4f}"
    )
    print(
        "Oracle : top1={top1:.4f} f1_macro={f1_macro:.4f} f1_weighted={f1_weighted:.4f}".format(
            **oracle_metrics
        )
    )
    print("Oracle selects the per-case prediction set with higher label-set F1.")
    print()

    header = (
        f"{'Gold':<8} {'N':>4} {'MAS_top1':>9} {'TFIDF_top1':>11} "
        f"{'MAS_only':>9} {'TFIDF_only':>11} {'Both':>7} {'Neither':>9}"
    )
    print(header)
    print("-" * len(header))
    for gold_class in sorted(class_breakdown):
        stats = class_breakdown[gold_class]
        n_cases = stats["n"]
        mas_top1 = stats["mas_right"] / n_cases if n_cases else 0.0
        tfidf_top1 = stats["tfidf_right"] / n_cases if n_cases else 0.0
        print(
            f"{gold_class:<8} {n_cases:>4d} {mas_top1:>9.3f} {tfidf_top1:>11.3f} "
            f"{stats['mas_only']:>9d} {stats['tfidf_only']:>11d} "
            f"{stats['both_right']:>7d} {stats['both_wrong']:>9d}"
        )


if __name__ == "__main__":
    main()
