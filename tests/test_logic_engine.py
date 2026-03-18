"""Tests for the Deterministic Diagnostic Logic Engine."""
from __future__ import annotations

import pytest

from culturedx.core.models import CheckerOutput, CriterionResult
from culturedx.diagnosis.logic_engine import DiagnosticLogicEngine, LogicEngineOutput


def _make_checker(
    disorder: str, met: list[str], not_met: list[str], required: int = 0
) -> CheckerOutput:
    criteria = []
    for cid in met:
        criteria.append(CriterionResult(criterion_id=cid, status="met", confidence=0.9))
    for cid in not_met:
        criteria.append(CriterionResult(criterion_id=cid, status="not_met", confidence=0.2))
    return CheckerOutput(
        disorder=disorder,
        criteria=criteria,
        criteria_met_count=len(met),
        criteria_required=required,
    )


@pytest.fixture
def engine():
    return DiagnosticLogicEngine()


class TestLogicEngineF32:
    """F32 Depressive episode: min_core=2, min_total=4."""

    def test_meets_threshold(self, engine):
        co = _make_checker("F32", met=["B1", "B2", "C1", "C2", "C3"], not_met=["B3", "C4"])
        result = engine.evaluate([co])
        assert "F32" in result.confirmed_codes

    def test_below_total(self, engine):
        co = _make_checker("F32", met=["B1", "B2", "C1"], not_met=["B3", "C2", "C3"])
        result = engine.evaluate([co])
        assert "F32" not in result.confirmed_codes

    def test_below_core(self, engine):
        co = _make_checker("F32", met=["B1", "C1", "C2", "C3", "C4"], not_met=["B2", "B3"])
        result = engine.evaluate([co])
        # Only 1 core (B1), need 2 → should fail
        assert "F32" not in result.confirmed_codes


class TestLogicEngineF22:
    """F22 Persistent delusional disorder: all_required=true."""

    def test_all_met(self, engine):
        co = _make_checker("F22", met=["A", "B", "C"], not_met=[])
        result = engine.evaluate([co])
        assert "F22" in result.confirmed_codes

    def test_missing_one(self, engine):
        co = _make_checker("F22", met=["A", "B"], not_met=["C"])
        result = engine.evaluate([co])
        assert "F22" not in result.confirmed_codes


class TestLogicEngineF20:
    """F20 Schizophrenia: 1 first_rank OR 2 other."""

    def test_one_first_rank(self, engine):
        co = _make_checker("F20", met=["A1"], not_met=["A2", "A3", "A4", "B1", "B2"])
        result = engine.evaluate([co])
        assert "F20" in result.confirmed_codes

    def test_two_other(self, engine):
        co = _make_checker("F20", met=["B1", "B2"], not_met=["A1", "A2", "A3", "A4"])
        result = engine.evaluate([co])
        assert "F20" in result.confirmed_codes

    def test_neither(self, engine):
        co = _make_checker("F20", met=["B1"], not_met=["A1", "A2", "A3", "A4", "B2"])
        result = engine.evaluate([co])
        assert "F20" not in result.confirmed_codes


class TestLogicEngineF41_1:
    """F41.1 GAD: min_symptoms=4."""

    def test_meets_4(self, engine):
        co = _make_checker("F41.1", met=["A", "B1", "B2", "B3"], not_met=["B4"])
        result = engine.evaluate([co])
        assert "F41.1" in result.confirmed_codes

    def test_below_4(self, engine):
        co = _make_checker("F41.1", met=["A", "B1", "B2"], not_met=["B3", "B4"])
        result = engine.evaluate([co])
        assert "F41.1" not in result.confirmed_codes


class TestLogicEngineF40:
    """F40 Phobic anxiety: core_required + min_additional=1."""

    def test_core_plus_one(self, engine):
        co = _make_checker("F40", met=["A", "B", "C1"], not_met=["C2", "C3"])
        result = engine.evaluate([co])
        assert "F40" in result.confirmed_codes

    def test_core_only(self, engine):
        co = _make_checker("F40", met=["A", "B"], not_met=["C1", "C2", "C3"])
        result = engine.evaluate([co])
        assert "F40" not in result.confirmed_codes


class TestLogicEngineMultiple:
    """Test multiple disorders simultaneously."""

    def test_comorbid(self, engine):
        co1 = _make_checker("F32", met=["B1", "B2", "C1", "C2"], not_met=["B3"])
        co2 = _make_checker("F41.1", met=["A", "B1", "B2", "B3", "B4"], not_met=[])
        result = engine.evaluate([co1, co2])
        assert "F32" in result.confirmed_codes
        assert "F41.1" in result.confirmed_codes
        assert len(result.confirmed) == 2

    def test_one_confirmed_one_rejected(self, engine):
        co1 = _make_checker("F32", met=["B1", "B2", "C1", "C2"], not_met=["B3"])
        co2 = _make_checker("F41.1", met=["A", "B1"], not_met=["B2", "B3", "B4"])
        result = engine.evaluate([co1, co2])
        assert "F32" in result.confirmed_codes
        assert "F41.1" not in result.confirmed_codes
        assert len(result.rejected) == 1

    def test_empty_input(self, engine):
        result = engine.evaluate([])
        assert len(result.confirmed) == 0
        assert len(result.rejected) == 0

    def test_unknown_disorder(self, engine):
        co = _make_checker("X99", met=["A", "B"], not_met=[])
        result = engine.evaluate([co])
        assert "X99" not in result.confirmed_codes

    def test_confirmed_sorted_by_met_count(self, engine):
        co1 = _make_checker("F41.1", met=["A", "B1", "B2", "B3", "B4"], not_met=[])
        co2 = _make_checker("F32", met=["B1", "B2", "C1", "C2"], not_met=["B3"])
        result = engine.evaluate([co1, co2])
        # F41.1 has 5 met, F32 has 4 → F41.1 should be first
        assert result.confirmed[0].disorder_code == "F41.1"
