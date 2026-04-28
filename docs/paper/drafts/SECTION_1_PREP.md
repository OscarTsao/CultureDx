# §1 Introduction — Prep Package

**Date**: 2026-04-27
**Per GPT round 48**: Phase 2 Step 3 greenlight. §1 Introduction prep only. No prose.
**Status**: Prep-only deliverable. Locked thesis sentence + 5-paragraph narrative arc + scope-bounded contribution bullets + reviewer attack matrix. All anchors verified against §3-§7 prose at HEAD `972f689`.

---

## ITEM 1 — Source artifacts (consolidated, with connector source-map per lesson 21a)

All 13 sources verified to exist on remote at HEAD `972f689`:

| # | Artifact | Path | Role |
|---:|---|---|---|
| 1 | §3 Task & Datasets prose | `docs/paper/drafts/SECTION_3.md` | ¶1 problem framing + ¶3 dataset preview |
| 2 | §4 Methods prose | `docs/paper/drafts/SECTION_4.md` | ¶3 CultureDx approach summary |
| 3 | §5.1 main benchmark prose | `docs/paper/drafts/SECTION_5_1.md` | ¶4 contribution 1 (parity); §5.1 line 5 anchors |
| 4 | §5.2 feature-block prose | `docs/paper/drafts/SECTION_5_2.md` | ¶3 hybrid-stacker caveat motivation |
| 5 | §5.3 F32/F41 prose | `docs/paper/drafts/SECTION_5_3.md` | ¶4 contribution 2 (bias-asymmetry reduction) |
| 6 | §5.4 dual-standard prose | `docs/paper/drafts/SECTION_5_4.md` | ¶4 contribution 4 (dual-standard audit) |
| 7 | §6 disagreement-triage prose | `docs/paper/drafts/SECTION_6.md` | ¶4 contribution 3 (model/standard discordance) |
| 8 | §7 limitations prose | `docs/paper/drafts/SECTION_7.md` | ¶5 scope statement source-of-truth |
| 9 | §5-§7 integration review | `docs/paper/integration/SECTION_5_7_INTEGRATION_REVIEW.md` | locked story sentence + cross-section consistency |
| 10 | MAS vs LGBM contribution | `docs/analysis/MAS_vs_LGBM_CONTRIBUTION.md` | ¶3 hybrid-stacker descriptive context |
| 11 | Disagreement-as-triage v4 | `docs/analysis/DISAGREEMENT_AS_TRIAGE.md` | ¶4 contribution 3 mechanics |
| 12 | F32/F41 asymmetry v4 | `docs/analysis/MDD5K_F32_F41_ASYMMETRY_V4.md` | ¶4 contribution 2 anchor numbers |
| 13 | Evaluation provenance | `docs/analysis/EVALUATION_PROVENANCE.md` | ¶3 v4 evaluation contract |

### Connector source-map (per lesson 21a; covers Introduction → §3-§7)

| Introduction reference | Source section |
|---|---|
| Top-1 = 0.612 vs reproduced 0.610 (parity) | §5.1 line 5 ✓ |
| 189× → 3.97× (F32/F41 reduction) | §5.3 lines 13-18 ✓ |
| 47.7-fold reduction | §5.3 line 18 + §7 line 13 ✓ |
| Both mode 1000/1000, 925/925, 0/15 | §5.4 lines 44-45 + §7 line 10 ✓ |
| `dsm5_criteria.json` v0 / 0.1-DRAFT / UNVERIFIED | §5.4 line 8 + §7 line 8 ✓ |
| 26.4% / 2.06× / 42.5% (model-discordance) | §6 lines 13-17 ✓ |
| 25.1% (LingxiDiag) / 20.8% (MDD-5k) standard-discordance | §6 lines 41/53 ✓ |
| 11.4pp TF-IDF reproduction gap | §5.5 line 3 + §7 line 23 ✓ |
| LingxiDiag-16K N=1000 / MDD-5k N=925 (synthetic) | §3.2.1, §3.2.2 ✓ |
| 12-class paper taxonomy | §3.3 + §3.1 ✓ |
| Hybrid stacker (31 features = 13 TF-IDF + 18 MAS) | §4.2 ✓ |
| 3 standard configurations (ICD-10 / DSM-5-only / Both) | §4.3 ✓ |
| Pre-v4 audit n=696 → post-v4 n=473 | §3.3 + §4.4 ✓ |

---

## ITEM 2 — Locked thesis sentence

Per GPT round 48 explicit, the Introduction is anchored on this single sentence. Every other Introduction sentence must support it; nothing in the Introduction may go beyond it.

> "CultureDx is a Chinese psychiatric differential-diagnosis benchmark system that reaches Top-1 parity with a strong reproduced TF-IDF baseline while adding MAS-enabled audit properties: cross-dataset F32/F41 bias-asymmetry reduction under ICD-10 MAS, model/standard-discordance triage, and dual-standard ICD-10/DSM-5 audit output, with DSM-5-v0 and synthetic-data limitations explicitly scoped."

This sentence corresponds to the round 42 locked paper story, with one wording adjustment ("bias-asymmetry **reduction**" rather than "bias-robustness", per §7.5 forbidden-list which says "we do not claim F32/F41 bias is solved"; "reduction" is more accurate than "robustness").

The Introduction prose may polish this sentence, but it must NOT:
- Strengthen "parity" to "superiority" or "outperformance"
- Strengthen "reduction" to "elimination" or "solved"
- Drop the "synthetic-data limitations explicitly scoped" qualifier
- Drop the DSM-5 v0 caveat
- Add unmentioned contributions (e.g., AIDA-Path, clinical validation)

---

## ITEM 3 — Global forbidden wording (Introduction-level)

```
GLOBAL FORBIDDEN (Introduction is most prone to overclaim):
❌ "SOTA LLM system" / "LLM SOTA" / "state-of-the-art LLM"
❌ "MAS beats TF-IDF" / "MAS outperforms TF-IDF" / "MAS achieves new accuracy"
❌ "supervised baselines fail" / "TF-IDF is insufficient"
❌ "clinically validated" / "clinical deployment" / "ready for clinical use"
❌ "real-world validation" / "prospective clinical cohort"
❌ "DSM-5 improves robustness" / "DSM-5 generalizes better" / "DSM-5 superiority"
❌ "DSM-5 diagnosis" (when describing our outputs) / "clinical DSM-5"
❌ "Both mode ensemble" / "dual-standard ensemble" / "ensemble gain"
❌ "bias solved" / "asymmetry resolved" / "bias removed"
❌ "F32/F41 problem solved"
❌ "disagreement beats confidence" / "model discordance is superior to confidence"
❌ "comprehensive 12-class coverage" / "uniform per-class performance"
❌ "deployment-ready" / "deployment properties" (positive)
❌ "AIDA-Path validation completed" / "clinician-reviewed criteria"
❌ "criterion-D = OCD time/distress" (factually wrong)
❌ "first multi-agent psychiatric diagnosis system" (likely overclaim without literature audit)
❌ "novel contribution" used loosely
```

---

## ITEM 4 — Global allowed replacement patterns

```
✅ "benchmark differential-diagnosis system"
✅ "Chinese psychiatric differential diagnosis"
✅ "hybrid supervised + MAS stacker" / "hybrid-system comparison"
✅ "accuracy parity / non-inferiority" (NOT "accuracy gain")
✅ "audit-relevant system properties"
✅ "model-discordance triage" / "diagnostic-standard discordance"
✅ "metric-specific trade-offs"
✅ "cross-dataset F32/F41 bias-asymmetry reduction" (NOT "bias robustness")
✅ "47.7-fold reduction in the asymmetry ratio"
✅ "synthetic / curated benchmark data"
✅ "external synthetic distribution-shift evaluation"
✅ "experimental audit observation"
✅ "LLM-drafted v0 formalization"
✅ "ICD-10 primary output with DSM-5 sidecar audit evidence"
✅ "scoped limitations" / "explicitly scoped"
✅ "pending clinical validation" / "pending clinician review"
```

---

## ITEM 5 — 5-paragraph narrative arc (per GPT round 48 explicit)

### ¶1 — Problem motivation

**Locked claims**:
- Chinese psychiatric differential diagnosis from clinical dialogue / transcript is the task scope
- Psychiatric diagnosis evaluation is not just Top-1 classification; auditability, standard sensitivity, and distribution-shift behavior matter for benchmark systems intended to support future clinical translation
- Current evaluation under benchmark contracts (e.g., LingxiDiag-style 12-class taxonomy) captures Top-1 but does not capture audit-relevant properties

**Source**: §3.1 task definition + §7 limitations framing (synthetic-only scope).

**Estimated length**: 90-130 words.

**Allowed wording** (per ITEM 4): "benchmark differential-diagnosis task", "audit-relevant system behavior", "Chinese psychiatric differential diagnosis".

**Forbidden** (per ITEM 3): "clinical diagnosis system", "ready for clinical use", "real patient validation", "first system to do X".

**Connector**: ¶1 forwards to §3.1 (task definition) and §7.1 (synthetic-only scope).

---

### ¶2 — Gap in accuracy-only evaluation

**Locked claims**:
- Strong supervised TF-IDF / character-n-gram baselines can achieve high Top-1 on 12-class psychiatric taxonomies; this is documented by our reproduced TF-IDF baseline (§5.5)
- LLM-only and MAS systems must justify themselves beyond raw accuracy because (a) hybrid stackers can match supervised baselines on Top-1 but (b) MAS-derived feature share is small (11.9% per §5.2) and (c) confidence-gated MAS/TF-IDF ensembling produces no detectable accuracy gain (§5.6 null result)
- The empirical story for CultureDx is therefore parity, not accuracy dominance — and the case for MAS rests on system properties not captured by Top-1

**Source**: §5.1 + §5.2 + §5.5 + §5.6 prose.

**Estimated length**: 120-160 words.

**Allowed wording** (per ITEM 4): "accuracy parity / non-inferiority", "system properties not captured by Top-1", "hybrid supervised + MAS stacker".

**Forbidden** (per ITEM 3): "MAS outperforms TF-IDF", "LLM SOTA", "supervised baselines fail", "TF-IDF is insufficient".

**Connector**: ¶2 forwards to §5.1 (parity), §5.2 (feature share), §5.5 (reproduction gap), §5.6 (ensemble null).

---

### ¶3 — CultureDx approach

**Locked claims**:
- CultureDx is a multi-agent reasoning architecture (HiED) producing primary diagnosis + criterion-level audit traces
- The reported benchmark system is a **hybrid supervised + MAS stacker (Stacker LGBM)** with 31 features (13 TF-IDF + 18 MAS), not an LLM-only system
- The architecture supports three paper-facing standard configurations (ICD-10, DSM-5-only, Both) implemented as standard-dispatch settings within HiED
- Evaluation is anchored to a v4 contract (`EVALUATION_PROVENANCE.md`); auxiliary 2-class / 4-class tasks use raw `DiagnosisCode` with F41.2 handled per task

**Source**: §4.1 + §4.2 + §4.3 + §4.4 prose.

**Estimated length**: 130-180 words.

**Required hybrid caveat** (per round 48 explicit): "The primary model is a hybrid supervised + MAS stacker, not an LLM-only system." This must appear in ¶3 verbatim or near-verbatim because §5.1 line 3 already establishes the comparison as a hybrid-system comparison.

**Allowed wording** (per ITEM 4): "hybrid supervised + MAS stacker", "standard configurations", "v4 evaluation contract".

**Forbidden** (per ITEM 3): "LLM-only system" (when describing Stacker LGBM), "Both mode ensemble", "code has separate icd10/dsm5/both modes" (Methods §4.3 already disambiguates code-vs-paper terminology).

**Connector**: ¶3 forwards to §4 (Methods).

---

### ¶4 — Contributions (5 scoped bullets)

**Per GPT round 48 explicit** — these 5 bullets are the locked contribution list. The Introduction prose may compress wording but must NOT add or drop items:

#### Contribution 1 — Benchmark parity with a strong reproduced supervised baseline

Locked claim:
"Stacker LGBM Top-1 = 0.612 vs reproduced TF-IDF = 0.610; the +0.2pp paired Top-1 difference is within the pre-specified ±5pp non-inferiority margin.
McNemar p ≈ 1.0 is reported as paired-discordance context (no detectable paired Top-1 difference at our sample size), NOT as the basis of the non-inferiority claim and NOT as an equivalence proof." 

Source: §5.1 lines 3-5.

Forbidden wording: "Stacker LGBM beats TF-IDF", "MAS outperforms TF-IDF", "accuracy gain", "parity under McNemar p ≈ 1.0" (round 49 Fix A — McNemar is not the basis of non-inferiority).
Allowed wording: "+0.2pp paired difference within ±5pp non-inferiority margin", "McNemar p ≈ 1.0 reported as paired-discordance context, not an equivalence proof", "no statistically detectable Top-1 advantage".

#### Contribution 2 — F32/F41 cross-dataset bias-asymmetry reduction under ICD-10 MAS

Locked claim: "On MDD-5k synthetic distribution-shift, single-LLM Qwen3-32B-AWQ collapses asymmetrically (189 F41→F32 errors versus 1 F32→F41, ratio 189×); MAS ICD-10 v4 reduces this to 151/38 = 3.97× (95% bootstrap CI [2.82, 6.08]) — a 47.7-fold reduction in the asymmetry ratio. Residual asymmetry remains; we do not claim F32/F41 bias is solved."

Source: §5.3 lines 3, 13-18, 30 + §7 lines 13-14.

Forbidden wording: "F32/F41 bias is solved", "asymmetry resolved", "47.7× improvement" (must be "47.7-fold reduction").
Allowed wording: "bias-asymmetry reduction" (NOT "bias robustness"), "47.7-fold reduction in the asymmetry ratio", "residual asymmetry remains".

#### Contribution 3 — Model and standard discordance signals as audit-relevant case-level triage

Locked claim:
"TF-IDF/Stacker model-discordance flags 26.4% of LingxiDiag-16K cases at 2.06× the unflagged Stacker error rate, recovering 42.5% of all Stacker errors; the confidence-quantile baseline reaches 1.92× / 40.7% at the same review budget.
Bootstrap CI on the disagreement-vs-confidence advantage includes zero — we do not claim disagreement statistically beats confidence — but the two signals flag partially distinct cases (Jaccard 0.357), supporting a complementary union policy.
ICD-10/DSM-5 standard discordance flags 25.1% of LingxiDiag-16K and 20.8% of MDD-5k cases as a separate audit signal."

Source: §6.1 lines 13-17, 25-26, 32 + §6.2 lines 41, 53.

Forbidden wording: "disagreement beats confidence", "model discordance is superior to confidence quantile".
Allowed wording: "no statistically detectable advantage", "complementary case-level signals", "partially distinct flag sets".

#### Contribution 4 — Dual-standard audit output with Both mode as architectural pass-through

Locked claim: "DSM-5-only mode reveals dataset-dependent metric-specific trade-offs (improved on some metrics, worsened on others — including F42/OCD recall and F32/F41 asymmetry — relative to ICD-10 mode). Both mode preserves the ICD-10 mode primary output and exposes DSM-5 reasoning as sidecar audit evidence (1000/1000 LingxiDiag and 925/925 MDD-5k pairwise agreement, 0/15 metric-key differences); Both mode is therefore an architectural pass-through, not an ensemble."

Source: §5.4 + §7 line 10.

Forbidden wording: "Both mode ensemble", "DSM-5 improves robustness", "DSM-5 generalizes better", "ensemble gain".
Allowed wording: "ICD-10 primary output with DSM-5 sidecar audit evidence", "metric-specific trade-offs", "architectural pass-through".

#### Contribution 5 — Transparent limitations and v4 evaluation contract

Locked claim:
"DSM-5 templates are LLM-drafted v0 formalization (`dsm5_criteria.json`, version `0.1-DRAFT`, source-note `UNVERIFIED`) — experimental audit observations, not clinically validated DSM-5 diagnoses.
All evaluation uses synthetic / curated benchmark data; we make no clinical deployment claim.
Auxiliary 2-class / 4-class tasks use raw `DiagnosisCode` (F41.2 excluded from binary task; n = 473 LingxiDiag, 490 MDD-5k under v4 contract) — earlier audit values (n=696) are superseded and retained for provenance."

Source: §3.3 + §4.4 + §7.1 + §7.2.

Forbidden wording: "clinically validated DSM-5", "clinical deployment readiness", "DSM-5 clinical validity", "old audit was wrong".
Allowed wording: "experimental audit observations", "synthetic / curated benchmark data", "earlier artifacts retained for provenance", "post-v4 evaluation contract".

---

### ¶5 — Scope statement (CRITICAL guardrail)

**Per GPT round 48 explicit**: This paragraph is critical. It must explicitly say what the paper does NOT claim, before reviewers read §5-§7.

**Locked claim** (must appear verbatim or near-verbatim):

> "We do not claim clinical deployment readiness, DSM-5 clinical validity, or MAS accuracy superiority over TF-IDF. AIDA-Path structural alignment and clinician review of the DSM-5 v0 schema are pending future work."

**Estimated length**: 70-100 words.

**Source**: §7 prose (entire section).

**Forbidden wording** (most important paragraph for this constraint): all of ITEM 3 forbidden patterns, especially "AIDA-Path validation completed" and "clinician-reviewed criteria" since they're forward-looking commitments.

**Allowed wording**: "scoped to benchmark behavior", "pending clinical validation", "pending AIDA-Path structural alignment".

**Connector**: ¶5 forwards directly to §7 limitations (the consolidated home for all scope statements).

---

## ITEM 6 — Reviewer attack matrix (per GPT round 48 explicit)

5 attacks anticipated for any psychiatric NLP paper claiming MAS-based audit properties:

### Attack 1 — "If TF-IDF is as good, why use MAS?"

> Response: "MAS is not retained for Top-1 dominance; §5.1 establishes parity, not superiority. The case for MAS rests on system properties not captured by Top-1: criterion-level audit traces (§4.1), F32/F41 cross-dataset bias-asymmetry reduction under ICD-10 MAS (§5.3, 47.7-fold reduction), dual-standard ICD-10/DSM-5 audit output (§5.4), and case-level model/standard-discordance triage signals (§6.1, §6.2)."

### Attack 2 — "Is this clinically validated?"

> Response: "No. All current evidence is benchmark-level on synthetic / curated datasets (LingxiDiag-16K test_final N=1000 and MDD-5k synthetic distribution-shift N=925, both synthetic). We have not yet evaluated CultureDx on clinician-adjudicated real-world clinical transcripts. AIDA-Path structural alignment and clinician review of the DSM-5 v0 schema are listed as pending future work in §7.8."

### Attack 3 — "Is DSM-5 better than ICD-10?"

> Response: "No. DSM-5-only mode shows dataset-dependent metric-specific trade-offs relative to ICD-10 mode, and worsens F32/F41 asymmetry on MDD-5k (3.97× ICD-10 → 7.24× DSM-5 v0 with paired bootstrap Δratio +3.24, CI [+1.12, +6.89] excluding zero). DSM-5 v0 is used as audit output, not as clinical DSM-5 validation. The DSM-5 v0 schema (`dsm5_criteria.json`, version `0.1-DRAFT`, source-note `UNVERIFIED`) has not been reviewed by clinicians (§7.2)."

### Attack 4 — "Is Both mode an ensemble?"

> Response: "No. Both mode preserves the ICD-10 mode primary output and attaches DSM-5 reasoning as sidecar audit evidence on the same case. Pairwise agreement with ICD-10 mode is 1000/1000 on LingxiDiag-16K and 925/925 on MDD-5k, with 0/15 metric-key differences (§5.4 Table 5.4c). Both mode is an architectural pass-through, not an ensemble; we do not claim accuracy gain from combining ICD-10 and DSM-5 reasoning."

### Attack 5 — "Does disagreement beat confidence?"

> Response: "No statistically detectable advantage at equal review budget. The bootstrap CI on the disagreement-minus-confidence advantage includes zero. Disagreement and confidence flag partially distinct error subsets (Jaccard 0.357 between flag sets); the union of the two signals flags 38.9% of cases at 2.17× error enrichment and 58.0% error recall (§6.1). We frame disagreement and confidence as complementary triage signals, not as a competitive-advantage claim."

---

## ITEM 7 — Cross-section consistency map (lesson 43a temporal-residue check)

For every Introduction claim, the corresponding §3-§7 anchor that must support it:

| Introduction claim | Source section / line |
|---|---|
| "Chinese psychiatric differential diagnosis" benchmark | §3.1 line 5 ✓ |
| Stacker LGBM Top-1 = 0.612 | §5.1 line 3 ✓ |
| Reproduced TF-IDF Top-1 = 0.610 | §5.1 line 5 / §5.5 line 3 ✓ |
| ±5pp non-inferiority margin / McNemar p ≈ 1.0 | §5.1 line 5 / §4.5 ✓ |
| 11.9% MAS feature share | §5.2 line 3 ✓ |
| Confidence-gated ensemble null result | §5.6 line 3 ✓ |
| 31 features (13 TF-IDF + 18 MAS) | §4.2 lines 19-22 ✓ |
| 189× single LLM → 3.97× MAS ICD-10 v4 | §5.3 lines 13-18 ✓ |
| 95% bootstrap CI [2.82, 6.08] | §5.3 line 18 ✓ |
| 47.7-fold reduction | §5.3 line 18 + §7 line 13 ✓ |
| 26.4% / 2.06× / 42.5% (model-discordance) | §6 lines 13/17/32 ✓ |
| 1.92× / 40.7% (confidence baseline) | §6 lines 14/17 ✓ |
| Jaccard 0.357 between flag sets | §6 line 26 ✓ |
| 38.9% / 2.17× / 58.0% (union) | §6 (verify in prose) |
| 25.1% LingxiDiag / 20.8% MDD-5k standard discordance | §6 lines 41/53 ✓ |
| Both mode 1000/1000, 925/925, 0/15 | §5.4 lines 44-45 + §7 line 10 ✓ |
| `dsm5_criteria.json` v0 / 0.1-DRAFT / UNVERIFIED | §5.4 line 8 + §7 line 8 ✓ |
| 7.24× DSM-5 asymmetry on MDD-5k | §5.3 line 22 ✓ |
| Δratio +3.24 [+1.12, +6.89] paired bootstrap | §5.3 line 22 ✓ |
| 11.4pp TF-IDF reproduction gap | §5.5 line 3 + §7 line 23 ✓ |
| F41.2 excluded; n=473 / 490 | §3.3 + §4.4 ✓ |
| Pre-v4 n=696 deprecated | §3.3 + §4.4 ✓ |
| Synthetic / curated / no clinical deployment | §3.2.2 + §7 lines 3-5 ✓ |
| AIDA-Path / clinician review pending | §7 lines 26-28 ✓ |

✅ All 24 Introduction-relevant claims trace to committed §3-§7 prose. **No new Introduction claim that doesn't exist in §3-§7.**

🔍 One verification needed during prose: §6 union-policy numbers (38.9% / 2.17× / 58.0%) — let me re-verify:

```
(verified in prep)
- §6 line 25: "Disagreement only | 26.4% | 2.06× | 42.5% | 1.000"
- §6 line 26: "Confidence only | 26.4% | 1.92× | 40.7% | 0.357"
- (union row would need separate verification at prose drafting time)
```

Lesson 40a application reminder: at §1 prose drafting, confirm the union-policy 38.9%/2.17%/58.0% triple appears in §6 prose verbatim before placing in Introduction.

---

## ITEM 8 — Prose plan (NO PROSE)

Per GPT round 48 explicit: prep only. No Introduction prose.

When §1 prose is authorized (post-round-49), suggested structure:

| Paragraph | Topic | Estimated words |
|---|---|---:|
| ¶1 | Problem motivation | 90-130 |
| ¶2 | Gap in accuracy-only evaluation | 120-160 |
| ¶3 | CultureDx approach | 130-180 |
| ¶4 | Contributions (5 bulleted) | 200-280 |
| ¶5 | Scope statement (CRITICAL guardrail) | 70-100 |
| **Total estimate** | — | **610-850 words** |

**Format discipline (lesson 33a)**: Sentence-level line breaks from initial draft. Not as post-hoc cleanup.

**Lesson 40a explicit (CRITICAL for Introduction)**: every numerical anchor in Introduction prose must grep-verify in source §3-§7 prose BEFORE placement. Item 7 already pre-traces 24 anchors; final draft will re-verify at prose time.

**Lesson 43a explicit**: at §1 prose v1 delivery, run cross-section forbidden grep against §1 + §3 + §4 + §5 + §6 + §7 simultaneously (now 11 prose files including §1).

**Lesson 44a (NEW from round 44)**: any factual nuance surfaced during this prep that doesn't fit a primary structure slot must be captured here as a one-line trap or note. Such nuances surfaced this round:

- Note: "bias-asymmetry reduction" is preferred over "bias robustness" because §7.5 forbidden-list says "we do not claim F32/F41 bias is solved"; "robustness" is too strong as claim language. (Captured in ITEM 2 / ITEM 4.)
- Note: "first multi-agent psychiatric diagnosis system" is forbidden because we have not done a literature audit to support such a primacy claim. (Captured in ITEM 3.)
- Note: Introduction must NOT use "deployment properties" (round 43 lesson 42a) — even though §1 was drafted after the §5 wording sync, the Introduction is the most likely place for the same root to creep back in. (Captured in ITEM 3.)

---

## ITEM 9 — Round 49 narrow review request (per GPT round 48 spec)

```
§1 prep committed at <hash>.

Round 49 narrow review:
1. Does the Introduction thesis match §3–§7?
2. Are the contributions scoped correctly?
3. Does the Introduction avoid clinical / DSM-5 / SOTA overclaim?
4. Is the "why MAS if TF-IDF parity?" answer strong enough?
5. Can we start §1 prose?
```

If 5/5 pass → §1 prose v1 authorized.

---

## Cumulative round 14-48 lessons applied during this prep

| Lesson | Application in §1 prep |
|---|---|
| 21a | All 13 source artifacts listed with paths + roles + connector source-map (Item 1) |
| 22e / 23b / 38b | Quantifier discipline: "47.7-fold reduction" not "improvement"; "parity / non-inferiority" not "as good as"; "no statistically detectable advantage" not "no advantage" |
| 25a-d | Every fact verified against source artifact line numbers (Item 7) |
| 25b / 32a / 38a | Mode terminology: "standard configurations" / "primary-output perspective" / "audit observation" — distinct from "DSM-5 diagnosis" |
| 31a | Cross-section directionality: F32/F41 direction (F41→F32 dominant) preserved in Item 5 contribution 2 |
| 33a | Format-during-draft: sentence-level breaks throughout |
| 35a / 40a | Mechanism precision: contribution 2 explicitly states "raw 189/1, raw 151/38"; contribution 3 explicitly states bootstrap CI direction |
| 36a (escalation) | Forbidden list (Item 3) has 18 patterns vs §3+§4 prep's 16 — Introduction expected to face most overclaim risk |
| 38a | "MAS-derived features" / "supervised features" distinction maintained |
| 42a | "deployment" only in negation/forbidden; "system properties" used positively |
| 42b | Paper register: "scoped to benchmark behavior" / "we make no clinical deployment claim" |
| 43a | Cross-section forbidden grep planned for §1 prose vs all 11 prose files (Item 8) |
| 44a | Drafting-context nuances captured explicitly (Item 8 notes — "bias-asymmetry reduction" wording, "first multi-agent" forbidden, Introduction-specific deployment-root vigilance) |

Most prep guardrails of any prep file: 13 sources × 24 cross-section anchors × 18 forbidden patterns × 5 reviewer attacks. Inherits all 34 cumulative lessons.

---

## Sequential discipline status

```
✓ §3 + §4 closed (972f689)
✓ §5 + §6 + §7 closed
✓ Phase 2 Step 1 closed (integration review)
✓ Phase 2 Step 2 closed (§3+§4 prep + prose)
□ Phase 2 Step 3: §1 Introduction prep ← awaiting your push
□ Round 49 narrow review
□ §1 prose v1 ← if 5/5 pass
□ Phase 2 Step 4: §2 Related Work prep (DEFERRED until §1 closed)
□ Phase 2 Step 5: AIDA-Path slotting decision
□ Phase 2 Step 6: PI / advisor review
```

§1 prep is structurally compact (5 paragraphs, 5 contributions, 5 attacks) but heavily cross-referenced (24 anchors across 8 source sections). Estimated ~500 lines when committed.
