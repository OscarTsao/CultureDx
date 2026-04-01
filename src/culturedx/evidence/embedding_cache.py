"""Sentence embedding cache for dense retrievers.

Avoids re-encoding identical sentence sets across sweep conditions.
Cache key is a content hash of the sorted sentences.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """In-memory cache for sentence embeddings keyed by content hash.

    Thread-safe for read-after-write (no concurrent writes to same key).
    Designed for sweep execution where same cases are processed across
    multiple conditions.
    """

    def __init__(self, max_entries: int = 50000) -> None:
        self._cache: dict[str, np.ndarray] = {}
        self._max_entries = max_entries
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _hash_sentences(sentences: list[str]) -> str:
        """Compute content hash for a list of sentences."""
        content = "\n".join(sentences)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:24]

    def get(self, sentences: list[str]) -> np.ndarray | None:
        """Look up cached embeddings for a sentence set."""
        key = self._hash_sentences(sentences)
        result = self._cache.get(key)
        if result is not None:
            self._hits += 1
            return result
        self._misses += 1
        return None

    def put(self, sentences: list[str], embeddings: np.ndarray) -> None:
        """Store embeddings for a sentence set."""
        if len(self._cache) >= self._max_entries:
            # Simple eviction: clear oldest half
            keys = list(self._cache.keys())
            for k in keys[: len(keys) // 2]:
                del self._cache[k]
            logger.info("EmbeddingCache evicted %d entries", len(keys) // 2)
        key = self._hash_sentences(sentences)
        self._cache[key] = embeddings

    @property
    def stats(self) -> dict[str, int]:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "entries": len(self._cache),
            "hit_rate": (
                round(self._hits / (self._hits + self._misses), 3)
                if (self._hits + self._misses) > 0
                else 0.0
            ),
        }
