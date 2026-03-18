"""Cross-lingual evidence gap evaluation and selective prediction metrics."""
from __future__ import annotations

import logging

import numpy as np
from sklearn.metrics import f1_score

logger = logging.getLogger(__name__)


def evidence_delta(
    preds_with: list[int],
    preds_without: list[int],
    golds: list[int],
    metric: str = "binary_f1",
) -> float:
    """Compute evidence delta: metric(with_evidence) - metric(without_evidence).
    
    Args:
        preds_with: Predictions with evidence pipeline.
        preds_without: Predictions without evidence pipeline.
        golds: Ground truth labels.
        metric: "binary_f1" or "macro_f1".
    
    Returns:
        Delta value (positive = evidence helps).
    """
    if metric == "binary_f1":
        f1_with = float(f1_score(golds, preds_with, average="binary", zero_division=0))
        f1_without = float(f1_score(golds, preds_without, average="binary", zero_division=0))
    elif metric == "macro_f1":
        f1_with = float(f1_score(golds, preds_with, average="macro", zero_division=0))
        f1_without = float(f1_score(golds, preds_without, average="macro", zero_division=0))
    else:
        raise ValueError(f"Unknown metric: {metric}")
    return f1_with - f1_without


def paired_bootstrap_test(
    preds_with_cn: list[int],
    preds_without_cn: list[int],
    golds_cn: list[int],
    preds_with_en: list[int],
    preds_without_en: list[int],
    golds_en: list[int],
    n_resamples: int = 10000,
    seed: int = 42,
    metric: str = "binary_f1",
) -> dict:
    """Paired bootstrap test for cross-lingual evidence gap.
    
    Tests H1: evidence_delta(Chinese) > evidence_delta(English).
    
    Returns:
        Dict with delta_cn, delta_en, gap, p_value, significant (at p<0.05).
    """
    rng = np.random.RandomState(seed)

    delta_cn = evidence_delta(preds_with_cn, preds_without_cn, golds_cn, metric)
    delta_en = evidence_delta(preds_with_en, preds_without_en, golds_en, metric)
    observed_gap = delta_cn - delta_en

    # Bootstrap
    cn_with = np.array(preds_with_cn)
    cn_without = np.array(preds_without_cn)
    cn_gold = np.array(golds_cn)
    en_with = np.array(preds_with_en)
    en_without = np.array(preds_without_en)
    en_gold = np.array(golds_en)

    n_cn = len(cn_gold)
    n_en = len(en_gold)

    gaps = np.zeros(n_resamples)
    for i in range(n_resamples):
        # Resample Chinese
        idx_cn = rng.randint(0, n_cn, size=n_cn)
        if metric == "binary_f1":
            avg = "binary"
        else:
            avg = "macro"
        
        f1_cn_with = f1_score(cn_gold[idx_cn], cn_with[idx_cn], average=avg, zero_division=0)
        f1_cn_without = f1_score(cn_gold[idx_cn], cn_without[idx_cn], average=avg, zero_division=0)
        d_cn = f1_cn_with - f1_cn_without

        # Resample English
        idx_en = rng.randint(0, n_en, size=n_en)
        f1_en_with = f1_score(en_gold[idx_en], en_with[idx_en], average=avg, zero_division=0)
        f1_en_without = f1_score(en_gold[idx_en], en_without[idx_en], average=avg, zero_division=0)
        d_en = f1_en_with - f1_en_without

        gaps[i] = d_cn - d_en

    # One-sided p-value: P(gap <= 0 under H0)
    p_value = float(np.mean(gaps <= 0))

    return {
        "delta_cn": delta_cn,
        "delta_en": delta_en,
        "observed_gap": observed_gap,
        "p_value": p_value,
        "significant": p_value < 0.05,
        "n_resamples": n_resamples,
        "ci_95_lower": float(np.percentile(gaps, 2.5)),
        "ci_95_upper": float(np.percentile(gaps, 97.5)),
    }


def aurc(
    confidences: list[float],
    correct: list[bool],
) -> float:
    """Area Under Risk-Coverage Curve.
    
    Sort predictions by confidence (descending). At each coverage level,
    compute risk (1 - accuracy). AURC = area under this curve.
    Lower is better.
    
    Args:
        confidences: Model confidence for each prediction.
        correct: Whether each prediction was correct.
    
    Returns:
        AURC score (lower is better).
    """
    if not confidences:
        return 1.0

    n = len(confidences)
    # Sort by confidence descending
    indices = np.argsort(confidences)[::-1]
    sorted_correct = np.array(correct)[indices]

    # Compute cumulative risk at each coverage level
    cumsum = np.cumsum(1 - sorted_correct.astype(float))
    coverage = np.arange(1, n + 1) / n
    risk = cumsum / np.arange(1, n + 1)

    area = float(np.trapezoid(risk, coverage))
    return area


def selective_accuracy(
    confidences: list[float],
    correct: list[bool],
    coverage_target: float = 0.8,
) -> dict:
    """Compute accuracy at a target coverage level.
    
    Args:
        confidences: Model confidence scores.
        correct: Whether each prediction was correct.
        coverage_target: What fraction of cases to include (0.0-1.0).
    
    Returns:
        Dict with accuracy, coverage, n_selected, n_total.
    """
    if not confidences:
        return {"accuracy": 0.0, "coverage": 0.0, "n_selected": 0, "n_total": 0}

    n = len(confidences)
    n_select = max(1, int(n * coverage_target))

    # Select top-confidence predictions
    indices = np.argsort(confidences)[::-1][:n_select]
    selected_correct = [correct[i] for i in indices]

    accuracy = sum(selected_correct) / len(selected_correct)
    return {
        "accuracy": accuracy,
        "coverage": n_select / n,
        "n_selected": n_select,
        "n_total": n,
    }
