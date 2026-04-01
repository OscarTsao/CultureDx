"""Tests for ICD-10 criteria ontology."""
import pytest
from culturedx.ontology.icd10 import (
    load_criteria,
    get_disorder_criteria,
    get_criterion_text,
    get_disorder_threshold,
    list_disorders,
)


class TestICD10Ontology:
    def test_load_criteria(self):
        data = load_criteria()
        assert "F32" in data
        assert "F41.1" in data
        assert "F39" in data
        assert "F98" in data

    def test_list_disorders(self):
        disorders = list_disorders()
        assert "F32" in disorders
        assert "F45" in disorders
        assert len(disorders) >= 12

    def test_get_disorder_criteria(self):
        criteria = get_disorder_criteria("F32")
        assert criteria is not None
        assert "B1" in criteria
        assert criteria["B1"]["text"]
        assert criteria["B1"]["text_zh"]

    def test_new_disorders_have_expected_thresholds(self):
        f39_criteria = get_disorder_criteria("F39")
        f98_criteria = get_disorder_criteria("F98")
        f39_threshold = get_disorder_threshold("F39")
        f98_threshold = get_disorder_threshold("F98")
        assert f39_criteria is not None
        assert f98_criteria is not None
        assert "A1" in f39_criteria
        assert "A1" in f98_criteria
        assert f39_threshold["min_total"] == 3
        assert f98_threshold["min_total"] == 3

    def test_get_criterion_text(self):
        text_en = get_criterion_text("F32", "B1", language="en")
        assert "depressed mood" in text_en.lower()
        text_zh = get_criterion_text("F32", "B1", language="zh")
        assert "抑郁" in text_zh or "情绪低落" in text_zh

    def test_unknown_disorder(self):
        criteria = get_disorder_criteria("F99.9")
        assert criteria is None

    def test_unknown_criterion(self):
        text = get_criterion_text("F32", "Z99", language="en")
        assert text is None
