"""Tests for error taxonomy analysis."""
from __future__ import annotations

import pytest

from culturedx.eval.error_analysis import (
    CaseError,
    ErrorTaxonomyCollector,
    ErrorType,
)


@pytest.fixture
def collector():
    return ErrorTaxonomyCollector()


class TestErrorTaxonomy:
    def test_correct_prediction(self, collector):
        errors = collector.analyze_case("c1", "F32", "F32")
        assert len(errors) == 0

    def test_parent_code_match(self, collector):
        errors = collector.analyze_case("c1", "F41.1", "F41")
        assert len(errors) == 0

    def test_abstention_error(self, collector):
        errors = collector.analyze_case("c1", None, "F32", confidence=0.2)
        assert len(errors) == 1
        assert errors[0].error_type == ErrorType.CALIBRATOR_ABSTAIN

    def test_ontology_not_covered(self, collector):
        errors = collector.analyze_case("c1", "F32", "F99")
        assert len(errors) == 1
        assert errors[0].error_type == ErrorType.ONTOLOGY_NOT_COVERED

    def test_triage_miss(self, collector):
        # Gold F41.1 not in criteria_results
        criteria_results = [{"disorder": "F32", "criteria_met_count": 5, "criteria_required": 4}]
        errors = collector.analyze_case(
            "c1", "F32", "F41", criteria_results=criteria_results
        )
        assert any(e.error_type == ErrorType.TRIAGE_MISS for e in errors)

    def test_logic_false_reject(self, collector):
        # Gold F41.1 checked but below threshold
        criteria_results = [
            {"disorder": "F41.1", "criteria_met_count": 3, "criteria_required": 4,
             "criteria": [
                 {"criterion_id": "A", "status": "insufficient_evidence"},
                 {"criterion_id": "B1", "status": "met"},
                 {"criterion_id": "B2", "status": "met"},
                 {"criterion_id": "B3", "status": "met"},
                 {"criterion_id": "B4", "status": "not_met"},
             ]},
            {"disorder": "F32", "criteria_met_count": 5, "criteria_required": 4},
        ]
        errors = collector.analyze_case(
            "c1", "F32", "F41", criteria_results=criteria_results
        )
        assert any(e.error_type == ErrorType.LOGIC_FALSE_REJECT for e in errors)

    def test_calibrator_rank_swap(self, collector):
        # Gold F41.1 confirmed but F32 ranked higher
        criteria_results = [
            {"disorder": "F41.1", "criteria_met_count": 4, "criteria_required": 4},
            {"disorder": "F32", "criteria_met_count": 6, "criteria_required": 4},
        ]
        errors = collector.analyze_case(
            "c1", "F32", "F41", criteria_results=criteria_results
        )
        assert any(e.error_type == ErrorType.CALIBRATOR_RANK_SWAP for e in errors)

    def test_summarize(self, collector):
        collector.analyze_case("c1", "F32", "F41")
        collector.analyze_case("c2", None, "F32", confidence=0.1)
        collector.analyze_case("c3", "F32", "F32")  # correct
        summary = collector.summarize()
        assert summary.total_errors == 2
        assert len(summary.error_counts) >= 1

    def test_format_summary(self, collector):
        collector.analyze_case("c1", "F32", "F41")
        summary = collector.summarize()
        summary.total_cases = 10
        summary.total_correct = 9
        text = collector.format_summary(summary)
        assert "Error Taxonomy" in text
        assert "Pipeline Stage" in text
