# tests/test_lingxidiag16k.py
"""Tests for LingxiDiag-16K dataset adapter."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from culturedx.data.adapters.lingxidiag16k import LingxiDiag16kAdapter
from culturedx.core.models import Turn


FIXTURES = Path(__file__).parent / "fixtures"


class TestDialogueParsing:
    """Test the _parse_dialogue method."""

    def test_basic_dialogue(self):
        text = "医生：你好，最近怎么样？\n患者：不太好，一直失眠。"
        turns = LingxiDiag16kAdapter._parse_dialogue(text)
        assert len(turns) == 2
        assert turns[0].speaker == "doctor"
        assert turns[0].turn_id == 0
        assert "你好" in turns[0].text
        assert turns[1].speaker == "patient"
        assert turns[1].turn_id == 1
        assert "失眠" in turns[1].text

    def test_multi_turn_dialogue(self):
        text = (
            "医生：第一个问题\n"
            "患者：第一个回答\n"
            "医生：第二个问题\n"
            "患者：第二个回答"
        )
        turns = LingxiDiag16kAdapter._parse_dialogue(text)
        assert len(turns) == 4
        assert [t.speaker for t in turns] == [
            "doctor", "patient", "doctor", "patient"
        ]
        assert [t.turn_id for t in turns] == [0, 1, 2, 3]

    def test_empty_text(self):
        turns = LingxiDiag16kAdapter._parse_dialogue("")
        assert turns == []

    def test_no_speaker_prefix(self):
        turns = LingxiDiag16kAdapter._parse_dialogue("just some text without speakers")
        assert turns == []


class TestRowToCase:
    """Test _row_to_case conversion."""

    def test_single_diagnosis(self):
        adapter = LingxiDiag16kAdapter(data_path="/tmp")
        row = {
            "patient_id": "12345",
            "cleaned_text": "医生：你好\n患者：不好",
            "DiagnosisCode": "F32.900",
            "Diagnosis": "抑郁发作",
            "icd_clf_label": ["F32"],
            "four_class_label": "Depression",
            "Age": "28",
            "Gender": "女",
            "ChiefComplaint": "情绪低落",
        }
        case = adapter._row_to_case(row)
        assert case is not None
        assert case.case_id == "12345"
        assert case.language == "zh"
        assert case.dataset == "lingxidiag16k"
        assert case.diagnoses == ["F32"]
        assert case.comorbid is False
        assert case.metadata["diagnosis_code_full"] == "F32.900"

    def test_comorbid_diagnosis(self):
        adapter = LingxiDiag16kAdapter(data_path="/tmp")
        row = {
            "patient_id": "12346",
            "cleaned_text": "医生：你好\n患者：不好",
            "DiagnosisCode": "F32.900,F41.100",
            "Diagnosis": "抑郁焦虑共病",
            "icd_clf_label": ["F32", "F41"],
            "four_class_label": "Mixed",
        }
        case = adapter._row_to_case(row)
        assert case is not None
        assert case.diagnoses == ["F32", "F41"]
        assert case.comorbid is True

    def test_empty_text_returns_none(self):
        adapter = LingxiDiag16kAdapter(data_path="/tmp")
        row = {"patient_id": "999", "cleaned_text": ""}
        case = adapter._row_to_case(row)
        assert case is None

    def test_fallback_to_full_codes(self):
        """When icd_clf_label is empty, fall back to DiagnosisCode."""
        adapter = LingxiDiag16kAdapter(data_path="/tmp")
        row = {
            "patient_id": "12347",
            "cleaned_text": "医生：你好\n患者：不好",
            "DiagnosisCode": "F32.900",
            "Diagnosis": "抑郁发作",
            "icd_clf_label": [],
        }
        case = adapter._row_to_case(row)
        assert case is not None
        assert case.diagnoses == ["F32.900"]


class TestPatientTurnDetection:
    """Verify patient turn detection works with Chinese speaker labels."""

    def test_patient_turns(self):
        adapter = LingxiDiag16kAdapter(data_path="/tmp")
        row = {
            "patient_id": "test",
            "cleaned_text": "医生：问题\n患者：回答\n医生：问题2\n患者：回答2",
            "DiagnosisCode": "F32.900",
            "icd_clf_label": ["F32"],
        }
        case = adapter._row_to_case(row)
        assert case is not None
        patient_turns = case.patient_turns()
        assert len(patient_turns) == 2
        assert all(t.speaker == "patient" for t in patient_turns)


class TestLogicalSplits:
    """Tests for the v2.5 logical splits (rag_pool / dev_hpo / test_final)."""

    def test_placeholder_manifest_raises_clear_error(self, tmp_path, monkeypatch):
        """If the split yaml is still a placeholder, loading rag_pool or
        dev_hpo must raise a clear RuntimeError pointing at generate_splits.py."""
        # Build a fake repo layout that has only a placeholder manifest
        configs = tmp_path / "configs" / "splits"
        configs.mkdir(parents=True)
        (configs / "lingxidiag16k_v2_5.yaml").write_text(
            "version: v2.5\n"
            "status: PLACEHOLDER\n"
            "splits:\n"
            "  dev_hpo: {n_cases: 0, case_ids: []}\n"
            "  rag_pool: {n_cases: 0, case_ids: []}\n"
            "  test_final: {n_cases: 0, case_ids: []}\n",
            encoding="utf-8",
        )

        # Move the adapter module's __file__ view so _load_split_ids finds
        # our temp manifest instead of the repo one.
        from culturedx.data.adapters import lingxidiag16k as mod
        fake_mod_path = tmp_path / "src" / "culturedx" / "data" / "adapters" / "dummy.py"
        fake_mod_path.parent.mkdir(parents=True)
        fake_mod_path.touch()
        monkeypatch.setattr(mod, "__file__", str(fake_mod_path))

        with pytest.raises(RuntimeError, match="placeholder"):
            mod._load_split_ids("dev_hpo")

    def test_missing_manifest_raises(self, tmp_path, monkeypatch):
        """If the manifest doesn't exist at all, raise FileNotFoundError."""
        from culturedx.data.adapters import lingxidiag16k as mod
        # Point __file__ at a location with no ancestors containing configs/splits
        fake = tmp_path / "isolated" / "dummy.py"
        fake.parent.mkdir(parents=True)
        fake.touch()
        monkeypatch.setattr(mod, "__file__", str(fake))

        with pytest.raises(FileNotFoundError, match="generate_splits"):
            mod._load_split_ids("dev_hpo")

    def test_test_final_alias_uses_validation_parquet(self, tmp_path):
        """test_final must route to the native validation parquet.

        Without real parquet in the temp dir, the adapter should raise
        FileNotFoundError mentioning `validation`.
        """
        pytest.importorskip("pyarrow")
        adapter = LingxiDiag16kAdapter(data_path=str(tmp_path))
        with pytest.raises(FileNotFoundError, match="validation"):
            adapter.load(split="test_final")
