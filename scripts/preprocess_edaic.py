#!/usr/bin/env python3
"""Preprocess raw E-DAIC data into the JSON format expected by EDAICAdapter.

Reads per-participant tar.gz archives (transcripts) and PHQ-8 label CSVs,
then writes a single JSON array to disk.

Usage:
    uv run python scripts/preprocess_edaic.py \
        --raw-dir data/raw/daic_explain/edaic_download \
        --output  data/raw/daic_explain/edaic_processed.json
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import tarfile
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Mapping from Detailed_PHQ8_Labels.csv column names to short keys used
# in the adapter's ``phq8`` dict.
PHQ8_COLUMNS: list[tuple[str, str]] = [
    ("PHQ_8NoInterest", "no_interest"),
    ("PHQ_8Depressed", "depressed"),
    ("PHQ_8Sleep", "sleep"),
    ("PHQ_8Tired", "tired"),
    ("PHQ_8Appetite", "appetite"),
    ("PHQ_8Failure", "failure"),
    ("PHQ_8Concentrating", "concentrating"),
    ("PHQ_8Moving", "moving"),
]


def load_phq8_labels(labels_dir: Path) -> dict[int, dict]:
    """Return ``{participant_id: {"phq8": {...}, "phq8_total": int}}``."""
    phq8_path = labels_dir / "Detailed_PHQ8_Labels.csv"
    if not phq8_path.exists():
        raise FileNotFoundError(f"PHQ-8 label file not found: {phq8_path}")

    labels: dict[int, dict] = {}
    with open(phq8_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pid = int(row["Participant_ID"])
            phq8_items: dict[str, int] = {}
            for col, key in PHQ8_COLUMNS:
                phq8_items[key] = int(row[col])
            labels[pid] = {
                "phq8": phq8_items,
                "phq8_total": int(row["PHQ_8Total"]),
            }
    logger.info("Loaded PHQ-8 labels for %d participants.", len(labels))
    return labels


def extract_transcript(tar_path: Path) -> list[dict[str, str]]:
    """Extract transcript rows from a participant tar.gz.

    Streams through the archive and stops as soon as the transcript
    CSV is found, avoiding decompression of large audio/feature files.

    Returns a list of ``{"start": str, "end": str, "text": str}`` dicts.
    """
    pid_str = tar_path.name.replace("_P.tar.gz", "")
    transcript_name = f"{pid_str}_P/{pid_str}_Transcript.csv"

    rows: list[dict[str, str]] = []
    with tarfile.open(tar_path, "r:gz") as tar:
        for member in tar:
            if member.name == transcript_name:
                fobj = tar.extractfile(member)
                if fobj is None:
                    raise RuntimeError(
                        f"Cannot extract {transcript_name} from {tar_path}"
                    )
                text = fobj.read().decode("utf-8")
                reader = csv.DictReader(io.StringIO(text))
                for row in reader:
                    utterance = row["Text"].strip()
                    if utterance:
                        rows.append(
                            {
                                "start": row["Start_Time"],
                                "end": row["End_Time"],
                                "text": utterance,
                            }
                        )
                return rows
    raise KeyError(f"{transcript_name} not found in {tar_path}")


def build_dialogue(
    transcript_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Combine consecutive participant utterances into dialogue turns.

    Since all utterances are from the participant (no interviewer text),
    we merge consecutive rows into single turns separated by a gap
    threshold of 2 seconds to approximate natural pauses between responses.
    """
    if not transcript_rows:
        return []

    gap_threshold = 2.0  # seconds -- merge if gap < threshold
    turns: list[dict[str, str]] = []
    current_texts: list[str] = [transcript_rows[0]["text"]]
    current_end: float = float(transcript_rows[0]["end"])

    for row in transcript_rows[1:]:
        start = float(row["start"])
        if start - current_end < gap_threshold:
            # Continue the same turn.
            current_texts.append(row["text"])
        else:
            # Flush the accumulated turn.
            turns.append(
                {
                    "speaker": "participant",
                    "text": " ".join(current_texts),
                }
            )
            current_texts = [row["text"]]
        current_end = float(row["end"])

    # Flush last turn.
    turns.append(
        {"speaker": "participant", "text": " ".join(current_texts)}
    )
    return turns


def preprocess(raw_dir: Path, output: Path) -> list[dict]:
    """Run the full preprocessing pipeline and return the dataset list."""
    labels_dir = raw_dir / "labels"
    data_dir = raw_dir / "data"

    labels = load_phq8_labels(labels_dir)

    tar_files = sorted(data_dir.glob("*_P.tar.gz"))
    if not tar_files:
        raise FileNotFoundError(
            f"No tar.gz files found in {data_dir}"
        )
    logger.info("Found %d participant archives.", len(tar_files))

    dataset: list[dict] = []
    skipped_no_label = 0
    skipped_empty = 0

    for tar_path in tar_files:
        pid_str = tar_path.name.replace("_P.tar.gz", "")
        pid = int(pid_str)

        if pid not in labels:
            skipped_no_label += 1
            logger.debug("Skipping %s -- no PHQ-8 label.", pid_str)
            continue

        try:
            transcript_rows = extract_transcript(tar_path)
        except (KeyError, RuntimeError, EOFError, OSError) as exc:
            logger.warning(
                "Skipping %s -- transcript error: %s", pid_str, exc
            )
            continue

        dialogue = build_dialogue(transcript_rows)
        if not dialogue:
            skipped_empty += 1
            logger.debug("Skipping %s -- empty transcript.", pid_str)
            continue

        label = labels[pid]
        dataset.append(
            {
                "case_id": str(pid),
                "dialogue": dialogue,
                "phq8": label["phq8"],
                "phq8_total": label["phq8_total"],
            }
        )

    logger.info(
        "Processed %d cases "
        "(%d skipped: %d no label, %d empty transcript).",
        len(dataset),
        skipped_no_label + skipped_empty,
        skipped_no_label,
        skipped_empty,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    logger.info("Wrote %s (%d cases).", output, len(dataset))

    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preprocess raw E-DAIC data into adapter-ready JSON.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        required=True,
        help="Root of the raw E-DAIC download directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for the output JSON file.",
    )
    args = parser.parse_args()
    preprocess(args.raw_dir, args.output)


if __name__ == "__main__":
    main()
