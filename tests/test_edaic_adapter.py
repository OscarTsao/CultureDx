"""Tests for E-DAIC dataset adapter."""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from culturedx.data.adapters.edaic import EDAICAdapter


@pytest.fixture
def edaic_data(tmp_path):
    data = [
        {
            "case_id": "E001",
            "dialogue": [
                {"speaker": "interviewer", "text": "How are you feeling today?"},
                {"speaker": "participant", "text": "Not great, I've been feeling down."},
                {"speaker": "interviewer", "text": "How long has this been going on?"},
                {"speaker": "participant", "text": "About two months now."},
            ],
            "phq8": [2, 1, 3, 2, 1, 0, 2, 1],
            "phq8_total": 12,
        },
        {
            "case_id": "E002",
            "dialogue": [
                {"speaker": "interviewer", "text": "Tell me about yourself."},
                {"speaker": "participant", "text": "I'm doing okay, work is fine."},
            ],
            "phq8": [0, 0, 1, 0, 0, 0, 0, 1],
            "phq8_total": 2,
        },
    ]
    path = tmp_path / "edaic.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class TestEDAICAdapter:
    def test_load_cases(self, edaic_data):
        adapter = EDAICAdapter(data_path=edaic_data)
        cases = adapter.load()
        assert len(cases) == 2

    def test_case_language(self, edaic_data):
        adapter = EDAICAdapter(data_path=edaic_data)
        cases = adapter.load()
        assert all(c.language == "en" for c in cases)

    def test_case_dataset(self, edaic_data):
        adapter = EDAICAdapter(data_path=edaic_data)
        cases = adapter.load()
        assert all(c.dataset == "edaic" for c in cases)

    def test_transcript_parsing(self, edaic_data):
        adapter = EDAICAdapter(data_path=edaic_data)
        cases = adapter.load()
        assert len(cases[0].transcript) == 4
        assert cases[0].transcript[0].speaker == "interviewer"
        assert cases[0].transcript[1].text == "Not great, I've been feeling down."

    def test_severity_scores(self, edaic_data):
        adapter = EDAICAdapter(data_path=edaic_data)
        cases = adapter.load()
        assert cases[0].severity["phq8_total"] == 12
        assert len(cases[0].severity["phq8"]) == 8

    def test_binary_threshold_default(self, edaic_data):
        adapter = EDAICAdapter(data_path=edaic_data)
        cases = adapter.load()
        assert cases[0].metadata["binary"] == 1  # 12 >= 10
        assert cases[1].metadata["binary"] == 0  # 2 < 10

    def test_binary_threshold_custom(self, edaic_data):
        adapter = EDAICAdapter(data_path=edaic_data, binary_threshold=15)
        cases = adapter.load()
        assert cases[0].metadata["binary"] == 0  # 12 < 15
        assert cases[1].metadata["binary"] == 0  # 2 < 15

    def test_coding_system(self, edaic_data):
        adapter = EDAICAdapter(data_path=edaic_data)
        cases = adapter.load()
        assert all(c.coding_system == "dsm5" for c in cases)
