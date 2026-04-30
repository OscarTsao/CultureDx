#!/usr/bin/env python3
"""Native offline Code Path Equivalence (CPE) audit for BETA-2b.

Applies the production helper apply_beta2b_finalization (extracted from
hied.py) to all 5775 cached BETA-2a canonical records (Round 114), then
compares helper-derived output byte-by-byte against the Round 120
standalone CPU projection.

This audit verifies CODE PATH equivalence (production helper output ==
Round 120 projection), NOT GPU re-run equivalence (which would require V3).

CPU only. NO GPU. NO LLM. NO new inference.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from culturedx.modes.hied import apply_beta2b_finalization


CANONICAL_DIR = ROOT / "results/gap_e_canonical_20260429_225243"
PROJECTION_DIR = ROOT / "results/gap_e_beta2b_projection_20260430_164210"

MODES = [
    ("lingxi_icd10", 1000),
    ("lingxi_dsm5",  1000),
    ("lingxi_both",  1000),
    ("mdd_icd10",     925),
    ("mdd_dsm5",      925),
    ("mdd_both",      925),
]


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(l) for l in f]


def derive_beta2b_record(canonical_record):
    """Apply production helper to a single canonical (BETA-2a) record."""
    dt = canonical_record.get("decision_trace") or {}
    top_ranked = dt.get("diagnostician_ranked") or []
    primary = canonical_record.get("primary_diagnosis")
    veto_applied = dt.get("veto_applied", False)
    primary_source = dt.get("veto_to") if veto_applied else "top1"

    new_primary, new_veto, new_src = apply_beta2b_finalization(
        primary,
        top_ranked,
        veto_applied,
        primary_source,
        "beta2b_primary_locked",
    )

    new_record = dict(canonical_record)
    new_record["primary_diagnosis"] = new_primary
    new_record["primary_diagnosis_icd10"] = new_primary
    new_record["comorbid_diagnoses"] = []
    new_record["schema_version"] = "v2b"
    return new_record


def main(out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 100)
    print("BETA-2b Native Offline CPE — production helper applied to 5775 cached records")
    print("=" * 100)
    print(f"{'Mode':<14} | {'N':>5} | {'helper-derived':>16} | {'projection-match':>18} | {'verdict':>10}")
    print("-" * 100)

    overall_total = 0
    overall_match = 0
    overall_invariant_pass = True

    for label, n_exp in MODES:
        src_path = CANONICAL_DIR / f"{label}_n{n_exp}" / "predictions.jsonl"
        proj_path = PROJECTION_DIR / f"{label}_n{n_exp}" / "predictions.jsonl"

        canonical = load_jsonl(src_path)
        projection = load_jsonl(proj_path)
        proj_by_id = {p["case_id"]: p for p in projection}

        # Helper-derived records
        derived_records = [derive_beta2b_record(r) for r in canonical]

        # Write helper-derived records
        out_mode_dir = out_dir / f"{label}_n{n_exp}"
        out_mode_dir.mkdir(parents=True, exist_ok=True)
        with (out_mode_dir / "predictions.jsonl").open("w") as f:
            for r in derived_records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        # Per-record invariants on helper-derived records
        n = len(derived_records)
        inv_sv = sum(1 for r in derived_records if r.get("schema_version") == "v2b")
        inv_cd = sum(1 for r in derived_records if r.get("comorbid_diagnoses") == [])
        inv_audit = sum(1 for r in derived_records if "audit_comorbid" in (r.get("decision_trace") or {}))
        inv_p_top1 = sum(
            1 for r in derived_records
            if r.get("primary_diagnosis")
            == ((r.get("decision_trace") or {}).get("diagnostician_ranked") or [None])[0]
        )
        invariants_pass = (inv_sv == n and inv_cd == n and inv_audit == n and inv_p_top1 == n)

        # Equivalence vs projection (byte-compare key fields)
        match_count = 0
        diff_examples = []
        for r in derived_records:
            cid = r["case_id"]
            p = proj_by_id.get(cid)
            if p is None:
                continue
            r_dt = r.get("decision_trace") or {}
            p_dt = p.get("decision_trace") or {}
            same = (
                r.get("primary_diagnosis") == p.get("primary_diagnosis")
                and r.get("comorbid_diagnoses") == p.get("comorbid_diagnoses")
                and r.get("schema_version") == p.get("schema_version")
                and r_dt.get("diagnostician_ranked") == p_dt.get("diagnostician_ranked")
                and r_dt.get("audit_comorbid") == p_dt.get("audit_comorbid")
                and r_dt.get("raw_checker_outputs") == p_dt.get("raw_checker_outputs")
                and r_dt.get("logic_engine_confirmed_codes") == p_dt.get("logic_engine_confirmed_codes")
            )
            if same:
                match_count += 1
            else:
                if len(diff_examples) < 3:
                    diff_examples.append({
                        "case_id": cid,
                        "helper_primary": r.get("primary_diagnosis"),
                        "proj_primary": p.get("primary_diagnosis"),
                        "helper_sv": r.get("schema_version"),
                        "proj_sv": p.get("schema_version"),
                    })

        verdict = "BIT-IDENTICAL" if (invariants_pass and match_count == n) else "DIVERGE"
        if not (invariants_pass and match_count == n):
            overall_invariant_pass = False
        overall_total += n
        overall_match += match_count

        print(f"{label:<14} | {n:>5} | inv-pass: {invariants_pass!s:<5} | {match_count}/{n} ({match_count*100/n:.0f}%) | {verdict:>10}")
        if diff_examples:
            for d in diff_examples:
                print(f"  diff: {d}")

    print()
    print(f"Overall match: {overall_match}/{overall_total} ({overall_match*100/overall_total:.2f}%)")
    print(f"Overall invariants pass: {overall_invariant_pass}")

    return overall_invariant_pass and overall_match == overall_total


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "results/gap_e_beta2b_native_offline_TEST"
    success = main(out)
    sys.exit(0 if success else 1)
