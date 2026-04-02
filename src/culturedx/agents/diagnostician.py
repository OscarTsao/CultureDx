"""Diagnostician agent: holistic ranking over candidate disorders."""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.agents.base import AgentInput, AgentOutput, BaseAgent
from culturedx.llm.json_utils import extract_json_from_response

logger = logging.getLogger(__name__)


class DiagnosticianAgent(BaseAgent):
    """Rank candidate diagnoses using holistic clinical judgment."""

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
        """Rank candidate disorders for the case transcript."""
        extra = input.extra or {}
        candidate_disorders = list(extra.get("candidate_disorders", []))
        disorder_names = dict(extra.get("disorder_names", {}))

        template_name = f"diagnostician_{input.language}.jinja"
        template = self._env.get_template(template_name)
        prompt = template.render(
            transcript_text=input.transcript_text,
            candidate_disorders=candidate_disorders,
            disorder_names=disorder_names,
        )

        source, _, _ = self._env.loader.get_source(self._env, template_name)
        prompt_hash = self.llm.compute_prompt_hash(source)

        raw = self.llm.generate(prompt, prompt_hash=prompt_hash, language=input.language)
        parsed = extract_json_from_response(raw)
        result = self._parse_ranking(parsed, candidate_disorders)

        return AgentOutput(
            raw_response=raw,
            parsed=result,
            model_name=self.llm.model,
            prompt_hash=prompt_hash,
        )

    def _parse_ranking(
        self,
        parsed: dict | list | None,
        candidate_disorders: list[str],
    ) -> dict:
        """Parse ranked diagnoses from the LLM response."""
        if not parsed or not isinstance(parsed, dict):
            return {
                "ranked_codes": [],
                "reasoning": [],
            }

        ranked = parsed.get("ranked_diagnoses", [])
        if not isinstance(ranked, list):
            logger.warning("Diagnostician parse failure: ranked_diagnoses is not a list")
            return {
                "ranked_codes": [],
                "reasoning": [],
            }

        allowed_codes = set(candidate_disorders)
        ranked_codes: list[str] = []
        reasoning: list[str] = []
        seen_codes: set[str] = set()

        for item in ranked:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code", "")).strip()
            if not code:
                continue
            if code not in allowed_codes:
                logger.warning(
                    "Diagnostician returned code %s outside candidate disorders %s",
                    code,
                    candidate_disorders,
                )
                return {
                    "ranked_codes": [],
                    "reasoning": [],
                }
            if code in seen_codes:
                continue
            seen_codes.add(code)
            ranked_codes.append(code)
            reasoning.append(str(item.get("reasoning", "")).strip())

        return {
            "ranked_codes": ranked_codes,
            "reasoning": reasoning,
        }
