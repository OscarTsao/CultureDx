#!/usr/bin/env python3
"""Fit a learned diagnosis calibrator artifact from JSONL feature rows.

Expected input schema per row:
{
  "label": 0 | 1,
  "features": {
    "avg_confidence": 0.82,
    "threshold_ratio": 1.0,
    ...
  },
  "metadata": {... optional ...}
}

The script is intentionally generic: it does not assume a specific dataset or
private artifact format. Missing features default to 0.0.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.diagnosis.calibrator import ConfidenceCalibrator


def load_rows(paths: list[Path], features_field: str, label_field: str) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            if path.suffix.lower() == ".json":
                data = json.load(f)
                iterable = data if isinstance(data, list) else data.get("rows", [])
            else:
                iterable = (json.loads(line) for line in f if line.strip())

            for item in iterable:
                features = dict(item.get(features_field, {}))
                if not features:
                    continue
                label = item.get(label_field)
                if label is None:
                    continue
                rows.append({
                    "features": features,
                    "label": int(bool(label)),
                    "metadata": item.get("metadata", {}),
                })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", "-i", action="append", required=True, type=Path)
    parser.add_argument("--output", "-o", required=True, type=Path)
    parser.add_argument("--feature-names", default="", help="Comma-separated feature order override")
    parser.add_argument("--abstain-threshold", type=float, default=0.3)
    parser.add_argument("--comorbid-threshold", type=float, default=0.5)
    parser.add_argument("--features-field", default="features")
    parser.add_argument("--label-field", default="label")
    args = parser.parse_args()

    rows = load_rows(args.input, args.features_field, args.label_field)
    if len(rows) < 2:
        raise SystemExit("Need at least two labeled rows to fit a calibrator artifact.")

    feature_names = [f.strip() for f in args.feature_names.split(",") if f.strip()] or None
    examples = [row["features"] for row in rows]
    labels = [row["label"] for row in rows]

    artifact = ConfidenceCalibrator.fit_linear_artifact(
        examples=examples,
        labels=labels,
        feature_names=feature_names,
        abstain_threshold=args.abstain_threshold,
        comorbid_threshold=args.comorbid_threshold,
        metadata={
            "source_files": [str(p) for p in args.input],
            "n_rows": len(rows),
            "label_field": args.label_field,
            "features_field": args.features_field,
        },
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    artifact.save(args.output)
    print(f"Saved calibrator artifact to {args.output}")


if __name__ == "__main__":
    main()
