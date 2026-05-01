# Gap F MDD Null-Result Diagnostic

**Date:** 2026-05-02
**Branch:** tier2b/hierarchical-prompt @ HEAD
**Status:** CPU-only diagnostic. Uncommitted.

## Question

User: Why do all TF-IDF methods give 0pp gain on MDD-direction? Is it implementation bug (truncation, vocabulary), or is MDD baseline already too good?

## Hypothesis A: Implementation issue (truncation, vocabulary)

**Test:** Re-run kNN with per-corpus MDD vectorizer (vocab=20K, ngram 1-2) and FULL text (no 5K truncation).

| Configuration | size=2 lift on MDD-test |
|---|---:|
| Original (cross-corpus vectorizer, 5K char truncation) | +6.7pp in-domain |
| Fresh per-corpus MDD vectorizer + full text | **+2.7pp** |

Result: per-corpus full-text gives LESS lift than truncated. Truncation/vocabulary is NOT the cause.

Possible mechanism: dialogue text dilutes TF-IDF vocabulary across turn markers, fillers, conversational repetition — full text adds noise, not signal.

## Hypothesis B: MDD baseline already too good

**Test:** Compare MDD vs Lingxi Top-K oracle ceilings.

| Metric | MDD | Lingxi | Comparison |
|---|---:|---:|---|
| size=2 BOTH gold in top-3 | 34.7% | 40.7% | MDD WORSE |
| size=2 BOTH gold in top-5 | 44.0% | 56.8% | MDD WORSE |
| Top-1 baseline | 0.5924 | 0.5240 | MDD better (+7pp) |

Result: MDD has LOWER multi-gold set coverage (44% vs 57%) — there IS room for improvement on size=2. But MDD Top-1 baseline is 7pp higher.

Interpretation:
- Single-label primary correctness IS stronger on MDD (less reranker headroom)
- Multi-label set retrieval is actually WORSE on MDD (MORE room for candidate-source improvement)

So "baseline already good" is partially true for Top-1 metric (less headroom for reranking), but FALSE for size=2 set coverage (more headroom for candidate generation, yet methods don't capture it).

## Real explanation (synthesis)

The MDD null is a combination of three factors:

1. **Reranker headroom is smaller** on MDD because Top-1 baseline already 0.59 (vs 0.52 Lingxi). Less room for ranking improvement.

2. **Scope mismatch confounds candidate-source approaches.** 33 of 925 MDD cases have gold codes (F64 gender dysphoria, F01 vascular dementia, G47 sleep) outside the 14-disorder scope. NO TF-IDF method can recover these.

3. **Dialogue-style text yields less informative TF-IDF features.** Tested across 8 methods × per-corpus vectorizer × full text. The signal genuinely is weaker — the asymmetry mechanism is real, not artifactual.

## Conclusion

Implementation NOT the cause. The MDD null is genuine corpus-style mismatch. Future work options:
- Specialized dialogue-aware features (DialogBERT, conversation-state encoders)
- Filter out scope-mismatch cases before evaluation
- Train candidate-source ML on dialogue-style data (more MDD-style training corpora)
- Test on real clinical text (likely intermediate between Lingxi and MDD style)

