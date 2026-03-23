"""Triage agent: classifies cases into broad ICD-10 categories."""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.agents.base import AgentInput, AgentOutput, BaseAgent
from culturedx.llm.json_utils import extract_json_from_response

logger = logging.getLogger(__name__)

# Category -> disorder code mapping
CATEGORY_DISORDERS: dict[str, list[str]] = {
    "mood": ["F31", "F32", "F33"],
    "anxiety": ["F40", "F41.0", "F41.1", "F42"],
    "stress": ["F43.1", "F43.2"],
    "somatoform": ["F45"],
    "psychotic": ["F20", "F22"],
    "sleep": ["F51"],
}

VALID_CATEGORIES = set(CATEGORY_DISORDERS.keys())


class TriageAgent(BaseAgent):
    """Classifies cases into broad ICD-10 chapter F categories."""

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/agents",
        confidence_threshold: float = 0.7,
        max_categories: int = 3,
        activation_threshold: float = 0.2,
    ) -> None:
        self.llm = llm_client
        self.prompts_dir = Path(prompts_dir)
        self._env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            keep_trailing_newline=True,
        )
        self.confidence_threshold = confidence_threshold
        self.max_categories = max_categories
        self.activation_threshold = activation_threshold

    def run(self, input: AgentInput) -> AgentOutput:
        """Classify case into broad categories.

        Returns AgentOutput with parsed containing:
            - categories: list of {category, confidence}
            - disorder_codes: list of specific ICD-10 codes to check
        """
        # Build evidence summary
        evidence_summary = None
        if input.evidence:
            evidence_summary = input.evidence.get("evidence_summary")

        # Render prompt
        template_name = f"triage_{input.language}.jinja"
        template = self._env.get_template(template_name)
        # Pass demographic/chief complaint info if available in extra
        extra = input.extra or {}
        prompt = template.render(
            transcript_text=input.transcript_text,
            evidence_summary=evidence_summary,
            chief_complaint=extra.get("chief_complaint"),
            age=extra.get("age"),
            gender=extra.get("gender"),
        )

        source, _, _ = self._env.loader.get_source(self._env, template_name)
        prompt_hash = self.llm.compute_prompt_hash(source)

        # Call LLM
        raw = self.llm.generate(prompt, prompt_hash=prompt_hash, language=input.language)

        # Parse response
        parsed = extract_json_from_response(raw)
        result = self._parse_triage(parsed)

        return AgentOutput(
            raw_response=raw,
            parsed=result,
            model_name=self.llm.model,
            prompt_hash=prompt_hash,
        )

    def _parse_triage(self, parsed: dict | list | None) -> dict:
        """Parse triage response and expand categories to disorder codes."""
        categories = []
        if parsed and isinstance(parsed, dict) and "categories" in parsed:
            for item in parsed["categories"]:
                cat = item.get("category", "")
                conf = max(0.0, min(1.0, float(item.get("confidence", 0.0))))
                if cat in VALID_CATEGORIES:
                    categories.append({"category": cat, "confidence": conf})

        if not categories:
            # Fallback: activate all categories
            logger.warning("Triage produced no valid categories, activating all")
            categories = [{"category": c, "confidence": 0.5} for c in VALID_CATEGORIES]

        # Sort by confidence descending
        categories.sort(key=lambda x: x["confidence"], reverse=True)

        # Apply activation logic (spec §3 Stage 1):
        # Activate all with confidence >= activation_threshold OR top-max_categories
        top_conf = categories[0]["confidence"]
        if top_conf >= self.confidence_threshold:
            # High confidence in top-1: activate those >= activation_threshold
            active = [c for c in categories if c["confidence"] >= self.activation_threshold]
        else:
            # Low confidence: take top-max_categories
            active = categories[: self.max_categories]

        # Expand to disorder codes
        disorder_codes = []
        for cat in active:
            codes = CATEGORY_DISORDERS.get(cat["category"], [])
            for code in codes:
                if code not in disorder_codes:
                    disorder_codes.append(code)

        return {
            "categories": active,
            "disorder_codes": disorder_codes,
        }
