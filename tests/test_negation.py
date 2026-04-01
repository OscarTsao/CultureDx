"""Tests for scope-aware Chinese negation detection."""
from __future__ import annotations

import pytest

from culturedx.evidence.negation import NegationDetector


@pytest.fixture(scope="module")
def detector() -> NegationDetector:
    return NegationDetector(mode="clause-rule")


def test_simple_negation(detector: NegationDetector):
    result = detector.detect("没有头痛", "头痛")
    assert result.is_negated is True
    assert result.negation_cue == "没有"
    assert result.scope == "没有头痛"


def test_scope_boundary_with_batch_detection(detector: NegationDetector):
    chest_tightness, anxiety = detector.detect_batch("没有胸闷，但是很焦虑", ["胸闷", "焦虑"])
    assert chest_tightness.is_negated is True
    assert anxiety.is_negated is False


def test_positive_symptom_with_embedded_negation(detector: NegationDetector):
    result = detector.detect("睡不着", "睡不着")
    assert result.is_negated is False


def test_discourse_exception_is_not_symptom_negation(detector: NegationDetector):
    result = detector.detect("不是我的问题", "问题")
    assert result.is_negated is False


def test_double_negation_is_resolved(detector: NegationDetector):
    result = detector.detect("并非完全没有改善", "改善")
    assert result.is_negated is False


def test_clause_scope_with_multiple_negations(detector: NegationDetector):
    nausea, vomiting, dizziness = detector.detect_batch(
        "我没有恶心，也没有呕吐，但是会头晕",
        ["恶心", "呕吐", "头晕"],
    )
    assert nausea.is_negated is True
    assert vomiting.is_negated is True
    assert dizziness.is_negated is False


def test_no_negation_returns_false(detector: NegationDetector):
    result = detector.detect("心情很低落", "低落")
    assert result.is_negated is False


def test_denial_cue_negates_suicidal_ideation(detector: NegationDetector):
    result = detector.detect("否认有自杀想法", "自杀想法")
    assert result.is_negated is True
    assert result.negation_cue == "否认"


def test_nominal_wu_scope_does_not_negate_later_symptom(detector: NegationDetector):
    cause = detector.detect("无明显诱因出现焦虑", "诱因")
    anxiety = detector.detect("无明显诱因出现焦虑", "焦虑")
    assert cause.is_negated is True
    assert anxiety.is_negated is False
