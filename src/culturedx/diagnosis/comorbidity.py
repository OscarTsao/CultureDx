"""Comorbidity Resolver — ICD-10 exclusion and interaction rules.

Handles:
- Hierarchical exclusion (e.g., F33 supersedes F32, F31 supersedes F32/F33)
- Mutual exclusion (e.g., F20 vs F22)
- Forbidden pairs from ICD-10 exclusion criteria
- Maximum comorbidity limits
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def _pair_key(left: str, right: str) -> frozenset[str]:
    return frozenset((left, right))


# ICD-10 hierarchical exclusion rules: if A is present, exclude B.
# These are directional — A supersedes B.
EXCLUSION_RULES: list[tuple[str, str]] = [
    # F33 (recurrent depressive) supersedes F32 (single episode)
    ("F33", "F32"),
    # F31 (bipolar) with current depressive episode excludes F32/F33
    ("F31", "F32"),
    ("F31", "F33"),
    # Schizophrenia excludes persistent delusional disorder
    ("F20", "F22"),
]

# ICD-10 forbidden comorbidity pairs — these CANNOT coexist.
# Based on ICD-10 exclusion criteria, NOT derived from any dataset.
# Everything NOT in this set is allowed (ICD-10 default: any two
# disorders can co-occur if each independently meets criteria).
FORBIDDEN_COMORBIDITY_PAIRS: set[frozenset[str]] = {
    # F32 excluded by F31 (bipolar supersedes depression)
    _pair_key("F32", "F31"),
    # F33 excluded by F31
    _pair_key("F33", "F31"),
    # F32 and F33 are mutually exclusive (single vs recurrent)
    _pair_key("F32", "F33"),
    # F41.2 (mixed anxiety-depression) excluded when either F32 or F41
    # independently meets full diagnostic criteria
    _pair_key("F41.2", "F32"),
    _pair_key("F41.2", "F33"),
    _pair_key("F41.2", "F41"),
    _pair_key("F41.2", "F41.1"),
    # F20 (schizophrenia) excludes F22 (persistent delusional)
    _pair_key("F20", "F22"),
    # Schizophrenia + mood (should be schizoaffective F25)
    _pair_key("F20", "F32"),
    _pair_key("F20", "F33"),
    _pair_key("F20", "F31"),
    # Stress-related mutual exclusions
    _pair_key("F43.1", "F43.2"),
    # Z71 (counseling) excludes all specific disorders
    _pair_key("Z71", "F32"),
    _pair_key("Z71", "F33"),
    _pair_key("Z71", "F41"),
    _pair_key("Z71", "F41.1"),
    _pair_key("Z71", "F42"),
    _pair_key("Z71", "F43.1"),
    _pair_key("Z71", "F43.2"),
    _pair_key("Z71", "F45"),
    _pair_key("Z71", "F20"),
    _pair_key("Z71", "F31"),
    _pair_key("Z71", "F51"),
    _pair_key("Z71", "F98"),
}


@dataclass
class ComorbidityResult:
    """Result of comorbidity resolution."""
    primary: str
    comorbid: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    exclusion_reasons: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    decision_trace: list[dict[str, str]] = field(default_factory=list)


class ComorbidityResolver:
    """Resolves comorbidity interactions using ICD-10 rules.

    Uses a blacklist (forbidden pairs) rather than a whitelist.
    ICD-10 principle: any two disorders can coexist unless explicitly
    excluded by exclusion criteria.
    """

    def __init__(
        self,
        max_comorbid: int = 3,
        exclusion_rules: list[tuple[str, str]] | None = None,
        forbidden_pairs: set[frozenset[str]] | None = None,
    ) -> None:
        self.max_comorbid = max_comorbid
        self.rules = exclusion_rules if exclusion_rules is not None else EXCLUSION_RULES
        self.forbidden_pairs = (
            set(forbidden_pairs) if forbidden_pairs is not None
            else FORBIDDEN_COMORBIDITY_PAIRS
        )

    def _pair_forbidden(self, a: str, b: str) -> bool:
        """Check if a pair is forbidden, matching at both exact and parent level."""
        a_parent = a.split(".")[0]
        b_parent = b.split(".")[0]
        for left, right in [
            (a, b), (a_parent, b), (a, b_parent), (a_parent, b_parent),
        ]:
            if _pair_key(left, right) in self.forbidden_pairs:
                return True
        return False

    def resolve(
        self,
        confirmed: list[str],
        confidences: dict[str, float] | None = None,
    ) -> ComorbidityResult:
        """Resolve comorbidity from a list of confirmed disorders.

        Args:
            confirmed: List of confirmed disorder codes (ordered by confidence).
            confidences: Optional mapping of disorder code to confidence score
                (used for ordering, not gating).

        Returns:
            ComorbidityResult with primary, comorbid, and excluded lists.
        """
        if not confirmed:
            return ComorbidityResult(primary="", comorbid=[], excluded=[])

        confs = confidences or {}

        # Sort by confidence descending
        sorted_disorders = sorted(
            confirmed,
            key=lambda d: confs.get(d, 0.0),
            reverse=True,
        )

        # Apply hierarchical exclusion rules
        active = list(sorted_disorders)
        excluded = []
        reasons = []
        decision_trace = []

        for superseding, to_exclude in self.rules:
            if superseding in active and to_exclude in active:
                active.remove(to_exclude)
                excluded.append(to_exclude)
                reasons.append(f"{superseding} excludes {to_exclude}")
                decision_trace.append({
                    "disorder": to_exclude,
                    "decision": "excluded",
                    "reason": f"{superseding} excludes {to_exclude}",
                })
                logger.info("Exclusion: %s excludes %s", superseding, to_exclude)

        if not active:
            return ComorbidityResult(
                primary=sorted_disorders[0],
                comorbid=[],
                excluded=excluded,
                exclusion_reasons=reasons,
                decision_trace=decision_trace,
            )

        # Primary is highest-confidence remaining
        primary = active[0]
        decision_trace.append({
            "disorder": primary,
            "decision": "primary",
            "reason": "highest_confidence_remaining_after_exclusions",
        })

        comorbid = []
        rejected = []
        rejection_reasons = []

        for candidate in active[1:]:
            if len(comorbid) >= self.max_comorbid:
                rejected.append(candidate)
                rejection_reasons.append(f"{candidate} rejected: max_comorbid_limit")
                decision_trace.append({
                    "disorder": candidate,
                    "decision": "rejected",
                    "reason": "max_comorbid_limit",
                })
                continue

            # Blacklist check: reject forbidden pairs
            if self._pair_forbidden(primary, candidate):
                rejected.append(candidate)
                rejection_reasons.append(
                    f"{candidate} rejected: forbidden_pair_with_{primary}"
                )
                decision_trace.append({
                    "disorder": candidate,
                    "decision": "rejected",
                    "reason": f"forbidden_pair_with_{primary}",
                })
                continue


            comorbid.append(candidate)
            decision_trace.append({
                "disorder": candidate,
                "decision": "comorbid",
                "reason": "passes_exclusions",
            })

        return ComorbidityResult(
            primary=primary,
            comorbid=comorbid,
            excluded=excluded,
            exclusion_reasons=reasons,
            rejected=rejected,
            rejection_reasons=rejection_reasons,
            decision_trace=decision_trace,
        )
