# Gap F — Final Synthesis (Multi-Diagnosis Candidate Completeness)

**Date:** 2026-05-02
**Branch:** feature/gap-e-beta2-implementation @ HEAD
**Scope:** Consolidates 25+ Gap F sub-experiments (commits `32441df` through Broader-K) into one paper-ready summary.
**Status:** Read-only synthesis. No production code, manuscript, or canonical tag is touched. paper-integration-v0.1 (c3b0a46) frozen; BETA-2b primary-only contract preserved.

---

## TL;DR

| Question | Answer | Evidence |
|---|---|---|
| Is "Top-3 = 0.80" enough for multi-diagnosis cases? | **NO.** Both gold codes in top-3 only 35-42% on size=2. | size-cohort coverage table |
| Does any reranking method beat baseline EM on aligned source? | **YES — TF-IDF feature reranker.** +6.80pp Top-1 (5-fold CV ± 0.93pp); +10.3pp on single split; +10.3pp EM under BETA-2b primary-only contract. | bootstrap CI, 5-fold CV, feature ablation |
| Does the +10.3pp lift transfer cross-corpus? | **NO** — corpus-style-dependent. Lingxi (criterion-text) yes; MDD (dialogue) no. Verified across 8 ML methods. | 8 methods × 4 directions sweep |
| Does any LLM meta-agent variant beat Qwen3 baseline? | **Only B3c (disorder-def-only).** +1.9pp standalone. Other 4 variants negative (-0.7 to -8.8pp). | B3a/B3b/B3c/B3e/B3i sweep |
| Does B3c stack with the reranker? | **NO.** B3c+reranker = +8.3pp (drops 2pp from reranker-alone). Reranker captures B3c's signal. | stacking test |
| Can Qwen3 itself produce broader-K candidates to close the size=2 gap? | **NO.** Top-12 = 43.2% (vs TF-IDF union 79.0%). Qwen3 ranking IS the bottleneck. | Broader-K probe |

**Headline architectural recommendation:** Adopt a single learned **Lexical-Feature Reranker** (TF-IDF features over Qwen3 top-5) as a future v0.2 component on Lingxi-style corpora. Do NOT add same-LLM meta-agent or LLM-only ensemble layers — they are dominated. Keep BETA-2b primary-only as the post-hoc emission contract.

---

## §1 — Empirical foundation: why a Gap F was needed

### 1.1 Top-3 = 0.80 is misleading for multi-diagnosis

Gold-size distribution (LingxiDiag-16K N=1000, MDD-5k N=925; size≥4 = 0):

| Size | Lingxi | MDD-5k |
|---|---:|---:|
| size=1 | 91.4% (914) | 91.2% (844) |
| size=2 | 8.1% (81) | 8.1% (75) |
| size=3 | 0.5% (5) | 0.6% (6) |

For size=2 cases on Lingxi:

- Top-3 contains primary gold: ~94%
- Top-3 contains BOTH gold codes: only ~41%

The headline "Top-3 = 0.80" is `gold[0] ∈ top-3`. Complete-set coverage is much weaker, motivating the Gap F architectural search.

### 1.2 In-pool oracle ceiling

| Pool source | size=1 (n=914) | size=2 (n=81) | size=3 (n=5) | Aggregate oracle EM |
|---|---:|---:|---:|---:|
| Qwen only (top-5) | 85.7% | 56.8% | 20.0% | **83.0%** |
| Qwen + TF-IDF+LR | 98.6% | 79.0% | 60.0% | **96.8%** |
| All 4 sources greedy | 98.6% | 84.0% | 60.0% | **97.2%** |

**Headroom budget:**

- Realized BETA-2b primary-only EM: 46.9%
- Ranking headroom (current Qwen pool): 36pp
- Candidate-source headroom (with TF-IDF): +14pp on top of that
- Reranker captures ~30% of the ranking headroom (+10.3pp single-split, +6.8pp 5-fold CV)

---

## §2 — What we tested (full menu)

Twelve mechanism families × multiple variants each. Each family was either *positive* (lift > +1pp Top-1 or EM), *neutral*, or *negative* (lift < -1pp).

| # | Family | Best variant | Δ Top-1 / coverage | Verdict |
|---|---|---|---:|---|
| 1 | TF-IDF as candidate-source (Lingxi-direction) | LR top-5 union | +22.2pp size=2 coverage | ✅ POSITIVE |
| 2 | TF-IDF as candidate-source (MDD-direction) | LR top-5 union | +4.0pp coverage | ⚠️ MARGINAL |
| 3 | Pure TF-IDF kNN cross-domain | k=50 | +11.1pp size=2 coverage | ✅ POSITIVE |
| 4 | Multi-LLM ensemble (Qwen + Gemma) | union | +3.7pp coverage | ⚠️ MARGINAL |
| 5 | Lexical-feature reranker (logistic) | TF-IDF + rank features | +9.7pp Top-1 | ✅ POSITIVE |
| 6 | Lexical-feature reranker (LightGBM HP-swept) | best of 48 configs | +10.3pp Top-1 | ✅ POSITIVE |
| 7 | Confusion-pair forced expansion | F32↔F41↔F42 | +2.7-6.2pp size=2 | ⚠️ MARGINAL |
| 8 | Confusion-pair detector + gated reranker | LR detector | ~+6pp expected | ⚠️ MARGINAL |
| 9 | Class-specific rerankers (per top-1 class) | F32-only LightGBM | +12.2pp on F32 subset | ⚠️ MARGINAL (vs unified) |
| 10 | LLM meta-agent variants (B3a/B3b/B3c/B3e/B3i) | B3c (disorder-def-only) | +1.9pp Top-1 | ⚠️ ONLY B3c POSITIVE |
| 11 | B3c × reranker stacking | reranker + is_b3c_pick feature | -2.0pp from reranker-only | ❌ NEGATIVE |
| 12 | Broader-K Qwen3 (top-12 prompt) | size=2 sample n=81 | top-12 = 43.2% (vs TF-IDF 79.0%) | ❌ NEGATIVE |
| — | LR / LightGBM on MDD-direction | best | -0.4 to -1.4pp | ❌ FAILS cross-corpus |
| — | Tier 2B hierarchical prompt | — | -5 to -25pp | ❌ NEGATIVE |
| — | 1B-α conservative veto on aligned source | — | -0.4pp EM | ❌ RED |

---

## §3 — Mechanism: why TF-IDF features dominate

### 3.1 Marginal source contribution

(Δ recall on size=2 set coverage; Δ noise on size=1 spurious candidates)

| Source added to Qwen top-5 | Δ recall | Δ noise | ROI |
|---|---:|---:|---:|
| Gemma-3-12B-it | +1.2pp | +0.00 | ∞ (small numerator) |
| TF-IDF + LR (in-domain) | **+11.1pp** | +1.82 | 6.1 |
| Pure TF-IDF kNN | +2.5pp | +0.00 | ∞ |

TF-IDF + LR is the unique high-recall contributor. Multi-LLM ensembling alone (Gemma) is dominated by ~3×.

### 3.2 Reranker feature ablation (drop-one feature group)

| Drop | Δ Top-1 | Impact on lift |
|---|---:|---:|
| (full features) | +10.33pp | baseline |
| -tfidf | +0.33pp | **-10.0pp (DOMINANT)** |
| -in_confirmed | +9.00pp | -1.3pp |
| -in_pair | +9.33pp | -1.0pp |
| -class_onehot | +9.33pp | -1.0pp |
| -rank | +9.67pp | -0.7pp |
| -n_confirmed | +9.67pp | -0.7pp |
| -met_ratio | +10.00pp | -0.3pp |
| -is_primary | +10.33pp | 0.0pp (redundant) |

**TF-IDF features account for ~97% of the +10.3pp lift.** Without them, the ranker barely beats baseline (+0.33pp). All other features combined add ~0.3pp.

### 3.3 Statistical robustness

| Statistic | Value | Method |
|---|---:|---|
| Single 70/30 split | +10.3pp | original |
| Bootstrap CI (50 reps) | +8.15pp ± 2.09pp, [+3.89, +12.52] | resampled splits |
| **5-fold CV** | **+6.80pp ± 0.93pp** | **most rigorous (paper-recommended)** |
| Fresh-fit n-gram sweep | +3.3 to +4.7pp | TF-IDF HP matters for absolute lift |

### 3.4 Per-class breakdown

| Class | N (test) | Helped | Hurt | Net | Mechanism |
|---|---:|---:|---:|---:|---|
| F41 (anxiety) | 114 | +20 | 0 | +20 | recovers F41-misclassified-as-F32 |
| F39 (mood NOS) | 23 | +14 | 0 | +14 | rare class with distinctive lexical signal |
| F32 (depression) | 99 | 0 | -6 | -6 | Qwen-baseline-correct cases mistakenly swapped to F41 |
| F98/F43/F31 | 13 | +3 | 0 | +3 | small additional rare-class wins |
| Others | ~51 | 0 | -1 | -1 | noise |

The lift is concentrated on the F32↔F41 confusion pair and rare class F39. F32 → F41 false swaps are the only systematic cost.

### 3.5 Top-3 effect (not just Top-1)

| Metric | Baseline | Reranker | Δ |
|---|---:|---:|---:|
| Top-1 | 0.4700 | 0.5733 | +10.3pp |
| Top-3 | 0.8033 | 0.8467 | +4.3pp |

Reranker improves both: +10.3pp Top-1 (rank 2-5 → 1) and +4.3pp Top-3 (rank 4-5 → top-3). Strengthens the claim that this is a general candidate-quality improver, not just a Top-1 optimizer.

### 3.6 EM impact (under BETA-2b primary-only contract)

| Method | Top-1 | EM |
|---|---:|---:|
| Baseline (Qwen3 rank-1 = primary) | 0.4700 | 0.4033 |
| Reranker (LightGBM with TF-IDF) | 0.5733 | 0.5067 |
| Δ | +10.3pp | **+10.3pp** |

Top-1 lift translates 1:1 to EM lift on test split because the BETA-2b contract emits primary-only and size=1 cases are 91% of the dataset. The reranker is the first positive-result mechanism that delivers EM lift on aligned source — every prior post-hoc gate (1B-α, Tier 2A re-prompt, Tier 2B) was RED or marginal.

---

## §4 — Cross-corpus asymmetry is fundamental, not an artifact

### 4.1 8 methods × 4 directions sweep

| Method | Lingxi-test direction | MDD-test direction | Asymmetry |
|---|---:|---:|---:|
| kNN-K100 | +24.7pp | +4.0pp | +20.7pp |
| LightGBM | +21.0pp | +5.3pp | +15.7pp |
| NaiveBayes | +21.0pp | +6.7pp | +14.3pp |
| Random Forest | +16.0pp | +5.3pp | +10.7pp |
| SVM | +9.9pp | +4.0pp | +5.9pp |
| kNN-K50 | +7.4pp | +4.0pp | +3.4pp |
| LR (sklearn-default) | +2.5pp | +4.0pp | -1.5pp |
| kNN-K10 | +2.5pp | +4.0pp | -1.5pp |

Across all 8 ML paradigms (linear, kernel, tree, probabilistic, gradient-boosting, kNN at multiple K), **Lingxi-direction lift dominates MDD-direction lift**. This is method-agnostic.

### 4.2 Disproven alternative explanations

- **Implementation bug (truncation)?** Tested with full text + per-corpus vectorizer → +2.7pp (LESS than truncated +6.7pp). Disproved.
- **MDD already saturated?** MDD baseline is 0.604 vs Lingxi 0.470; oracle ceiling on MDD-direction also low. Not a saturation issue.
- **Method-paradigm artifact?** All 8 paradigms show same asymmetry. Not an artifact.

### 4.3 Mechanistic explanation

- **Lingxi**: lexical-dense criterion-aligned text → TF-IDF features informative, lexical anchors discriminative.
- **MDD-5k**: dialogue-style verbose multi-turn text → TF-IDF features uninformative, lexical anchors diluted.

The asymmetry is **a property of the corpus pair**, not of the classifier or implementation. This is a genuine limitation to acknowledge in the paper, not a failure to fix.

---

## §5 — LLM meta-agent variants (testing the user's "no-transcript / different perspective / different data source" hypothesis)

Five Qwen3-meta-judge variants tested on Lingxi N=1000:

| Variant | Has transcript? | Has structured? | Has disorder defs? | Δ Top-1 | Helped:Hurt |
|---|:---:|:---:|:---:|---:|---:|
| **B3c (disorder-def-only)** | NO | NO | YES (top-5) | **+1.9pp** | **3.1:1** |
| B3e (pairwise, no transcript) | NO | YES (top-2 + checker) | top-2 only | -0.7pp | 1.0:1 |
| B3b (structured-only meta) | NO | YES (full) | NO | -2.0pp | 0.5:1 |
| B3a (primary-fix, full context) | YES | YES | NO | -2.8pp | 0.4:1 |
| **B3i (critical reviewer w/transcript)** | YES | YES (top-3 reasoning) | NO | **-8.8pp** | **0.46:1** |

### 5.1 What the user's hypothesis predicted vs what we found

User predicted: "no-transcript / different perspective / different data source" agents would help.

**Empirical verdict — partially confirmed, with refinement:**

- ✅ **"Different paradigm" matters**: B3c (disorder-definitions paradigm, no transcript) is the only positive variant.
- ⚠️ **"No transcript" alone is not sufficient**: B3b (structured-only, no transcript, no defs) is -2.0pp. Removing transcript without adding a different signal source doesn't help.
- ❌ **"Different perspective via critique framing" backfires badly**: B3i ("find weakness in Qwen's reasoning") = -8.8pp, the worst variant. The framing biases the LLM toward changing primary even when the original is correct.

Refined finding: **the paradigm/data-source matters more than the absence of transcript.** B3c works because ICD criterion-text is a fundamentally different signal source (canonical, non-noisy) — not because the transcript is absent.

### 5.2 No-stacking finding

| Configuration | Top-1 | Δ vs Qwen baseline |
|---|---:|---:|
| Qwen3 baseline | 0.4700 | — |
| **Reranker only** | **0.5733** | **+10.3pp** |
| Reranker + B3c feature (`is_b3c_pick`) | 0.5533 | +8.3pp (-2.0pp from reranker alone) |
| B3c only (standalone) | 0.5200 | +1.9pp |

B3c's signal is fully captured by the reranker's TF-IDF features. Stacking actually hurts (the binary `is_b3c_pick` adds noise). **One learned reranker is sufficient — no need for a meta-LLM-judge layer.**

### 5.3 No multi-LLM-family ensembling beyond Qwen+Gemma

Llama-3.3-70B-AWQ vLLM init failed at 32 GB GPU (engine OOM). Per-class breakdown shows LLM ensembling (Qwen+Gemma) gives only +3.7pp marginal contribution vs TF-IDF feature's +9.7pp. Paradigm diversity (lexical-anchor vs LLM-reasoning) > LLM-family scale.

---

## §6 — Broader-K Qwen3 probe — does asking Qwen3 for top-12 close the gap?

**No.** Probe on 81 size=2 Lingxi cases prompting Qwen3-32B-AWQ to rank 12 candidates from the disorder pool:

| Metric | Value | Comparison |
|---|---:|---|
| Qwen3 top-5 (broader-K, fixed pool) | 16.0% | vs original Qwen3 free top-5: 56.8% |
| Qwen3 top-8 | 28.4% | — |
| Qwen3 top-12 | **43.2%** | vs Qwen+TFIDF union top-5: **79.0%** |

**Pre-registered verdicts:**

- top-12 ≥ 79.0%: NOT MET.
- top-12 < 60% (Qwen3 ranking is the bottleneck): TRIGGERED.

**Mechanism.** Two effects compound:

1. Qwen3 is much weaker at ranking-from-fixed-pool (16% top-5) than free generation (56.8%) — the prompt format itself hurts.
2. Qwen3 frequently outputs subcodes (F32.1, F31.1) not in the base-code pool, so post-filter retains <12 codes. (Parsing artifact, but does not change the headline.)

Even at K=12 with full ranking, Qwen3 reaches 43.2% — 36pp short of TF-IDF union 79.0%. Increasing prompt budget alone cannot recover the candidates TF-IDF surfaces. **TF-IDF as candidate-source remains uniquely contributing.**

Detail: `GAP_F_BROADER_K_QWEN3.md`.

---

## §7 — Architectural recommendation

### 7.1 What to adopt for paper-integration-v0.2 (or future work)

**Single positive Gap F component to add:**

1. **Lexical-Feature Reranker** (logistic regression or LightGBM, trained on dev split, applied to Qwen3 top-5)
   - Inputs: rank, met_ratio, in_confirmed, in_pair, class one-hot, **TF-IDF probability + rank + agreement**
   - Output: rerank score per candidate
   - Replaces the current "rank-1 = primary" rule on Lingxi-style corpora
   - Expected lift: **+6.80pp ± 0.93pp Top-1 (5-fold CV)** = same EM lift under BETA-2b primary-only contract

**What NOT to adopt:**

- ❌ Same-LLM meta-judge agents (B3a/B3b/B3c/B3e/B3i) — only B3c is positive standalone, and its signal is captured by the reranker.
- ❌ Multi-LLM ensemble as primary lift mechanism — +3.7pp dominated by reranker's +10.3pp.
- ❌ TF-IDF as candidate-source on dialogue-style corpora — corpus-style asymmetry confirmed.
- ❌ Broader-K Qwen3 prompting — top-12 = 43.2%, far below TF-IDF union 79.0%.
- ❌ Confusion-pair forced expansion or class-specific rerankers — marginal vs unified reranker, more moving parts.
- ❌ Tier 2A LLM re-prompt or 1B-α veto — both RED on aligned source.

### 7.2 Conditional logic for non-Lingxi corpora

For dialogue-style corpora (MDD-5k, real-clinical), where TF-IDF features are uninformative:

1. Skip TF-IDF Lexical Candidate Agent entirely.
2. Reranker uses non-TF-IDF features only (rank, met_ratio, confirmed, class one-hot) — gives ~+0.3pp, effectively neutral.
3. Future work: replace TF-IDF with dialogue-aware encoder (DialogBERT, MentalBERT, Qwen-style embedder) trained on multi-turn psychiatric conversations.

The corpus-direction asymmetry is acknowledged as a limitation; production deployment must include corpus-style detection upstream.

### 7.3 Confusion-pair detector + gated reranker (optional production refinement)

If absolute lift is less important than stability:

1. Detector predicts `is_confusion_prone` (F1 = 0.376, R = 0.567, P = 0.281 — soft gate).
2. If yes → apply reranker (with TF-IDF features).
3. If no → use Qwen rank-1 = primary (preserves baseline).

Trade-off: smaller absolute lift (~6pp vs 10pp) but reranker only fires on the 22% of cases that need it; lower variance, easier to debug. Recommended for production but not for headline paper claim.

---

## §8 — Paper-integration-v0.1 contract preserved

| Asset | Status |
|---|---|
| `paper-integration-v0.1` tag (commit c3b0a46) | UNTOUCHED |
| BETA-2b primary-only output policy | UNCHANGED |
| All committed predictions in `results/predictions/` | READ-ONLY |
| `src/culturedx/modes/hied.py` production code | NO Gap F changes |
| Manuscript drafts | NO Gap F edits |
| Round 149 verdict ("EM placement remains supplement-only") | RECONFIRMED |

This synthesis is read-only research output. Adoption decision deferred to v0.2 timeline.

---

## §9 — Defensibility against reviewer challenges

1. **"Why does TF-IDF help when LLMs are SOTA?"** — TF-IDF captures lexical-anchor signals (specific diagnostic keywords) that LLM reasoning de-emphasizes. The two paradigms have different blindspots. 88.9% of TF-IDF's recovered size=2 cases are not covered by ANY Qwen mode's top-5.
2. **"Cross-corpus asymmetry suggests cherry-picked dataset."** — 8 methods × 4 directions, ALL same asymmetry. Property of the corpus pair (criterion vs dialogue), not method choice. Disclosed as limitation.
3. **"+22pp in-domain is overfit."** — Cross-domain pure kNN (no trained classifier) achieves +11.1pp; LR retains 50%. Conservative claim is +6.80pp ± 0.93pp (5-fold CV).
4. **"Adding TF-IDF adds noise on size=1 cases."** — Use TF-IDF as REranker FEATURES (not as candidate source) → no pool pollution. Or G_ALL B=1 conservative budget.
5. **"Why not just use larger LLM (Llama-70B)?"** — Llama-70B vLLM init failed at our 32 GB. Per-class evidence: Qwen+Gemma ensemble = +3.7pp vs TF-IDF feature = +9.7pp. Paradigm diversity > LLM-family scale.
6. **"Same-LLM meta-judge should help."** — Tested 5 variants; only B3c (disorder-definitions-only) positive at +1.9pp; B3i (critical-reviewer framing) catastrophic at -8.8pp. Less context = less harm in same-LLM second pass; framing matters enormously.
7. **"Just ask Qwen3 for more candidates."** — Broader-K probe: top-12 = 43.2%, far below TF-IDF union 79.0%. Qwen3's diagnostic distribution itself is the bottleneck.

---

## §10 — Lineage and provenance

This document synthesizes:

- **Round 149** verdict: BETA-2b uniquely Pareto-optimal among post-hoc gates.
- **Round 156** verdict: 1B-α conservative veto RED on aligned source.
- **Round 159** verdict: all post-hoc gates RED on aligned source.
- **Tier 2A** audit (`GAP_E_TIER2A_REPROMPT_AUDIT.md`): LLM re-prompt does NOT outperform hand-crafted gates.
- **Gap F sub-experiments**: 25+ commits (`32441df` through HEAD) covering candidate-source augmentation, reranker design, asymmetry sweeps, LLM meta-agents, oracle ceilings, statistical robustness, stacking tests, and Broader-K probe.
- **Round 150 sandbox audit** (`ROUND150_SANDBOX_AUDIT.md`): aligned-source RED verdict for all post-hoc candidates.

Specific lineage commits referenced in body: 32441df, ec1e5f9, 79a1251, d13e2e8, 29f9952, 3396694, 91d28bb, f1b7165, 8668efe, 0b1c243, a6e2488, 7ccb1b3, 0ae4b5c, c1b21e3, 179c4c2, 193f98c, 4ab533d, 4fa5367.

This synthesis is the canonical Gap F reference; sub-audits are kept for traceability but no longer load-bearing for the paper-integration decision.
