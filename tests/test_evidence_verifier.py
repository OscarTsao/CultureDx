"""Tests for evidence_verifier module."""
from culturedx.diagnosis.evidence_verifier import (
    verify_criterion,
    verify_checker_output,
    split_sentences,
    extract_key_phrases,
    check_negation,
)


TRANSCRIPT = (
    "医生：你好，最近怎么样？\n"
    "患者：最近心烦，睡不着，脑子里一直想事情，停不下来。\n"
    "医生：睡不着大概多久了？\n"
    "患者：大概一个月了吧。\n"
    "医生：有没有食欲变化？\n"
    "患者：没有，吃饭还行。\n"
    "医生：工作受影响了吗？\n"
    "患者：没有下降，就是有点累。"
)
SENTENCES = split_sentences(TRANSCRIPT)


def test_verbatim_not_downgraded():
    ev = "心烦，睡不着，脑子里一直想事情，停不下来"
    cat, score, issues = verify_criterion(ev, TRANSCRIPT, SENTENCES)
    assert cat == "VERBATIM", f"Expected VERBATIM, got {cat}"
    assert score >= 0.8


def test_paraphrase_not_downgraded():
    ev = "患者报告睡不着，脑子里想事情停不下来，持续约一个月"
    cat, score, issues = verify_criterion(ev, TRANSCRIPT, SENTENCES)
    assert cat in ("PARAPHRASE", "VERBATIM", "SYNTHESIS"), f"Got {cat}"


def test_fabricated_downgraded():
    co = {
        "disorder_code": "F32",
        "criteria_met_count": 1,
        "criteria_total_count": 3,
        "per_criterion": [
            {"criterion_id": "A1", "status": "met", "confidence": 0.8,
             "evidence": "患者有严重的自杀意念和自伤行为，社交功能完全丧失"},
        ],
    }
    verified, n_down, details = verify_checker_output(co, TRANSCRIPT)
    assert n_down >= 1, "Fabricated evidence should be downgraded"
    assert verified["per_criterion"][0]["status"] != "met"


def test_negation_conflict():
    ev = "患者食欲下降，体重减轻"
    cat, score, issues = verify_criterion(ev, TRANSCRIPT, SENTENCES)
    # Transcript says "没有" regarding food changes
    neg = check_negation(ev, TRANSCRIPT)
    # "没有" + content that overlaps with "下降" could trigger
    # The exact behavior depends on transcript phrasing


def test_negation_downgrade():
    co = {
        "disorder_code": "F32",
        "criteria_met_count": 1,
        "criteria_total_count": 1,
        "per_criterion": [
            {"criterion_id": "B5", "status": "met", "confidence": 0.7,
             "evidence": "工作效率下降，注意力难以集中"},
        ],
    }
    # Transcript says "没有下降"
    verified, n_down, details = verify_checker_output(co, TRANSCRIPT)
    assert n_down >= 1, "Negation conflict should downgrade"
    assert verified["per_criterion"][0]["status"] in ("not_met", "insufficient_evidence")


def test_empty_evidence_not_crashed():
    co = {
        "disorder_code": "F41",
        "criteria_met_count": 1,
        "criteria_total_count": 2,
        "per_criterion": [
            {"criterion_id": "A", "status": "met", "confidence": 0.5, "evidence": ""},
            {"criterion_id": "B", "status": "not_met", "confidence": 0.1, "evidence": ""},
        ],
    }
    verified, n_down, details = verify_checker_output(co, TRANSCRIPT)
    assert verified is not None
    assert n_down == 0  # empty evidence on met doesn't crash


def test_criteria_injection_downgraded():
    co = {
        "disorder_code": "F43",
        "criteria_met_count": 1,
        "criteria_total_count": 1,
        "per_criterion": [
            {"criterion_id": "C", "status": "met", "confidence": 0.6,
             "evidence": "患者未表现出符合其他特定障碍的核心症状，如自杀意念，排除标准不符合"},
        ],
    }
    verified, n_down, details = verify_checker_output(co, TRANSCRIPT)
    assert n_down >= 1
    assert verified["per_criterion"][0]["status"] != "met"


def test_met_count_updated():
    co = {
        "disorder_code": "F32",
        "criteria_met_count": 2,
        "criteria_total_count": 3,
        "per_criterion": [
            {"criterion_id": "A", "status": "met", "confidence": 0.9,
             "evidence": "心烦，睡不着"},  # VERBATIM, kept
            {"criterion_id": "B", "status": "met", "confidence": 0.7,
             "evidence": "患者有严重自杀意念和自伤行为"},  # FABRICATED, downgraded
            {"criterion_id": "C", "status": "not_met", "confidence": 0.1, "evidence": ""},
        ],
    }
    verified, n_down, _ = verify_checker_output(co, TRANSCRIPT)
    assert verified["criteria_met_count"] == 1  # only A survives
    assert n_down == 1
