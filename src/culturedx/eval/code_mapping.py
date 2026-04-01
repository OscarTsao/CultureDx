"""Disorder code mapping for evaluation.

Maps dataset-level disorder codes to system-level ICD-10 codes,
handling ambiguous codes (F41 -> F41.0/F41.1) and exclusions.
"""
from __future__ import annotations


# Exact matches (dataset code -> system code)
EXACT_MAP: dict[str, str] = {
    "F20": "F20",
    "F31": "F31",
    "F32": "F32",
    "F42": "F42",
    "F45": "F45",
    "F51": "F51",
    "F39": "F39",
    "F98": "F98",
}

# Ambiguous codes that could map to multiple system codes
# The checker evaluates ALL candidates and the differential picks the best
AMBIGUOUS_MAP: dict[str, list[str]] = {
    "F41": ["F41.0", "F41.1"],  # Panic or GAD
    "F43": ["F43.1", "F43.2"],  # PTSD or Adjustment
}

# Codes to exclude from evaluation (not psychiatric diagnoses)
EXCLUDED_CODES = {"Others", "Z71"}

_SYSTEM_CODES = tuple(
    dict.fromkeys(
        [*EXACT_MAP.values(), *(candidate for values in AMBIGUOUS_MAP.values() for candidate in values)]
    )
)
_SYSTEM_CODE_SET = set(_SYSTEM_CODES)


def map_dataset_code(code: str) -> list[str]:
    """Map a dataset diagnosis code to system ICD-10 codes.

    Returns a list of candidate system codes, or an empty list if excluded or
    not covered by the ontology.
    """
    normalized = code.strip()
    if not normalized or normalized in EXCLUDED_CODES:
        return []
    if normalized in EXACT_MAP:
        return [EXACT_MAP[normalized]]
    if normalized in AMBIGUOUS_MAP:
        return list(AMBIGUOUS_MAP[normalized])
    if normalized in _SYSTEM_CODE_SET:
        return [normalized]

    for sys_code in sorted(_SYSTEM_CODES, key=len, reverse=True):
        if sys_code.startswith(normalized) or normalized.startswith(sys_code):
            return [sys_code]

    return []  # unmapped


def map_code_list(codes: list[str]) -> list[str]:
    """Map a code list into evaluation-ready ICD-10 codes.

    Excluded and unmapped labels are dropped. Duplicates are removed while
    preserving order.
    """
    mapped_codes: list[str] = []
    seen: set[str] = set()
    for code in codes:
        for mapped in map_dataset_code(code):
            if mapped not in seen:
                seen.add(mapped)
                mapped_codes.append(mapped)
    return mapped_codes


def is_correct_prediction(predicted_codes: list[str], gold_codes: list[str]) -> bool:
    """Check if prediction matches gold using code mapping.

    Handles ambiguous codes: if gold is F41 and predicted is F41.1, that's
    correct.
    """
    mapped_gold = set(map_code_list(gold_codes))
    mapped_gold.update(
        code.strip()
        for code in gold_codes
        if code.strip() and code.strip() not in EXCLUDED_CODES
    )

    candidate_predictions = map_code_list(predicted_codes)
    candidate_predictions.extend(
        code.strip()
        for code in predicted_codes
        if code.strip() and code.strip() not in EXCLUDED_CODES
    )

    seen_predictions: set[str] = set()
    for predicted in candidate_predictions:
        if predicted in seen_predictions:
            continue
        seen_predictions.add(predicted)
        if predicted in mapped_gold:
            return True
        for gold in mapped_gold:
            if gold.startswith(predicted) or predicted.startswith(gold):
                return True
    return False


__all__ = [
    "AMBIGUOUS_MAP",
    "EXACT_MAP",
    "EXCLUDED_CODES",
    "is_correct_prediction",
    "map_code_list",
    "map_dataset_code",
]
