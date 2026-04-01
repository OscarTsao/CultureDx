"""Confidence calibration analysis — reliability diagrams, ECE, Platt scaling.

Computes Expected Calibration Error (ECE) and generates data for
reliability diagrams (calibration curves) across diagnostic modes.
Includes PlattCalibrator for post-hoc calibration and risk-coverage curves.
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

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


def compute_brier_score(confidences: list[float], correct: list[bool]) -> float:
    """Compute the Brier score for confidence calibration."""
    if len(confidences) != len(correct):
        raise ValueError(
            f"Length mismatch: {len(confidences)} confidences vs {len(correct)} correct"
        )
    if not confidences:
        return 0.0
    errors = [(c - float(y)) ** 2 for c, y in zip(confidences, correct)]
    return float(sum(errors) / len(errors))


def compute_abstention_breakdown(
    confidences: list[float],
    correct: list[bool],
    abstained: list[bool],
) -> dict[str, float | int]:
    """Summarize abstention behavior for selective prediction analysis."""
    if not (len(confidences) == len(correct) == len(abstained)):
        raise ValueError(
            "Length mismatch: confidences, correct, and abstained must align"
        )
    if not confidences:
        return {
            "n_samples": 0,
            "abstain_rate": 0.0,
            "coverage": 0.0,
            "diagnosed_accuracy": 0.0,
            "abstained_accuracy": 0.0,
        }

    n = len(confidences)
    diagnosed = [i for i, flag in enumerate(abstained) if not flag]
    abstained_idx = [i for i, flag in enumerate(abstained) if flag]

    diagnosed_accuracy = (
        sum(float(correct[i]) for i in diagnosed) / len(diagnosed)
        if diagnosed
        else 0.0
    )
    abstained_accuracy = (
        sum(float(correct[i]) for i in abstained_idx) / len(abstained_idx)
        if abstained_idx
        else 0.0
    )

    return {
        "n_samples": n,
        "abstain_rate": float(len(abstained_idx) / n),
        "coverage": float(len(diagnosed) / n),
        "diagnosed_accuracy": float(diagnosed_accuracy),
        "abstained_accuracy": float(abstained_accuracy),
    }


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


class PlattCalibrator:
    """Post-hoc Platt scaling: logistic regression on raw confidence -> P(correct)."""

    def __init__(self) -> None:
        self.a: float = 0.0
        self.b: float = 0.0
        self.optimal_threshold: float = 0.3
        self.fitted: bool = False

    def fit(self, confidences: list[float], correct: list[bool]) -> None:
        """Fit Platt scaling on validation data.

        Uses sklearn LogisticRegression with C=1.0 to learn P(correct | confidence).
        Also finds the optimal abstain threshold that maximizes F1.
        """
        from sklearn.linear_model import LogisticRegression

        X = np.array(confidences).reshape(-1, 1)
        y = np.array(correct, dtype=int)

        model = LogisticRegression(C=1.0, random_state=42, max_iter=1000)
        model.fit(X, y)

        self.a = float(model.coef_[0, 0])
        self.b = float(model.intercept_[0])
        self.fitted = True

        # Find optimal threshold maximizing F1 on the fitting data
        self.optimal_threshold = self._find_optimal_threshold(confidences, correct)

    def transform(self, confidence: float) -> float:
        """Transform a single raw confidence to calibrated probability."""
        z = self.a * confidence + self.b
        return 1.0 / (1.0 + math.exp(-z))

    def transform_batch(self, confidences: list[float]) -> list[float]:
        """Transform a list of raw confidences."""
        return [self.transform(c) for c in confidences]

    def _find_optimal_threshold(
        self, confidences: list[float], correct: list[bool],
    ) -> float:
        """Find calibrated threshold maximizing F1 (predict correct if above)."""
        calibrated = self.transform_batch(confidences)
        best_f1 = 0.0
        best_thresh = 0.5

        for thresh in np.arange(0.1, 0.9, 0.01):
            tp = sum(1 for c, cor in zip(calibrated, correct) if c >= thresh and cor)
            fp = sum(1 for c, cor in zip(calibrated, correct) if c >= thresh and not cor)
            fn = sum(1 for c, cor in zip(calibrated, correct) if c < thresh and cor)
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = (
                2 * precision * recall / (precision + recall)
                if (precision + recall) > 0 else 0
            )
            if f1 > best_f1:
                best_f1 = f1
                best_thresh = float(thresh)

        return best_thresh

    def save(self, path: str | Path) -> None:
        """Save fitted parameters to JSON."""
        data = {
            "a": self.a,
            "b": self.b,
            "optimal_threshold": self.optimal_threshold,
            "fitted": self.fitted,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> "PlattCalibrator":
        """Load fitted parameters from JSON."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        cal = cls()
        cal.a = data["a"]
        cal.b = data["b"]
        cal.optimal_threshold = data.get("optimal_threshold", 0.3)
        cal.fitted = data.get("fitted", True)
        return cal


def compute_risk_coverage_curve(
    confidences: list[float],
    correct: list[bool],
    n_points: int = 20,
) -> list[dict]:
    """Compute risk-coverage curve data points.

    Sorts predictions by confidence descending, then at each coverage level
    computes accuracy on the top-N% most confident predictions.

    Returns:
        List of dicts with keys: coverage, accuracy, risk, threshold, n_selected.
    """
    if not confidences:
        return []

    n = len(confidences)
    indices = np.argsort(confidences)[::-1]
    sorted_conf = np.array(confidences)[indices]
    sorted_correct = np.array(correct, dtype=float)[indices]

    points = []
    for i in range(1, n_points + 1):
        coverage = i / n_points
        n_select = max(1, int(n * coverage))
        selected = sorted_correct[:n_select]
        accuracy = float(selected.mean())

        threshold = float(sorted_conf[min(n_select - 1, n - 1)])
        points.append({
            "coverage": round(coverage, 3),
            "accuracy": round(accuracy, 4),
            "risk": round(1 - accuracy, 4),
            "threshold": round(threshold, 4),
            "n_selected": n_select,
        })

    return points
