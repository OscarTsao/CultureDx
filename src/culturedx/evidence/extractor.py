"""LLM-based symptom span extraction from clinical transcripts."""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.core.models import ClinicalCase, SymptomSpan
from culturedx.llm.json_utils import extract_json_from_response

logger = logging.getLogger(__name__)

EXTRACTOR_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "symptoms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "turn_id": {"type": "integer"},
                    "symptom_type": {
                        "type": "string",
                        "enum": ["somatic", "emotional", "behavioral", "cognitive"],
                    },
                },
                "required": ["text", "turn_id", "symptom_type"],
            },
        }
    },
    "required": ["symptoms"],
}


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

    @staticmethod
    def _truncate_turns(turns: list, max_chars: int = 14000) -> list:
        """Truncate turns to fit within context window, preserving turn boundaries.

        Uses head/tail strategy (60/40 split) to keep chief complaint and summary.
        """
        total = sum(len(t.text) for t in turns)
        if total <= max_chars:
            return turns

        head_budget = int(max_chars * 0.6)
        tail_budget = max_chars - head_budget

        head_turns = []
        head_len = 0
        for t in turns:
            if head_len + len(t.text) > head_budget:
                break
            head_turns.append(t)
            head_len += len(t.text)

        tail_turns = []
        tail_len = 0
        for t in reversed(turns):
            if tail_len + len(t.text) > tail_budget:
                break
            tail_turns.insert(0, t)
            tail_len += len(t.text)

        # Deduplicate if head and tail overlap
        head_ids = {id(t) for t in head_turns}
        tail_turns = [t for t in tail_turns if id(t) not in head_ids]

        return head_turns + tail_turns

    def extract(self, case: ClinicalCase) -> list[SymptomSpan]:
        """Extract symptom mentions from the transcript."""
        if case.language not in ("zh", "en"):
            logger.warning(
                "Unsupported language '%s' for extraction, skipping case %s",
                case.language, case.case_id,
            )
            return []
        template_name = f"extract_symptoms_{case.language}.jinja"
        template = self._env.get_template(template_name)

        truncated_turns = self._truncate_turns(case.transcript)
        prompt = template.render(turns=truncated_turns)
        source, _, _ = self._env.loader.get_source(self._env, template_name)
        prompt_hash = self.llm.compute_prompt_hash(source)

        gen_kwargs: dict = {}
        if hasattr(self.llm, 'generate'):
            import inspect
            sig = inspect.signature(self.llm.generate)
            if 'json_schema' in sig.parameters:
                gen_kwargs['json_schema'] = EXTRACTOR_JSON_SCHEMA
        raw = self.llm.generate(
            prompt, prompt_hash=prompt_hash, language=case.language, **gen_kwargs
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
