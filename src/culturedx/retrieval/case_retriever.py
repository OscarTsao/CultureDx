"""Case retriever: find similar training cases for few-shot grounding.

Uses a pre-built FAISS index of BGE-M3 dense embeddings over the training
split.  At query time the caller's transcript is encoded, and the top-k
nearest neighbours are returned with diagnosis labels and a short preview.

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

# ---------------------------------------------------------------------------
# Lazy imports — fail gracefully when optional deps are missing
# ---------------------------------------------------------------------------

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
            "faiss is required for CaseRetriever. "
            "Install with: pip install faiss-cpu"
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class CaseRetriever:
    """Retrieve similar training cases for few-shot grounding.

    The retriever operates in two phases:

    1. **Offline** — ``scripts/build_case_index.py`` encodes every training
       transcript with BGE-M3, L2-normalises the vectors, and writes a FAISS
       ``IndexFlatIP`` plus a JSON metadata sidecar.
    2. **Online** — :meth:`retrieve` encodes the query transcript, searches
       the index, and returns the top-k results with diagnosis labels.

    Parameters
    ----------
    index_path : str | Path
        Path to the ``.faiss`` index file.
    metadata_path : str | Path
        Path to the JSON metadata sidecar.
    """

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
                f"Index/metadata size mismatch: "
                f"{self._index.ntotal} vectors vs {len(self._metadata)} metadata entries"
            )
        logger.info(
            "CaseRetriever ready: %d cases indexed", self._index.ntotal,
        )

        # Encoder is lazy-loaded on first retrieve() call without an encoder
        self._encoder: Any | None = None

        # Build class-to-indices mapping for balanced retrieval
        self._class_to_indices: dict[str, list[int]] = {}
        for i, meta in enumerate(self._metadata):
            for code in meta.get("gold_diagnoses", []):
                parent = code.split(".")[0]
                self._class_to_indices.setdefault(parent, []).append(i)

    # ------------------------------------------------------------------
    # Encoder management
    # ------------------------------------------------------------------

    def _get_encoder(self) -> Any:
        """Lazy-load the BGE-M3 sentence-transformer encoder."""
        if self._encoder is None:
            _check_sentence_transformers()
            from sentence_transformers import SentenceTransformer

            logger.info("Loading BGE-M3 encoder (first call)...")
            self._encoder = SentenceTransformer("BAAI/bge-m3", device="cpu")
            logger.info("BGE-M3 encoder loaded.")
        return self._encoder

    # ------------------------------------------------------------------
    # Public retrieval API
    # ------------------------------------------------------------------

    def retrieve(
        self,
        transcript: str,
        top_k: int = 5,
        encoder: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Find top-k most similar training cases.

        Parameters
        ----------
        transcript : str
            The query clinical transcript (full text).
        top_k : int
            Number of neighbours to return (default 5).
        encoder : optional
            A ``SentenceTransformer``-compatible encoder.  If *None*, the
            built-in BGE-M3 encoder is lazy-loaded on first call.

        Returns
        -------
        list[dict]
            Each dict contains:
            - ``similarity`` (float): cosine similarity score.
            - ``case_id`` (str): training case identifier.
            - ``diagnosis_codes`` (list[str]): gold ICD-10 codes.
            - ``diagnosis_names`` (list[str]): human-readable names.
            - ``transcript_preview`` (str): first ~100 chars of transcript.
        """
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
                # FAISS returns -1 for unfilled slots
                continue
            meta = self._metadata[idx]
            results.append({
                "similarity": float(scores[0][rank]),
                "case_id": meta.get("case_id", ""),
                "diagnosis_codes": meta.get("gold_diagnoses", []),
                "diagnosis_names": meta.get("diagnosis_names", []),
                "transcript_preview": meta.get("transcript_preview", ""),
            })
        return results

    def retrieve_balanced(
        self,
        transcript: str,
        candidate_codes: list[str],
        top_per_class: int = 1,
        encoder: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve nearest neighbor(s) per candidate class.

        Instead of global top-k (which lets F32 dominate), this retrieves
        the best-matching training case for each candidate disorder class.

        Parameters
        ----------
        transcript : str
            The query clinical transcript.
        candidate_codes : list[str]
            Candidate ICD-10 codes (e.g. ["F32", "F41.1", "F51"]).
        top_per_class : int
            Number of neighbours per class (default 1).
        encoder : optional
            External encoder; lazy-loads BGE-M3 if None.

        Returns
        -------
        list[dict]
            One result per class found, sorted by similarity descending.
        """
        if not transcript or not candidate_codes:
            return []

        enc = encoder if encoder is not None else self._get_encoder()
        query_vec = enc.encode(
            [transcript],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        query_vec = np.asarray(query_vec, dtype=np.float32).reshape(1, -1)

        # Global search with generous k, then filter per class
        k_global = min(200, self._index.ntotal)
        scores, indices = self._index.search(query_vec, k_global)

        # Collect best match(es) per parent code
        seen_parents: dict[str, int] = {}  # parent -> count
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
                names = meta.get("diagnosis_names", [])
                results.append({
                    "similarity": float(scores[0][rank]),
                    "case_id": meta.get("case_id", ""),
                    "diagnosis_codes": case_codes,
                    "diagnosis_names": names,
                    "transcript_preview": meta.get("transcript_preview", ""),
                    "key_evidence": meta.get("key_evidence", []),
                    "matched_class": parent,
                })

            # Stop early if all classes covered
            if all(seen_parents.get(p, 0) >= top_per_class for p in target_parents):
                break

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results

    def retrieve_batch(
        self,
        transcripts: list[str],
        top_k: int = 5,
        encoder: Any | None = None,
    ) -> list[list[dict[str, Any]]]:
        """Batch retrieve for multiple query transcripts.

        Parameters
        ----------
        transcripts : list[str]
            A list of clinical transcripts.
        top_k : int
            Number of neighbours per query.
        encoder : optional
            Shared encoder instance (avoids reloading per call).

        Returns
        -------
        list[list[dict]]
            One result list per query.
        """
        if not transcripts:
            return []

        enc = encoder if encoder is not None else self._get_encoder()
        query_vecs = enc.encode(
            transcripts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=32,
        )
        query_vecs = np.asarray(query_vecs, dtype=np.float32)
        if query_vecs.ndim == 1:
            query_vecs = query_vecs.reshape(1, -1)

        k = min(top_k, self._index.ntotal)
        scores, indices = self._index.search(query_vecs, k)

        all_results: list[list[dict[str, Any]]] = []
        for qi in range(len(transcripts)):
            results: list[dict[str, Any]] = []
            for rank in range(k):
                idx = int(indices[qi][rank])
                if idx < 0:
                    continue
                meta = self._metadata[idx]
                results.append({
                    "similarity": float(scores[qi][rank]),
                    "case_id": meta.get("case_id", ""),
                    "diagnosis_codes": meta.get("gold_diagnoses", []),
                    "diagnosis_names": meta.get("diagnosis_names", []),
                    "transcript_preview": meta.get("transcript_preview", ""),
                })
            all_results.append(results)
        return all_results

    @property
    def size(self) -> int:
        """Number of cases in the index."""
        return self._index.ntotal
