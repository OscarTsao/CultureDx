# Gap F B3a — Primary-Fix Agent (Qwen3 reviews own primary with transcript)

**Date:** 2026-05-02
**Branch:** tier2b/hierarchical-prompt @ HEAD
**Status:** Sandbox audit. Uncommitted (will commit with this file).

## TL;DR — NEGATIVE result

Qwen3 reviewing its own primary diagnosis with full transcript + structured upstream signals (ranked, confirmed_codes, reasoning) makes WORSE primary decisions than just keeping the original Qwen3 rank-1.

| Method | Top-1 | EM |
|---|---:|---:|
| Baseline (Qwen3 BETA-2a primary) | 0.5010 | 0.4520 |
| B3a (primary-fix agent) | 0.4730 | 0.4280 |
| Δ | -2.8pp | -2.4pp |

156 primary changes. Of those:
- delta_correct (B3a right, baseline wrong): 64
- delta_wrong (baseline right, B3a wrong): 92
- **Net: -28 cases harmed**

## Comparison with B3b (structured-only meta)

Both meta-judge variants lose to the original Qwen3:

| Variant | Has transcript? | Has structured signals? | Top-1 vs baseline |
|---|:---:|:---:|---:|
| B3a (this) | YES | YES | -2.8pp |
| B3b | NO | YES | -2.0pp |

B3a is slightly worse than B3b. Adding transcript actually doesn't help — the "review my own decision" framing is intrinsically biased toward changes (LLM is being asked "is this wrong?" so it finds reasons to change).

## Conclusion

Self-review by the same LLM is harmful regardless of input. The original Qwen3 forward-pass already captures the best signal available from this LLM family. Second-pass review introduces noise, not insight.

Implication: meta-judge / primary-fix agents using the SAME LLM are not useful. Future work would need a DIFFERENT LLM family (or DIFFERENT epistemic role like pairwise differential, critic, etc.).

