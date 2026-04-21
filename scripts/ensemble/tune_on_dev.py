#!/usr/bin/env python3
"""Tune a class-based MAS + TF-IDF ensemble on the dev split."""
from __future__ import annotations

import json

from _common import (
    RESULTS_DIR,
    build_ensemble_records,
    compute_metrics,
    config_to_dict,
    load_prediction_maps,
    load_split,
    rule_description,
    serialize_metrics,
    subset_records,
)
from culturedx.postproc.ensemble_gate import EnsembleConfig


def evaluate_rule(
    name: str,
    dev_ids: list[str],
    test_ids: list[str],
    mas_map: dict[str, dict],
    tfidf_map: dict[str, dict],
    config: EnsembleConfig | None = None,
) -> dict:
    if name == "mas_only":
        dev_records = subset_records(mas_map, dev_ids)
        test_records = subset_records(mas_map, test_ids)
    elif name == "tfidf_only":
        dev_records = subset_records(tfidf_map, dev_ids)
        test_records = subset_records(tfidf_map, test_ids)
    elif config is not None:
        dev_records = build_ensemble_records(dev_ids, mas_map, tfidf_map, config)
        test_records = build_ensemble_records(test_ids, mas_map, tfidf_map, config)
    else:
        raise ValueError(f"Missing config for ensemble rule {name}")

    return {
        "name": name,
        "description": rule_description(name, config),
        "config": config_to_dict(config) if config is not None else None,
        "dev": serialize_metrics(compute_metrics(dev_records)),
        "test": serialize_metrics(compute_metrics(test_records)),
    }


def select_best(results: list[dict]) -> dict:
    return max(
        results,
        key=lambda row: (
            row["dev"]["f1_macro"],
            row["dev"]["top1"],
            -len(row["description"]),
            row["name"],
        ),
    )


def maybe_expand_v2_candidates(best_v1: dict) -> list[dict]:
    if not (0.25 <= best_v1["dev"]["f1_macro"] <= 0.27):
        return []
    if best_v1["config"] is None:
        return []

    strong_classes = tuple(best_v1["config"]["mas_strong_classes"])
    thresholds = (0.30, 0.35, 0.40, 0.45, 0.50, 0.55)
    candidates: list[dict] = []
    for threshold in thresholds:
        config = EnsembleConfig(
            rule="v2_prob_threshold",
            mas_strong_classes=strong_classes,
            tfidf_threshold_high=threshold,
        )
        candidates.append(
            {
                "name": f"v2_prob_threshold_{threshold:.2f}",
                "config": config,
            }
        )
    return candidates


def gate_status(best_result: dict) -> str:
    dev_f1 = best_result["dev"]["f1_macro"]
    if dev_f1 > 0.27:
        return "G1 pass"
    if 0.25 <= dev_f1 <= 0.27:
        return "G1b borderline"
    return "G1c stop"


def main() -> None:
    split = load_split()
    dev_ids = split["dev"]
    test_ids = split["test"]
    mas_map, tfidf_map = load_prediction_maps()

    base_candidates: list[dict] = [
        {"name": "mas_only", "config": None},
        {"name": "tfidf_only", "config": None},
        {
            "name": "v1_f32",
            "config": EnsembleConfig(
                rule="v1_class_based",
                mas_strong_classes=("F32",),
            ),
        },
        {
            "name": "v1_f32_f41",
            "config": EnsembleConfig(
                rule="v1_class_based",
                mas_strong_classes=("F32", "F41"),
            ),
        },
        {
            "name": "v1_f32_f41_f45",
            "config": EnsembleConfig(
                rule="v1_class_based",
                mas_strong_classes=("F32", "F41", "F45"),
            ),
        },
        {
            "name": "v1_f32_f41_f42",
            "config": EnsembleConfig(
                rule="v1_class_based",
                mas_strong_classes=("F32", "F41", "F42"),
            ),
        },
        {
            "name": "v1_f32_f41_f42_f45",
            "config": EnsembleConfig(
                rule="v1_class_based",
                mas_strong_classes=("F32", "F41", "F42", "F45"),
            ),
        },
    ]

    results = [
        evaluate_rule(
            name=candidate["name"],
            dev_ids=dev_ids,
            test_ids=test_ids,
            mas_map=mas_map,
            tfidf_map=tfidf_map,
            config=candidate["config"],
        )
        for candidate in base_candidates
    ]
    best_result = select_best(results)

    extra_candidates = maybe_expand_v2_candidates(best_result)
    if extra_candidates:
        for candidate in extra_candidates:
            results.append(
                evaluate_rule(
                    name=candidate["name"],
                    dev_ids=dev_ids,
                    test_ids=test_ids,
                    mas_map=mas_map,
                    tfidf_map=tfidf_map,
                    config=candidate["config"],
                )
            )
        best_result = select_best(results)

    status = gate_status(best_result)

    print("DEV tuning sweep")
    print("=" * 120)
    print(
        f"{'Rule':<28} {'Dev Top1':>10} {'Dev F1m':>10} {'Dev F1w':>10} {'Notes':<58}"
    )
    print("-" * 120)
    for row in sorted(
        results,
        key=lambda item: (
            -item["dev"]["f1_macro"],
            -item["dev"]["top1"],
            item["name"],
        ),
    ):
        print(
            f"{row['name']:<28} {row['dev']['top1']:>10.4f} "
            f"{row['dev']['f1_macro']:>10.4f} {row['dev']['f1_weighted']:>10.4f} "
            f"{row['description']:<58}"
        )
    print("-" * 120)
    print(
        f"Winner by dev F1_macro: {best_result['name']} "
        f"(top1={best_result['dev']['top1']:.4f}, "
        f"f1_macro={best_result['dev']['f1_macro']:.4f}, "
        f"f1_weighted={best_result['dev']['f1_weighted']:.4f})"
    )
    print(
        "Winner held-out test: "
        f"top1={best_result['test']['top1']:.4f}, "
        f"f1_macro={best_result['test']['f1_macro']:.4f}, "
        f"f1_weighted={best_result['test']['f1_weighted']:.4f}"
    )
    print(f"Gate status: {status}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    best_rule_payload = {
        "selected_rule_name": best_result["name"],
        "selected_rule_description": best_result["description"],
        "selected_rule_config": best_result["config"],
        "gate_status": status,
        "winner_dev_metrics": best_result["dev"],
        "winner_test_metrics": best_result["test"],
        "all_results": results,
    }
    (RESULTS_DIR / "best_rule.json").write_text(
        json.dumps(best_rule_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RESULTS_DIR / "tune_results.json").write_text(
        json.dumps({"results": results, "winner": best_result, "gate_status": status}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
