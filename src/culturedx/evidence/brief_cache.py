"""Evidence Brief cache for sweep acceleration.

Caches EvidenceBrief objects per case to avoid re-running the full
evidence pipeline when the same case is processed across multiple
sweep conditions with identical evidence settings.

Cache key: (case_id, config_hash) where config_hash encodes:
  - target_disorders (sorted)
  - somatization_enabled
  - retriever type
  - scope_policy
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from culturedx.core.models import EvidenceBrief

logger = logging.getLogger(__name__)


class EvidenceBriefCache:
    """In-memory cache for EvidenceBrief objects.

    Avoids re-running evidence extraction pipeline when the same case
    appears across sweep conditions with identical evidence settings.
    """

    def __init__(self) -> None:
        self._cache: dict[str, EvidenceBrief] = {}
        self._hits = 0
        self._misses = 0

    @staticmethod
    def config_hash(
        target_disorders: list[str] | None,
        somatization_enabled: bool,
        scope_policy: str,
        retriever_type: str = "",
        reasoning_standard: str = "icd10",
    ) -> str:
        """Compute hash of evidence config for cache key."""
        key_data = {
            "disorders": sorted(target_disorders) if target_disorders else [],
            "somatization": somatization_enabled,
            "scope": scope_policy,
            "retriever": retriever_type,
            "reasoning_standard": reasoning_standard,
        }
        raw = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, case_id: str, cfg_hash: str) -> EvidenceBrief | None:
        """Look up cached evidence brief."""
        key = f"{case_id}:{cfg_hash}"
        result = self._cache.get(key)
        if result is not None:
            self._hits += 1
            return result
        self._misses += 1
        return None

    def put(self, case_id: str, cfg_hash: str, brief: EvidenceBrief) -> None:
        """Store evidence brief in cache."""
        key = f"{case_id}:{cfg_hash}"
        self._cache[key] = brief

    @property
    def stats(self) -> dict[str, Any]:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "entries": len(self._cache),
            "hit_rate": round(self._hits / total, 3) if total > 0 else 0.0,
        }
