#!/usr/bin/env python3
"""Marginal source contribution sweep — does each source add value, or are some redundant?

For combinations of {Qwen, Gemma, TF-IDF+LR (in-domain), Pure TF-IDF kNN}:
  Compute size=2 all-gold-coverage of each combination.
  Compute marginal lift = (combination with X) - (combination without X).
  Compute size=1 noise = added non-gold codes per case.

Output: docs/paper/integration/GAP_F_MARGINAL_SOURCE_CONTRIBUTION.md
"""
from __future__ import annotations
import json, time
from pathlib import Path
from collections import Counter
from itertools import combinations

REPO = Path("/home/user/YuNing/CultureDx")
AUDIT_OUT = REPO / "docs/paper/integration/GAP_F_MARGINAL_SOURCE_CONTRIBUTION.md"

def base(c): return c.split('.')[0] if c else c
def base_set(s): return set(base(c) for c in s)


def main():
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[Marginal source contribution] starting {started}")

    # Load all sources
    sample = [json.loads(l) for l in open(REPO / "results/phase1_recall_probe/sample_lingxi_size2_n100.jsonl")]
    gemma = {json.loads(l)["case_id"]: json.loads(l) for l in open(REPO / "results/phase1_recall_probe/gemma3_12b_top5.jsonl")}
    pure_tfidf = {json.loads(l)["case_id"]: json.loads(l) for l in open(REPO / "results/phase1_recall_probe/pure_tfidf_top5.jsonl")}
    tfidf_lr = {str(r["case_id"]): r for r in (json.loads(l) for l in open(REPO / "results/validation/tfidf_baseline/predictions.jsonl"))}

    # Also load size=1 sample for noise check
    qwen_lingxi = [json.loads(l) for l in open(REPO / "results/gap_e_beta2b_projection_20260430_164210/lingxi_icd10_n1000/predictions.jsonl")]
    size1_recs = [r for r in qwen_lingxi if len(r.get("gold_diagnoses", [])) == 1]

    print(f"  Sample size=2: {len(sample)}, Size=1 reference: {len(size1_recs)}")

    # Source extractors (top-5 per case_id)
    def src_qwen_size2(s): return base_set(s["qwen3_top5"][:5])
    def src_qwen_size1(r): return base_set(r["decision_trace"]["diagnostician_ranked"][:5])
    def src_gemma(cid): return base_set(gemma.get(cid, {}).get("top5", [])[:5])
    def src_tfidf_lr(cid): return base_set(tfidf_lr.get(cid, {}).get("ranked_codes", [])[:5])
    def src_pure_tfidf(cid): return base_set(pure_tfidf.get(cid, {}).get("top5", [])[:5])

    SOURCES = ["qwen", "gemma", "tfidf_lr", "pure_tfidf"]

    # Compute coverage for each subset of sources (always include qwen)
    results = {}
    for k in range(1, len(SOURCES) + 1):
        for combo in combinations(SOURCES, k):
            if "qwen" not in combo: continue
            # Size=2 coverage
            n_size2 = 0; covered = 0
            avg_pool = 0
            for s in sample:
                cid = s["case_id"]
                gold_b = base_set(s["gold_diagnoses"])
                pool = set()
                if "qwen" in combo: pool |= src_qwen_size2(s)
                if "gemma" in combo: pool |= src_gemma(cid)
                if "tfidf_lr" in combo: pool |= src_tfidf_lr(cid)
                if "pure_tfidf" in combo: pool |= src_pure_tfidf(cid)
                if not pool: continue
                n_size2 += 1
                avg_pool += len(pool)
                if gold_b.issubset(pool): covered += 1
            cov_pct = 100*covered/n_size2 if n_size2 else 0
            avg_pool_size = avg_pool/n_size2 if n_size2 else 0

            # Size=1 noise (per case, non-gold codes in pool)
            total_noise = 0
            n_size1 = 0
            for r in size1_recs:
                cid = str(r["case_id"])
                pool = set()
                if "qwen" in combo: pool |= src_qwen_size1(r)
                if "gemma" in combo: pool |= src_gemma(cid)
                if "tfidf_lr" in combo: pool |= src_tfidf_lr(cid)
                if "pure_tfidf" in combo: pool |= src_pure_tfidf(cid)
                if not pool: continue
                n_size1 += 1
                gold_b = base(r["gold_diagnoses"][0])
                noise = len(pool) - (1 if gold_b in pool else 0)
                total_noise += noise
            avg_noise = total_noise/n_size1 if n_size1 else 0
            results["+".join(combo)] = {
                "n_size2": n_size2, "size2_coverage": cov_pct,
                "avg_pool_size": avg_pool_size,
                "size1_noise_per_case": avg_noise,
                "n_size1": n_size1,
            }

    # Marginal contribution analysis
    # ΔRecall_X = full - (full - X)
    # ΔNoise_X = noise(full) - noise(full - X)
    full_combo = "+".join(SOURCES)
    full = results[full_combo]
    marginals = {}
    for src in SOURCES:
        if src == "qwen": continue
        without_src = "+".join(s for s in SOURCES if s != src)
        without = results[without_src]
        marginals[src] = {
            "delta_recall": full["size2_coverage"] - without["size2_coverage"],
            "delta_noise": full["size1_noise_per_case"] - without["size1_noise_per_case"],
            "without_combo": without_src,
        }

    # Render audit
    L = []
    L.append("# Gap F Marginal Source Contribution Sweep")
    L.append("")
    L.append(f"**Date:** {started}")
    L.append("**Branch:** tier2b/hierarchical-prompt @ HEAD")
    L.append("**Status:** CPU-only sweep. Uncommitted.")
    L.append("")
    L.append("## TL;DR")
    L.append("")
    L.append("Tests marginal contribution of each non-Qwen source: Gemma, TF-IDF+LR (in-domain Lingxi), Pure TF-IDF kNN.")
    L.append("Δ recall = full union coverage − coverage without that source. Higher = source contributes uniquely.")
    L.append("Δ noise = full union noise − noise without that source. Higher = source contributes pollution.")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §All-source-combination coverage table")
    L.append("")
    L.append("| Source combination | size=2 coverage | avg pool size | size=1 noise per case |")
    L.append("|---|---:|---:|---:|")
    # Sort: alphabetical for predictability
    for combo_label, info in sorted(results.items()):
        L.append(f"| {combo_label} | {info['size2_coverage']:.1f}% | {info['avg_pool_size']:.1f} | {info['size1_noise_per_case']:.2f} |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §Marginal contribution per non-Qwen source")
    L.append("")
    L.append("ΔRecall = coverage(full union) − coverage(union without this source)")
    L.append("ΔNoise = noise(full union) − noise(union without this source)")
    L.append("")
    L.append("| Source | Δ recall (size=2) | Δ noise (size=1) | ROI = Δrecall/Δnoise |")
    L.append("|---|---:|---:|---:|")
    for src, d in marginals.items():
        roi = d["delta_recall"] / d["delta_noise"] if d["delta_noise"] > 1e-6 else float('inf')
        roi_str = f"{roi:.1f}" if abs(roi) < 1000 else "∞" if roi > 0 else "-∞"
        L.append(f"| {src} | +{d['delta_recall']:.1f}pp | +{d['delta_noise']:.2f} | {roi_str} |")
    L.append("")
    L.append("Read this as: each non-Qwen source's UNIQUE marginal contribution to recall, traded against its noise added on size=1 cases.")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §Decision matrix")
    L.append("")
    L.append("| Source | Recommendation |")
    L.append("|---|---|")
    for src, d in marginals.items():
        if d["delta_recall"] >= 5.0 and d["delta_noise"] <= 1.0:
            rec = "**KEEP unconditionally** — high marginal recall, low noise"
        elif d["delta_recall"] >= 5.0:
            rec = "**KEEP gated** — high recall but noisy; use only on size=2 candidates"
        elif d["delta_recall"] >= 2.0:
            rec = "Marginal value — consider as feature/disagreement signal only"
        else:
            rec = "DROP from candidate union — redundant with other sources"
        L.append(f"| {src} | {rec} |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## §Summary key configurations")
    L.append("")
    L.append("| Configuration | size=2 cov | size=1 noise |")
    L.append("|---|---:|---:|")
    for label in ["qwen", "qwen+gemma", "qwen+tfidf_lr", "qwen+pure_tfidf",
                  "qwen+gemma+tfidf_lr", "qwen+gemma+pure_tfidf",
                  "qwen+gemma+pure_tfidf+tfidf_lr"]:
        if label in results:
            r = results[label]
            L.append(f"| {label} | {r['size2_coverage']:.1f}% | {r['size1_noise_per_case']:.2f} |")
    L.append("")
    AUDIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_OUT.write_text("\n".join(L))
    print(f"Audit written: {AUDIT_OUT}")
    print(f"Lines: {len(L)}")
    print()
    print("Marginal contributions:")
    for src, d in marginals.items():
        print(f"  {src}: Δrecall = +{d['delta_recall']:.1f}pp, Δnoise = +{d['delta_noise']:.2f}")


if __name__ == "__main__":
    main()
