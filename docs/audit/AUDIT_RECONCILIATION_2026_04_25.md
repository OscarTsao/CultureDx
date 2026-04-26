# Audit Reconciliation - Post Evaluation Contract Repair

**Date**: 2026-04-25 (paper-relevant) / committed 2026-04-26
**Trigger**: GPT-5.5-pro rounds 1-6 evaluation contract review
**Affected canonical**: `docs/analysis/AUDIT_REPORT_2026_04_22.md`
**P0 commits**: `914381b` (clean/v2.5), `c7f8fa0` (main-v2.4)

---

## TL;DR

The values in `docs/analysis/AUDIT_REPORT_2026_04_22.md` were captured from
then-current `metrics.json` files. After P0 evaluation contract repair,
several values in `metrics.json` changed. Audit report values are now
superseded. This document is the canonical change trail.

For paper claims, use values from
`results/analysis/metric_consistency_report.json`. For audit context, this
reconciliation explains what changed and why.

---

## Why values changed

P0 repair refactored `compute_table4_metrics` to
`compute_table4_metrics_v2` with separate prediction views per metric family:

- **Top-1**: primary_diagnosis (paper-parent)
- **Top-3**: `[primary] + (ranked_codes - {primary})[:2]` (paper-parent)
- **F1 / exact match**: `primary + threshold-gated comorbids` (multilabel)
- **2-class gold**: raw `DiagnosisCode` (preserves F41.2 for explicit exclusion)
- **4-class gold**: raw `DiagnosisCode` (preserves F41.2 for Mixed detection)

Before P0, all metrics shared a single `[primary] + comorbids` prediction
list. This caused:

- Top-3 computed from threshold-gated multilabel, which is length 1 in most
  cases, so it degenerated toward Top-1.
- 2-class gold computed from parent-collapsed labels, which lost F41.2 and
  falsely included mixed anxiety-depression cases (`n=696` instead of `473`).
- Audit Top-1 used over-strict single-label semantics (`0.605` instead of
  paper-aligned `0.612`).

---

## Change Table - Stacker (`clean/v2.5-eval-discipline`)

| Field | Audit (2026-04-22) | Post-fix v4 (commit `914381b`) | Reason |
|---|---:|---:|---|
| stacker_lgbm Top-1 | 0.605 | **0.612** | Audit used strict single-label; canonical is paper-aligned multilabel |
| stacker_lgbm Top-3 | 0.925 | **0.925** | Audit cited bootstrap value; old table4 was buggy 0.642 |
| stacker_lgbm F1_macro | 0.358 | **0.3344** | Recomputed from multilabel prediction view |
| stacker_lgbm F1_weighted | 0.587 | **0.5727** | Recomputed |
| stacker_lgbm 2class_Acc | 0.685 | **0.7526** | F41.2 now excluded; n changed 696 to 473 |
| stacker_lgbm 4class_Acc | not in audit | **0.5460** | New under v4 4c contract |
| stacker_lgbm Overall | 0.599 | **0.6166** | Recomputed from corrected components |
| stacker_lgbm 2class_n | 696 | **473** | F41.2 excluded per paper definition |
| stacker_lr Top-1 | 0.533 | **0.538** | Same reasoning as LGBM |
| stacker_lr Top-3 | 0.887 | **0.887** | Already correct in audit |
| stacker_lr F1_macro | 0.369 | **0.3596** | Recomputed |
| stacker_lr F1_weighted | 0.581 | **0.5579** | Recomputed |
| stacker_lr 2class_Acc | not in audit | **0.6195** | Recomputed under v4 |
| stacker_lr 4class_Acc | not in audit | **0.5380** | New |
| stacker_lr Overall | 0.546 | **0.5722** | Recomputed |
| stacker_lr 2class_n | 696 | **473** | F41.2 excluded |

---

## Change Table - Dual-Standard LingxiDiag (`main-v2.4-refactor`)

Before P0, `runner.py` used the same single-prediction-list contract.

| System | Field | Pre-fix | Post-fix v4 (commit `c7f8fa0`) |
|---|---|---:|---:|
| ICD-10 mode | Top-1 | 0.507 | **0.507** |
| ICD-10 mode | Top-3 | 0.644 | **0.800** |
| ICD-10 mode | Overall | 0.500 | **0.5145** |
| DSM-5 mode | Top-1 | 0.471 | **0.471** |
| DSM-5 mode | Top-3 | 0.589 | **0.803** |
| DSM-5 mode | Overall | 0.487 | **0.5065** |
| Both mode | Top-3 | 0.644 | **0.800** |
| Both mode | Overall | 0.500 | **0.5145** |
| All modes | 2class_n | 696 | **473** |

---

## New MDD-5k Full Benchmark (commit `3a2d6d5`)

These values were generated after the v4 contract was active. No reconciliation
is needed; they are canonical from generation.

| System | Top-1 | Top-3 | F1_m | F1_w | 2c Acc | 4c Acc | Overall |
|---|---:|---:|---:|---:|---:|---:|---:|
| MDD-5k ICD-10 | 0.597 | 0.853 | 0.197 | 0.514 | 0.890 | 0.444 | 0.566 |
| MDD-5k DSM-5 | 0.581 | 0.842 | 0.230 | 0.526 | 0.912 | 0.520 | 0.584 |
| MDD-5k Both | 0.597 | 0.853 | 0.197 | 0.514 | 0.890 | 0.444 | 0.566 |

2class_n = 490 for all modes; F41.2 is excluded from the 2-class task.

---

## Unchanged Values

These values were not affected by the contract repair:

- Paper TF-IDF Top-1 = 0.496 (published baseline reference)
- MDD-5k MAS bias asymmetry: single-LLM 189x -> MAS 8.94x -> R6v2 5.58x
- MAS feature contribution: TF-IDF 88.1% / MAS 11.9% (LGBM importance)
- Confidence-gated ensemble null result: selected rule = tfidf_only,
  McNemar p = 1.0
- Retracted experiments: WS-C Exp 1, Exp 2
  (`docs/RETRACTION_NOTICE_2026_04_22.md`)

---

## Hidden Bug Fixes Outside This Reconciliation Table

| Bug | Status | Commit |
|---|---|---|
| eval_stacker DtV subcode match (DtV Top-1 0.339 -> 0.516) | Fixed | `b04ab4f` |
| F32/F33 DSM-5 threshold mismatch (min_total 5 -> 3) | Fixed | `cf96a1f` |
| ICD-10 leftover guidance in DSM-5 checker template | Fixed | `dc2314e` |

These are documented in `docs/analysis/AUDIT_REPORT_2026_04_22.md`; their
resolution is in the commit history.

---

## Reviewer Guidance

If reviewing CultureDx paper claims:

1. Trust `metrics.json` files in `results/rebase_v2.5/` and
   `results/dual_standard_full/`.
2. Trust `results/analysis/metric_consistency_report.json` as the canonical
   numbers index.
3. Read this audit reconciliation for change history.
4. Do not use `docs/analysis/AUDIT_REPORT_2026_04_22.md` numbers without this
   reconciliation.
5. Verify unit tests pass: `uv run pytest tests/test_evaluation_contract.py -v`.

---

## Why This Trail Exists

- Audits on 2026-04-22 represented good-faith capture of then-current values.
- GPT-5.5-pro consultation rounds 1-6 identified evaluation contract bugs.
- P0 contract repair (`compute_table4_metrics_v2`) corrected the bugs.
- Different metrics changed by different amounts; some were unchanged.
- This trail preserves the change history instead of silently overwriting it.

This is methodological transparency, not bug history. Modern hybrid evaluation
systems require explicit prediction-source contracts. We document ours.

---

## Files Affected by This Reconciliation

- `docs/analysis/AUDIT_REPORT_2026_04_22.md` - superseded for numerical claims;
  valid for context and methodology.
- `docs/analysis/EVALUATION_PROVENANCE.md` - current source of truth for the
  evaluation contract.
- `results/analysis/metric_consistency_report.json` - current source of truth
  for canonical values.
- `metrics.json` files - current source of truth for raw metrics.
- `metrics_summary.json` files - synced with `metrics.json` by artifact cleanup
  v6.1.

---

**Last updated**: 2026-04-26
**Authors**: YuNing
**Reviewed by**: GPT-5.5-pro round 6
**Status**: Canonical change trail
