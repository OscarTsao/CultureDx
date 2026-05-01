# Gap F Multi-Classifier Ensemble + Confidence-Gated Reranker

**Date:** 2026-05-02
**Status:** CPU-only. Uncommitted.

## §A — Single-classifier comparison

| Classifier | Baseline Top-1 | Rerank Top-1 | Δ |
|---|---:|---:|---:|
| Logistic | 0.4700 | 0.5700 | +10.0pp |
| **LightGBM** | 0.4700 | **0.5733** | **+10.3pp** |
| Random Forest | 0.4700 | 0.5500 | +8.0pp |
| Gradient Boosting | 0.4700 | 0.5600 | +9.0pp |

LightGBM is best by ~0.3pp. All 4 classifiers within 2.3pp of each other.

## §B — Ensemble of 4 classifiers (mean of probabilities)

| Configuration | Top-1 | Δ |
|---|---:|---:|
| Single best (LightGBM) | 0.5733 | +10.3pp |
| **Mean ensemble (LR + LGBM + RF + GB)** | **0.5700** | **+10.0pp** |

**Ensemble does NOT improve over single best.** Models are too similar in their feature usage and decision boundaries; averaging doesn't add diversity.

## §C — Confidence-weighted reranker (threshold sweep)

Override rank-1 only if (rerank-top-1 score) − (rerank-top-2 score) ≥ threshold.

| Threshold | Top-1 | Δ |
|---|---:|---:|
| 0.0 (always override) | 0.5733 | **+10.3pp** |
| 0.05 | 0.5600 | +9.0pp |
| 0.10 | 0.5500 | +8.0pp |
| 0.15 | 0.5400 | +7.0pp |
| 0.20 | 0.5333 | +6.3pp |
| 0.30 | 0.5100 | +4.0pp |
| 0.50 | 0.4733 | +0.3pp |

**Confidence-gating monotonically reduces lift.** The full reranker (threshold=0) is optimal.

This is interesting — it implies the reranker's low-confidence overrides ARE generally correct, not just noise. The reranker isn't over-confident; gating loses real signal.

## §D — Conclusions

1. **No ensemble benefit.** Single LightGBM with TF-IDF features is sufficient.
2. **No confidence gating benefit.** Trust the reranker's full output.
3. **Production architecture: single LightGBM with TF-IDF features, no gating.**

This simplifies the architecture proposal: the reranker is a single learned model, and its full output is used (no thresholding). The simplicity is a strength.

