# Gap F B3i — Critical Reviewer Agent (WORST META-VARIANT)

**Date:** 2026-05-02

## TL;DR — STRONGLY NEGATIVE

B3i: Qwen3 receives transcript + Diagnostician's top-3 ranked codes + their reasoning + confirmed_codes. Asked to find WEAKNESS in Qwen's reasoning and revise primary if found.

| Method | Top-1 | Δ |
|---|---:|---:|
| Baseline (Qwen3 rank-1) | 0.5010 | — |
| **B3i (critical reviewer)** | **0.4130** | **-8.8pp** |

371 cases changed primary (37%! highest of any variant):
- delta_correct: 75
- delta_wrong: 163
- **Net: -88 cases harmed**

Helped:hurt ratio is 1:2.2 — strongly worse than chance.

## Mechanism: why "critical reviewer" framing fails so badly

The prompt explicitly asks the LLM to find weaknesses in Qwen's reasoning. This biases the LLM toward:
1. Finding flaws in any reasoning (confirmation-bias toward criticism)
2. Concluding the original primary is wrong (since you asked it to!)
3. Picking a different code from top-3 just to demonstrate "criticism"

37% change rate (vs 7-30% for other variants) confirms the LLM is over-eager to critique.

## Final ranking of ALL meta-agent variants on Lingxi-icd10 (n=1000)

| Variant | Has transcript? | Has structured signals? | Has disorder defs? | Δ Top-1 | Verdict |
|---|:---:|:---:|:---:|---:|---|
| **B3c (disorder-def-only)** | NO | NO | YES (top-5) | **+1.9pp** | **POSITIVE** |
| B3e (pairwise, no transcript) | NO | YES (top-2 + checker) | top-2 | -0.7pp | Marginal |
| B3b (structured-only) | NO | YES (full) | NO | -2.0pp | Negative |
| B3a (primary-fix, full context) | YES | YES | NO | -2.8pp | Negative |
| **B3i (critical reviewer w/transcript)** | YES | YES (top-3 reasoning) | NO | **-8.8pp** | **WORST** |

## Pattern observed

**Less context = less harm:**
- Most context (B3i transcript + reasoning + confirmed): -8.8pp
- Full transcript + structured (B3a): -2.8pp
- Structured only (B3b): -2.0pp
- Pairwise constrained (B3e): -0.7pp
- Definition-only (B3c): +1.9pp ← only positive

**Plus framing matters:**
- "Find weakness" (B3i): catastrophic
- "Review and may revise" (B3a): bad but less so
- "Pick from definitions" (B3c): mildly helpful

## Conclusion: NO meta-LLM-judge-with-Qwen architecture works

After exhaustive testing of 5 variants, the ONLY positive meta-variant is B3c (disorder-def-only), and its lift (+1.9pp) is fully captured by the +10.3pp TF-IDF feature reranker.

**Architectural recommendation: do NOT add a same-LLM meta-judge agent.** The original Qwen3 forward-pass already captures the best signal from this LLM family. Any second-pass review using Qwen3 introduces noise.

For genuine multi-LLM ensembling, would need a DIFFERENT LLM family (Llama-70B, GPT-5, Claude) — and even then evidence suggests +3.7pp marginal contribution at most (commit `91d28bb`).

