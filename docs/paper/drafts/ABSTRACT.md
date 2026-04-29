# Abstract

**Objective.**
To evaluate whether a Chinese psychiatric multi-agent diagnostic system can match strong supervised baselines while adding audit-relevant system properties beyond Top-1 accuracy.

**Materials and Methods.**
We benchmark CultureDx, a hybrid supervised plus multi-agent (MAS) stacker, on LingxiDiag-16K (in-domain, N=1000) and MDD-5k (external synthetic distribution-shift, N=925), both Chinese-language synthetic or curated benchmarks rather than clinician-adjudicated transcripts.
We compare CultureDx candidate systems against a reproduced TF-IDF baseline under a post-v4 raw-code-aware evaluation contract that defines 12-class paper-parent Top-1 / Top-3, raw-code 2-class and 4-class slices, and statistical procedures (paired McNemar, percentile bootstrap, ±5 percentage-point non-inferiority margin).
We additionally evaluate ICD-10 and DSM-5 v0 standard configurations and a Both mode that preserves the ICD-10 primary output with DSM-5 sidecar audit evidence.

**Results.**
The Stacker LGBM reached Top-1 0.612 versus reproduced TF-IDF 0.610, supporting parity within the non-inferiority margin defined in the post-v4 evaluation contract.
On MDD-5k, the F32/F41 error-asymmetry ratio decreased from 189× under a single-LLM baseline to 3.97× under MAS ICD-10.
TF-IDF/Stacker model-discordance flagged 26.4% of LingxiDiag cases at 2.06× error enrichment over unflagged cases.
Dual-standard evaluation exposed DSM-5-v0 metric-specific trade-offs while Both mode preserved ICD-10 primary output with DSM-5 sidecar audit evidence, not an ensemble.

**Discussion.**
All evidence is benchmark-level on synthetic or curated data, not clinical validation.
The DSM-5 v0 schema is LLM-drafted and unverified; AIDA-Path structural alignment and clinician review remain pending.

**Conclusion.**
CultureDx supports a parity-plus-audit framing rather than an accuracy-superiority or clinical-deployment claim.
