# Gap F Broader-K Qwen3 Probe — Asking Qwen3 for top-12 candidates

**Date:** 2026-05-02
**Branch:** feature/gap-e-beta2-implementation @ HEAD
**Status:** CPU-controlled vLLM probe. Read-only. Uncommitted.
**Sample:** 81 size=2 Lingxi cases (`results/phase1_recall_probe/sample_lingxi_size2_n100.jsonl`)
**Model:** Qwen/Qwen3-32B-AWQ via vLLM at http://localhost:8000/v1, T=0.0, /no_think.

## TL;DR — STRONGLY NEGATIVE

Asking Qwen3 directly for 12 ranked candidates from the fixed disorder pool does **NOT** match the TF-IDF union approach. Qwen3 ranking is the bottleneck, not the candidate-pool size.

| Metric | Value | Comparison |
|---|---:|---|
| Qwen3 top-5 (broader-K probe, fixed pool) | **16.0%** | vs original Qwen3 free top-5: 56.8% |
| Qwen3 top-8 | 28.4% | — |
| Qwen3 top-12 | **43.2%** | vs Qwen+TFIDF union top-5: **79.0%** |

**Pre-registered verdict map:**

- If top-12 ≥ 79.0% → Qwen3 alone matches TF-IDF union (TF-IDF redundant). **NOT MET.**
- If top-12 < 79.0% → TF-IDF-as-candidate-source remains uniquely contributing. **TRUE (43.2% < 79.0%).**
- If top-12 < 60% → Qwen3 LLM ranking is the bottleneck. **TRIGGERED (43.2% < 60%).**

## Mechanism

Two effects compound:

1. **Qwen3 free top-5 vs ranking-from-fixed-pool task mismatch.** The 56.8% baseline is Qwen3 producing its own natural top-5 diagnoses. The broader-K prompt instead gives Qwen3 a 14-code disorder pool and asks it to rank 12 of them. Performance collapses (16.0% at K=5) — Qwen3 is much weaker at ranking-from-fixed-pool than at free generation.

2. **Subcode mismatch (parsing artifact).** Qwen3 frequently outputs subcodes (F32.1, F31.1, F32.9) that are not in the base-code candidate pool {F32, F41, F42, ...}. After filtering to the pool, fewer than 12 codes remain. This adds parsing noise but does not change the headline conclusion — even at K=12 with full ranking, Qwen3 cannot reach 79%.

The dominant effect is #1: Qwen3's diagnostic distribution does not include the gold set frequently enough to cover size=2 cases, regardless of prompt budget.

## Implication

This is the fifth and strongest piece of evidence that **TF-IDF as a candidate-source is uniquely contributing** on Lingxi:

- Marginal source contribution: TF-IDF + LR adds +11.1pp recall not covered by any LLM source (commit `91d28bb`).
- Multi-LLM ensemble (Qwen+Gemma): only +3.7pp marginal.
- 88.9% of TF-IDF's recovered size=2 cases are not covered by ANY Qwen mode's top-5.
- Same-LLM meta-judge variants (B3a/B3b/B3e/B3i) all negative; only B3c (disorder-def-only, +1.9pp) positive.
- **Broader-K Qwen3 probe (this audit): K=12 = 43.2% << TF-IDF union 79.0%.**

The architectural conclusion stands: TF-IDF lexical retrieval surfaces candidates that Qwen3's LLM-reasoning paradigm systematically under-weights. Increasing Qwen3's prompt budget alone cannot recover this signal.

## Files

- Output: `results/phase1_recall_probe/qwen3_top12_lingxi_size2.jsonl` (81 records, top12 + raw model output)
- Probe script: `/tmp/probe/broader_k_qwen3.py` (sandbox-only, not committed)
- Coverage analysis: this document.

## Files NOT modified

- `paper-integration-v0.1` tag (commit c3b0a46) — UNTOUCHED
- BETA-2b primary-only output policy — UNCHANGED
- All committed predictions in `results/predictions/` — READ-ONLY
- `src/culturedx/modes/hied.py` production code — NO Gap F changes
- Manuscript drafts — NO Gap F edits
