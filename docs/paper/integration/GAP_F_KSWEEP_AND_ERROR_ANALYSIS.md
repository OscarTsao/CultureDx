# Gap F K-sweep + Reranker Error Analysis

**Date:** 2026-05-02

## §A — Pure TF-IDF kNN K-sweep

| K | Lingxi size=2 all-gold-in-union (Qwen + kNN top-5) |
|---:|---:|
| 5 | 64.2% |
| 10 | 67.9% |
| 25 | **70.4%** |
| 50 | 70.4% |
| 100 | 70.4% |
| 200 | 66.7% (declining) |
| 500 | 64.2% |
| 1000 | 61.7% |

**Optimal K = 25 to 100 (plateau).** Beyond K=200, neighbor noise dilutes label voting and coverage drops.

Sweet spot K=25 minimizes computation while achieving plateau coverage. K=50 is the value used in earlier experiments.

## §B — Reranker error analysis on test cases (n=300)

**41 cases helped, 10 cases hurt = 4.1:1 ratio.** Net +31 cases improved.

### Sample helped (reranker correctly changed primary):

| case_id | baseline → rerank | gold | top-5 |
|---|---|---|---|
| 327826586 | F41 → F39 | F39 | [F41, F32, F39, F51, F42] |
| 342949614 | F32 → F39 | F39 | [F32, F39, F41, F43, F51] |
| 334814081 | F32 → F41 | F41 | [F32, F41, F39, F51, F42] |
| 399980638 | F32 → F41 | F41 | [F32, F39, F41, F51, F43] |
| 398487934 | F41 → F39 | F39 | [F41, F39, F32, F51, F43] |

Pattern: reranker fixes F32→F41 (anxiety mistakenly classified as depression) and F32→F39 (mood NOS).

### Sample hurt (reranker wrongly changed primary):

| case_id | baseline → rerank | gold | top-5 |
|---|---|---|---|
| 350352506 | F32 → F41 | F32 | [F32, F41, F39, F51, F42] |
| 321077019 | F32 → F41 | F32 | [F32, F41, F39, F51, Z71] |
| 329640791 | F32 → F51 | F32 | [F32, F41, F39, F51, Z71] |
| 378881682 | F32 → F51 | F32 | [F32, F39, F41, F51, Z71] |
| 375048974 | F32 → F41 | F32 | [F32, F39, F41, F51, F98] |

Pattern: reranker over-corrects F32→F41 in cases where Qwen3 was actually correct on F32. Class confusion goes both ways.

## §C — Implication: F32↔F41 confusion pair drives most reranker effects

The reranker primarily resolves F32↔F41 ambiguity. In 80% of cases, this works correctly (gold was actually F41 and Qwen3 over-predicted F32). In 20% of cases, this hurts (Qwen3 was correct on F32 but reranker swaps to F41 due to TF-IDF lexical signal).

The 4:1 helped:hurt ratio means net positive, but suggests:
1. **Class-aware threshold** could improve precision: only override F32→F41 when TF-IDF probability exceeds a higher threshold
2. **F32-specific reranker** trained separately could reduce over-correction
3. **Confidence-aware decision**: keep baseline if reranker confidence is low; swap only on high confidence

These tunings are out of scope for the current paper but valuable future work.

