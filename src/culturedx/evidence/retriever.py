"""Retriever abstraction for dense, lexical, and hybrid evidence retrieval."""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np

from culturedx.evidence.normalization import concept_terms, normalize_text


@dataclass
class RetrievalResult:
    """A single retrieval result."""

    text: str
    turn_id: int
    score: float
    source: str = "dense"
    matched_terms: tuple[str, ...] = field(default_factory=tuple)
    normalized_text: str = ""


class BaseRetriever(ABC):
    """Abstract base for evidence retrievers."""

    @abstractmethod
    def retrieve(
        self,
        query: str,
        sentences: list[str],
        top_k: int = 10,
        turn_ids: list[int] | None = None,
    ) -> list[RetrievalResult]:
        """Retrieve top-k most relevant sentences for a query."""
        ...

    def retrieve_batch(
        self,
        queries: list[str],
        sentences: list[str],
        top_k: int = 10,
        turn_ids: list[int] | None = None,
    ) -> list[list[RetrievalResult]]:
        """Batch retrieve: encode sentences once for multiple queries.

        Default implementation calls retrieve() per query.
        Subclasses can override for optimized batch processing.
        """
        return [
            self.retrieve(q, sentences, top_k, turn_ids)
            for q in queries
        ]


def _result_key(result: RetrievalResult) -> tuple[int, str]:
    return result.turn_id, result.text


def _stable_sort(results: Iterable[RetrievalResult]) -> list[RetrievalResult]:
    return sorted(results, key=lambda r: (-r.score, r.turn_id, r.text))


class LexicalRetriever(BaseRetriever):
    """Lightweight lexical retriever based on normalized token overlap."""

    def retrieve(
        self,
        query: str,
        sentences: list[str],
        top_k: int = 10,
        turn_ids: list[int] | None = None,
    ) -> list[RetrievalResult]:
        if not sentences:
            return []
        if turn_ids is None:
            turn_ids = list(range(len(sentences)))

        query_terms = concept_terms(query)
        query_signature = set(query_terms)
        results = []
        for sent, tid in zip(sentences, turn_ids):
            sent_terms = concept_terms(sent)
            sent_signature = set(sent_terms)
            if query_signature and sent_signature:
                overlap = len(query_signature & sent_signature)
                denom = len(query_signature) + len(sent_signature)
                score = (2 * overlap / denom) if denom else 0.0
            else:
                score = 0.0
            results.append(
                RetrievalResult(
                    text=sent,
                    turn_id=tid,
                    score=float(score),
                    source="lexical",
                    matched_terms=tuple(sorted(query_signature & sent_signature)),
                    normalized_text=normalize_text(sent),
                )
            )
        return _stable_sort(results)[:top_k]


class HybridRetriever(BaseRetriever):
    """Combine dense and lexical retrievers with weighted score fusion."""

    def __init__(
        self,
        dense_retriever: BaseRetriever,
        lexical_retriever: BaseRetriever | None = None,
        dense_weight: float = 0.65,
        lexical_weight: float = 0.35,
    ) -> None:
        self.dense_retriever = dense_retriever
        self.lexical_retriever = lexical_retriever or LexicalRetriever()
        self.dense_weight = dense_weight
        self.lexical_weight = lexical_weight

    def retrieve(
        self,
        query: str,
        sentences: list[str],
        top_k: int = 10,
        turn_ids: list[int] | None = None,
    ) -> list[RetrievalResult]:
        if not sentences:
            return []

        dense_results = self.dense_retriever.retrieve(query, sentences, top_k=top_k, turn_ids=turn_ids)
        lexical_results = self.lexical_retriever.retrieve(query, sentences, top_k=top_k, turn_ids=turn_ids)
        return self._fuse_results(dense_results, lexical_results, top_k=top_k)

    def retrieve_batch(
        self,
        queries: list[str],
        sentences: list[str],
        top_k: int = 10,
        turn_ids: list[int] | None = None,
    ) -> list[list[RetrievalResult]]:
        if not queries:
            return []
        if not sentences:
            return [[] for _ in queries]

        dense_batches = self.dense_retriever.retrieve_batch(queries, sentences, top_k=top_k, turn_ids=turn_ids)
        lexical_batches = self.lexical_retriever.retrieve_batch(queries, sentences, top_k=top_k, turn_ids=turn_ids)
        return [
            self._fuse_results(dense, lexical, top_k=top_k)
            for dense, lexical in zip(dense_batches, lexical_batches)
        ]

    def _fuse_results(
        self,
        dense_results: list[RetrievalResult],
        lexical_results: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        merged: dict[tuple[int, str], RetrievalResult] = {}

        def _add(result: RetrievalResult, weight: float, source: str) -> None:
            key = _result_key(result)
            existing = merged.get(key)
            weighted_score = max(0.0, min(1.0, result.score * weight))
            if existing is None:
                merged[key] = RetrievalResult(
                    text=result.text,
                    turn_id=result.turn_id,
                    score=weighted_score,
                    source=source,
                    matched_terms=result.matched_terms,
                    normalized_text=result.normalized_text or normalize_text(result.text),
                )
                return
            combined_terms = tuple(sorted(set(existing.matched_terms) | set(result.matched_terms)))
            merged[key] = RetrievalResult(
                text=existing.text,
                turn_id=existing.turn_id,
                score=max(0.0, min(1.0, existing.score + weighted_score)),
                source="hybrid",
                matched_terms=combined_terms,
                normalized_text=existing.normalized_text or normalize_text(existing.text),
            )

        for result in dense_results:
            _add(result, self.dense_weight, "dense")
        for result in lexical_results:
            _add(result, self.lexical_weight, "lexical")

        fused = _stable_sort(merged.values())
        return fused[:top_k]


class MockRetriever(BaseRetriever):
    """Deterministic hash-based retriever for testing."""

    def retrieve(
        self,
        query: str,
        sentences: list[str],
        top_k: int = 10,
        turn_ids: list[int] | None = None,
    ) -> list[RetrievalResult]:
        if not sentences:
            return []
        if turn_ids is None:
            turn_ids = list(range(len(sentences)))

        results = []
        for i, (sent, tid) in enumerate(zip(sentences, turn_ids)):
            # Deterministic score from hash of query + sentence
            h = hashlib.md5(
                f"{query}:{sent}".encode("utf-8")
            ).hexdigest()
            score = int(h[:8], 16) / 0xFFFFFFFF
            results.append(
                RetrievalResult(
                    text=sent,
                    turn_id=tid,
                    score=score,
                    source="mock",
                    matched_terms=concept_terms(query),
                    normalized_text=normalize_text(sent),
                )
            )

        return _stable_sort(results)[:top_k]


class BGEM3Retriever(BaseRetriever):
    """BGE-M3 dense retriever using sentence-transformers."""

    def __init__(
        self,
        model_id: str = "BAAI/bge-m3",
        device: str = "auto",
        cache_dir: str | None = None,
    ) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is required for BGEM3Retriever. "
                "Install with: uv pip install 'culturedx[retrieval]'"
            ) from e

        if device == "auto":
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"

        self._model = SentenceTransformer(
            model_id, device=device, cache_folder=cache_dir
        )

    def retrieve(
        self,
        query: str,
        sentences: list[str],
        top_k: int = 10,
        turn_ids: list[int] | None = None,
    ) -> list[RetrievalResult]:
        if not sentences:
            return []
        if turn_ids is None:
            turn_ids = list(range(len(sentences)))

        query_emb = self._model.encode([query], normalize_embeddings=True)
        sent_emb = self._model.encode(sentences, normalize_embeddings=True)

        # Cosine similarity (embeddings already normalized)
        scores = np.dot(sent_emb, query_emb.T).flatten()

        # Get top-k indices
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            results.append(
                RetrievalResult(
                    text=sentences[idx],
                    turn_id=turn_ids[idx],
                    score=float(scores[idx]),
                    source="dense",
                    matched_terms=concept_terms(query),
                    normalized_text=normalize_text(sentences[idx]),
                )
            )
        return _stable_sort(results)

    def retrieve_batch(
        self,
        queries: list[str],
        sentences: list[str],
        top_k: int = 10,
        turn_ids: list[int] | None = None,
    ) -> list[list[RetrievalResult]]:
        """Batch retrieve: encode sentences once for all queries."""
        if not sentences or not queries:
            return [[] for _ in queries]
        if turn_ids is None:
            turn_ids = list(range(len(sentences)))

        # Encode all at once — this is the key optimization
        query_embs = self._model.encode(queries, normalize_embeddings=True)
        sent_embs = self._model.encode(sentences, normalize_embeddings=True)

        # All-pairs cosine similarity: (n_sent, n_queries)
        scores_matrix = np.dot(sent_embs, query_embs.T)

        all_results = []
        for qi in range(len(queries)):
            scores = scores_matrix[:, qi]
            top_indices = np.argsort(scores)[::-1][:top_k]
            results = []
            for idx in top_indices:
                results.append(
                    RetrievalResult(
                        text=sentences[idx],
                        turn_id=turn_ids[idx],
                        score=float(scores[idx]),
                        source="dense",
                        matched_terms=concept_terms(queries[qi]),
                        normalized_text=normalize_text(sentences[idx]),
                    )
                )
            all_results.append(_stable_sort(results))
        return all_results
