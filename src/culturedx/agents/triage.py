"""Triage agent: classifies cases into broad ICD-10 categories."""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.agents.base import AgentInput, AgentOutput, BaseAgent
from culturedx.llm.json_utils import extract_json_from_response
from culturedx.agents.triage_routing import (
    CATEGORY_DISORDERS,
    load_calibration_artifact,
    normalize_triage_categories,
    route_triage_categories,
)

logger = logging.getLogger(__name__)


class TriageAgent(BaseAgent):
    """Classifies cases into broad ICD-10 chapter F categories."""

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/agents",
        confidence_threshold: float = 0.7,
        max_categories: int = 3,
        activation_threshold: float = 0.2,
        calibration_artifact_path: str | Path | None = None,
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
        self.calibration_artifact_path = (
            Path(calibration_artifact_path)
            if calibration_artifact_path is not None
            else None
        )
        self._calibration_artifact, self._calibration_fallback_reason = load_calibration_artifact(
            self.calibration_artifact_path
        )
        if self._calibration_artifact is not None:
            logger.info(
                "Loaded triage calibration artifact from %s (temperature=%.3f)",
                self.calibration_artifact_path,
                self._calibration_artifact.temperature,
            )
        elif self.calibration_artifact_path is not None:
            logger.warning(
                "Triage calibration artifact unavailable at %s: %s",
                self.calibration_artifact_path,
                self._calibration_fallback_reason,
            )

    def run(self, input: AgentInput) -> AgentOutput:
        """Classify case into broad categories.

        Returns AgentOutput with parsed containing:
            - categories: list of routing objects with raw/calibrated scores
            - disorder_codes: list of selected specific ICD-10 codes to check
        """
        # Build evidence summary
        evidence_summary = None
        if input.evidence:
            evidence_summary = input.evidence.get("evidence_summary")

        # Render prompt (with optional CoT variant)
        prompt_variant = (input.extra or {}).get("prompt_variant", "")
        if prompt_variant == "cot" and input.language == "zh":
            template_name = "triage_cot_zh.jinja"
        else:
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
        """Parse triage response and expand categories to a routing payload."""
        category_inputs, fallback_reason = normalize_triage_categories(parsed)
        if not category_inputs:
            logger.warning("Triage parse failure: no valid categories extracted from LLM response")
            return {
                "categories": [],
                "disorder_codes": [],
                "selected_categories": [],
                "candidate_disorder_codes": [],
                "fallback_reason": fallback_reason or "no_valid_categories",
                "routing_mode": "parse_failure",
                "calibration_status": "n/a",
                "calibration_artifact_path": None,
                "calibration_method": "n/a",
                "calibration_temperature": None,
                "raw_categories": [],
                "parse_failure": True,
            }
        routing = route_triage_categories(
            category_inputs,
            calibration_artifact=self._calibration_artifact,
            calibration_artifact_path=self.calibration_artifact_path,
            confidence_threshold=self.confidence_threshold,
            activation_threshold=self.activation_threshold,
            max_categories=self.max_categories,
        )

        payload = routing.to_dict()
        payload["fallback_reason"] = fallback_reason or payload.get("fallback_reason")
        payload["categories"] = [
            {
                "category": category.category,
                "confidence": category.calibrated_score,
                "raw_score": category.raw_score,
                "calibrated_score": category.calibrated_score,
                "selected": category.selected,
                "disorder_codes": category.disorder_codes,
            }
            for category in routing.categories
        ]
        payload["raw_categories"] = [
            {
                "category": item.category,
                "raw_score": item.raw_score,
            }
            for item in category_inputs
        ]
        payload["routing_mode"] = (
            "calibrated"
            if self._calibration_artifact is not None
            else "heuristic_fallback"
        )
        payload["calibration_status"] = (
            "loaded" if self._calibration_artifact is not None else "fallback"
        )
        payload["calibration_artifact_path"] = (
            str(self.calibration_artifact_path) if self.calibration_artifact_path else None
        )
        payload["calibration_method"] = (
            self._calibration_artifact.method
            if self._calibration_artifact is not None
            else "identity"
        )
        payload["calibration_temperature"] = (
            self._calibration_artifact.temperature
            if self._calibration_artifact is not None
            else 1.0
        )
        payload["selected_categories"] = routing.selected_categories
        payload["candidate_disorder_codes"] = routing.candidate_disorder_codes
        return payload
