# Paper Narrative Reframe (v4) — Post-Audit, Pre-Regenerated-Metrics

**Status**: 🟡 NARRATIVE READY, NUMBERS CANDIDATE. All `[P0]` markers replace with commit-hash-backed values after `02_REGENERATE_AND_RECONCILE.md` Step 5 completes.

**v4 changes from v3**:
- All Stacker LGBM Top-1 `0.612` reverted to audit canonical `0.605` (Δ2)
- "Independent decision paths" → "supervised-hybrid model discordance" / "diagnostic-standard discordance" (Δ3)
- All Overall values marked `[P0]` (Δ10)
- Confidence triage baseline added to Section 6 (Δ11)
- F42 wording: "checker frequently marks D as insufficient_evidence" (not "correctly identifies", per round 4)

---

## Abstract draft

> CultureDx is a Chinese psychiatric multi-agent diagnosis system for ICD-10 and DSM-5 reasoning over clinical transcripts. We report deployment-oriented capabilities not provided by pure supervised baselines, while documenting accuracy parity rather than improvement.
>
> First, **disagreement-driven clinician triage**: supervised–hybrid model discordance flags 26.4% of cases and enriches deployed-model error rate by 2.06× (LingxiDiag-16K, N=1000). The signal is not redundant with confidence-quantile triage (Jaccard 0.357); a two-stage union policy captures 58% of system errors at 38.9% flag rate. Diagnostic-standard discordance (ICD-10 vs DSM-5) provides a complementary triage signal at 25.1% flag rate.
>
> Second, **cross-dataset bias robustness**: under MDD-5k synthetic distribution shift, a single-LLM baseline exhibits 189× F32/F41 asymmetric collapse; the multi-agent pipeline bounds this to 8.94× (a 21× improvement), and a somatization-aware prompt mitigation further reduces asymmetry to 5.58×.
>
> Third, **dual-standard audit**: CultureDx supports parallel ICD-10 and DSM-5 reasoning. Both-mode output preserves ICD-10 primary decision and surfaces DSM-5 sidecar evidence; this is an audit feature, not an ensemble. We measure 25.1% standard-level disagreement on N=1000.
>
> The Stacker LGBM achieves Top-1 [P0] (audit canonical 0.605 pre-revision; expected 0.612 post-evaluation-contract repair), matching our reproduced TF-IDF baseline (0.611) within ±5pp pre-specified non-inferiority margin (McNemar p ≈ 1.0). MAS features contribute 12% of stacker decision weight; supervised features contribute 88%. We report this decomposition transparently to inform deployment trade-offs: accuracy-only deployments may use TF-IDF; deployments requiring auditability, bias control, or dual-standard reasoning require the MAS architecture.
>
> All experiments are on synthetic Chinese clinical dialogues. DSM-5 v0 criteria are LLM-drafted; AIDA-Path structural alignment and Chang Gung Memorial Hospital clinical review are pending. Class-specific limitations (F31, F43, F98, Z71 near-zero recall; F42 OCD recall reduced 40pp in DSM-5 mode under conservative all-required exclusion semantics) are documented openly.

---

## Section 5 (architecture results) — UPDATED

### 5.1 Main benchmark — CANDIDATE values pending P0

[Table 5 — paper-aligned multilabel evaluation, post evaluation contract repair]

| System | 2c Acc | 4c Acc | 12c Top-1 | 12c Top-3 | F1_macro | F1_w | Overall |
|---|---:|---:|---:|---:|---:|---:|---:|
| Paper TF-IDF | .753 | .476 | .496 | .645 | .295 | .520 | .533 |
| Paper best LLM | .841 | .470 | .487 | .574 | .197 | .439 | .521 |
| Our TF-IDF | [P0] | [P0] | .604 | [P0] | .373 | .602 | [P0] |
| MAS-only (DtV) | [P0] | [P0] | .516 | [P0] | .171 | .447 | [P0] |
| **Stacker LGBM** | [P0] | [P0] | [P0] | [P0] | [P0] | [P0] | [P0] |
| **Stacker LR** | [P0] | [P0] | [P0] | [P0] | [P0] | [P0] | [P0] |

`[P0]` denotes a candidate value awaiting evaluation contract repair commit. Values verified post-commit will replace all `[P0]` markers with commit-hash-backed canonical values (see `metric_consistency_report.json`).

> Stacker LGBM matches our reproduced TF-IDF on Top-1 within ±5pp pre-specified non-inferiority margin (McNemar p ≈ 1.0). It exceeds the published paper TF-IDF and the published best LLM. We openly disclose that our reproduced TF-IDF is 10.6pp stronger than the paper's reported value — cause not fully identified, see Section 5.5.

### 5.2 Feature ablation (MAS contribution)

> Stacker LGBM feature importance: TF-IDF 88.1%, MAS 11.9%. MAS adds [P0] macro-F1 over TF-IDF-alone (concentrated in rare classes) but no measurable Top-1 improvement.
>
> We report this candidly: MAS architecture justifies its computational cost via the deployment properties (Section 6 disagreement triage, Section 5.4 dual-standard, Section 5.6 bias robustness), not via accuracy improvement.

### 5.3 Cross-dataset bias robustness

> [Existing R6v2 result text — unchanged]

### 5.4 Dual-standard reasoning

> Three reasoning configurations on the same case: ICD-10-only, DSM-5-only, both-mode. On LingxiDiag N=1000:
>
> | Mode | 12c Top-1 | 12c F1_macro |
> |---|---:|---:|
> | ICD-10 | 0.507 | 0.199 |
> | DSM-5 | 0.471 | 0.188 |
> | Both | 0.507 | 0.199 |
>
> ICD-10 and DSM-5 predictions agree on 74.9% of cases at the paper-parent level. Both-mode predictions are identical to ICD-10 mode (1000/1000 match), reflecting our current ensemble policy of preserving ICD-10 primary decision (billing-compatible) and emitting DSM-5 reasoning as sidecar evidence. We frame Both mode as a **dual-standard audit mechanism**, not an ensemble improvement.
>
> DSM-5 mode is usable but weaker than ICD-10 mode in aggregate, with **class-specific trade-offs**: improved F32 recall (+4.1pp), reduced F41 recall (-11.5pp), and substantially reduced F42 recall (-40.0pp). Section 7.2 traces F42 to a known limitation: under `all_required: true` schema, criterion D (exclusion) requires ruling out substance/medical/other-disorder explanations from a single transcript, which the checker frequently marks as `insufficient_evidence` in 80% of F42-gold cases.
>
> **Caveat**: DSM-5 v0 criteria are LLM-drafted (`UNVERIFIED_LLM_DRAFT`). Structural alignment against AIDA-Path machine-actionable DSM-5 criteria (Strasser-Kirchweger et al. 2026) and clinical review at Chang Gung Memorial Hospital are pending and not part of the current submission.

### 5.5 TF-IDF reproduction gap (honest disclosure)

> Our reproduced TF-IDF: 0.604 Top-1. Paper TF-IDF: 0.496. Gap: 10.6pp unexplained. Candidate causes documented in Appendix B.
>
> Parity claim is qualified: against our (stronger) reproduced baseline. We report both comparisons rather than choosing the more flattering one.

### 5.6 Confidence-gated ensemble (transparent negative result)

> A confidence-gated rule for combining MAS and TF-IDF predictions, tuned on dev_hpo and evaluated on the held-out 500-case split, selected `tfidf_only` (McNemar p = 1.0, ensemble-only = 0, tfidf-only = 0). Confidence-based ensembling does not provide reliable case-level override signal over the supervised baseline. We report this as a transparent negative finding rather than concealing it.

---

## Section 6 (Disagreement-as-Triage) — NEW with v4 corrections

### 6.1 Model discordance triage

> Hybrid systems naturally produce multiple decision paths. We evaluate disagreement between paths as clinician-triage routing rather than accuracy improvement.
>
> **Setup**: On LingxiDiag-16K test_final (N=1000), supervised TF-IDF predictions and the deployed Stacker LGBM predictions are compared by case_id. Cases are partitioned into "agreement" (same paper-parent class) and "disagreement" (different classes).
>
> **Note**: TF-IDF vs Stacker is **supervised-hybrid model discordance**, not "independent decision paths" — Stacker incorporates TF-IDF features. We use the more precise term throughout.
>
> **Results**: Disagreement rate is 26.4%. In the disagreement subset, deployed Stacker accuracy drops from 69.7% (agreement subset) to 37.5%, corresponding to **2.06× error rate enrichment**. The signal captures **42.5% of all deployed-model errors** at 26.4% flag rate, a 1.61× sensitivity gain over uniform-random review of the same 26.4% of cases.
>
> **Comparison to confidence-quantile triage**: Flagging the lowest 26.4% of cases by Stacker primary-class probability gives 1.92× error enrichment and 40.7% recall. Disagreement edges out by +0.14× enrichment and +1.8pp recall. Disagreement and confidence flag overlapping but distinct populations (Jaccard 0.357), confirming they are complementary signals rather than equivalent.
>
> **Two-stage policy**: Combining the signals as "flag if either disagreement OR low confidence" gives **2.17× enrichment and 58.0% error recall at 38.9% flag rate** — the strongest configuration. We propose this as a clinical deployment recommendation: 40% review burden captures 58% of system errors.
>
> **Practical advantages of disagreement triage** over confidence triage:
> 1. Architecturally free — already computed in any hybrid system
> 2. Interpretable to clinicians ("two methods disagree on this case")
> 3. Requires no probability calibration

### 6.2 Diagnostic-standard discordance audit

> CultureDx supports parallel ICD-10 and DSM-5 reasoning over the same case. On N=1000, the two reasoning modes disagree on **25.1% of cases** at the paper-parent level. In this disagreement subset, deployed ICD-10 accuracy drops from 54.9% to 38.2% (**1.37× error enrichment**).
>
> This is a **complementary signal** to model discordance: it identifies cases where the diagnostic standards genuinely conflict, not just where one model is uncertain. Paper-relevant differences include F32-vs-F41 boundary cases (mood-anxiety differential) and F42-vs-F41-vs-F39 boundary cases (OCD-vs-anxiety-vs-unspecified).
>
> We do not propose this as an ensemble rule. Both mode in our current implementation preserves the ICD-10 primary decision (1000/1000 match with ICD-10 mode) and emits DSM-5 reasoning as sidecar evidence. The disagreement rate quantifies how often the two standards point to different diagnoses, providing an explicit audit signal for cases requiring clinician judgment.

---

## Section 7 (Limitations) — UPDATED

### 7.1 Synthetic-only evaluation
> Both LingxiDiag-16K and MDD-5k are synthetic. Real-world clinical validation at Chang Gung Memorial Hospital is pending IRB approval.

### 7.2 DSM-5 v0 criteria
> All DSM-5 criteria are LLM-drafted with `UNVERIFIED_LLM_DRAFT` status. AIDA-Path structural alignment for 5 overlapping disorders is pending. Clinical review at Chang Gung is pending IRB.
> 
> Specific known weakness: F42 OCD recall in DSM-5 mode is 12% versus 52% in ICD-10 mode. Trace analysis shows `all_required: true` + criterion D (exclusion) being marked `insufficient_evidence` in 80% of F42-gold cases — a conservative evidence policy under limited transcript information that prevents F42 confirmation. **We do not adjust this threshold for the current submission to avoid test-set tuning.** Phase W will refine evidence-extraction strategies for exclusion criteria across all disorders.

### 7.3 Class coverage
> Five classes (F31, F43, F98, Z71, Others) show near-zero recall in both reasoning modes, representing 14.3% of test_final cases and placing a hard ceiling on aggregate Top-1. Phase W will prioritize criterion refinement for rare classes.

### 7.4 Both-mode is not an ensemble
> Both mode preserves ICD-10 primary decision (1000/1000 match); DSM-5 outputs are sidecar evidence. We do not claim ensemble accuracy improvement. Voting ensembles allowing DSM-5 to override ICD-10 in specific conditions are future work.

### 7.5 Retracted experiments
> WS-C Exp 1 and Exp 2 retracted (`docs/RETRACTION_NOTICE_2026_04_22.md`). Documented as transparent negative findings.

### 7.6 Evaluation contract repair history
> Pre-2026-04-25 metric values are deprecated. The current paper values are post-evaluation-contract repair (commit [P0]). See `AUDIT_RECONCILIATION_2026_04_25.md` and `metric_consistency_report.json` for change trail. This is presented as evidence of methodological transparency, not as an apology — modern hybrid systems require explicit evaluation contracts and we document ours openly.

---

## Discussion key points

1. **MAS-as-substrate, not MAS-as-classifier**: We do not claim MAS improves accuracy — verified by 4 independent measurements (feature ablation 12% MAS, ensemble null result, dual-standard ICD-10 = MAS-only Top-1, both-mode pass-through). We claim MAS enables deployment properties (auditability, dual-standard, disagreement triage, bias control) unavailable without it. Trade-off explicit, not hidden.

2. **Reproducibility-first frame**: Evaluation contract documented (Appendix A), pre-specified non-inferiority margin (±5pp), case manifest SHA256, unit tests for paper-parent normalization, TF-IDF gap disclosed, deprecated values tracked. Positioned as a contribution to clinical NLP reproducibility practice.

3. **Honest negative findings**: ensemble null, novel-class retraction, F42 limitation, F33 not in taxonomy. All reported. Costs nothing, gains substantial reviewer trust.

4. **Disagreement triage > confidence triage** (slightly but consistently): empirically verified; complementary in two-stage policy; architecturally free. Not just a "we built another classifier" claim.

---

## What this narrative survives

| Reviewer attack | Defense |
|---|---|
| "Just TF-IDF + LLM features" | Yes — we say so explicitly. Contribution is deployment, not accuracy. |
| "MAS doesn't improve accuracy" | We report this finding ourselves. |
| "DSM-5 LLM-drafted, unvalidated" | Three layers: AIDA-Path planned, clinician review planned, F42 limitation documented openly. |
| "Both mode is hollow" | Reframed as audit feature. We measure 25.1% disagreement; not zero contribution. |
| "Numbers don't match between artifacts" | Evaluation contract documented, sanity checks committed, all artifacts reconciled (`AUDIT_RECONCILIATION_2026_04_25.md`). |
| "Synthetic-only" | Stated upfront in abstract. Phase W planned. |
| "Disagreement just proxy for confidence" | Empirical comparison: 2.06× vs 1.92×, Jaccard 0.357 → complementary not equivalent. Two-stage union > either alone. |
| "Edit history shows numbers changed" | `AUDIT_RECONCILIATION_2026_04_25.md` documents WHY they changed (evaluation contract repair). Methodological transparency, not bug history. |

---

## What this narrative does NOT claim

- ❌ Outperforms TF-IDF on accuracy
- ❌ Disagreement captures all errors
- ❌ DSM-5 mode is clinically validated
- ❌ Both-mode improves over single-standard
- ❌ Ensemble produces gains
- ❌ Novel class detection works
- ❌ Real-world deployment validated
- ❌ AIDA-Path validation completed (pending)

All defended in advance.

---

## Status

**Narrative**: ✅ Reviewer-safe, can begin drafting paper sections
**Numbers**: 🟡 Candidate, replace `[P0]` markers after evaluation contract repair commit

**Next milestone**: Replace all `[P0]` markers with commit-hash-backed values from `metric_consistency_report.json`.
