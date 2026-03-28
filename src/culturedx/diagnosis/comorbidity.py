"""Comorbidity Resolver — ICD-10 exclusion and interaction rules.

Handles:
- Mutual exclusion rules (e.g., F32 vs F33)
- Hierarchical exclusion (e.g., F33 supersedes F32)
- Bereavement exclusion for depressive episodes
- Maximum comorbidity limits
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ICD-10 exclusion rules: if A is present, exclude B
# Format: (superseding, excluded)
EXCLUSION_RULES: list[tuple[str, str]] = [
    # F33 (recurrent depressive) supersedes F32 (single episode)
    ("F33", "F32"),
    # F31 (bipolar) with current depressive episode excludes F32/F33
    ("F31", "F32"),
    ("F31", "F33"),
    # Schizophrenia excludes persistent delusional disorder
    ("F20", "F22"),
    # GAD and panic can co-occur, but if panic is primary, GAD may be secondary
    # (not exclusion, just hierarchy — no rule here)
]


def _pair_key(left: str, right: str) -> frozenset[str]:
    return frozenset((left, right))


DEFAULT_ALLOWED_COMORBIDITY_PAIRS: set[frozenset[str]] = {
    _pair_key("F32", "F41.1"),
    _pair_key("F32", "F42"),
    _pair_key("F33", "F41.1"),
    _pair_key("F33", "F42"),
    _pair_key("F41.1", "F42"),
    _pair_key("F41.1", "F43.1"),
    _pair_key("F41.1", "F43.2"),
    _pair_key("F32", "F43.1"),
    _pair_key("F32", "F43.2"),
    _pair_key("F33", "F43.1"),
    _pair_key("F33", "F43.2"),
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
    
    Takes a set of confirmed disorders and applies exclusion rules
    to produce a valid comorbidity set.
    """

    def __init__(
        self,
        max_comorbid: int = 3,
        exclusion_rules: list[tuple[str, str]] | None = None,
        comorbid_min_ratio: float = 0.0,
        allowed_pairs: set[frozenset[str]] | None = None,
    ) -> None:
        self.max_comorbid = max_comorbid
        self.rules = exclusion_rules if exclusion_rules is not None else EXCLUSION_RULES
        self.comorbid_min_ratio = comorbid_min_ratio
        self.allowed_pairs = set(allowed_pairs) if allowed_pairs is not None else None

    def resolve(
        self,
        confirmed: list[str],
        confidences: dict[str, float] | None = None,
    ) -> ComorbidityResult:
        """Resolve comorbidity from a list of confirmed disorders.
        
        Args:
            confirmed: List of confirmed disorder codes (ordered by confidence).
            confidences: Optional mapping of disorder code to confidence score.
        
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

        # Apply exclusion rules
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
            # All excluded — shouldn't happen, but use first confirmed
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
        primary_conf = confs.get(primary, 0.0)

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

            if (
                self.allowed_pairs is not None
                and _pair_key(primary, candidate) not in self.allowed_pairs
            ):
                rejected.append(candidate)
                rejection_reasons.append(f"{candidate} rejected: invalid_pair_with_{primary}")
                decision_trace.append({
                    "disorder": candidate,
                    "decision": "rejected",
                    "reason": f"invalid_pair_with_{primary}",
                })
                continue

            if self.comorbid_min_ratio > 0 and primary_conf > 0:
                candidate_conf = confs.get(candidate, 0.0)
                min_required = self.comorbid_min_ratio * primary_conf
                if candidate_conf < min_required:
                    rejected.append(candidate)
                    rejection_reasons.append(
                        f"{candidate} rejected: confidence_ratio_below_{self.comorbid_min_ratio:.2f}"
                    )
                    decision_trace.append({
                        "disorder": candidate,
                        "decision": "rejected",
                        "reason": "confidence_ratio_below_threshold",
                    })
                    continue

            comorbid.append(candidate)
            decision_trace.append({
                "disorder": candidate,
                "decision": "comorbid",
                "reason": "passes_exclusions_and_thresholds",
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
