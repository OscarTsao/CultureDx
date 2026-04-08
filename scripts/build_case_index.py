#!/usr/bin/env python
"""Build a FAISS case index from LingxiDiag-16K training split.

Usage
-----
    python scripts/build_case_index.py \
        --data-path data/raw/lingxidiag16k \
        --output-dir data/cache

Outputs
-------
    <output-dir>/train_case_index.faiss   -- FAISS IndexFlatIP (cosine)
    <output-dir>/train_case_metadata.json  -- per-vector metadata sidecar
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_transcript_text(case) -> str:
    """Flatten ClinicalCase.transcript (list[Turn]) into plain text."""
    lines = []
    for turn in case.transcript:
        speaker = turn.speaker.capitalize()
        lines.append(f"{speaker}: {turn.text}")
    return "\n".join(lines)


def _diagnosis_names(codes: list[str]) -> list[str]:
    """Map ICD-10 codes to human-readable names via the ontology module."""
    try:
        from culturedx.ontology.icd10 import get_disorder_name
    except ImportError:
        return codes  # fallback: just return codes

    names = []
    for code in codes:
        name = get_disorder_name(code, language="zh")
        if name is None:
            name = get_disorder_name(code, language="en")
        names.append(name or code)
    return names


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build FAISS case index from LingxiDiag-16K train split.",
    )
    parser.add_argument(
        "--data-path",
        type=str,
        required=True,
        help="Path to LingxiDiag-16K data directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/cache",
        help="Directory for output files (default: data/cache).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Encoding batch size (default: 32).",
    )
    parser.add_argument(
        "--model-id",
        type=str,
        default="BAAI/bge-m3",
        help="SentenceTransformer model ID (default: BAAI/bge-m3).",
    )
    args = parser.parse_args()

    data_path = Path(args.data_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    index_path = output_dir / "train_case_index.faiss"
    meta_path = output_dir / "train_case_metadata.json"

    # ------------------------------------------------------------------
    # 1. Load training data
    # ------------------------------------------------------------------
    logger.info("Loading LingxiDiag-16K train split from %s ...", data_path)
    from culturedx.data.adapters.lingxidiag16k import LingxiDiag16kAdapter

    adapter = LingxiDiag16kAdapter(data_path)
    cases = adapter.load(split="train")
    logger.info("Loaded %d training cases.", len(cases))

    if not cases:
        logger.error("No cases found — aborting.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 2. Prepare texts and metadata
    # ------------------------------------------------------------------
    logger.info("Preparing transcripts and metadata ...")
    transcripts: list[str] = []
    metadata: list[dict] = []

    for case in cases:
        text = _build_transcript_text(case)
        if not text:
            continue
        transcripts.append(text)
        metadata.append({
            "case_id": case.case_id,
            "gold_diagnoses": case.diagnoses,
            "diagnosis_names": _diagnosis_names(case.diagnoses),
            "transcript_preview": text[:100],
        })

    logger.info(
        "Prepared %d transcripts (%d skipped — empty).",
        len(transcripts),
        len(cases) - len(transcripts),
    )

    # ------------------------------------------------------------------
    # 3. Encode with BGE-M3
    # ------------------------------------------------------------------
    logger.info("Loading encoder: %s ...", args.model_id)
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.error(
            "sentence-transformers is required. "
            "Install with: pip install sentence-transformers"
        )
        sys.exit(1)

    encoder = SentenceTransformer(args.model_id)

    logger.info(
        "Encoding %d transcripts (batch_size=%d) ...",
        len(transcripts),
        args.batch_size,
    )
    t0 = time.time()

    # Encode in batches with progress logging
    all_embeddings: list[np.ndarray] = []
    n_total = len(transcripts)
    for start in range(0, n_total, args.batch_size):
        end = min(start + args.batch_size, n_total)
        batch = transcripts[start:end]
        batch_vecs = encoder.encode(
            batch,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=args.batch_size,
        )
        all_embeddings.append(np.asarray(batch_vecs, dtype=np.float32))

        done = end
        if done % 100 < args.batch_size or done == n_total:
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            logger.info(
                "  encoded %d / %d  (%.1f cases/s)", done, n_total, rate,
            )

    embeddings = np.vstack(all_embeddings)
    elapsed = time.time() - t0
    logger.info(
        "Encoding complete: %d vectors, dim=%d, %.1fs total.",
        embeddings.shape[0],
        embeddings.shape[1],
        elapsed,
    )

    # ------------------------------------------------------------------
    # 4. Build FAISS index
    # ------------------------------------------------------------------
    logger.info("Building FAISS IndexFlatIP ...")
    try:
        import faiss
    except ImportError:
        logger.error(
            "faiss is required. Install with: pip install faiss-cpu"
        )
        sys.exit(1)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    logger.info("Index contains %d vectors.", index.ntotal)

    # ------------------------------------------------------------------
    # 5. Save
    # ------------------------------------------------------------------
    faiss.write_index(index, str(index_path))
    logger.info("Saved FAISS index to %s", index_path)

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=1)
    logger.info("Saved metadata to %s (%d entries)", meta_path, len(metadata))

    # Quick sanity check
    logger.info("--- Sanity check ---")
    query_vec = embeddings[:1]
    scores, indices = index.search(query_vec, 3)
    for rank in range(3):
        idx = int(indices[0][rank])
        meta = metadata[idx]
        logger.info(
            "  rank %d: score=%.4f  case=%s  dx=%s  preview=%s",
            rank + 1,
            float(scores[0][rank]),
            meta["case_id"],
            meta["gold_diagnoses"],
            meta["transcript_preview"][:60],
        )

    logger.info("Done.")


if __name__ == "__main__":
    main()
