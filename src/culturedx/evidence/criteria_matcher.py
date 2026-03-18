"""Per-criterion evidence matching via dense retrieval."""
from __future__ import annotations

from dataclasses import replace

from culturedx.core.models import CriterionEvidence, SymptomSpan
from culturedx.evidence.retriever import BaseRetriever, RetrievalResult
from culturedx.ontology.icd10 import get_disorder_criteria, get_criterion_text

_SOMATIZATION_BOOST = 0.15


class CriteriaMatcher:
    """Match transcript sentences to diagnostic criteria via retrieval."""

    def __init__(
        self,
        retriever: BaseRetriever,
        top_k: int = 10,
        min_score: float = 0.1,
    ) -> None:
        self.retriever = retriever
        self.top_k = top_k
        self.min_score = min_score

    def match_criterion(
        self,
        criterion_text: str,
        sentences: list[str],
        turn_ids: list[int] | None = None,
        criterion_id: str = "",
        somatization_map: dict[str, list[str]] | None = None,
    ) -> CriterionEvidence:
        """Match sentences to a single criterion via retrieval."""
        results = self.retriever.retrieve(
            query=criterion_text,
            sentences=sentences,
            top_k=self.top_k,
            turn_ids=turn_ids,
        )

        # Apply somatization boost
        if somatization_map and criterion_id:
            boosted = []
            for r in results:
                if criterion_id in somatization_map.get(r.text, []):
                    boosted.append(
                        replace(r, score=min(1.0, r.score + _SOMATIZATION_BOOST))
                    )
                else:
                    boosted.append(r)
            results = sorted(boosted, key=lambda r: r.score, reverse=True)

        # Filter by min_score and convert to CriterionEvidence
        spans = []
        for r in results:
            if r.score < self.min_score:
                continue
            spans.append(
                SymptomSpan(
                    text=r.text,
                    turn_id=r.turn_id,
                    symptom_type="retrieved",
                )
            )

        # Confidence from the best matching result after filtering
        filtered_results = [r for r in results if r.score >= self.min_score]
        confidence = filtered_results[0].score if filtered_results else 0.0
        return CriterionEvidence(
            criterion_id=criterion_id,
            spans=spans,
            confidence=confidence,
        )

    def match_for_disorder(
        self,
        disorder_code: str,
        sentences: list[str],
        turn_ids: list[int] | None = None,
        language: str = "zh",
        somatization_map: dict[str, list[str]] | None = None,
    ) -> list[CriterionEvidence]:
        """Match all criteria for a disorder. Returns list of CriterionEvidence."""
        criteria = get_disorder_criteria(disorder_code)
        if criteria is None:
            return []

        results = []
        for crit_id in criteria:
            full_id = f"{disorder_code}.{crit_id}"
            crit_text = get_criterion_text(
                disorder_code, crit_id, language=language
            )
            if crit_text is None:
                continue
            evidence = self.match_criterion(
                criterion_text=crit_text,
                sentences=sentences,
                turn_ids=turn_ids,
                criterion_id=full_id,
                somatization_map=somatization_map,
            )
            results.append(evidence)
        return results
