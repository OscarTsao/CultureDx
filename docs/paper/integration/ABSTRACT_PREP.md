# Abstract Prep

**Date**: 2026-04-29
**Per GPT round 76 trigger**: Phase 2 Step 5f — Abstract prep (claim-boundary artifact, NOT prose).
**Artifact location**: `docs/paper/integration/ABSTRACT_PREP.md`
**Status**: Planning document only. NO Abstract prose drafted in this commit. Step 5f-apply (prose drafting) deferred to a later trigger after round 77 review.

This document defines the claim boundary for the CultureDx Abstract: which hero numbers may appear, which framings are forbidden, which thesis sentences are candidate, and how each abstract claim maps to a canonical source. It does NOT draft Abstract prose.

---

## 1. Target venues and abstract constraints

The target venue is not yet locked. The Abstract prep prepares three candidate modes; final venue decision will collapse to one mode at Step 5f-apply trigger time.

### Mode A — JAMIA / JAMIA Open structured abstract

```
Limit:    up to 250 words
Headings: Objective; Materials and Methods; Results; Discussion; Conclusion
Format:   structured, with the five subheadings above
```

Default if targeting JAMIA-style clinical informatics venue. Encourages explicit Materials and Methods detail, which suits CultureDx's evaluation contract focus. Round 77 verification: JAMIA Research & Applications structured abstract limit is 250 words per the journal's General Instructions.

### Mode B — npj Digital Medicine Article abstract

```
Limit:  up to 150 words
Format: unstructured, no subheadings
```

Default if targeting npj Digital Medicine. Round 77 verification: npj Digital Medicine Article abstract limit is 150 words with no subheadings per the journal's content-types guidance. Higher overclaim risk because compression forces compact framing; prep mitigates by pre-locking forbidden patterns and capping hero-number budget at 2 (see §4).

### Mode C — conference-style abstract

```
Limit:  venue-specific (NeurIPS / ACL / EMNLP / ICML differ)
Format: typically Problem / Method / Results / Limitations / Contribution
```

Use 200-250 words only if the target venue permits it. Suited for ML / AI conferences. Less stringent on clinical caveats than Modes A/B; somewhat higher tolerance for technical-novelty framing, but cumulative round 1-75 forbidden patterns still apply.

### Default drafting path

Draft Mode A first if the target remains JAMIA / clinical-informatics style, but enforce the 250-word cap.

If the target switches to npj Digital Medicine, rewrite into Mode B rather than compressing Mode A mechanically. JAMIA structured and npj unstructured are not just different word counts; they are different rhetorical formats — JAMIA demands per-subheading content allocation, npj demands a single-paragraph narrative arc.

Rationale: CultureDx's contributions are evaluation-contract repair, audit properties, and discordance-based triage. Under Mode A's 250-word cap, these benefit from structured Materials and Methods space; under Mode B's 150-word cap, the abstract must be a single arc rather than a compressed JAMIA section sequence.

---

## 2. Allowed hero claims

These are the CultureDx claims that may appear in the Abstract. Each is supported by a canonical source verified in §7.

| # | Allowed claim | Canonical source |
|---:|---|---|
| 1 | Top-1 parity with a strong reproduced TF-IDF baseline | §5.1 / Table 2 |
| 2 | Hybrid supervised + MAS stacker (NOT LLM-only) | §5.1 line 19 |
| 3 | F32/F41 error-asymmetry reduction from 189× (single-LLM) to 3.97× (MAS ICD-10 v4) on MDD-5k | §5.3 lines 17, 20, 22 |
| 4 | Model-discordance triage flags error-enriched cases (TF-IDF/Stacker disagreement) | §6.1 / Table 5 |
| 5 | Diagnostic-standard discordance exposes standard-sensitive trade-offs | §5.4 / Table 4 |
| 6 | Both mode preserves ICD-10 primary output with DSM-5 v0 as sidecar audit evidence (architectural pass-through) | §5.4 / Table 4 Panel C |
| 7 | Synthetic / curated benchmark setting (LingxiDiag-16K + MDD-5k); NOT clinical validation | §3 / Table 1 / §7 |
| 8 | DSM-5 v0 schema is LLM-drafted and unverified | §4.3 / §7.2 |
| 9 | AIDA-Path structural alignment + clinician review pending | `AIDAPATH_SLOT_DECISION.md` / §7.8 |
| 10 | Reproducibility infrastructure documented for reviewers | `REPRODUCTION_README.md` |

Each numbered claim above must trace to a canonical source line via the §7 ledger before appearing in Abstract prose.

---

## 3. Forbidden abstract claims

The Abstract is the highest-overclaim surface in the manuscript. Each pattern below is forbidden in any positive context. Allowed forms appear in `## Allowed replacements` below.

```
❌ SOTA LLM system
❌ MAS beats TF-IDF
❌ TF-IDF is weak / TF-IDF generally beats deep models
❌ clinical deployment readiness
❌ clinically validated DSM-5 diagnoses
❌ DSM-5 improves robustness
❌ DSM-5 generalizes better
❌ DSM-5 superiority
❌ Both mode ensemble
❌ dual-standard ensemble
❌ ensemble gain
❌ bias solved
❌ bias eliminated
❌ disagreement beats confidence
❌ AIDA-Path validated CultureDx
❌ AIDA-Path integration completed
❌ clinician-reviewed criteria
❌ clinician-reviewed DSM-5 criteria
❌ external structural validation completed
❌ real-world clinical validation
❌ first multi-agent psychiatric diagnosis system
❌ MAS proves interpretability
❌ pre-v4 `2class_n=696` cited as a current value
```

### Allowed replacements

```
✅ benchmark parity (NOT superiority)
✅ Top-1 parity within ±5 percentage-point non-inferiority margin
✅ hybrid supervised + MAS stacker
✅ audit-relevant system properties
✅ standard-sensitive trade-offs
✅ sidecar audit evidence
✅ architectural pass-through (for Both mode, NOT ensemble)
✅ residual asymmetry remains
✅ asymmetry reduction (NOT bias solved)
✅ no clinical deployment claim
✅ pending validation
✅ pending external structural alignment (AIDA-Path framing per Path B)
✅ DSM-5 v0 LLM-drafted unverified
✅ synthetic / curated benchmark evaluation
✅ external synthetic distribution-shift evaluation (MDD-5k specifically)
```

---

## 4. Candidate hero numbers

The Abstract must use **3-5 numbers maximum**. More numbers = more places for canonical-source-vs-abstract-text drift; fewer numbers = harder to communicate the system's empirical posture.

### Hero-number budget

| Priority | Number | Rationale | Canonical source |
|:---:|---|---|---|
| 1 | `0.612 vs 0.610` | parity with reproduced TF-IDF (the empirical posture of the paper) | §5.1 line 18 |
| 2 | `189× → 3.97×` | strongest bias-asymmetry story on MDD-5k synthetic shift | §5.3 lines 17, 20, 22 |
| 3 | `26.4%, 2.06×` | model-discordance triage at equal review budget | §6.1 / Table 5 lines 14, 18 |
| 4 | `58.0% at 38.9%` | union policy operating point (higher recall, higher review burden) | §6 line 28, line 31 |
| 5 | `1000/1000 + 925/925` | Both mode pass-through (qualitative mention preferred over numerical) | §5.4 prep / Table 4 Panel C |

### Mode-specific hero-number budget (Step 5f-apply guidance)

The hero-number budget MUST be mode-specific. A single 3-5 budget is too loose for a 150-word npj abstract and possibly too dense for a 250-word JAMIA abstract.

#### Mode A / JAMIA 250-word structured

Use **at most 3 numerical groups**:

1. `0.612 vs 0.610`
2. `189× → 3.97×`
3. `26.4% / 2.06×`

Mention Both pass-through and limitations qualitatively (no numbers).

#### Mode B / npj 150-word unstructured

Use **at most 2 numerical groups by default**:

1. `0.612 vs 0.610`
2. `189× → 3.97×`

Optionally add `26.4% / 2.06×` ONLY if the final abstract remains ≤150 words. Mention DSM-5-v0 / synthetic-data / AIDA-Path Path B limitations qualitatively (no numbers).

#### Mode C / conference

Use **at most 3-4 numerical groups**, depending on venue limit:

1. `0.612 vs 0.610`
2. `189× → 3.97×`
3. `26.4% / 2.06×`
4. `58.0% at 38.9%` (only if venue word count permits)

Mention `1000/1000 + 925/925` Both pass-through qualitatively only.

Rationale: priorities 1-3 form a self-contained narrative — parity / bias / triage. Priorities 4-5 are reinforcement, not core narrative. The cap differs by mode because the rhetorical density per word differs by mode: 250 words can absorb 3 number groups; 150 words struggles with more than 2.

### Forbidden number-handling patterns

```
❌ Cite Top-3 numbers without specifying class scheme (12-class? 4-class?)
❌ Cite F1-macro / F1-weighted in Abstract (table-level metric, not framing claim)
❌ Cite p-values (McNemar p ≈ 1.0 is paired-discordance context, not equivalence proof)
❌ Cite 11.9% MAS feature share without §5.2 caveat (descriptive, not causal)
❌ Cite confidence intervals without explicit "bootstrap CI" framing
❌ Cite pre-v4 `2class_n=696` (deprecated)
```

---

## 5. Structured abstract options

### Option 1 — Conservative clinical-journal framing (DEFAULT)

Best for: JAMIA, npj Digital Medicine, JAMIA Open, JBI.

```
CultureDx is framed as a benchmark and audit system, NOT a clinical diagnostic tool.
The Abstract emphasizes:
- parity, NOT superiority
- auditability and standard sensitivity
- explicit limitations (DSM-5 v0 unverified, synthetic data, AIDA-Path Path B pending)
```

This is the recommended default per round 76 §5.

### Option 2 — ML-conference framing

Best for: NeurIPS, ACL, EMNLP, ICML.

```
CultureDx is framed as a hybrid supervised + MAS architecture with:
- evaluation-contract repair (post-v4 raw-code-aware contract)
- bias robustness (F32/F41 asymmetry reduction under cross-dataset shift)
- discordance-based triage (model-discordance + standard-discordance)
```

Requires more emphasis on technical contribution; less on clinical caveats.

### Option 3 — Dual-standard framing

Use ONLY if venue specifically values diagnostic standards (e.g. nosology-focused journals).

```
CultureDx is framed around ICD-10 / DSM-5 standard-sensitive audit.
Requires HEAVY caveat of DSM-5 v0 unverified status.
```

Higher overclaim risk because dual-standard framing easily slides into "clinically validated DSM-5 audit". Avoid unless venue is explicitly nosology-focused.

### Default selection

**Option 1 (Mode A) as default drafting path** for Step 5f-apply, subject to round 77 venue-lock decision. If venue switches to npj Digital Medicine post-round-77, switch to Option 2 / Mode B with full Mode B compression strategy (NOT mechanical Mode A truncation).

---

## 6. One-sentence thesis variants

The locked thesis sentence (from user memories + cumulative round 1-75 discipline):

> **CultureDx is a Chinese psychiatric differential-diagnosis benchmark system that reaches Top-1 parity with a strong reproduced TF-IDF baseline while adding MAS-enabled audit properties: F32/F41 error-asymmetry reduction, model- and standard-discordance triage, and dual-standard ICD-10 / DSM-5 audit output, with DSM-5-v0 and synthetic-data limitations explicitly scoped.**

This is the source-of-truth sentence. Step 5f-apply MUST shorten this for Abstract use; multiple shortening candidates are listed below.

### Shortening candidates

#### Variant V1 — minimum compression (long, ~ 65 words)

The locked sentence above as-is. Suited for Mode A Conclusion section. Total: ~ 65 words.

#### Variant V2 — moderate compression (~ 45 words)

> CultureDx is a Chinese psychiatric differential-diagnosis benchmark system reaching Top-1 parity with a reproduced TF-IDF baseline, with MAS-enabled audit properties (F32/F41 asymmetry reduction, discordance triage, dual-standard ICD-10/DSM-5 audit) and explicit DSM-5-v0 / synthetic-data limitations.

Suited for Mode A Conclusion or Mode C Contribution.

#### Variant V3 — high compression (~ 30 words)

> A Chinese psychiatric differential-diagnosis benchmark and audit system that reaches Top-1 parity with reproduced TF-IDF while exposing audit-relevant properties under explicit data and DSM-5-v0 limitations.

Suited for Mode B unstructured abstract opening sentence.

### Forbidden compressions

The shortening MUST NOT collapse to:

```
❌ "CultureDx beats TF-IDF on Chinese psychiatric diagnosis"           (loses parity framing)
❌ "CultureDx is a clinically validated MAS for psychiatric diagnosis" (loses scoping discipline)
❌ "CultureDx is the first MAS for psychiatric differential diagnosis" (claim CultureDx does not make)
❌ "CultureDx demonstrates DSM-5 superiority over ICD-10"               (claim CultureDx does not make)
```

---

## 7. Claim-to-source ledger

Every Abstract claim must trace to a canonical source. Step 5f-apply must verify each claim against this ledger before drafting the corresponding sentence.

| # | Abstract claim | Section | Canonical source line / file |
|---:|---|---|---|
| 1 | Top-1 parity 0.612 vs 0.610 | §5.1 | `SECTION_5_1.md` line 18 |
| 2 | hybrid supervised + MAS stacker, NOT LLM-only | §5.1 | `SECTION_5_1.md` line 19 |
| 3 | F32/F41 single-LLM 189× | §5.3 | `SECTION_5_3.md` line 17 |
| 4 | F32/F41 MAS ICD-10 v4 = 3.97× | §5.3 | `SECTION_5_3.md` lines 20, 22 |
| 5 | 47.7-fold reduction in asymmetry ratio | §5.3 | `SECTION_5_3.md` line 22 |
| 6 | Bootstrap CI [2.82, 6.08] | §5.3 | `SECTION_5_3.md` line 22 |
| 7 | Model-discordance 26.4% review budget | §6.1 | `SECTION_6.md` lines 10, 14, 17, 18 |
| 8 | Model-discordance enrichment 2.06×, recall 42.5% | §6.1 | `SECTION_6.md` lines 14, 18 |
| 9 | Confidence baseline 1.92×, recall 40.7% (qualitative comparison only) | §6.1 | `SECTION_6.md` lines 15, 18 |
| 10 | Union policy 58.0% recall at 38.9% review burden (qualitative or numerical) | §6.1 | `SECTION_6.md` lines 28, 31 |
| 11 | Standard-discordance triage on dual-standard predictions | §6.2 | `SECTION_6.md` lines 54, 57 |
| 12 | DSM-5 v0 trade-offs (Top-1 −3.6pp on LingxiDiag, 4-class +2.9pp, F32/F41 worsens) | §5.4 | `SECTION_5_4.md` (per §5.4 PREP line 269 master claim) |
| 13 | Both mode = ICD-10 architectural pass-through (1000/1000 + 925/925) | §5.4 | `SECTION_5_4_PREP.md` lines 75-79; final §5.4 |
| 14 | Synthetic / curated benchmark setting (LingxiDiag-16K + MDD-5k) | §3 | `SECTION_3.md` (Datasets); Table 1 |
| 15 | DSM-5 v0 LLM-drafted unverified | §4.3 / §7.2 | `dsm5_criteria.json` v0.1-DRAFT / source-note `UNVERIFIED` |
| 16 | AIDA-Path structural alignment + clinician review pending | §7.8 | `AIDAPATH_SLOT_DECISION.md` (Path B) |
| 17 | F42/OCD recall degradation under DSM-5 v0 | §7.6 | `SECTION_7.md` lines 15-19 |
| 18 | Reproducibility infrastructure documented | (not in Abstract; internal reference) | `REPRODUCTION_README.md` (commit `38f9073`) |

Each Step 5f-apply Abstract sentence must annotate which claims # it supports. Sentences that don't trace to ≥1 ledger row must NOT appear.

---

## 8. Round 77 review request

After commit, send:

```
Abstract prep committed at <hash>.

Sanity:
- Forbidden hero-claim patterns in §3 forbidden-block: all in negation context
- §3 forbidden patterns count: 22 (cumulative rounds 1-75)
- §4 hero-number budget: mode-specific (Mode A=3 / Mode B=2 / Mode C=3-4)
- §6 thesis variants: V1 (65w) / V2 (45w) / V3 (30w)
- §7 claim-to-source ledger: 18 rows, each with canonical source line / file
- Long lines: 0
- §1-§7 prose untouched

Round 77 review:
1. Is the abstract claim budget too dense or too sparse?
2. Which abstract mode should we use first: JAMIA-style structured (Option 1), npj-style unstructured (Option 2), or conference-style (Option 3)?
3. Are the hero numbers correctly chosen and is the mode-specific budget calibrated correctly?
4. Does the abstract framing avoid clinical / DSM-5 / SOTA / Both-mode-ensemble overclaim?
5. Should the locked thesis sentence be V1 (65w), V2 (45w), or V3 (30w) for Step 5f-apply?
6. Can we proceed to Step 5f-apply (Abstract prose v1) after this prep is approved?
```

---

## 9. Cumulative discipline preserved

This prep artifact preserves the following cumulative disciplines from rounds 1-75:

| Round / lesson | Application in this artifact |
|---|---|
| Round 22 (negation-context preservation) | §3 forbidden block + §6 forbidden compressions |
| Round 25 (mode terminology — Both mode is NOT ensemble) | §3 + §6 forbidden + §7 claim-to-source ledger row 13 |
| Round 31a (cross-section consistency) | §7 claim-to-source ledger maps each claim to specific §X line |
| Round 33a (long-line discipline) | sentence-level format throughout |
| Round 40a (explicit absence with rationale) | §3 forbidden patterns explicitly listed; §1 venue not yet locked explicitly stated |
| Round 50a (no over-instruction) | §4 hero-number budget capped at 5 max; §6 thesis sentence V3 at ~ 30 words |
| Round 64 (parallel-location residue sweep) | §3 forbidden / §6 forbidden compressions / §4 forbidden number-handling patterns mirror each other |
| Round 65/66/67/68 (citation pass forbidden patterns) | §3 includes "first multi-agent" / "MAS proves interpretability" / "DSM-5 superiority" |
| Round 70 lesson (no training-data recall for source values) | §7 every claim cites specific canonical source line |
| Round 71 (AIDA-Path Path B) | §2 row 9 + §3 forbidden + §7 row 16 + §6 forbidden compressions |
| Round 73 (deprecated artifacts) | §3 forbidden "pre-v4 `2class_n=696`" + §4 forbidden number-handling |
| Round 74-75 (no source-paper-recall content) | §7 row 12 cites §5.4 PREP master claim verbatim, NOT MDD-5k subcode percentages |

No new lesson introduced. Cumulative count remains **36 lessons**.

---

## 10. Sequential discipline status

```
✓ §1-§7 all closed (manuscript body complete)
✓ Phase 2 Step 5a: assembly review v1.1                              (82bd2a4)
✓ Phase 2 Step 5d-plan: table numbering plan v1.2                   (3bdc4af)
✓ Phase 2 Step 5d-apply: table-renumbering apply-pass v1.1           (eea8cf1)
✓ Phase 2 Step 5b-plan: citation pass plan v1.1                      (bca33ce)
✓ Phase 2 Step 5b-apply: citation apply-pass v1.2                    (d4992cc)
✓ Phase 2 Step 5b-mini: unresolved-source mini-pass v1.1             (2b17aa3)
✓ Phase 2 Step 5c: AIDA-Path slot decision (Path B)                  (57e4b02)
✓ Phase 2 Step 5e: reviewer-facing reproduction README v1.2          (38f9073)
✓ Phase 2 Step 5f-prep: this commit (Abstract claim-boundary artifact) ← NEW
□ Round 77 narrow review (6 questions in §8 above)
□ Phase 2 Step 5f-apply: Abstract prose v1 (LAST — only after this prep is approved)
□ Phase 2 Step 6: PI / advisor review
□ `main` branch merge (only after final manuscript sweep)
```

Per round 76 explicit:
- NO Abstract prose drafting in this commit (Step 5f-apply deferred)
- NO `main` branch merge
- NO refactoring
- NO AIDA-Path completed wording
- NO new experiments
