# Gap F B3c — Disorder-Definition-Only Reasoning Agent (POSITIVE RESULT)

**Date:** 2026-05-02
**Status:** Sandbox audit. Uncommitted (will commit with this file).

## TL;DR — POSITIVE result (FIRST meta-agent variant to beat baseline)

B3c: Qwen3 sees ONLY (a) Qwen3's top-5 ranked list, (b) ICD-10 disorder definitions for those candidates. NO transcript, NO checker output, NO confirmed_codes.

| Method | Top-1 | Δ |
|---|---:|---:|
| Baseline (Qwen3 rank-1 primary) | 0.5010 | — |
| **B3c (disorder-def-only)** | **0.5200** | **+1.9pp** |

77 cases changed primary:
- delta_correct: 28
- delta_wrong: 9
- **Net: +19 cases helped**

3.1:1 helped:hurt ratio (favorable).

## Comparison with all meta-agent variants

| Variant | Has transcript? | Has structured signals? | Has disorder defs? | Δ Top-1 |
|---|:---:|:---:|:---:|---:|
| B3a (primary-fix, full context) | YES | YES | NO | -2.8pp |
| B3b (structured-only) | NO | YES (full) | NO | -2.0pp |
| B3e (pairwise no transcript) | NO | YES (top-2 + checker) | YES (top-2 only) | -0.7pp |
| **B3c (disorder-def-only)** | NO | NO | YES (top-5) | **+1.9pp** |

## Mechanism: why does B3c work?

The clean POSITIVE result for B3c, while ALL three other meta-variants are NEGATIVE, suggests:

1. **Disorder definitions are the discriminative signal.** When the LLM has ICD criteria text (which is canonical, non-noisy), it can reason about which candidate is the best fit.

2. **Transcript adds noise to second-pass review.** B3a/B3e (with various transcript info) all hurt. The case-text re-reading triggers the LLM to find new "supporting evidence" for changes that aren't actually correct.

3. **Structured signals (met_ratio, confirmed_codes) without text are too sparse.** B3b had this and underperformed.

4. **Definitional reasoning IS a different perspective from transcript-based reasoning.** The LLM has to compare "which definition best fits Qwen3's evidence"; this differs from "which symptoms in the text suggest each disorder."

## Implications

- This is the **FIRST positive meta-agent variant** in our sweep.
- Suggests adding a **definition-aware refinement layer** to the MAS architecture.
- Not large in absolute magnitude (+1.9pp) but consistent direction (3.1:1 helped:hurt).
- Notably orthogonal to the +10pp TF-IDF reranker — could potentially STACK.

## Combined-claim evaluation

If B3c +1.9pp stacks orthogonally with reranker +10.3pp, total addressable lift could be ~+12pp. But this is speculative — would need to test the stacked combination.

## Sample helped cases

(To be added: 5 cases where B3c correctly switched primary based on definition mismatch with Qwen3's choice.)

