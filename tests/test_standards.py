"""Tests for the unified diagnostic-standard ontology helpers."""
from __future__ import annotations

from pathlib import Path

import culturedx.ontology.icd10 as icd10
import pytest

from culturedx.eval.lingxidiag_paper import PAPER_12_CLASSES
from culturedx.ontology.standards import (
    DiagnosticStandard,
    dsm5_to_icd10,
    get_disorder_criteria,
    get_disorder_name,
    get_disorder_threshold,
    icd10_to_dsm5,
    list_disorders,
    load_criteria,
    paper_parent_icd10,
)

_DSM5_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "culturedx"
    / "ontology"
    / "data"
    / "dsm5_criteria.json"
)


def _require_dsm5_file() -> None:
    if not _DSM5_PATH.exists():
        pytest.skip("DSM-5 criteria draft has not been created yet.")


class TestICD10Backend:
    def test_load_criteria(self) -> None:
        data = load_criteria(DiagnosticStandard.ICD10)
        assert "F32" in data
        assert "F41.2" in data
        assert len(data) == 26

    def test_list_disorders(self) -> None:
        disorders = list_disorders(DiagnosticStandard.ICD10)
        assert disorders == list(load_criteria(DiagnosticStandard.ICD10).keys())
        assert "Z71" in disorders
        assert len(disorders) == 26

    def test_paper_classes_covered(self) -> None:
        disorder_parents = {
            parent
            for code in list_disorders(DiagnosticStandard.ICD10)
            if (parent := paper_parent_icd10(code)) is not None
        }
        expected = {code for code in PAPER_12_CLASSES if code != "Others"}
        assert expected <= disorder_parents

    def test_f32_structure(self) -> None:
        disorder = get_disorder_criteria("F32", DiagnosticStandard.ICD10)
        assert disorder is not None
        assert disorder["name"] == "Depressive episode"
        assert disorder["name_zh"]
        assert disorder["criteria"]["B1"]["text"]
        assert disorder["criteria"]["B1"]["text_zh"]
        assert get_disorder_name("F32", DiagnosticStandard.ICD10, lang="zh") == "抑郁发作"
        assert get_disorder_threshold("F32", DiagnosticStandard.ICD10) == {
            "min_core": 2,
            "min_total": 4,
            "duration_weeks": 2,
        }

    def test_unknown_returns_none(self) -> None:
        assert get_disorder_criteria("F99.9", DiagnosticStandard.ICD10) is None
        assert get_disorder_name("F99.9", DiagnosticStandard.ICD10) is None
        assert get_disorder_threshold("F99.9", DiagnosticStandard.ICD10) == {}


class TestDSM5Backend:
    def test_load_criteria(self) -> None:
        _require_dsm5_file()
        data = load_criteria(DiagnosticStandard.DSM5)
        assert data
        assert "F20" in data
        assert len(data) == 26

    def test_verification_status_check(self) -> None:
        _require_dsm5_file()
        disorder = get_disorder_criteria("F20", DiagnosticStandard.DSM5)
        assert disorder is not None
        assert disorder["verification_status"] == "UNVERIFIED_LLM_DRAFT"


class TestBackwardsCompat:
    def test_old_icd10_imports_still_work(self) -> None:
        criteria = icd10.get_disorder_criteria("F32")
        assert criteria is not None
        assert "B1" in criteria
        assert icd10.get_criterion_text("F32", "B1", language="en") is not None
        assert icd10.get_disorder_name("F32", language="zh") == "抑郁发作"
        assert icd10.get_disorder_threshold("F32")["min_total"] == 4


class TestTranslationHelpers:
    def test_paper_parent(self) -> None:
        assert paper_parent_icd10("F32.1") == "F32"
        assert paper_parent_icd10(" z71.9 ") == "Z71"
        assert paper_parent_icd10("") is None

    def test_icd10_to_dsm5(self) -> None:
        assert icd10_to_dsm5("F32.1") == "296.22"
        assert icd10_to_dsm5("F32.8") == "296.2x"
        assert icd10_to_dsm5("F41.2") is None
        assert icd10_to_dsm5("F99") is None

    def test_dsm5_to_icd10(self) -> None:
        assert dsm5_to_icd10("296.22") == ["F32.1"]
        assert dsm5_to_icd10("300.01") == ["F41.0"]
        assert dsm5_to_icd10("not-a-code") == []


class TestDSM5CriteriaCompleteness:
    def test_all_disorders_unverified(self) -> None:
        _require_dsm5_file()
        data = load_criteria(DiagnosticStandard.DSM5)
        assert len(data) == 26
        assert all(
            disorder["verification_status"] == "UNVERIFIED_LLM_DRAFT"
            for disorder in data.values()
        )

    def test_lossy_cases_flagged(self) -> None:
        _require_dsm5_file()
        data = load_criteria(DiagnosticStandard.DSM5)
        required_lossy = {"F41.2", "F43.2", "F45", "F51", "F98"}
        flagged = {
            code
            for code, disorder in data.items()
            if disorder.get("is_lossy_reasoning") is True
        }
        assert required_lossy <= flagged

    def test_f412_has_fallback(self) -> None:
        _require_dsm5_file()
        disorder = get_disorder_criteria("F41.2", DiagnosticStandard.DSM5)
        assert disorder is not None
        assert disorder["is_lossy_reasoning"] is True
        assert disorder["dsm5_reasoning_fallback"]
