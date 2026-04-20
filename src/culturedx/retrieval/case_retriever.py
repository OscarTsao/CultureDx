"""Case retriever: find similar training cases for few-shot grounding.

Uses a pre-built FAISS index of BGE-M3 dense embeddings over the training
split. At query time the caller's transcript is encoded, and the top-k nearest
neighbours are returned with diagnosis labels and a short preview.

Dependencies (optional):
    pip install faiss-cpu sentence-transformers
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

_FAISS_AVAILABLE: bool | None = None
_ST_AVAILABLE: bool | None = None


def _check_faiss() -> None:
    global _FAISS_AVAILABLE
    if _FAISS_AVAILABLE is None:
        try:
            import faiss  # noqa: F401

            _FAISS_AVAILABLE = True
        except ImportError:
            _FAISS_AVAILABLE = False
    if not _FAISS_AVAILABLE:
        raise ImportError(
            "faiss is required for CaseRetriever. Install with: pip install faiss-cpu"
        )


def _check_sentence_transformers() -> None:
    global _ST_AVAILABLE
    if _ST_AVAILABLE is None:
        try:
            import sentence_transformers  # noqa: F401

            _ST_AVAILABLE = True
        except ImportError:
            _ST_AVAILABLE = False
    if not _ST_AVAILABLE:
        raise ImportError(
            "sentence-transformers is required for CaseRetriever encoding. "
            "Install with: pip install sentence-transformers"
        )


class CaseRetriever:
    """Retrieve similar training cases for few-shot grounding."""

    def __init__(
        self,
        index_path: str | Path,
        metadata_path: str | Path,
    ) -> None:
        _check_faiss()
        import faiss  # noqa: WPS433

        self._index_path = Path(index_path)
        self._metadata_path = Path(metadata_path)

        if not self._index_path.exists():
            raise FileNotFoundError(f"FAISS index not found: {self._index_path}")
        if not self._metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {self._metadata_path}")

        logger.info("Loading FAISS index from %s", self._index_path)
        self._index: Any = faiss.read_index(str(self._index_path))

        with open(self._metadata_path, encoding="utf-8") as f:
            self._metadata: list[dict[str, Any]] = json.load(f)

        if self._index.ntotal != len(self._metadata):
            raise ValueError(
                f"Index/metadata size mismatch: {self._index.ntotal} vectors vs "
                f"{len(self._metadata)} metadata entries"
            )
        logger.info("CaseRetriever ready: %d cases indexed", self._index.ntotal)

        self._encoder: Any | None = None

    def _get_encoder(self) -> Any:
        """Lazy-load the BGE-M3 sentence-transformer encoder."""
        if self._encoder is None:
            _check_sentence_transformers()
            from sentence_transformers import SentenceTransformer

            logger.info("Loading BGE-M3 encoder (first call)...")
            self._encoder = SentenceTransformer("BAAI/bge-m3", device="cpu")
            logger.info("BGE-M3 encoder loaded.")
        return self._encoder

    def retrieve(
        self,
        transcript: str,
        top_k: int = 5,
        encoder: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Find top-k most similar training cases."""
        if not transcript:
            return []

        enc = encoder if encoder is not None else self._get_encoder()
        query_vec = enc.encode(
            [transcript],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        query_vec = np.asarray(query_vec, dtype=np.float32)
        if query_vec.ndim == 1:
            query_vec = query_vec.reshape(1, -1)

        k = min(top_k, self._index.ntotal)
        scores, indices = self._index.search(query_vec, k)

        results: list[dict[str, Any]] = []
        for rank in range(k):
            idx = int(indices[0][rank])
            if idx < 0:
                continue
            meta = self._metadata[idx]
            results.append(
                {
                    "similarity": float(scores[0][rank]),
                    "case_id": meta.get("case_id", ""),
                    "diagnosis_codes": meta.get("gold_diagnoses", []),
                    "diagnosis_names": meta.get("diagnosis_names", []),
                    "transcript_preview": meta.get("transcript_preview", ""),
                }
            )
        return results

    def retrieve_balanced(
        self,
        transcript: str,
        candidate_codes: list[str],
        top_per_class: int = 1,
        encoder: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve nearest neighbor(s) per candidate class."""
        if not transcript or not candidate_codes:
            return []

        enc = encoder if encoder is not None else self._get_encoder()
        query_vec = enc.encode(
            [transcript],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        query_vec = np.asarray(query_vec, dtype=np.float32).reshape(1, -1)

        k_global = min(200, self._index.ntotal)
        scores, indices = self._index.search(query_vec, k_global)

        seen_parents: dict[str, int] = {}
        results: list[dict[str, Any]] = []
        target_parents = {code.split(".")[0] for code in candidate_codes}

        for rank in range(k_global):
            idx = int(indices[0][rank])
            if idx < 0:
                continue
            meta = self._metadata[idx]
            case_codes = meta.get("gold_diagnoses", [])
            case_parents = {c.split(".")[0] for c in case_codes}

            for parent in case_parents & target_parents:
                if seen_parents.get(parent, 0) >= top_per_class:
                    continue
                seen_parents[parent] = seen_parents.get(parent, 0) + 1
                results.append(
                    {
                        "similarity": float(scores[0][rank]),
                        "case_id": meta.get("case_id", ""),
                        "diagnosis_codes": case_codes,
                        "diagnosis_names": meta.get("diagnosis_names", []),
                        "transcript_preview": meta.get("transcript_preview", ""),
                        "key_evidence": meta.get("key_evidence", []),
                        "matched_class": parent,
                    }
                )

            if all(seen_parents.get(p, 0) >= top_per_class for p in target_parents):
                break

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results

    @property
    def size(self) -> int:
        """Number of indexed cases."""
        return self._index.ntotal
