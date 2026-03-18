"""Tests for PDCH dataset adapter."""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from culturedx.data.adapters.pdch import PDCHAdapter


@pytest.fixture
def pdch_data(tmp_path):
    data = [
        {
            "case_id": "P001",
            "dialogue": [
                {"speaker": "doctor", "text": "你好，最近感觉怎么样？"},
                {"speaker": "patient", "text": "我最近情绪很低落，睡不好。"},
                {"speaker": "doctor", "text": "持续多久了？"},
                {"speaker": "patient", "text": "大概两个月了。"},
            ],
            "hamd17": [2, 1, 2, 3, 1, 0, 1, 0, 2, 1, 0, 1, 1, 0, 1, 2, 1],
            "hamd17_total": 19,
        },
        {
            "case_id": "P002",
            "dialogue": [
                {"speaker": "doctor", "text": "今天来看什么问题？"},
                {"speaker": "patient", "text": "只是来复查的。"},
            ],
            "hamd17": [0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
            "hamd17_total": 2,
        },
    ]
    path = tmp_path / "pdch.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


class TestPDCHAdapter:
    def test_load_cases(self, pdch_data):
        adapter = PDCHAdapter(data_path=pdch_data)
        cases = adapter.load()
        assert len(cases) == 2

    def test_case_language(self, pdch_data):
        adapter = PDCHAdapter(data_path=pdch_data)
        cases = adapter.load()
        assert all(c.language == "zh" for c in cases)

    def test_case_dataset(self, pdch_data):
        adapter = PDCHAdapter(data_path=pdch_data)
        cases = adapter.load()
        assert all(c.dataset == "pdch" for c in cases)

    def test_transcript_parsing(self, pdch_data):
        adapter = PDCHAdapter(data_path=pdch_data)
        cases = adapter.load()
        assert len(cases[0].transcript) == 4
        assert cases[0].transcript[0].speaker == "doctor"
        assert "情绪很低落" in cases[0].transcript[1].text

    def test_severity_scores(self, pdch_data):
        adapter = PDCHAdapter(data_path=pdch_data)
        cases = adapter.load()
        assert cases[0].severity["hamd17_total"] == 19
        assert len(cases[0].severity["hamd17"]) == 17

    def test_binary_threshold_default(self, pdch_data):
        adapter = PDCHAdapter(data_path=pdch_data)
        cases = adapter.load()
        assert cases[0].metadata["binary"] == 1  # 19 >= 8
        assert cases[1].metadata["binary"] == 0  # 2 < 8

    def test_binary_threshold_custom(self, pdch_data):
        adapter = PDCHAdapter(data_path=pdch_data, binary_threshold=20)
        cases = adapter.load()
        assert cases[0].metadata["binary"] == 0  # 19 < 20
        assert cases[1].metadata["binary"] == 0  # 2 < 20

    def test_coding_system(self, pdch_data):
        adapter = PDCHAdapter(data_path=pdch_data)
        cases = adapter.load()
        assert all(c.coding_system == "hamd17" for c in cases)
