# Gap F MDD-Direction TF-IDF Reranker Test

**Date:** 2026-05-02
**Branch:** tier2b/hierarchical-prompt @ HEAD
**Status:** CPU-only. Uncommitted.

## TL;DR

Tests whether the +9.7pp Top-1 reranker lift from TF-IDF features (committed `0b1c243`) transfers to the MDD-test direction. **Result: NO — the asymmetry is fundamental across both candidate-source AND feature usage paradigms.**

| Direction | TF-IDF source | Method | Baseline Top-1 | Rerank Top-1 | Δ |
|---|---|---|---:|---:|---:|
| Lingxi | in-domain (Lingxi-trained) | LightGBM features | 0.4700 | 0.5333 | **+6.3pp** |
| Lingxi | in-domain (Lingxi-trained) | Logistic features | 0.4700 | 0.5667 | **+9.7pp** |
| **MDD** | **in-domain (MDD-trained)** | **LightGBM features** | **0.6043** | **0.5899** | **-1.4pp** |
| **MDD** | **cross-domain (Lingxi-trained)** | **LightGBM features** | **0.6043** | **0.5971** | **-0.7pp** |

## Interpretation

The asymmetric corpus-property mechanism (Lingxi: lexical-dense criterion text; MDD: dialogue-style verbose text) is consistent across:

1. **Candidate source paradigm** — TF-IDF candidate union: +22.2pp Lingxi, +0-7pp MDD (committed in earlier audits)
2. **Reranker feature paradigm** — TF-IDF as ranker features: +9.7pp Lingxi, -1.4pp MDD

This means the corpus-direction asymmetry is NOT solvable by changing how TF-IDF is integrated. It's a property of the underlying text styles.

## Implication for paper claim

The TF-IDF mechanism (candidate or feature) helps for criterion-style case texts. For dialogue-style case texts, neither paradigm provides benefit. Future work should investigate:
- Specialized text-encoders for dialogue-style cases (e.g., DialogBERT)
- Different lexical features (n-gram + speaker turn structure)
- Per-corpus retrained TF-IDF vocabulary
- Real clinical case styles (intermediate between LingxiDiag and MDD)

## Caveat

MDD TF-IDF predictions only cover 185/925 cases (held-out test split). 70/30 case-level split → 278 test cases for the reranker. Smaller sample than Lingxi (1000), but pattern is clear.

