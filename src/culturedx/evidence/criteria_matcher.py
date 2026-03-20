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

    def match_all_disorders(
        self,
        disorder_codes: list[str],
        sentences: list[str],
        turn_ids: list[int] | None = None,
        language: str = "zh",
        somatization_map: dict[str, list[str]] | None = None,
    ) -> dict[str, list[CriterionEvidence]]:
        """Match all criteria for multiple disorders with batch retrieval.

        Encodes sentences once for all criteria across all disorders.
        """
        # Collect all criteria queries
        query_infos: list[tuple[str, str, str]] = []  # (disorder, full_id, text)
        for dc in disorder_codes:
            criteria = get_disorder_criteria(dc)
            if criteria is None:
                continue
            for crit_id in criteria:
                full_id = f"{dc}.{crit_id}"
                crit_text = get_criterion_text(dc, crit_id, language=language)
                if crit_text:
                    query_infos.append((dc, full_id, crit_text))

        if not query_infos:
            return {dc: [] for dc in disorder_codes}

        # Batch retrieve — encode sentences once
        queries = [qi[2] for qi in query_infos]
        batch_results = self.retriever.retrieve_batch(
            queries=queries,
            sentences=sentences,
            top_k=self.top_k,
            turn_ids=turn_ids,
        )

        # Process results per criterion
        results_map: dict[str, list[CriterionEvidence]] = {
            dc: [] for dc in disorder_codes
        }
        for (dc, full_id, _), results in zip(query_infos, batch_results):
            # Apply somatization boost
            if somatization_map and full_id:
                boosted = []
                for r in results:
                    if full_id in somatization_map.get(r.text, []):
                        boosted.append(
                            replace(r, score=min(1.0, r.score + _SOMATIZATION_BOOST))
                        )
                    else:
                        boosted.append(r)
                results = sorted(boosted, key=lambda r: r.score, reverse=True)

            # Filter by min_score and convert
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

            filtered_results = [r for r in results if r.score >= self.min_score]
            confidence = filtered_results[0].score if filtered_results else 0.0
            results_map[dc].append(
                CriterionEvidence(
                    criterion_id=full_id,
                    spans=spans,
                    confidence=confidence,
                )
            )

        return results_map

    @staticmethod
    def add_contrastive_scores(
        results_map: dict[str, list[CriterionEvidence]],
    ) -> dict[str, list[CriterionEvidence]]:
        """Compute cross-disorder uniqueness scores for each criterion's evidence.

        For each criterion, measures how specific its evidence spans are to that
        disorder vs shared across multiple disorders. A span that matches criteria
        in 3 disorders gets uniqueness 0.0; a span matching only 1 disorder gets 1.0.
        """
        n_disorders = len(results_map)
        if n_disorders <= 1:
            return results_map

        # Build inverted index: span_text -> set of disorder codes that matched it
        span_disorders: dict[str, set[str]] = {}
        for dc, criteria_list in results_map.items():
            for ce in criteria_list:
                for span in ce.spans:
                    key = span.text.strip()
                    if key:
                        if key not in span_disorders:
                            span_disorders[key] = set()
                        span_disorders[key].add(dc)

        # Compute uniqueness per criterion
        for dc, criteria_list in results_map.items():
            for ce in criteria_list:
                if not ce.spans:
                    ce.uniqueness_score = 0.5  # No evidence = neutral
                    continue

                span_uniquenesses = []
                for span in ce.spans:
                    key = span.text.strip()
                    if not key:
                        continue
                    n_matched = len(span_disorders.get(key, {dc}))
                    # 1.0 if unique to this disorder, 0.0 if shared with all
                    u = 1.0 - ((n_matched - 1) / (n_disorders - 1))
                    span_uniquenesses.append(u)

                if span_uniquenesses:
                    # Confidence-weighted: higher-scoring spans matter more
                    ce.uniqueness_score = sum(span_uniquenesses) / len(span_uniquenesses)
                else:
                    ce.uniqueness_score = 0.5

        return results_map
