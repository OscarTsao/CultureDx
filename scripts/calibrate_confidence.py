#!/usr/bin/env python3
"""Post-hoc Platt scaling + risk-coverage analysis on existing predictions.

Zero LLM cost: operates entirely on existing prediction files.

For each (dataset, mode) pair:
  1. Extract (confidence, correct) pairs
  2. Compute ECE BEFORE Platt scaling
  3. Fit Platt scaling using leave-one-dataset-out cross-validation
  4. Compute ECE AFTER, risk-coverage curve, AURC
  5. Selective accuracy at key coverage levels

Usage:
    uv run python scripts/calibrate_confidence.py
    uv run python scripts/calibrate_confidence.py --sweep-dirs outputs/sweeps/v10_*
    uv run python scripts/calibrate_confidence.py --output outputs/platt_calibration
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.eval.calibration import (
    PlattCalibrator,
    compute_calibration,
    compute_risk_coverage_curve,
)
from culturedx.eval.cross_lingual import aurc, selective_accuracy


# ──────────────────────────────────────────────────────────────
# Data loading
# ──────────────────────────────────────────────────────────────

def load_sweep_data(sweep_dir: Path) -> dict:
    """Load case_list and all condition predictions from a sweep directory.

    Returns dict with keys:
        dataset: str (inferred from dir name)
        gold: dict[case_id -> list[str]]  (gold diagnoses)
        conditions: dict[condition_name -> list[dict]]  (predictions)
    """
    case_list_path = sweep_dir / "case_list.json"
    if not case_list_path.exists():
        return {}

    with open(case_list_path, encoding="utf-8") as f:
        case_data = json.load(f)

    # Handle different case_list formats
    if isinstance(case_data, dict) and "cases" in case_data:
        # Standard format: {"n_cases": N, "seed": S, "cases": [{"case_id": ..., "diagnoses": [...]}]}
        gold = {str(c["case_id"]): c["diagnoses"] for c in case_data["cases"]}
    elif isinstance(case_data, list):
        # E-DAIC format: plain list of participant IDs (no gold labels inline)
        # Need to load gold from adapter
        gold = _load_edaic_gold(case_data)
    else:
        return {}

    # Infer dataset from directory name
    dirname = sweep_dir.name.lower()
    if "lingxidiag" in dirname:
        dataset = "lingxidiag"
    elif "mdd5k" in dirname:
        dataset = "mdd5k"
    elif "edaic" in dirname:
        dataset = "edaic"
    else:
        dataset = dirname.split("_")[0]

    conditions = {}
    for cond_dir in sorted(sweep_dir.iterdir()):
        if not cond_dir.is_dir():
            continue
        pred_path = cond_dir / "predictions.json"
        if not pred_path.exists():
            continue
        with open(pred_path, encoding="utf-8") as f:
            raw = json.load(f)
        preds = raw["predictions"] if isinstance(raw, dict) and "predictions" in raw else raw
        conditions[cond_dir.name] = preds

    return {"dataset": dataset, "gold": gold, "conditions": conditions}


def _load_edaic_gold(case_ids: list) -> dict[str, list[str]]:
    """Load E-DAIC gold labels from the data adapter."""
    try:
        from culturedx.data.adapters import get_adapter
        adapter = get_adapter("edaic", "data/raw/daic_explain/edaic_processed.json")
        cases = adapter.load()
        # Filter to only the case_ids in our list
        id_set = {str(cid) for cid in case_ids}
        return {
            c.case_id: c.diagnoses
            for c in cases
            if c.case_id in id_set
        }
    except Exception as e:
        print(f"  WARNING: Could not load E-DAIC gold labels: {e}")
        # Fallback: try loading from predictions metadata
        return {}


def extract_conf_correct(
    predictions: list[dict],
    gold: dict[str, list[str]],
) -> tuple[list[float], list[bool], int, int]:
    """Extract (confidence, correct) pairs using parent-code matching.

    Returns: (confidences, correct, n_valid, n_abstain)
    """
    confidences = []
    correct = []
    n_abstain = 0

    for pred in predictions:
        case_id = str(pred["case_id"])
        primary = pred.get("primary_diagnosis")
        conf = pred.get("confidence", 0.0)

        if primary is None or pred.get("decision") == "abstain":
            n_abstain += 1
            continue

        if case_id not in gold:
            continue

        gold_codes = gold[case_id]
        if not gold_codes:
            # Empty gold = no diagnosis; predicted something = incorrect
            confidences.append(conf)
            correct.append(False)
            continue

        # Parent code matching: F41.1 -> F41, F32 -> F32
        pred_parent = primary.split(".")[0]
        gold_parents = {g.split(".")[0] for g in gold_codes}
        is_correct = pred_parent in gold_parents

        confidences.append(conf)
        correct.append(is_correct)

    return confidences, correct, len(confidences), n_abstain


# ──────────────────────────────────────────────────────────────
# Leave-one-dataset-out cross-validation
# ──────────────────────────────────────────────────────────────

def loo_cv_platt(
    all_data: dict[str, tuple[list[float], list[bool]]],
) -> dict[str, dict]:
    """Leave-one-dataset-out Platt scaling.

    For each dataset, fit on all OTHER datasets, eval on held-out.

    Returns: dict[dataset -> {calibrator, calibrated_confs, correct, ece_before, ece_after}]
    """
    results = {}

    for held_out, (held_confs, held_correct) in all_data.items():
        if not held_confs:
            continue

        # Fit on all other datasets
        train_confs = []
        train_correct = []
        for ds, (confs, corr) in all_data.items():
            if ds != held_out:
                train_confs.extend(confs)
                train_correct.extend(corr)

        if len(train_confs) < 10:
            # Not enough training data, skip LOO for this one
            continue

        # Check that training data has both classes
        if len(set(train_correct)) < 2:
            continue

        cal = PlattCalibrator()
        cal.fit(train_confs, train_correct)

        calibrated = cal.transform_batch(held_confs)

        # ECE before and after
        ece_before = compute_calibration(held_confs, held_correct).ece
        ece_after = compute_calibration(calibrated, held_correct).ece

        results[held_out] = {
            "calibrator": cal,
            "calibrated_confs": calibrated,
            "correct": held_correct,
            "raw_confs": held_confs,
            "ece_before": ece_before,
            "ece_after": ece_after,
        }

    return results


def pooled_platt(
    all_data: dict[str, tuple[list[float], list[bool]]],
) -> dict[str, dict]:
    """Pooled Platt scaling: fit on all data, eval per dataset."""
    pool_confs = []
    pool_correct = []
    for confs, corr in all_data.values():
        pool_confs.extend(confs)
        pool_correct.extend(corr)

    if len(pool_confs) < 10 or len(set(pool_correct)) < 2:
        return {}

    cal = PlattCalibrator()
    cal.fit(pool_confs, pool_correct)

    results = {}
    for ds, (confs, corr) in all_data.items():
        if not confs:
            continue
        calibrated = cal.transform_batch(confs)
        ece_before = compute_calibration(confs, corr).ece
        ece_after = compute_calibration(calibrated, corr).ece
        results[ds] = {
            "calibrator": cal,
            "calibrated_confs": calibrated,
            "correct": corr,
            "raw_confs": confs,
            "ece_before": ece_before,
            "ece_after": ece_after,
        }

    return results


# ──────────────────────────────────────────────────────────────
# 5-fold CV within each dataset
# ──────────────────────────────────────────────────────────────

def kfold_cv_platt(
    confidences: list[float], correct: list[bool], k: int = 5, seed: int = 42,
) -> dict:
    """K-fold CV Platt scaling within a single dataset."""
    n = len(confidences)
    if n < k * 2:
        return {}

    rng = np.random.RandomState(seed)
    indices = rng.permutation(n)
    fold_size = n // k

    all_calibrated = [0.0] * n
    all_raw = list(confidences)

    for fold in range(k):
        test_start = fold * fold_size
        test_end = test_start + fold_size if fold < k - 1 else n
        test_idx = indices[test_start:test_end]
        train_idx = np.concatenate([indices[:test_start], indices[test_end:]])

        train_confs = [confidences[i] for i in train_idx]
        train_corr = [correct[i] for i in train_idx]

        if len(set(train_corr)) < 2:
            for i in test_idx:
                all_calibrated[i] = confidences[i]
            continue

        cal = PlattCalibrator()
        cal.fit(train_confs, train_corr)
        for i in test_idx:
            all_calibrated[i] = cal.transform(confidences[i])

    ece_before = compute_calibration(all_raw, correct).ece
    ece_after = compute_calibration(all_calibrated, correct).ece
    aurc_before = aurc(all_raw, correct)
    aurc_after = aurc(all_calibrated, correct)

    return {
        "ece_before": round(ece_before, 4),
        "ece_after": round(ece_after, 4),
        "aurc_before": round(aurc_before, 4),
        "aurc_after": round(aurc_after, 4),
    }


# ──────────────────────────────────────────────────────────────
# Analysis & reporting
# ──────────────────────────────────────────────────────────────

def analyze_one_condition(
    condition: str,
    dataset_data: dict[str, tuple[list[float], list[bool]]],
    output_dir: Path,
) -> dict:
    """Full analysis for one condition (mode) across datasets."""
    # --- Per-dataset raw metrics ---
    raw_metrics = {}
    for ds, (confs, corr) in dataset_data.items():
        if not confs:
            continue
        n = len(confs)
        n_correct = sum(corr)
        acc = n_correct / n if n > 0 else 0
        raw_ece = compute_calibration(confs, corr).ece
        raw_aurc = aurc(confs, corr)

        # Risk-coverage before calibration
        rc_before = compute_risk_coverage_curve(confs, corr, n_points=20)

        # Selective accuracy before calibration
        sel_50_raw = selective_accuracy(confs, corr, 0.5)
        sel_60_raw = selective_accuracy(confs, corr, 0.6)
        sel_70_raw = selective_accuracy(confs, corr, 0.7)
        sel_80_raw = selective_accuracy(confs, corr, 0.8)
        sel_90_raw = selective_accuracy(confs, corr, 0.9)

        raw_metrics[ds] = {
            "n": n,
            "accuracy": round(acc, 4),
            "ece": round(raw_ece, 4),
            "aurc": round(raw_aurc, 4),
            "mean_confidence": round(sum(confs) / n, 4) if n > 0 else 0,
            "risk_coverage": rc_before,
            "selective_acc_50": round(sel_50_raw["accuracy"], 4),
            "selective_acc_60": round(sel_60_raw["accuracy"], 4),
            "selective_acc_70": round(sel_70_raw["accuracy"], 4),
            "selective_acc_80": round(sel_80_raw["accuracy"], 4),
            "selective_acc_90": round(sel_90_raw["accuracy"], 4),
        }

    # --- LOO-CV Platt scaling ---
    loo_results = loo_cv_platt(dataset_data)
    loo_metrics = {}
    for ds, res in loo_results.items():
        cal_confs = res["calibrated_confs"]
        corr = res["correct"]
        cal_aurc = aurc(cal_confs, corr)
        rc_after = compute_risk_coverage_curve(cal_confs, corr, n_points=20)

        sel_50 = selective_accuracy(cal_confs, corr, 0.5)
        sel_60 = selective_accuracy(cal_confs, corr, 0.6)
        sel_70 = selective_accuracy(cal_confs, corr, 0.7)
        sel_80 = selective_accuracy(cal_confs, corr, 0.8)
        sel_90 = selective_accuracy(cal_confs, corr, 0.9)

        loo_metrics[ds] = {
            "ece_before": round(res["ece_before"], 4),
            "ece_after": round(res["ece_after"], 4),
            "ece_delta": round(res["ece_after"] - res["ece_before"], 4),
            "aurc_before": raw_metrics.get(ds, {}).get("aurc", 0),
            "aurc_after": round(cal_aurc, 4),
            "aurc_delta": round(
                cal_aurc - raw_metrics.get(ds, {}).get("aurc", 0), 4
            ),
            "platt_a": round(res["calibrator"].a, 4),
            "platt_b": round(res["calibrator"].b, 4),
            "optimal_threshold": round(res["calibrator"].optimal_threshold, 4),
            "selective_acc_50": round(sel_50["accuracy"], 4),
            "selective_acc_60": round(sel_60["accuracy"], 4),
            "selective_acc_70": round(sel_70["accuracy"], 4),
            "selective_acc_80": round(sel_80["accuracy"], 4),
            "selective_acc_90": round(sel_90["accuracy"], 4),
            "risk_coverage": rc_after,
        }

        # Save Platt parameters
        cal_dir = output_dir / condition
        cal_dir.mkdir(parents=True, exist_ok=True)
        res["calibrator"].save(cal_dir / f"platt_{ds}.json")

    # --- 5-fold CV within each dataset ---
    kfold_metrics = {}
    for ds, (confs, corr) in dataset_data.items():
        if not confs or len(confs) < 20:
            continue
        kfold_metrics[ds] = kfold_cv_platt(confs, corr)

    # --- Pooled Platt scaling ---
    pooled_results = pooled_platt(dataset_data)
    pooled_metrics = {}
    for ds, res in pooled_results.items():
        cal_confs = res["calibrated_confs"]
        corr = res["correct"]
        cal_aurc = aurc(cal_confs, corr)
        pooled_metrics[ds] = {
            "ece_before": round(res["ece_before"], 4),
            "ece_after": round(res["ece_after"], 4),
            "aurc_after": round(cal_aurc, 4),
        }

    return {
        "condition": condition,
        "raw": raw_metrics,
        "loo_cv": loo_metrics,
        "kfold_cv": kfold_metrics,
        "pooled": pooled_metrics,
    }


def print_summary(results: list[dict]) -> None:
    """Print human-readable summary."""
    print("\n" + "=" * 80)
    print("PLATT SCALING + RISK-COVERAGE ANALYSIS")
    print("=" * 80)

    for res in results:
        cond = res["condition"]
        print(f"\n{'─' * 70}")
        print(f"Condition: {cond}")
        print(f"{'─' * 70}")

        # Raw metrics
        header = f"  {'Dataset':15s} {'N':>5s} {'Acc':>7s} {'ECE':>7s} {'AURC':>7s} {'MeanConf':>9s}"
        print(f"\n{header}")
        print(f"  {'-'*15} {'-'*5} {'-'*7} {'-'*7} {'-'*7} {'-'*9}")
        for ds, m in res["raw"].items():
            print(f"  {ds:15s} {m['n']:5d} {m['accuracy']:7.4f} "
                  f"{m['ece']:7.4f} {m['aurc']:7.4f} {m['mean_confidence']:9.4f}")

        # LOO-CV results
        if res["loo_cv"]:
            print(f"\n  LOO-CV Platt Scaling:")
            print(f"  {'Dataset':15s} {'ECE_raw':>8s} {'ECE_platt':>10s} {'ΔECE':>7s} "
                  f"{'AURC_raw':>9s} {'AURC_platt':>11s} {'ΔAURC':>7s} {'Thresh':>7s}")
            print(f"  {'-'*15} {'-'*8} {'-'*10} {'-'*7} "
                  f"{'-'*9} {'-'*11} {'-'*7} {'-'*7}")
            for ds, m in res["loo_cv"].items():
                print(f"  {ds:15s} {m['ece_before']:8.4f} {m['ece_after']:10.4f} "
                      f"{m['ece_delta']:+7.4f} {m['aurc_before']:9.4f} "
                      f"{m['aurc_after']:11.4f} {m['aurc_delta']:+7.4f} "
                      f"{m['optimal_threshold']:7.4f}")

        # Selective accuracy comparison (raw vs calibrated)
        if res["loo_cv"]:
            print(f"\n  Selective Accuracy (raw → LOO-CV calibrated):")
            print(f"  {'Dataset':15s} {'Cov':>5s} {'Raw':>7s} {'Platt':>7s} {'Δ':>7s}")
            print(f"  {'-'*15} {'-'*5} {'-'*7} {'-'*7} {'-'*7}")
            for ds in res["loo_cv"]:
                raw_m = res["raw"].get(ds, {})
                loo_m = res["loo_cv"][ds]
                for cov in [50, 60, 70, 80, 90]:
                    raw_acc = raw_m.get(f"selective_acc_{cov}", 0)
                    platt_acc = loo_m.get(f"selective_acc_{cov}", 0)
                    delta = platt_acc - raw_acc
                    label = f"{ds}" if cov == 50 else ""
                    print(f"  {label:15s} {cov:4d}% {raw_acc:7.4f} "
                          f"{platt_acc:7.4f} {delta:+7.4f}")
                print()

        # 5-fold CV
        if res["kfold_cv"]:
            print(f"  5-Fold CV (within-dataset):")
            print(f"  {'Dataset':15s} {'ECE_raw':>8s} {'ECE_5cv':>8s} "
                  f"{'AURC_raw':>9s} {'AURC_5cv':>9s}")
            print(f"  {'-'*15} {'-'*8} {'-'*8} {'-'*9} {'-'*9}")
            for ds, m in res["kfold_cv"].items():
                print(f"  {ds:15s} {m['ece_before']:8.4f} {m['ece_after']:8.4f} "
                      f"{m['aurc_before']:9.4f} {m['aurc_after']:9.4f}")

        # Platt parameters
        if res["loo_cv"]:
            print(f"\n  Platt Parameters (LOO-CV, fitted on other datasets):")
            for ds, m in res["loo_cv"].items():
                print(f"  {ds:15s}  a={m['platt_a']:+.4f}  b={m['platt_b']:+.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Post-hoc Platt scaling + risk-coverage analysis"
    )
    parser.add_argument(
        "--sweep-dirs", nargs="*", default=None,
        help="Sweep directories to analyze (default: auto-discover)",
    )
    parser.add_argument(
        "--output", default="outputs/platt_calibration",
        help="Output directory for results and Platt parameters",
    )
    parser.add_argument(
        "--conditions", nargs="*", default=None,
        help="Filter to specific conditions (e.g. hied_no_evidence)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Auto-discover sweep directories
    if args.sweep_dirs:
        sweep_dirs = [Path(d) for d in args.sweep_dirs]
    else:
        sweeps_root = Path("outputs/sweeps")
        preferred = [
            "v10_lingxidiag_20260320_222603",
            "v10_mdd5k_20260320_233729",
            "evidence_lingxidiag_20260321_222749",
            "evidence_mdd5k_20260322_154253",
            "evidence_edaic_20260323_011113",
            "contrastive_off_lingxidiag_20260321_105016",
            "contrastive_off_mdd5k_20260321_131315",
        ]
        sweep_dirs = [sweeps_root / d for d in preferred if (sweeps_root / d).exists()]

    if not sweep_dirs:
        print("ERROR: No sweep directories found.")
        sys.exit(1)

    print(f"Loading {len(sweep_dirs)} sweep directories...")

    # Load all data: condition -> dataset -> (confs, correct)
    condition_data: dict[str, dict[str, tuple[list[float], list[bool]]]] = defaultdict(dict)
    sweep_info = []

    for sweep_dir in sweep_dirs:
        data = load_sweep_data(sweep_dir)
        if not data:
            print(f"  SKIP: {sweep_dir.name} (no case_list.json or bad format)")
            continue

        dataset = data["dataset"]
        gold = data["gold"]
        n_gold = len(gold)

        if not gold:
            print(f"  SKIP: {sweep_dir.name} (no gold labels)")
            continue

        for cond_name, preds in data["conditions"].items():
            if args.conditions and cond_name not in args.conditions:
                continue

            confs, correct, n_valid, n_abstain = extract_conf_correct(preds, gold)

            ds_key = dataset

            # Keep the larger dataset if duplicates
            if ds_key in condition_data[cond_name]:
                existing_confs, _ = condition_data[cond_name][ds_key]
                if len(confs) <= len(existing_confs):
                    continue

            condition_data[cond_name][ds_key] = (confs, correct)

            sweep_info.append({
                "sweep": sweep_dir.name,
                "dataset": dataset,
                "condition": cond_name,
                "n_gold": n_gold,
                "n_valid": n_valid,
                "n_abstain": n_abstain,
            })

    print(f"\nLoaded data:")
    for info in sweep_info:
        print(f"  {info['sweep']:50s}  {info['condition']:30s}  "
              f"dataset={info['dataset']:12s}  n={info['n_valid']:4d}  "
              f"abstain={info['n_abstain']:3d}")

    # Analyze each condition
    results = []
    for cond_name in sorted(condition_data.keys()):
        ds_data = condition_data[cond_name]
        if len(ds_data) < 1:
            continue
        res = analyze_one_condition(cond_name, ds_data, output_dir)
        results.append(res)

    # Print summary
    print_summary(results)

    # Save full results (strip non-serializable calibrator objects)
    save_results = []
    for res in results:
        save_results.append({
            "condition": res["condition"],
            "raw": res["raw"],
            "loo_cv": res["loo_cv"],
            "kfold_cv": res["kfold_cv"],
            "pooled": res["pooled"],
        })

    out_path = output_dir / "platt_calibration_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(save_results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")

    # Summary table
    summary = []
    for res in results:
        for ds, raw in res["raw"].items():
            loo = res["loo_cv"].get(ds, {})
            kf = res["kfold_cv"].get(ds, {})
            row = {
                "condition": res["condition"],
                "dataset": ds,
                "n": raw["n"],
                "accuracy": raw["accuracy"],
                "ece_raw": raw["ece"],
                "ece_loo": loo.get("ece_after"),
                "ece_5fold": kf.get("ece_after"),
                "aurc_raw": raw["aurc"],
                "aurc_loo": loo.get("aurc_after"),
                "aurc_5fold": kf.get("aurc_after"),
                "selective_acc_80_raw": raw.get("selective_acc_80"),
                "selective_acc_80_platt": loo.get("selective_acc_80"),
                "optimal_threshold": loo.get("optimal_threshold"),
            }
            summary.append(row)

    summary_path = output_dir / "summary_table.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"Summary table saved to {summary_path}")

    # Save risk-coverage data for plotting
    rc_data = {}
    for res in results:
        cond = res["condition"]
        rc_data[cond] = {}
        for ds, raw in res["raw"].items():
            rc_data[cond][f"{ds}_raw"] = raw.get("risk_coverage", [])
        for ds, loo in res["loo_cv"].items():
            rc_data[cond][f"{ds}_platt"] = loo.get("risk_coverage", [])

    rc_path = output_dir / "risk_coverage_data.json"
    with open(rc_path, "w", encoding="utf-8") as f:
        json.dump(rc_data, f, indent=2, ensure_ascii=False)
    print(f"Risk-coverage data saved to {rc_path}")


if __name__ == "__main__":
    main()
