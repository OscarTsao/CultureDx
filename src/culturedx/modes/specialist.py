"""Specialist-MAS mode: triage + specialist agents + LLM judge.

Alternative Mode A — closest to prior MoodAngels MAS pattern.
Included as comparison condition.
"""
from __future__ import annotations

import logging
from pathlib import Path

from culturedx.agents.base import AgentInput
from culturedx.agents.judge import JudgeAgent
from culturedx.agents.specialist import SpecialistAgent
from culturedx.agents.triage import TriageAgent
from culturedx.core.models import (
    ClinicalCase,
    DiagnosisResult,
    EvidenceBrief,
)
from culturedx.modes.base import BaseModeOrchestrator
from culturedx.ontology.icd10 import get_disorder_name, list_disorders

logger = logging.getLogger(__name__)


class SpecialistMode(BaseModeOrchestrator):
    """Specialist-MAS: triage + free-form specialists + LLM judge.

    Pipeline:
    1. Triage: classify into broad categories (same as HiED)
    2. Specialist Agents: free-form diagnostic reasoning per disorder
    3. Judge: synthesize specialist opinions into final diagnosis
    """

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/agents",
        target_disorders: list[str] | None = None,
    ) -> None:
        self.llm = llm_client
        self.prompts_dir = Path(prompts_dir)
        self.target_disorders = target_disorders

        self.triage = TriageAgent(llm_client, prompts_dir)
        self.specialist = SpecialistAgent(llm_client, prompts_dir)
        self.judge = JudgeAgent(llm_client, prompts_dir)

    def diagnose(
        self, case: ClinicalCase, evidence: EvidenceBrief | None = None
    ) -> DiagnosisResult:
        lang = case.language
        if lang not in ("zh", "en"):
            return self._abstain(case, lang)

        transcript_text = self._build_transcript_text(case)
        evidence_map = self._build_evidence_map(evidence) if evidence else {}

        # Stage 1: Triage (or use target disorders)
        if self.target_disorders is not None:
            candidate_codes = list(self.target_disorders)
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
                candidate_codes = list_disorders()

        if not candidate_codes:
            return self._abstain(case, lang)

        # Stage 2: Specialist agents
        specialist_opinions = []
        for code in candidate_codes:
            name = get_disorder_name(code, lang) or code
            evidence_summary = evidence_map.get(code)

            spec_input = AgentInput(
                transcript_text=transcript_text,
                evidence={"evidence_summary": evidence_summary} if evidence_summary else None,
                language=lang,
                extra={"disorder_code": code, "disorder_name": name},
            )
            output = self.specialist.run(spec_input)
            if output.parsed:
                specialist_opinions.append(output.parsed)

        if not specialist_opinions:
            return self._abstain(case, lang)

        # Stage 3: Judge
        judge_input = AgentInput(
            transcript_text=transcript_text,
            language=lang,
            extra={
                "specialist_opinions": specialist_opinions,
                "case_id": case.case_id,
            },
        )
        judge_output = self.judge.run(judge_input)

        if judge_output.parsed:
            return DiagnosisResult(
                case_id=case.case_id,
                primary_diagnosis=judge_output.parsed.get("primary_diagnosis"),
                comorbid_diagnoses=judge_output.parsed.get("comorbid_diagnoses", []),
                confidence=judge_output.parsed.get("confidence", 0.0),
                decision=judge_output.parsed.get("decision", "abstain"),
                mode="specialist",
                model_name=self.llm.model,
                language_used=lang,
            )

        return self._abstain(case, lang)

    def _abstain(self, case: ClinicalCase, lang: str) -> DiagnosisResult:
        return DiagnosisResult(
            case_id=case.case_id,
            primary_diagnosis=None,
            confidence=0.0,
            decision="abstain",
            mode="specialist",
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
                    parts.append(f"[{ce.criterion_id}] (conf={ce.confidence:.2f}): " + "; ".join(span_texts))
            if parts:
                result[de.disorder_code] = "\n".join(parts)
        return result

    @staticmethod
    def _build_global_evidence_summary(evidence: EvidenceBrief | None) -> str | None:
        if not evidence or not evidence.symptom_spans:
            return None
        symptoms = [s.text for s in evidence.symptom_spans[:20]]
        return "Extracted symptoms: " + "; ".join(symptoms)
