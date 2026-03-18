# tests/test_adapters.py
"""Tests for dataset adapters."""
import pytest
from pathlib import Path
from culturedx.data.adapters.base import BaseDatasetAdapter
from culturedx.data.adapters.mdd5k import MDD5kAdapter
from culturedx.data.adapters.pdch import PDCHAdapter
from culturedx.data.adapters.edaic import EDAICAdapter


FIXTURES = Path(__file__).parent / "fixtures"


class TestMDD5kAdapter:
    def test_load_fixture(self):
        adapter = MDD5kAdapter(data_path=FIXTURES / "mdd5k_sample.json")
        cases = adapter.load()
        assert len(cases) == 3
        assert cases[0].language == "zh"
        assert cases[0].coding_system == "icd10"
        assert cases[0].dataset == "mdd5k"
        assert cases[0].diagnoses == ["F32"]

    def test_comorbid_case(self):
        adapter = MDD5kAdapter(data_path=FIXTURES / "mdd5k_sample.json")
        cases = adapter.load()
        comorbid = cases[2]
        assert comorbid.comorbid is True
        assert len(comorbid.diagnoses) == 2

    def test_transcript_has_turns(self):
        adapter = MDD5kAdapter(data_path=FIXTURES / "mdd5k_sample.json")
        cases = adapter.load()
        assert len(cases[0].transcript) == 4
        assert cases[0].transcript[0].speaker == "doctor"


class TestPDCHAdapter:
    def test_load_fixture(self):
        adapter = PDCHAdapter(data_path=FIXTURES / "pdch_sample.json")
        cases = adapter.load()
        assert len(cases) == 2
        assert cases[0].language == "zh"
        assert cases[0].severity is not None
        assert cases[0].severity["hamd17_total"] == 15

    def test_binary_label(self):
        adapter = PDCHAdapter(data_path=FIXTURES / "pdch_sample.json", binary_threshold=8)
        cases = adapter.load()
        assert cases[0].metadata["binary"] == 1  # total=15 >= 8
        assert cases[1].metadata["binary"] == 0  # total=1 < 8


class TestEDAICAdapter:
    def test_load_fixture(self):
        adapter = EDAICAdapter(data_path=FIXTURES / "edaic_sample.json")
        cases = adapter.load()
        assert len(cases) == 2
        assert cases[0].language == "en"
        assert cases[0].coding_system == "dsm5"
        assert cases[0].severity["phq8_total"] == 12

    def test_binary_label(self):
        adapter = EDAICAdapter(data_path=FIXTURES / "edaic_sample.json")
        cases = adapter.load()
        assert cases[0].metadata["binary"] == 1  # total=12 >= 10
        assert cases[1].metadata["binary"] == 0  # total=0 < 10
