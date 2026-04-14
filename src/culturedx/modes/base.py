"""Shared utilities and contracts for diagnostic mode orchestrators.

Every mode subclass implements ``diagnose()`` and then reuses the helper
utilities here for transcript rendering, evidence summarization, parallel
checker fanout, and standardized abstention payloads.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
import logging
import threading
import time

logger = logging.getLogger(__name__)

_case_execution_state = threading.local()


@contextmanager
def case_execution_context(*, outer_parallelism: bool):
    """Mark the current thread as already participating in case-level fanout."""
    prior = bool(getattr(_case_execution_state, "outer_parallelism", False))
    _case_execution_state.outer_parallelism = prior or outer_parallelism
    try:
        yield
    finally:
        _case_execution_state.outer_parallelism = prior


def resolve_inner_parallelism(requested_workers: int) -> tuple[int, str | None]:
    """Resolve inner parallelism for checker threads.

    With sync HTTP (no asyncio), nested thread pools are safe at moderate scale.
    max_cases_in_flight=8 x 5 checker threads = 40 threads total — well within limits.
    """
    return requested_workers, None

from culturedx.core.models import (
    CheckerOutput,
    ClinicalCase,
    DiagnosisResult,
    EvidenceBrief,
    FailureInfo,
)


class BaseModeOrchestrator(ABC):
    """Abstract base for all diagnostic mode orchestrators."""

    # Subclasses must set these in __init__
    mode_name: str = ""
    llm: object = None  # LLM client

    def _context_window_tokens(self) -> int:
        """Return the serving context window used for prompt budgeting."""
        return int(getattr(self.llm, "context_window", None) or 16384)

    def _max_output_tokens(self) -> int:
        """Return configured generation cap used for prompt budgeting."""
        return int(getattr(self.llm, "max_tokens", 2048) or 2048)

    def _default_transcript_char_budget(
        self,
        *,
        evidence_present: bool,
        safety_margin_tokens: int = 1024,
        chars_per_token: float = 1.8,
    ) -> int:
        """Estimate a conservative transcript budget for the active backend.

        The budget is intentionally conservative because Chinese transcript
        prompts plus long ICD instructions and RAG exemplars can otherwise
        exceed smaller context windows even when character count looks modest.
        """
        input_budget_tokens = max(
            512,
            self._context_window_tokens() - self._max_output_tokens() - safety_margin_tokens,
        )
        max_chars = int(input_budget_tokens * chars_per_token)
        if evidence_present:
            max_chars = min(max_chars, 8000)
        return max(1200, min(max_chars, 20000))

    @abstractmethod
    def diagnose(
        self, case: ClinicalCase, evidence: EvidenceBrief | None = None
    ) -> DiagnosisResult:
        """Run one case through the mode and return a structured diagnosis.

        Implementations should keep routing mode, scope policy, failures, and
        stage timings explicit in the returned ``DiagnosisResult``.
        """
        ...

    @staticmethod
    def _build_transcript_text(
        case: ClinicalCase, max_chars: int = 20000,
    ) -> str:
        """Build formatted transcript text from case turns.

        For long transcripts, keeps first and last turns (head/tail truncation)
        to stay within context window. Clinical assessments have important info
        at the start (chief complaint) and end (summary/formulation).
        """
        lines = []
        for turn in case.transcript:
            speaker = turn.speaker.capitalize()
            lines.append(f"{speaker}: {turn.text}")
        full = "\n".join(lines)

        if len(full) <= max_chars:
            return full

        # Head/tail truncation: keep first 60% and last 40% of budget
        head_budget = int(max_chars * 0.6)
        tail_budget = max_chars - head_budget

        head_lines = []
        head_len = 0
        for line in lines:
            if head_len + len(line) + 1 > head_budget:
                break
            head_lines.append(line)
            head_len += len(line) + 1

        tail_lines = []
        tail_len = 0
        for line in reversed(lines):
            if tail_len + len(line) + 1 > tail_budget:
                break
            tail_lines.insert(0, line)
            tail_len += len(line) + 1

        marker = "\n[...对话中间部分省略 / middle turns omitted...]\n"
        return "\n".join(head_lines) + marker + "\n".join(tail_lines)

    @staticmethod
    def _build_evidence_map(evidence: EvidenceBrief) -> dict[str, str]:
        """Build disorder_code -> evidence summary text mapping.

        Includes structured metadata from negation detection and
        somatization mapping so the checker agent can use it.
        """
        result = {}
        for de in evidence.disorder_evidence:
            parts = []
            for ce in de.criteria_evidence:
                if not ce.spans:
                    continue
                span_descs = []
                for s in ce.spans:
                    desc = s.text
                    tags = []
                    if s.expression_type == "negated":
                        tags.append("否定")
                    if s.mapping_source:
                        tags.append(f"躯体化映射:{s.mapping_source}")
                    if s.normalized_concept and s.normalized_concept != s.text:
                        tags.append(f"标准化:{s.normalized_concept}")
                    if tags:
                        desc = f"{s.text} [{', '.join(tags)}]"
                    span_descs.append(desc)
                neg_marker = ""
                if ce.has_negated_spans:
                    neg_marker = " ⚠否定证据"
                soma_marker = ""
                if ce.has_somatization_mapped:
                    sources = "/".join(sorted(set(ce.somatization_sources)))
                    soma_marker = f" [躯体化:{sources}]"
                parts.append(
                    f"[{ce.criterion_id}] (conf={ce.confidence:.2f}){neg_marker}{soma_marker}: "
                    + "; ".join(span_descs)
                )
            if parts:
                result[de.disorder_code] = "\n".join(parts)
        return result

    @staticmethod
    def _build_global_evidence_summary(evidence: EvidenceBrief | None) -> str | None:
        """Extract top symptom spans as summary text."""
        if not evidence or not evidence.symptom_spans:
            return None
        symptoms = [s.text for s in evidence.symptom_spans[:20]]
        return "Extracted symptoms: " + "; ".join(symptoms)

    def _abstain(
        self,
        case: ClinicalCase,
        lang: str,
        criteria_results: list[CheckerOutput] | None = None,
        failure: FailureInfo | None = None,
        candidate_disorders: list[str] | None = None,
        routing_mode: str = "auto",
        scope_policy: str = "auto",
        decision_trace: dict | None = None,
        failures: list[FailureInfo] | None = None,
        stage_timings: dict[str, float] | None = None,
    ) -> DiagnosisResult:
        """Return an abstention DiagnosisResult."""
        failure_list = list(failures or [])
        if failure is not None:
            failure_list.append(failure)
        return DiagnosisResult(
            case_id=case.case_id,
            primary_diagnosis=None,
            confidence=0.0,
            decision="abstain",
            criteria_results=criteria_results or [],
            mode=self.mode_name,
            model_name=self.llm.model if self.llm else "",
            checker_model_name=getattr(self, "checker_model_name", None),
            language_used=lang,
            candidate_disorders=candidate_disorders or [],
            routing_mode=routing_mode,
            scope_policy=scope_policy,
            decision_trace=decision_trace,
            stage_timings=stage_timings or {},
            failure=failure,
            failures=failure_list,
        )

    def _parallel_check_criteria(
        self,
        checker,
        disorder_codes: list[str],
        transcript_text: str,
        evidence_map: dict[str, str | dict[str, str]],
        lang: str,
        prompt_variant: str = "",
        checker_llm_client=None,
        max_workers: int | None = None,
    ) -> list:
        """Run criterion checkers in parallel using ThreadPoolExecutor.

        Returns list of CheckerOutput for disorders that produced valid results.

        max_workers is auto-detected from LLM client:
        - Ollama (NUM_PARALLEL=1): sequential to avoid timeout cascading
        - vLLM (continuous batching): parallel for real concurrency
        """
        t_start = time.monotonic()
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from culturedx.agents.base import AgentInput
        from culturedx.core.models import CheckerOutput
        from culturedx.ontology.icd10 import get_disorder_name

        active_checker_llm = (
            checker_llm_client
            or getattr(checker, "llm", None)
            or self.llm
        )
        if max_workers is None:
            max_workers = max(getattr(active_checker_llm, "max_concurrent", 1), 5)

        def _check_one(disorder_code: str) -> CheckerOutput | None:
            evidence_payload = evidence_map.get(disorder_code)
            evidence_summary = None
            temporal_summary = None
            if isinstance(evidence_payload, dict):
                evidence_summary = evidence_payload.get("evidence_summary")
                temporal_summary = evidence_payload.get("temporal_summary")
            else:
                evidence_summary = evidence_payload

            # Lightweight somatization hints when no evidence pipeline
            if not evidence_summary and lang == "zh":
                from culturedx.ontology.symptom_map import scan_somatic_hints
                evidence_summary = scan_somatic_hints(transcript_text, disorder_code)

            checker_evidence = {}
            if evidence_summary:
                checker_evidence["evidence_summary"] = evidence_summary
            if temporal_summary:
                checker_evidence["temporal_summary"] = temporal_summary
            checker_input = AgentInput(
                transcript_text=transcript_text,
                evidence=checker_evidence or None,
                language=lang,
                extra={
                    "disorder_code": disorder_code,
                    "prompt_variant": prompt_variant,
                },
            )
            output = checker.run(checker_input)
            if output.parsed:
                return CheckerOutput(
                    disorder=output.parsed["disorder"],
                    criteria=output.parsed["criteria"],
                    criteria_met_count=output.parsed["criteria_met_count"],
                    criteria_required=output.parsed["criteria_required"],
                )
            return None

        checker_outputs = []
        requested_workers = min(len(disorder_codes), max_workers)
        workers, collapse_reason = resolve_inner_parallelism(requested_workers)
        if collapse_reason is not None:
            logger.info(
                "Checker fanout collapsed from %d to %d worker inside %s",
                requested_workers,
                workers,
                collapse_reason,
            )
        if workers <= 1:
            # Single disorder or nested outer fanout: avoid extra thread pool churn.
            for code in disorder_codes:
                co = _check_one(code)
                if co:
                    checker_outputs.append(co)
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_code = {
                    executor.submit(_check_one, code): code
                    for code in disorder_codes
                }
                for future in as_completed(future_to_code):
                    code = future_to_code[future]
                    try:
                        co = future.result()
                        if co:
                            checker_outputs.append(co)
                    except Exception:
                        logger.warning(
                            "Criterion checker failed for %s", code, exc_info=True
                        )
        t_total = time.monotonic() - t_start
        logger.info(
            "Checker timing: %d disorders in %.1fs (%.1fs/disorder, %d workers)",
            len(disorder_codes),
            t_total,
            t_total / max(len(disorder_codes), 1),
            workers,
        )
        return checker_outputs
