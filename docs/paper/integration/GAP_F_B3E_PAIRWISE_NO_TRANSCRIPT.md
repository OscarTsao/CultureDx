# Gap F B3e — Pairwise No-Transcript Differential Agent

**Date:** 2026-05-02
**Status:** Sandbox audit. Uncommitted (will commit with this file).

## TL;DR — Marginally negative

B3e: Qwen3 receives top-2 candidates from Diagnostician + per-candidate checker evidence (met_count, met_ratio, in_confirmed) + disorder definitions. NO transcript. Asked to pick winner.

| Method | Top-1 | Δ |
|---|---:|---:|
| Baseline (Qwen3 rank-1 primary) | 0.5010 | — |
| B3e (pairwise no transcript) | 0.4940 | **-0.7pp** |

66 cases changed primary:
- delta_correct: 16
- delta_wrong: 23
- Net: -7 cases (slightly negative)

## Comparison with other meta-agent variants

| Variant | Has transcript? | Has structured signals? | Δ Top-1 |
|---|:---:|:---:|---:|
| B3a (primary-fix, full context) | YES | YES | -2.8pp |
| B3b (structured-only, no transcript) | NO | YES (full) | -2.0pp |
| **B3e (pairwise no transcript)** | NO | YES (only top-2 + checker) | **-0.7pp** |

**B3e is the least harmful, but still negative.** The constrained pairwise framing reduces error magnitude vs free-form review (B3a) or full structured-input (B3b).

## Mechanism interpretation

The pairwise constraint (only 2 candidates) limits the LLM's degrees of freedom for adding noise. When asked "is it A or B given criterion evidence?" the LLM mostly defers to the primary's higher met_ratio.

But: of 66 changes, only 16 were correct fixes (24%). Random would be ~50%. So the LLM's pairwise judgment is below chance when it overrides the original ranker. This indicates the structured signals alone don't carry enough information to override the LLM Diagnostician's full-text reasoning.

## Conclusion

**No meta-agent variant beats baseline.** B3a (-2.8pp), B3b (-2.0pp), B3e (-0.7pp) all worse than original Qwen3 rank-1 = primary.

Confirms architectural finding: the original Diagnostician's forward-pass already captures the best signal available from this LLM family. Second-pass review (whether with full transcript, structured-only, or pairwise) introduces more noise than insight.

