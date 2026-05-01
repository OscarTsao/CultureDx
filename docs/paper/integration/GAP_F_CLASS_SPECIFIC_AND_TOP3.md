# Gap F Class-Specific Rerankers + Top-3 Effect

**Date:** 2026-05-02

## §A — Class-specific rerankers

Train separate LightGBM rerankers for each Qwen3 top-1 class. Test if class-specialized rerankers beat the unified reranker.

| Top-1 class | N test | Baseline | Unified | Class-specific |
|---|---:|---:|---:|---:|
| F32 | 188 | 0.4521 | 0.5691 (+11.7pp) | **0.5745 (+12.2pp)** |
| F41 | 77 | 0.5974 | **0.6494 (+5.2pp)** | 0.6364 (+3.9pp) |

Mixed result:
- F32 specialist: marginally better (+0.5pp over unified)
- F41 specialist: worse (-1.3pp from unified)

Sample sizes for other classes (F39, F42, F33) too small for stable per-class training.

**Conclusion:** Unified reranker is sufficient. Class-specific specialization gives marginal improvement at best, with risk of overfitting on small per-class subsets.

## §B — Reranker effect on Top-3 metric

Tests whether the reranker improves not just Top-1 but also Top-3 accuracy.

| Metric | Baseline | Reranker | Δ |
|---|---:|---:|---:|
| Top-1 | 0.4700 | 0.5733 | +10.3pp |
| **Top-3** | **0.8033** | **0.8467** | **+4.3pp** |

The reranker improves both metrics:
- **Top-1 +10.3pp**: ranking changes promote gold from rank 2-5 to rank 1
- **Top-3 +4.3pp**: ranking changes promote gold from rank 4-5 to rank 1-3

Top-3 lift is smaller because most of the time gold is already in original top-3. The +4.3pp recovers cases where Qwen3 had gold at rank 4 or 5 and the reranker pulls it into rank 3.

## §C — Why Top-3 effect matters

For downstream uses requiring top-3 candidate inspection (e.g., clinical review), the reranker provides additional benefit beyond Top-1:

- Improves the "is gold in the candidate set we'd surface to clinician" rate
- Doesn't just shuffle the same set — actively promotes correct candidates
- Useful for set-based set evaluation (multi-label cases, audit reports)

This strengthens the paper claim: the reranker is not just a Top-1 optimizer, it's a general candidate-quality improver across rank cutoffs.

