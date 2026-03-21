"""Contrastive checker agent: disambiguates shared criteria between disorders."""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.agents.base import AgentInput, AgentOutput, BaseAgent
from culturedx.llm.json_utils import extract_json_from_response

logger = logging.getLogger(__name__)

CONTRASTIVE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "attributions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "symptom_domain": {"type": "string"},
                    "primary_attribution": {"type": "string"},
                    "attribution_confidence": {"type": "number"},
                    "reasoning": {"type": "string"},
                },
                "required": [
                    "symptom_domain",
                    "primary_attribution",
                    "attribution_confidence",
                ],
            },
        }
    },
    "required": ["attributions"],
}


class ContrastiveCheckerAgent(BaseAgent):
    """Disambiguates shared criteria between two disorders."""

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
        """Evaluate shared criteria attribution between two disorders.

        Expects input.extra to contain:
            - shared_pairs: list[SharedCriterionPair]
            - checker_evidence: dict with "{disorder}_{criterion_id}" keys
            - disorder_names: dict mapping disorder_code -> name
        """
        shared_pairs = input.extra.get("shared_pairs", [])
        checker_evidence = input.extra.get("checker_evidence", {})
        disorder_names = input.extra.get("disorder_names", {})

        if not shared_pairs:
            return AgentOutput(raw_response="", parsed=None)

        # Render prompt
        template_name = f"contrastive_checker_{input.language}.jinja"
        template = self._env.get_template(template_name)
        prompt = template.render(
            transcript_text=input.transcript_text,
            shared_pairs=shared_pairs,
            checker_evidence=checker_evidence,
            disorder_names=disorder_names,
        )

        source, _, _ = self._env.loader.get_source(self._env, template_name)
        prompt_hash = self.llm.compute_prompt_hash(source)

        # Use guided JSON if available
        gen_kwargs: dict = {}
        if hasattr(self.llm, "generate"):
            import inspect
            sig = inspect.signature(self.llm.generate)
            if "json_schema" in sig.parameters:
                gen_kwargs["json_schema"] = CONTRASTIVE_JSON_SCHEMA

        raw = self.llm.generate(
            prompt, prompt_hash=prompt_hash, language=input.language, **gen_kwargs
        )

        # Parse response
        parsed = extract_json_from_response(raw)
        result = self._validate(parsed)

        return AgentOutput(
            raw_response=raw,
            parsed=result,
            model_name=self.llm.model,
            prompt_hash=prompt_hash,
        )

    @staticmethod
    def _validate(parsed: dict | list | None) -> dict | None:
        """Validate parsed JSON has the expected attributions structure."""
        if not parsed or not isinstance(parsed, dict):
            return None
        attributions = parsed.get("attributions")
        if not attributions or not isinstance(attributions, list):
            return None
        valid = []
        for attr in attributions:
            if not isinstance(attr, dict):
                continue
            if "symptom_domain" not in attr or "primary_attribution" not in attr:
                continue
            conf = attr.get("attribution_confidence", 0.5)
            valid.append({
                "symptom_domain": attr["symptom_domain"],
                "primary_attribution": attr["primary_attribution"],
                "attribution_confidence": max(0.0, min(1.0, float(conf))),
                "reasoning": attr.get("reasoning", ""),
            })
        if not valid:
            return None
        return {"attributions": valid}
