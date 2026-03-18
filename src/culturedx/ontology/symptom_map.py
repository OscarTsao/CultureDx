"""Somatization symptom ontology: Chinese somatic expressions to criteria mapping."""
from __future__ import annotations

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
    """Return the full symptom-to-criteria mapping dict."""
    return _load()


def lookup_symptom(symptom_text: str) -> dict | None:
    """Look up a symptom in the ontology. Returns entry dict or None."""
    return _load().get(symptom_text)


def get_criteria_for_symptom(symptom_text: str) -> list[str]:
    """Return list of criterion IDs mapped to this symptom, or empty list."""
    entry = lookup_symptom(symptom_text)
    return entry["criteria"] if entry else []
