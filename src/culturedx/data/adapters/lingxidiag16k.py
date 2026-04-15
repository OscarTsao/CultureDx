# src/culturedx/data/adapters/lingxidiag16k.py
"""LingxiDiag-16K dataset adapter."""
from __future__ import annotations

import re
from pathlib import Path

from culturedx.core.models import ClinicalCase, Turn
from culturedx.data.adapters.base import BaseDatasetAdapter


class LingxiDiag16kAdapter(BaseDatasetAdapter):
    """Adapter for LingxiDiag-16K: synthetic Chinese psychiatric dialogues.

    data_path should point to the directory containing the parquet data files
    (e.g., data/raw/lingxidiag16k/data/ or data/raw/lingxidiag16k/).
    """

    _SPEAKER_PATTERN = re.compile(r"^(医生|患者)：", re.MULTILINE)

    def load(self, split: str | None = None) -> list[ClinicalCase]:
        import pyarrow.parquet as pq

        data_dir = self.data_path
        if (data_dir / "data").is_dir():
            data_dir = data_dir / "data"

        if split is None:
            split = "validation"

        parquet_files = sorted(data_dir.glob(f"{split}-*.parquet"))
        if not parquet_files:
            raise FileNotFoundError(
                f"No parquet files found for split '{split}' in {data_dir}"
            )

        table = pq.read_table(parquet_files)
        cases = []
        for i in range(table.num_rows):
            row = {col: table.column(col)[i].as_py() for col in table.column_names}
            case = self._row_to_case(row)
            if case is not None:
                cases.append(case)
        return cases

    def _row_to_case(self, row: dict) -> ClinicalCase | None:
        """Convert a single parquet row to a ClinicalCase."""
        text = row.get("cleaned_text", "")
        if not text:
            return None

        transcript = self._parse_dialogue(text)
        if not transcript:
            return None

        # Parse ICD codes from DiagnosisCode (may be comma-separated)
        raw_code = row.get("DiagnosisCode", "")
        icd_codes = [c.strip() for c in re.split(r"[;,；，]", raw_code) if c.strip()]

        # Simplified labels (e.g., ["F41", "F32"])
        icd_labels = row.get("icd_clf_label", []) or []

        # Use icd_labels as diagnoses (parent codes), fall back to full codes
        diagnoses = icd_labels if icd_labels else icd_codes

        return ClinicalCase(
            case_id=str(row.get("patient_id", "")),
            transcript=transcript,
            language="zh",
            dataset="lingxidiag16k",
            transcript_format="dialogue",
            coding_system="icd10",
            diagnoses=diagnoses,
            comorbid=len(diagnoses) > 1,
            metadata={
                "diagnosis_text": row.get("Diagnosis", ""),
                "diagnosis_code_full": raw_code,
                "four_class_label": row.get("four_class_label"),
                "age": row.get("Age"),
                "gender": row.get("Gender"),
                "chief_complaint": row.get("ChiefComplaint"),
            },
        )

    @classmethod
    def _parse_dialogue(cls, text: str) -> list[Turn]:
        """Parse '医生：...\\n患者：...' format into Turn objects."""
        turns = []
        turn_id = 0
        # Split on speaker prefixes
        parts = cls._SPEAKER_PATTERN.split(text)
        # parts = ['', '医生', ' text...', '患者', ' text...', ...]
        # Skip empty first element
        i = 1
        while i < len(parts) - 1:
            speaker_zh = parts[i].strip()
            content = parts[i + 1].strip()
            if speaker_zh == "医生":
                speaker = "doctor"
            elif speaker_zh == "患者":
                speaker = "patient"
            else:
                i += 2
                continue
            if content:
                turns.append(Turn(speaker=speaker, text=content, turn_id=turn_id))
                turn_id += 1
            i += 2
        return turns
