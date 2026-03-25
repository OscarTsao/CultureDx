# src/culturedx/data/adapters/edaic.py
"""E-DAIC dataset adapter."""
from __future__ import annotations

import json
from pathlib import Path

from culturedx.core.models import ClinicalCase, ScaleScore, Turn
from culturedx.data.adapters.base import BaseDatasetAdapter


class EDAICAdapter(BaseDatasetAdapter):
    """Adapter for E-DAIC: English depression interviews with PHQ-8."""

    def __init__(self, data_path: str | Path, binary_threshold: int = 10, **kwargs) -> None:
        super().__init__(data_path, **kwargs)
        self.binary_threshold = binary_threshold

    def load(self, split: str | None = None) -> list[ClinicalCase]:
        with open(self.data_path, encoding="utf-8") as f:
            raw = json.load(f)

        cases = []
        for item in raw:
            turns = [
                Turn(speaker=turn["speaker"], text=turn["text"], turn_id=i)
                for i, turn in enumerate(item["dialogue"])
            ]
            total = item["phq8_total"]
            binary = 1 if total >= self.binary_threshold else 0
            phq8_items = item["phq8"] if isinstance(item["phq8"], list) else None
            cases.append(
                ClinicalCase(
                    case_id=item["case_id"],
                    transcript=turns,
                    language="en",
                    dataset="edaic",
                    transcript_format="dialogue",
                    coding_system="dsm5",
                    diagnoses=["F32"] if binary else [],
                    severity={"phq8": item["phq8"], "phq8_total": total},
                    metadata={"binary": binary},
                    scale_scores=[ScaleScore(name="phq8", total=total, items=phq8_items)],
                )
            )
        return cases
