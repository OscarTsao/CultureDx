# Gap F Preliminary Audit — Candidate-Set Completeness

**Date:** 2026-05-01 23:13:53
**Branch:** tier2b/hierarchical-prompt @ HEAD
**Status:** CPU-only preliminary diagnostic. Uncommitted.
**Source family:** BETA-2b CPU projection (`results/gap_e_beta2b_projection_20260430_164210/`).
**Scope:** Three preliminary diagnostics on existing predictions — no new GPU calls.

## TL;DR

**Question:** is the bottleneck candidate generation (gold not in top-K) or ranking (gold in top-K but not at rank-1)?

**Three measurements (no new GPU calls):**
- F0: Recall@k sweep on Qwen3 BETA-2b primary across 6 modes, stratified by gold size
- B2: Cross-mode candidate union (icd10 ∪ dsm5 ∪ both top-5 per case)
- B3: TF-IDF top-K union with Qwen3 top-5 — does a non-LLM candidate source recover missing gold?

---

## §F0 — Recall@k sweep, Qwen3 BETA-2b projection

For each mode, stratified by gold size:
- `primary_in_topk`: gold[0] ∈ top-K (matches the standard Top-K metric)
- `any_in_topk`: at least one gold code in top-K
- `all_in_topk`: ALL gold codes in top-K (set ⊆ top-K) — multi-label coverage

### lingxi_icd10

| Gold size | N | k=1 primary | k=1 all | k=3 primary | k=3 any | **k=3 all** | k=5 primary | k=5 any | **k=5 all** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| size=1 | 914 | 51.3% | 51.3% | 78.4% | 78.4% | **78.4%** | 85.7% | 85.7% | **85.7%** |
| size=2 | 81 | 59.3% | 0.0% | 88.9% | 93.8% | **40.7%** | 93.8% | 98.8% | **56.8%** |
| size=3 | 5 | 60.0% | 0.0% | 80.0% | 80.0% | **20.0%** | 80.0% | 100.0% | **20.0%** |

### lingxi_dsm5

| Gold size | N | k=1 primary | k=1 all | k=3 primary | k=3 any | **k=3 all** | k=5 primary | k=5 any | **k=5 all** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| size=1 | 914 | 51.6% | 51.6% | 79.0% | 79.0% | **79.0%** | 85.7% | 85.7% | **85.7%** |
| size=2 | 81 | 63.0% | 0.0% | 90.1% | 95.1% | **42.0%** | 93.8% | 98.8% | **56.8%** |
| size=3 | 5 | 60.0% | 0.0% | 80.0% | 100.0% | **0.0%** | 80.0% | 100.0% | **20.0%** |

### lingxi_both

| Gold size | N | k=1 primary | k=1 all | k=3 primary | k=3 any | **k=3 all** | k=5 primary | k=5 any | **k=5 all** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| size=1 | 914 | 51.3% | 51.3% | 78.4% | 78.4% | **78.4%** | 85.7% | 85.7% | **85.7%** |
| size=2 | 81 | 59.3% | 0.0% | 88.9% | 93.8% | **40.7%** | 93.8% | 98.8% | **56.8%** |
| size=3 | 5 | 60.0% | 0.0% | 80.0% | 80.0% | **20.0%** | 80.0% | 100.0% | **20.0%** |

### mdd_icd10

| Gold size | N | k=1 primary | k=1 all | k=3 primary | k=3 any | **k=3 all** | k=5 primary | k=5 any | **k=5 all** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| size=1 | 844 | 60.4% | 60.4% | 84.8% | 84.8% | **84.8%** | 90.0% | 90.0% | **90.0%** |
| size=2 | 75 | 46.7% | 0.0% | 78.7% | 88.0% | **34.7%** | 80.0% | 93.3% | **44.0%** |
| size=3 | 6 | 50.0% | 0.0% | 66.7% | 100.0% | **0.0%** | 66.7% | 100.0% | **16.7%** |

### mdd_dsm5

| Gold size | N | k=1 primary | k=1 all | k=3 primary | k=3 any | **k=3 all** | k=5 primary | k=5 any | **k=5 all** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| size=1 | 844 | 58.6% | 58.6% | 83.8% | 83.8% | **83.8%** | 89.2% | 89.2% | **89.2%** |
| size=2 | 75 | 53.3% | 0.0% | 78.7% | 86.7% | **41.3%** | 84.0% | 92.0% | **52.0%** |
| size=3 | 6 | 16.7% | 0.0% | 66.7% | 100.0% | **0.0%** | 66.7% | 100.0% | **0.0%** |

### mdd_both

| Gold size | N | k=1 primary | k=1 all | k=3 primary | k=3 any | **k=3 all** | k=5 primary | k=5 any | **k=5 all** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| size=1 | 844 | 60.4% | 60.4% | 84.8% | 84.8% | **84.8%** | 90.0% | 90.0% | **90.0%** |
| size=2 | 75 | 46.7% | 0.0% | 78.7% | 88.0% | **34.7%** | 80.0% | 93.3% | **44.0%** |
| size=3 | 6 | 50.0% | 0.0% | 66.7% | 100.0% | **0.0%** | 66.7% | 100.0% | **16.7%** |

Read this as: **k=3 all** and **k=5 all** are the multi-label set-coverage rates. The headline 'Top-3=0.79' refers only to `k=3 primary`. For size=2 cases, set coverage is much weaker.

---

## §B2 — Cross-mode candidate union

Question: does combining ICD-10 + DSM-5 + Both top-5 per case_id recover missing gold codes that single-mode top-5 misses?

- `single_mode` = ICD-10 top-5 (canonical)
- `union` = ICD-10 ∪ DSM-5 ∪ Both top-5

### lingxi

| Gold size | N | single top-3 all_in | **union top-3 all_in** | single top-5 all_in | **union top-5 all_in** | size≥2: single top-5 secondary_in | **union top-5 secondary_in** |
|---|---:|---:|---:|---:|---:|---:|---:|
| size=1 | 914 | 78.4% | **81.2%** | 85.7% | **87.6%** | — | — |
| size=2 | 81 | 40.7% | **44.4%** | 56.8% | **61.7%** | 61.7% | 65.4% |
| size=3 | 5 | 20.0% | **20.0%** | 20.0% | **20.0%** | 20.0% | 40.0% |

### mdd

| Gold size | N | single top-3 all_in | **union top-3 all_in** | single top-5 all_in | **union top-5 all_in** | size≥2: single top-5 secondary_in | **union top-5 secondary_in** |
|---|---:|---:|---:|---:|---:|---:|---:|
| size=1 | 844 | 84.8% | **87.1%** | 90.0% | **91.4%** | — | — |
| size=2 | 75 | 34.7% | **41.3%** | 44.0% | **53.3%** | 57.3% | 62.7% |
| size=3 | 6 | 0.0% | **0.0%** | 16.7% | **16.7%** | 33.3% | 33.3% |

Read this as: how much does cross-mode candidate union expand recall?

---

## §B3 — TF-IDF candidate union

Question: does adding TF-IDF (lexical) top-K to Qwen3 top-5 recover missing gold codes?
Source: TF-IDF baseline on LingxiDiag-16K (`results/validation/tfidf_baseline/predictions.jsonl`).

### lingxi_icd10

| Gold size | N | Qwen top-5 all | TF-IDF top-5 all | TF-IDF top-10 all | **Union top-5 all** | size≥2 Qwen secondary_in_top5 | **Union secondary_in_top5** |
|---|---:|---:|---:|---:|---:|---:|---:|
| size=1 | 914 | 85.7% | 96.3% | 99.7% | **98.6%** | — | — |
| size=2 | 81 | 56.8% | 69.1% | 97.5% | **79.0%** | 61.7% | 79.0% |
| size=3 | 5 | 20.0% | 40.0% | 80.0% | **60.0%** | 20.0% | 60.0% |

---

## §Diagnostic verdict

**Lingxi size=2 cases:** single-mode top-5 all_in_set = 56.8%, cross-mode union top-5 all_in_set = 61.7% (Δ = +4.9pp).
**Lingxi size=2 + TF-IDF union:** Qwen alone all_in = 56.8%, Qwen+TFIDF union top-5 = 79.0% (Δ = +22.2pp).

**Verdict (CPU-only evidence):**
- If cross-mode union or TF-IDF union substantially expands recall → MAS candidate-union approach has signal → proceed to GPU probes (Gemma/Llama in flight)
- If neither union expands recall meaningfully → the missing-gold problem is structural (gold codes not derivable from any reasonable candidate source on this benchmark)

---

## §Files NOT modified

- `paper-integration-v0.1` tag — frozen at c3b0a46
- `feature/gap-e-beta2-implementation` — NOT touched
- `main-v2.4-refactor` — NOT touched
- All previous audits — NOT modified
- This audit is on `tier2b/hierarchical-prompt` branch only
