"""PsyCoT-MAS: Flat criterion checking across all disorders.

Alternative Mode B — drops triage, runs criterion checkers across ALL
supported disorders sequentially. Same Logic Engine and Calibrator as HiED.
Slower but eliminates triage cascade risk.
"""
from __future__ import annotations

import logging
from pathlib import Path

from culturedx.agents.criterion_checker import CriterionCheckerAgent
from culturedx.core.models import (
    CheckerOutput,
    ClinicalCase,
    DiagnosisResult,
    EvidenceBrief,
)
from culturedx.diagnosis.calibrator import ConfidenceCalibrator
from culturedx.diagnosis.comorbidity import ComorbidityResolver
from culturedx.diagnosis.logic_engine import DiagnosticLogicEngine
from culturedx.modes.base import BaseModeOrchestrator
from culturedx.ontology.icd10 import list_disorders

logger = logging.getLogger(__name__)


class PsyCoTMode(BaseModeOrchestrator):
    """PsyCoT-MAS: flat criterion checking without triage.

    Runs criterion checkers across ALL supported disorders (or a specified
    subset), then applies Logic Engine + Calibrator. No triage cascade risk
    but slower than HiED.
    """

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/agents",
        checker_llm_client=None,
        target_disorders: list[str] | None = None,
        prompt_variant: str = "",
        abstain_threshold: float = 0.3,
        comorbid_threshold: float = 0.5,
        comorbid_min_ratio: float = 0.9,
    ) -> None:
        self.mode_name = "psycot"
        self.llm = llm_client
        self.checker_llm = checker_llm_client or llm_client
        self.checker_model_name = (
            getattr(checker_llm_client, "model", None)
            if checker_llm_client is not None
            else None
        )
        self.prompts_dir = Path(prompts_dir)
        self.target_disorders = target_disorders
        self._prompt_variant = ""
        self.prompt_variant = prompt_variant

        # Criterion Checker (reused for all disorders)
        self.checker = CriterionCheckerAgent(self.checker_llm, prompts_dir)

        # Logic Engine (deterministic, no LLM)
        self.logic_engine = DiagnosticLogicEngine()

        # Calibrator (statistical, no LLM)
        self.calibrator = ConfidenceCalibrator(
            abstain_threshold=abstain_threshold,
            comorbid_threshold=comorbid_threshold,
        )

        # Comorbidity resolver
        self.comorbidity_resolver = ComorbidityResolver(
            comorbid_min_ratio=comorbid_min_ratio,
        )

    @property
    def prompt_variant(self) -> str:
        return getattr(self, "_prompt_variant", "")

    @prompt_variant.setter
    def prompt_variant(self, value: str | None) -> None:
        self._prompt_variant = value or ""

    def diagnose(
        self, case: ClinicalCase, evidence: EvidenceBrief | None = None
    ) -> DiagnosisResult:
        lang = case.language
        if lang not in ("zh", "en"):
            return self._abstain(case, lang)

        # When evidence is provided, transcript is supplementary — reduce budget
        max_chars = 8000 if evidence else 20000
        transcript_text = self._build_transcript_text(case, max_chars=max_chars)
        evidence_map = self._build_evidence_map(evidence) if evidence else {}

        # PsyCoT: NO triage. Check ALL disorders.
        if self.target_disorders is not None:
            disorders = list(self.target_disorders)
        else:
            disorders = list_disorders()

        if not disorders:
            return self._abstain(case, lang)

        logger.info("PsyCoT checking %d disorders for case %s", len(disorders), case.case_id)

        # Run criterion checkers in parallel
        checker_outputs = self._parallel_check_criteria(
            self.checker,
            disorders,
            transcript_text,
            evidence_map,
            lang,
            prompt_variant=getattr(self, "_prompt_variant", ""),
            checker_llm_client=self.checker_llm,
        )

        if not checker_outputs:
            return self._abstain(case, lang, criteria_results=[])

        # Logic Engine: deterministic threshold checking
        logic_output = self.logic_engine.evaluate(checker_outputs)

        if not logic_output.confirmed:
            return DiagnosisResult(
                case_id=case.case_id,
                primary_diagnosis=None,
                confidence=0.0,
                decision="abstain",
                criteria_results=checker_outputs,
                mode=self.mode_name,
                model_name=self.llm.model,
                checker_model_name=self.checker_model_name,
                language_used=lang,
            )

        # Calibrator: statistical confidence + abstention
        cal_output = self.calibrator.calibrate(
            confirmed_disorders=logic_output.confirmed_codes,
            checker_outputs=checker_outputs,
            evidence=evidence,
        )

        if cal_output.primary is None:
            return DiagnosisResult(
                case_id=case.case_id,
                primary_diagnosis=None,
                confidence=0.0,
                decision="abstain",
                criteria_results=checker_outputs,
                mode=self.mode_name,
                model_name=self.llm.model,
                checker_model_name=self.checker_model_name,
                language_used=lang,
            )

        # Comorbidity resolution
        all_calibrated = [cal_output.primary] + cal_output.comorbid
        confidences = {c.disorder_code: c.confidence for c in all_calibrated}
        confirmed_codes = [c.disorder_code for c in all_calibrated]

        comorbidity_result = self.comorbidity_resolver.resolve(
            confirmed=confirmed_codes,
            confidences=confidences,
        )

        primary_cal = next(
            (c for c in all_calibrated if c.disorder_code == comorbidity_result.primary),
            cal_output.primary,
        )

        return DiagnosisResult(
            case_id=case.case_id,
            primary_diagnosis=comorbidity_result.primary,
            comorbid_diagnoses=comorbidity_result.comorbid,
            confidence=primary_cal.confidence,
            decision=primary_cal.decision,
            criteria_results=checker_outputs,
            mode=self.mode_name,
            model_name=self.llm.model,
            checker_model_name=self.checker_model_name,
            language_used=lang,
        )
