# Gap F CPU Batch Audit — Multi-experiment diagnostic results

**Date:** 2026-05-01 23:33:45
**Branch:** tier2b/hierarchical-prompt @ HEAD
**Status:** CPU-only batch audit. Uncommitted.
**Source:** BETA-2b CPU projection + TF-IDF baseline.

Six diagnostic sub-experiments on existing predictions, no new GPU calls.

---

## §A4 — Oracle EM@k ceiling (perfect reranker upper bound)

If a perfect reranker chose K codes from the candidate pool, what's the maximum EM?

| Mode | Gold size | N | k=1 | k=3 | k=5 | Cross-mode union | TF-IDF union |
|---|---|---:|---:|---:|---:|---:|---:|
| lingxi_icd10 | size=1 | 914 | 51.3% | 78.4% | 85.7% | 87.6% | 98.6% |
| lingxi_icd10 | size=2 | 81 | 0.0% | 40.7% | 56.8% | 61.7% | 79.0% |
| lingxi_icd10 | size=3 | 5 | 0.0% | 20.0% | 20.0% | 20.0% | 60.0% |
| lingxi_dsm5 | size=1 | 914 | 51.6% | 79.0% | 85.7% | 87.6% | 98.6% |
| lingxi_dsm5 | size=2 | 81 | 0.0% | 42.0% | 56.8% | 61.7% | 81.5% |
| lingxi_dsm5 | size=3 | 5 | 0.0% | 0.0% | 20.0% | 20.0% | 80.0% |
| lingxi_both | size=1 | 914 | 51.3% | 78.4% | 85.7% | 87.6% | 98.6% |
| lingxi_both | size=2 | 81 | 0.0% | 40.7% | 56.8% | 61.7% | 79.0% |
| lingxi_both | size=3 | 5 | 0.0% | 20.0% | 20.0% | 20.0% | 60.0% |
| mdd_icd10 | size=1 | 844 | 60.4% | 84.8% | 90.0% | 91.4% | n/a |
| mdd_icd10 | size=2 | 75 | 0.0% | 34.7% | 44.0% | 53.3% | n/a |
| mdd_icd10 | size=3 | 6 | 0.0% | 0.0% | 16.7% | 16.7% | n/a |
| mdd_dsm5 | size=1 | 844 | 58.6% | 83.8% | 89.2% | 91.4% | n/a |
| mdd_dsm5 | size=2 | 75 | 0.0% | 41.3% | 52.0% | 53.3% | n/a |
| mdd_dsm5 | size=3 | 6 | 0.0% | 0.0% | 0.0% | 16.7% | n/a |
| mdd_both | size=1 | 844 | 60.4% | 84.8% | 90.0% | 91.4% | n/a |
| mdd_both | size=2 | 75 | 0.0% | 34.7% | 44.0% | 53.3% | n/a |
| mdd_both | size=3 | 6 | 0.0% | 0.0% | 16.7% | 16.7% | n/a |

Read this as the ABSOLUTE CEILING for each candidate pool. Real systems can only reach this with a perfect downstream selector.

---

## §A3 — Missing-secondary-gold taxonomy

For multi-gold cases, where do the gold codes appear?

| Mode | in_top5 | in_candidates_not_top5 | out_of_candidates |
|---|---:|---:|---:|
| lingxi_icd10 | 135 (76.3%) | 42 (23.7%) | 0 (0.0%) |
| lingxi_dsm5 | 137 (77.4%) | 40 (22.6%) | 0 (0.0%) |
| lingxi_both | 135 (76.3%) | 42 (23.7%) | 0 (0.0%) |
| mdd_icd10 | 115 (68.5%) | 18 (10.7%) | 35 (20.8%) |
| mdd_dsm5 | 119 (70.8%) | 14 (8.3%) | 35 (20.8%) |
| mdd_both | 115 (68.5%) | 18 (10.7%) | 35 (20.8%) |

Sample of size=2 cases with missing secondary (5 per mode, lingxi_icd10):

| case_id | gold | missing_secondary | top5 | in_candidates? |
|---|---|---|---|---|
| 388730013 | ['F42', 'F41'] | F42 | ['F32', 'F41', 'F39', 'F51', 'F98'] | True |
| 319673363 | ['F42', 'F41'] | F42 | ['F41', 'F32', 'F51', 'F39', 'Z71'] | True |
| 380136533 | ['F51', 'F98'] | F98 | ['F32', 'F41', 'F39', 'F42', 'F51'] | True |
| 375588186 | ['F41', 'F98', 'F32'] | F98 | ['F32', 'F39', 'F41', 'F51', 'Z71'] | True |
| 380733404 | ['F98', 'F41'] | F98 | ['F41', 'F32', 'F51', 'F41', 'F39'] | True |

---

## §A7 — Per-class set coverage

For each class C: how often is C in gold, in top-5, primary-correct, involved in size=2, and set-covered when in size=2?

### lingxi_icd10

| Class | gold_count | in_top5 | primary_correct | involved_size2 | set_covered_size2 |
|---|---:|---:|---:|---:|---:|
| F32 | 370 | 99% | 89% | 39 | 95% |
| F41 | 394 | 100% | 42% | 61 | 62% |
| F42 | 36 | 50% | 36% | 12 | 8% |
| F33 | 0 | — | — | — | — |
| F39 | 63 | 95% | 8% | 8 | 75% |
| F51 | 43 | 95% | 5% | 13 | 54% |
| F45 | 16 | 31% | 12% | 7 | 0% |
| Z71 | 8 | 62% | 0% | 0 | — |

### lingxi_dsm5

| Class | gold_count | in_top5 | primary_correct | involved_size2 | set_covered_size2 |
|---|---:|---:|---:|---:|---:|
| F32 | 370 | 100% | 86% | 39 | 95% |
| F41 | 394 | 100% | 46% | 61 | 62% |
| F42 | 36 | 44% | 39% | 12 | 0% |
| F33 | 0 | — | — | — | — |
| F39 | 63 | 84% | 6% | 8 | 88% |
| F51 | 43 | 95% | 5% | 13 | 38% |
| F45 | 16 | 44% | 12% | 7 | 14% |
| Z71 | 8 | 38% | 0% | 0 | — |

### lingxi_both

| Class | gold_count | in_top5 | primary_correct | involved_size2 | set_covered_size2 |
|---|---:|---:|---:|---:|---:|
| F32 | 370 | 99% | 89% | 39 | 95% |
| F41 | 394 | 100% | 42% | 61 | 62% |
| F42 | 36 | 50% | 36% | 12 | 8% |
| F33 | 0 | — | — | — | — |
| F39 | 63 | 95% | 8% | 8 | 75% |
| F51 | 43 | 95% | 5% | 13 | 54% |
| F45 | 16 | 31% | 12% | 7 | 0% |
| Z71 | 8 | 62% | 0% | 0 | — |

### mdd_icd10

| Class | gold_count | in_top5 | primary_correct | involved_size2 | set_covered_size2 |
|---|---:|---:|---:|---:|---:|
| F32 | 410 | 99% | 89% | 43 | 70% |
| F41 | 339 | 100% | 49% | 47 | 60% |
| F42 | 21 | 62% | 24% | 3 | 33% |
| F33 | 2 | 0% | 0% | 1 | 0% |
| F39 | 65 | 98% | 8% | 2 | 50% |
| F51 | 28 | 86% | 0% | 8 | 50% |
| F45 | 9 | 56% | 0% | 2 | 50% |
| Z71 | 8 | 25% | 0% | 0 | — |

### mdd_dsm5

| Class | gold_count | in_top5 | primary_correct | involved_size2 | set_covered_size2 |
|---|---:|---:|---:|---:|---:|
| F32 | 410 | 99% | 91% | 43 | 74% |
| F41 | 339 | 100% | 44% | 47 | 68% |
| F42 | 21 | 62% | 24% | 3 | 100% |
| F33 | 2 | 0% | 0% | 1 | 0% |
| F39 | 65 | 83% | 0% | 2 | 50% |
| F51 | 28 | 96% | 0% | 8 | 62% |
| F45 | 9 | 67% | 11% | 2 | 50% |
| Z71 | 8 | 0% | 0% | 0 | — |

### mdd_both

| Class | gold_count | in_top5 | primary_correct | involved_size2 | set_covered_size2 |
|---|---:|---:|---:|---:|---:|
| F32 | 410 | 99% | 89% | 43 | 70% |
| F41 | 339 | 100% | 49% | 47 | 60% |
| F42 | 21 | 62% | 24% | 3 | 33% |
| F33 | 2 | 0% | 0% | 1 | 0% |
| F39 | 65 | 98% | 8% | 2 | 50% |
| F51 | 28 | 86% | 0% | 8 | 50% |
| F45 | 9 | 56% | 0% | 2 | 50% |
| Z71 | 8 | 25% | 0% | 0 | — |


---

## §B6 — Confusion-pair forced candidate expansion

Augment top-5 with primary's confusion pair (F32→F41, F41→F32, F42→F41, etc).
Tests: does forced expansion improve set coverage without external candidate sources?

| Mode | Gold size | N | baseline top-5 | expanded top-5 | Δ |
|---|---|---:|---:|---:|---:|
| lingxi_icd10 | size=1 | 914 | 85.7% | 86.4% | +0.8pp |
| lingxi_icd10 | size=2 | 81 | 56.8% | 61.7% | +4.9pp |
| lingxi_icd10 | size=3 | 5 | 20.0% | 40.0% | +20.0pp |
| lingxi_dsm5 | size=1 | 914 | 85.7% | 86.2% | +0.5pp |
| lingxi_dsm5 | size=2 | 81 | 56.8% | 63.0% | +6.2pp |
| lingxi_dsm5 | size=3 | 5 | 20.0% | 60.0% | +40.0pp |
| lingxi_both | size=1 | 914 | 85.7% | 86.4% | +0.8pp |
| lingxi_both | size=2 | 81 | 56.8% | 61.7% | +4.9pp |
| lingxi_both | size=3 | 5 | 20.0% | 40.0% | +20.0pp |
| mdd_icd10 | size=1 | 844 | 90.0% | 90.8% | +0.7pp |
| mdd_icd10 | size=2 | 75 | 44.0% | 46.7% | +2.7pp |
| mdd_icd10 | size=3 | 6 | 16.7% | 66.7% | +50.0pp |
| mdd_dsm5 | size=1 | 844 | 89.2% | 89.9% | +0.7pp |
| mdd_dsm5 | size=2 | 75 | 52.0% | 52.0% | +0.0pp |
| mdd_dsm5 | size=3 | 6 | 0.0% | 16.7% | +16.7pp |
| mdd_both | size=1 | 844 | 90.0% | 90.8% | +0.7pp |
| mdd_both | size=2 | 75 | 44.0% | 46.7% | +2.7pp |
| mdd_both | size=3 | 6 | 16.7% | 66.7% | +50.0pp |


---

## §D3 — Candidate ranker (logistic on rank/met/confirmed/tfidf features)

Train cases: 700, Test cases: 300
Baseline (rank-1 = primary): Top-1 = 47.0%
Reranker (logistic): Top-1 = 55.0%
Δ = +8.0pp

Top-8 feature importances:

| Feature | Coefficient |
|---|---:|
| `tfidf_prob` | +1.5260 |
| `is_F41` | +0.4904 |
| `is_F32` | +0.4304 |
| `rank` | -0.3119 |
| `is_F20` | -0.2786 |
| `is_F39` | -0.2657 |
| `in_confirmed` | +0.2429 |
| `is_Z71` | +0.2403 |

---

## §E1 — Cardinality classifier (predict gold size from features)

Test accuracy: 47.7% (N=300)

Confusion matrix (true → predicted):

| Cell | Count |
|---|---:|
| 1->1 | 134 |
| 1->2 | 87 |
| 1->3 | 49 |
| 2->1 | 15 |
| 2->2 | 9 |
| 2->3 | 4 |
| 3->1 | 1 |
| 3->2 | 1 |

Feature importance (max abs coef across classes):

| Feature | Importance |
|---|---:|
| `rank2_met_ratio` | 1.6371 |
| `high_conf_count` | 1.4701 |
| `rank2_in_confirmed` | 0.5117 |
| `n_confirmed` | 0.5055 |
| `rank2_in_pair` | 0.4380 |
| `rank3_met_ratio` | 0.2075 |
| `primary_met_ratio` | 0.0292 |

---

## §Summary

- A4: confirms ~75-80% in-top-3 oracle EM ceiling for lingxi (primary-only); cross-mode union and TF-IDF union extend ceiling further
- A3: confirms 24-31% of multi-gold codes are out-of-top5 (some out-of-candidates, especially MDD)
- A7: per-class breakdown — F42/F33 typically have lowest top-5 recall when they ARE gold
- B6: confusion-pair expansion provides modest lift (specific to F32/F41/F42 pairs)
- D3: simple logistic candidate-reranker test on a 70/30 case split — quantifies how much rank-rerank helps
- E1: cardinality classifier accuracy on size {1,2,3} — tests whether features predict gold size

These results inform the Gap F MAS architecture: candidate pool ceiling, rerank headroom, and set-size predictability.