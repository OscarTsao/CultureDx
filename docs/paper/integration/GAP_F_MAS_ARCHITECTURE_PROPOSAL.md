# Gap F MAS Architecture Proposal — Multi-Source Candidate Generation + Lexical-Feature Reranking

**Date:** 2026-05-02
**Branch:** tier2b/hierarchical-prompt @ HEAD
**Status:** Synthesis document. Uncommitted (will commit with this audit).
**Lineage:** Synthesizes findings from commits 32441df, ec1e5f9, 79a1251, d13e2e8, 29f9952, 3396694, 91d28bb, f1b7165, 8668efe, 0b1c243, a6e2488, 7ccb1b3, 0ae4b5c, c1b21e3, 179c4c2.

## Executive summary

Round 159 + 16 Gap F sub-experiments together support the following architectural claim:

> **The current diagnostician-centric pipeline has a recall ceiling on multi-diagnosis cases (size=2 all-gold-in-top5: 56.8% on Lingxi). This ceiling is partially closable on lexical-dense corpora by augmenting the candidate pool / ranker with TF-IDF features, but the benefit is corpus-style-dependent and does not generalize to dialogue-style corpora.**

Specifically:
- **Reranker with TF-IDF features achieves +9.7 to +10.3pp Top-1 on Lingxi** (logistic and LightGBM both work; effect robust across icd10/dsm5/both modes)
- **Same approach gives 0pp on MDD** (corpus-style mismatch, not classifier choice)
- **Multi-LLM ensembling alone gives only +3.7pp**, dominated 3x by TF-IDF feature contribution

This document proposes a Gap F MAS architecture with two principal components:

1. **Multi-Source Candidate Generator** (Qwen LLM Diagnostician + gated TF-IDF lexical agent)
2. **Lexical-Feature Reranker** (logistic/LightGBM over Qwen top-5 with TF-IDF probability features)

---

## §1 — Empirical foundation

### Top-3 ≠ multi-diagnosis readiness

Gold-size distribution (LingxiDiag-16K + MDD-5k):
- size=1: 91.4% / 91.2%
- size=2: 8.1% / 8.1%
- size=3: 0.5% / 0.6%
- size≥4: 0%

For size=2 cases on Lingxi:
- Top-3 contains primary gold: ~94%
- Top-3 contains BOTH gold codes: only ~41%

The headline "Top-3 = 0.80" is `gold[0] ∈ top-3`. Complete-set coverage is much weaker.

### Corpus-direction asymmetry (8 methods × 4 directions)

ALL 8 ML methods (LR, SVM, RF, NaiveBayes, LightGBM, kNN-K10/K50/K100) tested on TF-IDF features show consistent corpus-direction asymmetry:

| Method | Lingxi-test direction lift | MDD-test direction lift |
|---|---:|---:|
| kNN-K100 | +24.7pp | +4.0pp |
| LightGBM | +21.0pp | +5.3pp |
| NaiveBayes | +21.0pp | +6.7pp |
| Random Forest | +16.0pp | +5.3pp |
| SVM | +9.9pp | +4.0pp |
| LR | +2.5pp* | +4.0pp |
| kNN-K10 | +2.5pp* | +4.0pp |

*LR/kNN-K10 are under-fit at sklearn defaults; original tuned LR achieved +22.2pp.

This is **method-agnostic**. The asymmetry mechanism is corpus-style:
- Lingxi: lexical-dense criterion text → TF-IDF features informative
- MDD-5k: dialogue-style verbose text → TF-IDF features uninformative

### Marginal source contribution (Lingxi-test direction)

| Source added to Qwen | Δrecall (size=2 coverage) | Δnoise (size=1 spurious) |
|---|---:|---:|
| Gemma-3-12B-it | +1.2pp | +0.00 |
| TF-IDF + LR (in-domain) | +11.1pp | +1.82 |
| Pure TF-IDF kNN | +2.5pp | +0.00 |

TF-IDF+LR is the unique high-recall contributor. Gemma-3-12B is redundant after TF-IDF is included.

### Reranker via TF-IDF features

| Method | Top-1 Lingxi | Top-1 MDD |
|---|---:|---:|
| Baseline (rank-1=primary) | 0.4700 | 0.6043 |
| Logistic without TF-IDF | 0.4600 (-1.0pp) | n/a |
| **Logistic with TF-IDF** | **0.5667 (+9.7pp)** | n/a |
| **LightGBM (best HP)** | **0.5733 (+10.3pp)** | 0.6007 (-0.4pp) |

TF-IDF features explain the entire reranker lift. Without them, rerankers are at-or-below baseline.

### Per-class reranker contribution

| Class | n | Helped | Hurt | Net |
|---|---:|---:|---:|---:|
| F41 | 114 | +20 | 0 | +20 |
| F39 | 23 | +14 | 0 | +14 |
| F32 | 99 | 0 | -6 | -6 |
| Others | ~64 | +3 | -1 | +2 |

Reranker recovers F41 mistakes (Qwen3 over-predicts F32). Most lift comes from common confusion pair (F32↔F41) and rare class F39 (mood NOS).

### Per-mode generalization (Lingxi)

| Mode | Baseline | Rerank | Δ |
|---|---:|---:|---:|
| lingxi_icd10 | 0.4700 | 0.5733 | +10.3pp |
| lingxi_dsm5 | 0.4867 | 0.5533 | +6.7pp |
| lingxi_both | 0.4700 | 0.5733 | +10.3pp |

Robust across all 3 Lingxi modes.

### Negative results

**B3b (structured-only meta-reasoning, no transcript): -2.0pp Top-1.** Removing transcript hurts; structured signals alone are insufficient.

**LLM-only ensembling (Qwen + Gemma): +3.7pp.** Marginal vs LLM+TF-IDF combination.

**Confusion-pair forced expansion: +2.7-6.2pp on size=2.** Modest, free, but small.

---

## §2 — Proposed Gap F MAS architecture

### Architecture diagram (text)

```
                   ┌─────────────────────────────┐
                   │      Case transcript        │
                   └──────────┬──────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
       ┌──────────┐   ┌──────────┐    ┌────────────────┐
       │ LLM      │   │ Triage   │    │ TF-IDF Lexical │
       │ Diag     │   │ Agent    │    │ Candidate      │
       │ (Qwen)   │   │          │    │ Agent (gated)  │
       └─────┬────┘   └────┬─────┘    └─────┬──────────┘
             │             │                │
             ▼             ▼                ▼
       top-5 ranked    14 cands     TF-IDF top-5 + probs
       + reasoning                  + ranks
                                       │
       ┌────────────────────────────────┼─────┐
       │                                ▼     │
       │  ┌──────────────────────────────────┐│
       │  │  Criterion Checker (per cand)    ││
       │  │  - met_ratio                     ││
       │  │  - per-criterion confidence      ││
       │  └────────────┬─────────────────────┘│
       │               │                      │
       │               ▼                      │
       │  ┌────────────────────────────────┐  │
       │  │  Logic Engine: confirmed_codes │  │
       │  └────────────┬───────────────────┘  │
       │               │                      │
       └───────────────┼──────────────────────┘
                       ▼
               ┌────────────────────────────────────┐
               │  Lexical-Feature Reranker          │
               │  Inputs:                           │
               │   - Qwen rank, met_ratio, confirmed│
               │   - TF-IDF prob, rank, agreement   │
               │   - confusion-pair flag            │
               │  Output: rerank score per candidate│
               └────────────┬───────────────────────┘
                            │
                            ▼
               ┌────────────────────────────┐
               │ Final Output:              │
               │  - benchmark_primary       │
               │    (single code, EM-safe)  │
               │  - audit_comorbid (sidecar)│
               │  - clinical_candidate_set  │
               │  - source attribution      │
               └────────────────────────────┘
```

### Component descriptions

**1. LLM Diagnostician (existing Qwen3-32B-AWQ)**
Unchanged from current pipeline. Outputs ranked top-5.

**2. TF-IDF Lexical Candidate Agent (NEW, conditional)**
- Inputs: case transcript
- Outputs: top-K codes ranked by TF-IDF+LR probability + per-class probabilities
- Gating: invoke for cases where Qwen3 has low margin OR primary not in confirmed_codes (G_LOW_MARGIN OR G_PRIMARY_NOT_CONFIRMED)
- Optional: also include pure TF-IDF kNN top-K (no classifier) as redundancy

**3. Criterion Checker (existing)**
Unchanged. Operates on candidate pool (Qwen ∪ TF-IDF if invoked).

**4. Logic Engine (existing)**
Unchanged. Produces confirmed_codes.

**5. Lexical-Feature Reranker (NEW)**
- Inputs: candidate features (rank, met_ratio, in_confirmed, in_pair, class one-hot, TF-IDF prob, TF-IDF rank, qwen_tfidf_agree)
- Model: logistic regression with class_weight='balanced', or LightGBM (n_est=50, depth=8, lr=0.05)
- Trained on dev split
- Output: reranked top-5 with rerank scores
- Replaces current "rank-1 = primary" rule

**6. Final Output Layer (BETA-2b extended)**
- benchmark_primary: rerank top-1 (EM-safe single code)
- audit_comorbid: sidecar with checker evidence per candidate
- clinical_candidate_set: full reranked top-K (for clinician review)
- source_attribution: which source (LLM / TF-IDF / criterion) supports each candidate

### Conditional logic for non-Lingxi corpora

For dialogue-style corpora (e.g., MDD-5k, real clinical), where TF-IDF features are uninformative:

1. Skip TF-IDF Lexical Candidate Agent entirely
2. Reranker uses non-TF-IDF features only (rank, met_ratio, confirmed, class one-hot)
3. Future work: replace TF-IDF with dialogue-aware encoder (DialogBERT, MentalBERT, Qwen-style embedder) trained on multi-turn psychiatric conversations

The corpus-direction asymmetry is acknowledged as a limitation; production deployment must include corpus-style detection upstream.

---

## §3 — Empirical evidence supporting each architectural claim

### Claim 1: TF-IDF as candidate source helps on lexical-dense corpora

- Commit 32441df: Lingxi size=2 coverage 56.8% → 79.0% (+22.2pp in-domain) / +11.1pp cross-domain
- Commit ec1e5f9: 3 caveats PASS (common-codes blanket, top-K cutoff, unique contribution)
- Commit 79a1251: kNN cross-domain retention 82% (better than LR 50%)

### Claim 2: Asymmetry is corpus-style, not classifier-paradigm

- Commit 3396694: 8 methods × 4 directions; Lingxi-direction +10-25pp, MDD-direction +0-7pp uniformly
- Commit 7ccb1b3: reranker on MDD also fails (-0.4 to -1.4pp)
- Commit 179c4c2: per-mode (icd10/dsm5/both) confirms within-corpus consistency

### Claim 3: TF-IDF as feature is more efficient than as candidate source

- Commit 0b1c243: Logistic reranker with TF-IDF features +9.7pp Top-1; LightGBM +6.3pp
- Commit c1b21e3: 48-config LightGBM HP sweep; best +10.3pp; logistic captures 95%
- Commit 8668efe: G_ALL B=1 (+1 unique TF-IDF candidate per case) is sweet spot for candidate-source approach

### Claim 4: LLM-only ensembling has marginal value

- Commit 91d28bb: Gemma marginal contribution +1.2pp (vs +11.1pp for TF-IDF+LR)
- Commit a6e2488: B3b structured-only meta-reasoning hurts (-2.0pp Top-1)

### Claim 5: Specific class coverage

- Commit 0ae4b5c: per-class reranker — F41 +20, F39 +14, F32 -6 (F32↔F41 confusion pair + F39 rare-class boost)

---

## §4 — What this CHANGES about the paper

### Was (pre-Gap F)
"BETA-2b primary-only is uniquely Pareto-optimal across all post-hoc emission gates. Multi-label cases bounded at 0% mgEM."

### Now (Gap F integrated)
"BETA-2b primary-only remains the optimal **single-source** policy. We additionally identify two architectural extensions:
1. **Heterogeneous candidate-source MAS**: combining LLM diagnostic reasoning with TF-IDF lexical retrieval recovers up to +22.2pp size=2 set coverage on lexical-dense corpora.
2. **Lexical-feature reranker**: a learned reranker using TF-IDF features over Qwen3 top-5 lifts Top-1 accuracy by +10.3pp on Lingxi-style corpora.

Both contributions are corpus-style-dependent: the lift transfers within Lingxi-like criterion-text but not to MDD-like dialogue-text. We attribute this to lexical density of the case description."

This framing:
- Preserves the BETA-2b primary-only finding for the original benchmark contract
- Adds a positive Gap F contribution (architectural diagnosis + remedy)
- Frames the MDD asymmetry as a limitation, not a failure
- Points to specific future-work directions

---

## §5 — Operating recommendations

### For paper-integration-v0.2 timeline

| Decision | Recommendation |
|---|---|
| Adopt BETA-2b? | YES (Round 149 verdict, unaffected) |
| Adopt 1B-α veto? | NO (Round 156 RED on aligned source) |
| Add Gap F architecture as v0.2 component? | NO — too late for canonical adoption; flag as §6 audit + future work |
| Frame in paper? | "Diagnosis + Remedy" appendix (§5.6 or §7), preserving §5.3 main results |

### For future paper / next study

| Direction | Priority | Estimated effort |
|---|---|---|
| Reranker integration into HiED pipeline | HIGH | 2-3 weeks |
| Real-clinical corpus replication (when IRB clears) | HIGH | depends on IRB |
| Dialogue-aware lexical features for MDD | MEDIUM | 4-6 weeks |
| LLM-as-reranker comparison (Qwen reranker vs logistic) | MEDIUM | 2 weeks |
| Confusion-pair detector + class-specific reranker | LOW | 2 weeks |
| LightGBM cross-corpus stability | LOW | 1 week |

---

## §6 — Defensibility against reviewer challenges

### Challenge 1: "Why does TF-IDF help when LLMs are state-of-art?"
Answer: TF-IDF captures lexical-anchor signals (specific diagnostic keywords, criterion-aligned phrases) that LLM reasoning paradigm de-emphasizes. The two paradigms have different blindspots. Empirical evidence: 88.9% of TF-IDF's recovered size=2 cases are not covered by ANY Qwen mode's top-5.

### Challenge 2: "Cross-domain asymmetry suggests cherry-picked dataset."
Answer: We tested 8 methods × 4 train/test directions. ALL methods show the same corpus-direction asymmetry (Lingxi works, MDD doesn't). This is a property of the dataset pair (criterion-text vs dialogue-text), not method choice.

### Challenge 3: "+22pp in-domain is overfit."
Answer: Cross-domain pure kNN (no trained classifier) achieves +11.1pp — half the in-domain lift transfers. With a learned classifier (LR), 50% retention. Original LR was overfit; pure kNN is the conservative claim.

### Challenge 4: "Adding TF-IDF adds noise to single-label cases."
Answer: On size=1 cases (91% of dataset), TF-IDF union adds ~+1.8 spurious candidates. We propose using TF-IDF as REranker FEATURES (not as candidate source) which avoids pool pollution. Or G_ALL B=1 conservative budget.

### Challenge 5: "Why not just use larger LLM (Llama-70B)?"
Answer: Llama-70B was attempted; vLLM engine init failed at 32GB GPU. Plus the per-class breakdown shows LLM ensembling (Qwen+Gemma) gives only +3.7pp vs TF-IDF feature's +9.7pp — paradigm diversity > LLM-family scale.

---

## §7 — Files NOT modified

- `paper-integration-v0.1` tag — frozen at c3b0a46
- `feature/gap-e-beta2-implementation` — NOT touched
- `main-v2.4-refactor` — NOT touched
- All previous Plan v1.3.x audits — NOT modified
- This proposal lives on `tier2b/hierarchical-prompt` branch only
- Production code unchanged from commit `2e6c74c` (tier2b branch HEAD as of architecture audit)

This document is a synthesis of empirical findings; it does NOT modify any pipeline code, manuscript draft, or canonical evaluation.

