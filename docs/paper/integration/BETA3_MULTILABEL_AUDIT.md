# BETA-3 Multi-Label Emission — Sandbox Audit + New MAS Architecture

**Date:** 2026-05-02
**Branch:** tier2b/hierarchical-prompt @ HEAD (sandbox)
**Status:** CPU-only sandbox audit. No production code, manuscript, or tag is touched. Read-only.

## TL;DR — multi-label emission is data-ceiling-limited under current Lingxi signals

| Question | Answer |
|---|---|
| Can we emit reliable comorbid_diagnoses on Lingxi-icd10 N=1000? | **NO** under EM contract (all gates -1 to -17pp). Marginally under F1 contract (best -0.13pp F1, +2.3pp mgEM at -13.7pp EM). |
| Why doesn't the existing audit_comorbid gate (T_decisive≥0.85) work for benchmark emission? | Fires on 39.6% of all cases including 40.3% of size=1 false positives — gate doesn't discriminate. |
| Does ensemble confirmation (audit + qwen rank-2 + TF-IDF top-2) help? | Best precision 0.172 at 29 emits — still costs -1.2pp EM. Triple-confirmation collapses to P=0 because all confirmations share the same false-positive source. |
| Is BETA-2b primary-only the right choice under current data? | **YES.** Round 149 verdict reconfirmed. |
| Can future data unlock multi-label emission? | **YES** — needs (a) 5-10× more size=2 cases for size predictor training, (b) ICD-coding-rule training signal, (c) ideally additional modality. |

---

## §1 — Phase 1: Size predictor from reranker features

Trained logistic regression on 700-case train / 300-case test split (10% positive class size=2+).

| Threshold | Precision | Recall | F1 |
|---:|---:|---:|---:|
| 0.3 | 0.107 | 0.933 | 0.192 |
| 0.4 | 0.084 | 0.633 | 0.149 |
| 0.5 | 0.078 | 0.300 | 0.124 |
| 0.6 | 0.065 | 0.100 | 0.079 |
| 0.7 | 0.143 | 0.033 | 0.054 |

Best F1 = 0.192 at thr=0.3 (high recall, but P=0.107). Top features: `n_qwen_top5`, `top1_is_F42` (-), `top1_in_pair` (+), `top1_is_F39` (+).

**Fundamental signal limit**: with only 81 size=2 cases out of 1000 (8.1% prevalence), the size-prediction boundary is not learnable from existing reranker features. The classifier can flag SOME true-positives but only at unacceptable false-positive rates.

---

## §2 — Phase 1b: mgEM oracle ceiling (per pool)

| Pool | size=1 (n=914) | size=2 (n=81) | size=3 (n=5) | Aggregate |
|---|---:|---:|---:|---:|
| Qwen top-5 only | 85.7% | 56.8% | 20.0% | **83.0%** |
| Qwen top-5 + TF-IDF top-5 union | 98.6% | 79.0% | 60.0% | **96.8%** |
| Qwen top-5 + TF-IDF top-12 union | 100.0% | 100.0% | 100.0% | **100.0%** |

**Headroom remains**: with current pool, perfect comorbid-selector achieves 96.8% aggregate. The 13.8pp from realized 83% to 96.8% is the candidate-pool headroom. This is reachable in principle — but only if a reliable size+pair predictor exists, which Phase 1 shows we don't have.

---

## §3 — Phase 1c: Pair distribution (size=2 cases)

Top-10 size=2 pairs in Lingxi N=1000:

| Pair | Count |
|---|---:|
| F32 + F41 | 31 |
| F41 + F42 | 9 |
| F41 + F98 | 8 |
| F51 + F98 | 8 |
| F41 + F45 | 7 |
| F32 + F39 | 6 |
| F41 + F51 | 5 |
| F32 + F98 | 2 |
| F42 + F43 | 2 |
| F41 + F43 | 1 |

F32+F41 alone = 38% of size=2 cases. Top-5 pairs = 78%. Pair-specific detectors are theoretically tractable (low cardinality) but fail empirically because each pair has only 5-31 examples.

---

## §4 — Phase 1d: Emission-policy simulation under three families

Simulated on 300-case test split, against BETA-2b primary-only baseline EM=0.4033, F1=0.4494, mgEM=0.0000.

| Policy family | Best variant | ΔEM | ΔF1 | ΔmgEM |
|---|---|---:|---:|---:|
| A: size_thr + tf_top2 if confirmed/in-pair | thr=0.5 | -19.3pp | -4.3pp | 0.0 |
| B: size_thr + qwen rank-2 if confirmed | thr=0.5 | -14.3pp | -1.6pp | +6.7pp |
| C: size_thr + domain-pair if confirmed | thr=0.5 | -14.0pp | +0.6pp | +6.7pp |

**Only Policy C at thr=0.5 produces a positive F1 delta** (+0.0058) — but at -14pp EM cost. Not adoptable.

---

## §5 — Phase 2: Strict ensemble gates on full N=1000

| Gate | Emit count | Precision | ΔEM | ΔF1 | ΔmgEM |
|---|---:|---:|---:|---:|---:|
| Baseline BETA-2b | 0 | — | — | — | — |
| G1 (audit T_decisive≥0.85) | 326 | 0.080 | -13.7pp | -3.3pp | +2.3pp |
| G1 (audit T_decisive≥0.90) | 138 | 0.072 | -5.0pp | -1.2pp | 0.0 |
| G1 (audit T_decisive≥0.95) | 0 | — | 0 | 0 | 0 |
| G2 (audit AND TF-IDF top-2 agree, T≥0.85) | 139 | 0.036 | -7.6pp | -2.4pp | +1.2pp |
| G3 (audit AND Qwen rank-2 agree, T≥0.85) | **29** | **0.172** | -1.2pp | -0.13pp | +1.2pp |
| G3 (audit AND Qwen rank-2 agree, T≥0.90) | 13 | 0.077 | -0.6pp | -0.13pp | 0.0 |
| G4 (audit + Qwen rank-2 + TF-IDF top-2, T≥0.85) | 11 | 0.000 | -0.8pp | -0.27pp | 0.0 |
| G5 (G4 + known-pair filter, T≥0.85) | 1 | 0.000 | -0.1pp | -0.03pp | 0.0 |

**Pattern**: as gate strictness increases, emit rate drops faster than precision rises. Best precision is G3 at 0.172 — no ensemble gate reaches the P≥0.5 threshold needed for net-positive EM.

**Why all confirmations share the same false-positive source**: the criterion checker fires on co-existing *symptoms* (anxiety symptoms in a depression case meet F41 criterion A even when ICD coding rules say it's F32 not F32+F41). Adding more confirmations — TF-IDF top-2, Qwen rank-2, criterion verification — captures the same symptom-overlap pattern, not the diagnostic-distinctness signal. Triple confirmation collapses to 0% precision because the 11 emits that survive triple confirmation are dominated by the strongest false-positives.

---

## §6 — Comparison with prior Tier 2A LLM-as-judge audit

From `GAP_E_TIER2A_REPROMPT_AUDIT.md`:

| Mode | LLM emit% | ΔEM | ΔF1 | ΔmgEM |
|---|---:|---:|---:|---:|
| lingxi_icd10 | 3.9% | -0.017 | -0.000 | +0.012 |
| lingxi_dsm5 | 16.5% | -0.066 | +0.008 | +0.081 |
| mdd_icd10 | 5.6% | -0.035 | -0.005 | +0.012 |
| mdd_dsm5 | 6.3% | -0.029 | -0.002 | +0.019 |

LLM-as-judge produces the SAME trade-off pattern as our Phase 2 ensemble gates: small mgEM gain (+1-8pp on size≥2 subset) at meaningful EM cost (-2-7pp). This is **not a gating-mechanism deficiency**; it's a fundamental signal limit. Both feature-based gates and LLM-judge agents have the same operating curve.

---

## §7 — New MAS Architecture — under both EM and F1 contracts

### 7.1 EM-contract architecture (paper-integration-v0.2 candidate)

Single-headed: keep BETA-2b primary-only output, swap rank-1-as-primary for the Lexical-Feature Reranker.

```
┌─────────────────────────────────────────────┐
│             Case transcript                  │
└─────────────────┬───────────────────────────┘
                  │
   ┌──────────────┼──────────────────────────┐
   ▼              ▼                          ▼
┌─────────┐  ┌────────────┐         ┌─────────────────┐
│ LLM     │  │ Triage     │         │ TF-IDF Lexical  │
│ Diag    │  │ Agent      │         │ Candidate Agent │
│ (Qwen3) │  └────────────┘         │ (Lingxi-only)   │
└────┬────┘                         └────────┬────────┘
     │                                       │
     ▼                                       ▼
top-5 ranked + reasoning            top-5 + probs + ranks
                                            │
     ┌──────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────┐
│ Criterion Checker (per cand)│
│ - met_ratio, criterion A    │
└──────┬──────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Logic Engine               │
│ → confirmed_codes          │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────────────────────┐
│ Lexical-Feature Reranker (Gap F finding)   │
│ Inputs: rank, met_ratio, in_confirmed,     │
│ in_pair, class one-hot, TF-IDF prob/rank/  │
│ agreement                                   │
│ Output: rerank score per candidate          │
└──────┬─────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│ FINAL OUTPUT (BETA-2b contract) │
│ benchmark_primary = rerank top-1│
│ comorbid_diagnoses = []         │
│ audit_comorbid (sidecar) = ...  │
└─────────────────────────────────┘
```

**Expected paper claim:** +6.80pp ± 0.93pp Top-1 (5-fold CV) = +6.80pp EM under BETA-2b primary-only contract on Lingxi-style corpora. Cross-corpus asymmetry disclosed.

### 7.2 F1-contract architecture (BETA-3 candidate, NOT recommended for adoption)

Two-headed: above + multi-label head.

```
                   [reranker top-K, scores, criterion outputs]
                                    │
                  ┌─────────────────┼─────────────────┐
                  ▼                                   ▼
        ┌────────────────────┐           ┌────────────────────────┐
        │ Primary Head       │           │ Multi-Label Head        │
        │ rerank top-1       │           │ - Size predictor (LR)   │
        └─────────┬──────────┘           │ - Pair predictor (LR)   │
                  │                      │ - LLM size agent (opt.) │
                  │                      │ - Confidence gate       │
                  │                      └─────────┬──────────────┘
                  │                                ▼
                  │                       ┌────────────────────┐
                  │                       │ Comorbid Selector  │
                  │                       │ Pick from rerank   │
                  │                       │ top-K & TF-IDF top-K│
                  │                       └─────────┬──────────┘
                  │                                 │
                  ▼                                 ▼
           benchmark_primary               benchmark_comorbid
                  │                                 │
                  └─────────────┬───────────────────┘
                                ▼
              EM_strict / F1 / mgEM / sgEM disaggregated
```

**Empirically blocked**: Phase 1 + 2 + Tier 2A precedent show no positive-EM, marginal-F1 (best -0.13pp F1) configuration. Reserved as paper §future-work, not adopted.

### 7.3 Decision matrix

| Configuration | Adopt for paper-integration-v0.2? |
|---|---|
| Primary head only (Reranker, BETA-2b contract) | YES (reranker as v0.2 candidate; BETA-2b unchanged) |
| Primary head + multi-label head, EM-scored | NO (multi-label head adds -1 to -17pp EM) |
| Primary head + multi-label head, F1-scored | NO at headline (best is -0.13pp F1); disclose in §future-work |
| Primary head + LLM-size-predictor agent | NO (Tier 2A precedent: same trade-off) |

---

## §8 — Why "more LLM agents" doesn't help (task-architecture balance)

**Empirical pattern from this project:**

| MAS expansion | Result | Channel |
|---|---|---|
| 1 LLM → 2 LLMs (Qwen + Gemma) | +3.7pp coverage marginal | LLM-reasoning channel (already saturated) |
| Same-LLM meta-judge variants (5 tested) | -8.8 to +1.9pp Top-1; only B3c positive | LLM-reasoning channel |
| LLM-as-emit-judge (Tier 2A) | -2-7pp EM, +1-8pp mgEM | LLM-reasoning channel |
| **TF-IDF Lexical-Feature Reranker** | **+6.8pp EM (5-fold CV)** | **NEW lexical-anchor channel** |

The LLM-reasoning channel is saturated for this task by the existing Qwen3 Diagnostician + 12-disorder Criterion Checker + Logic Engine + Comorbidity Resolver. Adding more same-paradigm LLM agents inflates one channel's complexity without addressing the bottleneck.

The Gap F finding is that a *different paradigm* (lexical retrieval) provides orthogonal signal. This matches the task-architecture-complexity balance argument: complexity additions help only when they extend the architecture along axes the task requires but the current architecture lacks.

**Implication for future work**: paradigm-diversity (e.g., dialogue-aware encoder, audio modality, longitudinal EHR encoder) is more promising than agent-count expansion for this task.

---

## §9 — Files NOT modified

- `paper-integration-v0.1` tag (commit c3b0a46) — UNTOUCHED
- BETA-2b primary-only output policy — UNCHANGED
- All committed predictions in `results/gap_e_beta2b_projection_*` — READ-ONLY
- `src/culturedx/modes/hied.py` production code — NO BETA-3 changes
- Manuscript drafts — NO BETA-3 edits
- Sandbox scripts: `/tmp/probe/beta3_phase1_size_predictor.py`, `/tmp/probe/beta3_phase2_strict_ensemble.py` (not committed)

---

## §10 — Lineage and provenance

- Round 149 BETA-2b verdict: primary-only is uniquely Pareto-optimal (reconfirmed)
- Round 156: 1B-α veto RED on aligned source
- Round 159: all post-hoc gates RED on aligned source
- BETA-2 commit `62622a0`: introduced audit_comorbid sidecar at T_decisive≥0.85 strict gate
- Tier 2A audit: LLM-as-judge gives same trade-off pattern as feature-based gates
- Gap F final synthesis (commit `72b6bd0`): lexical-feature reranker as primary-head v0.2 candidate
- BETA-3 audit (this doc): multi-label emission empirically blocked under current data

The architectural recommendation stands: keep BETA-2b primary-only contract; adopt reranker as paper-integration-v0.2 single component; defer multi-label emission to future work pending more multi-diagnosis training data and/or additional modality.
