# src/culturedx/eval/metrics.py
"""Evaluation metrics for diagnosis and severity tasks."""
from __future__ import annotations

import numpy as np
from scipy import stats
from sklearn.metrics import f1_score


def top_k_accuracy(
    preds: list[list[str]], golds: list[list[str]], k: int = 1
) -> float:
    """Top-k accuracy: correct if any gold diagnosis is in top-k predictions."""
    correct = 0
    for pred_list, gold_list in zip(preds, golds):
        top_k_preds = set(pred_list[:k])
        if top_k_preds & set(gold_list):
            correct += 1
    return correct / len(preds) if preds else 0.0


def macro_f1(preds: list[str], golds: list[str]) -> float:
    """Macro-averaged F1 across all classes."""
    return float(f1_score(golds, preds, average="macro", zero_division=0))


def binary_f1(preds: list[int], golds: list[int]) -> float:
    """Binary F1 score (positive class)."""
    return float(f1_score(golds, preds, average="binary", zero_division=0))


def mae(preds: list[float], golds: list[float]) -> float:
    """Mean absolute error."""
    return float(np.mean(np.abs(np.array(preds) - np.array(golds))))


def rmse(preds: list[float], golds: list[float]) -> float:
    """Root mean squared error."""
    return float(np.sqrt(np.mean((np.array(preds) - np.array(golds)) ** 2)))


def pearson_r(preds: list[float], golds: list[float]) -> float:
    """Pearson correlation coefficient."""
    if len(preds) < 3:
        return float("nan")
    r, _ = stats.pearsonr(preds, golds)
    return float(r)


def compute_diagnosis_metrics(
    preds: list[list[str]], golds: list[list[str]]
) -> dict:
    """Compute all diagnosis metrics."""
    primary_preds = [p[0] if p else "unknown" for p in preds]
    primary_golds = [g[0] if g else "unknown" for g in golds]
    return {
        "top1_accuracy": top_k_accuracy(preds, golds, k=1),
        "top3_accuracy": top_k_accuracy(preds, golds, k=3),
        "macro_f1": macro_f1(primary_preds, primary_golds),
    }


def compute_severity_metrics(
    preds: list[float], golds: list[float]
) -> dict:
    """Compute all severity scoring metrics."""
    return {
        "mae": mae(preds, golds),
        "rmse": rmse(preds, golds),
        "pearson_r": pearson_r(preds, golds),
        # CCC deferred to Phase 2 (requires calibrated severity predictions)
    }
