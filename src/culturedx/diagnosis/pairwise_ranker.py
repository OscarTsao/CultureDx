"""Pairwise learned ranker for re-ordering confirmed disorders.

Loads pre-trained logistic regression weights from JSON.
Re-ranks disorders using accumulated pairwise win probabilities.
No sklearn needed at inference — only numpy.
"""
from __future__ import annotations

import json
import logging
from itertools import combinations
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

POINTWISE_COLS = [
    "threshold_ratio",
    "avg_confidence",
    "n_criteria_met",
    "n_criteria_total",
    "criteria_required",
    "margin",
    "evidence_coverage",
    "has_comorbid",
]


class PairwiseRanker:
    """Pairwise learned ranker using pre-trained logistic regression weights."""

    def __init__(self, weights_path: str | Path) -> None:
        with open(weights_path, encoding="utf-8") as f:
            w = json.load(f)
        self.coefficients = np.array(w["coefficients"])
        self.intercept = float(w["intercept"])
        self.scaler_mean = np.array(w["scaler_mean"])
        self.scaler_scale = np.array(w["scaler_scale"])
        self.include_identity = w.get("include_identity", True)
        self.disorder_ids: dict[str, int] = w.get("disorder_ids", {})
        self.n_disorders: int = w.get("n_disorders", len(self.disorder_ids))
        self.feature_dim: int = w.get("feature_dim", len(self.coefficients))

    def _disorder_onehot(self, code: str) -> np.ndarray:
        vec = np.zeros(self.n_disorders)
        idx = self.disorder_ids.get(code)
        if idx is not None:
            vec[idx] = 1.0
        return vec

    def _build_pairwise_features(
        self,
        feat_a: np.ndarray,
        feat_b: np.ndarray,
        disorder_a: str,
        disorder_b: str,
    ) -> np.ndarray:
        diff = feat_a - feat_b
        abs_diff = np.abs(diff)
        eps = 1e-6
        ratios = np.array([
            feat_a[0] / max(feat_b[0], eps),
            feat_a[1] / max(feat_b[1], eps),
            feat_a[2] / max(feat_b[2], eps),
        ])
        parts = [diff, abs_diff, ratios]
        if self.include_identity:
            parts.append(self._disorder_onehot(disorder_a))
            parts.append(self._disorder_onehot(disorder_b))
        return np.concatenate(parts)

    def _predict_prob(self, features: np.ndarray) -> float:
        """P(A beats B) via manual logistic regression."""
        scaled = (features - self.scaler_mean) / self.scaler_scale
        z = float(np.dot(scaled, self.coefficients) + self.intercept)
        return 1.0 / (1.0 + np.exp(-z))

    @staticmethod
    def extract_pointwise_from_criteria_result(
        cr: dict, n_confirmed: int
    ) -> np.ndarray:
        """Extract 8 pointwise features from a criteria_results dict.

        Matches extract_ranker_features.py lines 52-79 exactly.
        """
        criteria = cr.get("criteria", [])
        met = [c for c in criteria if c.get("status") == "met"]
        n_met = len(met)
        n_total = len(criteria)
        required = cr.get("criteria_required", 1)

        threshold_ratio = min(1.0, n_met / required) if required > 0 else 0.0
        avg_confidence = (
            sum(c.get("confidence", 0) for c in met) / len(met) if met else 0.0
        )
        margin = (
            max(0, n_met - required) / max(n_total - required, 1)
            if n_total > required
            else 0.0
        )
        evidence_coverage = (
            sum(
                1 for c in met if c.get("evidence") and c["evidence"].strip()
            )
            / len(met)
            if met
            else 0.0
        )
        has_comorbid = 1 if n_confirmed > 1 else 0

        return np.array([
            threshold_ratio,
            avg_confidence,
            n_met,
            n_total,
            required,
            margin,
            evidence_coverage,
            has_comorbid,
        ])

    def rerank(
        self,
        confirmed_codes: list[str],
        checker_outputs: list,
    ) -> list[str]:
        """Re-rank confirmed disorders using CheckerOutput objects (live pipeline).

        Args:
            confirmed_codes: [primary] + comorbid disorder codes.
            checker_outputs: List of CheckerOutput dataclass instances.

        Returns:
            Re-ordered list of disorder codes (highest score first).
        """
        if len(confirmed_codes) < 2:
            return list(confirmed_codes)

        co_map = {co.disorder: co for co in checker_outputs}
        n_confirmed = len(confirmed_codes)

        feat_map: dict[str, np.ndarray] = {}
        for code in confirmed_codes:
            co = co_map.get(code)
            if co is None:
                logger.warning("No CheckerOutput for %s, using zeros", code)
                feat_map[code] = np.zeros(len(POINTWISE_COLS))
            else:
                criteria = co.criteria
                met = [c for c in criteria if c.status == "met"]
                n_met = len(met)
                n_total = len(criteria)
                required = co.criteria_required

                threshold_ratio = min(1.0, n_met / required) if required > 0 else 0.0
                avg_confidence = (
                    sum(c.confidence for c in met) / len(met) if met else 0.0
                )
                margin = (
                    max(0, n_met - required) / max(n_total - required, 1)
                    if n_total > required
                    else 0.0
                )
                evidence_coverage = (
                    sum(
                        1 for c in met
                        if c.evidence and c.evidence.strip()
                    )
                    / len(met)
                    if met
                    else 0.0
                )
                has_comorbid = 1 if n_confirmed > 1 else 0

                feat_map[code] = np.array([
                    threshold_ratio, avg_confidence, n_met, n_total,
                    required, margin, evidence_coverage, has_comorbid,
                ])

        # Accumulate pairwise win scores
        scores: dict[str, float] = {code: 0.0 for code in confirmed_codes}
        for code_a, code_b in combinations(confirmed_codes, 2):
            pw_feat = self._build_pairwise_features(
                feat_map[code_a], feat_map[code_b], code_a, code_b
            )
            prob_a = self._predict_prob(pw_feat)
            scores[code_a] += prob_a
            scores[code_b] += 1.0 - prob_a

        return sorted(confirmed_codes, key=lambda c: -scores[c])

    def rerank_from_criteria_results(
        self,
        confirmed_codes: list[str],
        criteria_results: list[dict],
    ) -> list[str]:
        """Re-rank confirmed disorders using criteria_results dicts.

        Args:
            confirmed_codes: [primary] + comorbid disorder codes.
            criteria_results: List of criteria_result dicts from predictions.json.

        Returns:
            Re-ordered list of disorder codes (highest score first).
        """
        if len(confirmed_codes) < 2:
            return list(confirmed_codes)

        cr_map = {cr["disorder"]: cr for cr in criteria_results}
        n_confirmed = len(confirmed_codes)

        # Extract pointwise features for each confirmed disorder
        feat_map: dict[str, np.ndarray] = {}
        for code in confirmed_codes:
            cr = cr_map.get(code)
            if cr is None:
                logger.warning("No criteria_results for %s, using zeros", code)
                feat_map[code] = np.zeros(len(POINTWISE_COLS))
            else:
                feat_map[code] = self.extract_pointwise_from_criteria_result(
                    cr, n_confirmed
                )

        # Accumulate pairwise win scores
        scores: dict[str, float] = {code: 0.0 for code in confirmed_codes}
        for code_a, code_b in combinations(confirmed_codes, 2):
            pw_feat = self._build_pairwise_features(
                feat_map[code_a], feat_map[code_b], code_a, code_b
            )
            prob_a = self._predict_prob(pw_feat)
            scores[code_a] += prob_a
            scores[code_b] += 1.0 - prob_a

        return sorted(confirmed_codes, key=lambda c: -scores[c])
