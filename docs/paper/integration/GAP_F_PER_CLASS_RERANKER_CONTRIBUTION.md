# Gap F Per-Class TF-IDF Reranker Contribution

**Date:** 2026-05-02
**Branch:** tier2b/hierarchical-prompt @ HEAD
**Status:** CPU-only. Uncommitted.

## TL;DR

Decomposes the +9.7pp Top-1 logistic-reranker lift (commit `0b1c243`) by gold class. Identifies which classes benefit most/least from TF-IDF features.

## Per-class breakdown (test split, n=300 cases)

| Class | N | Helped | Hurt | Net | Net % |
|---|---:|---:|---:|---:|---:|
| **F41 (anxiety)** | 114 | **20** | 0 | **+20** | **+17.5%** |
| **F39 (mood NOS)** | 23 | **14** | 0 | **+14** | **+60.9%** |
| F98 (childhood) | 7 | 1 | 0 | +1 | +14.3% |
| F43 (PTSD/adjustment) | 3 | 1 | 0 | +1 | +33.3% |
| F31 (bipolar) | 3 | 1 | 0 | +1 | +33.3% |
| F32 (depression) | 99 | 0 | 6 | -6 | -6.1% |
| F20 (schizophrenia) | 4 | 0 | 1 | -1 | -25.0% |
| Others / F51 / F42 / F45 / Z71 | 49 | 0 | 0 | 0 | 0% |

## Mechanism

The reranker systematically prefers F41 (anxiety) when TF-IDF features favor it. This:

1. **Recovers F41 gold cases** that Qwen3 misclassified as F32: net +20 (out of 114 F41 cases)
2. **Costs F32 gold cases** that Qwen3 had right but reranker swapped to F41: net -6 (out of 99 F32 cases)
3. **F39 (rare, lexically distinctive)** is the biggest fractional beneficiary at +60.9% — TF-IDF surfaces F39-specific lexical patterns that Qwen3 under-weights

Net win is positive because:
- F41 errors >> F32 errors in baseline Qwen3
- F39's high beneficiation rate captures rare-class signal that LLMs struggle with

## Implication

The TF-IDF feature reranker is most useful for:
- **Common confusion pairs** (F32 ↔ F41) where Qwen3 has a systematic bias
- **Rare classes with distinctive lexical signals** (F39, F43, F31)

It's least useful (or harmful) for:
- Classes where Qwen3 baseline is already strong (F32 — the most common LLM-favored class)
- Very rare classes (F20, F45, Z71) where signal is too sparse to learn

## Future work

- Per-class threshold tuning (only apply reranker when class-specific confidence margin is low)
- Class-aware feature weighting (boost TF-IDF features for F41/F39 cases)
- Investigate F32-loss cases qualitatively — is the reranker actually wrong, or are some "F32 gold" labels questionable?

