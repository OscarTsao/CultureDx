# Paper Narrative Reframe (v5) - Canonical

**Status**: Numbers are commit-backed and paper-ready.
**P0 commits**: `914381b` (clean/v2.5) + `c7f8fa0` (main-v2.4)
**MDD-5k commit**: `3a2d6d5` (main-v2.4)
**Source of truth**: `results/analysis/metric_consistency_report.json`
**Canonical reconciliation**: `docs/audit/AUDIT_RECONCILIATION_2026_04_25.md`

---

## Abstract Draft

> CultureDx is a Chinese psychiatric multi-agent diagnosis system for ICD-10 and DSM-5 reasoning over clinical transcripts. We report deployment-oriented capabilities not provided by pure supervised baselines, while documenting accuracy parity rather than improvement.
>
> First, **disagreement-driven clinician triage**: supervised-hybrid model discordance flags 26.4% of cases and enriches deployed-model error rate by 2.06x on LingxiDiag-16K (N=1000). The signal is not redundant with confidence-quantile triage (Jaccard 0.357); a two-stage union policy captures 58% of system errors at 38.9% flag rate. Diagnostic-standard discordance (ICD-10 vs DSM-5) provides a complementary triage signal at 25.1% flag rate on LingxiDiag and 20.8% on MDD-5k.
>
> Second, **cross-dataset bias robustness**: under MDD-5k synthetic distribution shift, a single-LLM baseline exhibits 189x F32/F41 asymmetric collapse; the multi-agent pipeline bounds this to 8.94x (a 21x improvement), and a somatization-aware prompt mitigation further reduces asymmetry to 5.58x.
>
> Third, **dual-standard audit**: CultureDx supports parallel ICD-10 and DSM-5 reasoning with both-mode preserving ICD-10 primary decisions (1925/1925 ICD-10/Both match across LingxiDiag and MDD-5k). Dual-standard evaluation showed dataset-dependent metric trade-offs: DSM-5 v0 was weaker than ICD-10 on Top-1 in both datasets and weaker on Top-3 on MDD-5k, but achieved higher F1_macro, weighted-F1, binary accuracy, four-class accuracy, and Overall on MDD-5k. We interpret this as standard-sensitive diagnostic structure under distribution shift, not as DSM-5 clinical validation.
>
> The Stacker LGBM achieves Top-1 = 0.612, Top-3 = 0.925, F1_macro = 0.334, Overall = 0.617 on LingxiDiag-16K test_final, matching our reproduced TF-IDF baseline (Top-1 = 0.611) within the pre-specified +/-5pp non-inferiority margin (McNemar p approximately 1.0). MAS features contribute 11.9% of stacker decision weight; supervised features contribute 88.1%. We report this decomposition transparently to inform deployment trade-offs: accuracy-only deployments may use TF-IDF; deployments requiring auditability, bias control, or dual-standard reasoning require the MAS architecture.
>
> All experiments are on synthetic Chinese clinical dialogues. DSM-5 v0 criteria are LLM-drafted (`UNVERIFIED_LLM_DRAFT`); AIDA-Path structural alignment and Chang Gung Memorial Hospital clinical review are pending. Class-specific limitations (F31, F43, F98, Z71 near-zero recall on both datasets; F42 OCD recall reduced 40pp in DSM-5 mode under conservative all-required exclusion semantics) are documented openly.

---

## Section 5 - Architecture Results

### 5.1 Main Benchmark

[Table 5 - paper-aligned multilabel evaluation]

| System | 2c Acc | 4c Acc | 12c Top-1 | 12c Top-3 | F1_macro | F1_w | Overall |
|---|---:|---:|---:|---:|---:|---:|---:|
| Paper TF-IDF | .753 | .476 | .496 | .645 | .295 | .520 | .533 |
| Paper best LLM | .841 | .470 | .487 | .574 | .197 | .439 | .521 |
| Our TF-IDF | not v4-finalized | not v4-finalized | .611 | not v4-finalized | .373 | .602 | not v4-finalized |
| MAS-only (DtV) | not v4-finalized | not v4-finalized | .516 | not v4-finalized | .171 | .447 | not v4-finalized |
| **Stacker LGBM** | .753 | .546 | **.612** | **.925** | .334 | .573 | **.617** |
| **Stacker LR** | .619 | .538 | .538 | .887 | **.360** | .558 | .572 |

Stacker LGBM matches our reproduced TF-IDF on Top-1 (delta +0.001,
McNemar p approximately 1.0) within the pre-specified +/-5pp
non-inferiority margin. It exceeds the published paper TF-IDF baseline
(+11.6pp Top-1) and the published best LLM (+12.5pp). We disclose that our
reproduced TF-IDF is stronger than the paper's reported value; see Section 5.5.

### 5.2 Feature Ablation

Stacker LGBM feature importance: TF-IDF 88.1%, MAS 11.9%. The evidence is best
framed as MAS-as-deployment-substrate rather than MAS-as-accuracy-improver:
the architecture enables auditability, disagreement triage, bias control, and
dual-standard reasoning while supervised features carry most top-line accuracy.

### 5.3 Cross-Dataset Bias Robustness

Under MDD-5k synthetic distribution shift, the single-LLM baseline exhibits
189x F32/F41 asymmetric collapse. MAS reduces this to 8.94x, and R6v2
somatization-aware prompting reduces it further to 5.58x.

### 5.4 Dual-Standard Reasoning

We evaluate three reasoning configurations on the same cases: ICD-10-only,
DSM-5-only, and both-mode (ICD-10 primary + DSM-5 sidecar evidence).

Both-mode is not an ensemble. Across both datasets:

- LingxiDiag (N=1000): ICD-10 vs Both 1000/1000 match
- MDD-5k (N=925): ICD-10 vs Both 925/925 match

Both mode preserves the ICD-10 primary decision for billing compatibility and
emits DSM-5 reasoning as sidecar audit evidence.

**LingxiDiag results** (in-domain):

| Mode | Top-1 | Top-3 | F1_m | F1_w | 2c | 4c | Overall |
|---|---:|---:|---:|---:|---:|---:|---:|
| ICD-10 | 0.507 | 0.800 | 0.199 | 0.457 | 0.778 | 0.447 | 0.5145 |
| DSM-5 | 0.471 | 0.803 | 0.188 | 0.421 | 0.767 | 0.476 | 0.5065 |
| Both | 0.507 | 0.800 | 0.199 | 0.457 | 0.778 | 0.447 | 0.5145 |

ICD-10 vs DSM-5 paper-parent agreement: 0.749. DSM-5 is weaker on Top-1
(-3.6pp) and most aggregate metrics, but slightly higher on Top-3 (+0.3pp).

**MDD-5k results** (synthetic distribution shift):

| Mode | Top-1 | Top-3 | F1_m | F1_w | 2c | 4c | Overall |
|---|---:|---:|---:|---:|---:|---:|---:|
| ICD-10 | **0.597** | **0.853** | 0.197 | 0.514 | 0.890 | 0.444 | 0.566 |
| DSM-5 | 0.581 | 0.842 | **0.230** | **0.526** | **0.912** | **0.520** | **0.584** |
| Both | 0.597 | 0.853 | 0.197 | 0.514 | 0.890 | 0.444 | 0.566 |

ICD-10 vs DSM-5 paper-parent agreement: 0.792. Dual-standard evaluation showed
dataset-dependent metric trade-offs: DSM-5 v0 was weaker than ICD-10 on Top-1
in both datasets and weaker on Top-3 on MDD-5k, but achieved higher F1_macro,
weighted-F1, binary accuracy, four-class accuracy, and Overall on MDD-5k. We
interpret this as standard-sensitive diagnostic structure under distribution
shift, not as DSM-5 clinical validation.

All DSM-5 stubs are `UNVERIFIED_LLM_DRAFT`. The MDD-5k aggregate metric pattern
may reflect v0 criteria choices that align with MDD-5k label distribution, not
validated clinical superiority. AIDA-Path structural alignment for 5 overlapping
disorders is pending.

Per-class trade-off pattern:

- DSM-5 higher on F32 recall: LingxiDiag +4.1pp, MDD-5k +5.0pp
- DSM-5 lower on F41 recall: LingxiDiag -11.5pp, MDD-5k -8.4pp
- DSM-5 lower on F42 recall: LingxiDiag -40pp, MDD-5k -23pp
- F31, F39, F43, F98, and Z71 near-zero recall in both modes on both datasets

The F42 collapse is documented in
`docs/limitations/F42_DSM5_COLLAPSE_2026_04_25.md`: under `all_required: true`
schema, DSM-5 F42 criterion D exclusion is marked `insufficient_evidence` in
80% of F42-gold cases. We do not adjust F42 threshold for the current
submission to avoid test-set tuning.

### 5.5 TF-IDF Reproduction Gap

Our reproduced TF-IDF: 0.604 to 0.611 Top-1 depending on the frozen evaluation
artifact. Paper TF-IDF: 0.496. The gap is disclosed as a limitation. Parity is
claimed against our stronger reproduced baseline, not only against the paper
number.

### 5.6 Confidence-Gated Ensemble

A confidence-gated rule for combining MAS and TF-IDF predictions selected
`tfidf_only` on the held-out evaluation split (McNemar p = 1.0). Confidence
ensembling does not provide reliable case-level override signal over the
supervised baseline. This is reported as a negative result.

---

## Section 6 - Disagreement-as-Triage

### 6.1 Model Discordance Triage

On LingxiDiag-16K test_final (N=1000), supervised-hybrid model discordance
(TF-IDF vs Stacker LGBM) flags 26.4% of cases. Within the disagreement subset,
deployed Stacker accuracy drops from 0.697 (agreement) to 0.375
(disagreement), a 2.06x error-rate enrichment. The signal captures 42.5% of
all deployed-model errors at 26.4% flag rate.

Comparison to confidence-quantile triage: flagging the lowest 26.4% by Stacker
primary-class probability gives 1.92x error enrichment and 40.7% recall.
Disagreement edges out by +0.14x enrichment and +1.8pp recall. Disagreement and
confidence flag overlapping but distinct populations (Jaccard 0.357).

Two-stage policy: union of disagreement OR low confidence flags 38.9% of cases
at 2.17x enrichment and 58.0% error recall, the strongest configuration in the
analysis.

### 6.2 Diagnostic-Standard Discordance Audit

LingxiDiag (N=1000): ICD-10 vs DSM-5 disagree on 25.1% of cases. Deployed
ICD-10 accuracy in the disagreement subset is 0.382 vs 0.549 in the agreement
subset. Error enrichment: 1.37x.

MDD-5k (N=925): ICD-10 vs DSM-5 disagree on 20.8% of cases (192/925). A formal
MDD-5k error-enrichment triage table remains a next zero-GPU analysis, so the
current paper claim is limited to disagreement rate.

These signals are complementary to model discordance: they identify cases where
reasoning standards conflict, not only cases where one model is uncertain.

---

## Section 7 - Limitations

### 7.1 Synthetic-Only Datasets

LingxiDiag-16K and MDD-5k are synthetic. Real-world clinical validation at
Chang Gung Memorial Hospital is pending IRB.

### 7.2 DSM-5 v0 Criteria

All DSM-5 stubs are LLM-drafted (`UNVERIFIED_LLM_DRAFT`). MDD-5k aggregate
metrics for F1, 2-class, 4-class, and Overall may reflect v0 criteria
distribution alignment with MDD-5k labels, not clinical validity. AIDA-Path
structural alignment and clinician review are pending.

### 7.3 F42 OCD Collapse

DSM-5 F42 recall: LingxiDiag 12% vs ICD-10 52% (-40pp); MDD-5k 15% vs ICD-10
38% (-23pp). Trace shows criterion D exclusion marked `insufficient_evidence`
in 80% of F42-gold cases. Documented limitation, not patched. See
`docs/limitations/F42_DSM5_COLLAPSE_2026_04_25.md`.

### 7.4 Class Coverage

F31, F43, F98, and Z71 have near-zero recall in both modes across both datasets,
with F39 also weak in dual-standard slices. This creates a hard ceiling on
aggregate Top-1.

### 7.5 Both-Mode Is Not an Ensemble

Both = ICD-10 primary on 1925/1925 cases (LingxiDiag + MDD-5k). DSM-5 is
sidecar evidence.

### 7.6 Stacker Feature Contribution

TF-IDF 88.1% / MAS 11.9% (LGBM importance). Accuracy comes primarily from
supervised features.

### 7.7 Confidence-Gated Ensemble Is Null

Selected rule = `tfidf_only`. McNemar p = 1.0. Reported transparently.

### 7.8 Per-Class Slice Taxonomy

Per-class results in Section 5.4 use `pilot_comparison.per_class_metrics`
(paper-parent class total). `metrics_summary.slice_metrics` use a different
slice definition; these are not directly comparable. We report only the
paper-parent source for class-level claims.

### 7.9 TF-IDF Reproduction Gap

Our TF-IDF Top-1 is materially above the paper's reported TF-IDF Top-1. Cause
is not fully identified; candidate causes include tokenization, feature
engineering, logistic-regression hyperparameters, and split differences.

### 7.10 Evaluation Contract Repair History

Pre-2026-04-25 metric values are deprecated. Current values are post evaluation
contract repair (commits `914381b` and `c7f8fa0`). See
`docs/audit/AUDIT_RECONCILIATION_2026_04_25.md` for the change trail.

---

## Discussion Key Points

1. **MAS-as-substrate, not MAS-as-classifier**: We do not claim MAS improves
   accuracy. We claim MAS enables deployment properties unavailable without it:
   auditability, dual-standard reasoning, disagreement triage, and bias control.
2. **Reproducibility-first frame**: Evaluation contract documented, case
   manifest SHA256 recorded, paper-parent normalization tested, and deprecated
   values reconciled.
3. **Honest negative findings**: ensemble null, novel-class retraction, F42
   limitation, and F33 taxonomy handling are all reported.
4. **Disagreement triage and confidence triage are complementary**: 2.06x vs
   1.92x enrichment, Jaccard 0.357, and union policy strongest.

---

## What This Narrative Does Not Claim

- Outperforms TF-IDF on accuracy.
- Disagreement captures all errors.
- DSM-5 mode is clinically validated.
- Both-mode improves over single-standard accuracy.
- Confidence ensemble produces gains.
- Novel class detection works.
- Real-world deployment is validated.
- AIDA-Path validation is completed.

---

## Status

**Narrative**: reviewer-safe source for paper Section 5/6 drafting.
**Numbers**: canonical for the cleanup scope, backed by
`results/analysis/metric_consistency_report.json` and reconciled in
`docs/audit/AUDIT_RECONCILIATION_2026_04_25.md`.
