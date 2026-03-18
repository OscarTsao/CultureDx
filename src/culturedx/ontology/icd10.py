"""ICD-10 diagnostic criteria definitions and lookup."""
from __future__ import annotations

import json
from pathlib import Path

_CRITERIA_PATH = Path(__file__).parent / "data" / "icd10_criteria.json"
_CACHE: dict | None = None


def _load() -> dict:
    global _CACHE
    if _CACHE is None:
        with open(_CRITERIA_PATH, encoding="utf-8") as f:
            _CACHE = json.load(f)
    return _CACHE


def load_criteria() -> dict:
    """Return the full disorder-keyed criteria dict."""
    return _load()["disorders"]


def list_disorders() -> list[str]:
    """Return all disorder codes."""
    return list(load_criteria().keys())


def get_disorder_criteria(disorder_code: str) -> dict | None:
    """Return criteria dict for a disorder, or None if not found."""
    return load_criteria().get(disorder_code, {}).get("criteria")


def get_criterion_text(
    disorder_code: str, criterion_id: str, language: str = "en"
) -> str | None:
    """Return criterion text in the specified language, or None."""
    criteria = get_disorder_criteria(disorder_code)
    if criteria is None or criterion_id not in criteria:
        return None
    key = "text_zh" if language == "zh" else "text"
    return criteria[criterion_id].get(key)


def get_disorder_name(disorder_code: str, language: str = "en") -> str | None:
    """Return disorder name in the specified language, or None."""
    disorders = load_criteria()
    if disorder_code not in disorders:
        return None
    key = "name_zh" if language == "zh" else "name"
    return disorders[disorder_code].get(key)
