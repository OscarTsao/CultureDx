# src/culturedx/modes/single.py
"""Single-model baseline mode."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.core.models import ClinicalCase, DiagnosisResult, EvidenceBrief
from culturedx.llm.json_utils import extract_json_from_response
from culturedx.modes.base import BaseModeOrchestrator


class SingleModelMode(BaseModeOrchestrator):
    """Zero-shot or few-shot single LLM call for diagnosis."""

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/single",
    ) -> None:
        self.llm = llm_client
        self.prompts_dir = Path(prompts_dir)
        self._env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            keep_trailing_newline=True,
        )

    def diagnose(
        self, case: ClinicalCase, evidence: EvidenceBrief | None = None
    ) -> DiagnosisResult:
        lang = case.language
        if lang not in ("zh", "en"):
            return DiagnosisResult(
                case_id=case.case_id,
                primary_diagnosis=None,
                confidence=0.0,
                decision="abstain",
                mode="single",
                model_name=self.llm.model,
                prompt_hash="",
                language_used=lang,
            )
        if evidence and evidence.disorder_evidence:
            template_name = f"zero_shot_evidence_{lang}.jinja"
        else:
            template_name = f"zero_shot_{lang}.jinja"
        template = self._env.get_template(template_name)

        prompt = template.render(
            transcript=case.transcript,
            evidence=evidence,
        )
        source, _, _ = self._env.loader.get_source(self._env, template_name)
        prompt_hash = self.llm.compute_prompt_hash(source)

        raw = self.llm.generate(prompt, prompt_hash=prompt_hash, language=lang)
        parsed = extract_json_from_response(raw)

        if parsed is None or not isinstance(parsed, dict):
            return DiagnosisResult(
                case_id=case.case_id,
                primary_diagnosis=None,
                confidence=0.0,
                decision="abstain",
                mode="single",
                model_name=self.llm.model,
                prompt_hash=prompt_hash,
                language_used=case.language,
            )

        return DiagnosisResult(
            case_id=case.case_id,
            primary_diagnosis=parsed.get("primary_diagnosis"),
            comorbid_diagnoses=parsed.get("comorbid_diagnoses", []),
            confidence=parsed.get("confidence", 0.0),
            decision="diagnosis",
            mode="single",
            model_name=self.llm.model,
            prompt_hash=prompt_hash,
            language_used=case.language,
        )
