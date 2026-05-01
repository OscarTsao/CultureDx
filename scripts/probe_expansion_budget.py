#!/usr/bin/env python3
"""Expansion budget sweep — how many TF-IDF candidates per case is optimal?

Tests +0, +1, +2, +3, +5 unique TF-IDF codes added to Qwen top-5.
"Unique" = not already in Qwen top-5.

For each budget B and gate (G_LOW_MARGIN, G_ANY_TWO, G_ALL), compute:
  size=2 all-gold-coverage
  size=1 noise per case
  marginal Pareto position

Output: docs/paper/integration/GAP_F_EXPANSION_BUDGET.md
"""
from __future__ import annotations
import json, time
from pathlib import Path

REPO = Path("/home/user/YuNing/CultureDx")
AUDIT_OUT = REPO / "docs/paper/integration/GAP_F_EXPANSION_BUDGET.md"

def base(c): return c.split('.')[0] if c else c
def base_set(s): return set(base(c) for c in s)


def main():
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[Expansion budget sweep] starting {started}")

    qwen_lingxi = [json.loads(l) for l in open(REPO / "results/gap_e_beta2b_projection_20260430_164210/lingxi_icd10_n1000/predictions.jsonl")]
    tfidf_lr = {str(r["case_id"]): r for r in (json.loads(l) for l in open(REPO / "results/validation/tfidf_baseline/predictions.jsonl"))}
    print(f"  Qwen: {len(qwen_lingxi)}, TFIDF+LR: {len(tfidf_lr)}")

    def qwen_top5(rec): return base_set(rec.get("decision_trace", {}).get("diagnostician_ranked", [])[:5])
    def tfidf_unique(rec, qwen5_set, k):
        cid = str(rec["case_id"])
        tfidf_ranked = [base(c) for c in tfidf_lr.get(cid, {}).get("ranked_codes", [])]
        unique_added = []
        for c in tfidf_ranked:
            if c not in qwen5_set and c not in unique_added:
                unique_added.append(c)
                if len(unique_added) >= k: break
        return unique_added

    def gate_low_margin(rec):
        rk = rec.get("decision_trace", {}).get("diagnostician_ranked", [])
        mr = {co["disorder_code"]: co.get("met_ratio", 0) for co in rec.get("decision_trace", {}).get("raw_checker_outputs", []) or []}
        if len(rk) < 2: return False
        return abs(mr.get(rk[0], 0) - mr.get(rk[1], 0)) < 0.05
    def gate_primary_not_confirmed(rec):
        rk = rec.get("decision_trace", {}).get("diagnostician_ranked", [])
        if not rk: return False
        cf = set(base(c) for c in rec.get("decision_trace", {}).get("logic_engine_confirmed_codes", []))
        return base(rk[0]) not in cf
    def gate_checker_ambig(rec):
        return len(set(base(c) for c in rec.get("decision_trace", {}).get("logic_engine_confirmed_codes", []))) >= 4
    def gate_any_two(rec):
        return sum([gate_low_margin(rec), gate_primary_not_confirmed(rec), gate_checker_ambig(rec)]) >= 2

    GATES = {
        "G_ALL": lambda rec: True,
        "G_LOW_MARGIN": gate_low_margin,
        "G_ANY_TWO": gate_any_two,
    }
    BUDGETS = [0, 1, 2, 3, 5, 10]

    size1 = [r for r in qwen_lingxi if len(r.get("gold_diagnoses", [])) == 1]
    size2 = [r for r in qwen_lingxi if len(r.get("gold_diagnoses", [])) == 2]
    print(f"  size=1: {len(size1)}, size=2: {len(size2)}")

    table = []
    for gate_name, gate_fn in GATES.items():
        for B in BUDGETS:
            n_size2 = 0; covered = 0
            for r in size2:
                cid = str(r["case_id"])
                n_size2 += 1
                qwen5 = qwen_top5(r)
                gold_b = base_set(r["gold_diagnoses"])
                if gate_fn(r) and B > 0:
                    extra = set(tfidf_unique(r, qwen5, B))
                    pool = qwen5 | extra
                else:
                    pool = qwen5
                if gold_b.issubset(pool): covered += 1
            cov_pct = 100*covered/n_size2 if n_size2 else 0

            n_size1 = 0; total_noise = 0
            for r in size1:
                cid = str(r["case_id"])
                n_size1 += 1
                gold = base(r["gold_diagnoses"][0])
                qwen5 = qwen_top5(r)
                if gate_fn(r) and B > 0:
                    extra = set(tfidf_unique(r, qwen5, B))
                    pool = qwen5 | extra
                else:
                    pool = qwen5
                noise = len(pool) - (1 if gold in pool else 0)
                total_noise += noise
            noise_pc = total_noise/n_size1 if n_size1 else 0
            table.append({"gate": gate_name, "budget": B, "size2_cov": cov_pct, "size1_noise": noise_pc})

    # Render audit
    L = []
    L.append("# Gap F Expansion Budget Sweep")
    L.append("")
    L.append(f"**Date:** {started}")
    L.append("**Branch:** tier2b/hierarchical-prompt @ HEAD")
    L.append("**Status:** CPU-only sweep. Uncommitted.")
    L.append("")
    L.append("## TL;DR")
    L.append("")
    L.append("How many TF-IDF unique candidates per case maximizes recall while minimizing noise?")
    L.append("Tests budgets {0, 1, 2, 3, 5, 10} across 3 gates.")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §Sweep table — size=2 coverage / size=1 noise")
    L.append("")
    L.append("| Gate | Budget B | size=2 coverage | size=1 noise/case |")
    L.append("|---|---:|---:|---:|")
    for row in table:
        L.append(f"| {row['gate']} | {row['budget']} | {row['size2_cov']:.1f}% | {row['size1_noise']:.2f} |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §Per-gate Pareto curves")
    L.append("")
    for gate_name in GATES:
        L.append(f"### {gate_name}")
        L.append("")
        L.append("| B | size=2 cov | size=1 noise | recall/noise marginal |")
        L.append("|---:|---:|---:|---:|")
        prev = None
        for row in [r for r in table if r["gate"] == gate_name]:
            if prev is None:
                marginal = "—"
            else:
                d_cov = row["size2_cov"] - prev["size2_cov"]
                d_noise = row["size1_noise"] - prev["size1_noise"]
                if abs(d_noise) < 0.001:
                    marginal = "+∞" if d_cov > 0 else "0"
                else:
                    marginal = f"{d_cov/d_noise:.1f}"
            L.append(f"| {row['budget']} | {row['size2_cov']:.1f}% | {row['size1_noise']:.2f} | {marginal} |")
            prev = row
        L.append("")
    L.append("---")
    L.append("")
    L.append("## §Recommendation")
    L.append("")
    # Find best (gate, budget) by some criterion: cov >= 70 and minimize noise
    candidates = [r for r in table if r["size2_cov"] >= 70.0]
    if candidates:
        best = min(candidates, key=lambda r: r["size1_noise"])
        L.append(f"**Best (gate, budget) for ≥70% size=2 coverage minimizing noise:**")
        L.append(f"- Gate: {best['gate']}, Budget: {best['budget']}")
        L.append(f"- size=2 coverage: {best['size2_cov']:.1f}%")
        L.append(f"- size=1 noise/case: {best['size1_noise']:.2f}")
    else:
        L.append("No (gate, budget) achieves ≥70% size=2 coverage. Use highest available.")
    L.append("")
    AUDIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_OUT.write_text("\n".join(L))
    print(f"Audit written: {AUDIT_OUT}")
    print()
    print("Sweep summary (gate, budget): cov, noise:")
    for r in table:
        print(f"  {r['gate']:15s} B={r['budget']:2d}  cov={r['size2_cov']:5.1f}%  noise={r['size1_noise']:.2f}")


if __name__ == "__main__":
    main()
