# Section 7 — Limitations and Scope

All current evaluations use synthetic or curated benchmark data — LingxiDiag-16K test_final (N = 1000) and the synthetic distribution-shift dataset MDD-5k (N = 925).
We do not claim clinical deployment readiness or prospective clinical validity.
We have not yet evaluated CultureDx on clinician-adjudicated real-world clinical transcripts.
The §5 / §6 results characterize benchmark-level behavior — accuracy parity, F32/F41 directional asymmetry, dual-standard audit trade-offs, and case-level disagreement triage — and we frame these throughout as audit-relevant system properties rather than clinical evidence.

The DSM-5 reasoning mode used in §5.4 and §6.2 relies on an LLM-drafted v0 formalization of DSM-5 concepts (`dsm5_criteria.json`, version `0.1-DRAFT`, source-note `UNVERIFIED`).
This schema has not been reviewed or validated by clinicians, so all DSM-5 outputs throughout the paper are experimental audit observations rather than clinically validated DSM-5 diagnoses.
Both mode preserves the ICD-10 mode primary output and exposes DSM-5 reasoning as sidecar audit evidence on the same case; pairwise agreement with ICD-10 mode is 1000 / 1000 on LingxiDiag-16K and 925 / 925 on MDD-5k, with 0 / 15 metric-key differences on both datasets.
Both mode is therefore an architectural pass-through, not an ensemble; we do not claim accuracy gain from combining ICD-10 and DSM-5 reasoning.

The F32/F41 asymmetry result reduces the MDD-5k F41→F32 / F32→F41 ratio from 189× under the single-LLM baseline (raw 189 / 1) to 3.97× under MAS ICD-10 v4 (raw 151 / 38, 95% bootstrap CI [2.82, 6.08]) — a 47.7-fold reduction relative to the baseline.
The 3.97× endpoint remains an asymmetric error pattern, with F41→F32 still the dominant misclassification direction within this F32/F41 error pair; we do not claim F32/F41 bias is solved.
F42/OCD recall decreases under DSM-5-only mode on both datasets, with magnitudes that depend on the slice and class definition.
Under the LingxiDiag paper-parent per-class definition, F42 recall drops from 52% (ICD-10) to 12% (DSM-5) at n = 25; under the v4 slice metric on LingxiDiag, the corresponding drop is approximately 30.6 percentage points at n = 36.
On MDD-5k both definitions show the same direction at smaller magnitudes (paper-parent −23.1pp at n = 13 small-N exploratory; v4 slice −23.8pp at n = 21).
The F42 finding is a limitation of the v0 DSM-5 formalization — specifically criterion-D exclusion / differential-diagnosis evidence handling, which cannot be reliably verified from a single transcript under the current schema.
We therefore do not retune F42 thresholds post hoc on the basis of this test-set finding; criterion-D handling itself remains pending clinician review (§7.8).

Class-level coverage is uneven: several low-frequency paper classes show near-zero recall under the present pipeline, and macro-F1 remains modest relative to Top-1 / Top-3 because of these rare-class and Others blind spots.
Where class-specific claims are made elsewhere in the paper, we report raw counts and scope them to the relevant high-frequency or pre-specified diagnostic pair rather than asserting uniform per-class performance or comprehensive 12-class coverage.
Our reproduced TF-IDF baseline reaches Top-1 = 0.610 on LingxiDiag-16K test_final, an 11.4 percentage-point gain over the published baseline of 0.496, and we have not fully isolated the cause of this reproduction gap; plausible contributors are documented in §5.5.
We disclose this gap explicitly: the §5.1 parity claim uses our stronger reproduced baseline (Stacker LGBM 0.612 vs reproduced TF-IDF 0.610) rather than the easier published baseline, so reviewers may inspect both comparisons.

Two external validation anchors remain pending and are listed as future work, not present evidence.
AIDA-Path structural alignment between the v0 DSM-5 schema and the AIDA-Path digital-medicine ontology has been planned but not yet completed; the same applies to independent clinician review of the DSM-5 v0 schema (§7.2) and the F42 criterion-D exclusion handling (§7.6).
We do not present any AIDA-Path overlap result or clinician-reviewed criterion as part of the present paper's evidence.
Accordingly, the present claims are restricted to the bias-asymmetry, dual-standard audit, and disagreement-triage findings under the scoped benchmark setting.
