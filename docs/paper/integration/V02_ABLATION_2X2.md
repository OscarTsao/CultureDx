# v0.2 2×2 Ablation: TF-IDF Channel vs ML Learning Contribution

**Date:** 2026-05-02
**Protocol:** 5-fold case-level CV, seed=42, same fold assignment across all cells
**Goal:** Disentangle TF-IDF lexical channel contribution from learned reranker contribution.

## Results

| Cell | Config | 5-fold CV Top-1 lift | Mean ± std | Per-fold |
|---|---|---:|---:|---:|
| A | Qwen rank-1 baseline | — | 0.5200 ± 0.0138 abs | [0.5000, 0.5400, 0.5150, 0.5150, 0.5300] |
| C | NO-ML linear combo (per-fold tuned weights) | +7.20pp | ± 1.21pp | [+7.00pp, +7.00pp, +9.50pp, +6.50pp, +6.00pp] |
| D | ML w/o TF-IDF (Qwen features only) | -0.10pp | ± 1.53pp | [+1.50pp, +2.00pp, -1.50pp, -1.50pp, -1.00pp] |
| E | ML w/ TF-IDF (full features) | +7.00pp | ± 1.00pp | [+9.00pp, +6.50pp, +6.50pp, +6.50pp, +6.50pp] |

## Decompositions

| Comparison | Value | Interpretation |
|---:|---|---|
| C − A | +7.20pp | TF-IDF channel contribution without learning |
| D − A | -0.10pp | ML contribution without orthogonal channel |
| E − C | -0.20pp | ML's marginal contribution given TF-IDF |
| E − D | +7.10pp | TF-IDF channel contribution given ML |

## Architectural framing implications

The 5-fold matrix shows that the no-ML TF-IDF channel contributes +7.20pp over the same-fold Qwen rank-1 baseline, while the Qwen-only learned reranker contributes -0.10pp. Adding TF-IDF to the learned reranker yields +7.00pp overall, leaving a marginal ML-given-TF-IDF effect of -0.20pp and a marginal TF-IDF-given-ML effect of +7.10pp. These values frame v0.2 as a decomposition of lexical-channel signal versus learned candidate selection, rather than as evidence for a single undifferentiated reranking gain.

## Per-fold detail

| Fold | A baseline | C lift | D lift | E lift |
|---:|---:|---:|---:|---:|
| 1 | 0.5000 | +7.00pp | +1.50pp | +9.00pp |
| 2 | 0.5400 | +7.00pp | +2.00pp | +6.50pp |
| 3 | 0.5150 | +9.50pp | -1.50pp | +6.50pp |
| 4 | 0.5150 | +6.50pp | -1.50pp | +6.50pp |
| 5 | 0.5300 | +6.00pp | -1.00pp | +6.50pp |
