#!/usr/bin/env python3
"""Final test-split evaluation for the selected MAS + TF-IDF ensemble rule."""
from __future__ import annotations

import json

from _common import (
    RESULTS_DIR,
    build_ensemble_records,
    compute_metrics,
    correct_flags,
    load_prediction_maps,
    load_split,
    subset_records,
    write_jsonl,
)
from culturedx.eval.statistical_tests import mcnemar_test
from culturedx.postproc.ensemble_gate import EnsembleConfig


def load_best_rule() -> tuple[str, str, EnsembleConfig | None, str]:
    path = RESULTS_DIR / "best_rule.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Best-rule file not found: {path}. Run scripts/ensemble/tune_on_dev.py first."
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    rule_name = payload["selected_rule_name"]
    rule_description = payload["selected_rule_description"]
    gate_status = payload["gate_status"]
    config_payload = payload.get("selected_rule_config")
    config = EnsembleConfig(**config_payload) if config_payload is not None else None
    return rule_name, rule_description, config, gate_status


def main() -> None:
    rule_name, rule_description, config, gate_status = load_best_rule()
    if gate_status != "G1 pass":
        raise SystemExit(f"Best dev result did not clear G1 ({gate_status}). Final evaluation not run.")

    split = load_split()
    test_ids = split["test"]
    mas_map, tfidf_map = load_prediction_maps()

    mas_records = subset_records(mas_map, test_ids)
    tfidf_records = subset_records(tfidf_map, test_ids)
    if rule_name == "mas_only":
        ensemble_records = mas_records
    elif rule_name == "tfidf_only":
        ensemble_records = tfidf_records
    elif config is not None:
        ensemble_records = build_ensemble_records(test_ids, mas_map, tfidf_map, config)
    else:
        raise ValueError(f"Missing config for selected rule {rule_name}")

    mas_metrics = compute_metrics(mas_records)
    tfidf_metrics = compute_metrics(tfidf_records)
    ensemble_metrics = compute_metrics(ensemble_records)

    ensemble_vs_tfidf = mcnemar_test(correct_flags(ensemble_records), correct_flags(tfidf_records))
    ensemble_vs_mas = mcnemar_test(correct_flags(ensemble_records), correct_flags(mas_records))

    final_metrics = {
        "selected_rule_name": rule_name,
        "selected_rule_description": rule_description,
        "mas_alone": mas_metrics,
        "tfidf_alone": tfidf_metrics,
        "ensemble": ensemble_metrics,
        "mcnemar": {
            "ensemble_vs_tfidf": {
                "p_value": ensemble_vs_tfidf["p_value"],
                "statistic": ensemble_vs_tfidf["statistic"],
                "n_both_correct": ensemble_vs_tfidf["n_both_correct"],
                "n_ensemble_only": ensemble_vs_tfidf["n_a_only"],
                "n_tfidf_only": ensemble_vs_tfidf["n_b_only"],
                "n_both_wrong": ensemble_vs_tfidf["n_both_wrong"],
            },
            "ensemble_vs_mas": {
                "p_value": ensemble_vs_mas["p_value"],
                "statistic": ensemble_vs_mas["statistic"],
                "n_both_correct": ensemble_vs_mas["n_both_correct"],
                "n_ensemble_only": ensemble_vs_mas["n_a_only"],
                "n_mas_only": ensemble_vs_mas["n_b_only"],
                "n_both_wrong": ensemble_vs_mas["n_both_wrong"],
            },
        },
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(RESULTS_DIR / "test_predictions.jsonl", ensemble_records)
    (RESULTS_DIR / "final_metrics.json").write_text(
        json.dumps(final_metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("Final test evaluation")
    print("=" * 88)
    print(f"Selected rule: {rule_name}")
    print(rule_description)
    print(
        f"MAS alone    : top1={mas_metrics['top1']:.4f} "
        f"f1_macro={mas_metrics['f1_macro']:.4f} "
        f"f1_weighted={mas_metrics['f1_weighted']:.4f}"
    )
    print(
        f"TF-IDF alone : top1={tfidf_metrics['top1']:.4f} "
        f"f1_macro={tfidf_metrics['f1_macro']:.4f} "
        f"f1_weighted={tfidf_metrics['f1_weighted']:.4f}"
    )
    print(
        f"Ensemble     : top1={ensemble_metrics['top1']:.4f} "
        f"f1_macro={ensemble_metrics['f1_macro']:.4f} "
        f"f1_weighted={ensemble_metrics['f1_weighted']:.4f}"
    )
    print(
        "McNemar vs TF-IDF: "
        f"p={ensemble_vs_tfidf['p_value']:.6f} "
        f"(ensemble_only={ensemble_vs_tfidf['n_a_only']}, tfidf_only={ensemble_vs_tfidf['n_b_only']})"
    )
    print(
        "McNemar vs MAS   : "
        f"p={ensemble_vs_mas['p_value']:.6f} "
        f"(ensemble_only={ensemble_vs_mas['n_a_only']}, mas_only={ensemble_vs_mas['n_b_only']})"
    )


if __name__ == "__main__":
    main()
