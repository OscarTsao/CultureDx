"""Text normalization and lightweight concept matching helpers for evidence work."""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache

_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")
_PUNCT_RE = re.compile(r"[\s\-\_/\\|,;:。！？、·…（）()\[\]{}<>\'\"`]+")

_NEGATION_MARKERS = (
    "无",
    "沒有",
    "没有",
    "否认",
    "否認",
    "未",
    "不",
    "没",
    "從不",
    "从不",
    "not",
    "no",
)
_STRONG_NEGATION_MARKERS = (
    "无",
    "沒有",
    "没有",
    "否认",
    "否認",
    "從不",
    "从不",
    "not",
    "no",
)
_NEGATION_EXCEPTION_MARKERS = (
    "睡不着",
    "睡不著",
    "睡不着觉",
    "睡不著覺",
    "吃不下",
    "不想做事",
    "没兴趣",
    "沒有興趣",
    "提不起劲",
    "提不起勁",
    "停不下来",
    "停不下來",
    "控制不住",
    "忍不住",
)
_DURATION_MARKERS = (
    "持续",
    "長期",
    "长期",
    "多月",
    "多周",
    "多天",
    "半年",
    "一月",
    "一周",
    "两周",
    "3个月",
    "3月",
    "weeks",
    "months",
    "since",
)
_FUNCTIONAL_IMPAIRMENT_MARKERS = (
    "工作",
    "学习",
    "學習",
    "社交",
    "生活",
    "功能",
    "影响",
    "影響",
    "unable to work",
    "cannot work",
    "impair",
)
_HISTORICAL_MARKERS = (
    "以前",
    "之前",
    "曾经",
    "曾經",
    "那时候",
    "那時候",
    "过去",
    "過去",
    "小时候",
    "小時候",
    "used to",
    "previously",
    "in the past",
)
_OTHER_PERSON_MARKERS = (
    "妈妈",
    "媽媽",
    "母亲",
    "母親",
    "父亲",
    "父親",
    "家人",
    "朋友",
    "同事",
    "他",
    "她",
    "丈夫",
    "妻子",
    "boyfriend",
    "girlfriend",
    "mother",
    "father",
    "family",
)
_AMBIGUITY_MARKERS = (
    "不舒服",
    "难受",
    "難受",
    "说不上",
    "說不上",
    "怪怪的",
    "好像",
    "像是",
    "似乎",
    "感觉怪",
    "感覺怪",
    "sort of",
    "kind of",
    "hard to describe",
)
_DIRECT_SYMPTOM_MARKERS = (
    "情绪低落",
    "情緒低落",
    "焦虑",
    "焦慮",
    "担心",
    "擔心",
    "兴趣减退",
    "興趣減退",
    "没兴趣",
    "沒有興趣",
    "悲伤",
    "悲傷",
    "害怕",
    "恐惧",
    "恐懼",
    "失去兴趣",
    "depressed",
    "anxious",
    "worried",
    "panic",
)
_BODILY_MARKERS = (
    "疼",
    "痛",
    "闷",
    "悶",
    "慌",
    "晕",
    "暈",
    "抖",
    "乏",
    "胃",
    "肚",
    "胸",
    "头",
    "頭",
    "心",
    "睡",
    "呼吸",
    "吃",
    "appetite",
    "sleep",
    "chest",
    "stomach",
    "head",
    "body",
)


@lru_cache(maxsize=8192)
def normalize_text(text: str) -> str:
    """Normalize text for retrieval and concept matching."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = _PUNCT_RE.sub("", normalized)
    return normalized.strip()


def _cjk_bigrams(text: str) -> tuple[str, ...]:
    bigrams: list[str] = []
    for run in _CJK_RUN_RE.findall(text):
        if len(run) <= 1:
            bigrams.append(run)
            continue
        for idx in range(len(run) - 1):
            bigrams.append(run[idx : idx + 2])
    return tuple(bigrams)


@lru_cache(maxsize=8192)
def concept_terms(text: str) -> tuple[str, ...]:
    """Return lightweight concept terms for a string."""
    normalized = normalize_text(text)
    if not normalized:
        return ()
    terms = list(_WORD_RE.findall(normalized))
    terms.extend(_cjk_bigrams(normalized))
    if not terms and normalized:
        terms = [normalized]
    deduped = list(dict.fromkeys(term for term in terms if term))
    return tuple(deduped)


def concept_signature(text: str) -> frozenset[str]:
    """Return a stable signature used for concept overlap calculations."""
    return frozenset(concept_terms(text))


def jaccard_similarity(left: str, right: str) -> float:
    """Compute a lightweight token overlap score."""
    left_terms = concept_signature(left)
    right_terms = concept_signature(right)
    if not left_terms or not right_terms:
        return 0.0
    intersection = len(left_terms & right_terms)
    union = len(left_terms | right_terms)
    return intersection / union if union else 0.0


def sequence_similarity(left: str, right: str) -> float:
    """Character-level fallback similarity."""
    return SequenceMatcher(None, normalize_text(left), normalize_text(right)).ratio()


def contains_negation(text: str) -> bool:
    normalized = normalize_text(text)
    if any(marker in normalized for marker in _STRONG_NEGATION_MARKERS):
        return True
    if any(marker in normalized for marker in _NEGATION_EXCEPTION_MARKERS):
        return False
    return any(marker in normalized for marker in _NEGATION_MARKERS)


def contains_duration_marker(text: str) -> bool:
    normalized = normalize_text(text)
    return any(marker in normalized for marker in _DURATION_MARKERS)


def contains_functional_impairment_marker(text: str) -> bool:
    normalized = normalize_text(text)
    return any(marker in normalized for marker in _FUNCTIONAL_IMPAIRMENT_MARKERS)


def contains_historical_marker(text: str) -> bool:
    normalized = normalize_text(text)
    return any(marker in normalized for marker in _HISTORICAL_MARKERS)


def contains_other_person_marker(text: str) -> bool:
    normalized = normalize_text(text)
    return any(marker in normalized for marker in _OTHER_PERSON_MARKERS)


def contains_ambiguity_marker(text: str) -> bool:
    normalized = normalize_text(text)
    return any(marker in normalized for marker in _AMBIGUITY_MARKERS)


def contains_direct_symptom_marker(text: str) -> bool:
    normalized = normalize_text(text)
    return any(marker in normalized for marker in _DIRECT_SYMPTOM_MARKERS)


def contains_bodily_marker(text: str) -> bool:
    normalized = normalize_text(text)
    return any(marker in normalized for marker in _BODILY_MARKERS)
