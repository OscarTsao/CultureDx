# Gap F Marginal Source Contribution Sweep

**Date:** 2026-05-01 23:53:12
**Branch:** tier2b/hierarchical-prompt @ HEAD
**Status:** CPU-only sweep. Uncommitted.

## TL;DR

Tests marginal contribution of each non-Qwen source: Gemma, TF-IDF+LR (in-domain Lingxi), Pure TF-IDF kNN.
Δ recall = full union coverage − coverage without that source. Higher = source contributes uniquely.
Δ noise = full union noise − noise without that source. Higher = source contributes pollution.

---

## §All-source-combination coverage table

| Source combination | size=2 coverage | avg pool size | size=1 noise per case |
|---|---:|---:|---:|
| qwen | 56.8% | 4.8 | 3.93 |
| qwen+gemma | 60.5% | 5.8 | 3.93 |
| qwen+gemma+pure_tfidf | 72.8% | 7.1 | 3.93 |
| qwen+gemma+tfidf_lr | 81.5% | 7.5 | 5.75 |
| qwen+gemma+tfidf_lr+pure_tfidf | 84.0% | 8.0 | 5.75 |
| qwen+pure_tfidf | 70.4% | 6.4 | 3.93 |
| qwen+tfidf_lr | 79.0% | 6.8 | 5.75 |
| qwen+tfidf_lr+pure_tfidf | 82.7% | 7.4 | 5.75 |

---

## §Marginal contribution per non-Qwen source

ΔRecall = coverage(full union) − coverage(union without this source)
ΔNoise = noise(full union) − noise(union without this source)

| Source | Δ recall (size=2) | Δ noise (size=1) | ROI = Δrecall/Δnoise |
|---|---:|---:|---:|
| gemma | +1.2pp | +0.00 | ∞ |
| tfidf_lr | +11.1pp | +1.82 | 6.1 |
| pure_tfidf | +2.5pp | +0.00 | ∞ |

Read this as: each non-Qwen source's UNIQUE marginal contribution to recall, traded against its noise added on size=1 cases.

---

## §Decision matrix

| Source | Recommendation |
|---|---|
| gemma | DROP from candidate union — redundant with other sources |
| tfidf_lr | **KEEP gated** — high recall but noisy; use only on size=2 candidates |
| pure_tfidf | Marginal value — consider as feature/disagreement signal only |

---

## §Summary key configurations

| Configuration | size=2 cov | size=1 noise |
|---|---:|---:|
| qwen | 56.8% | 3.93 |
| qwen+gemma | 60.5% | 3.93 |
| qwen+tfidf_lr | 79.0% | 5.75 |
| qwen+pure_tfidf | 70.4% | 3.93 |
| qwen+gemma+tfidf_lr | 81.5% | 5.75 |
| qwen+gemma+pure_tfidf | 72.8% | 3.93 |
