# Section 4 — Methods

## 4.1 CultureDx MAS architecture

CultureDx is a multi-agent reasoning architecture that produces a primary diagnosis together with criterion-level audit traces for each case.
The architecture is designed to expose audit traces in addition to benchmark performance: agents communicate via structured intermediate artifacts so that downstream decisions can be traced to specific criterion evidence.

The agent pipeline consists of a Triage agent that selects a candidate disorder shortlist, a Criterion Checker that evaluates per-disorder ICD-10 or DSM-5 criteria against transcript evidence, a Logic Engine that resolves criterion-level decisions into per-disorder eligibility, a Calibrator that adjusts confidences using held-out development data, a Comorbidity Gate that decides whether multiple disorders should be reported jointly, and a Diagnostician that produces the final ranked output.
A Direct-to-Verdict (DtV) configuration of the Diagnostician is also retained as a comparator: it bypasses the criterion-checking pipeline and emits a ranked output directly from the LLM, and it serves as the MAS-only baseline reported in §5.1.
The LLM backbone is Qwen3-32B-AWQ served via vLLM. BGE-M3 supports retrieval utilities in the broader system, but the reported benchmark metrics do not depend on a retrieval ablation.
We make no claim that criterion traces are clinically faithful; the agents are LLM-backed and have not been clinically validated.

## 4.2 Baselines and stacker

We compare our system against two LingxiDiag report reference baselines (the published TF-IDF baseline and the published best LLM baseline) and against four candidate systems of our own.
Our selected primary system is **Stacker LGBM**, a hybrid supervised-plus-MAS stacker built on a LightGBM tree booster.
The remaining three candidate systems are: a **reproduced TF-IDF baseline** (logistic regression on character / word TF-IDF features); a **MAS-only DtV** comparator (Direct-to-Verdict diagnostician without supervised features); and **Stacker LR**, an alternative hybrid stacker built on logistic regression.

The stacker uses 31 total features partitioned into a TF-IDF block and an MAS block.
The TF-IDF block contains 13 features: 12 per-class TF-IDF probabilities plus a Top-1 margin feature.
The MAS block contains 18 features: 5 DtV rank confidences, 12 per-class Criterion Checker met-ratios, and 1 abstain flag.
This decomposition is documented in `docs/analysis/MAS_vs_LGBM_CONTRIBUTION.md` and motivates the §5.2 feature-importance analysis.
Stacker LGBM is therefore a hybrid supervised-plus-MAS model, not an LLM-only system; we treat all benchmark comparisons against the LingxiDiag published baselines as hybrid-system comparisons rather than LLM-only results.

We retain Stacker LR alongside Stacker LGBM because the two stackers occupy different points on the Top-1 / macro-F1 trade-off: Stacker LR has the highest macro-F1 in our evaluation but does not pass the ±5pp non-inferiority margin against the reproduced TF-IDF baseline on Top-1.
Our reproduced TF-IDF baseline reaches a stronger Top-1 than the LingxiDiag-published TF-IDF baseline (see §5.5); the parity claim in §5.1 deliberately uses our stronger reproduced baseline rather than the easier published baseline.

## 4.3 Dual-standard infrastructure

The MAS architecture supports three paper-facing standard configurations: **ICD-10 mode** (MAS reasoning under the ICD-10 standard), **DSM-5-only mode** (the same MAS architecture under v0 DSM-5 templates), and **Both mode** (ICD-10 reasoning produces the primary output, with DSM-5 reasoning attached as sidecar audit evidence on the same case).
For paper readability we describe these as standard configurations; in implementation they are standard-dispatch settings (`DiagnosticStandard.{ICD10, DSM5, BOTH}`) within the HiED pipeline mode rather than separate top-level code modes — the actual code-level pipeline modes are `hied` and `single`, where `single` is the DtV-only baseline used in §4.2.

Both mode is an architectural pass-through, not an ensemble: pairwise agreement with ICD-10 mode is 1000 / 1000 on LingxiDiag-16K and 925 / 925 on MDD-5k, with 0 / 15 metric-key differences on both datasets (Table 4 Panel C).
We do not claim accuracy gain from combining ICD-10 and DSM-5 reasoning; the value of Both mode lies in the case-level DSM-5 sidecar audit evidence it exposes alongside the unchanged ICD-10 primary output.

The DSM-5 templates used in DSM-5-only mode and as the Both-mode sidecar are LLM-drafted v0 formalizations stored in `src/culturedx/ontology/data/dsm5_criteria.json`, with version `0.1-DRAFT` and source-note `LLM-drafted v0 based on DSM-5-TR concepts. UNVERIFIED.`.
This schema has not been reviewed or validated by clinicians; we treat all DSM-5 outputs throughout the paper as experimental audit observations rather than clinically validated DSM-5 diagnoses, and we discuss this scoped interpretation in §5.4 and §7.2.

## 4.4 Evaluation contract v4

All §5 / §6 numerical claims in the present paper are computed under evaluation contract v4 (post-2026-04-25 reconciliation).
Earlier paper-number artifacts are retained for provenance; current paper claims use the post-v4 metric-consistency report and audit reconciliation documented in `docs/audit/AUDIT_RECONCILIATION_2026_04_25.md`.

Each metric family in the contract uses an explicit prediction view and an explicit gold view, listed below.

**Box 1 — CultureDx v4 evaluation contract.**

| Metric family | Prediction source | Gold source |
|---|---|---|
| 12-class Top-1 | `primary_diagnosis` paper-parent normalized | multilabel paper-parent gold |
| 12-class Top-3 | `[primary] + (ranked − {primary})[:2]` | multilabel paper-parent gold |
| 12-class F1 / Exact Match | primary plus threshold-gated comorbid_diagnoses | multilabel paper-parent gold |
| 2-class | primary mapped to binary category | raw `DiagnosisCode`; F41.2 excluded |
| 4-class | predicted label set mapped to four-class category | raw `DiagnosisCode`; F41.2 → Mixed |
| Overall | mean of all non-`_n` metric values in the contract above | (composite) |

Two clarifications follow directly from this contract.
First, raw `DiagnosisCode` is used to construct 2-class / 4-class gold labels; predictions are mapped from model outputs to the corresponding binary or four-class category, not read from raw `DiagnosisCode`.
Second, Top-3 is computed as `[primary] + (ranked − {primary})[:2]` rather than `primary + comorbid_diagnoses` — the latter is threshold-gated and typically too short to fill Top-3.
Under v4, the 2-class evaluation has n = 473 on LingxiDiag-16K and n = 490 on MDD-5k after F41.2 and mixed-comorbid exclusions; the 4-class evaluation retains all 1000 / 925 cases.
Pre-v4 audit numbers used parent-collapsed 2-class gold and reported n = 696, which conflated F41.2 and mixed cases; these earlier values are superseded under v4 and should not be cited as current claims.

## 4.5 Statistical analysis

Statistical claims throughout §5 and §6 use procedures defined in the post-v4 evaluation contract: paired McNemar tests for paired Top-1 comparisons, percentile bootstrap confidence intervals for asymmetry ratios and metric differences, and a ±5 percentage-point non-inferiority margin on Top-1.
McNemar uses continuity correction with a p < 0.05 threshold.
Bootstrap CIs use 1000 resamples with seed 20260420 and the 95% percentile interval.
Paired bootstrap is used for the F32/F41 asymmetry comparison between DSM-5 and ICD-10 modes (§5.3) and for the disagreement-triage advantage analysis (§6.1).

Non-inferiority is assessed by the paired Top-1 difference relative to this ±5pp margin, NOT by the McNemar p-value alone.
McNemar is reported as a paired discordance test — evidence of no detectable paired difference at our sample size — and is not by itself an equivalence test.
The parity claim in §5.1 rests on the bounded effect size (+0.2pp Stacker LGBM vs reproduced TF-IDF, well within ±5pp), with McNemar p ≈ 1.0 reported as supporting descriptive context.

For the disagreement-triage analyses in §6.1, we report case-level metrics defined on a fixed review-budget basis: flag rate, accuracy on flagged versus unflagged subsets, error enrichment ratio, and error recall.
We do not interpret a bootstrap CI on the disagreement-vs-confidence advantage that includes zero as evidence that the two signals are equivalent; we report instead that no statistically detectable advantage is observed at our sample size.
