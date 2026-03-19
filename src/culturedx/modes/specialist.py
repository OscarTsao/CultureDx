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
        self.mode_name = "specialist"
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

        # Stage 2: Specialist agents (parallel)
        specialist_opinions = self._parallel_specialist_opinions(
            candidate_codes, transcript_text, evidence_map, lang,
        )

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

    def _parallel_specialist_opinions(
        self,
        candidate_codes: list[str],
        transcript_text: str,
        evidence_map: dict[str, str],
        lang: str,
        max_workers: int = 4,
    ) -> list[dict]:
        """Run specialist agents in parallel."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _run_one(code: str) -> dict | None:
            name = get_disorder_name(code, lang) or code
            evidence_summary = evidence_map.get(code)
            spec_input = AgentInput(
                transcript_text=transcript_text,
                evidence={"evidence_summary": evidence_summary} if evidence_summary else None,
                language=lang,
                extra={"disorder_code": code, "disorder_name": name},
            )
            output = self.specialist.run(spec_input)
            return output.parsed if output.parsed else None

        opinions = []
        workers = min(len(candidate_codes), max_workers)
        if workers <= 1:
            for code in candidate_codes:
                result = _run_one(code)
                if result:
                    opinions.append(result)
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {executor.submit(_run_one, c): c for c in candidate_codes}
                for future in as_completed(future_map):
                    try:
                        result = future.result()
                        if result:
                            opinions.append(result)
                    except Exception:
                        logger.warning(
                            "Specialist failed for %s", future_map[future], exc_info=True
                        )
        return opinions
