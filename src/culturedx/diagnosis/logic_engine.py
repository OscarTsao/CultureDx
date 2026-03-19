"""Deterministic Diagnostic Logic Engine — no LLM.

Applies ICD-10 threshold rules to CheckerOutput to determine
which disorders meet diagnostic criteria.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from culturedx.core.models import CheckerOutput, CriterionResult
from culturedx.ontology.icd10 import get_disorder_criteria, get_disorder_threshold

logger = logging.getLogger(__name__)


@dataclass
class LogicEngineResult:
    """Result from the logic engine for one disorder."""
    disorder_code: str
    meets_threshold: bool
    met_count: int
    required_count: int
    rule_explanation: str = ""


@dataclass  
class LogicEngineOutput:
    """Complete output from the logic engine."""
    confirmed: list[LogicEngineResult] = field(default_factory=list)
    rejected: list[LogicEngineResult] = field(default_factory=list)

    @property
    def confirmed_codes(self) -> list[str]:
        return [r.disorder_code for r in self.confirmed]


class DiagnosticLogicEngine:
    """Deterministic ICD-10 diagnostic threshold checker.
    
    No LLM involved. Takes CheckerOutput from criterion checkers
    and applies threshold rules from the ICD-10 ontology.
    """

    def evaluate(self, checker_outputs: list[CheckerOutput]) -> LogicEngineOutput:
        """Evaluate all checker outputs against ICD-10 thresholds."""
        confirmed = []
        rejected = []

        for co in checker_outputs:
            result = self._evaluate_disorder(co)
            if result.meets_threshold:
                confirmed.append(result)
            else:
                rejected.append(result)

        # Sort confirmed by met_count descending (strongest evidence first)
        confirmed.sort(key=lambda r: r.met_count, reverse=True)

        return LogicEngineOutput(confirmed=confirmed, rejected=rejected)

    def _evaluate_disorder(self, co: CheckerOutput) -> LogicEngineResult:
        """Evaluate a single disorder against its threshold rules."""
        threshold = get_disorder_threshold(co.disorder)
        criteria_def = get_disorder_criteria(co.disorder)

        if not threshold or not criteria_def:
            logger.warning("No threshold/criteria for %s, rejecting", co.disorder)
            return LogicEngineResult(
                disorder_code=co.disorder,
                meets_threshold=False,
                met_count=co.criteria_met_count,
                required_count=0,
                rule_explanation=f"No threshold rules found for {co.disorder}",
            )

        met_ids = {cr.criterion_id for cr in co.criteria if cr.status == "met"}

        # Dispatch to specific threshold evaluation
        if "all_required" in threshold and threshold["all_required"]:
            return self._eval_all_required(co.disorder, threshold, criteria_def, met_ids)
        if "min_core" in threshold and "min_total" in threshold:
            return self._eval_core_total(co.disorder, threshold, criteria_def, met_ids)
        if "min_first_rank" in threshold and "min_other" in threshold:
            return self._eval_first_rank(co.disorder, threshold, criteria_def, met_ids)
        if "core_required" in threshold and "min_additional" in threshold:
            return self._eval_core_additional(co.disorder, threshold, criteria_def, met_ids)
        if "min_symptoms" in threshold:
            return self._eval_min_symptoms(co.disorder, threshold, criteria_def, met_ids)
        if "attacks_per_month" in threshold:
            return self._eval_panic(co.disorder, threshold, criteria_def, met_ids)
        if "min_episodes" in threshold:
            return self._eval_bipolar(co.disorder, threshold, criteria_def, met_ids)
        if "duration_weeks" in threshold and "distress_required" in threshold:
            return self._eval_ocd(co.disorder, threshold, criteria_def, met_ids)
        if "frequency_per_week" in threshold:
            return self._eval_frequency(co.disorder, threshold, criteria_def, met_ids)

        # Fallback: generic count check
        total_criteria = len(criteria_def)
        met_count = len(met_ids)
        return LogicEngineResult(
            disorder_code=co.disorder,
            meets_threshold=met_count >= total_criteria,
            met_count=met_count,
            required_count=total_criteria,
            rule_explanation=f"Fallback: {met_count}/{total_criteria} criteria met",
        )

    def _eval_all_required(
        self, code: str, threshold: dict, criteria: dict, met_ids: set[str]
    ) -> LogicEngineResult:
        """All criteria must be met (e.g., F22)."""
        total = len(criteria)
        met = len(met_ids & set(criteria.keys()))
        return LogicEngineResult(
            disorder_code=code,
            meets_threshold=met >= total,
            met_count=met,
            required_count=total,
            rule_explanation=f"All required: {met}/{total}",
        )

    def _eval_core_total(
        self, code: str, threshold: dict, criteria: dict, met_ids: set[str]
    ) -> LogicEngineResult:
        """min_core + min_total (e.g., F32, F33).

        For F33 (recurrence_required=True), criterion A (recurrence evidence)
        must be specifically met in addition to core/total counts.
        """
        min_core = threshold["min_core"]
        min_total = threshold["min_total"]

        core_ids = {k for k, v in criteria.items() if v.get("type") == "core"}
        core_met = len(met_ids & core_ids)
        total_met = len(met_ids & set(criteria.keys()))

        meets = core_met >= min_core and total_met >= min_total

        # Check recurrence requirement (F33: must have criterion A = prior episode)
        if meets and threshold.get("recurrence_required"):
            # Criterion A must be specifically met for recurrent depression
            if "A" not in met_ids:
                meets = False
                return LogicEngineResult(
                    disorder_code=code,
                    meets_threshold=False,
                    met_count=total_met,
                    required_count=min_total,
                    rule_explanation=f"Core: {core_met}/{min_core}, Total: {total_met}/{min_total}, "
                    f"but recurrence criterion A not met",
                )

        return LogicEngineResult(
            disorder_code=code,
            meets_threshold=meets,
            met_count=total_met,
            required_count=min_total,
            rule_explanation=f"Core: {core_met}/{min_core}, Total: {total_met}/{min_total}"
            + (
                ", recurrence confirmed"
                if threshold.get("recurrence_required") and "A" in met_ids
                else ""
            ),
        )

    def _eval_first_rank(
        self, code: str, threshold: dict, criteria: dict, met_ids: set[str]
    ) -> LogicEngineResult:
        """min_first_rank + min_other (e.g., F20 Schizophrenia)."""
        min_fr = threshold["min_first_rank"]
        min_other = threshold["min_other"]

        fr_ids = {k for k, v in criteria.items() if v.get("type") == "first_rank"}
        other_ids = {k for k, v in criteria.items() if v.get("type") == "other"}
        fr_met = len(met_ids & fr_ids)
        other_met = len(met_ids & other_ids)

        # ICD-10 F20: 1 first-rank symptom OR 2 other symptoms
        meets = fr_met >= min_fr or other_met >= min_other
        total_met = fr_met + other_met
        required = min_fr  # minimum path
        return LogicEngineResult(
            disorder_code=code,
            meets_threshold=meets,
            met_count=total_met,
            required_count=required,
            rule_explanation=f"First-rank: {fr_met}/{min_fr} OR Other: {other_met}/{min_other}",
        )

    def _eval_core_additional(
        self, code: str, threshold: dict, criteria: dict, met_ids: set[str]
    ) -> LogicEngineResult:
        """core_required + min_additional (e.g., F40)."""
        min_additional = threshold["min_additional"]

        core_ids = {k for k, v in criteria.items() if v.get("type") == "core"}
        non_core_ids = set(criteria.keys()) - core_ids
        core_met = len(met_ids & core_ids)
        additional_met = len(met_ids & non_core_ids)

        core_all_met = core_met >= len(core_ids)
        meets = core_all_met and additional_met >= min_additional
        total_met = core_met + additional_met
        return LogicEngineResult(
            disorder_code=code,
            meets_threshold=meets,
            met_count=total_met,
            required_count=len(core_ids) + min_additional,
            rule_explanation=f"Core: {core_met}/{len(core_ids)}, Additional: {additional_met}/{min_additional}",
        )

    def _eval_min_symptoms(
        self, code: str, threshold: dict, criteria: dict, met_ids: set[str]
    ) -> LogicEngineResult:
        """min_symptoms count (e.g., F41.1 GAD, F45)."""
        min_symp = threshold["min_symptoms"]
        met_count = len(met_ids & set(criteria.keys()))
        return LogicEngineResult(
            disorder_code=code,
            meets_threshold=met_count >= min_symp,
            met_count=met_count,
            required_count=min_symp,
            rule_explanation=f"Symptoms: {met_count}/{min_symp}",
        )

    def _eval_panic(
        self, code: str, threshold: dict, criteria: dict, met_ids: set[str]
    ) -> LogicEngineResult:
        """Panic disorder: attacks + min symptoms per attack (F41.0)."""
        min_per_attack = threshold["min_symptoms_per_attack"]
        # Core (panic attacks) + symptom count
        core_ids = {k for k, v in criteria.items() if v.get("type") == "core"}
        symptom_ids = set(criteria.keys()) - core_ids
        core_met = len(met_ids & core_ids)
        symptom_met = len(met_ids & symptom_ids)

        meets = core_met >= len(core_ids) and symptom_met >= min_per_attack
        total_met = core_met + symptom_met
        return LogicEngineResult(
            disorder_code=code,
            meets_threshold=meets,
            met_count=total_met,
            required_count=len(core_ids) + min_per_attack,
            rule_explanation=f"Core: {core_met}/{len(core_ids)}, Symptoms: {symptom_met}/{min_per_attack}",
        )

    def _eval_bipolar(
        self, code: str, threshold: dict, criteria: dict, met_ids: set[str]
    ) -> LogicEngineResult:
        """Bipolar: min_episodes + at_least_one_manic (F31)."""
        manic_ids = {k for k, v in criteria.items() if v.get("type") == "manic"}
        has_manic = len(met_ids & manic_ids) > 0
        
        core_ids = {k for k, v in criteria.items() if v.get("type") == "core"}
        core_met = len(met_ids & core_ids) > 0
        
        total_met = len(met_ids & set(criteria.keys()))
        meets = core_met and has_manic
        return LogicEngineResult(
            disorder_code=code,
            meets_threshold=meets,
            met_count=total_met,
            required_count=2,
            rule_explanation=f"Core episodes: {'yes' if core_met else 'no'}, Manic: {'yes' if has_manic else 'no'}",
        )

    def _eval_ocd(
        self, code: str, threshold: dict, criteria: dict, met_ids: set[str]
    ) -> LogicEngineResult:
        """OCD: duration + distress required (F42)."""
        core_ids = {k for k, v in criteria.items() if v.get("type") == "core"}
        distress_ids = {k for k, v in criteria.items() if v.get("type") == "distress"}
        obs_comp_ids = {k for k, v in criteria.items() if v.get("type") in ("obsession", "compulsion")}

        core_met = len(met_ids & core_ids) >= len(core_ids)
        distress_met = len(met_ids & distress_ids) > 0
        has_obs_or_comp = len(met_ids & obs_comp_ids) > 0

        meets = core_met and distress_met and has_obs_or_comp
        total_met = len(met_ids & set(criteria.keys()))
        return LogicEngineResult(
            disorder_code=code,
            meets_threshold=meets,
            met_count=total_met,
            required_count=3,
            rule_explanation=f"Core: {'yes' if core_met else 'no'}, Distress: {'yes' if distress_met else 'no'}, Obs/Comp: {'yes' if has_obs_or_comp else 'no'}",
        )

    def _eval_frequency(
        self, code: str, threshold: dict, criteria: dict, met_ids: set[str]
    ) -> LogicEngineResult:
        """Frequency-based threshold (e.g., F51 sleep disorders)."""
        met_count = len(met_ids & set(criteria.keys()))
        total = len(criteria)
        # For frequency-based, all core criteria should be met
        core_ids = {k for k, v in criteria.items() if v.get("type") == "core"}
        core_met = len(met_ids & core_ids) >= len(core_ids)
        meets = core_met and met_count >= 2
        return LogicEngineResult(
            disorder_code=code,
            meets_threshold=meets,
            met_count=met_count,
            required_count=2,
            rule_explanation=f"Core met: {'yes' if core_met else 'no'}, Total: {met_count}/{total}",
        )
