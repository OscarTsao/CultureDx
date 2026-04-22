"""ICD-10 diagnostic criteria definitions and lookup."""
from __future__ import annotations

from typing import Any

from culturedx.ontology.standards import (
    DiagnosticStandard,
    _clear_cache as _clear_standard_cache,
    _load_standard_blob,
    get_disorder_criteria as _get_disorder_entry,
    get_disorder_name as _get_disorder_name,
    get_disorder_threshold as _get_disorder_threshold,
    list_disorders as _list_disorders,
    load_criteria as _load_criteria,
)


def _load() -> dict[str, Any]:
    return _load_standard_blob(DiagnosticStandard.ICD10)


def load_criteria() -> dict:
    """Return the full disorder-keyed criteria dict (deep copy for safety)."""
    return _load_criteria(DiagnosticStandard.ICD10)


def list_disorders() -> list[str]:
    """Return all disorder codes."""
    return _list_disorders(DiagnosticStandard.ICD10)


def get_disorder_criteria(disorder_code: str) -> dict | None:
    """Return criteria dict for a disorder, or None if not found."""
    disorder = _get_disorder_entry(disorder_code, DiagnosticStandard.ICD10)
    if disorder is None:
        return None
    criteria = disorder.get("criteria")
    if criteria is None:
        return None
    return criteria


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
    return _get_disorder_name(
        disorder_code,
        DiagnosticStandard.ICD10,
        lang=language,
    )


def get_disorder_threshold(disorder_code: str) -> dict:
    """Return the threshold dict for a disorder, or {} if not found."""
    return _get_disorder_threshold(disorder_code, DiagnosticStandard.ICD10)


def _clear_cache() -> None:
    """Clear module cache (for testing only)."""
    _clear_standard_cache()
