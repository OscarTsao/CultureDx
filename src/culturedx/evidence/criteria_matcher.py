"""Per-criterion evidence matching via dense, lexical, or hybrid retrieval."""
from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from culturedx.core.models import CriterionEvidence, SymptomSpan
from culturedx.evidence.normalization import (
    concept_signature,
    contains_duration_marker,
    contains_functional_impairment_marker,
    contains_negation,
    jaccard_similarity,
    normalize_text,
)
from culturedx.evidence.retriever import BaseRetriever, RetrievalResult
from culturedx.evidence.somatization import resolve_symptom_concept
from culturedx.ontology.icd10 import get_disorder_criteria, get_criterion_text

_SOMATIZATION_BOOST = 0.15
_CONTRADICTION_NEGATION_PENALTY = 0.20


class EvidenceReranker(Protocol):
    """Protocol for optional reranking stages."""

    def rerank(
        self,
        criterion_text: str,
        results: list[RetrievalResult],
        criterion_id: str = "",
    ) -> list[RetrievalResult]:
        ...


class ConceptOverlapReranker:
    """Lightweight reranker based on concept overlap and negation signals."""

    def __init__(self, concept_weight: float = 0.55, score_weight: float = 0.45) -> None:
        self.concept_weight = concept_weight
        self.score_weight = score_weight

    def rerank(
        self,
        criterion_text: str,
        results: list[RetrievalResult],
        criterion_id: str = "",
    ) -> list[RetrievalResult]:
        if not results:
            return []

        reranked: list[RetrievalResult] = []
        for result in results:
            concept_score = jaccard_similarity(criterion_text, result.text)
            negation_penalty = _CONTRADICTION_NEGATION_PENALTY if contains_negation(result.text) else 0.0
            fused = (
                self.score_weight * result.score
                + self.concept_weight * concept_score
                - negation_penalty
            )
            reranked.append(
                replace(
                    result,
                    score=max(0.0, min(1.0, fused)),
                    matched_terms=tuple(sorted(set(result.matched_terms) | set(concept_signature(criterion_text)))),
                )
            )
        return sorted(reranked, key=lambda r: (-r.score, r.turn_id, r.text))


class CriteriaMatcher:
    """Match transcript sentences to diagnostic criteria via retrieval."""

    def __init__(
        self,
        retriever: BaseRetriever,
        top_k: int = 10,
        min_score: float = 0.1,
        reranker: EvidenceReranker | None = None,
        rerank_top_n: int = 5,
    ) -> None:
        self.retriever = retriever
        self.top_k = top_k
        self.min_score = min_score
        self.reranker = reranker
        self.rerank_top_n = rerank_top_n

    def match_criterion(
        self,
        criterion_text: str,
        sentences: list[str],
        turn_ids: list[int] | None = None,
        criterion_id: str = "",
        somatization_map: dict[str, list[str]] | None = None,
    ) -> CriterionEvidence:
        """Match sentences to a single criterion via retrieval."""
        raw_results = self.retriever.retrieve(
            query=criterion_text,
            sentences=sentences,
            top_k=self.top_k,
            turn_ids=turn_ids,
        )
        return self._build_evidence(
            criterion_text=criterion_text,
            criterion_id=criterion_id,
            results=raw_results,
            somatization_map=somatization_map,
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
            raw_results = self.retriever.retrieve(
                query=crit_text,
                sentences=sentences,
                top_k=self.top_k,
                turn_ids=turn_ids,
            )
            evidence = self._build_evidence(
                criterion_text=crit_text,
                criterion_id=full_id,
                results=raw_results,
                somatization_map=somatization_map,
            )
            setattr(evidence, "criterion_type", criteria.get(crit_id, {}).get("type", ""))
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
        """Match all criteria for multiple disorders with batch retrieval."""
        query_infos: list[tuple[str, str, str, dict]] = []
        for dc in disorder_codes:
            criteria = get_disorder_criteria(dc)
            if criteria is None:
                continue
            for crit_id in criteria:
                full_id = f"{dc}.{crit_id}"
                crit_text = get_criterion_text(dc, crit_id, language=language)
                if crit_text:
                    query_infos.append((dc, full_id, crit_text, criteria.get(crit_id, {})))

        if not query_infos:
            return {dc: [] for dc in disorder_codes}

        queries = [qi[2] for qi in query_infos]
        batch_results = self.retriever.retrieve_batch(
            queries=queries,
            sentences=sentences,
            top_k=self.top_k,
            turn_ids=turn_ids,
        )

        results_map: dict[str, list[CriterionEvidence]] = {
            dc: [] for dc in disorder_codes
        }
        for (dc, full_id, crit_text, crit_meta), results in zip(query_infos, batch_results):
            evidence = self._build_evidence(
                criterion_text=crit_text,
                criterion_id=full_id,
                results=results,
                somatization_map=somatization_map,
                criterion_meta=crit_meta,
            )
            setattr(evidence, "criterion_type", crit_meta.get("type", ""))
            results_map[dc].append(evidence)

        return results_map

    def _build_evidence(
        self,
        criterion_text: str,
        criterion_id: str,
        results: list[RetrievalResult],
        somatization_map: dict[str, list[str]] | None = None,
        criterion_meta: dict | None = None,
    ) -> CriterionEvidence:
        reranked = False
        if self.reranker is not None and results:
            head = results[: self.rerank_top_n]
            tail = results[self.rerank_top_n :]
            head = self.reranker.rerank(
                criterion_text=criterion_text,
                results=head,
                criterion_id=criterion_id,
            )
            results = head + tail
            reranked = True

        if somatization_map and criterion_id:
            boosted = []
            for r in results:
                if criterion_id in somatization_map.get(r.text, []):
                    boosted.append(
                        replace(r, score=min(1.0, r.score + _SOMATIZATION_BOOST))
                    )
                else:
                    boosted.append(r)
            results = sorted(boosted, key=lambda r: (-r.score, r.turn_id, r.text))

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
        evidence = CriterionEvidence(
            criterion_id=criterion_id,
            spans=spans,
            confidence=confidence,
        )
        signals = self._build_signals(
            criterion_text=criterion_text,
            criterion_id=criterion_id,
            results=results,
            filtered_results=filtered_results,
            reranked=reranked,
            criterion_meta=criterion_meta or {},
        )
        setattr(evidence, "evidence_signals", signals)
        setattr(evidence, "signal_tags", signals["signal_tags"])
        setattr(evidence, "retrieval_mode", signals["retrieval_mode"])
        return evidence

    def _build_signals(
        self,
        criterion_text: str,
        criterion_id: str,
        results: list[RetrievalResult],
        filtered_results: list[RetrievalResult],
        reranked: bool,
        criterion_meta: dict,
    ) -> dict:
        signal_tags: list[str] = []
        if not filtered_results:
            signal_tags.append("insufficient_evidence")
        else:
            top = filtered_results[0]
            if contains_negation(top.text) and jaccard_similarity(criterion_text, top.text) > 0.20:
                signal_tags.append("contradiction")

        criterion_type = criterion_meta.get("type", "")
        result_texts = [r.text for r in filtered_results]
        result_blob = " ".join(result_texts)
        if criterion_type == "duration" or "持续" in criterion_text or "duration" in normalize_text(criterion_text):
            if not contains_duration_marker(result_blob):
                signal_tags.append("duration_missing")

        if any(keyword in normalize_text(criterion_text) for keyword in ("功能", "工作", "学习", "社交", "impair")):
            if not contains_functional_impairment_marker(result_blob):
                signal_tags.append("functional_impairment_missing")

        return {
            "criterion_id": criterion_id,
            "signal_tags": signal_tags,
            "reranked": reranked,
            "retrieval_mode": self._retrieval_mode_name(),
            "top_score": filtered_results[0].score if filtered_results else 0.0,
            "span_count": len(filtered_results),
            "concept_signature": sorted(concept_signature(criterion_text)),
        }

    def _retrieval_mode_name(self) -> str:
        name = type(self.retriever).__name__.replace("Retriever", "").lower()
        if name == "hybrid":
            return "hybrid"
        if name == "lexical":
            return "lexical"
        if name == "mock":
            return "mock"
        return "dense"

    @staticmethod
    def add_contrastive_scores(
        results_map: dict[str, list[CriterionEvidence]],
    ) -> dict[str, list[CriterionEvidence]]:
        """Compute cross-disorder uniqueness scores for each criterion's evidence."""
        n_disorders = len(results_map)
        if n_disorders <= 1:
            return results_map

        span_concepts: dict[str, set[str]] = {}
        for dc, criteria_list in results_map.items():
            for ce in criteria_list:
                for span in ce.spans:
                    key = CriteriaMatcher._concept_key_for_span(span.text)
                    if key:
                        span_concepts.setdefault(key, set()).add(dc)

        for dc, criteria_list in results_map.items():
            for ce in criteria_list:
                if not ce.spans:
                    ce.uniqueness_score = 0.5
                    continue

                span_uniquenesses = []
                for span in ce.spans:
                    key = CriteriaMatcher._concept_key_for_span(span.text)
                    if not key:
                        continue
                    n_matched = len(span_concepts.get(key, {dc}))
                    u = 1.0 - ((n_matched - 1) / (n_disorders - 1))
                    span_uniquenesses.append(u)

                if span_uniquenesses:
                    ce.uniqueness_score = sum(span_uniquenesses) / len(span_uniquenesses)
                else:
                    ce.uniqueness_score = 0.5

        return results_map

    @staticmethod
    def _concept_key_for_span(text: str) -> str:
        resolved = resolve_symptom_concept(text)
        if resolved is not None:
            return f"{resolved.category}|{resolved.canonical_text}|{','.join(resolved.criteria)}"
        tokens = sorted(concept_signature(text))
        if not tokens:
            return normalize_text(text)
        return "|".join(tokens[:8])
