"""Specialist agent: free-form disorder-specific diagnostic reasoning."""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.agents.base import AgentInput, AgentOutput, BaseAgent
from culturedx.llm.json_utils import extract_json_from_response

logger = logging.getLogger(__name__)


class SpecialistAgent(BaseAgent):
    """Free-form disorder specialist providing diagnostic reasoning.
    
    Unlike CriterionCheckerAgent which evaluates structured criteria,
    this agent provides free-form expert reasoning about a specific disorder.
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
        disorder_code = input.extra.get("disorder_code", "unknown")
        disorder_name = input.extra.get("disorder_name", disorder_code)

        evidence_summary = None
        if input.evidence:
            evidence_summary = input.evidence.get("evidence_summary")

        template_name = f"specialist_{input.language}.jinja"
        template = self._env.get_template(template_name)
        prompt = template.render(
            disorder_code=disorder_code,
            disorder_name=disorder_name,
            transcript_text=input.transcript_text,
            evidence_summary=evidence_summary,
        )

        source, _, _ = self._env.loader.get_source(self._env, template_name)
        prompt_hash = self.llm.compute_prompt_hash(source)

        raw = self.llm.generate(prompt, prompt_hash=prompt_hash, language=input.language)
        parsed = extract_json_from_response(raw)

        result = self._parse_specialist(parsed, disorder_code)

        return AgentOutput(
            raw_response=raw,
            parsed=result,
            model_name=self.llm.model,
            prompt_hash=prompt_hash,
        )

    @staticmethod
    def _parse_specialist(parsed: dict | list | None, disorder_code: str) -> dict:
        if not parsed or not isinstance(parsed, dict):
            return {
                "disorder_code": disorder_code,
                "diagnosis_likely": False,
                "confidence": 0.0,
                "reasoning": "",
                "key_symptoms": [],
            }

        return {
            "disorder_code": parsed.get("disorder_code", disorder_code),
            "diagnosis_likely": bool(parsed.get("diagnosis_likely", False)),
            "confidence": max(0.0, min(1.0, float(parsed.get("confidence", 0.0)))),
            "reasoning": str(parsed.get("reasoning", "")),
            "key_symptoms": list(parsed.get("key_symptoms", [])),
        }
