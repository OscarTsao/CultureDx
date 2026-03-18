"""LLM-based symptom span extraction from clinical transcripts."""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.core.models import ClinicalCase, SymptomSpan
from culturedx.llm.json_utils import extract_json_from_response

logger = logging.getLogger(__name__)


class SymptomExtractor:
    """Extract symptom spans from transcript turns using an LLM."""

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/evidence",
    ) -> None:
        self.llm = llm_client
        self._env = Environment(
            loader=FileSystemLoader(str(prompts_dir)),
            keep_trailing_newline=True,
        )

    def extract(self, case: ClinicalCase) -> list[SymptomSpan]:
        """Extract symptom mentions from the transcript."""
        template_name = f"extract_symptoms_{case.language}.jinja"
        template = self._env.get_template(template_name)

        prompt = template.render(turns=case.transcript)
        source, _, _ = self._env.loader.get_source(self._env, template_name)
        prompt_hash = self.llm.compute_prompt_hash(source)

        raw = self.llm.generate(
            prompt, prompt_hash=prompt_hash, language=case.language
        )
        parsed = extract_json_from_response(raw)

        if parsed is None or not isinstance(parsed, dict):
            logger.warning("Failed to parse symptoms for case %s", case.case_id)
            return []

        symptoms = parsed.get("symptoms", [])
        spans = []
        for s in symptoms:
            if not isinstance(s, dict):
                continue
            text = s.get("text", "")
            if not text:
                continue
            stype = s.get("symptom_type", "unknown")
            spans.append(
                SymptomSpan(
                    text=text,
                    turn_id=s.get("turn_id", -1),
                    symptom_type=stype,
                    is_somatic=(stype == "somatic"),
                )
            )
        return spans
