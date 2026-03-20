"""Confidence calibration analysis — reliability diagrams and ECE.

Computes Expected Calibration Error (ECE) and generates data for
reliability diagrams (calibration curves) across diagnostic modes.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CalibrationBin:
    """A single bin in the reliability diagram."""
    bin_lower: float
    bin_upper: float
    avg_confidence: float
    avg_accuracy: float
    count: int


@dataclass
class CalibrationResult:
    """Complete calibration analysis for one mode."""
    mode: str
    ece: float
    mce: float  # Maximum Calibration Error
    bins: list[CalibrationBin] = field(default_factory=list)
    n_samples: int = 0
    overall_accuracy: float = 0.0
    avg_confidence: float = 0.0


def compute_calibration(
    confidences: list[float],
    correct: list[bool],
    n_bins: int = 10,
    mode: str = "",
) -> CalibrationResult:
    """Compute reliability diagram data and ECE.

    Args:
        confidences: Per-case confidence scores from the diagnostic mode.
        correct: Per-case correctness (True if primary diagnosis matches gold).
        n_bins: Number of equal-width bins for the reliability diagram.
        mode: Name of the diagnostic mode (for labeling).

    Returns:
        CalibrationResult with bins, ECE, MCE, and summary statistics.
    """
    if len(confidences) != len(correct):
        raise ValueError(
            f"Length mismatch: {len(confidences)} confidences vs {len(correct)} correct"
        )

    n = len(confidences)
    if n == 0:
        return CalibrationResult(mode=mode, ece=0.0, mce=0.0)

    bins = []
    weighted_error_sum = 0.0
    max_error = 0.0

    bin_width = 1.0 / n_bins
    for i in range(n_bins):
        lower = i * bin_width
        upper = (i + 1) * bin_width

        # Gather predictions in this bin
        bin_confs = []
        bin_correct = []
        for conf, cor in zip(confidences, correct):
            if lower <= conf < upper or (i == n_bins - 1 and conf == upper):
                bin_confs.append(conf)
                bin_correct.append(float(cor))

        if not bin_confs:
            continue

        avg_conf = sum(bin_confs) / len(bin_confs)
        avg_acc = sum(bin_correct) / len(bin_correct)
        count = len(bin_confs)

        bins.append(CalibrationBin(
            bin_lower=lower,
            bin_upper=upper,
            avg_confidence=avg_conf,
            avg_accuracy=avg_acc,
            count=count,
        ))

        error = abs(avg_acc - avg_conf)
        weighted_error_sum += count * error
        max_error = max(max_error, error)

    ece = weighted_error_sum / n if n > 0 else 0.0
    overall_accuracy = sum(float(c) for c in correct) / n
    avg_confidence = sum(confidences) / n

    return CalibrationResult(
        mode=mode,
        ece=ece,
        mce=max_error,
        bins=bins,
        n_samples=n,
        overall_accuracy=overall_accuracy,
        avg_confidence=avg_confidence,
    )


def format_calibration_table(results: list[CalibrationResult]) -> str:
    """Format calibration results as a markdown table."""
    lines = [
        "| Mode | N | Accuracy | Avg Conf | ECE | MCE |",
        "|------|---|----------|----------|-----|-----|",
    ]
    for r in results:
        lines.append(
            f"| {r.mode} | {r.n_samples} | {r.overall_accuracy:.3f} "
            f"| {r.avg_confidence:.3f} | {r.ece:.3f} | {r.mce:.3f} |"
        )
    return "\n".join(lines)


def format_reliability_diagram_data(result: CalibrationResult) -> str:
    """Format bin data for plotting a reliability diagram."""
    lines = [
        f"# Reliability Diagram: {result.mode} (ECE={result.ece:.4f})",
        "| Bin Range | Avg Confidence | Avg Accuracy | Count |",
        "|-----------|---------------|-------------|-------|",
    ]
    for b in result.bins:
        lines.append(
            f"| [{b.bin_lower:.1f}, {b.bin_upper:.1f}) "
            f"| {b.avg_confidence:.3f} | {b.avg_accuracy:.3f} | {b.count} |"
        )
    return "\n".join(lines)


def calibration_from_predictions(
    predictions_path: str | Path,
    gold_labels: dict[str, str] | None = None,
    mode: str = "",
    n_bins: int = 10,
) -> CalibrationResult:
    """Compute calibration from a predictions.json file.

    Args:
        predictions_path: Path to predictions.json (list of dicts with
            case_id, primary_diagnosis, confidence).
        gold_labels: Optional mapping of case_id -> gold diagnosis code.
            If None, attempts to read from prediction entries.
        mode: Mode name for labeling.
        n_bins: Number of calibration bins.
    """
    with open(predictions_path, encoding="utf-8") as f:
        predictions = json.load(f)

    confidences = []
    correct = []

    for pred in predictions:
        conf = pred.get("confidence", 0.0)
        primary = pred.get("primary_diagnosis")
        case_id = pred.get("case_id", "")

        if primary is None:
            continue  # Skip abstentions for calibration

        confidences.append(conf)

        if gold_labels and case_id in gold_labels:
            gold = gold_labels[case_id]
            # Parent-code matching (F41.1 matches F41)
            is_correct = (
                primary == gold
                or primary.startswith(gold)
                or gold.startswith(primary)
            )
            correct.append(is_correct)
        elif "gold_diagnosis" in pred:
            gold = pred["gold_diagnosis"]
            is_correct = (
                primary == gold
                or primary.startswith(gold)
                or gold.startswith(primary)
            )
            correct.append(is_correct)
        else:
            # Can't determine correctness without gold labels
            continue

    if len(confidences) != len(correct):
        # Trim to matching length
        min_len = min(len(confidences), len(correct))
        confidences = confidences[:min_len]
        correct = correct[:min_len]

    return compute_calibration(confidences, correct, n_bins=n_bins, mode=mode)
