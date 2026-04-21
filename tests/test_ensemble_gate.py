"""Tests for the confidence-gated MAS + TF-IDF ensemble."""
from __future__ import annotations

from culturedx.postproc.ensemble_gate import EnsembleConfig, apply_ensemble, paper_parent


def build_mas(primary: str) -> dict:
    return {
        "case_id": "1",
        "gold_diagnoses": ["F32"],
        "primary_diagnosis": primary,
        "comorbid_diagnoses": ["F39"],
        "confidence": 0.91,
    }


def build_tfidf(primary: str, prob: float) -> dict:
    return {
        "case_id": "1",
        "gold_diagnoses": ["F32"],
        "primary_diagnosis": primary,
        "comorbid_diagnoses": ["F43"],
        "ranked_codes": [primary, "F43", "F32"],
        "proba_scores": [prob, 0.2, 0.1],
    }


def test_paper_parent_collapses_decimal_suffix():
    assert paper_parent("F41.2") == "F41"
    assert paper_parent("z71.0") == "Z71"


def test_v1_uses_mas_for_strong_class():
    result = apply_ensemble(
        build_mas("F32.1"),
        build_tfidf("F41", 0.88),
        EnsembleConfig(rule="v1_class_based", mas_strong_classes=("F32",)),
    )
    assert result["ensemble_source"] == "mas"
    assert result["primary_diagnosis"] == "F32.1"
    assert result["confidence"] == 0.91


def test_v1_uses_tfidf_when_mas_not_strong():
    result = apply_ensemble(
        build_mas("F45"),
        build_tfidf("F41", 0.88),
        EnsembleConfig(rule="v1_class_based", mas_strong_classes=("F32", "F41")),
    )
    assert result["ensemble_source"] == "tfidf"
    assert result["primary_diagnosis"] == "F41"
    assert result["ranked_codes"][0] == "F41"
    assert result["confidence"] == 0.88


def test_v2_prefers_high_confidence_tfidf_when_non_strong():
    result = apply_ensemble(
        build_mas("F32"),
        build_tfidf("F43", 0.55),
        EnsembleConfig(
            rule="v2_prob_threshold",
            mas_strong_classes=("F32", "F41"),
            tfidf_threshold_high=0.4,
        ),
    )
    assert result["ensemble_source"] == "tfidf"
    assert result["primary_diagnosis"] == "F43"


def test_v2_falls_back_to_v1_when_tfidf_class_is_strong():
    result = apply_ensemble(
        build_mas("F32"),
        build_tfidf("F41", 0.92),
        EnsembleConfig(
            rule="v2_prob_threshold",
            mas_strong_classes=("F32", "F41"),
            tfidf_threshold_high=0.4,
        ),
    )
    assert result["ensemble_source"] == "mas"
    assert result["primary_diagnosis"] == "F32"
