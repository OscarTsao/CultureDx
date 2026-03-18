"""Tests for somatization symptom map."""
import pytest
from culturedx.ontology.symptom_map import (
    load_somatization_map,
    lookup_symptom,
    get_criteria_for_symptom,
)


class TestSymptomMap:
    def test_load_map(self):
        data = load_somatization_map()
        assert "头疼" in data
        assert "失眠" in data

    def test_lookup_known_symptom(self):
        result = lookup_symptom("头疼")
        assert result is not None
        assert "criteria" in result
        assert "F32.C6" in result["criteria"]

    def test_lookup_unknown_symptom(self):
        result = lookup_symptom("未知症状xyz")
        assert result is None

    def test_get_criteria_for_symptom(self):
        criteria = get_criteria_for_symptom("失眠")
        assert isinstance(criteria, list)
        assert "F32.C6" in criteria
        assert "F51.A" in criteria

    def test_get_criteria_unknown(self):
        criteria = get_criteria_for_symptom("不存在的症状")
        assert criteria == []

    def test_all_entries_have_criteria(self):
        data = load_somatization_map()
        for symptom, entry in data.items():
            assert "criteria" in entry, f"{symptom} missing criteria"
            assert len(entry["criteria"]) > 0, f"{symptom} has empty criteria"
