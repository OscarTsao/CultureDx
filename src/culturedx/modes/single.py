# src/culturedx/modes/single.py
"""Single-model baseline mode."""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.core.models import (
    ClinicalCase,
    CriterionEvidence,
    DiagnosisResult,
    DisorderEvidence,
    EvidenceBrief,
)
from culturedx.llm.json_utils import extract_json_from_response
from culturedx.modes.base import BaseModeOrchestrator

logger = logging.getLogger(__name__)


class SingleModelMode(BaseModeOrchestrator):
    """Zero-shot or few-shot single LLM call for diagnosis."""

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/single",
    ) -> None:
        self.mode_name = "single"
        self.llm = llm_client
        self.prompts_dir = Path(prompts_dir)
        self._env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            keep_trailing_newline=True,
        )

    def _truncate_evidence(
        self, evidence: EvidenceBrief, max_chars: int, case_id: str
    ) -> EvidenceBrief:
        """Truncate evidence to fit within character budget."""
        # Estimate original size
        original_chars = sum(
            len(span.text) + 50  # overhead per span (turn id, formatting)
            for de in evidence.disorder_evidence
            for ce in de.criteria_evidence
            for span in ce.spans
        )
        if original_chars <= max_chars:
            return evidence

        # Build truncated copy
        budget = max_chars
        new_disorders = []
        for de in evidence.disorder_evidence:
            new_criteria = []
            for ce in de.criteria_evidence:
                new_spans = []
                for span in ce.spans:
                    cost = len(span.text) + 50
                    if budget < cost:
                        break
                    new_spans.append(span)
                    budget -= cost
                if new_spans:
                    new_criteria.append(
                        CriterionEvidence(
                            criterion_id=ce.criterion_id,
                            spans=new_spans,
                            confidence=ce.confidence,
                        )
                    )
                if budget <= 0:
                    break
            if new_criteria:
                new_disorders.append(
                    DisorderEvidence(
                        disorder_code=de.disorder_code,
                        disorder_name=de.disorder_name,
                        criteria_evidence=new_criteria,
                    )
                )
            if budget <= 0:
                break

        logger.warning(
            "Single mode: evidence truncated from ~%d to ~%d chars for case %s",
            original_chars,
            max_chars - budget,
            case_id,
        )
        return EvidenceBrief(
            case_id=evidence.case_id,
            language=evidence.language,
            disorder_evidence=new_disorders,
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
                mode=self.mode_name,
                model_name=self.llm.model,
                prompt_hash="",
                language_used=lang,
            )
        if evidence and evidence.disorder_evidence:
            template_name = f"zero_shot_evidence_{lang}.jinja"
        else:
            template_name = f"zero_shot_{lang}.jinja"
        template = self._env.get_template(template_name)
        # When evidence is provided, transcript is supplementary — reduce budget
        max_chars = 8000 if evidence else 20000
        transcript_text = self._build_transcript_text(case, max_chars=max_chars)

        # Estimate non-evidence tokens and guard against context overflow
        # Context: 16384 total - 2048 max_tokens = 14336 max input tokens
        # Use 2.0 chars/token (worst-case for Qwen + mixed Chinese/punctuation)
        # Budget 12000 tokens to leave 2336 tokens safety margin
        base_prompt = template.render(transcript_text=transcript_text, evidence=None)
        base_chars = len(base_prompt)
        max_evidence_chars = int(12000 * 2.0) - base_chars

        if evidence and max_evidence_chars > 0:
            evidence = self._truncate_evidence(evidence, max_evidence_chars, case.case_id)

        prompt = template.render(transcript_text=transcript_text, evidence=evidence)
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
                mode=self.mode_name,
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
            mode=self.mode_name,
            model_name=self.llm.model,
            prompt_hash=prompt_hash,
            language_used=case.language,
        )
