"""Debate-MAS mode: four perspective agents + consensus judge.

Alternative Mode C — four perspective agents (Biological, Psychological,
Social, Cultural) see same full evidence. Two debate rounds.
Consensus judge. Cultural agent is the Chinese-specific contribution.
"""
from __future__ import annotations

import logging
from pathlib import Path

from culturedx.agents.base import AgentInput
from culturedx.agents.judge import JudgeAgent
from culturedx.agents.perspective import PERSPECTIVES, PerspectiveAgent
from culturedx.core.models import (
    ClinicalCase,
    DiagnosisResult,
    EvidenceBrief,
)
from culturedx.modes.base import BaseModeOrchestrator

logger = logging.getLogger(__name__)


class DebateMode(BaseModeOrchestrator):
    """Debate-MAS: perspective-based deliberation + consensus judge.

    Pipeline:
    1. Round 1: Each perspective agent analyzes independently
    2. Round 2: Each agent sees Round 1 opinions, refines view
    3. Judge: Synthesizes all perspectives into final diagnosis
    """

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/agents",
        num_rounds: int = 2,
    ) -> None:
        self.mode_name = "debate"
        self.llm = llm_client
        self.prompts_dir = Path(prompts_dir)
        self.num_rounds = num_rounds

        # Create one agent per perspective
        self.perspective_agents = {
            p: PerspectiveAgent(llm_client, p, prompts_dir)
            for p in PERSPECTIVES
        }

        # Consensus judge (reuse JudgeAgent)
        self.judge = JudgeAgent(llm_client, prompts_dir)

    def diagnose(
        self, case: ClinicalCase, evidence: EvidenceBrief | None = None
    ) -> DiagnosisResult:
        lang = case.language
        if lang not in ("zh", "en"):
            return self._abstain(case, lang)

        transcript_text = self._build_transcript_text(case)
        evidence_summary = self._build_global_evidence_summary(evidence)

        # === Debate Rounds ===
        all_opinions = []
        prior_opinions: list[dict] = []

        for round_num in range(1, self.num_rounds + 1):
            round_opinions = []
            for perspective in PERSPECTIVES:
                agent = self.perspective_agents[perspective]
                agent_input = AgentInput(
                    transcript_text=transcript_text,
                    evidence={"evidence_summary": evidence_summary} if evidence_summary else None,
                    language=lang,
                    extra={"prior_round_opinions": prior_opinions if round_num > 1 else []},
                )
                output = agent.run(agent_input)
                if output.parsed:
                    output.parsed["round"] = round_num
                    round_opinions.append(output.parsed)

            all_opinions.extend(round_opinions)
            prior_opinions = round_opinions

        if not all_opinions:
            return self._abstain(case, lang)

        # === Consensus Judge ===
        # Convert perspective opinions to specialist-like format for judge
        specialist_opinions = self._convert_to_specialist_format(all_opinions)

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
                mode="debate",
                model_name=self.llm.model,
                language_used=lang,
            )

        return self._abstain(case, lang)

    @staticmethod
    def _convert_to_specialist_format(opinions: list[dict]) -> list[dict]:
        """Convert perspective opinions to specialist format for the judge."""
        converted = []
        for op in opinions:
            # Take the top diagnosis from each perspective
            diagnoses = op.get("diagnoses", [])
            top_code = diagnoses[0]["disorder_code"] if diagnoses else "unknown"
            converted.append({
                "disorder_code": f"{op.get('perspective', 'unknown')}_{top_code}",
                "diagnosis_likely": bool(diagnoses),
                "confidence": op.get("confidence", 0.0),
                "reasoning": op.get("reasoning", ""),
                "key_symptoms": [],
            })
        return converted
