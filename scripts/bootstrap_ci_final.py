#!/usr/bin/env python3
"""Bootstrap confidence intervals for CultureDx final sweep results.

Computes bootstrap CIs (B=10,000, seed=42, percentile method, 95% CI) for:
  - Top-1 accuracy (parent-normalized)
  - Top-3 accuracy (parent-normalized)
  - Macro F1
  - Per-disorder recall for F32 and F41

Also computes paired bootstrap CIs for key deltas (evidence, somatization, MAS).

Usage:
    uv run python scripts/bootstrap_ci_final.py
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
B = 10_000
SEED = 42
CI_ALPHA = 0.05

CONDITIONS: list[str] = [
    "hied_no_evidence",
    "hied_bge-m3_evidence",
    "hied_bge-m3_no_somatization",
    "psycot_no_evidence",
    "psycot_bge-m3_evidence",
    "psycot_bge-m3_no_somatization",
    "single_no_evidence",
    "single_bge-m3_evidence",
    "single_bge-m3_no_somatization",
]

DATASETS: dict[str, str] = {
    "lingxidiag": "outputs/sweeps/final_lingxidiag_20260323_131847",
    "mdd5k": "outputs/sweeps/final_mdd5k_20260324_120113",
}

# Parent-code mapping: map sub-codes to their parent.
# Gold F32.1 matches predicted F32 or F33.
# Gold F41.1 matches predicted F41.1 or F41.
PARENT_MAP: dict[str, str] = {
    "F32": "F32",
    "F32.0": "F32",
    "F32.1": "F32",
    "F32.2": "F32",
    "F32.3": "F32",
    "F33": "F32",
    "F33.0": "F32",
    "F33.1": "F32",
    "F33.2": "F32",
    "F33.3": "F32",
    "F41": "F41",
    "F41.0": "F41",
    "F41.1": "F41",
    "F41.2": "F41",
    "F41.9": "F41",
}


def _parent(code: str | None) -> str | None:
    """Normalize an ICD code to its parent group."""
    if code is None or code == "None":
        return None
    return PARENT_MAP.get(code, code)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_gold_labels(base: Path) -> dict[str, list[str]]:
    """Load gold labels from case_list.json.

    Returns {case_id: [parent codes]}.
    """
    path = base / "case_list.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    gold: dict[str, list[str]] = {}
    for case in data["cases"]:
        cid = str(case["case_id"])
        parents: list[str] = []
        for dx in case["diagnoses"]:
            p = _parent(dx)
            if p is not None and p not in parents:
                parents.append(p)
        gold[cid] = parents
    return gold


def load_predictions(
    base: Path, condition: str,
) -> dict[str, list[str]]:
    """Load predictions for a condition.

    Returns {case_id: [ranked parent codes]}.
    """
    path = base / condition / "predictions.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    preds: dict[str, list[str]] = {}
    for pred in data["predictions"]:
        cid = str(pred["case_id"])
        ranked: list[str] = []
        # Primary diagnosis is rank-1
        primary = pred.get("primary_diagnosis")
        p_primary = _parent(primary)
        if p_primary is not None:
            ranked.append(p_primary)
        # Comorbid diagnoses follow
        for dx in pred.get("comorbid_diagnoses", []):
            p_dx = _parent(dx)
            if p_dx is not None and p_dx not in ranked:
                ranked.append(p_dx)
        preds[cid] = ranked
    return preds


# ---------------------------------------------------------------------------
# Metric computation (vectorized per-case)
# ---------------------------------------------------------------------------
def compute_case_metrics(
    gold: dict[str, list[str]],
    preds: dict[str, list[str]],
) -> dict[str, np.ndarray]:
    """Compute per-case binary indicators for each metric.

    Returns dict with arrays of shape (n_cases,) for:
      top1, top3, and per-disorder arrays for macro-F1 components.
    """
    case_ids = sorted(gold.keys())
    n = len(case_ids)

    top1 = np.zeros(n, dtype=np.float64)
    top3 = np.zeros(n, dtype=np.float64)

    # For macro-F1 we need per-class TP, FP, FN per case
    all_classes: set[str] = set()
    for g in gold.values():
        all_classes.update(g)
    for p in preds.values():
        all_classes.update(p)
    all_classes_sorted = sorted(all_classes)

    # Per-case, per-class: tp, fp, fn
    tp = np.zeros((n, len(all_classes_sorted)), dtype=np.float64)
    fp = np.zeros((n, len(all_classes_sorted)), dtype=np.float64)
    fn = np.zeros((n, len(all_classes_sorted)), dtype=np.float64)
    class_idx = {c: i for i, c in enumerate(all_classes_sorted)}

    # Per-disorder recall tracking for F32 and F41
    f32_correct = np.zeros(n, dtype=np.float64)
    f32_present = np.zeros(n, dtype=np.float64)
    f41_correct = np.zeros(n, dtype=np.float64)
    f41_present = np.zeros(n, dtype=np.float64)

    for idx, cid in enumerate(case_ids):
        g_set = set(gold[cid])
        p_list = preds.get(cid, [])
        p_top1 = set(p_list[:1])
        p_top3 = set(p_list[:3])

        # Top-1: any gold label matched by top-1 prediction
        if g_set & p_top1:
            top1[idx] = 1.0
        # Top-3: any gold label matched by top-3 predictions
        if g_set & p_top3:
            top3[idx] = 1.0

        # For F1: use top-1 prediction as the "predicted set"
        for c in all_classes_sorted:
            ci = class_idx[c]
            in_gold = c in g_set
            in_pred = c in p_top1
            if in_gold and in_pred:
                tp[idx, ci] = 1.0
            elif in_pred and not in_gold:
                fp[idx, ci] = 1.0
            elif in_gold and not in_pred:
                fn[idx, ci] = 1.0

        # Per-disorder recall
        if "F32" in g_set:
            f32_present[idx] = 1.0
            if "F32" in p_top1:
                f32_correct[idx] = 1.0
        if "F41" in g_set:
            f41_present[idx] = 1.0
            if "F41" in p_top1:
                f41_correct[idx] = 1.0

    return {
        "case_ids": case_ids,
        "top1": top1,
        "top3": top3,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "classes": all_classes_sorted,
        "f32_correct": f32_correct,
        "f32_present": f32_present,
        "f41_correct": f41_correct,
        "f41_present": f41_present,
    }


def aggregate_metrics(
    metrics: dict[str, np.ndarray],
    indices: np.ndarray | None = None,
) -> dict[str, float]:
    """Aggregate per-case metrics into summary statistics.

    If indices is given, subset to those rows (for bootstrap).
    """
    if indices is not None:
        top1 = metrics["top1"][indices]
        top3 = metrics["top3"][indices]
        tp = metrics["tp"][indices]
        fp = metrics["fp"][indices]
        fn = metrics["fn"][indices]
        f32_c = metrics["f32_correct"][indices]
        f32_p = metrics["f32_present"][indices]
        f41_c = metrics["f41_correct"][indices]
        f41_p = metrics["f41_present"][indices]
    else:
        top1 = metrics["top1"]
        top3 = metrics["top3"]
        tp = metrics["tp"]
        fp = metrics["fp"]
        fn = metrics["fn"]
        f32_c = metrics["f32_correct"]
        f32_p = metrics["f32_present"]
        f41_c = metrics["f41_correct"]
        f41_p = metrics["f41_present"]

    acc_top1 = float(np.mean(top1))
    acc_top3 = float(np.mean(top3))

    # Macro F1: per-class F1, then average
    tp_sum = tp.sum(axis=0)
    fp_sum = fp.sum(axis=0)
    fn_sum = fn.sum(axis=0)

    f1s: list[float] = []
    for i in range(tp_sum.shape[0]):
        if tp_sum[i] + fp_sum[i] + fn_sum[i] == 0:
            continue  # class not present in this sample
        prec = (
            tp_sum[i] / (tp_sum[i] + fp_sum[i])
            if (tp_sum[i] + fp_sum[i]) > 0
            else 0.0
        )
        rec = (
            tp_sum[i] / (tp_sum[i] + fn_sum[i])
            if (tp_sum[i] + fn_sum[i]) > 0
            else 0.0
        )
        f1 = (
            2 * prec * rec / (prec + rec)
            if (prec + rec) > 0
            else 0.0
        )
        f1s.append(f1)
    macro_f1 = float(np.mean(f1s)) if f1s else 0.0

    f32_recall = (
        float(f32_c.sum() / f32_p.sum()) if f32_p.sum() > 0 else 0.0
    )
    f41_recall = (
        float(f41_c.sum() / f41_p.sum()) if f41_p.sum() > 0 else 0.0
    )

    return {
        "top1_acc": acc_top1,
        "top3_acc": acc_top3,
        "macro_f1": macro_f1,
        "f32_recall": f32_recall,
        "f41_recall": f41_recall,
    }


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
def bootstrap_ci(
    metrics: dict[str, np.ndarray],
    rng: np.random.Generator,
    b: int = B,
    alpha: float = CI_ALPHA,
) -> dict[str, dict[str, float]]:
    """Compute bootstrap CIs for all metrics.

    Returns {metric_name: {point, lo, hi}}.
    """
    n = len(metrics["top1"])
    point = aggregate_metrics(metrics)

    boot_results: dict[str, list[float]] = defaultdict(list)
    for _ in range(b):
        idx = rng.integers(0, n, size=n)
        agg = aggregate_metrics(metrics, idx)
        for k, v in agg.items():
            boot_results[k].append(v)

    result: dict[str, dict[str, float]] = {}
    for k in point:
        arr = np.array(boot_results[k])
        lo = float(np.percentile(arr, 100 * alpha / 2))
        hi = float(np.percentile(arr, 100 * (1 - alpha / 2)))
        result[k] = {"point": point[k], "lo": lo, "hi": hi}

    return result


def paired_bootstrap_delta(
    metrics_a: dict[str, np.ndarray],
    metrics_b: dict[str, np.ndarray],
    rng: np.random.Generator,
    b: int = B,
    alpha: float = CI_ALPHA,
) -> dict[str, dict[str, float]]:
    """Paired bootstrap for delta = A - B on each metric.

    Returns {metric_name: {delta, lo, hi, excludes_zero}}.
    """
    n = len(metrics_a["top1"])
    point_a = aggregate_metrics(metrics_a)
    point_b = aggregate_metrics(metrics_b)

    boot_deltas: dict[str, list[float]] = defaultdict(list)
    for _ in range(b):
        idx = rng.integers(0, n, size=n)
        agg_a = aggregate_metrics(metrics_a, idx)
        agg_b = aggregate_metrics(metrics_b, idx)
        for k in agg_a:
            boot_deltas[k].append(agg_a[k] - agg_b[k])

    result: dict[str, dict[str, float]] = {}
    for k in point_a:
        delta = point_a[k] - point_b[k]
        arr = np.array(boot_deltas[k])
        lo = float(np.percentile(arr, 100 * alpha / 2))
        hi = float(np.percentile(arr, 100 * (1 - alpha / 2)))
        excludes_zero = bool(lo > 0 or hi < 0)
        result[k] = {
            "delta": delta,
            "lo": lo,
            "hi": hi,
            "excludes_zero": excludes_zero,
        }

    return result


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def fmt_ci(d: dict[str, float], pct: bool = True) -> str:
    """Format a point estimate with CI."""
    mult = 100.0 if pct else 1.0
    suffix = "%" if pct else ""
    return (
        f"{d['point'] * mult:.1f}{suffix} "
        f"[{d['lo'] * mult:.1f}, {d['hi'] * mult:.1f}]"
    )


def fmt_delta(d: dict[str, float], pct: bool = True) -> str:
    """Format a delta with CI."""
    mult = 100.0 if pct else 1.0
    suffix = "%" if pct else ""
    sig = "*" if d["excludes_zero"] else ""
    sign = "+" if d["delta"] >= 0 else ""
    return (
        f"{sign}{d['delta'] * mult:.1f}{suffix} "
        f"[{d['lo'] * mult:.1f}, {d['hi'] * mult:.1f}]{sig}"
    )


def generate_markdown(
    all_cis: dict[str, dict[str, dict[str, dict[str, float]]]],
    all_deltas: dict[str, dict[str, dict[str, dict[str, float]]]],
) -> str:
    """Generate markdown report."""
    lines: list[str] = []
    lines.append("# CultureDx Final Sweep \u2014 Bootstrap CIs")
    lines.append("")
    lines.append(f"B = {B:,}, seed = {SEED}, 95% percentile CI")
    lines.append("")

    metric_names = [
        "top1_acc", "top3_acc", "macro_f1",
        "f32_recall", "f41_recall",
    ]
    metric_labels = {
        "top1_acc": "Top-1 Acc",
        "top3_acc": "Top-3 Acc",
        "macro_f1": "Macro F1",
        "f32_recall": "F32 Recall",
        "f41_recall": "F41 Recall",
    }

    for ds_name in sorted(all_cis.keys()):
        ds_cis = all_cis[ds_name]
        lines.append(f"## {ds_name}")
        lines.append("")

        # Header
        header = "| Condition | " + " | ".join(
            metric_labels[m] for m in metric_names
        ) + " |"
        sep = (
            "|" + "|".join(["---"] * (len(metric_names) + 1)) + "|"
        )
        lines.append(header)
        lines.append(sep)

        for cond in CONDITIONS:
            cis = ds_cis[cond]
            cells = " | ".join(
                fmt_ci(cis[m]) for m in metric_names
            )
            lines.append(f"| {cond} | {cells} |")
        lines.append("")

        # Deltas
        lines.append(f"### Paired Deltas \u2014 {ds_name}")
        lines.append("")
        lines.append(header)
        lines.append(sep)

        ds_deltas = all_deltas[ds_name]
        for comp_name, deltas in ds_deltas.items():
            cells = " | ".join(
                fmt_delta(deltas[m]) for m in metric_names
            )
            lines.append(f"| {comp_name} | {cells} |")
        lines.append("")
        lines.append("\\* CI excludes 0 (significant at 95%)")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap CIs for CultureDx final sweep.",
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default=".",
        help="Project root directory (default: cwd).",
    )
    parser.add_argument(
        "--bootstrap-b",
        type=int,
        default=B,
        help=f"Number of bootstrap resamples (default: {B}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=SEED,
        help=f"Random seed (default: {SEED}).",
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    b = args.bootstrap_b
    seed = args.seed

    rng = np.random.default_rng(seed)

    all_cis: dict[
        str, dict[str, dict[str, dict[str, float]]]
    ] = {}
    all_deltas: dict[
        str, dict[str, dict[str, dict[str, float]]]
    ] = {}
    all_metrics_cache: dict[
        str, dict[str, dict[str, np.ndarray]]
    ] = {}

    for ds_name, ds_rel in DATASETS.items():
        ds_path = base_dir / ds_rel
        logger.info(
            "Loading dataset: %s from %s", ds_name, ds_path,
        )
        gold = load_gold_labels(ds_path)
        logger.info(
            "  Gold labels: %d cases, classes: %s",
            len(gold),
            sorted({c for cs in gold.values() for c in cs}),
        )

        ds_cis: dict[str, dict[str, dict[str, float]]] = {}
        ds_metrics: dict[str, dict[str, np.ndarray]] = {}

        for cond in CONDITIONS:
            logger.info("  Condition: %s", cond)
            preds = load_predictions(ds_path, cond)
            metrics = compute_case_metrics(gold, preds)
            ds_metrics[cond] = metrics

            ci = bootstrap_ci(metrics, rng, b=b)
            ds_cis[cond] = ci

            point = aggregate_metrics(metrics)
            logger.info(
                "    Top-1=%.1f%% Top-3=%.1f%% F1=%.3f "
                "F32-R=%.1f%% F41-R=%.1f%%",
                point["top1_acc"] * 100,
                point["top3_acc"] * 100,
                point["macro_f1"],
                point["f32_recall"] * 100,
                point["f41_recall"] * 100,
            )

        all_cis[ds_name] = ds_cis
        all_metrics_cache[ds_name] = ds_metrics

        # Paired deltas
        comparisons: dict[str, tuple[str, str]] = {
            "Evidence (hied+ev vs hied-noev)": (
                "hied_bge-m3_evidence",
                "hied_no_evidence",
            ),
            "Somatization (hied+ev vs hied+ev-nosom)": (
                "hied_bge-m3_evidence",
                "hied_bge-m3_no_somatization",
            ),
            "MAS (hied-noev vs single-noev)": (
                "hied_no_evidence",
                "single_no_evidence",
            ),
        }

        ds_deltas: dict[
            str, dict[str, dict[str, float]]
        ] = {}
        for comp_name, (cond_a, cond_b) in comparisons.items():
            logger.info("  Delta: %s", comp_name)
            delta = paired_bootstrap_delta(
                ds_metrics[cond_a],
                ds_metrics[cond_b],
                rng,
                b=b,
            )
            ds_deltas[comp_name] = delta

            for m, d in delta.items():
                sig = "SIG" if d["excludes_zero"] else "ns"
                logger.info(
                    "    %s: %+.1f%% [%.1f, %.1f] %s",
                    m,
                    d["delta"] * 100,
                    d["lo"] * 100,
                    d["hi"] * 100,
                    sig,
                )

        all_deltas[ds_name] = ds_deltas

    # ---- Output ----
    out_dir = base_dir / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    # JSON output
    json_out: dict[str, Any] = {
        "bootstrap_b": b,
        "seed": seed,
        "ci_alpha": CI_ALPHA,
        "datasets": {},
    }
    for ds_name in sorted(all_cis.keys()):
        ds_entry: dict[str, Any] = {
            "conditions": {},
            "deltas": {},
        }
        for cond in CONDITIONS:
            ds_entry["conditions"][cond] = all_cis[ds_name][cond]
        for comp_name, delta_val in all_deltas[ds_name].items():
            ds_entry["deltas"][comp_name] = delta_val
        json_out["datasets"][ds_name] = ds_entry

    json_path = out_dir / "bootstrap_ci_final.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_out, f, indent=2, ensure_ascii=False)
    logger.info("JSON written to %s", json_path)

    # Markdown output
    md_content = generate_markdown(all_cis, all_deltas)
    md_path = out_dir / "bootstrap_ci_final.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    logger.info("Markdown written to %s", md_path)


if __name__ == "__main__":
    main()
