#!/usr/bin/env python3
"""Gap F preliminary CPU audit.

Three analyses on existing predictions (no GPU, no new LLM calls):
  F0  — Recall@k sweep on Qwen3 BETA-2b projection (k=1,3,5)
        Per-mode + stratified by gold_size
  B2  — Cross-mode candidate union (Lingxi icd10 ∪ dsm5 ∪ both top-5)
  B3  — TF-IDF top-K candidate union with Qwen3 top-5
        (TF-IDF ranked_codes provide an additional candidate source)

Output: docs/paper/integration/GAP_F_PRELIMINARY_AUDIT.md
"""
from __future__ import annotations
import json
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path("/home/user/YuNing/CultureDx")

QWEN_PRED = {
    "lingxi_icd10": REPO / "results/gap_e_beta2b_projection_20260430_164210/lingxi_icd10_n1000/predictions.jsonl",
    "lingxi_dsm5":  REPO / "results/gap_e_beta2b_projection_20260430_164210/lingxi_dsm5_n1000/predictions.jsonl",
    "lingxi_both":  REPO / "results/gap_e_beta2b_projection_20260430_164210/lingxi_both_n1000/predictions.jsonl",
    "mdd_icd10":    REPO / "results/gap_e_beta2b_projection_20260430_164210/mdd_icd10_n925/predictions.jsonl",
    "mdd_dsm5":     REPO / "results/gap_e_beta2b_projection_20260430_164210/mdd_dsm5_n925/predictions.jsonl",
    "mdd_both":     REPO / "results/gap_e_beta2b_projection_20260430_164210/mdd_both_n925/predictions.jsonl",
}

TFIDF_PRED = {
    "lingxidiag16k_full": REPO / "results/generalization/tfidf/train_lingxidiag16k_test_lingxidiag16k/predictions.jsonl",
    "lingxidiag16k_validation_baseline": REPO / "results/validation/tfidf_baseline/predictions.jsonl",
}

AUDIT_OUT = REPO / "docs/paper/integration/GAP_F_PRELIMINARY_AUDIT.md"


def base_code(c): return c.split(".")[0] if c else c
def base_set(codes): return set(base_code(c) for c in codes)

def load_jsonl(p):
    with open(p) as f: return [json.loads(l) for l in f if l.strip()]


def topk_set(rec, k):
    """Get base-coded top-k set from BETA-2b projection record."""
    ranked = rec.get("decision_trace", {}).get("diagnostician_ranked", []) or []
    return set(base_code(c) for c in ranked[:k])


def tfidf_topk_set(rec, k):
    """Get base-coded top-k set from TF-IDF prediction record."""
    ranked = rec.get("ranked_codes", []) or []
    return set(base_code(c) for c in ranked[:k])


# ============== F0 — Recall@k sweep ==============

def f0_recall_audit():
    out = {}
    for tag, path in QWEN_PRED.items():
        if not path.exists(): continue
        recs = load_jsonl(path)
        per_size = defaultdict(lambda: {"n": 0, **{f"k{k}_primary_in": 0 for k in [1,3,5]}, **{f"k{k}_any_in": 0 for k in [1,3,5]}, **{f"k{k}_all_in": 0 for k in [1,3,5]}})
        for rec in recs:
            gold = rec.get("gold_diagnoses", [])
            if not gold: continue
            size = len(gold)
            gold_b = base_set(gold)
            primary_b = base_code(gold[0])
            per_size[size]["n"] += 1
            for k in [1, 3, 5]:
                tk = topk_set(rec, k)
                if primary_b in tk:
                    per_size[size][f"k{k}_primary_in"] += 1
                if gold_b & tk:
                    per_size[size][f"k{k}_any_in"] += 1
                if gold_b.issubset(tk):
                    per_size[size][f"k{k}_all_in"] += 1
        out[tag] = dict(per_size)
    return out


# ============== B2 — Cross-mode candidate union ==============

def b2_cross_mode_union():
    """For Lingxi: union of icd10 + dsm5 + both top-5 per case_id.
       For MDD: same."""
    out = {}
    for prefix in ["lingxi", "mdd"]:
        modes = [f"{prefix}_icd10", f"{prefix}_dsm5", f"{prefix}_both"]
        # Load all 3 modes, key by case_id
        by_mode = {}
        for m in modes:
            by_mode[m] = {str(r["case_id"]): r for r in load_jsonl(QWEN_PRED[m])}
        # Common case_ids
        common = set(by_mode[modes[0]].keys()) & set(by_mode[modes[1]].keys()) & set(by_mode[modes[2]].keys())
        sizes_stats = defaultdict(lambda: {"n": 0,
                                            "single_mode_top5_all_in": 0,
                                            "union_top5_all_in": 0,
                                            "single_mode_top3_all_in": 0,
                                            "union_top3_all_in": 0,
                                            "single_mode_secondary_in_top5": 0,
                                            "union_secondary_in_top5": 0})
        for cid in common:
            recs = [by_mode[m][cid] for m in modes]
            gold = recs[0].get("gold_diagnoses", [])
            if not gold: continue
            size = len(gold)
            gold_b = base_set(gold)
            single_top5 = topk_set(recs[0], 5)  # icd10 alone
            single_top3 = topk_set(recs[0], 3)
            union_top5 = topk_set(recs[0], 5) | topk_set(recs[1], 5) | topk_set(recs[2], 5)
            union_top3 = topk_set(recs[0], 3) | topk_set(recs[1], 3) | topk_set(recs[2], 3)
            sizes_stats[size]["n"] += 1
            if gold_b.issubset(single_top5): sizes_stats[size]["single_mode_top5_all_in"] += 1
            if gold_b.issubset(union_top5): sizes_stats[size]["union_top5_all_in"] += 1
            if gold_b.issubset(single_top3): sizes_stats[size]["single_mode_top3_all_in"] += 1
            if gold_b.issubset(union_top3): sizes_stats[size]["union_top3_all_in"] += 1
            if size >= 2:
                # secondary = gold codes other than primary
                secondary = gold_b - {base_code(gold[0])}
                if secondary.issubset(single_top5): sizes_stats[size]["single_mode_secondary_in_top5"] += 1
                if secondary.issubset(union_top5): sizes_stats[size]["union_secondary_in_top5"] += 1
        out[prefix] = dict(sizes_stats)
    return out


# ============== B3 — TF-IDF candidate union ==============

def b3_tfidf_union():
    out = {}
    # Try lingxi validation baseline
    tfidf_path = TFIDF_PRED["lingxidiag16k_validation_baseline"]
    if not tfidf_path.exists():
        return {"error": "TF-IDF predictions not found"}
    tfidf_recs = load_jsonl(tfidf_path)
    tfidf_by_id = {str(r["case_id"]): r for r in tfidf_recs}
    # Use Qwen lingxi_icd10 as match
    qwen_recs = load_jsonl(QWEN_PRED["lingxi_icd10"])
    sizes_stats = defaultdict(lambda: {"n": 0,
                                        "qwen_top5_all_in": 0,
                                        "tfidf_top5_all_in": 0,
                                        "tfidf_top10_all_in": 0,
                                        "union_top5_all_in": 0,
                                        "qwen_top3_all_in": 0,
                                        "tfidf_top3_all_in": 0,
                                        "union_top3_all_in": 0,
                                        "qwen_secondary_in_top5": 0,
                                        "tfidf_secondary_in_top5": 0,
                                        "union_secondary_in_top5": 0})
    for rec in qwen_recs:
        cid = str(rec["case_id"])
        if cid not in tfidf_by_id: continue
        gold = rec.get("gold_diagnoses", [])
        if not gold: continue
        size = len(gold)
        gold_b = base_set(gold)
        qwen5 = topk_set(rec, 5)
        qwen3 = topk_set(rec, 3)
        tfidf5 = tfidf_topk_set(tfidf_by_id[cid], 5)
        tfidf10 = tfidf_topk_set(tfidf_by_id[cid], 10)
        tfidf3 = tfidf_topk_set(tfidf_by_id[cid], 3)
        union5 = qwen5 | tfidf5
        union3 = qwen3 | tfidf3
        sizes_stats[size]["n"] += 1
        if gold_b.issubset(qwen5): sizes_stats[size]["qwen_top5_all_in"] += 1
        if gold_b.issubset(tfidf5): sizes_stats[size]["tfidf_top5_all_in"] += 1
        if gold_b.issubset(tfidf10): sizes_stats[size]["tfidf_top10_all_in"] += 1
        if gold_b.issubset(union5): sizes_stats[size]["union_top5_all_in"] += 1
        if gold_b.issubset(qwen3): sizes_stats[size]["qwen_top3_all_in"] += 1
        if gold_b.issubset(tfidf3): sizes_stats[size]["tfidf_top3_all_in"] += 1
        if gold_b.issubset(union3): sizes_stats[size]["union_top3_all_in"] += 1
        if size >= 2:
            secondary = gold_b - {base_code(gold[0])}
            if secondary.issubset(qwen5): sizes_stats[size]["qwen_secondary_in_top5"] += 1
            if secondary.issubset(tfidf5): sizes_stats[size]["tfidf_secondary_in_top5"] += 1
            if secondary.issubset(union5): sizes_stats[size]["union_secondary_in_top5"] += 1
    return {"lingxi_icd10": dict(sizes_stats)}


# ============== Render audit ==============

def main():
    import time
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[Gap F preliminary audit] starting {started}")

    f0 = f0_recall_audit()
    b2 = b2_cross_mode_union()
    b3 = b3_tfidf_union()

    L = []
    L.append("# Gap F Preliminary Audit — Candidate-Set Completeness")
    L.append("")
    L.append(f"**Date:** {started}")
    L.append("**Branch:** tier2b/hierarchical-prompt @ HEAD")
    L.append("**Status:** CPU-only preliminary diagnostic. Uncommitted.")
    L.append("**Source family:** BETA-2b CPU projection (`results/gap_e_beta2b_projection_20260430_164210/`).")
    L.append("**Scope:** Three preliminary diagnostics on existing predictions — no new GPU calls.")
    L.append("")
    L.append("## TL;DR")
    L.append("")
    L.append("**Question:** is the bottleneck candidate generation (gold not in top-K) or ranking (gold in top-K but not at rank-1)?")
    L.append("")
    L.append("**Three measurements (no new GPU calls):**")
    L.append("- F0: Recall@k sweep on Qwen3 BETA-2b primary across 6 modes, stratified by gold size")
    L.append("- B2: Cross-mode candidate union (icd10 ∪ dsm5 ∪ both top-5 per case)")
    L.append("- B3: TF-IDF top-K union with Qwen3 top-5 — does a non-LLM candidate source recover missing gold?")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §F0 — Recall@k sweep, Qwen3 BETA-2b projection")
    L.append("")
    L.append("For each mode, stratified by gold size:")
    L.append("- `primary_in_topk`: gold[0] ∈ top-K (matches the standard Top-K metric)")
    L.append("- `any_in_topk`: at least one gold code in top-K")
    L.append("- `all_in_topk`: ALL gold codes in top-K (set ⊆ top-K) — multi-label coverage")
    L.append("")
    for tag, sizes in f0.items():
        L.append(f"### {tag}")
        L.append("")
        L.append("| Gold size | N | k=1 primary | k=1 all | k=3 primary | k=3 any | **k=3 all** | k=5 primary | k=5 any | **k=5 all** |")
        L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for size in sorted(sizes.keys()):
            d = sizes[size]
            n = d["n"]
            row = f"| size={size} | {n} | "
            row += f"{100*d['k1_primary_in']/n:.1f}% | {100*d['k1_all_in']/n:.1f}% | "
            row += f"{100*d['k3_primary_in']/n:.1f}% | {100*d['k3_any_in']/n:.1f}% | **{100*d['k3_all_in']/n:.1f}%** | "
            row += f"{100*d['k5_primary_in']/n:.1f}% | {100*d['k5_any_in']/n:.1f}% | **{100*d['k5_all_in']/n:.1f}%** |"
            L.append(row)
        L.append("")
    L.append("Read this as: **k=3 all** and **k=5 all** are the multi-label set-coverage rates. The headline 'Top-3=0.79' refers only to `k=3 primary`. For size=2 cases, set coverage is much weaker.")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §B2 — Cross-mode candidate union")
    L.append("")
    L.append("Question: does combining ICD-10 + DSM-5 + Both top-5 per case_id recover missing gold codes that single-mode top-5 misses?")
    L.append("")
    L.append("- `single_mode` = ICD-10 top-5 (canonical)")
    L.append("- `union` = ICD-10 ∪ DSM-5 ∪ Both top-5")
    L.append("")
    for prefix, sizes in b2.items():
        L.append(f"### {prefix}")
        L.append("")
        L.append("| Gold size | N | single top-3 all_in | **union top-3 all_in** | single top-5 all_in | **union top-5 all_in** | size≥2: single top-5 secondary_in | **union top-5 secondary_in** |")
        L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for size in sorted(sizes.keys()):
            d = sizes[size]
            n = d["n"]
            sec_single = f"{100*d['single_mode_secondary_in_top5']/n:.1f}%" if size >= 2 else "—"
            sec_union = f"{100*d['union_secondary_in_top5']/n:.1f}%" if size >= 2 else "—"
            L.append(f"| size={size} | {n} | {100*d['single_mode_top3_all_in']/n:.1f}% | **{100*d['union_top3_all_in']/n:.1f}%** | {100*d['single_mode_top5_all_in']/n:.1f}% | **{100*d['union_top5_all_in']/n:.1f}%** | {sec_single} | {sec_union} |")
        L.append("")
    L.append("Read this as: how much does cross-mode candidate union expand recall?")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §B3 — TF-IDF candidate union")
    L.append("")
    L.append("Question: does adding TF-IDF (lexical) top-K to Qwen3 top-5 recover missing gold codes?")
    L.append("Source: TF-IDF baseline on LingxiDiag-16K (`results/validation/tfidf_baseline/predictions.jsonl`).")
    L.append("")
    if "error" in b3:
        L.append(f"⚠ {b3['error']}")
    else:
        for tag, sizes in b3.items():
            L.append(f"### {tag}")
            L.append("")
            L.append("| Gold size | N | Qwen top-5 all | TF-IDF top-5 all | TF-IDF top-10 all | **Union top-5 all** | size≥2 Qwen secondary_in_top5 | **Union secondary_in_top5** |")
            L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
            for size in sorted(sizes.keys()):
                d = sizes[size]
                n = d["n"]
                if n == 0: continue
                sec_q = f"{100*d['qwen_secondary_in_top5']/n:.1f}%" if size >= 2 else "—"
                sec_u = f"{100*d['union_secondary_in_top5']/n:.1f}%" if size >= 2 else "—"
                L.append(f"| size={size} | {n} | {100*d['qwen_top5_all_in']/n:.1f}% | {100*d['tfidf_top5_all_in']/n:.1f}% | {100*d['tfidf_top10_all_in']/n:.1f}% | **{100*d['union_top5_all_in']/n:.1f}%** | {sec_q} | {sec_u} |")
            L.append("")
    L.append("---")
    L.append("")
    L.append("## §Diagnostic verdict")
    L.append("")
    # Compute Lingxi size=2 union vs single from B2
    if "lingxi" in b2 and 2 in b2["lingxi"]:
        d = b2["lingxi"][2]
        n = d["n"]
        s5 = d['single_mode_top5_all_in']/n if n else 0
        u5 = d['union_top5_all_in']/n if n else 0
        delta = u5 - s5
        L.append(f"**Lingxi size=2 cases:** single-mode top-5 all_in_set = {100*s5:.1f}%, cross-mode union top-5 all_in_set = {100*u5:.1f}% (Δ = {100*delta:+.1f}pp).")
    if "lingxi_icd10" in b3.get("lingxi_icd10" , {}) or 2 in b3.get("lingxi_icd10", {}):
        bd = b3["lingxi_icd10"].get(2)
        if bd and bd["n"]:
            qs = bd['qwen_top5_all_in']/bd['n']
            us = bd['union_top5_all_in']/bd['n']
            L.append(f"**Lingxi size=2 + TF-IDF union:** Qwen alone all_in = {100*qs:.1f}%, Qwen+TFIDF union top-5 = {100*us:.1f}% (Δ = {100*(us-qs):+.1f}pp).")
    L.append("")
    L.append("**Verdict (CPU-only evidence):**")
    L.append("- If cross-mode union or TF-IDF union substantially expands recall → MAS candidate-union approach has signal → proceed to GPU probes (Gemma/Llama in flight)")
    L.append("- If neither union expands recall meaningfully → the missing-gold problem is structural (gold codes not derivable from any reasonable candidate source on this benchmark)")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §Files NOT modified")
    L.append("")
    L.append("- `paper-integration-v0.1` tag — frozen at c3b0a46")
    L.append("- `feature/gap-e-beta2-implementation` — NOT touched")
    L.append("- `main-v2.4-refactor` — NOT touched")
    L.append("- All previous audits — NOT modified")
    L.append("- This audit is on `tier2b/hierarchical-prompt` branch only")
    L.append("")
    AUDIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_OUT.write_text("\n".join(L))
    print(f"Audit written: {AUDIT_OUT}")
    print(f"Lines: {len(L)}")


if __name__ == "__main__":
    main()
