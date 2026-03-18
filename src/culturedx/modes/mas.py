"""MAS mode orchestrator: multi-agent diagnostic pipeline."""
from __future__ import annotations

import logging
from pathlib import Path

from culturedx.agents.base import AgentInput
from culturedx.agents.criterion_checker import CriterionCheckerAgent
from culturedx.agents.differential import DifferentialDiagnosisAgent
from culturedx.core.models import (
    CheckerOutput,
    ClinicalCase,
    CriterionResult,
    DiagnosisResult,
    EvidenceBrief,
)
from culturedx.modes.base import BaseModeOrchestrator
from culturedx.ontology.icd10 import get_disorder_name, list_disorders

logger = logging.getLogger(__name__)


class MASMode(BaseModeOrchestrator):
    """Multi-agent system mode: criterion checking + differential diagnosis."""

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/agents",
        target_disorders: list[str] | None = None,
    ) -> None:
        self.llm = llm_client
        self.prompts_dir = Path(prompts_dir)
        self.target_disorders = target_disorders
        self.checker = CriterionCheckerAgent(llm_client, prompts_dir)
        self.differential = DifferentialDiagnosisAgent(llm_client, prompts_dir)

    def diagnose(
        self, case: ClinicalCase, evidence: EvidenceBrief | None = None
    ) -> DiagnosisResult:
        lang = case.language
        if lang not in ("zh", "en"):
            return DiagnosisResult(
                case_id=case.case_id,
                primary_diagnosis=None,
                confidence=0.0,
                decision="abstain",
                mode="mas",
                model_name=self.llm.model,
                language_used=lang,
            )

        # Step 1: Identify candidate disorders
        candidates = self._identify_candidates(evidence)
        if not candidates:
            logger.warning("No candidate disorders for case %s", case.case_id)
            return DiagnosisResult(
                case_id=case.case_id,
                primary_diagnosis=None,
                confidence=0.0,
                decision="abstain",
                mode="mas",
                model_name=self.llm.model,
                language_used=lang,
            )

        # Step 2: Build transcript text
        transcript_text = self._build_transcript_text(case)

        # Step 3: Build evidence summary per disorder
        evidence_map = self._build_evidence_map(evidence) if evidence else {}

        # Step 4: Run criterion checker per disorder
        checker_outputs: list[CheckerOutput] = []
        disorder_names: dict[str, str] = {}
        for disorder_code in candidates:
            name = get_disorder_name(disorder_code, lang) or disorder_code
            disorder_names[disorder_code] = name

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
            return DiagnosisResult(
                case_id=case.case_id,
                primary_diagnosis=None,
                confidence=0.0,
                decision="abstain",
                mode="mas",
                model_name=self.llm.model,
                language_used=lang,
            )

        # Step 5: Run differential diagnosis
        diff_input = AgentInput(
            transcript_text=transcript_text,
            language=lang,
            extra={
                "checker_outputs": checker_outputs,
                "case_id": case.case_id,
                "disorder_names": disorder_names,
            },
        )
        diff_output = self.differential.run(diff_input)

        if diff_output.parsed:
            return DiagnosisResult(
                case_id=diff_output.parsed["case_id"],
                primary_diagnosis=diff_output.parsed["primary_diagnosis"],
                comorbid_diagnoses=diff_output.parsed["comorbid_diagnoses"],
                confidence=diff_output.parsed["confidence"],
                decision=diff_output.parsed["decision"],
                criteria_results=checker_outputs,
                mode="mas",
                model_name=self.llm.model,
                prompt_hash=diff_output.prompt_hash,
                language_used=lang,
            )

        return DiagnosisResult(
            case_id=case.case_id,
            primary_diagnosis=None,
            confidence=0.0,
            decision="abstain",
            criteria_results=checker_outputs,
            mode="mas",
            model_name=self.llm.model,
            language_used=lang,
        )

    def _identify_candidates(self, evidence: EvidenceBrief | None) -> list[str]:
        """Identify candidate disorders to check."""
        if self.target_disorders:
            return self.target_disorders
        if evidence and evidence.disorder_evidence:
            return [de.disorder_code for de in evidence.disorder_evidence]
        # Fallback: use all known disorders
        return list_disorders()

    @staticmethod
    def _build_transcript_text(case: ClinicalCase) -> str:
        """Build plain text from transcript turns."""
        lines = []
        for turn in case.transcript:
            speaker = turn.speaker.capitalize()
            lines.append(f"{speaker}: {turn.text}")
        return "\n".join(lines)

    @staticmethod
    def _build_evidence_map(evidence: EvidenceBrief) -> dict[str, str]:
        """Build per-disorder evidence summary strings from EvidenceBrief."""
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
