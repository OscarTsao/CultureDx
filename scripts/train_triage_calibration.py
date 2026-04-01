#!/usr/bin/env python3
"""Fit a simple triage calibration artifact from JSONL routing data.

Expected input schema per line:
{
  "example_id": "case-001",
  "gold_categories": ["mood", "anxiety"],
  "raw_category_scores": {"mood": 0.91, "anxiety": 0.33, "sleep": 0.12}
}

The loader also accepts:
  - `gold_labels` or `labels` instead of `gold_categories`
  - `scores` instead of `raw_category_scores`
  - `categories` as a list of `{category, confidence}` or `{category, raw_score}`

Usage:
    uv run python scripts/train_triage_calibration.py \
        --input data/triage_calibration/train.jsonl \
        --output outputs/triage_calibration/artifact.json \
        --metrics-output outputs/triage_calibration/metrics.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.agents.triage_routing import (  # noqa: E402
    TriageCalibrationExample,
    evaluate_triage_calibration,
    fit_temperature_scaling,
)


def _load_examples(path: Path) -> list[TriageCalibrationExample]:
    examples: list[TriageCalibrationExample] = []
    with open(path, encoding="utf-8") as f:
        for line_idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            example_id = str(payload.get("example_id") or payload.get("case_id") or f"row-{line_idx}")
            gold = payload.get("gold_categories") or payload.get("gold_labels") or payload.get("labels") or []
            raw_scores = payload.get("raw_category_scores") or payload.get("scores")
            if raw_scores is None and isinstance(payload.get("categories"), list):
                raw_scores = {}
                for item in payload["categories"]:
                    if not isinstance(item, dict):
                        continue
                    category = str(item.get("category", "")).strip()
                    if not category:
                        continue
                    raw_scores[category] = float(item.get("confidence", item.get("raw_score", 0.0)))
            if not isinstance(raw_scores, dict) or not gold:
                continue
            examples.append(
                TriageCalibrationExample(
                    example_id=example_id,
                    gold_categories=[str(item) for item in gold],
                    raw_category_scores={
                        str(category): float(score)
                        for category, score in raw_scores.items()
                    },
                )
            )
    return examples


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="JSONL calibration dataset")
    parser.add_argument("--output", required=True, type=Path, help="Artifact output path")
    parser.add_argument(
        "--metrics-output",
        type=Path,
        default=None,
        help="Optional JSON metrics output path",
    )
    args = parser.parse_args()

    examples = _load_examples(args.input)
    if not examples:
        raise SystemExit(f"No valid calibration examples found in {args.input}")

    artifact = fit_temperature_scaling(examples)
    metrics = evaluate_triage_calibration(examples, artifact)
    artifact.validation_metrics = metrics
    artifact.metadata.update(
        {
            "source_input": str(args.input),
            "num_examples": len(examples),
        }
    )
    artifact.save(args.output)
    print(f"Saved triage calibration artifact to {args.output}")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))

    if args.metrics_output is not None:
        args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.metrics_output, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        print(f"Saved metrics to {args.metrics_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
