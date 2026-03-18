# src/culturedx/data/adapters/mdd5k.py
"""MDD-5k dataset adapter."""
from __future__ import annotations

import json
from pathlib import Path

from culturedx.core.models import ClinicalCase, Turn
from culturedx.data.adapters.base import BaseDatasetAdapter


class MDD5kAdapter(BaseDatasetAdapter):
    """Adapter for MDD-5k: Chinese multi-disorder diagnostic dialogues."""

    def load(self, split: str | None = None) -> list[ClinicalCase]:
        with open(self.data_path, encoding="utf-8") as f:
            raw = json.load(f)

        cases = []
        for item in raw:
            turns = [
                Turn(
                    speaker=turn["speaker"],
                    text=turn["text"],
                    turn_id=i,
                )
                for i, turn in enumerate(item["dialogue"])
            ]
            diagnoses = item["diagnosis"]
            cases.append(
                ClinicalCase(
                    case_id=item["case_id"],
                    transcript=turns,
                    language="zh",
                    dataset="mdd5k",
                    transcript_format="dialogue",
                    coding_system="icd10",
                    diagnoses=diagnoses,
                    comorbid=len(diagnoses) > 1,
                    metadata={"diagnosis_text": item.get("diagnosis_text", "")},
                )
            )
        return cases
