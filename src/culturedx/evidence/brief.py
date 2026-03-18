"""Evidence Brief assembler: combine matched evidence into structured brief."""
from __future__ import annotations

from culturedx.core.models import (
    CriterionEvidence,
    DisorderEvidence,
    EvidenceBrief,
    SymptomSpan,
)
from culturedx.ontology.icd10 import get_disorder_name


class EvidenceBriefAssembler:
    """Assemble an EvidenceBrief from matched evidence."""

    def __init__(self, min_confidence: float = 0.1) -> None:
        self.min_confidence = min_confidence

    def assemble(
        self,
        case_id: str,
        language: str,
        symptom_spans: list[SymptomSpan] | None = None,
        criteria_results: dict[str, list[CriterionEvidence]] | None = None,
    ) -> EvidenceBrief:
        """Assemble an EvidenceBrief.

        Args:
            case_id: The case identifier.
            language: Language code ("zh" or "en").
            symptom_spans: Extracted symptom spans (optional).
            criteria_results: Dict mapping disorder_code to list of
                CriterionEvidence from criteria matching.

        Returns:
            Assembled EvidenceBrief.
        """
        disorder_evidence = []
        if criteria_results:
            for disorder_code, criterion_list in criteria_results.items():
                # Filter by min_confidence
                filtered = [
                    ce for ce in criterion_list
                    if ce.confidence >= self.min_confidence
                ]
                name = get_disorder_name(disorder_code, language) or disorder_code
                disorder_evidence.append(
                    DisorderEvidence(
                        disorder_code=disorder_code,
                        disorder_name=name,
                        criteria_evidence=filtered,
                    )
                )

        return EvidenceBrief(
            case_id=case_id,
            language=language,
            symptom_spans=symptom_spans or [],
            disorder_evidence=disorder_evidence,
        )
