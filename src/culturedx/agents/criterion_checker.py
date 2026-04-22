"""Criterion checker agent: evaluates criteria for a single disorder."""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.agents.base import AgentInput, AgentOutput, BaseAgent
from culturedx.core.models import CriterionResult
from culturedx.llm.json_utils import extract_json_from_response
from culturedx.ontology.standards import (
    DiagnosticStandard,
    get_disorder_criteria,
    get_disorder_name,
    get_disorder_threshold,
    normalize_standard,
)

logger = logging.getLogger(__name__)


def _compute_required(disorder_code: str, criteria: dict, threshold: dict) -> int:
    """Compute the number of criteria required for a disorder to meet threshold.

    This is a best-effort estimate based on the threshold structure.
    Different disorders use different threshold schemas.
    """
    if "all_required" in threshold and threshold["all_required"]:
        return len(criteria)
    if "min_total" in threshold:
        return threshold["min_total"]
    if "min_symptoms" in threshold:
        return threshold["min_symptoms"]
    if "min_first_rank" in threshold and "min_other" in threshold:
        return threshold["min_first_rank"] + threshold["min_other"]
    if "core_required" in threshold and "min_additional" in threshold:
        core_count = sum(1 for c in criteria.values() if c.get("type") == "core")
        return core_count + threshold["min_additional"]
    if "attacks_per_month" in threshold and "min_symptoms_per_attack" in threshold:
        return threshold["min_symptoms_per_attack"]
    # Fallback: require all criteria
    return len(criteria)


# JSON schema for guided decoding (vLLM structured output)
CHECKER_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["met", "not_met", "insufficient_evidence"],
                    },
                    "evidence": {
                        "anyOf": [{"type": "string"}, {"type": "null"}]
                    },
                    "confidence": {"type": "number"},
                },
                "required": ["criterion_id", "status", "confidence"],
            },
        }
    },
    "required": ["criteria"],
}


class CriterionCheckerAgent(BaseAgent):
    """Per-disorder criterion evaluation agent.

    Evaluates whether a clinical transcript meets the active diagnostic criteria
    for a specific disorder, producing structured CheckerOutput with criterion-level
    met/unmet decisions and confidence scores.
    """

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/agents",
        standard: DiagnosticStandard | str = DiagnosticStandard.ICD10,
    ) -> None:
        self.llm = llm_client
        self.prompts_dir = Path(prompts_dir)
        self.standard = normalize_standard(standard)
        self._env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            keep_trailing_newline=True,
        )

    def _resolve_standard(self, input: AgentInput) -> DiagnosticStandard:
        extra = input.extra or {}
        return normalize_standard(extra.get("standard", self.standard))

    def _select_template_name(
        self,
        template_name: str,
        standard: DiagnosticStandard,
        language: str,
    ) -> str:
        if standard != DiagnosticStandard.DSM5 or language != "zh":
            return template_name
        suffix = "_zh.jinja"
        if not template_name.endswith(suffix):
            return template_name
        candidate = f"{template_name[:-len(suffix)]}_dsm5{suffix}"
        if (self.prompts_dir / candidate).exists():
            return candidate
        return template_name

    @staticmethod
    def _clip_text_middle(text: str, max_chars: int) -> str:
        """Head/tail trim already-formatted transcript text to a char budget."""
        if len(text) <= max_chars:
            return text
        head_budget = int(max_chars * 0.6)
        tail_budget = max_chars - head_budget
        marker = "\n[...对话中间部分省略 / middle turns omitted...]\n"
        return text[:head_budget] + marker + text[-tail_budget:]

    def _max_prompt_chars(self) -> int:
        context_window = int(getattr(self.llm, "context_window", None) or 16384)
        max_tokens = int(getattr(self.llm, "max_tokens", 2048) or 2048)
        input_budget_tokens = max(768, context_window - max_tokens - 512)
        return int(input_budget_tokens * 1.8)

    def run(self, input: AgentInput) -> AgentOutput:
        """Evaluate criteria for a disorder specified in input.extra['disorder_code']."""
        disorder_code = input.extra.get("disorder_code")
        if not disorder_code:
            logger.error("No disorder_code in input.extra")
            return AgentOutput(raw_response="", parsed=None)

        standard = self._resolve_standard(input)
        disorder = get_disorder_criteria(disorder_code, standard)
        criteria = disorder.get("criteria") if disorder else None
        if criteria is None:
            logger.warning("Unknown disorder code: %s", disorder_code)
            return AgentOutput(raw_response="", parsed=None)

        disorder_name = get_disorder_name(
            disorder_code,
            standard,
            lang=input.language,
        ) or disorder_code

        # Build evidence summary from input.evidence if provided
        evidence_summary = None
        if input.evidence:
            evidence_summary = input.evidence.get("evidence_summary")

        # Build temporal summary for F41.1 if available
        temporal_summary = None
        if input.evidence and disorder_code == "F41.1":
            temporal_summary = input.evidence.get("temporal_summary")

        # Render prompt: select template variant
        prompt_variant = (input.extra or {}).get("prompt_variant", "")
        if temporal_summary and disorder_code == "F41.1" and input.language == "zh":
            template_name = "criterion_checker_temporal_zh.jinja"
        elif prompt_variant == "v2_improved" and input.language == "zh":
            template_name = "criterion_checker_v2_improved_zh.jinja"
        elif prompt_variant == "v2" and input.language == "zh":
            template_name = "criterion_checker_v2_zh.jinja"
        elif prompt_variant == "cot" and input.language == "zh":
            template_name = "criterion_checker_cot_zh.jinja"
        else:
            template_name = f"criterion_checker_{input.language}.jinja"
        template_name = self._select_template_name(template_name, standard, input.language)

        # Graceful fallback: if the selected template isn't available,
        # fall back to the best available variant instead of raising
        # TemplateNotFound and losing all criteria for this disorder.
        try:
            template = self._env.get_template(template_name)
        except Exception as e:
            logger.warning(
                "Template %s not found for %s (%s): falling back to v2_zh",
                template_name, disorder_code, e,
            )
            template_name = (
                "criterion_checker_v2_zh.jinja"
                if input.language == "zh"
                else f"criterion_checker_{input.language}.jinja"
            )
            template_name = self._select_template_name(template_name, standard, input.language)
            template = self._env.get_template(template_name)
        transcript_text = input.transcript_text
        prompt = template.render(
            disorder_code=disorder_code,
            disorder_name=disorder_name,
            criteria=criteria,
            transcript_text=transcript_text,
            evidence_summary=evidence_summary,
            temporal_summary=temporal_summary,
        )
        max_prompt_chars = self._max_prompt_chars()
        if len(prompt) > max_prompt_chars:
            overflow = len(prompt) - max_prompt_chars
            clipped_chars = max(1400, len(transcript_text) - overflow - 256)
            transcript_text = self._clip_text_middle(transcript_text, clipped_chars)
            prompt = template.render(
                disorder_code=disorder_code,
                disorder_name=disorder_name,
                criteria=criteria,
                transcript_text=transcript_text,
                evidence_summary=evidence_summary,
                temporal_summary=temporal_summary,
            )

        source, _, _ = self._env.loader.get_source(self._env, template_name)
        prompt_hash = self.llm.compute_prompt_hash(source)

        # Use guided JSON if the LLM client supports it (vLLM)
        gen_kwargs: dict = {}
        if hasattr(self.llm, 'generate'):
            import inspect
            sig = inspect.signature(self.llm.generate)
            if 'json_schema' in sig.parameters:
                gen_kwargs['json_schema'] = CHECKER_JSON_SCHEMA
        raw = self.llm.generate(
            prompt, prompt_hash=prompt_hash, language=input.language, **gen_kwargs
        )

        # Parse response
        parsed = extract_json_from_response(raw)
        checker_output = self._parse_checker_output(
            disorder_code,
            criteria,
            parsed,
            standard=standard,
        )

        return AgentOutput(
            raw_response=raw,
            parsed=checker_output,
            model_name=self.llm.model,
            prompt_hash=prompt_hash,
        )

    def _parse_checker_output(
        self,
        disorder_code: str,
        criteria: dict,
        parsed: dict | list | None,
        standard: DiagnosticStandard | str = DiagnosticStandard.ICD10,
    ) -> dict:
        """Parse LLM JSON response into CheckerOutput-compatible dict."""
        results = []
        if parsed and isinstance(parsed, dict) and "criteria" in parsed:
            for item in parsed["criteria"]:
                status = item.get("status", "insufficient_evidence")
                if status not in ("met", "not_met", "insufficient_evidence"):
                    status = "insufficient_evidence"
                results.append(
                    CriterionResult(
                        criterion_id=item.get("criterion_id", ""),
                        status=status,
                        evidence=item.get("evidence") or "",
                        confidence=max(0.0, min(1.0, float(item.get("confidence", 0.0)))),
                    )
                )

        # If no results were parsed, create insufficient_evidence for all criteria
        if not results:
            for crit_id in criteria:
                results.append(
                    CriterionResult(
                        criterion_id=crit_id,
                        status="insufficient_evidence",
                        evidence="",
                        confidence=0.0,
                    )
                )

        met_count = sum(1 for r in results if r.status == "met")

        # Get threshold info for criteria_required
        threshold = get_disorder_threshold(disorder_code, standard)
        required = _compute_required(disorder_code, criteria, threshold)

        return {
            "disorder": disorder_code,
            "criteria": results,
            "criteria_met_count": met_count,
            "criteria_required": required,
        }
