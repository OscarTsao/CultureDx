# Gap F LightGBM Reranker Hyperparameter Sweep

**Date:** 2026-05-02
**Branch:** tier2b/hierarchical-prompt @ HEAD
**Status:** CPU-only. Uncommitted.

## TL;DR

48-config hyperparameter sweep (n_est × max_depth × lr) on LightGBM reranker with TF-IDF features. Best config achieves +10.3pp Top-1 lift, only marginally better than logistic baseline (+9.7pp).

## Best configurations (top 5 by Δ)

| n_est | max_depth | lr | Baseline Top-1 | Rerank Top-1 | Δ |
|---:|---:|---:|---:|---:|---:|
| 50 | 8 | 0.05 | 0.4700 | **0.5733** | **+10.3pp** |
| 200 | 4 | 0.05 | 0.4700 | 0.5733 | +10.3pp |
| 400 | 4 | 0.05 | 0.4700 | 0.5700 | +10.0pp |
| 50 | 6 | 0.05 | 0.4700 | 0.5667 | +9.7pp |
| 100 | 4 | 0.05 | 0.4700 | 0.5667 | +9.7pp |

## Key observations

1. **Low learning rate (0.05) consistently best** across n_est values
2. **Shallow depth (4-6) performs as well as deep (8-10)** — feature interactions are mostly linear
3. **n_est plateau around 50-100** — more trees don't help (overfitting risk)
4. **Robust to hyperparameter choice**: 75% of configs achieve ≥+8pp lift; entire sweep ranges +6 to +10.3pp
5. **Logistic reranker (+9.7pp) within 0.6pp of best LightGBM** — non-linearities give marginal improvement only

## Implication

The +9.7pp logistic baseline captures essentially the same lift as a tuned LightGBM. Practical recommendation: use logistic regression with TF-IDF features for the production reranker. It has:
- Same interpretability (linear coefficients)
- Same training speed
- Trivially calibrated probabilities
- 95% of the LightGBM lift

The TF-IDF feature signal is strong enough that complex classifiers don't add much.

## Caveat

Still Lingxi-test direction only. MDD-direction reranker collapse (commit `7ccb1b3`) holds across both logistic and LightGBM (tested separately).

