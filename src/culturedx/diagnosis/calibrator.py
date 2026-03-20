"""Confidence Calibrator — statistical, no LLM.

Computes calibrated diagnostic confidence from:
- Criterion checker confidence scores
- Evidence coverage
- Logic engine threshold satisfaction ratio
- Somatization mapper hit rate (if applicable)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from culturedx.core.models import CheckerOutput, CriterionResult, EvidenceBrief

logger = logging.getLogger(__name__)

# Common Chinese stop characters that inflate character-set overlap
_ZH_STOP_CHARS = frozenset("的了是我有在不会很也都你他她它这那个人们要和就")


def _evidence_overlaps(a: str, b: str) -> bool:
    """Check if two evidence strings share substantial word-level overlap."""
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    # Character-level set overlap for Chinese text, filtering stop chars
    set_a = set(a) - _ZH_STOP_CHARS
    set_b = set(b) - _ZH_STOP_CHARS
    if not set_a or not set_b:
        return False
    overlap = len(set_a & set_b) / len(set_a | set_b)
    return overlap > 0.5


@dataclass
class CalibratedDiagnosis:
    """A diagnosis with calibrated confidence and decision."""
    disorder_code: str
    confidence: float
    decision: str  # "diagnosis" or "abstain"
    evidence_coverage: float = 0.0
    avg_criterion_confidence: float = 0.0
    threshold_ratio: float = 0.0
    criteria_met_count: int = 0
    criteria_total_count: int = 0
    # V2 signal fields
    core_score: float = 0.0
    uniqueness_score: float = 0.0
    margin_score: float = 0.0
    variance_penalty: float = 0.0
    info_content_score: float = 0.0


@dataclass
class CalibrationOutput:
    """Complete calibrator output."""
    primary: CalibratedDiagnosis | None = None
    comorbid: list[CalibratedDiagnosis] = field(default_factory=list)
    abstained: list[CalibratedDiagnosis] = field(default_factory=list)


class ConfidenceCalibrator:
    """Statistical confidence calibrator for diagnostic decisions.
    
    No LLM. Combines multiple signals into a calibrated confidence score.
    """

    def __init__(
        self,
        abstain_threshold: float = 0.3,
        comorbid_threshold: float = 0.5,
        version: int = 2,
        # V1 weights (backward compat)
        evidence_weight: float = 0.3,
        criterion_weight: float = 0.4,
        threshold_weight: float = 0.3,
    ) -> None:
        self.abstain_threshold = abstain_threshold
        self.comorbid_threshold = comorbid_threshold
        self.version = version
        self.evidence_weight = evidence_weight
        self.criterion_weight = criterion_weight
        self.threshold_weight = threshold_weight
        # V2 weights — optimal values from grid search (sum = 1.00)
        # uniqueness=0: character-set overlap cannot detect semantic overlap in
        #   Chinese paraphrased evidence, so the signal is unreliable.
        # info_content=0: structurally favors disorders with more ICD-10 criteria
        #   (F32 always wins), producing systematic bias against shorter checklists.
        # The feature computation code is kept below for future analysis.
        self.v2_weights = {
            "core_score": 0.30,
            "avg_confidence": 0.207,
            "threshold_ratio": 0.207,
            "evidence_coverage": 0.207,
            "uniqueness": 0.00,
            "margin": 0.08,
            "variance": 0.00,
            "info_content": 0.00,
        }

    def calibrate(
        self,
        confirmed_disorders: list[str],
        checker_outputs: list[CheckerOutput],
        evidence: EvidenceBrief | None = None,
        confirmation_types: dict[str, str] | None = None,
    ) -> CalibrationOutput:
        """Calibrate confidence for confirmed disorders.
        
        Args:
            confirmed_disorders: Disorder codes confirmed by logic engine.
            checker_outputs: All checker outputs (confirmed + rejected).
            evidence: Optional evidence brief for coverage computation.
        """
        checker_map = {co.disorder: co for co in checker_outputs}

        # Get confirmed checker outputs for cross-disorder comparison
        confirmed_outputs = [
            checker_map[code] for code in confirmed_disorders
            if code in checker_map
        ]

        scored = []
        for code in confirmed_disorders:
            co = checker_map.get(code)
            if co is None:
                continue
            if self.version >= 2:
                cal = self._compute_calibrated_v2(
                    code, co, confirmed_outputs, evidence,
                )
            else:
                cal = self._compute_calibrated(code, co, evidence)
            scored.append(cal)

        # Apply soft confirmation penalty
        if confirmation_types:
            for cal in scored:
                ctype = confirmation_types.get(cal.disorder_code)
                if ctype == "soft":
                    cal.confidence *= 0.85

        # Sort by confidence descending
        scored.sort(key=lambda c: c.confidence, reverse=True)

        # Split into primary, comorbid, abstained (unchanged)
        primary = None
        comorbid = []
        abstained = []

        for cal in scored:
            if cal.confidence < self.abstain_threshold:
                cal.decision = "abstain"
                abstained.append(cal)
            elif primary is None:
                cal.decision = "diagnosis"
                primary = cal
            elif cal.confidence >= self.comorbid_threshold:
                cal.decision = "diagnosis"
                comorbid.append(cal)
            else:
                cal.decision = "diagnosis"
                comorbid.append(cal)

        return CalibrationOutput(
            primary=primary,
            comorbid=comorbid,
            abstained=abstained,
        )

    def _compute_calibrated(
        self,
        disorder_code: str,
        checker_output: CheckerOutput,
        evidence: EvidenceBrief | None,
    ) -> CalibratedDiagnosis:
        """Compute calibrated confidence for a single disorder."""
        # 1. Average criterion confidence (for met criteria)
        met_criteria = [
            cr for cr in checker_output.criteria if cr.status == "met"
        ]
        avg_conf = (
            sum(cr.confidence for cr in met_criteria) / len(met_criteria)
            if met_criteria
            else 0.0
        )

        # 2. Threshold satisfaction ratio (use ICD-10 ontology required count)
        from culturedx.ontology.icd10 import get_disorder_threshold
        threshold = get_disorder_threshold(disorder_code)
        required = self._compute_required_from_threshold(
            threshold, checker_output, disorder_code
        )

        if required > 0:
            threshold_ratio = min(1.0, checker_output.criteria_met_count / required)
        else:
            threshold_ratio = 1.0 if checker_output.criteria_met_count > 0 else 0.0

        # 3. Evidence coverage (what fraction of criteria have evidence spans)
        evidence_coverage = self._compute_evidence_coverage(
            disorder_code, checker_output, evidence
        )

        # Weighted combination
        confidence = (
            self.criterion_weight * avg_conf
            + self.threshold_weight * threshold_ratio
            + self.evidence_weight * evidence_coverage
        )
        confidence = max(0.0, min(1.0, confidence))

        met_count = len(met_criteria)
        total_count = len(checker_output.criteria)

        return CalibratedDiagnosis(
            disorder_code=disorder_code,
            confidence=confidence,
            decision="",  # Set by calibrate()
            evidence_coverage=evidence_coverage,
            avg_criterion_confidence=avg_conf,
            threshold_ratio=threshold_ratio,
            criteria_met_count=met_count,
            criteria_total_count=total_count,
        )

    def _compute_calibrated_v2(
        self,
        disorder_code: str,
        checker_output: CheckerOutput,
        all_confirmed_outputs: list[CheckerOutput],
        evidence: EvidenceBrief | None,
    ) -> CalibratedDiagnosis:
        """V2 calibration with 6 signals for better disorder differentiation."""
        # Existing signals
        met_criteria = [cr for cr in checker_output.criteria if cr.status == "met"]
        avg_conf = (
            sum(cr.confidence for cr in met_criteria) / len(met_criteria)
            if met_criteria else 0.0
        )

        from culturedx.ontology.icd10 import get_disorder_threshold
        threshold = get_disorder_threshold(disorder_code)
        required = self._compute_required_from_threshold(
            threshold, checker_output, disorder_code
        )
        threshold_ratio = (
            min(1.0, checker_output.criteria_met_count / required)
            if required > 0
            else (1.0 if checker_output.criteria_met_count > 0 else 0.0)
        )

        evidence_coverage = self._compute_evidence_coverage(
            disorder_code, checker_output, evidence
        )

        # NEW V2 signals
        core_score = self._compute_core_score(checker_output, disorder_code)
        uniqueness = self._compute_evidence_uniqueness(
            disorder_code, checker_output, all_confirmed_outputs
        )
        margin = self._compute_margin_score(checker_output, disorder_code, required)
        variance = self._compute_variance_penalty(checker_output)
        info_content = self._compute_info_content(checker_output)

        # Weighted combination
        w = self.v2_weights
        confidence = (
            w["core_score"] * core_score
            + w["avg_confidence"] * avg_conf
            + w["threshold_ratio"] * threshold_ratio
            + w["evidence_coverage"] * evidence_coverage
            + w.get("uniqueness", 0) * uniqueness
            + w["margin"] * margin
            + w["variance"] * variance
            + w.get("info_content", 0) * info_content
        )
        confidence = max(0.0, min(1.0, confidence))

        met_count = len(met_criteria)
        total_count = len(checker_output.criteria)

        return CalibratedDiagnosis(
            disorder_code=disorder_code,
            confidence=confidence,
            decision="",
            evidence_coverage=evidence_coverage,
            avg_criterion_confidence=avg_conf,
            threshold_ratio=threshold_ratio,
            criteria_met_count=met_count,
            criteria_total_count=total_count,
            core_score=core_score,
            uniqueness_score=uniqueness,
            margin_score=margin,
            variance_penalty=variance,
            info_content_score=info_content,
        )

    @staticmethod
    def _compute_core_score(checker_output: CheckerOutput, disorder_code: str) -> float:
        """Weighted criterion score: core criteria count 1.5x, duration 1.3x, others 1.0x."""
        from culturedx.ontology.icd10 import get_disorder_criteria
        criteria_def = get_disorder_criteria(disorder_code) or {}

        TYPE_WEIGHTS = {
            "core": 1.5,
            "duration": 1.3,
            "first_rank": 1.5,
            "exclusion": 1.2,
        }

        weighted_sum = 0.0
        max_possible = 0.0
        for cr in checker_output.criteria:
            cdef = criteria_def.get(cr.criterion_id, {})
            ctype = cdef.get("type", "")
            w = TYPE_WEIGHTS.get(ctype, 1.0)
            max_possible += w
            if cr.status == "met":
                weighted_sum += w * cr.confidence

        return weighted_sum / max_possible if max_possible > 0 else 0.0

    @staticmethod
    def _compute_evidence_uniqueness(
        disorder_code: str,
        checker_output: CheckerOutput,
        all_confirmed_outputs: list[CheckerOutput],
    ) -> float:
        """Fraction of met criteria whose evidence is unique to this disorder."""
        met_criteria = [cr for cr in checker_output.criteria if cr.status == "met"]
        if not met_criteria:
            return 0.0

        # Collect evidence texts from other confirmed disorders
        other_evidence: set[str] = set()
        for co in all_confirmed_outputs:
            if co.disorder == disorder_code:
                continue
            for cr in co.criteria:
                if cr.status == "met" and cr.evidence and cr.evidence.strip():
                    other_evidence.add(cr.evidence.strip().lower())

        if not other_evidence:
            return 1.0  # No other disorders — all evidence unique

        unique = 0
        total_with_evidence = 0
        for cr in met_criteria:
            if cr.evidence and cr.evidence.strip():
                total_with_evidence += 1
                normalized = cr.evidence.strip().lower()
                # Check for word-level overlap with any other disorder's evidence
                is_shared = any(
                    _evidence_overlaps(normalized, other_ev)
                    for other_ev in other_evidence
                )
                if not is_shared:
                    unique += 1

        return unique / total_with_evidence if total_with_evidence > 0 else 0.5

    @staticmethod
    def _compute_margin_score(
        checker_output: CheckerOutput, disorder_code: str, required: int,
    ) -> float:
        """Score for how far criteria met exceeds the minimum threshold.

        Normalized by max possible excess for the disorder so that
        F41.1 (5 criteria, threshold 4, max excess 1) and F32 (11
        criteria, threshold 4, max excess 7) are on equal footing when
        all criteria are met.
        """
        import math

        met_count = sum(1 for cr in checker_output.criteria if cr.status == "met")
        total_criteria = len(checker_output.criteria)

        if required <= 0:
            return 0.5

        excess = met_count - required
        if excess <= 0:
            return 0.0

        max_excess = max(total_criteria - required, 1)
        excess_ratio = excess / max_excess  # [0, 1] regardless of checklist length
        return min(1.0, math.log1p(excess_ratio * 7) / math.log(8))

    @staticmethod
    def _compute_variance_penalty(checker_output: CheckerOutput) -> float:
        """Penalty for high variance in criterion confidence. Returns [0, 1]."""
        met_criteria = [cr for cr in checker_output.criteria if cr.status == "met"]
        if len(met_criteria) <= 1:
            return 1.0

        confs = [cr.confidence for cr in met_criteria]
        mean = sum(confs) / len(confs)
        variance = sum((c - mean) ** 2 for c in confs) / len(confs)
        normalized_var = min(1.0, variance / 0.25)
        return 1.0 - normalized_var

    @staticmethod
    def _compute_info_content(checker_output: CheckerOutput) -> float:
        """Information content: rewards more met criteria in absolute terms.
        
        A diagnosis supported by 8 met criteria has more diagnostic evidence
        than one supported by 4 criteria, regardless of total criteria count.
        Saturates at 8 met criteria.
        """
        import math
        met_count = sum(1 for cr in checker_output.criteria if cr.status == "met")
        # Sigmoid-like scaling: 1→0.12, 3→0.35, 5→0.58, 7→0.80, 8→0.88, 10→1.0
        return min(1.0, math.log1p(met_count) / math.log1p(10))

    @staticmethod
    def _compute_evidence_coverage(
        disorder_code: str,
        checker_output: CheckerOutput,
        evidence: EvidenceBrief | None,
    ) -> float:
        """Compute what fraction of met criteria have supporting evidence.

        Normalized by met criteria count (not total) to avoid penalizing
        disorders with more criteria, where unmet criteria naturally lack evidence.
        """
        if not evidence:
            met_criteria = [
                cr for cr in checker_output.criteria if cr.status == "met"
            ]
            total_met = len(met_criteria)
            if total_met == 0:
                return 0.0
            has_evidence = sum(
                1 for cr in met_criteria
                if cr.evidence is not None and cr.evidence.strip()
            )
            return has_evidence / total_met

        # With evidence brief, check disorder-specific evidence
        # Weight by uniqueness: unique evidence contributes full credit,
        # shared evidence contributes partial credit (min 0.3)
        for de in evidence.disorder_evidence:
            if de.disorder_code == disorder_code:
                met_criteria_ids = {
                    cr.criterion_id for cr in checker_output.criteria
                    if cr.status == "met"
                }
                total_met = len(met_criteria_ids)
                if total_met == 0:
                    return 0.0
                weighted_coverage = 0.0
                for ce in de.criteria_evidence:
                    if ce.spans and ce.criterion_id in met_criteria_ids:
                        # Scale by uniqueness: 1.0 for unique, 0.3 min for shared
                        weight = max(0.3, getattr(ce, "uniqueness_score", 1.0))
                        weighted_coverage += weight
                return min(1.0, weighted_coverage / total_met)

        return 0.0

    @staticmethod
    def _compute_required_from_threshold(
        threshold: dict, checker_output: CheckerOutput, disorder_code: str
    ) -> int:
        """Compute the effective required criterion count from ICD-10 threshold.

        Handles all threshold schemas to ensure fair confidence comparison
        across disorders with different threshold types.
        """
        if not threshold:
            return max(checker_output.criteria_required, 1)

        # Schema: min_core + min_total (F32, F33)
        if "min_total" in threshold:
            return max(threshold["min_total"], threshold.get("min_core", 0))

        # Schema: min_symptoms (F41.1 GAD)
        if "min_symptoms" in threshold:
            return threshold["min_symptoms"]

        # Schema: all_required (F22)
        if threshold.get("all_required"):
            from culturedx.ontology.icd10 import get_disorder_criteria
            criteria = get_disorder_criteria(disorder_code)
            return len(criteria) if criteria else checker_output.criteria_required

        # Schema: min_first_rank + min_other (F20)
        if "min_first_rank" in threshold and "min_other" in threshold:
            # Easier path: 1 first-rank symptom
            return threshold["min_first_rank"]

        # Schema: core_required + min_additional (F40)
        if "min_additional" in threshold:
            from culturedx.ontology.icd10 import get_disorder_criteria
            criteria = get_disorder_criteria(disorder_code) or {}
            core_count = sum(
                1 for v in criteria.values() if v.get("type") == "core"
            )
            return core_count + threshold["min_additional"]

        # Schema: attacks_per_month + min_symptoms_per_attack (F41.0)
        if "min_symptoms_per_attack" in threshold:
            from culturedx.ontology.icd10 import get_disorder_criteria
            criteria = get_disorder_criteria(disorder_code) or {}
            core_count = sum(
                1 for v in criteria.values() if v.get("type") == "core"
            )
            return core_count + threshold["min_symptoms_per_attack"]

        # Schema: min_episodes + at_least_one_manic (F31)
        if "min_episodes" in threshold:
            return 2  # core + manic

        # Schema: duration_weeks + distress_required (F42 OCD)
        if "distress_required" in threshold:
            return 3  # core + distress + obs/comp

        # Schema: frequency_per_week (F51)
        if "frequency_per_week" in threshold:
            return 2  # core + at least 1 symptom, as logic engine requires

        # Schema: trauma_required (F43.1 PTSD)
        if "trauma_required" in threshold:
            from culturedx.ontology.icd10 import get_disorder_criteria
            criteria = get_disorder_criteria(disorder_code) or {}
            return len(criteria) if criteria else 3

        # Schema: min_somatic_groups (F45)
        if "min_somatic_groups" in threshold:
            return threshold["min_somatic_groups"] + 1  # groups + core

        # Schema: onset_within_month (F43.2 adjustment)
        if "onset_within_month" in threshold:
            from culturedx.ontology.icd10 import get_disorder_criteria
            criteria = get_disorder_criteria(disorder_code) or {}
            return len(criteria) if criteria else 2

        # Fallback
        return max(checker_output.criteria_required, 1)
