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


class MDD5kRawAdapter(BaseDatasetAdapter):
    """Adapter for raw MDD-5k repo: file-per-patient JSON dialogues with ICD labels.

    data_path should point to the MDD-5k repo root containing MDD_5k/ and Label/ dirs.
    """

    def load(self, split: str | None = None) -> list[ClinicalCase]:
        dialogues_dir = self.data_path / "MDD_5k"
        labels_dir = self.data_path / "Label"

        if not dialogues_dir.is_dir():
            raise FileNotFoundError(f"MDD_5k directory not found at {dialogues_dir}")

        patient_files = sorted(dialogues_dir.glob("patient_*.json"))
        if not patient_files:
            raise FileNotFoundError(f"No patient files found in {dialogues_dir}")

        cases = []
        for pf in patient_files:
            patient_id = pf.stem  # "patient_1002"
            label_file = labels_dir / f"{patient_id}_label.json"

            # Load dialogue
            with open(pf, encoding="utf-8") as f:
                raw = json.load(f)

            # Parse turns from all conversation rounds
            turns = []
            turn_id = 0
            for entry in raw:
                for pair in entry.get("conversation", []):
                    doctor_text = pair.get("doctor", "").strip()
                    patient_text = pair.get("patient", "").strip()
                    if doctor_text:
                        turns.append(Turn(
                            speaker="doctor", text=doctor_text, turn_id=turn_id
                        ))
                        turn_id += 1
                    if patient_text:
                        turns.append(Turn(
                            speaker="patient", text=patient_text, turn_id=turn_id
                        ))
                        turn_id += 1

            if not turns:
                continue

            # Load label
            diagnoses = []
            diagnosis_text = ""
            icd_full = ""
            if label_file.exists():
                with open(label_file, encoding="utf-8") as f:
                    label = json.load(f)
                icd_full = label.get("ICD_Code", "")
                diagnosis_text = label.get("Diagnosis_Result", "")
                # Handle comma-separated codes: "F32.900,F41.101" -> ["F32", "F41"]
                if icd_full:
                    seen = set()
                    for code in icd_full.split(","):
                        parent = code.strip().split(".")[0]
                        if parent and parent not in seen:
                            seen.add(parent)
                            diagnoses.append(parent)

            cases.append(
                ClinicalCase(
                    case_id=patient_id,
                    transcript=turns,
                    language="zh",
                    dataset="mdd5k",
                    transcript_format="dialogue",
                    coding_system="icd10",
                    diagnoses=diagnoses,
                    comorbid=len(diagnoses) > 1,
                    metadata={
                        "diagnosis_text": diagnosis_text,
                        "icd_code_full": icd_full,
                    },
                )
            )
        return cases
