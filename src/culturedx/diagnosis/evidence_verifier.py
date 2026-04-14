"""Post-checker evidence verification.

Checks each 'met' criterion's evidence against the transcript to detect:
- Fabrication: key clinical phrases not present in transcript
- Negation conflicts: evidence affirms what patient explicitly denies
- Criteria injection: ICD criteria descriptions used as patient evidence

Ungrounded criteria are downgraded to 'insufficient_evidence'.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

_SYMPTOM_RE = re.compile(
    r"(失眠|早醒|嗜睡|心慌|胸闷|出汗|手抖|头晕|恶心|呕吐|"
    r"焦虑|担忧|紧张|害怕|恐惧|低落|悲伤|兴趣|愉快|疲倦|疲劳|"
    r"精力|注意力|食欲|体重|自责|罪恶|自杀|自伤|绝望|烦躁|"
    r"心情|睡眠|情绪|工作|学习|社交|功能|"
    r"心烦|睡不着|提不起劲|想事情|停不下来)"
)
_TIME_RE = re.compile(r"(\d+[个月周天年日小时]|超过\d+|近\d+|约\d+|至少\d+|持续\d+)")
_NEG_PREFIXES = ["没有", "否认", "未见", "不是", "不会", "不太", "不", "无", "未"]
_CRITERIA_KW = ["至少", "诊断标准", "符合", "标准", "核心症状", "排除", "不符合", "未表现", "需要", "必须"]


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"[。！？\n]+", text)
    sentences: list[str] = []
    for p in parts:
        sub = re.split(r"(?:医生|患者)：", p)
        for s in sub:
            s = s.strip()
            if len(s) >= 4:
                sentences.append(s)
    return sentences


def extract_key_phrases(evidence: str) -> list[str]:
    phrases: list[str] = []
    for m in _SYMPTOM_RE.finditer(evidence):
        phrases.append(m.group())
    for m in _TIME_RE.finditer(evidence):
        phrases.append(m.group())
    return list(set(phrases))


def check_negation(evidence: str, transcript: str) -> list[str]:
    conflicts: list[str] = []
    for prefix in _NEG_PREFIXES:
        for m in re.finditer(re.escape(prefix) + r"(.{2,12})", transcript):
            content = m.group(1)
            if content and content in evidence:
                if not any(n in evidence for n in ["没", "不", "无", "否", "未"]):
                    conflicts.append(f"negation:{m.group()}")
    return conflicts


def verify_criterion(
    evidence: str, transcript: str, sentences: list[str]
) -> tuple[str, float, list[str]]:
    if not evidence or len(evidence) < 4:
        return "EMPTY", 0.0, []

    best_score = 0.0
    for sent in sentences:
        score = SequenceMatcher(None, evidence, sent).ratio()
        if score > best_score:
            best_score = score

    key_phrases = extract_key_phrases(evidence)
    found = [kp for kp in key_phrases if kp in transcript]
    missing = [kp for kp in key_phrases if kp not in transcript]
    phrase_ratio = len(found) / max(len(key_phrases), 1)

    is_criteria = sum(1 for k in _CRITERIA_KW if k in evidence) >= 2

    neg_issues = check_negation(evidence, transcript)
    issues = neg_issues + [f"missing:{m}" for m in missing[:3]]

    if best_score >= 0.8:
        return "VERBATIM", best_score, neg_issues
    if best_score >= 0.5 or (phrase_ratio >= 0.8 and key_phrases):
        return "PARAPHRASE", best_score, neg_issues
    if phrase_ratio >= 0.5 and len(found) >= 2:
        return "SYNTHESIS", best_score, issues
    if is_criteria:
        return "CRITERIA_INJECTION", best_score, issues
    return "FABRICATED", best_score, issues


def verify_checker_output(
    checker_output: dict, transcript: str
) -> tuple[dict, int, list[dict]]:
    """Verify all criteria in a checker output dict against transcript.

    Returns (verified_output, n_downgraded, verification_details).
    """
    sentences = split_sentences(transcript)
    n_downgraded = 0
    details: list[dict] = []

    new_per_criterion: list[dict] = []
    for crit in checker_output.get("per_criterion", []):
        new_crit = dict(crit)

        if crit.get("status") == "met" and crit.get("evidence"):
            cat, score, issues = verify_criterion(crit["evidence"], transcript, sentences)
            neg_conflict = any(i.startswith("negation:") for i in issues)

            if neg_conflict:
                new_crit["status"] = "not_met"
                new_crit["confidence"] = 0.0
                new_crit["evidence"] = crit["evidence"] + " [否定冲突]"
                n_downgraded += 1
            elif cat in ("FABRICATED", "CRITERIA_INJECTION"):
                new_crit["status"] = "insufficient_evidence"
                new_crit["confidence"] = crit.get("confidence", 0.5) * 0.3
                new_crit["evidence"] = crit["evidence"] + f" [{cat}]"
                n_downgraded += 1

            details.append({
                "criterion_id": crit.get("criterion_id", ""),
                "category": cat,
                "score": round(score, 3),
                "issues": issues,
                "downgraded": new_crit["status"] != crit.get("status"),
            })

        new_per_criterion.append(new_crit)

    new_met = sum(1 for c in new_per_criterion if c.get("status") == "met")
    verified = dict(checker_output)
    verified["per_criterion"] = new_per_criterion
    verified["criteria_met_count"] = new_met
    total = max(checker_output.get("criteria_total_count", 1), 1)
    verified["met_ratio"] = new_met / total
    verified["verification"] = {"n_downgraded": n_downgraded, "details": details}

    return verified, n_downgraded, details
