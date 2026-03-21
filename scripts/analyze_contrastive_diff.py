#!/usr/bin/env python3
"""Case-level diff: contrastive ON vs OFF.

Usage:
    uv run python scripts/analyze_contrastive_diff.py \
        OFF_DIR ON_DIR CASE_LIST
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.eval.metrics import normalize_icd_code


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Contrastive ON vs OFF case-level diff"
    )
    parser.add_argument("off_dir", help="Contrastive OFF predictions dir")
    parser.add_argument("on_dir", help="Contrastive ON predictions dir")
    parser.add_argument("case_list", help="Path to case_list.json")
    args = parser.parse_args()

    with open(
        Path(args.off_dir) / "predictions.json", encoding="utf-8"
    ) as f:
        off_preds: dict[str, dict] = {
            p["case_id"]: p for p in json.load(f)["predictions"]
        }
    with open(
        Path(args.on_dir) / "predictions.json", encoding="utf-8"
    ) as f:
        on_preds: dict[str, dict] = {
            p["case_id"]: p for p in json.load(f)["predictions"]
        }
    with open(args.case_list, encoding="utf-8") as f:
        gold_map: dict[str, list[str]] = {
            c["case_id"]: c["diagnoses"]
            for c in json.load(f)["cases"]
        }

    helped: list[dict] = []  # wrong->correct
    hurt: list[dict] = []    # correct->wrong
    for cid in off_preds:
        gold = {normalize_icd_code(g) for g in gold_map.get(cid, [])}
        off_dx = normalize_icd_code(
            off_preds[cid]["primary_diagnosis"] or ""
        )
        on_dx = normalize_icd_code(
            on_preds[cid]["primary_diagnosis"] or ""
        )
        off_ok = off_dx in gold
        on_ok = on_dx in gold
        if off_ok and not on_ok:
            hurt.append({
                "case_id": cid,
                "gold": list(gold),
                "off": off_dx,
                "on": on_dx,
                "off_conf": off_preds[cid]["confidence"],
                "on_conf": on_preds[cid]["confidence"],
            })
        elif not off_ok and on_ok:
            helped.append({
                "case_id": cid,
                "gold": list(gold),
                "off": off_dx,
                "on": on_dx,
                "off_conf": off_preds[cid]["confidence"],
                "on_conf": on_preds[cid]["confidence"],
            })

    print(f"Contrastive HELPED: {len(helped)} cases (wrong->correct)")
    for h in helped[:10]:
        print(f"  {h['case_id']}: {h['off']}->{h['on']} gold={h['gold']}")
    print(
        f"\nContrastive HURT: {len(hurt)} cases (correct->wrong)"
    )
    for h in hurt[:10]:
        print(
            f"  {h['case_id']}: {h['off']}->{h['on']} gold={h['gold']} "
            f"off_conf={h['off_conf']:.3f} on_conf={h['on_conf']:.3f}"
        )
    print(f"\nNet: {len(helped) - len(hurt):+d} cases")


if __name__ == "__main__":
    main()
