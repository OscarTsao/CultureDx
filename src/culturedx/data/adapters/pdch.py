# src/culturedx/data/adapters/pdch.py
"""PDCH dataset adapter."""
from __future__ import annotations

import json
from pathlib import Path

from culturedx.core.models import ClinicalCase, Turn
from culturedx.data.adapters.base import BaseDatasetAdapter


class PDCHAdapter(BaseDatasetAdapter):
    """Adapter for PDCH: Chinese depression consultations with HAMD-17."""

    def __init__(self, data_path: str | Path, binary_threshold: int = 8, **kwargs) -> None:
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
            total = item["hamd17_total"]
            binary = 1 if total >= self.binary_threshold else 0
            cases.append(
                ClinicalCase(
                    case_id=item["case_id"],
                    transcript=turns,
                    language="zh",
                    dataset="pdch",
                    transcript_format="dialogue",
                    coding_system="hamd17",
                    diagnoses=[],
                    severity={"hamd17": item["hamd17"], "hamd17_total": total},
                    metadata={"binary": binary},
                )
            )
        return cases
