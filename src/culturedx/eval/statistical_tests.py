"""Statistical tests for pairwise mode comparison.

Provides McNemar's test with Bonferroni correction for comparing
diagnostic accuracy between different MAS modes on paired samples.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import combinations

logger = logging.getLogger(__name__)


@dataclass
class McNemarResult:
    """Result of a McNemar's test between two modes."""
    mode_a: str
    mode_b: str
    n_both_correct: int
    n_a_only: int      # A correct, B wrong
    n_b_only: int      # B correct, A wrong
    n_both_wrong: int
    statistic: float
    p_value: float
    significant: bool
    corrected_alpha: float


def mcnemar_test(
    correct_a: list[bool],
    correct_b: list[bool],
    alpha: float = 0.05,
) -> dict:
    """McNemar's test for paired binary outcomes.

    Tests whether two classifiers have the same error rate on paired data.
    Uses continuity correction for small samples.

    Args:
        correct_a: Per-case correctness for mode A.
        correct_b: Per-case correctness for mode B.
        alpha: Significance level.

    Returns:
        Dict with statistic, p_value, significant, and contingency counts.
    """
    if len(correct_a) != len(correct_b):
        raise ValueError(
            f"Lengths must match: {len(correct_a)} vs {len(correct_b)}"
        )

    n_both_correct = 0
    n_a_only = 0
    n_b_only = 0
    n_both_wrong = 0

    for a, b in zip(correct_a, correct_b):
        if a and b:
            n_both_correct += 1
        elif a and not b:
            n_a_only += 1
        elif not a and b:
            n_b_only += 1
        else:
            n_both_wrong += 1

    discordant = n_a_only + n_b_only
    if discordant == 0:
        return {
            "n_both_correct": n_both_correct,
            "n_a_only": n_a_only,
            "n_b_only": n_b_only,
            "n_both_wrong": n_both_wrong,
            "statistic": 0.0,
            "p_value": 1.0,
            "significant": False,
        }

    # McNemar's test with continuity correction
    statistic = (abs(n_a_only - n_b_only) - 1) ** 2 / discordant

    p_value = _chi2_sf(statistic, df=1)

    return {
        "n_both_correct": n_both_correct,
        "n_a_only": n_a_only,
        "n_b_only": n_b_only,
        "n_both_wrong": n_both_wrong,
        "statistic": statistic,
        "p_value": p_value,
        "significant": p_value < alpha,
    }


def pairwise_mcnemar(
    mode_results: dict[str, list[bool]],
    alpha: float = 0.05,
) -> list[McNemarResult]:
    """All pairwise McNemar tests with Bonferroni correction.

    Args:
        mode_results: Dict mapping mode name to per-case correctness list.
        alpha: Family-wise error rate.

    Returns:
        List of McNemarResult for each pair.
    """
    modes = sorted(mode_results.keys())
    n_comparisons = len(list(combinations(modes, 2)))
    if n_comparisons == 0:
        return []

    corrected_alpha = alpha / n_comparisons

    results = []
    for mode_a, mode_b in combinations(modes, 2):
        test = mcnemar_test(
            mode_results[mode_a],
            mode_results[mode_b],
            alpha=corrected_alpha,
        )
        results.append(McNemarResult(
            mode_a=mode_a,
            mode_b=mode_b,
            n_both_correct=test["n_both_correct"],
            n_a_only=test["n_a_only"],
            n_b_only=test["n_b_only"],
            n_both_wrong=test["n_both_wrong"],
            statistic=test["statistic"],
            p_value=test["p_value"],
            significant=test["p_value"] < corrected_alpha,
            corrected_alpha=corrected_alpha,
        ))

    return results


def format_mcnemar_table(results: list[McNemarResult]) -> str:
    """Format McNemar results as a markdown table."""
    lines = [
        "| Mode A | Mode B | A-only | B-only | χ² | p-value | Sig (Bonferroni) |",
        "|--------|--------|--------|--------|-----|---------|-----------------|",
    ]
    for r in results:
        sig = "**YES**" if r.significant else "no"
        lines.append(
            f"| {r.mode_a} | {r.mode_b} | {r.n_a_only} | {r.n_b_only} "
            f"| {r.statistic:.3f} | {r.p_value:.4f} | {sig} |"
        )
    return "\n".join(lines)


def _chi2_sf(x: float, df: int = 1) -> float:
    """Survival function (1 - CDF) of chi-squared distribution.

    Pure Python implementation to avoid scipy dependency.
    Uses the regularized incomplete gamma function for df=1.

    For df=1: P(chi2_1 > x) = erfc(sqrt(x/2))
    """
    if x <= 0:
        return 1.0
    if df != 1:
        raise NotImplementedError("Only df=1 supported without scipy")
    from math import erfc, sqrt
    return erfc(sqrt(x / 2))
