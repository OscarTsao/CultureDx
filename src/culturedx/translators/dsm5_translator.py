"""Post-hoc ICD-10 to DSM-5 translation helpers."""
from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_MAPPING_PATH = Path(__file__).resolve().parent.parent / "ontology" / "data" / "icd10_to_dsm5_mapping.json"
_CACHE: dict[str, Any] | None = None


@dataclass
class DSM5Result:
    """Machine-readable DSM-5 translation for a single ICD-10 code."""

    icd10_code: str | None
    dsm5_code: str | None
    dsm5_name_en: str | None
    dsm5_name_zh: str | None
    dsm5_category: str | None
    is_lossy: bool
    note: str | None
    fallback_codes: list[str] = field(default_factory=list)


def _load_mapping() -> dict[str, Any]:
    global _CACHE
    if _CACHE is None:
        with open(_MAPPING_PATH, encoding="utf-8") as f:
            _CACHE = json.load(f)
    return _CACHE


def get_mapping_meta() -> dict[str, Any]:
    """Return a defensive copy of the translator metadata."""
    return copy.deepcopy(_load_mapping()["meta"])


def _normalize_code(icd10_code: str | None) -> str | None:
    if icd10_code is None:
        return None
    normalized = str(icd10_code).strip().upper()
    return normalized or None


def _result_from_entry(
    *,
    icd10_code: str | None,
    entry: dict[str, Any],
    note_override: str | None = None,
) -> DSM5Result:
    return DSM5Result(
        icd10_code=icd10_code,
        dsm5_code=entry.get("dsm5_code"),
        dsm5_name_en=entry.get("dsm5_name_en"),
        dsm5_name_zh=entry.get("dsm5_name_zh"),
        dsm5_category=entry.get("dsm5_category"),
        is_lossy=bool(entry.get("is_lossy", False)),
        note=note_override if note_override is not None else entry.get("note"),
        fallback_codes=list(entry.get("fallback_codes", [])),
    )


def translate(icd10_code: str | None) -> DSM5Result:
    """Translate an ICD-10 code into a post-hoc DSM-5 equivalent."""
    normalized = _normalize_code(icd10_code)
    if normalized is None:
        return DSM5Result(
            icd10_code=None,
            dsm5_code=None,
            dsm5_name_en=None,
            dsm5_name_zh=None,
            dsm5_category=None,
            is_lossy=False,
            note="No ICD-10 code provided.",
            fallback_codes=[],
        )

    mappings = _load_mapping()["mappings"]
    exact = mappings.get(normalized)
    if exact is not None:
        return _result_from_entry(icd10_code=normalized, entry=exact)

    if "." in normalized:
        parent = normalized.split(".", 1)[0]
        parent_entry = mappings.get(parent)
        if parent_entry is not None:
            parent_note = parent_entry.get("note")
            fallback_note = f"Used parent-level fallback for unmapped ICD-10 subcode {normalized} via {parent}."
            if parent_note:
                fallback_note = f"{fallback_note} {parent_note}"
            return _result_from_entry(
                icd10_code=normalized,
                entry=parent_entry,
                note_override=fallback_note,
            )

    return DSM5Result(
        icd10_code=normalized,
        dsm5_code=None,
        dsm5_name_en=None,
        dsm5_name_zh=None,
        dsm5_category=None,
        is_lossy=False,
        note=f"No DSM-5 mapping found for ICD-10 code {normalized}.",
        fallback_codes=[],
    )


def translate_prediction_record(pred: dict[str, Any]) -> dict[str, Any]:
    """Return a prediction record augmented with DSM-5 translation fields."""
    enriched = copy.deepcopy(pred)
    primary = translate(enriched.get("primary_diagnosis"))
    comorbid = [translate(code) for code in enriched.get("comorbid_diagnoses") or []]
    gold = [translate(code) for code in enriched.get("gold_diagnoses") or []]

    enriched["dsm5_review_status"] = get_mapping_meta()["review_status"]
    enriched["dsm5_primary"] = asdict(primary)
    enriched["dsm5_primary_code"] = primary.dsm5_code
    enriched["dsm5_comorbid"] = [asdict(result) for result in comorbid]
    enriched["dsm5_comorbid_codes"] = [result.dsm5_code for result in comorbid]
    enriched["dsm5_gold"] = [asdict(result) for result in gold]
    enriched["dsm5_gold_codes"] = [result.dsm5_code for result in gold]
    return enriched


def _clear_cache() -> None:
    """Clear module cache (for testing only)."""
    global _CACHE
    _CACHE = None
