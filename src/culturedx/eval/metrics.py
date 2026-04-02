# src/culturedx/eval/metrics.py
"""Evaluation metrics for diagnosis and severity tasks."""
from __future__ import annotations

import numpy as np
from scipy import stats
from sklearn.metrics import accuracy_score, f1_score


def normalize_icd_code(code: str, level: str = "parent") -> str:
    """Normalize ICD-10 code to parent level for cross-granularity comparison.

    Examples:
        normalize_icd_code("F41.1") -> "F41"
        normalize_icd_code("F32.901") -> "F32"
        normalize_icd_code("F43.1") -> "F43"
        normalize_icd_code("F32") -> "F32"
    """
    if level == "parent":
        return code.split(".")[0]
    return code


def normalize_code_list(codes: list[str], level: str = "parent") -> list[str]:
    """Normalize a list of ICD-10 codes, removing duplicates while preserving order."""
    seen = set()
    result = []
    for c in codes:
        normalized = normalize_icd_code(c, level)
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def top_k_accuracy(
    preds: list[list[str]], golds: list[list[str]], k: int = 1
) -> float:
    """Top-k accuracy against the primary gold diagnosis.

    LingxiDiagBench-style diagnosis metrics treat the first gold label as the
    reference diagnosis for ranking metrics. A case is correct only when that
    primary gold code appears within the top-k predicted codes.
    """
    correct = 0
    for pred_list, gold_list in zip(preds, golds):
        gold_primary = gold_list[0] if gold_list else None
        if gold_primary is not None and gold_primary in pred_list[:k]:
            correct += 1
    return correct / len(preds) if preds else 0.0


def macro_f1(preds: list[str], golds: list[str]) -> float:
    """Macro-averaged F1 across all classes."""
    if not preds or not golds:
        return 0.0
    return float(f1_score(golds, preds, average="macro", zero_division=0))


def weighted_f1(preds: list[str], golds: list[str]) -> float:
    """Weighted F1 score (accounts for class imbalance)."""
    if not preds or not golds:
        return 0.0
    return float(f1_score(golds, preds, average="weighted", zero_division=0))


def multiclass_accuracy(preds: list[str], golds: list[str]) -> float:
    """Standard single-label multi-class accuracy."""
    if not preds or not golds:
        return 0.0
    return float(accuracy_score(golds, preds))


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
    preds: list[list[str]], golds: list[list[str]], normalize: str | None = "parent"
) -> dict:
    """Compute all diagnosis metrics.

    Args:
        preds: Predicted diagnosis lists per case.
        golds: Ground truth diagnosis lists per case.
        normalize: ICD code normalization level ("parent" or None).
    """
    if normalize:
        preds = [normalize_code_list(p, normalize) for p in preds]
        golds = [normalize_code_list(g, normalize) for g in golds]

    if not preds or not golds:
        return {
            "accuracy": 0.0,
            "top1_accuracy": 0.0,
            "top3_accuracy": 0.0,
            "macro_f1": 0.0,
            "weighted_f1": 0.0,
            "overall": 0.0,
        }

    primary_preds = [p[0] if p else "unknown" for p in preds]
    primary_golds = [g[0] if g else "unknown" for g in golds]
    metrics = {
        "accuracy": multiclass_accuracy(primary_preds, primary_golds),
        "top1_accuracy": top_k_accuracy(preds, golds, k=1),
        "top3_accuracy": top_k_accuracy(preds, golds, k=3),
        "macro_f1": macro_f1(primary_preds, primary_golds),
        "weighted_f1": weighted_f1(primary_preds, primary_golds),
    }
    metrics["overall"] = float(np.mean(list(metrics.values())))
    return metrics


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


def _normalize_code(code: str, normalize: str | None = "parent") -> str:
    """Normalize a single ICD-10 code to the requested granularity level.

    Delegates to the existing normalize_icd_code helper so that all
    normalization logic lives in one place.

    Args:
        code: Raw ICD-10 code string, e.g. "F32.1".
        normalize: "parent" strips the decimal suffix (F32.1 -> F32);
                   None returns the code unchanged.

    Returns:
        Normalized code string.
    """
    if normalize is None:
        return code
    return normalize_icd_code(code, level=normalize)


def compute_comorbidity_metrics(
    predictions: list[list[str]],
    golds: list[list[str]],
    normalize: str | None = "parent",
) -> dict:
    """Compute comorbidity-aware evaluation metrics.

    Each element of *predictions* and *golds* is a list of disorder labels
    for one clinical case, ordered primary-first with any comorbid labels
    following.  All five metrics below treat the full label set (primary +
    comorbid) as a multi-label problem.

    Args:
        predictions: Per-case predicted label lists,
                     e.g. [["F32", "F41"], ["F33"]].
        golds: Per-case gold label lists in the same format.
        normalize: ICD-10 normalization level passed to _normalize_code.
                   "parent" collapses sub-codes (F32.1 -> F32); None keeps
                   codes verbatim.

    Returns:
        A dict with the following keys:

        hamming_accuracy
            Per-disorder correctness averaged over cases.  For each case we
            compute the fraction of labels in the union(pred, gold) on which
            pred and gold agree (both present or both absent), then average
            across cases.

        subset_accuracy
            Fraction of cases where the predicted label set matches the gold
            label set exactly (order-insensitive).

        comorbidity_detection_f1
            Binary F1 (positive = "case has comorbidity", i.e. >1 label) for
            the system's ability to detect when comorbidity is present.

        label_coverage
            Macro-averaged per-case recall: fraction of gold labels that
            appear anywhere in the predictions.

        label_precision
            Macro-averaged per-case precision: fraction of predicted labels
            that appear in the gold set.

        avg_predicted_labels
            Mean number of predicted labels per case.

        avg_gold_labels
            Mean number of gold labels per case.
    """
    if not predictions:
        return {
            "hamming_accuracy": float("nan"),
            "subset_accuracy": float("nan"),
            "comorbidity_detection_f1": float("nan"),
            "label_coverage": float("nan"),
            "label_precision": float("nan"),
            "avg_predicted_labels": float("nan"),
            "avg_gold_labels": float("nan"),
        }

    # ------------------------------------------------------------------
    # Normalize codes and deduplicate within each case
    # ------------------------------------------------------------------
    def _norm_list(codes: list[str]) -> set[str]:
        seen: set[str] = set()
        result: list[str] = []
        for c in codes:
            n = _normalize_code(c, normalize)
            if n not in seen:
                seen.add(n)
                result.append(n)
        return set(result)

    pred_sets = [_norm_list(p) for p in predictions]
    gold_sets = [_norm_list(g) for g in golds]

    n = len(pred_sets)

    # ------------------------------------------------------------------
    # 1. Hamming accuracy (per-disorder agreement over the union)
    # ------------------------------------------------------------------
    hamming_scores: list[float] = []
    for pred_set, gold_set in zip(pred_sets, gold_sets):
        universe = pred_set | gold_set
        if not universe:
            hamming_scores.append(1.0)
            continue
        agreed = sum(
            1 for label in universe if (label in pred_set) == (label in gold_set)
        )
        hamming_scores.append(agreed / len(universe))
    hamming_accuracy = float(np.mean(hamming_scores))

    # ------------------------------------------------------------------
    # 2. Subset accuracy (exact label-set match)
    # ------------------------------------------------------------------
    subset_accuracy = float(
        sum(1 for p, g in zip(pred_sets, gold_sets) if p == g) / n
    )

    # ------------------------------------------------------------------
    # 3. Comorbidity detection F1
    #    Positive class = case has more than one label.
    # ------------------------------------------------------------------
    pred_comorbid = [1 if len(p) > 1 else 0 for p in pred_sets]
    gold_comorbid = [1 if len(g) > 1 else 0 for g in gold_sets]
    comorbidity_detection_f1 = binary_f1(pred_comorbid, gold_comorbid)

    # ------------------------------------------------------------------
    # 4. Label coverage (per-case recall of gold labels in predictions)
    # ------------------------------------------------------------------
    coverage_scores: list[float] = []
    for pred_set, gold_set in zip(pred_sets, gold_sets):
        if not gold_set:
            # No gold labels; treat as perfect recall by convention.
            coverage_scores.append(1.0)
            continue
        coverage_scores.append(len(pred_set & gold_set) / len(gold_set))
    label_coverage = float(np.mean(coverage_scores))

    # ------------------------------------------------------------------
    # 5. Label precision (per-case precision of predicted labels)
    # ------------------------------------------------------------------
    precision_scores: list[float] = []
    for pred_set, gold_set in zip(pred_sets, gold_sets):
        if not pred_set:
            # No predictions; treat as perfect precision by convention so
            # we do not unfairly penalise abstentions here (that is
            # captured by coverage/recall instead).
            precision_scores.append(1.0)
            continue
        precision_scores.append(len(pred_set & gold_set) / len(pred_set))
    label_precision = float(np.mean(precision_scores))

    # ------------------------------------------------------------------
    # 6. Average label counts
    # ------------------------------------------------------------------
    avg_predicted_labels = float(np.mean([len(p) for p in pred_sets]))
    avg_gold_labels = float(np.mean([len(g) for g in gold_sets]))

    return {
        "hamming_accuracy": hamming_accuracy,
        "subset_accuracy": subset_accuracy,
        "comorbidity_detection_f1": comorbidity_detection_f1,
        "label_coverage": label_coverage,
        "label_precision": label_precision,
        "avg_predicted_labels": avg_predicted_labels,
        "avg_gold_labels": avg_gold_labels,
    }
