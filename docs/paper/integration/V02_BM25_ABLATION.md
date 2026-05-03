# v0.2 BM25 Ablation — Standard Sparse Baseline Comparison

**Date:** 2026-05-03
**Protocol:** 5-fold case-level CV, seed=42, same split as v0.2 2×2 ablation (V02_ABLATION_2X2.md)
**Goal:** Address reviewer attack "Why TF-IDF and not BM25?". BM25 is the standard sparse lexical retrieval baseline.

## Standalone classifier comparison (Top-1 on test = primary code only)

| Method | Top-1 | Notes |
|---|---:|---|
| Qwen3-32B-AWQ rank-1 | 0.520 | CV mean across 5 folds |
| TF-IDF + LR (standalone) | 0.5367 | Existing result |
| **BM25 def-query (best k1, b)** | 0.1720 | Standalone, max BM25 score over disorder defs; best grid point |
| **BM25 def-query (default k1=1.5, b=0.75)** | 0.1710 | Robertson-classic params |
| **BM25 corpus-kNN (training cases)** | 0.4070 | Standard IR baseline: query test case, retrieve nearest training case; k1=1.5, b=0.75 |

BM25 standalone modes are intentionally separated. Mode 1 (def-query) uses query=case text and corpus=disorder definitions; it measures zero-shot alignment to short disorder descriptions. Mode 2 (corpus-kNN) uses query=case text and corpus=14k training cases; it is the standard IR baseline analogous to the TF-IDF train/test split. The reranker cells D and E below continue to use def-query BM25 scores as disorder-definition features, which is the intended ablation for those cells.

## 5-fold CV reranker comparison (Top-1 lift over Qwen rank-1)

| Cell | Config | 5-fold CV mean | std | Per-fold |
|---|---|---:|---:|---|
| A | Qwen rank-1 baseline | 0.520 | ±0.014 | [0.500, 0.540, 0.515, 0.515, 0.530] |
| F (=C) | TF-IDF, no ML (linear combo, per-fold tuned) | +7.2pp | ±1.2pp | [+7.0pp, +7.0pp, +9.5pp, +6.5pp, +6.0pp] |
| G (=E) | TF-IDF, with ML (LightGBM) | +7.0pp | ±1.0pp | [+9.0pp, +6.5pp, +6.5pp, +6.5pp, +6.5pp] |
| **D** | **BM25 def-query, no ML (linear combo)** | **-0.9pp** | **±0.9pp** | **[-2.0pp, +0.0pp, +0.0pp, -0.5pp, -2.0pp]** |
| **E_best** | **BM25 def-query + LightGBM (best k1, b)** | **-0.1pp** | **±1.8pp** | **[+2.0pp, +0.5pp, -2.0pp, +1.5pp, -2.5pp]** |
| **E_default** | **BM25 def-query + LightGBM (k1=1.5, b=0.75)** | **-0.1pp** | **±2.1pp** | — |
| **D2** | **BM25 corpus-kNN, no ML (linear combo)** | **+0.0pp** | **±0.0pp** | **[+0.0pp, +0.0pp, +0.0pp, +0.0pp, +0.0pp]** |
| **E2** | **BM25 corpus-kNN + LightGBM** | **-1.5pp** | **±1.9pp** | **[+2.0pp, -2.5pp, -3.0pp, -1.0pp, -3.0pp]** |

## BM25 (k1, b) hyperparameter sweep on E_bm25

| k1 | b | 5-fold CV mean | std |
|---:|---:|---:|---:|
| 0.8 | 0.40 | -1.6pp | ±2.8pp |
| 0.8 | 0.75 | -0.5pp | ±2.2pp |
| 0.8 | 1.00 | -0.6pp | ±3.0pp |
| 1.2 | 0.40 | -2.0pp | ±1.9pp |
| 1.2 | 0.75 | -0.7pp | ±3.5pp |
| 1.2 | 1.00 | -0.9pp | ±2.3pp |
| 1.5 | 0.40 | -1.2pp | ±2.8pp |
| 1.5 | 0.75 | -0.1pp | ±2.1pp |
| 1.5 | 1.00 | -1.9pp | ±3.2pp |
| 2.0 | 0.40 | -1.3pp | ±2.0pp |
| 2.0 | 0.75 | -0.1pp | ±1.8pp |
| 2.0 | 1.00 | -1.9pp | ±2.4pp |

## Direct comparison: TF-IDF vs BM25 paradigms

| Comparison | Δ |
|---|---:|
| BM25 def-query best − TF-IDF G (+7.0pp) | -7.1pp |
| BM25 def-query default − TF-IDF G (+7.0pp) | -7.1pp |
| BM25 corpus-kNN E2 − TF-IDF G (+7.0pp) | -8.5pp |
| BM25 def-query no-ML (D) − Qwen baseline | -0.9pp |
| BM25 corpus-kNN no-ML (D2) − Qwen baseline | +0.0pp |
| TF-IDF no-ML (F) − Qwen baseline | +7.2pp |

## Interpretation

### Scenario C: BM25 < TF-IDF
TF-IDF with learned calibration (LightGBM) outperforms the proper corpus-kNN BM25 reranker. This suggests that the supervised TF-IDF classifier probabilities are more informative than aggregated BM25 nearest-case scores for this reranking task. The def-query BM25 cells are retained only as a zero-shot definition-alignment diagnostic, not as the apples-to-apples TF-IDF analog.

## Conclusion

BM25 corpus-kNN E2 reaches -1.5pp versus TF-IDF G at +7.0pp, while def-query BM25 remains near zero lift. The paper should keep TF-IDF as the stronger v0.2 sparse implementation and present corpus-kNN BM25 as the canonical IR baseline requested by reviewers.

## Lineage

paper-integration-v0.1 (c3b0a46) frozen. BETA-2b primary-only contract preserved.
TF-IDF 2×2 ablation: V02_ABLATION_2X2.md (same fold split, seed=42).
