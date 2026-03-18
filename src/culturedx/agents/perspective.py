"""Perspective agents for Debate-MAS mode.

Four perspectives: Biological, Psychological, Social, Cultural.
Each sees the same evidence and provides diagnostic reasoning from their lens.
"""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.agents.base import AgentInput, AgentOutput, BaseAgent
from culturedx.llm.json_utils import extract_json_from_response

logger = logging.getLogger(__name__)

PERSPECTIVES = ["biological", "psychological", "social", "cultural"]


class PerspectiveAgent(BaseAgent):
    """Diagnostic reasoning from a specific theoretical perspective.

    Perspectives:
    - Biological: neurotransmitter, genetic, physiological symptoms
    - Psychological: cognitive patterns, emotional processing, trauma
    - Social: interpersonal, occupational, family dynamics
    - Cultural: culture-bound syndromes, somatization, help-seeking
    """

    def __init__(
        self,
        llm_client,
        perspective: str,
        prompts_dir: str | Path = "prompts/agents",
    ) -> None:
        if perspective not in PERSPECTIVES:
            raise ValueError(f"Invalid perspective: {perspective}. Must be one of {PERSPECTIVES}")
        self.llm = llm_client
        self.perspective = perspective
        self.prompts_dir = Path(prompts_dir)
        self._env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            keep_trailing_newline=True,
        )

    def run(self, input: AgentInput) -> AgentOutput:
        evidence_summary = None
        if input.evidence:
            evidence_summary = input.evidence.get("evidence_summary")

        # Use debate context from prior rounds if available
        prior_round = input.extra.get("prior_round_opinions", [])

        template_name = f"perspective_{input.language}.jinja"
        template = self._env.get_template(template_name)
        prompt = template.render(
            perspective=self.perspective,
            transcript_text=input.transcript_text,
            evidence_summary=evidence_summary,
            prior_round_opinions=prior_round,
        )

        source, _, _ = self._env.loader.get_source(self._env, template_name)
        prompt_hash = self.llm.compute_prompt_hash(source)

        raw = self.llm.generate(prompt, prompt_hash=prompt_hash, language=input.language)
        parsed = extract_json_from_response(raw)

        result = self._parse_perspective(parsed)

        return AgentOutput(
            raw_response=raw,
            parsed=result,
            model_name=self.llm.model,
            prompt_hash=prompt_hash,
        )

    def _parse_perspective(self, parsed: dict | list | None) -> dict:
        if not parsed or not isinstance(parsed, dict):
            return {
                "perspective": self.perspective,
                "diagnoses": [],
                "confidence": 0.0,
                "reasoning": "",
            }

        diagnoses = []
        for d in parsed.get("diagnoses", []):
            if isinstance(d, dict):
                diagnoses.append({
                    "disorder_code": str(d.get("disorder_code", "")),
                    "confidence": max(0.0, min(1.0, float(d.get("confidence", 0.0)))),
                })
            elif isinstance(d, str):
                diagnoses.append({"disorder_code": d, "confidence": 0.5})

        return {
            "perspective": self.perspective,
            "diagnoses": diagnoses,
            "confidence": max(0.0, min(1.0, float(parsed.get("confidence", 0.0)))),
            "reasoning": str(parsed.get("reasoning", "")),
        }
