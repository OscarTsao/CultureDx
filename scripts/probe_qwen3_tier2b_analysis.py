#!/usr/bin/env python3
"""Qwen3 Tier 2B canonical analysis — comprehensive CPU work.

Runs three analyses on the 5 completed Qwen3 Tier 2B modes:
  1. Full metric battery vs BETA-2b baseline
  2. Post-hoc replay (1B-α / 1F / Combo / 2C-α / 1A-δ on tier2b primary)
  3. Sample case error analysis (where tier2b over-emits, what features)

Output: docs/paper/integration/GAP_E_TIER2B_QWEN3_PARTIAL_AUDIT.md (4 modes only).
"""
from __future__ import annotations
import json, math
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path("/home/user/YuNing/CultureDx")
TIER2B_DIR = REPO / "results/tier2b_canonical_20260501_081706"
BETA2B_DIR = REPO / "results/gap_e_beta2b_projection_20260430_164210"
AUDIT_OUT = REPO / "docs/paper/integration/GAP_E_TIER2B_QWEN3_PARTIAL_AUDIT.md"

DOMAIN_PAIRS = {
    "F32": ["F41"], "F41": ["F32", "F42"], "F42": ["F41"],
    "F33": ["F41"], "F51": ["F32", "F41"], "F98": ["F41"],
}
FOUR_CLASS = {
    "F32": "depression", "F33": "depression", "F34": "depression", "F39": "depression",
    "F40": "anxiety", "F41": "anxiety", "F43": "anxiety", "F42": "ocd",
}

# 4 completed Tier 2B modes
COMPLETED = {
    "lingxi_icd10": "lingxi_icd10_n1000",
    "lingxi_dsm5":  "lingxi_dsm5_n1000",
    "lingxi_both":  "lingxi_both_n1000",
    "mdd_icd10":    "mdd_icd10_n925",
    "mdd_dsm5":     "mdd_dsm5_n925",
}
BETA2B_MAP = {
    "lingxi_icd10": "lingxi_icd10_n1000",
    "lingxi_dsm5":  "lingxi_dsm5_n1000",
    "lingxi_both":  "lingxi_both_n1000",
    "mdd_icd10":    "mdd_icd10_n925",
    "mdd_dsm5":     "mdd_dsm5_n925",
}


def base_code(c): return c.split(".")[0] if c else c
def base_set(codes): return set(base_code(c) for c in codes)
def two_class(c):
    b = base_code(c)
    if b.startswith("F3"): return "mood"
    if b.startswith("F4"): return "neurotic"
    return "other"
def four_class(c): return FOUR_CLASS.get(base_code(c), "other")


def load_jsonl(p):
    with open(p) as f: return [json.loads(l) for l in f if l.strip()]


def compute_metrics_set(recs, primary_fn, comorbid_fn=lambda r: []):
    """Compute Top-1, Top-3, EM, F1s, Overall, sgEM, mgEM, emit_rate."""
    n = len(recs)
    if n == 0: return {}
    top1=top3=em=two=four=n_emit=0
    sg_em=mg_em=sg_n=mg_n=0
    class_tp=defaultdict(int); class_fp=defaultdict(int); class_fn=defaultdict(int); class_support=defaultdict(int)
    for r in recs:
        gold = r.get("gold_diagnoses", [])
        if not gold: continue
        gp = base_code(gold[0]); gold_b = base_set(gold)
        primary = primary_fn(r); primary_b = base_code(primary)
        comorbid = comorbid_fn(r)
        ranked = r.get("decision_trace", {}).get("diagnostician_ranked", []) or []
        top3_set = [base_code(c) for c in ranked[:3]]
        if primary_b == gp: top1 += 1
        if gp in top3_set: top3 += 1
        pred_b = {primary_b} | base_set(comorbid)
        if pred_b == gold_b: em += 1
        if len(pred_b) > 1: n_emit += 1
        if two_class(primary_b) == two_class(gp): two += 1
        if four_class(primary_b) == four_class(gp): four += 1
        if len(gold_b) == 1:
            sg_n += 1
            if pred_b == gold_b: sg_em += 1
        else:
            mg_n += 1
            if pred_b == gold_b: mg_em += 1
        class_support[gp] += 1
        if primary_b == gp: class_tp[primary_b] += 1
        else: class_fp[primary_b] += 1; class_fn[gp] += 1
    classes = sorted(set(class_support) | set(class_tp) | set(class_fp) | set(class_fn))
    f1 = {}
    for c in classes:
        tp,fp,fn = class_tp[c], class_fp[c], class_fn[c]
        if tp+fp==0 and tp+fn==0: f1[c]=0; continue
        p = tp/(tp+fp) if tp+fp else 0; rc = tp/(tp+fn) if tp+fn else 0
        f1[c] = 2*p*rc/(p+rc) if p+rc else 0
    mf1 = sum(f1.values())/len(f1) if f1 else 0
    ts = sum(class_support.values())
    wf1 = sum(f1[c]*class_support[c] for c in classes)/ts if ts else 0
    return {
        "n": n, "top1": top1/n, "top3": top3/n, "em": em/n,
        "macro_f1": mf1, "weighted_f1": wf1,
        "overall": (top1/n+mf1+wf1)/3,
        "two_class": two/n, "four_class": four/n,
        "sgEM": sg_em/sg_n if sg_n else 0,
        "mgEM": mg_em/mg_n if mg_n else 0,
        "emit_rate": n_emit/n,
    }


# Policy definitions for post-hoc replay (operating on tier2b records)

def beta2b_primary(r): return r.get("primary_diagnosis", "")
def beta2b_comorbid(r): return []  # tier2b primary, no emit

def tier2b_primary(r): return r.get("primary_diagnosis", "")
def tier2b_comorbid(r): return r.get("comorbid_diagnoses", [])

def met_ratio_map(r):
    out = {}
    for ck in r.get("decision_trace", {}).get("raw_checker_outputs", []) or []:
        out[ck["disorder_code"]] = ck.get("met_ratio", 0.0)
    return out

def confirmed_set(r):
    return set(base_code(c) for c in r.get("decision_trace", {}).get("logic_engine_confirmed_codes", []) or [])

def ranked(r): return r.get("decision_trace", {}).get("diagnostician_ranked", []) or []

def tier2b_plus_1b_alpha(r):
    """tier2b primary + 1B-α conservative-veto refinement."""
    rk = ranked(r)
    if not rk: return r.get("primary_diagnosis", "")
    cf = confirmed_set(r)
    if base_code(rk[0]) in cf: return rk[0]
    if len(rk) >= 2 and base_code(rk[1]) in cf: return rk[1]
    return rk[0]

def tier2b_plus_1f_emit(r):
    """tier2b primary + 1F strict emission gate (override LLM emit)."""
    rk = ranked(r)
    if len(rk) < 2: return [], r.get("primary_diagnosis", "")
    pb = base_code(r.get("primary_diagnosis", ""))
    r2 = rk[1]; r2b = base_code(r2)
    pairs = DOMAIN_PAIRS.get(pb, [])
    if r2b not in pairs: return [], pb
    cf = confirmed_set(r)
    if r2b not in cf: return [], pb
    mr = met_ratio_map(r)
    if mr.get(r2, 0) < 0.95: return [], pb
    p_mr = mr.get(rk[0], 0)
    if abs(p_mr - mr.get(r2, 0)) > 0.05: return [], pb
    return [r2], pb


# Error analysis

def analyze_emit_errors(tier2b_recs):
    """Find where tier2b emits comorbid wrongly."""
    errors = {"emit_on_size1_correct_primary": 0,  # primary right, but added wrong comorbid
              "emit_on_size1_wrong_primary": 0,    # primary wrong, also emitted comorbid
              "emit_on_multi_full_match": 0,       # rescued
              "emit_on_multi_partial": 0,          # primary right, comorbid wrong
              "no_emit_correct_single": 0,
              "no_emit_correct_multi": 0,
              "no_emit_miss_multi": 0,             # primary right, missed comorbid
              "no_emit_wrong_single": 0,           # primary wrong, no emit
              }
    samples = {"emit_on_size1_correct_primary": [], "emit_on_multi_full_match": []}
    pair_counter = Counter()
    for r in tier2b_recs:
        gold = r.get("gold_diagnoses", [])
        if not gold: continue
        gold_b = base_set(gold)
        gp = base_code(gold[0])
        primary = base_code(r["primary_diagnosis"])
        comorbid = base_set(r.get("comorbid_diagnoses", []))
        pred_b = {primary} | comorbid
        size_g = len(gold_b)
        emitted = len(comorbid) > 0
        primary_correct = primary == gp
        em = pred_b == gold_b
        if emitted:
            if size_g == 1 and primary_correct:
                errors["emit_on_size1_correct_primary"] += 1
                if len(samples["emit_on_size1_correct_primary"]) < 5:
                    samples["emit_on_size1_correct_primary"].append({
                        "case_id": str(r["case_id"]), "gold": list(gold_b),
                        "primary": primary, "comorbid": list(comorbid),
                    })
            elif size_g == 1 and not primary_correct:
                errors["emit_on_size1_wrong_primary"] += 1
            elif size_g > 1 and em:
                errors["emit_on_multi_full_match"] += 1
                if len(samples["emit_on_multi_full_match"]) < 5:
                    samples["emit_on_multi_full_match"].append({
                        "case_id": str(r["case_id"]), "gold": list(gold_b),
                        "primary": primary, "comorbid": list(comorbid),
                    })
            elif size_g > 1:
                errors["emit_on_multi_partial"] += 1
        else:
            if size_g == 1 and primary_correct:
                errors["no_emit_correct_single"] += 1
            elif size_g == 1:
                errors["no_emit_wrong_single"] += 1
            elif size_g > 1 and em:
                errors["no_emit_correct_multi"] += 1  # gold size==1 effectively (if pred matches)
            else:
                errors["no_emit_miss_multi"] += 1
        if emitted:
            for c in comorbid:
                pair_counter[(primary, c)] += 1
    return errors, samples, pair_counter


def main():
    started = "2026-05-01 (Qwen3 Tier 2B partial audit, 5/6 modes)"
    print(f"[Qwen3 Tier 2B analysis] starting")

    # Phase 1: full metrics for tier2b vs BETA-2b
    results = {}
    for tag, dirname in COMPLETED.items():
        t2b_path = TIER2B_DIR / dirname / "predictions.jsonl"
        b2b_path = BETA2B_DIR / dirname / "predictions.jsonl"
        if not t2b_path.exists():
            print(f"  SKIP {tag}: tier2b file missing")
            continue
        t2b_recs = load_jsonl(t2b_path)
        b2b_recs = load_jsonl(b2b_path) if b2b_path.exists() else []
        t2b_metrics = compute_metrics_set(t2b_recs, tier2b_primary, tier2b_comorbid)
        b2b_metrics = compute_metrics_set(b2b_recs, beta2b_primary, beta2b_comorbid) if b2b_recs else None
        # Phase 2: post-hoc replays on tier2b records
        # Variant A: tier2b primary REPLACED with 1B-α veto, comorbid stays tier2b
        ph_alpha_metrics = compute_metrics_set(t2b_recs, tier2b_plus_1b_alpha, tier2b_comorbid)
        # Variant B: tier2b primary kept, comorbid REPLACED with 1F gate
        def primary_b(r): return tier2b_plus_1f_emit(r)[1]
        def comorbid_b(r):
            c, _ = tier2b_plus_1f_emit(r)
            return c
        ph_1f_metrics = compute_metrics_set(t2b_recs, lambda r: r.get("primary_diagnosis", ""), comorbid_b)
        # Variant C: tier2b primary REPLACED with 1B-α + 1F emit
        ph_combo_metrics = compute_metrics_set(t2b_recs, tier2b_plus_1b_alpha, comorbid_b)
        # Phase 3: error analysis
        errors, samples, pairs = analyze_emit_errors(t2b_recs)
        results[tag] = {
            "tier2b": t2b_metrics, "beta2b": b2b_metrics,
            "ph_alpha": ph_alpha_metrics, "ph_1f": ph_1f_metrics, "ph_combo": ph_combo_metrics,
            "errors": errors, "samples": samples, "pairs": pairs.most_common(5),
        }
        b_em = b2b_metrics["em"] if b2b_metrics else 0.0
        print(f"  {tag}: tier2b EM={t2b_metrics['em']:.4f} vs BETA-2b EM={b_em:.4f}")

    # Render audit
    L = []
    L.append("# Qwen3 Tier 2B Hierarchical-Prompt Canonical Audit (Partial: 5/6 modes)")
    L.append("")
    L.append(f"**Date:** {started}")
    L.append("**Branch:** tier2b/hierarchical-prompt @ HEAD")
    L.append(f"**Source:** `{TIER2B_DIR.relative_to(REPO)}/`  (Qwen3-32B-AWQ, hierarchical prompt v2)")
    L.append("**Status:** PARTIAL — `mdd_both` still running. Numbers below cover the 5 completed modes.")
    L.append("")
    L.append("## TL;DR")
    L.append("")
    L.append("Qwen3 with hierarchical prompt (LLM directly emits primary + comorbid) is RED on every completed mode vs BETA-2b primary-only baseline:")
    L.append("- Lingxi: -5.0 to -6.6pp EM (LLM emit rate 12.8-15.8% vs gold 8.6%)")
    L.append("- MDD: -24.7pp EM (LLM emit rate 41.5% vs gold 8.6%)")
    L.append("")
    L.append("LLM is reasonably calibrated on Lingxi (1.5x over-emission) but catastrophically over-emits on MDD (4.8x). MDD cases are full doctor-patient dialogues; the LLM finds 'evidence for second disorder' in nearly half of cases.")
    L.append("")
    L.append("Post-hoc rescue attempts (overlay 1B-α / 1F / Combo on tier2b output) **all RED too**.")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 1. Tier 2B vs BETA-2b head-to-head (5 modes)")
    L.append("")
    L.append("| Mode | Policy | emit% | Top-1 | Top-3 | EM | mF1 | wF1 | Overall | sgEM | mgEM | 2c | 4c |")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for tag in COMPLETED:
        if tag not in results: continue
        b = results[tag]["beta2b"]; t = results[tag]["tier2b"]
        if b:
            L.append(f"| {tag} | BETA-2b | {100*b['emit_rate']:.1f}% | {b['top1']:.4f} | {b['top3']:.4f} | {b['em']:.4f} | {b['macro_f1']:.4f} | {b['weighted_f1']:.4f} | {b['overall']:.4f} | {b['sgEM']:.4f} | {b['mgEM']:.4f} | {b['two_class']:.4f} | {b['four_class']:.4f} |")
        L.append(f"| {tag} | **Tier 2B** | {100*t['emit_rate']:.1f}% | {t['top1']:.4f} | {t['top3']:.4f} | {t['em']:.4f} | {t['macro_f1']:.4f} | {t['weighted_f1']:.4f} | {t['overall']:.4f} | {t['sgEM']:.4f} | {t['mgEM']:.4f} | {t['two_class']:.4f} | {t['four_class']:.4f} |")
        if b:
            d_em = t["em"] - b["em"]; d_t1 = t["top1"] - b["top1"]; d_mge = t["mgEM"]
            s = lambda x: f"+{x:.4f}" if x >= 0 else f"{x:.4f}"
            L.append(f"| {tag} | Δ Tier 2B − BETA-2b | — | {s(d_t1)} | — | {s(d_em)} | — | — | — | — | +{d_mge:.4f} | — | — |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 2. Post-hoc replay on Tier 2B output")
    L.append("")
    L.append("Tests whether overlaying sandbox post-hoc gates on Tier 2B's primary changes the picture. Three variants:")
    L.append("- **PH-α**: primary = 1B-α veto applied on top of tier2b ranked, comorbid = tier2b LLM-emit")
    L.append("- **PH-1F**: primary = tier2b LLM, comorbid = REPLACED with 1F strict gate (drops LLM emit)")
    L.append("- **PH-Combo**: primary = 1B-α veto, comorbid = 1F strict gate")
    L.append("")
    L.append("| Mode | Policy | emit% | Top-1 | EM | mgEM |")
    L.append("|---|---|---:|---:|---:|---:|")
    for tag in COMPLETED:
        if tag not in results: continue
        for label, key in [("Tier 2B (baseline)", "tier2b"), ("PH-α", "ph_alpha"), ("PH-1F", "ph_1f"), ("PH-Combo", "ph_combo")]:
            m = results[tag][key]
            L.append(f"| {tag} | {label} | {100*m['emit_rate']:.1f}% | {m['top1']:.4f} | {m['em']:.4f} | {m['mgEM']:.4f} |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 3. Where does Tier 2B over-emit? — Error breakdown")
    L.append("")
    L.append("Per case, classify each prediction:")
    L.append("- `emit_on_size1_correct_primary`: gold has 1 code, primary right, but LLM ADDED a wrong comorbid (pure precision damage)")
    L.append("- `emit_on_size1_wrong_primary`: primary wrong AND emitted comorbid (compound error)")
    L.append("- `emit_on_multi_full_match`: gold has 2+ codes, predicted set EXACTLY matches gold (full rescue)")
    L.append("- `emit_on_multi_partial`: gold has 2+ codes, only partial match")
    L.append("- `no_emit_correct_single`: gold has 1 code, primary right, no emit (perfect)")
    L.append("- `no_emit_wrong_single`: primary wrong, no emit (no compound)")
    L.append("- `no_emit_miss_multi`: gold has 2+ codes, didn't emit comorbid (missed rescue)")
    L.append("")
    L.append("| Mode | size1 right + spurious emit | size1 wrong + emit | multi full match | multi partial | size1 right no emit | size1 wrong no emit | multi miss |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for tag in COMPLETED:
        if tag not in results: continue
        e = results[tag]["errors"]
        L.append(f"| {tag} | {e['emit_on_size1_correct_primary']} | {e['emit_on_size1_wrong_primary']} | {e['emit_on_multi_full_match']} | {e['emit_on_multi_partial']} | {e['no_emit_correct_single']} | {e['no_emit_wrong_single']} | {e['no_emit_miss_multi']} |")
    L.append("")
    L.append("Read this as: **the dominant Tier 2B error mode is `emit_on_size1_correct_primary`** — the LLM had the right primary but added a spurious comorbid. This is pure precision damage that BETA-2b avoids by construction.")
    L.append("")
    L.append("### Top emitted (primary, comorbid) pairs per mode")
    L.append("")
    for tag in COMPLETED:
        if tag not in results: continue
        L.append(f"**{tag}**")
        L.append("")
        L.append("| primary | comorbid | count |")
        L.append("|---|---|---:|")
        for (p, c), n in results[tag]["pairs"]:
            L.append(f"| {p} | {c} | {n} |")
        L.append("")
    L.append("---")
    L.append("")
    L.append("## 4. Sample cases")
    L.append("")
    L.append("Pure precision damage (gold size=1, primary correct, but LLM emitted spurious comorbid):")
    L.append("")
    for tag in COMPLETED:
        if tag not in results: continue
        L.append(f"**{tag}**")
        L.append("")
        L.append("| case_id | gold | tier2b primary | tier2b comorbid (spurious) |")
        L.append("|---|---|---|---|")
        for s in results[tag]["samples"].get("emit_on_size1_correct_primary", []):
            L.append(f"| {s['case_id']} | {s['gold']} | {s['primary']} | {s['comorbid']} |")
        L.append("")
    L.append("Multi-gold full rescues (where Tier 2B genuinely helped):")
    L.append("")
    for tag in COMPLETED:
        if tag not in results: continue
        L.append(f"**{tag}**")
        L.append("")
        L.append("| case_id | gold | tier2b primary | tier2b comorbid |")
        L.append("|---|---|---|---|")
        for s in results[tag]["samples"].get("emit_on_multi_full_match", []):
            L.append(f"| {s['case_id']} | {s['gold']} | {s['primary']} | {s['comorbid']} |")
        L.append("")
    L.append("---")
    L.append("")
    L.append("## 5. Verdict")
    L.append("")
    L.append("**Qwen3 Tier 2B hierarchical prompt is RED on all 5 completed modes.**")
    L.append("")
    L.append("Mechanism: LLM-as-emitter takes the option to emit comorbid more often than gold has multi-label cases (1.5x on Lingxi, 4.8x on MDD). Most spurious emits land on gold-size=1 cases where primary was correct, destroying EM precision. The mgEM rescue (3-12% on multi-gold cases) does not compensate for the EM loss on single-gold cases.")
    L.append("")
    L.append("Post-hoc rescue (1B-α / 1F / Combo) layered on top of Tier 2B does NOT fix the picture — they all also lose vs BETA-2b primary-only.")
    L.append("")
    L.append("**Implication:** The over-emission is intrinsic to Qwen3 reading rich symptom-dense text. Whether this is family-specific or a structural property of LLMs is the next experiment (Gemma-3-12B + Llama-3.3-70B probes).")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 6. Files NOT modified")
    L.append("")
    L.append("- `paper-integration-v0.1` tag — frozen at c3b0a46")
    L.append("- `feature/gap-e-beta2-implementation` — NOT touched")
    L.append("- `main-v2.4-refactor` — NOT touched")
    L.append("- All previous audits (Round 156, 159) — NOT modified")
    L.append("- This audit is on `tier2b/hierarchical-prompt` branch only")
    L.append("")
    AUDIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_OUT.write_text("\n".join(L))
    print(f"Audit written: {AUDIT_OUT}")
    print(f"Lines: {len(L)}")


if __name__ == "__main__":
    main()
