# v0.2 Paper-Claim Reframe — TF-IDF Lexical Channel as the Architectural Contribution

**Date:** 2026-05-03
**Branch:** tier2b/hierarchical-prompt @ HEAD
**Status:** Read-only synthesis. Supersedes earlier "Lexical-Feature Reranker is the v0.2 contribution" framing. paper-integration-v0.1 (c3b0a46) frozen; BETA-2b primary-only contract preserved.

## §A — The reframe in one paragraph

**OLD framing** (from EXHAUSTIVE_FINAL_ROUND_SUMMARY.md, EXHAUSTIVE_PHASE_EF_APPENDIX.md, EXHAUSTIVE_SWEEP_SYNTHESIS.md):
"Lexical-Feature Reranker (LightGBM on TF-IDF features) is the single positive Gap F component, providing +6.80pp ± 0.93pp 5-fold CV Top-1 lift."

**NEW framing** (post-2×2 ablation):
"The architectural contribution is the **TF-IDF lexical channel itself**, not the learned reranker. Specifically, calibrated TF-IDF + LR scoring as a candidate channel provides +7.20pp Top-1 (5-fold CV ± 1.21pp) when fused with Qwen rank via per-fold-tuned linear combination. The LightGBM wrapper that earlier docs spotlighted contributes a marginal −0.20pp (noise-level) over the simpler linear fusion; LightGBM without TF-IDF features contributes −0.10pp (essentially zero). The +7pp lift is entirely attributable to the lexical channel; the choice of fusion mechanism (linear combo vs LightGBM) is secondary."

## §B — Headline ablation (5-fold CV, seed=42, same fold split across all cells)

| Cell | Config | Δ Top-1 | Std |
|---|---|---:|---:|
| A | Qwen rank-1 baseline | (0.5200 abs) | ± 0.0138 |
| **C** | **TF-IDF, NO ML (per-fold tuned linear combo)** | **+7.20pp** | **± 1.21pp** |
| D | LightGBM with Qwen-only features (no TF-IDF) | -0.10pp | ± 1.53pp |
| E | LightGBM with full features (TF-IDF + Qwen) | +7.00pp | ± 1.00pp |

Key decompositions:
- **C − A = +7.20pp**: TF-IDF channel alone, no learning. The architectural contribution.
- **D − A = -0.10pp**: ML alone with no orthogonal channel. Zero.
- **E − C = -0.20pp**: ML's marginal contribution given TF-IDF. Noise-level negative.
- **E − D = +7.10pp**: TF-IDF channel given ML. Same magnitude as C − A.

## §C — Sparse baseline comparison: TF-IDF vs BM25

Standard sparse lexical retrieval baseline comparison (V02_BM25_ABLATION.md):

Standalone Top-1 (gold[0] match):

| Method | Top-1 |
|---|---:|
| Qwen3-32B-AWQ rank-1 | ~0.47 |
| TF-IDF + LR | 0.5367 |
| BM25 corpus-kNN (best k1, b) | 0.4070 |
| BM25 def-query (best k1, b grid) | 0.1720 |

5-fold CV reranker lift:

| Cell | Δ Top-1 |
|---|---:|
| F. TF-IDF, no ML | +7.20pp ± 1.21 |
| G. TF-IDF + LightGBM | +7.00pp ± 1.00 |
| **D2. BM25 corpus-kNN, no ML** | **+0.00pp ± 0.0** |
| **E2. BM25 corpus-kNN + LightGBM** | **-1.5pp ± 1.9** |
| **E_best. BM25 def-query (best grid) + LightGBM** | **-0.1pp ± 1.8** |

**TF-IDF beats BM25 by ~8.5pp across configurations.** This is "Scenario C" of the BM25 ablation — TF-IDF + LR's calibration step is what works, not raw sparse retrieval.

## §D — Mechanism for the reframe (paper-quotable explanation)

Psychiatric differential diagnosis decision boundaries are constructed primarily from **lexical anchors aligned with ICD-10 criterion text** — specific symptom phrases ("自殺意念", "持續六個月", "強迫想法", "驚恐發作"), duration markers, and severity modifiers. These anchors are directly mentioned as constituent elements of the diagnostic criteria.

- **Dense neural retrieval** (bge-m3 +3.7pp, hybrid +5.7pp, cross-encoders -17 to -38pp) learns *semantic similarity* on general-purpose corpora. Psychiatric symptoms cluster tightly in semantic space (depression/anxiety/PTSD/adjustment overlap), so dense methods *smooth over* the criterion-level lexical anchors that distinguish them.
- **Cross-encoders** (-17 to -38pp catastrophic) directly score (case, definition) similarity; semantic-similarity scoring inverts the diagnostic-discrimination axis when the discrimination is between near-synonymous symptom clusters.
- **Unsupervised sparse retrieval** (BM25 corpus-kNN +0.0pp, def-query -0.1pp) preserves lexical specificity but lacks supervised calibration of which lexical features map to which diagnostic codes.
- **Supervised TF-IDF + LR** captures the lexical anchors AND learns the calibration of (anchor → diagnosis) mapping in a single layer. The +7.2pp comes from this calibration step; learned reranker (LightGBM) adds nothing because the calibration is already in the LR-trained TF-IDF probabilities.

## §E — Eight IR-SOTA methods all defeated by TF-IDF + LR

Comprehensive evidence (from EXHAUSTIVE_PHASE_EF_APPENDIX.md, V02_BM25_ABLATION.md):

| IR method | Δ Top-1 | Verdict |
|---|---:|---|
| TF-IDF + LR (LightGBM or linear combo) | **+7.0 to +7.2pp** | ✅ winner |
| bge-m3 dense kNN (standalone) | +3.7pp | TF-IDF wins by 2.6× |
| bge-m3 hybrid (dense+sparse+ColBERT) | +5.7pp | TF-IDF wins by 1.3× |
| Reranker with full bge-m3 1024-dim emb | +4.7pp | TF-IDF wins |
| RRF fusion (qwen+tfidf+bge) | +2.3pp | dilutes TF-IDF signal |
| **BM25 corpus-kNN (linear combo)** | **+0.0pp** | unsupervised lexical fails |
| **BM25 def-query (best k1, b)** | **-0.1pp** | unsupervised lexical fails |
| Cosine reranker (bge cosine, no learning) | -18.25pp | semantic smoothing fails |
| **bge-reranker-v2-m3 cross-encoder** | -22.5pp | SOTA cross-encoder fails |
| **gte-multilingual-reranker** | -17.4pp | multilingual cross-encoder fails |
| jina-reranker-v3 | predict-failed | — |
| jina-reranker-v2-multilingual | -18.0pp | fails |
| mxbai-rerank-large-v2 | -37.6pp | catastrophic |
| mxbai-rerank-base-v2 | -26.8pp | fails |
| bge-reranker-v2-gemma | -32.5pp | fails |
| bge-reranker-large | -31pp standalone, +1.8pp set-cov | fails as reranker |

## §F — Updated v0.2 architectural claim

**Final v0.2 claim:** "We introduce a **calibrated TF-IDF lexical channel** as a candidate-source augmentation for psychiatric LLM diagnosticians, providing +7.20pp Top-1 lift (5-fold CV, ± 1.21pp) on Lingxi-icd10. This contribution is paradigm-level — supervised TF-IDF + LR scoring of disorder-specific lexical anchors. The fusion mechanism (linear combination of Qwen rank with TF-IDF probability vs LightGBM wrapper) is secondary; both achieve essentially identical 5-fold CV performance."

**Limitations to disclose honestly:**
- Lift is corpus-style-dependent: +7pp on Lingxi (criterion-text), -2.4pp on MDD (dialogue-style). Verified across 8 ML methods × 4 directions.
- TF-IDF baseline LR hyperparameters matter: fresh-fit n-gram sweep gives +3.3 to +4.7pp, vs +7pp for the prior tuned LR. Suggests calibration quality matters.
- bge-m3 dense kNN provides initial cross-corpus evidence (+7.4pp size=2 set-coverage on MDD); future work for dialogue corpora.

**Optional additional channels** (validated as separately positive but not headline):
- QLoRA fine-tuned Qwen3-8B: Top-1 56.67% raw (+9.7pp), highest single-method raw Top-1 in sweep
- MoE-routing for cross-corpus (Lingxi+MDD): +3.98pp combined
- Calibrated abstention top-10% confidence: 80% selective accuracy

## §G — Reviewer Q&A pre-emption

**Q: Why TF-IDF and not BM25?**
A: BM25 was tested. BM25 corpus-kNN gives +0.0pp 5-fold CV; BM25 def-query (best of k1, b grid) gives -0.1pp. TF-IDF + LR's supervised calibration step (which BM25 lacks) is the operative mechanism, not raw sparse retrieval scoring.

**Q: Why TF-IDF and not dense neural retrieval?**
A: bge-m3 dense kNN gives +3.7pp standalone vs TF-IDF's +9.7pp single-split. Cross-encoders (bge-reranker-v2-m3, gte-multilingual, mxbai variants, jina variants) are all catastrophically negative (-17 to -38pp). 8 IR SOTA methods tested; all defeated by TF-IDF + LR. Mechanism: psychiatric diagnostic discrimination depends on lexical anchors that dense methods semantically smooth over.

**Q: What does the LightGBM reranker contribute?**
A: -0.20pp ± noise. The LightGBM wrapper has noise-level marginal contribution over a simple per-fold-tuned linear combination of (Qwen rank decay) + (TF-IDF probability). Linear combo at +7.20pp matches LightGBM at +7.00pp. The architectural contribution is the lexical channel, not the learned ranker.

**Q: Why does ML alone fail (D = -0.10pp)?**
A: Without orthogonal lexical signal, LightGBM trained on Qwen's internal features (rank, met_ratio, in_confirmed, class one-hot, n_confirmed, is_primary, in_pair_with_primary) extracts no additional information beyond Qwen rank-1. This confirms the +7pp comes entirely from injecting an external paradigm channel, not from learning over Qwen's existing signal.

**Q: Cross-corpus generalization?**
A: Lingxi (criterion-text) +7.20pp; MDD (dialogue-style) -2.38pp combined reranker. Asymmetry verified across 8 ML methods × 4 directions — corpus property, not method choice. bge-m3 dense kNN gives +7.4pp size=2 set-coverage on MDD direction; flagged as future work for dialogue-aware encoders. Disclosed as honest limitation.

**Q: Why not fine-tune the LLM?**
A: We did. QLoRA-Qwen3-8B achieves Top-1 56.67% raw, the highest single-method raw Top-1 in our 109-experiment sweep. This is reported as a v0.2+ optional component, not the headline, because (a) it changes the production deployment surface (fine-tuned weights vs reranker on existing Qwen3-AWQ outputs), and (b) the v0.2 claim is about the architectural channel, not LLM-side optimization which is orthogonal.

## §H — Deprecate / demote earlier framings

Items that earlier docs over-emphasized:
- "Stacked ensemble (LR + LightGBM + LambdaMART) +9.13pp ± 1.96pp" — DEMOTE to a single line in v0.2; the +1.9pp over single-LightGBM doesn't justify 3× training cost given LightGBM matches no-ML linear combo.
- "Combined 86-feature reranker (LDA + symptom keywords + temporal + PHQ/GAD)" — DEMOTE; CV gain (+6.57pp ± 2.52pp) lower than no-ML linear combo (+7.20pp ± 1.21pp).
- "LDA K=12 topic features standalone +9.0pp single-split" — DEMOTE; subsumed by LDA-in-combined +6.57pp CV; symptom keywords subsumed.
- All "Lexical-Feature Reranker is the architectural contribution" claims — REPLACE with "TF-IDF lexical channel is the architectural contribution; reranker is one of multiple equivalent fusion choices."

## §I — Lineage

This document is the canonical v0.2 paper-claim reference. Earlier appendix docs (EXHAUSTIVE_*, V02_*) are kept for traceability but no longer load-bearing for the architectural framing decision.

paper-integration-v0.1 (c3b0a46) frozen. BETA-2b primary-only contract preserved across all 109+ experiments. No production code, manuscript, or canonical tag is touched.

## §J — Linear combo weight stability across folds

**Protocol:** Same 5-fold CV (seed=42, KFold shuffle), same weight grid (w_qwen ∈ {0.3,0.5,0.7,1.0,1.5,2.0}, w_tfidf ∈ {0.3,0.5,1.0,1.5,2.0,3.0}), same data as Cell C. Per-fold weights tuned on train split and evaluated on held-out test split.

### Per-fold best weights

| Fold | w_qwen | w_tfidf | train_acc | test_acc |
|---:|---:|---:|---:|---:|
| 1 | 0.5 | 1.5 | 0.6025 | 0.5700 |
| 2 | 0.3 | 2.0 | 0.5962 | 0.6100 |
| 3 | 0.3 | 2.0 | 0.5962 | 0.6100 |
| 4 | 0.3 | 1.5 | 0.6025 | 0.5800 |
| 5 | 0.3 | 2.0 | 0.6012 | 0.5900 |

### Weight coefficient of variation

| Weight | Mean | Std | CV |
|---|---:|---:|---:|
| w_qwen | 0.34 | 0.08 | 23.53% |
| w_tfidf | 1.80 | 0.24 | 13.61% |

**Stability verdict: STABLE** — both CVs below 30% threshold.

### Fixed-weight vs per-fold-tuned comparison

| Config | Mean test acc | Δ Top-1 (over baseline) | Std |
|---|---:|---:|---:|
| Per-fold-tuned Cell C | 0.5920 | +7.20pp | ±1.60pp |
| Fixed weights (w_qwen=0.3, w_tfidf=2.0) | 0.5990 | +7.90pp | ±0.92pp |
| Gap (fixed − per-fold-tuned) | — | **+0.70pp** | — |

Fixed-weight CV matches (and slightly exceeds) per-fold-tuned CV at +7.90pp vs +7.20pp. This is an atypical result: normally per-fold tuning should be ≥ fixed weights. The small positive gap (+0.70pp) arises because one fold (fold 1) tuned to a suboptimal weight on training data that happened to underperform the global optimum on that fold's test split. The difference is within noise (±1.6pp std).

### Paper-reportable conclusion

Weights are stable and essentially fixed across folds. The paper can report **w_qwen=0.3, w_tfidf=2.0 as fixed hyperparameters** validated by 5-fold CV — this is not an overfitting risk. The per-fold-tuned protocol used in the headline +7.20pp result is a conservative estimate; the fixed-weight equivalent gives +7.90pp. Both are consistent with the architectural claim.

**Recommendation:** Report headline as +7.20pp (per-fold-tuned, conservative) with footnote that fixed weights w_qwen=0.3, w_tfidf=2.0 give +7.90pp (±0.92pp) on the same 5-fold CV split.
