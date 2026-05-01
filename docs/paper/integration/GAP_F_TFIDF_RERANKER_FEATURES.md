# Gap F TF-IDF as Reranker Features (not as candidate source)

**Date:** 2026-05-02 00:00:29
**Branch:** tier2b/hierarchical-prompt @ HEAD
**Status:** CPU-only. Uncommitted.

## TL;DR

Tests whether using TF-IDF probabilities/ranks/disagreement as features in a learned ranker (rather than as a candidate source) improves Top-1 selection from Qwen3 top-5.

Train/test: 70/30 case-level split (no test-tuning), N=1000 lingxi_icd10 cases.

---

## §Reranker comparison

| Ranker | Features | Test cases | Baseline Top-1 | Rerank Top-1 | Δ |
|---|---|---:|---:|---:|---:|
| Logistic | basic only (rank, met, confirmed, class one-hot) | 300 | 0.4700 | 0.4600 | -0.0100 |
| Logistic | basic + TF-IDF features | 300 | 0.4700 | 0.5667 | +0.0967 |
| LightGBM | basic + TF-IDF features | 300 | 0.4700 | 0.5333 | +0.0633 |

---

## §Feature importance

### Logistic basic (no TF-IDF features)

| Feature | Coefficient |
|---|---:|
| `is_F41` | +1.1300 |
| `is_F32` | +0.7166 |
| `in_confirmed` | +0.4048 |
| `rank` | -0.3989 |
| `is_primary` | +0.3356 |
| `met_ratio` | +0.3022 |
| `is_F98` | +0.2745 |
| `in_pair_with_primary` | -0.2294 |
| `is_F42` | +0.2266 |
| `is_F45` | +0.2081 |

### Logistic full (basic + TF-IDF features)

| Feature | Coefficient |
|---|---:|
| `tfidf_rank` | -1.1527 |
| `tfidf_prob` | +0.9525 |
| `is_F41` | +0.5835 |
| `is_F32` | +0.4511 |
| `is_F51` | -0.2714 |
| `in_pair_with_primary` | -0.2461 |
| `in_confirmed` | +0.2414 |
| `is_F20` | -0.2387 |
| `is_Z71` | +0.2310 |
| `is_F39` | -0.2111 |

### LightGBM full

| Feature | Importance (split count) |
|---|---:|
| `tfidf_prob` | 2231 |
| `met_ratio` | 546 |
| `tfidf_rank` | 388 |
| `n_confirmed` | 370 |
| `rank` | 285 |
| `is_F41` | 177 |
| `qwen_tfidf_top1_agree` | 152 |
| `in_pair_with_primary` | 87 |
| `is_F32` | 85 |
| `is_F42` | 61 |

---

## §Conclusion

LightGBM ranker with TF-IDF features achieves Top-1 = 0.5333 (+6.3pp over Qwen rank-1 baseline). Strong evidence that TF-IDF as reranker features is high-impact.
