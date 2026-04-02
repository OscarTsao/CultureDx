#!/usr/bin/env python3
"""Verify CultureDx evaluation aligns with LingxiDiagBench Table 4."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from culturedx.eval.lingxidiag_paper import (
    classify_2class_from_raw,
    classify_4class_from_raw,
    gold_to_parent_list,
    to_paper_parent,
)


def main() -> int:
    errors: list[str] = []

    checks = [
        ("F41.1", "F41"),
        ("F41.0", "F41"),
        ("F43.2", "F43"),
        ("F43.1", "F43"),
        ("F32.900", "F32"),
        ("F39", "F39"),
        ("F98", "F98"),
        ("Z71.9", "Z71"),
        ("F22", "Others"),
        ("F33", "Others"),
        ("F40", "Others"),
        ("F20.0", "F20"),
        ("garbage", "Others"),
    ]
    for code, expected in checks:
        result = to_paper_parent(code)
        if result != expected:
            errors.append(
                f"to_paper_parent({code!r}) = {result!r}, expected {expected!r}"
            )

    assert gold_to_parent_list("F32.100;F41.000") == ["F32", "F41"]
    assert gold_to_parent_list("Z71") == ["Z71"]
    assert gold_to_parent_list("") == ["Others"]
    assert gold_to_parent_list("F99.999") == ["Others"]

    assert classify_2class_from_raw("F32.100") == "Depression"
    assert classify_2class_from_raw("F41.000") == "Anxiety"
    assert classify_2class_from_raw("F32.100;F41.000") is None
    assert classify_2class_from_raw("F41.200") is None
    assert classify_2class_from_raw("F20.000") is None

    assert classify_4class_from_raw("F32.100") == "Depression"
    assert classify_4class_from_raw("F41.000") == "Anxiety"
    assert classify_4class_from_raw("F32.100;F41.000") == "Mixed"
    assert classify_4class_from_raw("F41.200") == "Mixed"
    assert classify_4class_from_raw("F20.000") == "Others"

    if errors:
        print(f"FAILED - {len(errors)} errors:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("All paper-alignment checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
