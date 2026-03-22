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
        self.mode_name = "mas"
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
            return self._abstain(case, lang)

        # Step 1: Identify candidate disorders
        candidates = self._identify_candidates(evidence)
        if not candidates:
            logger.warning("No candidate disorders for case %s", case.case_id)
            return self._abstain(case, lang)

        # Step 2: Build transcript text
        # When evidence is provided, transcript is supplementary — reduce budget
        max_chars = 8000 if evidence else 20000
        transcript_text = self._build_transcript_text(case, max_chars=max_chars)

        # Step 3: Build evidence summary per disorder
        evidence_map = self._build_evidence_map(evidence) if evidence else {}

        # Step 4: Run criterion checkers in parallel
        disorder_names = {
            code: get_disorder_name(code, lang) or code for code in candidates
        }
        checker_outputs = self._parallel_check_criteria(
            self.checker, candidates, transcript_text, evidence_map, lang,
        )

        if not checker_outputs:
            return self._abstain(case, lang, criteria_results=[])

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
                mode=self.mode_name,
                model_name=self.llm.model,
                prompt_hash=diff_output.prompt_hash,
                language_used=lang,
            )

        return self._abstain(case, lang, criteria_results=checker_outputs)

    def _identify_candidates(self, evidence: EvidenceBrief | None) -> list[str]:
        """Identify candidate disorders to check."""
        if self.target_disorders is not None:
            return self.target_disorders
        if evidence and evidence.disorder_evidence:
            return [de.disorder_code for de in evidence.disorder_evidence]
        # Fallback: use all known disorders
        return list_disorders()
