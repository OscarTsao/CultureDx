"""Chinese somatization mapper: ontology lookup + LLM fallback."""
from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.core.models import SymptomSpan
from culturedx.llm.json_utils import extract_json_from_response
from culturedx.ontology.symptom_map import get_criteria_for_symptom

logger = logging.getLogger(__name__)


class SomatizationMapper:
    """Map Chinese somatic symptoms to psychiatric criteria."""

    def __init__(
        self,
        llm_client=None,
        llm_fallback: bool = True,
        prompts_dir: str | Path = "prompts/evidence",
    ) -> None:
        self.llm = llm_client
        self.llm_fallback = llm_fallback and (llm_client is not None)
        if self.llm_fallback:
            self._env = Environment(
                loader=FileSystemLoader(str(prompts_dir)),
                keep_trailing_newline=True,
            )
        else:
            self._env = None

    def map_span(
        self, span: SymptomSpan, context: str = ""
    ) -> SymptomSpan:
        """Map a single somatic span to criteria. Returns new SymptomSpan."""
        if not span.is_somatic:
            return span

        # Step 1: Ontology lookup
        criteria = get_criteria_for_symptom(span.text)
        if criteria:
            return replace(
                span, mapped_criterion=",".join(criteria)
            )

        # Step 2: LLM fallback (if enabled)
        if self.llm_fallback and self._env is not None:
            criteria = self._llm_map(span.text, context)
            if criteria:
                return replace(
                    span, mapped_criterion=",".join(criteria)
                )

        return span

    def map_all(
        self, spans: list[SymptomSpan], context: str = ""
    ) -> list[SymptomSpan]:
        """Map all somatic spans in the list. Returns new list."""
        return [self.map_span(s, context) for s in spans]

    def _llm_map(self, symptom_text: str, context: str) -> list[str]:
        """Use LLM to map an unknown somatic symptom to criteria."""
        template = self._env.get_template("somatization_fallback_zh.jinja")
        prompt = template.render(
            symptom_text=symptom_text, context=context
        )
        source, _, _ = self._env.loader.get_source(
            self._env, "somatization_fallback_zh.jinja"
        )
        prompt_hash = self.llm.compute_prompt_hash(source)

        raw = self.llm.generate(
            prompt, prompt_hash=prompt_hash, language="zh"
        )
        parsed = extract_json_from_response(raw)

        if parsed is None or not isinstance(parsed, dict):
            logger.warning(
                "LLM fallback failed for symptom: %s", symptom_text
            )
            return []

        return parsed.get("mapped_criteria", [])
