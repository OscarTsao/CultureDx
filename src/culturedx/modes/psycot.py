"""PsyCoT-MAS: Flat criterion checking across all disorders.

Alternative Mode B — drops triage, runs criterion checkers across ALL
supported disorders sequentially. Same Logic Engine and Calibrator as HiED.
Slower but eliminates triage cascade risk.
"""
from __future__ import annotations

import logging
from pathlib import Path

from culturedx.agents.base import AgentInput
from culturedx.agents.criterion_checker import CriterionCheckerAgent
from culturedx.core.models import (
    CheckerOutput,
    ClinicalCase,
    CriterionResult,
    DiagnosisResult,
    EvidenceBrief,
)
from culturedx.diagnosis.calibrator import ConfidenceCalibrator
from culturedx.diagnosis.comorbidity import ComorbidityResolver
from culturedx.diagnosis.logic_engine import DiagnosticLogicEngine
from culturedx.modes.base import BaseModeOrchestrator
from culturedx.ontology.icd10 import get_disorder_name, list_disorders

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
        target_disorders: list[str] | None = None,
        abstain_threshold: float = 0.3,
        comorbid_threshold: float = 0.5,
    ) -> None:
        self.llm = llm_client
        self.prompts_dir = Path(prompts_dir)
        self.target_disorders = target_disorders

        # Criterion Checker (reused for all disorders)
        self.checker = CriterionCheckerAgent(llm_client, prompts_dir)

        # Logic Engine (deterministic, no LLM)
        self.logic_engine = DiagnosticLogicEngine()

        # Calibrator (statistical, no LLM)
        self.calibrator = ConfidenceCalibrator(
            abstain_threshold=abstain_threshold,
            comorbid_threshold=comorbid_threshold,
        )

        # Comorbidity resolver
        self.comorbidity_resolver = ComorbidityResolver()

    def diagnose(
        self, case: ClinicalCase, evidence: EvidenceBrief | None = None
    ) -> DiagnosisResult:
        lang = case.language
        if lang not in ("zh", "en"):
            return self._abstain(case, lang)

        transcript_text = self._build_transcript_text(case)
        evidence_map = self._build_evidence_map(evidence) if evidence else {}

        # PsyCoT: NO triage. Check ALL disorders.
        if self.target_disorders is not None:
            disorders = list(self.target_disorders)
        else:
            disorders = list_disorders()

        if not disorders:
            return self._abstain(case, lang)

        logger.info("PsyCoT checking %d disorders for case %s", len(disorders), case.case_id)

        # Run criterion checker for every disorder
        checker_outputs: list[CheckerOutput] = []
        for disorder_code in disorders:
            name = get_disorder_name(disorder_code, lang) or disorder_code
            evidence_summary = evidence_map.get(disorder_code)

            checker_input = AgentInput(
                transcript_text=transcript_text,
                evidence={"evidence_summary": evidence_summary} if evidence_summary else None,
                language=lang,
                extra={"disorder_code": disorder_code},
            )
            output = self.checker.run(checker_input)
            if output.parsed:
                co = CheckerOutput(
                    disorder=output.parsed["disorder"],
                    criteria=output.parsed["criteria"],
                    criteria_met_count=output.parsed["criteria_met_count"],
                    criteria_required=output.parsed["criteria_required"],
                )
                checker_outputs.append(co)

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
                mode="psycot",
                model_name=self.llm.model,
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
                mode="psycot",
                model_name=self.llm.model,
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
            mode="psycot",
            model_name=self.llm.model,
            language_used=lang,
        )

    def _abstain(
        self, case: ClinicalCase, lang: str, criteria_results: list[CheckerOutput] | None = None
    ) -> DiagnosisResult:
        return DiagnosisResult(
            case_id=case.case_id,
            primary_diagnosis=None,
            confidence=0.0,
            decision="abstain",
            criteria_results=criteria_results or [],
            mode="psycot",
            model_name=self.llm.model,
            language_used=lang,
        )

    @staticmethod
    def _build_transcript_text(case: ClinicalCase) -> str:
        lines = []
        for turn in case.transcript:
            speaker = turn.speaker.capitalize()
            lines.append(f"{speaker}: {turn.text}")
        return "\n".join(lines)

    @staticmethod
    def _build_evidence_map(evidence: EvidenceBrief) -> dict[str, str]:
        result = {}
        for de in evidence.disorder_evidence:
            parts = []
            for ce in de.criteria_evidence:
                span_texts = [s.text for s in ce.spans]
                if span_texts:
                    parts.append(
                        f"[{ce.criterion_id}] (conf={ce.confidence:.2f}): "
                        + "; ".join(span_texts)
                    )
            if parts:
                result[de.disorder_code] = "\n".join(parts)
        return result
