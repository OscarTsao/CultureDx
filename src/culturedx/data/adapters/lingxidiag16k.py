# src/culturedx/data/adapters/lingxidiag16k.py
"""LingxiDiag-16K dataset adapter.

Supports the v2.5 eval discipline (three logical splits):
    - "rag_pool"   : ~14k from train, minus dev_hpo. Used for TF-IDF training,
                     FAISS RAG index, SFT checker training.
    - "dev_hpo"    : 1k stratified from train. Used for HPO, stacker training,
                     prompt iteration.
    - "test_final" : 1k (the native `validation-*.parquet`). Used for paper
                     numbers; touched once per ablation at submission.

Also still supports the legacy physical splits:
    - "train"      : entire train parquet (~15k). Only useful for sanity checks;
                     downstream code should prefer the logical splits.
    - "validation" : alias for "test_final".

The logical splits are loaded via a committed case-id manifest at
configs/splits/lingxidiag16k_v2_5.yaml. If that file is a placeholder
(unpopulated), a clear error is raised pointing the user at
scripts/generate_splits.py.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from culturedx.core.models import ClinicalCase, Turn
from culturedx.data.adapters.base import BaseDatasetAdapter

logger = logging.getLogger(__name__)

_LOGICAL_SPLITS = {"rag_pool", "dev_hpo", "test_final"}


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
            split = "train"

        # Logical split: resolve via manifest + filter the physical parquet
        if split in _LOGICAL_SPLITS:
            return self._load_logical(data_dir, split)

        # Legacy alias: test_final == validation physical split
        physical = split

        parquet_files = sorted(data_dir.glob(f"{physical}-*.parquet"))
        if not parquet_files:
            raise FileNotFoundError(
                f"No parquet files found for split '{physical}' in {data_dir}"
            )

        table = pq.read_table(parquet_files)
        cases = []
        for i in range(table.num_rows):
            row = {col: table.column(col)[i].as_py() for col in table.column_names}
            case = self._row_to_case(row)
            if case is not None:
                cases.append(case)
        return cases

    def _load_logical(self, data_dir: Path, split: str) -> list[ClinicalCase]:
        """Load a logical split (rag_pool / dev_hpo / test_final)."""
        import pyarrow.parquet as pq

        # test_final is just the native validation parquet
        if split == "test_final":
            parquet_files = sorted(data_dir.glob("validation-*.parquet"))
            if not parquet_files:
                raise FileNotFoundError(
                    f"No validation-*.parquet in {data_dir}. test_final is an "
                    f"alias for the LingxiDiag-16K validation split."
                )
            table = pq.read_table(parquet_files)
            cases = []
            for i in range(table.num_rows):
                row = {col: table.column(col)[i].as_py() for col in table.column_names}
                case = self._row_to_case(row)
                if case is not None:
                    cases.append(case)
            logger.info("Loaded logical split '%s': %d cases", split, len(cases))
            return cases

        # rag_pool / dev_hpo: load train, then filter by case_id manifest
        ids = _load_split_ids(split)

        parquet_files = sorted(data_dir.glob("train-*.parquet"))
        if not parquet_files:
            raise FileNotFoundError(
                f"No train-*.parquet in {data_dir}; required for '{split}'."
            )
        table = pq.read_table(parquet_files)

        id_set = {str(x) for x in ids}
        cases = []
        matched_ids = set()
        for i in range(table.num_rows):
            row = {col: table.column(col)[i].as_py() for col in table.column_names}
            case_id = str(row.get("patient_id", ""))
            if case_id not in id_set:
                continue
            case = self._row_to_case(row)
            if case is not None:
                cases.append(case)
                matched_ids.add(case_id)

        if len(matched_ids) != len(id_set):
            missing = id_set - matched_ids
            logger.warning(
                "Logical split '%s' manifest lists %d ids; parquet matched %d. "
                "%d ids unmatched (first 5: %s). "
                "Regenerate split yaml with scripts/generate_splits.py --force "
                "if the parquet changed.",
                split, len(id_set), len(matched_ids), len(missing),
                list(missing)[:5],
            )

        logger.info("Loaded logical split '%s': %d cases", split, len(cases))
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
        icd_codes = [c.strip() for c in raw_code.split(",") if c.strip()]

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
        turns: list[Turn] = []
        turn_id = 0
        parts = cls._SPEAKER_PATTERN.split(text)
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


# --------------------------------------------------------------------------- #
# Split manifest loading
# --------------------------------------------------------------------------- #
def _load_split_ids(split_name: str) -> list[str]:
    """Load case ids for rag_pool or dev_hpo from the committed manifest."""
    import yaml

    # Locate the manifest relative to this module. We search upward so it
    # works regardless of CWD.
    here = Path(__file__).resolve()
    manifest_path: Path | None = None
    for parent in here.parents:
        candidate = parent / "configs" / "splits" / "lingxidiag16k_v2_5.yaml"
        if candidate.exists():
            manifest_path = candidate
            break
    if manifest_path is None:
        raise FileNotFoundError(
            "configs/splits/lingxidiag16k_v2_5.yaml not found anywhere up the "
            "tree. Run scripts/generate_splits.py first."
        )

    with manifest_path.open(encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    if manifest.get("status") == "PLACEHOLDER":
        raise RuntimeError(
            f"{manifest_path} is a placeholder. Populate it by running:\n"
            f"    uv run python scripts/generate_splits.py --force\n"
            f"(requires LingxiDiag-16K parquet under data/raw/lingxidiag16k/)"
        )

    splits = manifest.get("splits") or {}
    if split_name not in splits:
        raise ValueError(
            f"Split '{split_name}' not in manifest. Available: {list(splits)}"
        )
    case_ids = splits[split_name].get("case_ids") or []
    if not case_ids:
        raise RuntimeError(
            f"Split '{split_name}' in {manifest_path} has no case_ids. "
            f"Regenerate with scripts/generate_splits.py --force."
        )
    return [str(x) for x in case_ids]
