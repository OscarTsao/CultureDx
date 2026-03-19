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
        evidence_weight: float = 0.3,
        criterion_weight: float = 0.4,
        threshold_weight: float = 0.3,
    ) -> None:
        self.abstain_threshold = abstain_threshold
        self.comorbid_threshold = comorbid_threshold
        self.evidence_weight = evidence_weight
        self.criterion_weight = criterion_weight
        self.threshold_weight = threshold_weight

    def calibrate(
        self,
        confirmed_disorders: list[str],
        checker_outputs: list[CheckerOutput],
        evidence: EvidenceBrief | None = None,
    ) -> CalibrationOutput:
        """Calibrate confidence for confirmed disorders.
        
        Args:
            confirmed_disorders: Disorder codes confirmed by logic engine.
            checker_outputs: All checker outputs (confirmed + rejected).
            evidence: Optional evidence brief for coverage computation.
        """
        # Build checker map
        checker_map = {co.disorder: co for co in checker_outputs}

        # Compute calibrated scores for confirmed disorders
        scored = []
        for code in confirmed_disorders:
            co = checker_map.get(code)
            if co is None:
                continue
            cal = self._compute_calibrated(code, co, evidence)
            scored.append(cal)

        # Sort by confidence descending
        scored.sort(key=lambda c: c.confidence, reverse=True)

        # Split into primary, comorbid, abstained
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
        for de in evidence.disorder_evidence:
            if de.disorder_code == disorder_code:
                met_criteria_ids = {
                    cr.criterion_id for cr in checker_output.criteria
                    if cr.status == "met"
                }
                total_met = len(met_criteria_ids)
                if total_met == 0:
                    return 0.0
                covered = sum(
                    1 for ce in de.criteria_evidence
                    if ce.spans and ce.criterion_id in met_criteria_ids
                )
                return min(1.0, covered / total_met)

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
