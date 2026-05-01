# Gap F Reranker Feature Ablation + 5-Fold CV + n-gram Sweep

**Date:** 2026-05-02
**Branch:** tier2b/hierarchical-prompt @ HEAD

## §A — Feature ablation (drop-one-feature-group)

| Drop | Δ Top-1 | Impact on lift |
|---|---:|---:|
| (full features) | +10.33pp | baseline |
| -tfidf | +0.33pp | **-10.0pp** (DOMINANT) |
| -in_confirmed | +9.00pp | -1.3pp |
| -in_pair | +9.33pp | -1.0pp |
| -class_onehot | +9.33pp | -1.0pp |
| -rank | +9.67pp | -0.7pp |
| -n_confirmed | +9.67pp | -0.7pp |
| -met_ratio | +10.00pp | -0.3pp |
| -is_primary | +10.33pp | 0.0pp (redundant) |

**Key finding: TF-IDF features account for ~97% of the +10.3pp lift.** Without TF-IDF features, the ranker barely beats baseline (+0.33pp). All other features combined add ~0.3pp.

This confirms paper claim: TF-IDF as feature is the central architectural contribution.

## §B — 5-Fold Cross-Validation

| Fold | Baseline Top-1 | Rerank Top-1 | Δ |
|---:|---:|---:|---:|
| 1 | 0.5750 | 0.6550 | +0.080 |
| 2 | 0.4950 | 0.5550 | +0.060 |
| 3 | 0.4900 | 0.5650 | +0.075 |
| 4 | 0.5150 | 0.5700 | +0.055 |
| 5 | 0.5250 | 0.5950 | +0.070 |
| **Mean** | **0.5200** | **0.5880** | **+0.0680** |
| SD | 0.034 | 0.038 | 0.0093 |

**5-fold CV mean Δ: +6.80pp ± 0.93pp**

This is more conservative than the original 70/30 single-split estimate (+10.3pp) and the bootstrap CI mean (+8.15pp). 5-fold CV is the most rigorous statistical estimate for paper claim.

**Updated paper-defensible Top-1 lift: +6.80pp ± 0.93pp (5-fold CV).** Lower than headline +10pp but still clearly larger than:
- LLM ensemble (+3.7pp)
- Confusion-pair expansion (+4.9pp)

## §C — TF-IDF n-gram range sweep

Fresh-fit TF-IDF LR with different n-gram ranges (sklearn-default hyperparameters):

| n-gram | Top-1 lift |
|---|---:|
| (1, 1) — unigrams only | +4.67pp |
| (1, 2) | +4.00pp |
| (1, 3) | +4.67pp |
| (2, 3) — bigrams + trigrams only | +3.33pp |

Fresh-fit LR gives ~+4-5pp lift regardless of n-gram. The original `outputs/tfidf_baseline/` uses better-tuned LR hyperparameters and gives +10pp single-split.

**Implication:** the reranker mechanism is robust (gives positive lift across n-gram choices), but the TF-IDF predictor's own hyperparameters matter for the absolute magnitude.

## §D — Updated key claims

| Statistic | Value | Method |
|---|---:|---|
| Single 70/30 split | +10.3pp | original measurement |
| Bootstrap CI (50 reps) | +8.15pp ± 2.09pp, [3.89, 12.52] | resampled splits |
| **5-fold CV** | **+6.80pp ± 0.93pp** | **most rigorous** |
| Fresh-fit n-gram sweep | +3.3 to +4.7pp | LR hyperparams matter |

For paper, recommend: report 5-fold CV result (+6.80pp ± 0.93pp) as the headline lift, with bootstrap CI [+3.9, +12.5] as broad uncertainty range. Note that LR hyperparameter tuning matters for absolute magnitude.

