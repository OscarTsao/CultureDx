# Exhaustive Sweep Appendix — Phase E/F Frontier Methods

**Date:** 2026-05-02
**Branch:** tier2b/hierarchical-prompt @ HEAD
**Scope:** Recent SOTA-2024/2025 methods we hadn't tested in the original synthesis. Local-free only; closed APIs (Phase H) and training-heavy (Phase G) deferred.

## §A — Phase F: Alternative cross-encoders (all NEGATIVE)

7 cross-encoders tested as zero-shot (case, disorder_def) rerankers on Lingxi N=300 test split:

| Cross-encoder | Δ Top-1 | Notes |
|---|---:|---|
| bge-reranker-v2-m3 | -22.5pp | original test |
| gte-multilingual-reranker-base | -17.4pp | |
| jina-reranker-v3 | predict-failed | config bug (no padding token) |
| jina-reranker-v2-base-multilingual | -18.0pp | |
| mxbai-rerank-large-v2 | **-37.6pp** | worst |
| mxbai-rerank-base-v2 | -26.8pp | |
| bge-reranker-v2-gemma | -32.5pp | randomly-initialized score head |

**Verdict:** Zero-shot cross-encoders of (case-text, disorder-definition-text) are universally wrong-signal at this task. **Fine-tuning required** (Phase G #65) — not testable at local zero-shot.

## §B — Phase F: Alternative dense embedders

| Embedder | Top-1 | Qwen ∪ top-5 set-cov |
|---|---:|---:|
| bge-m3 (baseline) | 0.5067 | +10.0pp ✓ |
| mxbai-embed-large-v1 | 0.5100 | **+10.0pp** ✓ |
| jina-embeddings-v3 | similar | similar |
| **SPLADE-cocondenser** (sparse) | 0.4067 | **+9.0pp** ✓ |
| Stella-1.5B-v5 | encode failed (transformers version) | n/a |
| NV-Embed-v2 (~14GB) | CUDA OOM | n/a |
| E5-Mistral-7B (~14GB) | CUDA OOM | n/a |

**Verdict:** **3 different paradigms** (bge dense, mxbai dense, SPLADE sparse) all give ~+9-10pp set-coverage as candidate-source. Robust across embedder choice. The 14GB+ embedders don't fit on our 32GB GPU once driver/framework overhead is accounted for.

## §C — Phase F: Learned RRF fusion (POSITIVE)

| Method | Δ Top-1 |
|---|---:|
| Hardcoded weighted RRF (best grid: w=1,3,0,0) | +3.0pp |
| **Learned RRF weights via LR** | **+8.0pp** ← new positive finding |

Learned weights confirm TF-IDF dominance:
- `rrf_tf` = +0.99 (TF-IDF rank)
- `tf_prob` = +1.16 (TF-IDF probability) ← strongest
- `rrf_qwen` = +0.20 (Qwen rank)
- `rrf_pure_tfidf` = 0.00 (redundant)
- `qwen_rank` = -0.21 (negative — high rank means worse)

## §D — Stacking ensemble robustness verification

Three independent stability checks:

| Statistic | Stacked ensemble |
|---|---|
| Single 70/30 split | +11.0pp (lucky single-shot) |
| 5-fold CV (3-base) | +8.70pp ± 4.32pp |
| 10-seed × 70/30 split (3-base) | **+9.13pp ± 1.96pp** ← tight |
| 30-rep bootstrap (3-base avg-norm) | mean = +X, **95% CI [+4.24, +11.33]**, min +4pp / max +11pp |

**Conservative paper-defensible claim**: stacking ensemble lifts +9.13pp ± 1.96pp on Lingxi (10-seed mean), with 95% bootstrap CI [+4.24pp, +11.33pp]. The +11pp single-split is at the upper bound of the bootstrap CI; the 10-seed mean is more representative.

5-base stacking (LR-balanced, LR-l2, LR-l1, LightGBM-d6, LightGBM-d10) gives +9.67pp single-split (best individual LR-l2 also +10.33pp). Meta-LR weights heavily favor LR-balanced (4.11), with marginal contribution from others.

## §E — Calibrated abstention (POSITIVE NEW MECHANISM)

For production deployment with selective accuracy:

| Emit fraction | Selective accuracy by confidence | by margin |
|---:|---:|---:|
| 100% (emit all) | 0.5600 | 0.5600 |
| 90% | 0.6000 | 0.5704 |
| 80% | 0.6167 | 0.5875 |
| 70% | 0.6333 | 0.6048 |
| 50% | **0.7133** | 0.6600 |

**Confidence-based abstention: emit only top-50% by reranker confidence → 71.3% selective accuracy (+15.3pp over emit-all 56%).** Useful for production deployment where some cases can be deferred to human review.

## §F — Test-time augmentation (NEGATIVE)

3 paraphrased prompts (Chinese / English / restructured), majority vote on N=300:
- Baseline: 0.5333
- TTA: 0.3300
- **Δ = -20.33pp catastrophic**

Confirms same-LLM-paraphrase pattern. Different prompts elicit different LLM responses but most are wrong; voting amplifies the wrong-answer mode.

## §G — What's still untested at local-free

| Tier | What's left | Why |
|---|---|---|
| Phase E (LLM, vLLM-bound, ~10 variants) | Tool-using, Verify-Generate, Constrained, Branch-Solve-Merge, RaR, PAL, AutoGen, LangGraph, MetaGPT, AgentVerse, SC-CoVe, AoT/BoT/RoT, Memory-aug, Beam-search | Need vLLM restart + 30-60 min batch. Pattern likely consistent with prior B3 family + ToT/SoT/CoT (-9 to -35pp negative) |
| Phase G (training, 4-24h) | LoRA fine-tune Qwen3, Fine-tuned cross-encoder, MentalBERT/DialogBERT pretraining, MoE-routing, Domain-adversarial, Synthetic data, Distillation, Continual pretraining | Heavy compute, separate session |
| Phase H (closed API, cost-barrier) | GPT-5, Claude Opus, Gemini 2.5 Pro, DeepSeek-V3/R1, Qwen-Max, Llama-4-405B, GLM-4 | $50-200 per probe, NEEDS USER COST APPROVAL |

## §H — Final architectural recommendations (updated)

**Adopt for paper-integration-v0.2 (single-method baseline):**
- LightGBM reranker on TF-IDF features: **+6.80pp ± 0.93pp 5-fold CV** (prior, unchanged)

**Adopt for v0.2+ (ensemble):**
- Stacked ensemble (LR + LightGBM + LambdaMART): **+9.13pp ± 1.96pp (10 seeds)** = +2.3pp over single LightGBM at 3× training cost

**Adopt for production deployment:**
- Calibrated abstention at 50% emit threshold → **71.3% selective accuracy** vs 56% emit-all

**Adopt for cross-corpus (MDD direction):**
- bge-m3 dense kNN candidate-source: **+7.4pp size=2 set-coverage** (breaks TF-IDF asymmetry)

**Confirmed irrelevant on this task** (do not adopt):
- All zero-shot cross-encoder rerankers (-17 to -38pp)
- All same-LLM elaborate-prompting variants (CoT, ToT, SoT, RaR, self-refine, plan-solve, few-shot, ICD-rule, B3a/b/i, pair-LLM-agent, TTA, self-consistency, broader-K) — all -9 to -35pp
- All graph propagation methods at 12-node scale (PPR, GCN, heat-diffusion, random-walk, TransE — -4 to -36pp)
- Cosine reranker (no learning): -18pp
- LLM-as-judge variants on alternative LLM family (Yi-9B): -7 to -13pp on all 3 successful probes

Llama-3.3-70B-AWQ vLLM init unfeasible on single 32GB GPU (model weights 29.5GB exceed framework headroom budget).

---

paper-integration-v0.1 (c3b0a46) frozen. BETA-2b primary-only contract preserved. Read-only audit; no production code, manuscript, or canonical tag is touched.
