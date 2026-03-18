"""ICD-10 diagnostic criteria definitions and lookup."""
from __future__ import annotations

import copy
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
    """Return the full disorder-keyed criteria dict (deep copy for safety)."""
    return copy.deepcopy(_load()["disorders"])


def list_disorders() -> list[str]:
    """Return all disorder codes."""
    return list(_load()["disorders"].keys())


def get_disorder_criteria(disorder_code: str) -> dict | None:
    """Return criteria dict for a disorder, or None if not found."""
    disorders = _load()["disorders"]
    disorder = disorders.get(disorder_code)
    if disorder is None:
        return None
    return copy.deepcopy(disorder.get("criteria"))


def get_criterion_text(
    disorder_code: str, criterion_id: str, language: str = "en"
) -> str | None:
    """Return criterion text in the specified language, or None."""
    disorders = _load()["disorders"]
    disorder = disorders.get(disorder_code)
    if disorder is None:
        return None
    criteria = disorder.get("criteria")
    if criteria is None or criterion_id not in criteria:
        return None
    key = "text_zh" if language == "zh" else "text"
    return criteria[criterion_id].get(key)


def get_disorder_name(disorder_code: str, language: str = "en") -> str | None:
    """Return disorder name in the specified language, or None."""
    disorders = _load()["disorders"]
    if disorder_code not in disorders:
        return None
    key = "name_zh" if language == "zh" else "name"
    return disorders[disorder_code].get(key)


def get_disorder_threshold(disorder_code: str) -> dict:
    """Return the threshold dict for a disorder, or {} if not found."""
    disorders = _load()["disorders"]
    disorder = disorders.get(disorder_code)
    if disorder is None:
        return {}
    return copy.deepcopy(disorder.get("threshold", {}))


def _clear_cache() -> None:
    """Clear module cache (for testing only)."""
    global _CACHE
    _CACHE = None
