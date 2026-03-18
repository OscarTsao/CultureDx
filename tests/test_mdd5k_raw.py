# tests/test_mdd5k_raw.py
"""Tests for MDD-5k raw file-per-patient adapter."""
import json
import pytest
from pathlib import Path

from culturedx.data.adapters.mdd5k import MDD5kRawAdapter


@pytest.fixture
def mdd5k_raw_dir(tmp_path):
    """Create a minimal MDD-5k repo structure."""
    mdd5k_dir = tmp_path / "MDD_5k"
    mdd5k_dir.mkdir()
    label_dir = tmp_path / "Label"
    label_dir.mkdir()

    # Patient 1: single diagnosis
    dialogue1 = [
        {
            "conversation": [
                {"doctor": "你好，最近怎么样？", "patient": "不太好，情绪一直很低落。"},
                {"doctor": "睡眠怎样？", "patient": "失眠严重，经常凌晨才睡着。"},
            ]
        }
    ]
    with open(mdd5k_dir / "patient_101.json", "w", encoding="utf-8") as f:
        json.dump(dialogue1, f, ensure_ascii=False)
    with open(label_dir / "patient_101_label.json", "w", encoding="utf-8") as f:
        json.dump({"ICD_Code": "F32.901", "Diagnosis_Result": "抑郁状态"}, f)

    # Patient 2: different diagnosis
    dialogue2 = [
        {
            "conversation": [
                {"doctor": "你来看什么问题？", "patient": "我总是很紧张焦虑，心跳加速。"},
            ]
        }
    ]
    with open(mdd5k_dir / "patient_102.json", "w", encoding="utf-8") as f:
        json.dump(dialogue2, f, ensure_ascii=False)
    with open(label_dir / "patient_102_label.json", "w", encoding="utf-8") as f:
        json.dump({"ICD_Code": "F41.100", "Diagnosis_Result": "广泛性焦虑障碍"}, f)

    # Patient 3: no label file
    dialogue3 = [
        {
            "conversation": [
                {"doctor": "你好", "patient": "你好"},
            ]
        }
    ]
    with open(mdd5k_dir / "patient_103.json", "w", encoding="utf-8") as f:
        json.dump(dialogue3, f, ensure_ascii=False)

    return tmp_path


class TestMDD5kRawAdapter:
    def test_load_cases(self, mdd5k_raw_dir):
        adapter = MDD5kRawAdapter(data_path=mdd5k_raw_dir)
        cases = adapter.load()
        assert len(cases) == 3

    def test_diagnosis_extraction(self, mdd5k_raw_dir):
        adapter = MDD5kRawAdapter(data_path=mdd5k_raw_dir)
        cases = adapter.load()
        # Cases are sorted by filename, so patient_101 first
        case_101 = next(c for c in cases if c.case_id == "patient_101")
        assert case_101.diagnoses == ["F32"]
        assert case_101.metadata["icd_code_full"] == "F32.901"
        assert case_101.metadata["diagnosis_text"] == "抑郁状态"

    def test_turn_structure(self, mdd5k_raw_dir):
        adapter = MDD5kRawAdapter(data_path=mdd5k_raw_dir)
        cases = adapter.load()
        case_101 = next(c for c in cases if c.case_id == "patient_101")
        assert len(case_101.transcript) == 4
        assert case_101.transcript[0].speaker == "doctor"
        assert case_101.transcript[1].speaker == "patient"
        assert case_101.transcript[0].turn_id == 0
        assert case_101.transcript[3].turn_id == 3

    def test_missing_label(self, mdd5k_raw_dir):
        adapter = MDD5kRawAdapter(data_path=mdd5k_raw_dir)
        cases = adapter.load()
        case_103 = next(c for c in cases if c.case_id == "patient_103")
        assert case_103.diagnoses == []

    def test_language_and_dataset(self, mdd5k_raw_dir):
        adapter = MDD5kRawAdapter(data_path=mdd5k_raw_dir)
        cases = adapter.load()
        for case in cases:
            assert case.language == "zh"
            assert case.dataset == "mdd5k"
            assert case.coding_system == "icd10"

    def test_patient_turns(self, mdd5k_raw_dir):
        adapter = MDD5kRawAdapter(data_path=mdd5k_raw_dir)
        cases = adapter.load()
        case_101 = next(c for c in cases if c.case_id == "patient_101")
        patient_turns = case_101.patient_turns()
        assert len(patient_turns) == 2
        assert all(t.speaker == "patient" for t in patient_turns)

    def test_missing_dir_raises(self, tmp_path):
        adapter = MDD5kRawAdapter(data_path=tmp_path)
        with pytest.raises(FileNotFoundError):
            adapter.load()
