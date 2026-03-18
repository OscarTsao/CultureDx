"""Consensus judge agent for Debate-MAS mode.

Synthesizes perspective-agent opinions into a final diagnosis.
"""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.agents.base import AgentInput, AgentOutput, BaseAgent
from culturedx.llm.json_utils import extract_json_from_response

logger = logging.getLogger(__name__)


class JudgeAgent(BaseAgent):
    """Synthesizes perspective opinions into a consensus diagnosis.

    Expects input.extra to contain:
        - specialist_opinions: list of dicts with disorder_code, confidence, reasoning
        - case_id: str
    """

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/agents",
    ) -> None:
        self.llm = llm_client
        self.prompts_dir = Path(prompts_dir)
        self._env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            keep_trailing_newline=True,
        )

    def run(self, input: AgentInput) -> AgentOutput:
        specialist_opinions = input.extra.get("specialist_opinions", [])
        case_id = input.extra.get("case_id", "")

        if not specialist_opinions:
            logger.warning("No specialist opinions provided for judge")
            return AgentOutput(raw_response="", parsed=None)

        template_name = f"judge_{input.language}.jinja"
        template = self._env.get_template(template_name)
        prompt = template.render(
            transcript_text=input.transcript_text,
            specialist_opinions=specialist_opinions,
            case_id=case_id,
        )

        source, _, _ = self._env.loader.get_source(self._env, template_name)
        prompt_hash = self.llm.compute_prompt_hash(source)

        raw = self.llm.generate(prompt, prompt_hash=prompt_hash, language=input.language)
        parsed = extract_json_from_response(raw)
        result = self._parse_result(parsed, case_id, input.language)

        return AgentOutput(
            raw_response=raw,
            parsed=result,
            model_name=self.llm.model,
            prompt_hash=prompt_hash,
        )

    def _parse_result(
        self,
        parsed: dict | list | None,
        case_id: str,
        language: str,
    ) -> dict:
        if parsed and isinstance(parsed, dict):
            primary = parsed.get("primary_diagnosis")
            comorbid = parsed.get("comorbid_diagnoses", [])
            if not isinstance(comorbid, list):
                comorbid = []
            confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.0))))
            decision = parsed.get("decision", "diagnosis" if primary else "abstain")
        else:
            primary = None
            comorbid = []
            confidence = 0.0
            decision = "abstain"

        return {
            "case_id": case_id,
            "primary_diagnosis": primary,
            "comorbid_diagnoses": comorbid,
            "confidence": confidence,
            "decision": decision,
            "language_used": language,
        }
