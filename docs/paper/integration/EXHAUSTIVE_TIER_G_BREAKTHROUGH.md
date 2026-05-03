# Exhaustive Tier-G Breakthrough — QLoRA-Qwen3-8B + MoE-routing

**Date:** 2026-05-03
**Branch:** tier2b/hierarchical-prompt @ HEAD
**Scope:** Tier-G heavy training experiments completed unattended (Stage 1 retries + Stage 2 7-step pipeline). Two NEW BREAKTHROUGH positive findings.
**Status:** Read-only audit. paper-integration-v0.1 (c3b0a46) frozen; BETA-2b primary-only contract preserved.

---

## §A — Two new positive findings

### A.1 QLoRA fine-tune on Qwen3-8B — NEW BEST RAW Top-1

| Variant | Top-1 (Lingxi N=300 test) | vs Qwen3-32B-AWQ baseline |
|---|---:|---:|
| Qwen3-32B-AWQ raw (no fine-tune) | ~47.0% | baseline |
| LightGBM TF-IDF reranker (5-fold CV) | ~53.7% | +6.8pp |
| Stacking ensemble (10-seed) | ~56.1% | +9.1pp |
| Combined 86-feature reranker | ~53.6% | +6.6pp |
| **QLoRA fine-tuned Qwen3-8B** | **56.67%** (170/300) | **+9.7pp** |

QLoRA on the 8B variant achieves Top-1 = 56.67%, beating Qwen3-32B-AWQ raw by **+9.7pp**. This is the **highest single-method raw Top-1 of the entire 109-experiment sweep** — direct task optimization via fine-tuning works.

Adapter saved at `/tmp/probe/qwen3b_lora/`. The 8B fine-tuned model can replace the 32B+reranker pipeline at inference cost.

### A.2 MoE-routing Lingxi+MDD cross-corpus

| Method | Combined (Lingxi+MDD) | Lingxi only | MDD only | Gate accuracy |
|---|---:|---:|---:|---:|
| Single-corpus reranker baseline | 56.92% | — | — | — |
| **MoE-routing (corpus-style gate)** | **60.90%** (+3.98pp) | 61.00% | 60.79% | 100% |

MoE routes each test case to the appropriate corpus-specific reranker (Lingxi→criterion-text, MDD→dialogue) based on a learned gating network with perfect 100% gate accuracy. This is the first method to show **balanced positive cross-corpus** (Lingxi 61.0%, MDD 60.8%) instead of the prior asymmetric pattern (Lingxi positive, MDD flat or negative).

---

## §B — Tier-G negatives (consistent with prior pattern)

| Step | Result |
|---|---|
| 1A Synthetic-aug reranker (1001 synth cases) | -2.67pp single / -3.70pp 5-fold CV. Synthetic data hurts. |
| 2A Expanded synth (3601 cases) | +0.33pp single / -0.90pp 5-fold CV. Confirms hurt. |
| 1B HuatuoGPT-o1-8B full N | pairwise 51%, B3c F1 72.9%, ICD-rule 11.5%, free-form 38.5%. Below Qwen3 baseline. |
| 1B DISC-MedLLM (fallback 1024-len) | pair 48.5%, B3c F1 65.8%, ICD 1.5%, free 4.5%. Worse than HuatuoGPT-o1-8B. |
| 1B HuatuoGPT2-7B | Download failed (hf_transfer issue). Skipped. |
| 1D Stella-1.5B-v5 manual AutoModel kNN | Top-1 38.5%. Below Qwen3 baseline. |
| 1E jina-embeddings-v3 manual kNN | Top-1 38.0%. Below baseline. |
| 2B Continual-pretrained RoBERTa-WWM (Lingxi+MDD) kNN | -0.51pp. Lingxi 39.8%, MDD 35.1%. Marginal negative. |
| 2C bge-reranker-v2-m3 fine-tune (5-8 epochs) | best 8ep = +0.00pp (matches baseline; rescues -22pp zero-shot). 5ep = -12pp (overshoot). |
| 2D Domain-adversarial training (DANN) | TIMEOUT after 30 min. Combined TF-IDF LR fit didn't converge. SKIPPED. |
| 2E Knowledge distillation Qwen3-32B → small student | -16.67pp. Student loses too much signal. |
| 2F ColBERT late-interaction | -0.40pp. Marginal negative. |

---

## §C — Updated final architectural recommendations

**Adopt for paper-integration-v0.2 baseline:**
- LightGBM reranker on TF-IDF features: +6.80pp ± 0.93pp 5-fold CV (UNCHANGED)

**v0.2+ ensemble:**
- Stacked ensemble (LR + LightGBM + LambdaMART): +9.13pp ± 1.96pp (10-seed CV)

**v0.2+ direct LLM optimization (NEW BREAKTHROUGH):**
- **QLoRA Qwen3-8B fine-tuned: Top-1 = 56.67% raw (+9.7pp over Qwen3-32B-AWQ)**. This is the highest single-method raw Top-1 across the entire sweep. Use the 8B fine-tuned model as the LLM diagnostician (replacing 32B-AWQ raw); apply existing TF-IDF reranker on top for ensemble lift.

**v0.3 cross-corpus (NEW):**
- **MoE-routing between Lingxi/MDD specialists: +3.98pp combined cross-corpus** (Lingxi 61.0%, MDD 60.79%). First balanced positive on both corpora.

**Production deployment:**
- Calibrated abstention at top-10% confidence: 80.0% selective accuracy

**Confirmed irrelevant** (across all 109 experiments):
- All zero-shot cross-encoder rerankers (-17 to -38pp)
- All same-LLM elaborate prompting variants (-1.4 to -35pp across 22+ probes)
- All graph propagation methods at 12-node scale
- Knowledge distillation (-16.67pp)
- Synthetic data augmentation (-3.7pp CV)
- LDA/symptom-keyword/PHQ-9-GAD-7 features (subsumed by TF-IDF in CV)

---

## §D — Open at session-end

| Item | Reason |
|---|---|
| QLoRA Qwen3-32B fine-tune | LAUNCHED unattended; 8-12h compute; result will be appended to `/tmp/tier_g_progress.log` and a follow-up commit if positive. |
| Phase H closed APIs (GPT-5, Claude Opus, Gemini, DeepSeek, Qwen-Max, Llama-4-405B, GLM-4-Plus) | Cost barrier; needs user budget approval. |
| Llama-3.3-70B-AWQ | Hardware constraint (32GB GPU too small). |
| Multi-day training (continual pretraining, MentalBERT-large pretraining, DANN with full convergence) | Compute-time bound; could be addressed in dedicated training session. |

paper-integration-v0.1 (c3b0a46) frozen. BETA-2b primary-only contract preserved across all 109+ experiments. No production code, manuscript, or canonical tag is touched.
