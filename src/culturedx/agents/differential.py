"""Differential diagnosis agent: cross-disorder synthesis."""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.agents.base import AgentInput, AgentOutput, BaseAgent
from culturedx.core.models import CheckerOutput
from culturedx.llm.json_utils import extract_json_from_response

logger = logging.getLogger(__name__)


class DifferentialDiagnosisAgent(BaseAgent):
    """Cross-disorder differential diagnosis from checker outputs."""

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
        """Perform differential diagnosis from checker outputs.

        Expects input.extra to contain:
            - checker_outputs: list[CheckerOutput]
            - case_id: str
            - disorder_names: dict mapping disorder_code -> name (optional)
        """
        checker_outputs: list[CheckerOutput] = input.extra.get("checker_outputs", [])
        case_id: str = input.extra.get("case_id", "")
        disorder_names: dict = input.extra.get("disorder_names", {})

        if not checker_outputs:
            logger.warning("No checker outputs provided for differential diagnosis")
            return AgentOutput(raw_response="", parsed=None)

        # Build checker_results for template
        checker_results = []
        for co in checker_outputs:
            criteria_dicts = []
            for cr in co.criteria:
                criteria_dicts.append({
                    "criterion_id": cr.criterion_id,
                    "status": cr.status,
                    "evidence": cr.evidence,
                    "confidence": cr.confidence,
                })
            checker_results.append({
                "disorder": co.disorder,
                "disorder_name": disorder_names.get(co.disorder, co.disorder),
                "criteria": criteria_dicts,
                "criteria_met_count": co.criteria_met_count,
                "criteria_required": co.criteria_required,
            })

        # Use substantial transcript for differential reasoning (chief complaint
        # and functional impairment context are spread throughout the interview)
        transcript_summary = input.transcript_text[:15000] if input.transcript_text else ""

        # Render prompt
        template_name = f"differential_{input.language}.jinja"
        template = self._env.get_template(template_name)
        prompt = template.render(
            checker_results=checker_results,
            transcript_summary=transcript_summary,
            language=input.language,
        )

        source, _, _ = self._env.loader.get_source(self._env, template_name)
        prompt_hash = self.llm.compute_prompt_hash(source)

        # Call LLM
        raw = self.llm.generate(prompt, prompt_hash=prompt_hash, language=input.language)

        # Parse response
        parsed = extract_json_from_response(raw)
        result = self._parse_result(parsed, case_id, checker_outputs, input.language)

        return AgentOutput(
            raw_response=raw,
            parsed=result,
            model_name=self.llm.model,
            prompt_hash=prompt_hash,
        )

    def _parse_result(
        self,
        parsed: dict | list | None,
        case_id: str,
        checker_outputs: list[CheckerOutput],
        language: str,
    ) -> dict:
        """Parse LLM JSON response into DiagnosisResult-compatible dict."""
        if parsed and isinstance(parsed, dict):
            primary = parsed.get("primary_diagnosis")
            comorbid = parsed.get("comorbid_diagnoses", [])
            if not isinstance(comorbid, list):
                comorbid = []
            confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.0))))
            decision = "diagnosis" if primary else "abstain"
        else:
            primary = None
            comorbid = []
            confidence = 0.0
            decision = "abstain"

        return {
            "case_id": case_id,
            "primary_diagnosis": primary,
            "comorbid_diagnoses": comorbid,
            "confidence": confidence,
            "decision": decision,
            "criteria_results": checker_outputs,
            "mode": "mas",
            "language_used": language,
        }
