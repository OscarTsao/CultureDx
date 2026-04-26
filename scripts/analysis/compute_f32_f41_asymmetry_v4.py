#!/usr/bin/env python3
"""Compute F32/F41 asymmetry under v4 evaluator with bootstrap CI.

Reads predictions.jsonl from dual_standard_full runs, computes F32/F41 confusion
counts using paper-parent taxonomy, and emits asymmetry metrics with bootstrap CI.

Per GPT round 10 directive: 'F32/F41 asymmetry under v4 + bootstrap CI'.

Usage:
    uv run python scripts/analysis/compute_f32_f41_asymmetry_v4.py \\
        --output results/analysis/mdd5k_f32_f41_asymmetry_v4.json
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_DIR = ROOT / "results" / "dual_standard_full"
DEFAULT_BASELINE_FILE = ROOT / "results" / "generalization" / "bias_transfer_analysis.json"
DEFAULT_OUTPUT = ROOT / "results" / "analysis" / "mdd5k_f32_f41_asymmetry_v4.json"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


def to_paper_parent(code: str | None) -> str:
    """Map ICD code to paper-parent class. F33 -> Others, F41.x -> F41, etc."""
    if not code:
        return "Others"
    parent = str(code).split(".")[0]
    if parent == "F33":
        return "Others"
    return parent


def confusion_counts(predictions: list[dict]) -> dict:
    """Compute F41->F32 and F32->F41 confusion counts under paper-parent taxonomy."""
    f41_to_f32 = 0
    f32_to_f41 = 0
    f41_n = 0
    f32_n = 0
    for r in predictions:
        gold_set = {to_paper_parent(g) for g in (r.get("gold_diagnoses") or [])}
        pred = to_paper_parent(r.get("primary_diagnosis"))
        if "F41" in gold_set:
            f41_n += 1
            if pred == "F32":
                f41_to_f32 += 1
        if "F32" in gold_set:
            f32_n += 1
            if pred == "F41":
                f32_to_f41 += 1
    return {
        "f41_to_f32": f41_to_f32,
        "f32_to_f41": f32_to_f41,
        "f41_n": f41_n,
        "f32_n": f32_n,
        "asymmetry_ratio": (f41_to_f32 / f32_to_f41) if f32_to_f41 > 0 else None,
        "asymmetric_excess": f41_to_f32 - f32_to_f41,
    }


def bootstrap_single_ci(predictions: list[dict], n_boot: int = 1000, seed: int = 20260420) -> dict:
    """Bootstrap CI for single-system asymmetry."""
    random.seed(seed)
    n = len(predictions)
    ratios = []
    excesses = []
    for _ in range(n_boot):
        sample = [predictions[random.randrange(n)] for _ in range(n)]
        c = confusion_counts(sample)
        if c["asymmetry_ratio"] is not None:
            ratios.append(c["asymmetry_ratio"])
        excesses.append(c["asymmetric_excess"])
    ratios.sort()
    excesses.sort()
    nr = len(ratios)
    return {
        "n_boot_valid_ratio": nr,
        "ratio_ci95_low": ratios[int(nr * 0.025)] if nr >= 40 else None,
        "ratio_ci95_high": ratios[int(nr * 0.975)] if nr >= 40 else None,
        "excess_ci95_low": excesses[int(len(excesses) * 0.025)],
        "excess_ci95_high": excesses[int(len(excesses) * 0.975)],
    }


def paired_bootstrap_diff(
    icd_preds: list[dict], dsm_preds: list[dict], n_boot: int = 1000, seed: int = 20260420
) -> dict:
    """Paired bootstrap of (DSM-5 asymmetry - ICD-10 asymmetry)."""
    random.seed(seed)
    icd_by_id = {r["case_id"]: r for r in icd_preds}
    dsm_by_id = {r["case_id"]: r for r in dsm_preds}
    common = sorted(set(icd_by_id) & set(dsm_by_id))
    n = len(common)
    diff_ratio = []
    diff_excess = []
    for _ in range(n_boot):
        sample_ids = [common[random.randrange(n)] for _ in range(n)]
        i_c = confusion_counts([icd_by_id[c] for c in sample_ids])
        d_c = confusion_counts([dsm_by_id[c] for c in sample_ids])
        if i_c["asymmetry_ratio"] is not None and d_c["asymmetry_ratio"] is not None:
            diff_ratio.append(d_c["asymmetry_ratio"] - i_c["asymmetry_ratio"])
        diff_excess.append(d_c["asymmetric_excess"] - i_c["asymmetric_excess"])
    diff_ratio.sort()
    diff_excess.sort()
    return {
        "n_paired_cases": n,
        "diff_ratio_median": diff_ratio[len(diff_ratio) // 2] if diff_ratio else None,
        "diff_ratio_ci95_low": diff_ratio[int(len(diff_ratio) * 0.025)] if diff_ratio else None,
        "diff_ratio_ci95_high": diff_ratio[int(len(diff_ratio) * 0.975)] if diff_ratio else None,
        "diff_excess_median": diff_excess[len(diff_excess) // 2],
        "diff_excess_ci95_low": diff_excess[int(len(diff_excess) * 0.025)],
        "diff_excess_ci95_high": diff_excess[int(len(diff_excess) * 0.975)],
    }


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR)
    parser.add_argument("--baseline-file", type=Path, default=DEFAULT_BASELINE_FILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--n-boot", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260420)
    args = parser.parse_args()

    results: dict = {
        "generated_at": "2026-04-26",
        "metric_definition": {
            "asymmetry_ratio": "(F41 gold predicted as F32) / (F32 gold predicted as F41)",
            "asymmetric_excess": "(F41 gold predicted as F32) - (F32 gold predicted as F41)",
            "taxonomy": "paper-parent (F33 -> Others, F41.x -> F41, F32.x -> F32)",
            "bootstrap": f"{args.n_boot} resamples, seed={args.seed}",
        },
        "systems": {},
        "paired_comparisons": {},
    }

    # v4 dual-standard runs
    for ds in ["lingxidiag16k", "mdd5k"]:
        for mode in ["icd10", "dsm5", "both"]:
            preds_path = args.base_dir / ds / f"mode_{mode}" / f"pilot_{mode}" / "predictions.jsonl"
            if not preds_path.exists():
                logger.warning("Missing predictions: %s", preds_path)
                continue
            preds = load_jsonl(preds_path)
            counts = confusion_counts(preds)
            ci = bootstrap_single_ci(preds, n_boot=args.n_boot, seed=args.seed)
            key = f"{ds}_v4_mas_{mode}"
            results["systems"][key] = {
                "dataset": ds,
                "system": f"MAS {mode.upper()} (v4 dual-standard)",
                "n_cases": len(preds),
                **counts,
                "asymmetry_ci95": [ci["ratio_ci95_low"], ci["ratio_ci95_high"]],
                "excess_ci95": [ci["excess_ci95_low"], ci["excess_ci95_high"]],
            }

    # Paired bootstrap (DSM-5 - ICD-10)
    for ds in ["lingxidiag16k", "mdd5k"]:
        icd_path = args.base_dir / ds / "mode_icd10" / "pilot_icd10" / "predictions.jsonl"
        dsm_path = args.base_dir / ds / "mode_dsm5" / "pilot_dsm5" / "predictions.jsonl"
        if not (icd_path.exists() and dsm_path.exists()):
            continue
        icd_preds = load_jsonl(icd_path)
        dsm_preds = load_jsonl(dsm_path)
        paired = paired_bootstrap_diff(icd_preds, dsm_preds, n_boot=args.n_boot, seed=args.seed)
        key = f"{ds}_dsm5_minus_icd10"
        results["paired_comparisons"][key] = {
            "description": f"Paired bootstrap of (DSM-5 - ICD-10) asymmetry on {ds}",
            **paired,
            "ratio_diff_significant_at_alpha_0.05": (
                paired["diff_ratio_ci95_low"] is not None
                and not (paired["diff_ratio_ci95_low"] <= 0 <= paired["diff_ratio_ci95_high"])
            ),
            "excess_diff_significant_at_alpha_0.05": not (
                paired["diff_excess_ci95_low"] <= 0 <= paired["diff_excess_ci95_high"]
            ),
        }

    # Pre-v4 MDD-5k baselines from existing analysis
    if args.baseline_file.exists():
        existing = json.loads(args.baseline_file.read_text())
        for run in existing.get("runs", []):
            if run.get("dataset") != "mdd5k":
                continue
            label = run["label"].lower().replace(" ", "_").replace("-", "_")
            key = f"mdd5k_baseline_{label}"
            results["systems"][key] = {
                "dataset": "mdd5k",
                "system": run["label"],
                "n_cases": run["num_predictions"],
                "f41_to_f32": run["f41_gold_pred_f32"],
                "f32_to_f41": run["f32_gold_pred_f41"],
                "asymmetry_ratio": run["ratio"],
                "asymmetric_excess": run["f41_gold_pred_f32"] - run["f32_gold_pred_f41"],
                "note": "pre-v4 baseline (from bias_transfer_analysis.json)",
            }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    logger.info("Wrote %s", args.output)

    # Print summary
    print("\n=== F32/F41 asymmetry — MDD-5k systems ===")
    for key, sys_info in results["systems"].items():
        if sys_info["dataset"] != "mdd5k":
            continue
        ratio = sys_info["asymmetry_ratio"]
        ratio_str = f"{ratio:.2f}x" if ratio is not None and ratio != float("inf") else "inf"
        print(
            f"  {sys_info['system']:<40} "
            f"{sys_info['f41_to_f32']:>4}/{sys_info['f32_to_f41']:<4} "
            f"{ratio_str:>10}"
        )


if __name__ == "__main__":
    main()
