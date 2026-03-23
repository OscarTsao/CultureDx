"""Base mode orchestrator."""
from __future__ import annotations

from abc import ABC, abstractmethod
import logging
import time

logger = logging.getLogger(__name__)

from culturedx.core.models import (
    CheckerOutput,
    ClinicalCase,
    DiagnosisResult,
    EvidenceBrief,
)


class BaseModeOrchestrator(ABC):
    """Abstract base for all diagnostic mode orchestrators."""

    # Subclasses must set these in __init__
    mode_name: str = ""
    llm: object = None  # LLM client

    @abstractmethod
    def diagnose(
        self, case: ClinicalCase, evidence: EvidenceBrief | None = None
    ) -> DiagnosisResult:
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
        """Build disorder_code -> evidence summary text mapping."""
        result = {}
        for de in evidence.disorder_evidence:
            parts = []
            for ce in de.criteria_evidence:
                span_texts = [s.text for s in ce.spans]
                if span_texts:
                    parts.append(
                        f"[{ce.criterion_id}] (conf={ce.confidence:.2f}): "
                        + "; ".join(span_texts)
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
    ) -> DiagnosisResult:
        """Return an abstention DiagnosisResult."""
        return DiagnosisResult(
            case_id=case.case_id,
            primary_diagnosis=None,
            confidence=0.0,
            decision="abstain",
            criteria_results=criteria_results or [],
            mode=self.mode_name,
            model_name=self.llm.model if self.llm else "",
            language_used=lang,
        )

    def _parallel_check_criteria(
        self,
        checker,
        disorder_codes: list[str],
        transcript_text: str,
        evidence_map: dict[str, str],
        lang: str,
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

        if max_workers is None:
            max_workers = getattr(self.llm, "max_concurrent", 1)

        def _check_one(disorder_code: str) -> CheckerOutput | None:
            get_disorder_name(disorder_code, lang) or disorder_code
            evidence_summary = evidence_map.get(disorder_code)

            # Lightweight somatization hints when no evidence pipeline
            if not evidence_summary and lang == "zh":
                from culturedx.ontology.symptom_map import scan_somatic_hints
                evidence_summary = scan_somatic_hints(transcript_text, disorder_code)

            checker_input = AgentInput(
                transcript_text=transcript_text,
                evidence={"evidence_summary": evidence_summary} if evidence_summary else None,
                language=lang,
                extra={"disorder_code": disorder_code},
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
        workers = min(len(disorder_codes), max_workers)
        if workers <= 1:
            # Single disorder: no threading overhead
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
                        import logging

                        logging.getLogger(__name__).warning(
                            "Criterion checker failed for %s", code, exc_info=True
                        )
        t_total = time.monotonic() - t_start
        actual_workers = getattr(self.llm, "max_concurrent", 1)
        logger.info(
            "Checker timing: %d disorders in %.1fs (%.1fs/disorder, %d workers)",
            len(disorder_codes),
            t_total,
            t_total / max(len(disorder_codes), 1),
            actual_workers,
        )
        return checker_outputs
