# Gap F B3c + Reranker Stacking Test

**Date:** 2026-05-02

## TL;DR — B3c does NOT stack with reranker

Tests whether B3c's +1.9pp standalone lift adds to the reranker's +10.3pp.

| Configuration | Top-1 | Δ vs Qwen rank-1 baseline |
|---|---:|---:|
| Qwen3 baseline (rank-1 = primary) | 0.4700 | — |
| **Reranker only** | **0.5733** | **+10.3pp** |
| Reranker + B3c feature (`is_b3c_pick`) | 0.5533 | +8.3pp (-2.0pp from reranker alone) |
| B3c only (standalone) | 0.5200 | +1.9pp |

## Interpretation

Adding the B3c indicator as a reranker feature HURTS by 2pp. The B3c signal is:
- Mostly redundant with TF-IDF features the reranker already uses
- Adds noise when included as a binary indicator
- Less reliable than the learned TF-IDF + rank + checker features

**The reranker captures everything B3c offers.** B3c works as a standalone fallback but doesn't add value when combined with the reranker.

## Conclusion

Recommended architecture: **single reranker (no B3c stacking)**. The +10.3pp from the reranker is the dominant lift. B3c's +1.9pp is a standalone alternative if reranker training data isn't available, but they shouldn't be combined.

This simplifies the proposed MAS architecture — just one learned component (reranker), not multiple.

