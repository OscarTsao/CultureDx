"""Retriever abstraction for dense evidence retrieval."""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass
class RetrievalResult:
    """A single retrieval result."""

    text: str
    turn_id: int
    score: float


class BaseRetriever(ABC):
    """Abstract base for dense retrievers."""

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
            results.append(RetrievalResult(text=sent, turn_id=tid, score=score))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]


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
                )
            )
        return results
