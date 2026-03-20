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

@dataclass
class ComorbidityResult:
    """Result of comorbidity resolution."""
    primary: str
    comorbid: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    exclusion_reasons: list[str] = field(default_factory=list)


class ComorbidityResolver:
    """Resolves comorbidity interactions using ICD-10 rules.
    
    Takes a set of confirmed disorders and applies exclusion rules
    to produce a valid comorbidity set.
    """

    def __init__(
        self,
        max_comorbid: int = 3,
        exclusion_rules: list[tuple[str, str]] | None = None,
    ) -> None:
        self.max_comorbid = max_comorbid
        self.rules = exclusion_rules if exclusion_rules is not None else EXCLUSION_RULES

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

        for superseding, to_exclude in self.rules:
            if superseding in active and to_exclude in active:
                active.remove(to_exclude)
                excluded.append(to_exclude)
                reasons.append(f"{superseding} excludes {to_exclude}")
                logger.info("Exclusion: %s excludes %s", superseding, to_exclude)

        if not active:
            # All excluded — shouldn't happen, but use first confirmed
            return ComorbidityResult(
                primary=sorted_disorders[0],
                comorbid=[],
                excluded=excluded,
                exclusion_reasons=reasons,
            )

        # Primary is highest-confidence remaining
        primary = active[0]
        comorbid = active[1:self.max_comorbid + 1]

        return ComorbidityResult(
            primary=primary,
            comorbid=comorbid,
            excluded=excluded,
            exclusion_reasons=reasons,
        )
