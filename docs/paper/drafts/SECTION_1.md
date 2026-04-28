# Section 1 — Introduction

Chinese-language psychiatric differential diagnosis from clinical dialogue or transcript is a difficult benchmark task: a single case may carry overlapping ICD-10 [CITE who1992icd10] categories, raw subcodes such as F41.2 (mixed anxiety-depression) that do not map cleanly onto coarse parent labels, and dataset-specific surface patterns that make Top-1 classification a useful but partial measure of system quality.
Beyond Top-1 accuracy, three further properties matter for benchmark systems intended to support future clinical translation.
Auditability allows downstream readers to trace each diagnostic decision to specific criterion evidence.
Sensitivity to the choice of diagnostic standard (ICD-10 versus DSM-5 [CITE apa2022dsm5tr]) allows a system's behavior under an alternative standard to be inspected rather than assumed.
Distribution-shift evaluation probes whether benchmark behavior is silently driven by surface artifacts of one synthetic dataset.
Existing LingxiDiag-style [CITE — verify: LingxiDiag] benchmark reporting emphasizes Top-1 and related classification metrics, but does not directly evaluate these audit-relevant system properties.

A second observation from our experiments motivates the paper's empirical posture.
Strong character / word TF-IDF baselines remain remarkably competitive on the 12-class psychiatric Top-1 task: our reproduced TF-IDF baseline reaches Top-1 = 0.610 on LingxiDiag-16K, substantially stronger than the published TF-IDF baseline of Top-1 = 0.496 and within +0.2 percentage points of our selected hybrid Stacker LGBM at Top-1 = 0.612 (§5.1, §5.5).
LLM-only and multi-agent (MAS) systems therefore cannot justify themselves on Top-1 dominance alone in this setting: the MAS-derived feature block contributes only 11.9 percent of the Stacker LGBM feature importance share (§5.2), and a confidence-gated MAS / TF-IDF ensemble produces no detectable Top-1 gain (§5.6).
Our empirical posture is accordingly Top-1 parity, not accuracy superiority, with the case for MAS resting on system properties that Top-1 does not capture.

CultureDx is built around a multi-agent hierarchical evidence-driven (HiED) reasoning pipeline that produces a primary diagnosis together with criterion-level audit traces.
The reported benchmark system, Stacker LGBM, is a hybrid supervised + MAS stacker rather than an LLM-only system: it combines 13 TF-IDF features (12 per-class probabilities plus a Top-1 margin) with 18 MAS-derived features (5 Direct-to-Verdict rank confidences, 12 per-class Criterion Checker met-ratios, and 1 abstain flag), trained as a LightGBM tree booster (§4.2).
The MAS architecture supports three paper-facing standard configurations — ICD-10, DSM-5-only, and Both — implemented as standard-dispatch settings within HiED rather than as separate code-level pipeline modes (§4.3).
All §5–§7 numerical claims use a post-v4 evaluation contract that distinguishes 12-class paper-parent metrics from raw-`DiagnosisCode`-aware 2-class and 4-class auxiliary tasks, with F41.2 and mixed comorbid cases excluded from the binary depression / anxiety task per the paper's task definition (§4.4).

The paper makes five scoped contributions.
First, CultureDx reaches benchmark parity with a strong reproduced supervised baseline: Stacker LGBM obtains Top-1 = 0.612 versus reproduced TF-IDF = 0.610 on LingxiDiag-16K, a +0.2 percentage-point paired difference within the ±5 percentage-point non-inferiority margin; paired-discordance testing is reported in §5.1.
Second, the ICD-10 MAS pipeline substantially reduces cross-dataset F32/F41 error asymmetry: on MDD-5k [CITE — verify: MDD-5k], the single-LLM baseline exhibits a 189× F41→F32 / F32→F41 directional asymmetry, whereas MAS ICD-10 v4 reduces this to 3.97×; residual asymmetry remains and we do not claim the bias is solved (§5.3).
Third, model-discordance and diagnostic-standard discordance expose error-enriched case subsets: TF-IDF/Stacker disagreement flags 26.4 percent of LingxiDiag cases at 2.06× error enrichment, and a union with confidence-based triage increases error recall to 58.0 percent, so we frame these signals as complementary audit mechanisms rather than replacements for confidence-based triage (§6).
Fourth, dual-standard evaluation exposes DSM-5-v0 metric-specific trade-offs, including a widened F32/F41 asymmetry, while Both mode preserves the ICD-10 primary output and attaches DSM-5 sidecar audit evidence rather than forming an ensemble (§5.4, §7.3).
Fifth, we make the evaluation contract and limitations explicit: DSM-5 criteria are LLM-drafted and unverified, datasets are synthetic / curated benchmarks, the post-v4 raw-code-aware evaluation contract documents F41.2 handling and supersedes earlier pre-v4 audit artifacts, and AIDA-Path [CITE strasser2026machine] structural alignment and clinician review remain pending future work (§4.4, §7.1, §7.2).

We close the introduction with an explicit scope statement.
We do not claim clinical deployment readiness, DSM-5 clinical validity, or MAS accuracy superiority over TF-IDF.
The paper reports benchmark behavior on synthetic / curated datasets; AIDA-Path structural alignment and clinician review of the DSM-5 v0 schema are pending future work, as is evaluation on clinician-adjudicated real-world clinical transcripts (§7.1, §7.2, §7.8).
The sections that follow describe the task and datasets (§3), the CultureDx methods and evaluation contract (§4), the main benchmark and audit-relevant findings (§5–§6), and a consolidated discussion of limitations (§7).
