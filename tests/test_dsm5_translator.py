"""Tests for the ICD-10 to DSM-5 post-hoc translator."""
from __future__ import annotations

from culturedx.translators.dsm5_translator import DSM5Result, get_mapping_meta, translate, translate_prediction_record


def test_translate_direct_mapping_f20():
    result = translate("F20")

    assert isinstance(result, DSM5Result)
    assert result.icd10_code == "F20"
    assert result.dsm5_code == "295.90"
    assert result.dsm5_name_en == "Schizophrenia"
    assert result.dsm5_name_zh == "思覺失調症"
    assert result.is_lossy is False


def test_translate_severity_specifier_f321():
    result = translate("F32.1")

    assert result.dsm5_code == "296.22"
    assert result.dsm5_name_en == "Major Depressive Disorder, Single Episode, Moderate"
    assert result.is_lossy is False


def test_translate_subcode_mapping_f410():
    result = translate("f41.0")

    assert result.icd10_code == "F41.0"
    assert result.dsm5_code == "300.01"
    assert result.dsm5_name_en == "Panic Disorder"
    assert result.is_lossy is False


def test_translate_lossy_case_f412():
    result = translate("F41.2")

    assert result.dsm5_code is None
    assert result.is_lossy is True
    assert result.fallback_codes == ["300.00", "311"]
    assert "direct equivalent" in result.note.lower()


def test_translate_missing_code_f99():
    result = translate("F99")

    assert result.dsm5_code is None
    assert result.is_lossy is False
    assert result.note == "No DSM-5 mapping found for ICD-10 code F99."


def test_translate_empty_string():
    result = translate("")

    assert result.icd10_code is None
    assert result.dsm5_code is None
    assert result.note == "No ICD-10 code provided."


def test_translate_none_input():
    result = translate(None)

    assert result.icd10_code is None
    assert result.dsm5_code is None
    assert result.note == "No ICD-10 code provided."


def test_translate_parent_only_f32():
    result = translate("F32")

    assert result.dsm5_code == "296.2x"
    assert result.dsm5_name_en == "Major Depressive Disorder, Single Episode"
    assert result.is_lossy is False


def test_translate_unmapped_subcode_falls_back_to_parent():
    result = translate("F32.8")

    assert result.icd10_code == "F32.8"
    assert result.dsm5_code == "296.2x"
    assert result.note is not None
    assert "parent-level fallback" in result.note
    assert "F32.8" in result.note


def test_translate_parent_family_requires_review_for_f41():
    result = translate("F41")

    assert result.dsm5_code is None
    assert result.is_lossy is True
    assert "Subtype Review Required" in result.dsm5_name_en
    assert "300.01" in result.fallback_codes


def test_translate_f512_keeps_family_placeholder():
    result = translate("F51.2")

    assert result.dsm5_code == "327.3x"
    assert result.is_lossy is True
    assert "circadian" in result.dsm5_name_en.lower()


def test_translate_prediction_record_augments_fields_without_mutating_input():
    pred = {
        "case_id": "case-001",
        "primary_diagnosis": "F32.1",
        "comorbid_diagnoses": ["F41.2", "F42"],
        "gold_diagnoses": ["F32", "F41"],
    }

    enriched = translate_prediction_record(pred)

    assert "dsm5_primary" not in pred
    assert enriched["dsm5_review_status"] == "NOT_CLINICALLY_VALIDATED"
    assert enriched["dsm5_primary_code"] == "296.22"
    assert enriched["dsm5_primary"]["dsm5_name_zh"] == "重度憂鬱症單次發作，中度"
    assert enriched["dsm5_comorbid_codes"] == [None, "300.3"]
    assert enriched["dsm5_comorbid"][0]["is_lossy"] is True
    assert enriched["dsm5_gold_codes"] == ["296.2x", None]


def test_mapping_meta_reports_not_clinically_validated():
    meta = get_mapping_meta()

    assert meta["review_status"] == "NOT_CLINICALLY_VALIDATED"
    assert meta["paper_class_count"] == 12
    assert meta["subcode_count"] == 20
