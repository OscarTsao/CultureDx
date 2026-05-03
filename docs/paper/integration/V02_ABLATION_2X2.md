# v0.2 2×2 Ablation: TF-IDF Channel vs ML Learning Contribution

**Date:** 2026-05-02
**Protocol:** 5-fold case-level CV, seed=42, same fold assignment across all cells
**Goal:** Disentangle TF-IDF lexical channel contribution from learned reranker contribution.

## Results

| Cell | Config | Mean ± std | Per-fold deltas |
|---|---|---:|---|
| A | Qwen rank-1 baseline (floor) | 0.520 ± 0.014 | [0.500, 0.540, 0.515, 0.515, 0.530] |
| C | NO-ML linear combo (per-fold tuned weights) | +7.2pp ± 1.2pp | [+7.0pp, +7.0pp, +9.5pp, +6.5pp, +6.0pp] |
| D | ML w/o TF-IDF (Qwen features only) | -0.1pp ± 1.5pp | [+1.5pp, +2.0pp, -1.5pp, -1.5pp, -1.0pp] |
| E | ML w/ TF-IDF (full features) | +7.0pp ± 1.0pp | [+9.0pp, +6.5pp, +6.5pp, +6.5pp, +6.5pp] |

## Decompositions

| Comparison | Value | Interpretation |
|---|---:|---|
| C − A | +7.2pp | TF-IDF channel contribution without learning |
| D − A | -0.1pp | ML contribution without orthogonal channel |
| E − C | -0.2pp | ML's marginal contribution given TF-IDF |
| E − D | +7.1pp | TF-IDF channel contribution given ML |

## Architectural framing implications

The decomposition separates a no-ML lexical-channel lift of +7.2pp from a Qwen-only ML lift of -0.1pp and a full learned-channel lift of +7.0pp. The resulting marginals, -0.2pp for ML given TF-IDF and +7.1pp for TF-IDF given ML, should be used as the paper's primary architectural framing numbers.

## Per-fold detail

| Fold | A (baseline acc) | C delta | D delta | E delta |
|---:|---:|---:|---:|---:|
| 1 | 0.500 | +7.0pp | +1.5pp | +9.0pp |
| 2 | 0.540 | +7.0pp | +2.0pp | +6.5pp |
| 3 | 0.515 | +9.5pp | -1.5pp | +6.5pp |
| 4 | 0.515 | +6.5pp | -1.5pp | +6.5pp |
| 5 | 0.530 | +6.0pp | -1.0pp | +6.5pp |
| **Mean** | **0.520** | **+7.2pp** | **-0.1pp** | **+7.0pp** |
| **Std** | **0.014** | **±1.2pp** | **±1.5pp** | **±1.0pp** |
