#!/usr/bin/env python3
"""Offline tuning of comorbidity confidence thresholds.

Re-evaluates existing predictions at different comorbidity thresholds
to find the optimal setting that minimizes Mixed class false positives
while preserving comorbidity detection.

Usage:
    uv run python scripts/tune_comorbidity_threshold.py
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.core.models import CheckerOutput, CriterionResult
from culturedx.diagnosis.calibrator import ConfidenceCalibrator
from culturedx.diagnosis.comorbidity import ComorbidityResolver
from culturedx.diagnosis.logic_engine import DiagnosticLogicEngine
from culturedx.eval.metrics import compute_comorbidity_metrics

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

SWEEP_PATHS = [
    (
        "final_lingxidiag",
        "outputs/sweeps/final_lingxidiag_20260323_131847",
    ),
    (
        "v10_lingxidiag",
        "outputs/sweeps/v10_lingxidiag_20260320_222603",
    ),
    (
        "v10_mdd5k",
        "outputs/sweeps/v10_mdd5k_20260320_233729",
    ),
    (
        "n200_3mode",
        "outputs/sweeps/n200_3mode_20260320_131920",
    ),
    (
        "lingxidiag_crossval",
        "outputs/sweeps/lingxidiag_3mode_crossval_20260320_195057",
    ),
]

ABSOLUTE_THRESHOLDS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
RATIO_THRESHOLDS = [0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

# 4-class category codes
MOOD_CODES = {"F32", "F33"}
ANXIETY_CODES = {"F40", "F41"}


def reconstruct_checker_outputs(pred: dict) -> list[CheckerOutput]:
    """Reconstruct CheckerOutput objects from prediction criteria_results."""
    outputs = []
    criteria_results = pred.get("criteria_results", [])

    for cr_data in criteria_results:
        if isinstance(cr_data, dict):
            criteria = []
            for c in cr_data.get("criteria", []):
                criteria.append(CriterionResult(
                    criterion_id=c.get("criterion_id", ""),
                    status=c.get("status", "not_met"),
                    confidence=c.get("confidence", 0.0),
                    evidence=c.get("evidence", ""),
                ))
            outputs.append(CheckerOutput(
                disorder=cr_data.get("disorder", ""),
                criteria=criteria,
                criteria_met_count=cr_data.get("criteria_met_count", 0),
                criteria_required=cr_data.get("criteria_required", 0),
            ))

    return outputs


def recompute_diagnoses(
    checker_outputs: list[CheckerOutput],
) -> tuple[list[str], dict[str, float], dict[str, str]]:
    """Run logic engine + calibrator to get confirmed disorders and confidences.

    Returns:
        (confirmed_codes, confidences_dict, confirmation_types_dict)
    """
    engine = DiagnosticLogicEngine()
    logic_output = engine.evaluate(checker_outputs)

    if not logic_output.confirmed:
        return [], {}, {}

    confirmation_types = {
        r.disorder_code: r.confirmation_type
        for r in logic_output.confirmed
    }

    cal = ConfidenceCalibrator(abstain_threshold=0.3, comorbid_threshold=0.5)
    cal_output = cal.calibrate(
        confirmed_disorders=logic_output.confirmed_codes,
        checker_outputs=checker_outputs,
        evidence=None,
        confirmation_types=confirmation_types,
    )

    confirmed_codes = []
    confidences = {}

    if cal_output.primary is not None:
        confirmed_codes.append(cal_output.primary.disorder_code)
        confidences[cal_output.primary.disorder_code] = (
            cal_output.primary.confidence
        )

    for c in cal_output.comorbid:
        confirmed_codes.append(c.disorder_code)
        confidences[c.disorder_code] = c.confidence

    return confirmed_codes, confidences, confirmation_types


def apply_absolute_threshold(
    confirmed: list[str],
    confidences: dict[str, float],
    threshold: float,
) -> list[str]:
    """Filter comorbid disorders by absolute confidence threshold.

    The primary (first) disorder is always kept. Comorbid disorders
    with confidence below the threshold are removed.
    """
    if not confirmed:
        return []
    if threshold <= 0.0:
        return list(confirmed)

    primary = confirmed[0]
    result = [primary]
    for code in confirmed[1:]:
        if confidences.get(code, 0.0) >= threshold:
            result.append(code)
    return result


def apply_ratio_threshold(
    confirmed: list[str],
    confidences: dict[str, float],
    ratio: float,
) -> list[str]:
    """Filter comorbid disorders by confidence ratio relative to primary.

    Uses ComorbidityResolver with comorbid_min_ratio.
    """
    if not confirmed:
        return []
    if ratio <= 0.0:
        return list(confirmed)

    resolver = ComorbidityResolver(
        max_comorbid=3,
        comorbid_min_ratio=ratio,
    )
    result = resolver.resolve(confirmed, confidences)
    all_codes = [result.primary] if result.primary else []
    all_codes.extend(result.comorbid)
    return all_codes


def to_4class(codes: list[str]) -> str:
    """Map a list of ICD-10 codes to 4-class label for LingxiDiag."""
    parent_codes = {c.split(".")[0] for c in codes}
    has_mood = bool(parent_codes & MOOD_CODES)
    has_anxiety = bool(parent_codes & ANXIETY_CODES)

    if has_mood and has_anxiety:
        return "Mixed"
    if has_mood:
        return "Depression"
    if has_anxiety:
        return "Anxiety"
    return "Other"


def load_sweep_data(
    sweep_dir: Path,
) -> list[tuple[dict, list[dict]]] | None:
    """Load gold labels and all hied predictions from a sweep directory.

    Returns list of (gold_map, predictions_list) tuples, one per condition.
    """
    case_list = sweep_dir / "case_list.json"
    if not case_list.exists():
        return None

    with open(case_list, encoding="utf-8") as f:
        case_data = json.load(f)

    if isinstance(case_data, dict) and "cases" in case_data:
        gold = {
            str(c["case_id"]): c["diagnoses"]
            for c in case_data["cases"]
        }
    else:
        return None

    results = []
    # Look for any hied prediction directories
    for cond_dir in sorted(sweep_dir.iterdir()):
        if not cond_dir.is_dir():
            continue
        pred_path = cond_dir / "predictions.json"
        if not pred_path.exists():
            continue
        # Only use hied conditions (the ones with criteria_results)
        if "hied" not in cond_dir.name:
            continue
        with open(pred_path, encoding="utf-8") as f:
            raw = json.load(f)
        preds = raw["predictions"] if isinstance(raw, dict) else raw
        results.append((gold, preds))

    return results if results else None


def evaluate_threshold(
    all_predictions: list[list[str]],
    all_golds: list[list[str]],
    is_lingxidiag: bool,
) -> dict:
    """Evaluate a set of predictions against gold labels."""
    metrics = compute_comorbidity_metrics(
        all_predictions, all_golds, normalize="parent",
    )

    result = {
        "hamming": metrics["hamming_accuracy"],
        "subset": metrics["subset_accuracy"],
        "label_cov": metrics["label_coverage"],
        "label_prec": metrics["label_precision"],
        "avg_pred": metrics["avg_predicted_labels"],
        "comorbid_f1": metrics["comorbidity_detection_f1"],
    }

    if is_lingxidiag:
        pred_4cls = [to_4class(p) for p in all_predictions]
        gold_4cls = [to_4class(g) for g in all_golds]

        # Compute 4-class accuracy
        correct = sum(
            1 for p, g in zip(pred_4cls, gold_4cls) if p == g
        )
        n = len(pred_4cls) if pred_4cls else 1
        result["4class_acc"] = correct / n

        # Per-class precision/recall
        classes = ["Depression", "Anxiety", "Mixed", "Other"]
        for cls in classes:
            tp = sum(
                1 for p, g in zip(pred_4cls, gold_4cls)
                if p == cls and g == cls
            )
            fp = sum(
                1 for p, g in zip(pred_4cls, gold_4cls)
                if p == cls and g != cls
            )
            fn = sum(
                1 for p, g in zip(pred_4cls, gold_4cls)
                if p != cls and g == cls
            )
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            result[f"4cls_{cls}_prec"] = prec
            result[f"4cls_{cls}_rec"] = rec

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tune comorbidity confidence thresholds offline."
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed (default: 42)"
    )
    args = parser.parse_args()

    print("=" * 80)
    print("COMORBIDITY THRESHOLD TUNING")
    print("=" * 80)

    # Collect all data from all sweeps
    all_sweep_data: list[
        tuple[str, dict, list[dict]]
    ] = []  # (label, gold_map, preds)

    for label, sweep_path in SWEEP_PATHS:
        sweep_dir = Path(sweep_path)
        data = load_sweep_data(sweep_dir)
        if data is None:
            logger.info("SKIP: %s (not found or bad format)", label)
            continue

        for gold, preds in data:
            all_sweep_data.append((label, gold, preds))
            logger.info(
                "Loaded %s: %d predictions, %d gold",
                label, len(preds), len(gold),
            )

    if not all_sweep_data:
        logger.error("No sweep data found. Exiting.")
        sys.exit(1)

    logger.info(
        "Total sweep conditions loaded: %d", len(all_sweep_data)
    )

    # Pre-compute recomputed diagnoses for each prediction across all sweeps
    # Structure: list of (label, case_id, confirmed, confidences, gold_codes)
    all_cases: list[
        tuple[str, str, list[str], dict[str, float], list[str]]
    ] = []

    for label, gold, preds in all_sweep_data:
        for pred in preds:
            case_id = str(pred["case_id"])
            if case_id not in gold:
                continue

            gold_codes = gold[case_id]
            checker_outputs = reconstruct_checker_outputs(pred)
            if not checker_outputs:
                continue

            confirmed, confidences, _ = recompute_diagnoses(
                checker_outputs
            )
            if not confirmed:
                continue

            all_cases.append(
                (label, case_id, confirmed, confidences, gold_codes)
            )

    logger.info("Total cases for evaluation: %d", len(all_cases))

    # Split into lingxidiag and non-lingxidiag
    lingxidiag_cases = [
        c for c in all_cases if "lingxidiag" in c[0].lower()
    ]
    non_lingxidiag_cases = [
        c for c in all_cases if "lingxidiag" not in c[0].lower()
    ]

    all_results: dict = {
        "strategy_a_absolute": {},
        "strategy_b_ratio": {},
    }

    # ── Strategy A: Absolute threshold ──
    print("\n" + "─" * 80)
    print("STRATEGY A: ABSOLUTE CONFIDENCE THRESHOLD")
    print("─" * 80)

    header = (
        f"{'Thresh':>6s}  {'Hamming':>7s}  {'Subset':>7s}  "
        f"{'LblCov':>7s}  {'LblPrec':>7s}  {'AvgPred':>7s}  "
        f"{'CmbF1':>7s}"
    )
    print(f"\n  ALL cases (n={len(all_cases)}):")
    print(f"  {header}")
    print(f"  {'─' * len(header)}")

    for thresh in ABSOLUTE_THRESHOLDS:
        preds_lists = []
        golds_lists = []
        for label, case_id, confirmed, confidences, gold_codes in all_cases:
            filtered = apply_absolute_threshold(
                confirmed, confidences, thresh
            )
            preds_lists.append(filtered)
            golds_lists.append(gold_codes)

        metrics = evaluate_threshold(preds_lists, golds_lists, False)
        all_results["strategy_a_absolute"][str(thresh)] = {
            "all": metrics,
        }

        print(
            f"  {thresh:6.2f}  {metrics['hamming']:7.4f}  "
            f"{metrics['subset']:7.4f}  {metrics['label_cov']:7.4f}  "
            f"{metrics['label_prec']:7.4f}  {metrics['avg_pred']:7.3f}  "
            f"{metrics['comorbid_f1']:7.4f}"
        )

    # LingxiDiag subset with 4-class
    if lingxidiag_cases:
        header_4cls = (
            f"{'Thresh':>6s}  {'Hamming':>7s}  {'Subset':>7s}  "
            f"{'LblCov':>7s}  {'LblPrec':>7s}  {'AvgPred':>7s}  "
            f"{'4clsAcc':>7s}  {'MxdP':>5s}  {'MxdR':>5s}  "
            f"{'DepP':>5s}  {'AnxP':>5s}"
        )
        print(f"\n  LingxiDiag only (n={len(lingxidiag_cases)}):")
        print(f"  {header_4cls}")
        print(f"  {'─' * len(header_4cls)}")

        for thresh in ABSOLUTE_THRESHOLDS:
            preds_lists = []
            golds_lists = []
            for (
                label, case_id, confirmed, confidences, gold_codes
            ) in lingxidiag_cases:
                filtered = apply_absolute_threshold(
                    confirmed, confidences, thresh
                )
                preds_lists.append(filtered)
                golds_lists.append(gold_codes)

            metrics = evaluate_threshold(
                preds_lists, golds_lists, True
            )
            all_results["strategy_a_absolute"][str(thresh)][
                "lingxidiag"
            ] = metrics

            mixed_p = metrics.get("4cls_Mixed_prec", 0.0)
            mixed_r = metrics.get("4cls_Mixed_rec", 0.0)
            dep_p = metrics.get("4cls_Depression_prec", 0.0)
            anx_p = metrics.get("4cls_Anxiety_prec", 0.0)

            print(
                f"  {thresh:6.2f}  {metrics['hamming']:7.4f}  "
                f"{metrics['subset']:7.4f}  {metrics['label_cov']:7.4f}  "
                f"{metrics['label_prec']:7.4f}  {metrics['avg_pred']:7.3f}  "
                f"{metrics['4class_acc']:7.4f}  {mixed_p:5.3f}  "
                f"{mixed_r:5.3f}  {dep_p:5.3f}  {anx_p:5.3f}"
            )

    # ── Strategy B: Ratio threshold ──
    print("\n" + "─" * 80)
    print("STRATEGY B: RELATIVE CONFIDENCE RATIO")
    print("─" * 80)

    header = (
        f"{'Ratio':>6s}  {'Hamming':>7s}  {'Subset':>7s}  "
        f"{'LblCov':>7s}  {'LblPrec':>7s}  {'AvgPred':>7s}  "
        f"{'CmbF1':>7s}"
    )
    print(f"\n  ALL cases (n={len(all_cases)}):")
    print(f"  {header}")
    print(f"  {'─' * len(header)}")

    for ratio in RATIO_THRESHOLDS:
        preds_lists = []
        golds_lists = []
        for label, case_id, confirmed, confidences, gold_codes in all_cases:
            filtered = apply_ratio_threshold(
                confirmed, confidences, ratio
            )
            preds_lists.append(filtered)
            golds_lists.append(gold_codes)

        metrics = evaluate_threshold(preds_lists, golds_lists, False)
        all_results["strategy_b_ratio"][str(ratio)] = {
            "all": metrics,
        }

        print(
            f"  {ratio:6.2f}  {metrics['hamming']:7.4f}  "
            f"{metrics['subset']:7.4f}  {metrics['label_cov']:7.4f}  "
            f"{metrics['label_prec']:7.4f}  {metrics['avg_pred']:7.3f}  "
            f"{metrics['comorbid_f1']:7.4f}"
        )

    # LingxiDiag subset with 4-class
    if lingxidiag_cases:
        header_4cls = (
            f"{'Ratio':>6s}  {'Hamming':>7s}  {'Subset':>7s}  "
            f"{'LblCov':>7s}  {'LblPrec':>7s}  {'AvgPred':>7s}  "
            f"{'4clsAcc':>7s}  {'MxdP':>5s}  {'MxdR':>5s}  "
            f"{'DepP':>5s}  {'AnxP':>5s}"
        )
        print(f"\n  LingxiDiag only (n={len(lingxidiag_cases)}):")
        print(f"  {header_4cls}")
        print(f"  {'─' * len(header_4cls)}")

        for ratio in RATIO_THRESHOLDS:
            preds_lists = []
            golds_lists = []
            for (
                label, case_id, confirmed, confidences, gold_codes
            ) in lingxidiag_cases:
                filtered = apply_ratio_threshold(
                    confirmed, confidences, ratio
                )
                preds_lists.append(filtered)
                golds_lists.append(gold_codes)

            metrics = evaluate_threshold(
                preds_lists, golds_lists, True
            )
            all_results["strategy_b_ratio"][str(ratio)][
                "lingxidiag"
            ] = metrics

            mixed_p = metrics.get("4cls_Mixed_prec", 0.0)
            mixed_r = metrics.get("4cls_Mixed_rec", 0.0)
            dep_p = metrics.get("4cls_Depression_prec", 0.0)
            anx_p = metrics.get("4cls_Anxiety_prec", 0.0)

            print(
                f"  {ratio:6.2f}  {metrics['hamming']:7.4f}  "
                f"{metrics['subset']:7.4f}  {metrics['label_cov']:7.4f}  "
                f"{metrics['label_prec']:7.4f}  {metrics['avg_pred']:7.3f}  "
                f"{metrics['4class_acc']:7.4f}  {mixed_p:5.3f}  "
                f"{mixed_r:5.3f}  {dep_p:5.3f}  {anx_p:5.3f}"
            )

    # ── Per-sweep breakdown ──
    print("\n" + "─" * 80)
    print("PER-SWEEP BREAKDOWN (Strategy B, selected ratios)")
    print("─" * 80)

    sweep_labels = sorted(set(c[0] for c in all_cases))
    selected_ratios = [0.0, 0.5, 0.7, 0.9]

    for slabel in sweep_labels:
        sweep_cases = [c for c in all_cases if c[0] == slabel]
        is_lx = "lingxidiag" in slabel.lower()

        print(f"\n  {slabel} (n={len(sweep_cases)}):")
        hdr = f"  {'Ratio':>6s}  {'Subset':>7s}  {'LblPrec':>7s}  {'AvgPred':>7s}"
        if is_lx:
            hdr += f"  {'4clsAcc':>7s}  {'MxdP':>5s}"
        print(hdr)

        for ratio in selected_ratios:
            preds_lists = []
            golds_lists = []
            for (
                label, case_id, confirmed, confidences, gold_codes
            ) in sweep_cases:
                filtered = apply_ratio_threshold(
                    confirmed, confidences, ratio
                )
                preds_lists.append(filtered)
                golds_lists.append(gold_codes)

            metrics = evaluate_threshold(
                preds_lists, golds_lists, is_lx
            )
            line = (
                f"  {ratio:6.2f}  {metrics['subset']:7.4f}  "
                f"{metrics['label_prec']:7.4f}  "
                f"{metrics['avg_pred']:7.3f}"
            )
            if is_lx:
                line += (
                    f"  {metrics.get('4class_acc', 0):7.4f}  "
                    f"{metrics.get('4cls_Mixed_prec', 0):5.3f}"
                )
            print(line)

    # ── Save results ──
    out_path = Path("outputs/comorbidity_threshold_tuning.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert any non-serializable values
    def make_serializable(obj: object) -> object:
        if isinstance(obj, float):
            if obj != obj:  # NaN
                return None
            return round(obj, 6)
        if isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [make_serializable(v) for v in obj]
        return obj

    serializable = make_serializable(all_results)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to {out_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
