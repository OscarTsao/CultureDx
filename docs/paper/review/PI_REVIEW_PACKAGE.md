# PI / Advisor Review Package

**Date**: 2026-04-29
**Per GPT round 81 trigger**: Phase 2 Step 6 — PI / advisor review package. Review package, NOT prose.
**Artifact location**: `docs/paper/review/PI_REVIEW_PACKAGE.md`
**Status**: Self-contained review package summarizing the manuscript freeze at `paper-integration-v0.1`. NO §1-§7 prose modified. NO Abstract modified. NO new claims introduced.

---

## 1. Current branch / tag

| Item | Value |
|---|---|
| Branch | `main-v2.4-refactor` |
| Current HEAD commit | `c3b0a46` (docs(paper): normalize Section 5.2 and 5.6 line breaks) |
| Paper-integration freeze tag | `paper-integration-v0.1` (annotated `c7ba2b4` → commit `c3b0a46`) |
| Repository | github.com/OscarTsao/CultureDx |
| Recommended review-time checkout | `git checkout paper-integration-v0.1` |

### Phase 2 commit lineage (Step 5a → Step 5g + cleanup)

```
c3b0a46  docs(paper): normalize Section 5.2 and 5.6 line breaks            (line-break normalization)
0ca7625  docs(paper): sync reproduction guide final manuscript status      (Commit 2 from sweep §9)
63a7f73  docs(paper): final manuscript sweep                                (Step 5g, Commit 1)
ccadc20  docs(paper): draft structured abstract                            (Step 5f-apply v1.1)
273f78a  docs(paper): prepare abstract claim framing                       (Step 5f-prep v1.1)
38f9073  docs(paper): add reviewer-facing reproduction guide               (Step 5e)
57e4b02  docs(paper): record AIDA-Path slot decision                       (Step 5c, Path B)
2b17aa3  docs(paper): resolve remaining citation sources                   (Step 5b-mini)
d4992cc  docs(paper): apply citation pass and bibliography ledger          (Step 5b-apply)
bca33ce  docs(paper): citation pass plan for manuscript assembly           (Step 5b-plan)
eea8cf1  docs(paper): apply table-renumbering pass                         (Step 5d-apply)
3bdc4af  docs(paper): table numbering plan for manuscript assembly         (Step 5d-plan)
82bd2a4  docs(paper): full manuscript assembly review                      (Step 5a)
```

The `0f5d32a` v6.1 cleanup commit is also an ancestor of HEAD; v6.1 fixes (LingxiDiag metrics_summary sync / compute_table4 v4 contract / AUDIT_RECONCILIATION / EVALUATION_PROVENANCE [P0] / NARRATIVE_REFRAME [P0] / MDD-5k DSM-5 wording) are absorbed.

---

## 2. One-paragraph paper story

CultureDx is a Chinese psychiatric differential-diagnosis benchmark and audit system that reaches Top-1 parity (0.612 vs reproduced TF-IDF 0.610) within a ±5 percentage-point non-inferiority margin defined in the post-v4 evaluation contract, while adding three audit-relevant system properties that Top-1 alone does not capture.
First, on MDD-5k synthetic distribution-shift, the F32/F41 error-asymmetry ratio decreases from 189× under a single-LLM baseline to 3.97× under MAS ICD-10, a 47.7-fold reduction (95% bootstrap CI [2.82, 6.08]).
Second, TF-IDF/Stacker model-discordance flags 26.4% of LingxiDiag cases at 2.06× error enrichment over unflagged cases, providing a case-level triage signal at equal review budget.
Third, dual-standard ICD-10 / DSM-5 v0 evaluation exposes standard-sensitive trade-offs while Both mode preserves the ICD-10 primary output with DSM-5 sidecar audit evidence as an architectural pass-through, not an ensemble.
All evidence is benchmark-level on synthetic or curated data, not clinical validation.
The DSM-5 v0 schema is LLM-drafted and unverified; AIDA-Path structural alignment and clinician review remain pending.
The paper's empirical posture is parity-plus-audit, not accuracy-superiority or clinical-deployment readiness.

---

## 3. Abstract

The Abstract lives at `docs/paper/drafts/ABSTRACT.md` (commit `ccadc20`, 22 lines / 239 words / Mode A JAMIA-style structured / 0 long lines). Reproduced verbatim below for review convenience.

---

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

---

### Abstract design properties

- Mode A — JAMIA / JAMIA Open structured, ≤ 250-word cap (verified: 239 words, 11-word margin).
- 5 standard subheadings: Objective / Materials and Methods / Results / Discussion / Conclusion.
- Mode-specific hero-number budget = 3 numerical groups (parity / asymmetry / triage); Both mode pass-through and limitations qualitative.
- Forbidden-claim sweep at HEAD `c3b0a46`: 0 positive uses; 6 hits in negation context (per `FINAL_MANUSCRIPT_SWEEP.md` §4).

If venue switches to npj Digital Medicine, an Mode B 150-word unstructured abstract would need separate drafting (NOT mechanical compression of Mode A). See `ABSTRACT_PREP.md` §1, §4 for mode-specific guidance.

---

## 4. Table / Box inventory

The final manuscript contains 1 box and 6 tables, locked at Step 5d-apply (commit `eea8cf1`). All references in §1-§7 prose and Abstract use the final labels listed below.

| # | Label | Title | Defining section / file | Role |
|---:|---|---|---|---|
| 1 | Table 1 | Datasets | §3.2 (`SECTION_3.md`) | LingxiDiag-16K + MDD-5k inventory + sample sizes |
| 2 | Box 1 | v4 evaluation contract | §4.4 (`SECTION_4.md`) | post-v4 raw-code-aware contract: 12-class paper-parent Top-1/Top-3, 2-class and 4-class slices, statistical procedures |
| 3 | Table 2 | Main benchmark | §5.1 (`SECTION_5_1.md`) | Stacker LGBM vs reproduced TF-IDF baseline + published baselines |
| 4 | Table 3 | F32/F41 cascade | §5.3 (`SECTION_5_3.md`) | MDD-5k asymmetry across pipeline states (single-LLM 189× → MAS ICD-10 v4 3.97×) |
| 5 | Table 4 (Panels A/B/C) | Dual-standard audit | §5.4 (`SECTION_5_4.md`) | Panel A: standard-conditional metrics; Panel B: F32/F41 by standard; Panel C: Both pass-through verification (1000/1000 + 925/925) |
| 6 | Table 5 | Model-discordance triage | §6.1 (`SECTION_6.md`) | TF-IDF/Stacker disagreement vs confidence baseline at 26.4% review budget; union policy 58.0% recall at 38.9% review burden |
| 7 | Table 6 | Standard-discordance | §6.2 (`SECTION_6.md`) | LingxiDiag 25.1% / MDD-5k 20.8% standard-discordance flagging |

Table-label discipline at HEAD `c3b0a46`: 0 old labels (5.4a / 5.4b / 5.4c / 6.1a / 6.1b / 6.2a) in §1-§7 prose. All 7 final labels verified canonical-defined per `FINAL_MANUSCRIPT_SWEEP.md` §5.

---

## 5. Main claims and supporting tables

The manuscript's empirical posture rests on five claims, each supported by a primary table or section. PI/advisor should read each claim alongside its supporting evidence.

### Claim 1 — Top-1 parity, NOT superiority

```
Claim:        Stacker LGBM Top-1 = 0.612 vs reproduced TF-IDF 0.610 supports
              parity within the ±5 pp non-inferiority margin defined in the
              post-v4 evaluation contract.
Source:       §5.1 (Table 2, Box 1)
Statistical:  McNemar p ≈ 1.0 is paired-discordance context, not equivalence
              proof; the ±5 pp margin is a structured non-inferiority claim,
              not a regulatory-grade prespecified margin.
Forbidden:    "MAS beats TF-IDF" / "SOTA LLM" / "TF-IDF is weak" all = 0
              positive uses in manuscript.
```

### Claim 2 — F32/F41 error-asymmetry reduction under cross-dataset shift

```
Claim:        On MDD-5k synthetic distribution-shift, single-LLM baseline
              shows 189 F41→F32 errors vs 1 F32→F41 (asymmetry 189×).
              MAS ICD-10 v4 reaches 151/38 = 3.97× (95% bootstrap CI
              [2.82, 6.08]), a 47.7-fold reduction.
Source:       §5.3 (Table 3 cascade)
Statistical:  Percentile bootstrap with N=2000 resamples on the v4 scope.
Caveat:       Each cascade row corresponds to a pipeline state; we do NOT
              attribute the change between adjacent rows to single repairs.
              The 3.97× residual remains; the claim is reduction, NOT
              elimination ("bias solved" = forbidden, 0 positive uses).
Switching to DSM-5 v0 increases asymmetry to 7.24× on MDD-5k; Δratio paired
bootstrap CI excludes 0 (see §5.3 line 28).
```

### Claim 3 — Model-discordance triage flags error-enriched cases at equal review budget

```
Claim:        TF-IDF/Stacker disagreement flags 26.4% of LingxiDiag cases at
              2.06× error enrichment over unflagged cases; recall = 42.5% of
              all Stacker errors.
Compared to:  Confidence-quantile baseline at same 26.4% budget reaches 1.92×
              enrichment, 40.7% recall.
Union policy: Disagreement OR low-confidence captures 58.0% of errors at
              38.9% review burden.
Source:       §6.1 (Table 5)
Forbidden:    "Disagreement beats confidence" = 0 positive uses; the two
              signals are reported as comparable but not ordered.
```

### Claim 4 — Dual-standard audit reveals standard-sensitive trade-offs; Both mode is architectural pass-through

```
Claim:        DSM-5 v0 mode shows dataset-dependent metric-specific trade-offs
              vs ICD-10 mode (Top-1 -3.6 pp / 4-class +2.9 pp on LingxiDiag;
              mixed direction on MDD-5k). F32/F41 asymmetry worsens under
              DSM-5 v0 on both datasets.
Both mode:    Pairwise-agreement with ICD-10 = 1000/1000 on LingxiDiag and
              925/925 on MDD-5k; 0 of 15 metric-keys differ. Both is an
              ICD-10 architectural pass-through with DSM-5 sidecar audit
              evidence, NOT an ensemble.
Source:       §5.4 (Table 4 Panels A/B/C)
Forbidden:    "DSM-5 superiority" / "DSM-5 generalizes better" / "Both mode
              ensemble" = 0 positive uses.
```

### Claim 5 — Standard-discordance triage on dual-standard predictions

```
Claim:        ICD-10/DSM-5 disagreement flags 25.1% of LingxiDiag cases and
              20.8% of MDD-5k cases as standard-sensitive. Flagged subset
              shows 1.83× enrichment / 32.4% recall under ICD-10 primary
              perspective and 2.06× / 35.1% under DSM-5 v0 primary.
Source:       §6.2 (Table 6)
Status:       This is a standard-sensitivity audit, NOT a "DSM-5 catches
              what ICD-10 misses" claim. DSM-5 v0 unverified caveat applies.
```

---

## 6. Clinical-scope caveats

The manuscript scopes its empirical evidence as follows. PI/advisor should review whether the level of disclosure matches the target venue's requirements.

### 6.1 Synthetic / curated benchmark setting

```
LingxiDiag-16K = synthetic / curated Chinese psychiatric clinical dialogues
                 (1000 test_final cases for v4 contract).
MDD-5k         = synthetic vignette / dialogue benchmark for cross-dataset
                 distribution-shift evaluation (925 cases for v4 contract).
```

Neither dataset is clinician-adjudicated real-world clinical transcripts. All evidence is benchmark-level. The manuscript explicitly states (§3 line 19; §7 line 4; Abstract Discussion):

> "Both datasets are synthetic or curated rather than clinician-adjudicated real-world clinical transcripts; benchmark-level results are not equivalent to clinical validation."

### 6.2 No clinical deployment claim

```
§1 line 28:  "We do not claim clinical deployment readiness, DSM-5 clinical
             validity, or MAS accuracy superiority over TF-IDF."
§3 line 8:   "we make no claim of clinical deployment readiness or
             prospective clinical validity."
§7 line 4:   "We do not claim clinical deployment readiness or prospective
             clinical validity."
Abstract:    "CultureDx supports a parity-plus-audit framing rather than an
             accuracy-superiority or clinical-deployment claim."
```

Per `FINAL_MANUSCRIPT_SWEEP.md` §4, all 6 forbidden-claim hits are in explicit-negation context. 0 positive uses.

### 6.3 Cross-cultural generalization scoping

The Chinese-language scoping is documented in §3 (Datasets) and §7 (Limitations). The benchmark does NOT make claims about:
- Generalization to non-Chinese psychiatric populations
- Generalization to non-Chinese-language clinical text
- Generalization across cultural / regional variations within Chinese-speaking contexts
- Generalization to spoken vs written Chinese text
- Generalization to traditional vs simplified Chinese script (LingxiDiag is simplified)

---

## 7. DSM-5 v0 / AIDA-Path status

Two scope-boundary decisions are explicitly locked in the manuscript and require PI/advisor review.

### 7.1 DSM-5 v0 schema status (UNVERIFIED)

```
Schema file:      src/culturedx/ontology/data/dsm5_criteria.json
Version tag:      0.1-DRAFT
Source-note:      UNVERIFIED
Provenance:       LLM-drafted, NOT clinician-reviewed
```

All DSM-5 outputs throughout the manuscript are framed as **experimental audit observations**, NOT clinically validated DSM-5 diagnoses (`SECTION_4.md` line 37; `SECTION_5_4.md` line 8; `SECTION_7.md` line 9; Abstract Discussion).

Open question for PI/advisor: is the current "experimental audit observation" framing sufficient, or should DSM-5 results be:
- (a) Removed from the paper entirely
- (b) Moved to an appendix with stronger caveats
- (c) Kept in §5.4 / §6.2 with current "v0 LLM-drafted unverified" framing
- (d) Held until clinician-reviewed v1 schema is available

The current default is (c). See PI question #2 below.

### 7.2 AIDA-Path Path B (decision locked at `57e4b02`)

The AIDA-Path slot decision is locked at `docs/paper/integration/AIDAPATH_SLOT_DECISION.md` (commit `57e4b02`) under **Path B** framing:

```
Path B = AIDA-Path structural alignment + clinician review remain pending.
         No AIDA-Path overlap result or clinician-reviewed criterion is
         presented as evidence in the present paper.
```

§7.8 lines 27-28 explicitly state:

> "AIDA-Path structural alignment between the v0 DSM-5 schema and the AIDA-Path digital-medicine ontology has been planned but not yet completed; the same applies to independent clinician review of the DSM-5 v0 schema (§7.2) and the F42 criterion-D exclusion handling (§7.6)."
>
> "We do not present any AIDA-Path overlap result or clinician-reviewed criterion as part of the present paper's evidence."

Path A (AIDA-Path overlap analysis as a contribution) is NOT pursued in the present paper. The 5 trigger conditions for switching to Path A are enumerated in `AIDAPATH_SLOT_DECISION.md`; until those conditions are met, the manuscript continues operating under Path B wording.

Open question for PI/advisor: is Path B acceptable for submission, or should AIDA-Path overlap analysis be completed before submission? See PI question #5 below.

### 7.3 F42 / OCD-related caveat

DSM-5 v0 degrades F42 / OCD recall in both datasets. Magnitude and slice details are documented in §7.6 with cross-reference to `docs/limitations/F42_DSM5_COLLAPSE_2026_04_25.md`. This is NOT presented as a primary result; it is a v0 schema limitation.

---

## 8. Reviewer-facing reproduction guide pointer

The reviewer-facing reproduction guide lives at `docs/paper/repro/REPRODUCTION_README.md` (commit `38f9073`, post-`0ca7625` pointer sync; 308 lines).

Recommended PI/advisor reading order:

```
1. Open paper-integration-v0.1 tag:        git checkout paper-integration-v0.1
2. Read docs/paper/repro/REPRODUCTION_README.md  (navigation document, NOT recompute manual)
3. Read docs/paper/drafts/ABSTRACT.md             (Mode A JAMIA-style, 239 words)
4. Read §1-§7 prose in numerical order
5. Cross-check Tables 1-6 + Box 1 in their defining sections
6. Optionally consult integration artifacts:
     - FULL_MANUSCRIPT_ASSEMBLY_REVIEW.md  (Step 5a cross-section consistency)
     - AIDAPATH_SLOT_DECISION.md            (Step 5c Path B)
     - FINAL_MANUSCRIPT_SWEEP.md           (Step 5g verification pass)
```

The reproduction README contains:
- Branch / commit pointers (post-`0ca7625` sync includes Reproduction-README + Abstract + manuscript-integration commits)
- Pointer table to canonical metric sources (NOT metric duplication)
- Pointers to 9 supporting integration artifacts
- Pointer to citation infrastructure (20-source ledger + BibTeX)
- Sequential discipline status (Phase 2 Step 5a → Step 5g all closed)

---

## 9. Specific questions for PI / advisor

These 6 questions are framed for direct PI/advisor response. Each maps to a specific scope-boundary or framing decision documented in the manuscript or integration artifacts.

### Q1 — Is the clinical-scope wording conservative enough?

```
Locations in manuscript:  §1 line 28  /  §3 line 8  /  §7 line 4  /  Abstract Discussion
Current wording:           "We do not claim clinical deployment readiness, DSM-5
                           clinical validity, or MAS accuracy superiority over TF-IDF."
Round 80 sweep verdict:    0 positive uses; 6 negation-context hits documented.
PI/advisor decision:       (a) sufficient; (b) strengthen further; (c) move clinical
                           scoping to a dedicated subsection
```

### Q2 — Is DSM-5 v0 framed correctly as unverified audit formalization?

```
Locations:                 §4.3  /  §5.4 line 8, 14  /  §7.2  /  Abstract Discussion
Current framing:           "experimental audit observations rather than clinically
                           validated DSM-5 diagnoses" (v0 LLM-drafted, source-note
                           UNVERIFIED)
PI/advisor decision:       (a) keep current "experimental audit" framing; (b) remove
                           DSM-5 results entirely; (c) move to appendix; (d) hold
                           submission until clinician-reviewed v1 schema is available
```

### Q3 — Is the synthetic / curated benchmark limitation strong enough?

```
Locations:                 §3 line 19  /  §7.1  /  Abstract Discussion
Current wording:           "Both datasets are synthetic or curated rather than
                           clinician-adjudicated real-world clinical transcripts;
                           benchmark-level results are not equivalent to clinical
                           validation."
PI/advisor decision:       (a) sufficient; (b) strengthen with explicit non-clinical-
                           adjudication caveat at every results-section header; (c)
                           rephrase "clinical validation" to "prospective clinical
                           evaluation" for stronger separation
```

### Q4 — Does the parity-plus-audit framing make sense clinically?

```
Locations:                 Abstract Conclusion  /  §1  /  §5.1  /  §7
Current framing:           Top-1 parity within ±5 pp NI margin + 3 audit properties
                           (F32/F41 asymmetry reduction, model-discordance triage,
                           dual-standard sidecar audit). NOT accuracy superiority.
PI/advisor decision:       (a) framing is clinically meaningful; (b) "audit
                           properties" needs a more clinically-grounded synonym
                           ("safety properties" / "review-supporting properties"
                           / "case-level reliability properties"); (c) re-order so
                           audit properties come before Top-1 parity in §1
```

### Q5 — Is AIDA-Path pending status acceptable for submission, or should overlap analysis be completed before submission?

```
Locations:                 §7.8  /  AIDAPATH_SLOT_DECISION.md  /  Abstract Discussion
Current decision:          Path B (structural alignment + clinician review remain
                           pending; no AIDA-Path overlap result presented as paper
                           evidence)
Path A trigger conditions: 5 conditions enumerated in AIDAPATH_SLOT_DECISION.md;
                           until met, Path B continues
PI/advisor decision:       (a) Path B acceptable for submission; (b) require
                           AIDA-Path overlap analysis as a §7.8.1 sub-result before
                           submission (would activate Path A drafting); (c) hold
                           submission until clinician review of v0 schema completes
```

### Q6 — Are there any claims that should be removed before external review?

```
Forbidden-claim sweep (FINAL_MANUSCRIPT_SWEEP.md §4): 0 positive uses across all
forbidden patterns:
  - "SOTA LLM" / "MAS beats TF-IDF"                                            0 ✓
  - "clinical deployment readiness"                                              0 positive (3 negation)
  - "clinically validated DSM-5"                                                 0 positive (3 negation)
  - "DSM-5 superiority" / "DSM-5 generalizes better" / "DSM-5 improves robustness" 0
  - "Both mode ensemble" / "dual-standard ensemble" / "bias solved"             0
  - "disagreement beats confidence"                                              0
  - "AIDA-Path validated" / "clinician-reviewed criteria"                       0

PI/advisor decision:       (a) no further removals needed; (b) flag specific
                           sentences for additional hedging; (c) flag claims that
                           overstate evidence for the target venue (please specify)
```

---

## 10. Manuscript-package contents inventory (for PI/advisor binding)

| Category | File | Lines | Role |
|---|---|---:|---|
| Abstract | `docs/paper/drafts/ABSTRACT.md` | 22 | Mode A JAMIA-style, 239 words |
| §1 Introduction | `docs/paper/drafts/SECTION_1.md` | 30 | Empirical posture + scope boundary |
| §2 Related Work | `docs/paper/drafts/SECTION_2.md` | 44 | Lit positioning |
| §3 Datasets | `docs/paper/drafts/SECTION_3.md` | 53 | Table 1 + synthetic/curated framing |
| §4 Method | `docs/paper/drafts/SECTION_4.md` | 75 | Box 1 + DSM-5 v0 unverified caveat |
| §5.1 Main benchmark | `docs/paper/drafts/SECTION_5_1.md` | 33 | Table 2 + Top-1 parity claim |
| §5.2 Feature ablation | `docs/paper/drafts/SECTION_5_2.md` | 7 | TF-IDF 88.1% / MAS 11.9% feature share |
| §5.3 F32/F41 cascade | `docs/paper/drafts/SECTION_5_3.md` | 36 | Table 3 + 189× → 3.97× claim |
| §5.4 Dual-standard | `docs/paper/drafts/SECTION_5_4.md` | 62 | Table 4 + Both pass-through |
| §5.5 TF-IDF reproduction gap | `docs/paper/drafts/SECTION_5_5.md` | 8 | 0.610 vs published 0.496 disclosure |
| §5.6 Confidence-gated null result | `docs/paper/drafts/SECTION_5_6.md` | 8 | Negative finding, retained |
| §6 Triage | `docs/paper/drafts/SECTION_6.md` | 63 | Tables 5, 6 + 26.4% / 2.06× claim |
| §7 Limitations | `docs/paper/drafts/SECTION_7.md` | 29 | Synthetic data + DSM-5 v0 + Path B |
| Reproduction guide | `docs/paper/repro/REPRODUCTION_README.md` | 308 | Reviewer-facing navigation |
| Citation ledger | `docs/paper/references/CITATION_LEDGER.md` | 279 | 20-source provenance ledger |
| BibTeX | `docs/paper/references/references.bib` | 314 | 20 verified BibTeX entries |
| Final sweep | `docs/paper/integration/FINAL_MANUSCRIPT_SWEEP.md` | 532 | Step 5g verification report |
| AIDA-Path decision | `docs/paper/integration/AIDAPATH_SLOT_DECISION.md` | (varies) | Path B + 5 Path A trigger conditions |
| Abstract prep | `docs/paper/integration/ABSTRACT_PREP.md` | 378 | Mode A/B/C claim-boundary v1.1 |
| Assembly review | `docs/paper/integration/FULL_MANUSCRIPT_ASSEMBLY_REVIEW.md` | (varies) | Step 5a cross-section consistency |

Total manuscript-facing surface for PI review: **13 prose files (Abstract + 12 §X.Y) + 1 reproduction guide + 2 references = 16 files**.

Total supporting integration artifacts: **6 integration files** (assembly review + table plan + citation plan + AIDA-Path decision + abstract prep + final sweep).

Total Phase 2 paper artifacts: **22** (16 manuscript-facing + 6 integration).

---

## 11. Sequential discipline status

```
✓ §1-§7 all closed (manuscript body complete)
✓ Phase 2 Step 5a: assembly review v1.1                              (82bd2a4)
✓ Phase 2 Step 5d-plan: table numbering plan v1.2                    (3bdc4af)
✓ Phase 2 Step 5d-apply: table-renumbering apply-pass v1.1           (eea8cf1)
✓ Phase 2 Step 5b-plan: citation pass plan v1.1                      (bca33ce)
✓ Phase 2 Step 5b-apply: citation apply-pass v1.2                    (d4992cc)
✓ Phase 2 Step 5b-mini: unresolved-source mini-pass v1.1             (2b17aa3)
✓ Phase 2 Step 5c: AIDA-Path slot decision (Path B)                  (57e4b02)
✓ Phase 2 Step 5e: reviewer-facing reproduction README v1.2          (38f9073)
✓ Phase 2 Step 5f-prep: abstract claim-boundary v1.1                 (273f78a)
✓ Phase 2 Step 5f-apply: structured abstract v1.1                    (ccadc20)
✓ Phase 2 Step 5g: final manuscript sweep                            (63a7f73)
✓ Phase 2 Commit 2: reproduction README pointer sync                 (0ca7625)
✓ Phase 2 §5.2/§5.6 line-break normalization                         (c3b0a46)
✓ Phase 2 paper-integration-v0.1 tag                                 (c7ba2b4 → c3b0a46)
✓ Phase 2 Step 6: PI / advisor review package                        ← this commit
□ Phase 2 Step 7: PI / advisor review (PI / advisor pass)
□ Pre-submission freeze (post-PI revisions absorbed)
□ `main` branch merge                                                (only after pre-submission freeze)
```

Per round 81 explicit:
- NO new experiments
- NO AIDA-Path Path A wording
- NO `main` branch merge yet
- NO refactoring
- NO further v6.1 cleanup
- NO round-8 historical loop

This artifact is a self-contained review package for the PI / advisor pass. It does NOT introduce new claims, new tables, or new prose. All numbers, framings, and decisions reproduce values already in `paper-integration-v0.1`.
