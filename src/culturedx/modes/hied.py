"""HiED-MAS: Hierarchical Evidence-grounded Diagnostic pipeline.

4-stage pipeline:
  Stage 1: Triage → broad ICD-10 categories
  Stage 2: Criterion Checkers → per-disorder criteria evaluation
  Stage 3: Logic Engine → deterministic ICD-10 threshold checking
  Stage 4: Calibrator → statistical confidence scoring + abstention
"""
from __future__ import annotations

import logging
from pathlib import Path

from culturedx.agents.base import AgentInput
from culturedx.agents.criterion_checker import CriterionCheckerAgent
from culturedx.agents.triage import TriageAgent
from culturedx.core.models import (
    CheckerOutput,
    ClinicalCase,
    CriterionResult,
    DiagnosisResult,
    EvidenceBrief,
)
from culturedx.diagnosis.calibrator import ConfidenceCalibrator
from culturedx.diagnosis.logic_engine import DiagnosticLogicEngine
from culturedx.modes.base import BaseModeOrchestrator
from culturedx.ontology.icd10 import get_disorder_name

logger = logging.getLogger(__name__)


class HiEDMode(BaseModeOrchestrator):
    """Hierarchical Evidence-grounded Diagnostic MAS.

    Primary mode implementing the 4-stage pipeline:
    1. Triage: classify into broad ICD-10 categories
    2. Criterion Checkers: per-disorder ICD-10 criteria evaluation
    3. Logic Engine: deterministic threshold checking (no LLM)
    4. Calibrator: statistical confidence + abstention (no LLM)
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

        # Stage 1: Triage
        self.triage = TriageAgent(llm_client, prompts_dir)

        # Stage 2: Criterion Checkers (one per disorder, reuse single agent)
        self.checker = CriterionCheckerAgent(llm_client, prompts_dir)

        # Stage 3: Logic Engine (deterministic)
        self.logic_engine = DiagnosticLogicEngine()

        # Stage 4: Calibrator (statistical)
        self.calibrator = ConfidenceCalibrator(
            abstain_threshold=abstain_threshold,
            comorbid_threshold=comorbid_threshold,
        )

    def diagnose(
        self, case: ClinicalCase, evidence: EvidenceBrief | None = None
    ) -> DiagnosisResult:
        lang = case.language
        if lang not in ("zh", "en"):
            return self._abstain(case, lang)

        transcript_text = self._build_transcript_text(case)
        evidence_map = self._build_evidence_map(evidence) if evidence else {}

        # === Stage 1: Triage ===
        if self.target_disorders is not None:
            # Skip triage when target disorders are explicitly set
            candidate_codes = list(self.target_disorders)
            logger.info("Skipping triage, using %d target disorders", len(candidate_codes))
        else:
            triage_input = AgentInput(
                transcript_text=transcript_text,
                evidence={"evidence_summary": self._build_global_evidence_summary(evidence)} if evidence else None,
                language=lang,
            )
            triage_output = self.triage.run(triage_input)
            if triage_output.parsed and "disorder_codes" in triage_output.parsed:
                candidate_codes = triage_output.parsed["disorder_codes"]
            else:
                logger.warning("Triage failed for case %s, using all disorders", case.case_id)
                from culturedx.ontology.icd10 import list_disorders
                candidate_codes = list_disorders()

        if not candidate_codes:
            return self._abstain(case, lang)

        logger.info("Case %s: %d candidate disorders from triage", case.case_id, len(candidate_codes))

        # === Stage 2: Criterion Checkers ===
        checker_outputs: list[CheckerOutput] = []
        for disorder_code in candidate_codes:
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

        # === Stage 3: Logic Engine (deterministic) ===
        logic_output = self.logic_engine.evaluate(checker_outputs)

        if not logic_output.confirmed:
            # No disorders meet thresholds
            return DiagnosisResult(
                case_id=case.case_id,
                primary_diagnosis=None,
                confidence=0.0,
                decision="abstain",
                criteria_results=checker_outputs,
                mode="hied",
                model_name=self.llm.model,
                language_used=lang,
            )

        # === Stage 4: Calibrator (statistical) ===
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
                mode="hied",
                model_name=self.llm.model,
                language_used=lang,
            )

        return DiagnosisResult(
            case_id=case.case_id,
            primary_diagnosis=cal_output.primary.disorder_code,
            comorbid_diagnoses=[c.disorder_code for c in cal_output.comorbid],
            confidence=cal_output.primary.confidence,
            decision=cal_output.primary.decision,
            criteria_results=checker_outputs,
            mode="hied",
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
            mode="hied",
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

    @staticmethod
    def _build_global_evidence_summary(evidence: EvidenceBrief | None) -> str | None:
        if not evidence or not evidence.symptom_spans:
            return None
        symptoms = [s.text for s in evidence.symptom_spans[:20]]
        return "Extracted symptoms: " + "; ".join(symptoms)
