"""Unified diagnostic-standard ontology access helpers."""
from __future__ import annotations

import copy
import json
from enum import Enum
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).parent / "data"
_MAPPING_PATH = _DATA_DIR / "icd10_to_dsm5_mapping.json"
_CRITERIA_CACHE: dict["DiagnosticStandard", dict[str, Any]] = {}
_MAPPING_CACHE: dict[str, Any] | None = None


class DiagnosticStandard(str, Enum):
    """Supported diagnostic criteria backends."""

    ICD10 = "icd10"
    DSM5 = "dsm5"


def _normalize_standard(
    standard: DiagnosticStandard | str,
) -> DiagnosticStandard:
    if isinstance(standard, DiagnosticStandard):
        return standard

    normalized = str(standard).strip().lower().replace("-", "")
    if not normalized:
        raise ValueError("Diagnostic standard must be provided.")

    for candidate in DiagnosticStandard:
        if candidate.value == normalized:
            return candidate

    raise ValueError(f"Unsupported diagnostic standard: {standard!r}")


def _normalize_icd_code(code: str | None) -> str | None:
    if code is None:
        return None
    normalized = str(code).strip().upper()
    return normalized or None


def _criteria_path(standard: DiagnosticStandard | str) -> Path:
    normalized = _normalize_standard(standard)
    return _DATA_DIR / f"{normalized.value}_criteria.json"


def _load_standard_blob(
    standard: DiagnosticStandard | str,
) -> dict[str, Any]:
    normalized = _normalize_standard(standard)
    cached = _CRITERIA_CACHE.get(normalized)
    if cached is not None:
        return cached

    path = _criteria_path(normalized)
    if not path.exists():
        raise FileNotFoundError(
            f"Criteria file not found for standard {normalized.value}: {path}"
        )

    with open(path, encoding="utf-8") as f:
        blob = json.load(f)

    _CRITERIA_CACHE[normalized] = blob
    return blob


def _load_mapping() -> dict[str, Any]:
    global _MAPPING_CACHE
    if _MAPPING_CACHE is None:
        with open(_MAPPING_PATH, encoding="utf-8") as f:
            _MAPPING_CACHE = json.load(f)
    return _MAPPING_CACHE


def load_criteria(
    standard: DiagnosticStandard | str,
) -> dict[str, dict[str, Any]]:
    """Return a deep copy of the disorder-keyed criteria mapping."""
    return copy.deepcopy(_load_standard_blob(standard)["disorders"])


def list_disorders(standard: DiagnosticStandard | str) -> list[str]:
    """Return all disorder codes for a standard."""
    return list(_load_standard_blob(standard)["disorders"].keys())


def get_disorder_criteria(
    disorder_code: str,
    standard: DiagnosticStandard | str,
) -> dict[str, Any] | None:
    """Return a deep copy of one disorder definition, or None."""
    normalized_code = _normalize_icd_code(disorder_code)
    if normalized_code is None:
        return None
    disorder = _load_standard_blob(standard)["disorders"].get(normalized_code)
    if disorder is None:
        return None
    return copy.deepcopy(disorder)


def get_disorder_name(
    disorder_code: str,
    standard: DiagnosticStandard | str,
    lang: str = "en",
) -> str | None:
    """Return the disorder display name in the requested language."""
    disorder = get_disorder_criteria(disorder_code, standard)
    if disorder is None:
        return None
    key = "name_zh" if str(lang).lower().startswith("zh") else "name"
    return disorder.get(key)


def get_disorder_threshold(
    disorder_code: str,
    standard: DiagnosticStandard | str,
) -> dict[str, Any]:
    """Return a deep copy of a disorder threshold dict, or {}."""
    disorder = get_disorder_criteria(disorder_code, standard)
    if disorder is None:
        return {}
    return copy.deepcopy(disorder.get("threshold", {}))


def paper_parent_icd10(code: str | None) -> str | None:
    """Collapse an ICD-10 subcode to its parent family code."""
    normalized = _normalize_icd_code(code)
    if normalized is None:
        return None
    return normalized.split(".", 1)[0]


def icd10_to_dsm5(code: str | None) -> str | None:
    """Translate an ICD-10 code into a DSM-5 code when mapped."""
    normalized = _normalize_icd_code(code)
    if normalized is None:
        return None

    mappings = _load_mapping()["mappings"]
    entry = mappings.get(normalized)
    if entry is not None:
        return entry.get("dsm5_code")

    parent = paper_parent_icd10(normalized)
    if parent and parent != normalized:
        parent_entry = mappings.get(parent)
        if parent_entry is not None:
            return parent_entry.get("dsm5_code")

    return None


def dsm5_to_icd10(code: str | None) -> list[str]:
    """Translate a DSM-5 code back to all matching ICD-10 codes."""
    if code is None:
        return []

    normalized = str(code).strip().lower()
    if not normalized:
        return []

    matches: list[str] = []
    for icd10_code, entry in _load_mapping()["mappings"].items():
        dsm5_code = entry.get("dsm5_code")
        if dsm5_code is None:
            continue
        if str(dsm5_code).strip().lower() == normalized:
            matches.append(icd10_code)
    return matches


def _clear_cache() -> None:
    """Clear cached criteria and mapping data (for testing only)."""
    global _MAPPING_CACHE
    _CRITERIA_CACHE.clear()
    _MAPPING_CACHE = None


__all__ = [
    "DiagnosticStandard",
    "dsm5_to_icd10",
    "get_disorder_criteria",
    "get_disorder_name",
    "get_disorder_threshold",
    "icd10_to_dsm5",
    "list_disorders",
    "load_criteria",
    "paper_parent_icd10",
]
