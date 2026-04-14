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
        target_disorders: list[str] | None = None,
        prompt_variant: str = "",
        case_retriever=None,
    ) -> None:
        self.mode_name = "single"
        self.llm = llm_client
        self.prompts_dir = Path(prompts_dir)
        self.target_disorders = target_disorders or []
        self.prompt_variant = prompt_variant
        self.case_retriever = case_retriever
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

    def _retrieve_similar_cases(self, transcript_text: str) -> list[dict] | None:
        """Retrieve similar training cases if CaseRetriever is available."""
        if self.case_retriever is None:
            return None
        try:
            candidate_codes = self.target_disorders or []
            if hasattr(self.case_retriever, 'retrieve_balanced') and candidate_codes:
                raw_cases = self.case_retriever.retrieve_balanced(
                    transcript_text, candidate_codes, top_per_class=1,
                )
            else:
                raw_cases = self.case_retriever.retrieve(transcript_text, top_k=5)
            similar_cases = []
            for sc in raw_cases:
                codes = sc.get("diagnosis_codes", [])
                names = sc.get("diagnosis_names", [])
                similar_cases.append({
                    "similarity": sc["similarity"],
                    "diagnosis_code": codes[0] if codes else "?",
                    "diagnosis_name": names[0] if names else "",
                })
            return similar_cases
        except Exception as e:
            logger.warning("CaseRetriever failed in single mode: %s", e)
            return None

    def _fit_prompt_to_context(
        self,
        *,
        case: ClinicalCase,
        template,
        evidence: EvidenceBrief | None,
        initial_max_chars: int,
        similar_cases: list[dict] | None = None,
    ) -> tuple[str, str]:
        """Render a prompt while shrinking transcript text for smaller backbones."""
        transcript_budget = initial_max_chars
        context_chars = max(
            1200,
            int((self._context_window_tokens() - self._max_output_tokens() - 512) * 1.8),
        )

        while True:
            transcript_text = self._build_transcript_text(case, max_chars=transcript_budget)
            prompt = template.render(
                transcript_text=transcript_text,
                evidence=evidence,
                similar_cases=similar_cases,
            )
            if len(prompt) <= context_chars or transcript_budget <= 1400:
                return transcript_text, prompt

            overflow = len(prompt) - context_chars
            transcript_budget = max(1400, transcript_budget - overflow - 256)

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
        elif getattr(self, "prompt_variant", "") == "rag":
            template_name = f"zero_shot_rag_{lang}.jinja"
        else:
            template_name = f"zero_shot_{lang}.jinja"
        template = self._env.get_template(template_name)
        max_chars = self._default_transcript_char_budget(
            evidence_present=bool(evidence),
        )
        transcript_text = self._build_transcript_text(case, max_chars=max_chars)

        # Retrieve similar cases for RAG variant
        similar_cases = None
        if getattr(self, "prompt_variant", "") == "rag":
            similar_cases = self._retrieve_similar_cases(transcript_text)

        # Estimate non-evidence prompt overhead and reserve room for evidence.
        base_prompt = template.render(
            transcript_text=transcript_text,
            evidence=None,
            similar_cases=similar_cases,
        )
        base_chars = len(base_prompt)
        input_chars_budget = max(
            1200,
            int((self._context_window_tokens() - self._max_output_tokens() - 512) * 1.8),
        )
        max_evidence_chars = input_chars_budget - base_chars

        if evidence and max_evidence_chars > 0:
            evidence = self._truncate_evidence(evidence, max_evidence_chars, case.case_id)

        transcript_text, prompt = self._fit_prompt_to_context(
            case=case,
            template=template,
            evidence=evidence,
            initial_max_chars=max_chars,
            similar_cases=similar_cases,
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
