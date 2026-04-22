"""Validate the draft DSM-5 criteria file against the ICD-10 coverage set."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
ICD10_PATH = REPO_ROOT / "src" / "culturedx" / "ontology" / "data" / "icd10_criteria.json"
DSM5_PATH = REPO_ROOT / "src" / "culturedx" / "ontology" / "data" / "dsm5_criteria.json"
REQUIRED_LOSSY_CODES = {"F41.2", "F43.2", "F45", "F51", "F98"}


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    icd10 = _load_json(ICD10_PATH)["disorders"]
    dsm5_root = _load_json(DSM5_PATH)
    dsm5 = dsm5_root["disorders"]

    errors: list[str] = []

    missing = sorted(set(icd10) - set(dsm5))
    extra = sorted(set(dsm5) - set(icd10))
    if missing:
        errors.append(f"Missing DSM-5 counterparts for ICD-10 codes: {', '.join(missing)}")
    if extra:
        errors.append(f"Unexpected DSM-5 draft keys not present in ICD-10 source: {', '.join(extra)}")

    for code, disorder in dsm5.items():
        if disorder.get("verification_status") != "UNVERIFIED_LLM_DRAFT":
            errors.append(
                f"{code}: verification_status must be UNVERIFIED_LLM_DRAFT, got {disorder.get('verification_status')!r}"
            )
        if not disorder.get("name_zh"):
            errors.append(f"{code}: missing name_zh")
        if not disorder.get("source_note_zh"):
            errors.append(f"{code}: missing source_note_zh")

    for code in sorted(REQUIRED_LOSSY_CODES):
        disorder = dsm5.get(code)
        if disorder is None:
            continue
        if disorder.get("is_lossy_reasoning") is not True:
            errors.append(f"{code}: required lossy case is not flagged with is_lossy_reasoning=true")

    f412 = dsm5.get("F41.2")
    if f412 is None:
        errors.append("F41.2: missing required mixed anxiety/depression stub")
    else:
        if not f412.get("dsm5_reasoning_fallback"):
            errors.append("F41.2: missing dsm5_reasoning_fallback")
        if not f412.get("dsm5_reasoning_fallback_zh"):
            errors.append("F41.2: missing dsm5_reasoning_fallback_zh")

    print("DSM-5 criteria draft validation")
    print(f"- ICD-10 disorders: {len(icd10)}")
    print(f"- DSM-5 draft disorders: {len(dsm5)}")
    print(f"- Required lossy flags checked: {', '.join(sorted(REQUIRED_LOSSY_CODES))}")

    if errors:
        print(f"- Validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"  * {error}")
        return 1

    print("- Validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
