#!/usr/bin/env python3
"""Gated TF-IDF expansion sweep — when should MAS invoke TF-IDF?

Tests multiple gating criteria for selectively triggering TF-IDF expansion
on Qwen3 candidate pool.

Gates tested:
  G_ALL: always expand (baseline = current "blanket union")
  G_NEVER: never expand (Qwen alone)
  G_LOW_MARGIN: Qwen top1-top2 met_ratio gap small
  G_QWEN_GEMMA_DISAGREE: Qwen and Gemma top-1 differ
  G_PRIMARY_NOT_CONFIRMED: Qwen primary not in confirmed_codes (1B-α-style)
  G_PAIR_F32_F41: Qwen primary is F32/F41/F42 (confusion-pair flag)
  G_CHECKER_AMBIG: confirmed_set has >=3 codes (lots of ambiguity)
  G_ANY_TWO: any two of above triggers fire

For each gate, report:
  expansion_rate (% of cases gate fires)
  size=2 all-gold-coverage with gate
  size=1 average added noise (only on gate-triggered cases)
  size=1 noise per case (averaged over all)

Output: docs/paper/integration/GAP_F_GATED_TFIDF_EXPANSION.md
"""
from __future__ import annotations
import json, time
from pathlib import Path

REPO = Path("/home/user/YuNing/CultureDx")
AUDIT_OUT = REPO / "docs/paper/integration/GAP_F_GATED_TFIDF_EXPANSION.md"

DOMAIN_PAIRS = {
    "F32": ["F41"], "F41": ["F32", "F42"], "F42": ["F41"],
    "F33": ["F41"], "F51": ["F32", "F41"], "F98": ["F41"],
}

def base(c): return c.split('.')[0] if c else c
def base_set(s): return set(base(c) for c in s)


def main():
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[Gated TF-IDF expansion] starting {started}")

    # Load all sources
    qwen_lingxi = [json.loads(l) for l in open(REPO / "results/gap_e_beta2b_projection_20260430_164210/lingxi_icd10_n1000/predictions.jsonl")]
    gemma = {}  # only on size=2 sample
    for l in open(REPO / "results/phase1_recall_probe/gemma3_12b_top5.jsonl"):
        r = json.loads(l)
        gemma[r["case_id"]] = r
    tfidf_lr = {str(r["case_id"]): r for r in (json.loads(l) for l in open(REPO / "results/validation/tfidf_baseline/predictions.jsonl"))}

    print(f"  Qwen Lingxi: {len(qwen_lingxi)}, Gemma: {len(gemma)}, TFIDF+LR: {len(tfidf_lr)}")

    # Build helpers
    def qwen_top5(rec): return base_set(rec.get("decision_trace", {}).get("diagnostician_ranked", [])[:5])
    def qwen_top2(rec):
        rk = rec.get("decision_trace", {}).get("diagnostician_ranked", [])
        return [base(c) for c in rk[:2]]
    def qwen_confirmed(rec): return set(base(c) for c in rec.get("decision_trace", {}).get("logic_engine_confirmed_codes", []))
    def qwen_met_ratios(rec):
        return {co["disorder_code"]: co.get("met_ratio", 0.0) for co in rec.get("decision_trace", {}).get("raw_checker_outputs", []) or []}
    def tfidf_top5(cid): return base_set(tfidf_lr.get(cid, {}).get("ranked_codes", [])[:5])
    def gemma_top5(cid): return base_set(gemma.get(cid, {}).get("top5", [])[:5])

    # Define gates (each returns True = expand)
    def gate_all(rec, cid): return True
    def gate_never(rec, cid): return False
    def gate_low_margin(rec, cid):
        rk = rec.get("decision_trace", {}).get("diagnostician_ranked", [])
        mr = qwen_met_ratios(rec)
        if len(rk) < 2: return False
        gap = abs(mr.get(rk[0], 0) - mr.get(rk[1], 0))
        return gap < 0.05
    def gate_qwen_gemma_disagree(rec, cid):
        rk = qwen_top2(rec)
        if not rk or cid not in gemma: return False
        gemma_top = base(gemma[cid].get("top5", [])[0]) if gemma[cid].get("top5") else None
        return rk[0] != gemma_top
    def gate_primary_not_confirmed(rec, cid):
        rk = rec.get("decision_trace", {}).get("diagnostician_ranked", [])
        if not rk: return False
        return base(rk[0]) not in qwen_confirmed(rec)
    def gate_pair_classes(rec, cid):
        rk = rec.get("decision_trace", {}).get("diagnostician_ranked", [])
        if not rk: return False
        return base(rk[0]) in {"F32", "F41", "F42", "F33", "F51", "F98"}
    def gate_checker_ambig(rec, cid):
        return len(qwen_confirmed(rec)) >= 4
    def gate_any_two(rec, cid):
        triggers = [
            gate_low_margin(rec, cid),
            gate_qwen_gemma_disagree(rec, cid),
            gate_primary_not_confirmed(rec, cid),
            gate_checker_ambig(rec, cid),
        ]
        return sum(triggers) >= 2

    GATES = {
        "G_ALL (always expand)": gate_all,
        "G_NEVER (Qwen alone)": gate_never,
        "G_LOW_MARGIN (top1-top2 met gap <0.05)": gate_low_margin,
        "G_QWEN_GEMMA_DISAGREE": gate_qwen_gemma_disagree,
        "G_PRIMARY_NOT_CONFIRMED (1B-α-style)": gate_primary_not_confirmed,
        "G_PAIR_CLASSES (primary in F3x/F4x)": gate_pair_classes,
        "G_CHECKER_AMBIG (≥4 confirmed)": gate_checker_ambig,
        "G_ANY_TWO (≥2 triggers fire)": gate_any_two,
    }

    # For each gate, compute size=2 coverage AND size=1 noise
    size1 = [r for r in qwen_lingxi if len(r.get("gold_diagnoses", [])) == 1]
    size2 = [r for r in qwen_lingxi if len(r.get("gold_diagnoses", [])) == 2]
    print(f"  size=1: {len(size1)}, size=2: {len(size2)}")

    results = []
    for gate_name, gate_fn in GATES.items():
        # Size=2 metrics
        n_size2 = 0; covered = 0; gate_fired_size2 = 0
        for r in size2:
            cid = str(r["case_id"])
            n_size2 += 1
            gold_b = base_set(r["gold_diagnoses"])
            qwen5 = qwen_top5(r)
            if gate_fn(r, cid):
                gate_fired_size2 += 1
                tfidf5 = tfidf_top5(cid)
                pool = qwen5 | tfidf5
            else:
                pool = qwen5
            if gold_b.issubset(pool): covered += 1
        size2_cov = 100*covered/n_size2 if n_size2 else 0
        size2_fire_rate = 100*gate_fired_size2/n_size2 if n_size2 else 0

        # Size=1 metrics (noise)
        n_size1 = 0; total_noise = 0; gate_fired_size1 = 0
        for r in size1:
            cid = str(r["case_id"])
            n_size1 += 1
            gold = base(r["gold_diagnoses"][0])
            qwen5 = qwen_top5(r)
            if gate_fn(r, cid):
                gate_fired_size1 += 1
                tfidf5 = tfidf_top5(cid)
                pool = qwen5 | tfidf5
            else:
                pool = qwen5
            noise = len(pool) - (1 if gold in pool else 0)
            total_noise += noise
        size1_noise = total_noise/n_size1 if n_size1 else 0
        size1_fire_rate = 100*gate_fired_size1/n_size1 if n_size1 else 0

        results.append({
            "gate": gate_name,
            "size2_fire_rate": size2_fire_rate,
            "size2_coverage": size2_cov,
            "size1_fire_rate": size1_fire_rate,
            "size1_noise": size1_noise,
        })

    # Render audit
    L = []
    L.append("# Gap F Gated TF-IDF Expansion Sweep")
    L.append("")
    L.append(f"**Date:** {started}")
    L.append("**Branch:** tier2b/hierarchical-prompt @ HEAD")
    L.append("**Status:** CPU-only sweep. Uncommitted.")
    L.append("")
    L.append("## TL;DR")
    L.append("")
    L.append("Tests multiple gating criteria for SELECTIVELY invoking TF-IDF expansion. The blanket union (G_ALL) is the upper bound for both recall and noise; G_NEVER is Qwen3-alone (low recall, low noise). Gates aim to recover the recall benefit only on cases that need it.")
    L.append("")
    L.append("**Goal:** identify a gate that captures most of the recall benefit on size=2 cases while keeping size=1 noise low.")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §Gate sweep results")
    L.append("")
    L.append("| Gate | size=2 fire rate | **size=2 coverage** | size=1 fire rate | **size=1 noise/case** |")
    L.append("|---|---:|---:|---:|---:|")
    for r in results:
        L.append(f"| {r['gate']} | {r['size2_fire_rate']:.1f}% | **{r['size2_coverage']:.1f}%** | {r['size1_fire_rate']:.1f}% | **{r['size1_noise']:.2f}** |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §Pareto analysis")
    L.append("")
    # Find G_ALL and G_NEVER as references
    g_all = next(r for r in results if r["gate"].startswith("G_ALL"))
    g_never = next(r for r in results if r["gate"].startswith("G_NEVER"))
    L.append(f"**Reference points:**")
    L.append(f"- G_ALL: size=2 = {g_all['size2_coverage']:.1f}%, size=1 noise = {g_all['size1_noise']:.2f}")
    L.append(f"- G_NEVER: size=2 = {g_never['size2_coverage']:.1f}%, size=1 noise = {g_never['size1_noise']:.2f}")
    L.append(f"- G_ALL recall lift over G_NEVER: +{g_all['size2_coverage']-g_never['size2_coverage']:.1f}pp")
    L.append(f"- G_ALL noise cost over G_NEVER: +{g_all['size1_noise']-g_never['size1_noise']:.2f}")
    L.append("")
    L.append("**Best gates by recall-recovery / noise-saving ratio:**")
    L.append("")
    L.append("| Gate | Recall recovered | Noise saved | Recall/Noise ratio |")
    L.append("|---|---:|---:|---:|")
    for r in results:
        if r["gate"].startswith("G_ALL") or r["gate"].startswith("G_NEVER"): continue
        recall_recovered = r["size2_coverage"] - g_never["size2_coverage"]
        noise_saved = g_all["size1_noise"] - r["size1_noise"]
        ratio = recall_recovered / max(noise_saved, 0.01)
        L.append(f"| {r['gate']} | +{recall_recovered:.1f}pp | -{noise_saved:.2f} | {ratio:.1f} |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §Recommendation")
    L.append("")
    # Find gate with best balance: at least 50% of G_ALL's recall recovery, at most 50% of G_ALL's noise cost
    best = None
    for r in results:
        if r["gate"].startswith("G_ALL") or r["gate"].startswith("G_NEVER"): continue
        rr = r["size2_coverage"] - g_never["size2_coverage"]
        ns = g_all["size1_noise"] - r["size1_noise"]
        max_rr = g_all["size2_coverage"] - g_never["size2_coverage"]
        max_ns = g_all["size1_noise"] - g_never["size1_noise"]
        if max_rr > 0 and rr / max_rr >= 0.5 and ns / max(max_ns, 0.01) >= 0.3:
            if best is None or (rr/max_rr - 0.4*((max_ns - ns) / max(max_ns, 0.01))) > best[1]:
                best = (r["gate"], rr/max_rr - 0.4*((max_ns - ns) / max(max_ns, 0.01)))
    if best:
        L.append(f"Best gated trigger: **{best[0]}** — captures most of the recall benefit while saving substantial noise.")
    else:
        L.append("No gate strictly dominates. Consider tunable threshold-sweep on top of G_LOW_MARGIN or G_PRIMARY_NOT_CONFIRMED.")
    L.append("")
    AUDIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_OUT.write_text("\n".join(L))
    print(f"Audit written: {AUDIT_OUT}")
    print(f"Lines: {len(L)}")
    print()
    print("Gate results summary:")
    for r in results:
        print(f"  {r['gate']:50s}: fire={r['size2_fire_rate']:.0f}% cov={r['size2_coverage']:.1f}% noise/case={r['size1_noise']:.2f}")


if __name__ == "__main__":
    main()
