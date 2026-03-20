"""Somatization symptom ontology: Chinese somatic expressions to criteria mapping."""
from __future__ import annotations

import copy
import json
from pathlib import Path

_MAP_PATH = Path(__file__).parent / "data" / "somatization_map.json"
_CACHE: dict | None = None


def _load() -> dict:
    global _CACHE
    if _CACHE is None:
        with open(_MAP_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        _CACHE = raw["mappings"]
    return _CACHE


def load_somatization_map() -> dict:
    """Return the full symptom-to-criteria mapping dict (deep copy for safety)."""
    return copy.deepcopy(_load())


def lookup_symptom(symptom_text: str) -> dict | None:
    """Look up a symptom in the ontology. Returns entry dict copy or None."""
    entry = _load().get(symptom_text)
    return copy.deepcopy(entry) if entry is not None else None


def get_criteria_for_symptom(symptom_text: str) -> list[str]:
    """Return list of criterion IDs mapped to this symptom, or empty list."""
    entry = _load().get(symptom_text)
    return list(entry["criteria"]) if entry else []


def _clear_cache() -> None:
    """Clear module cache (for testing only)."""
    global _CACHE
    _CACHE = None


def scan_somatic_hints(transcript_text: str, disorder_code: str) -> str | None:
    """Scan transcript for known somatic expressions relevant to a disorder.

    Returns a short hint string for the criterion checker prompt,
    or None if no relevant somatic keywords are found.
    """
    somatization_data = _load()
    hints = []
    seen_criteria: set[str] = set()

    for symptom_text, entry in somatization_data.items():
        if symptom_text in transcript_text:
            criteria = entry.get("criteria", [])
            for crit in criteria:
                if crit.startswith(disorder_code) and crit not in seen_criteria:
                    seen_criteria.add(crit)
                    hints.append(f"- \"{symptom_text}\" → {crit}")

    if not hints:
        return None

    return "以下躯体化表述在对话中被检测到，可能与该障碍的诊断标准相关：\n" + "\n".join(hints)
