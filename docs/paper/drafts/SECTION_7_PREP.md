# §7 Limitations — Prep Package

**Date**: 2026-04-27
**Per GPT round 39**: §6 closed at `453193d`. Greenlight §7 prep only (NOT prose).
**Status**: §7 prep with 8 limitation blocks per round 39 spec. Each block = 6 elements (source / locked claim / allowed / forbidden / reviewer attack + response / connector). Global forbidden + allowed wording lists. Format-during-draft (lesson 33a) applied throughout.

---

## ITEM 1 — Source artifacts (consolidated)

All 9 sources verified to exist on remote at `453193d`.

| # | Artifact | Path | Role |
|---:|---|---|---|
| 1 | F42 limitation doc | `docs/limitations/F42_DSM5_COLLAPSE_2026_04_25.md` | §7.6 primary source |
| 2 | F32/F41 v4 asymmetry analysis | `docs/analysis/MDD5K_F32_F41_ASYMMETRY_V4.md` | §7.5 primary source |
| 3 | DSM-5 v0 criteria schema | `src/culturedx/ontology/data/dsm5_criteria.json` | §7.2 primary source (version `0.1-DRAFT`, source_note `UNVERIFIED`) |
| 4 | TF-IDF reproduction audit (post-v4) | `docs/audit/AUDIT_RECONCILIATION_2026_04_25.md` | §7.7 primary source (supersedes `docs/analysis/AUDIT_REPORT_2026_04_22.md`) |
| 5 | §5.1 prose | `docs/paper/drafts/SECTION_5_1.md` | §7.4 source (12-class fine-grained, MAS-only / Stacker LR comparators) |
| 6 | §5.3 prose | `docs/paper/drafts/SECTION_5_3.md` | §7.5 source (3.97× residual + "we document this residual asymmetry as a limitation in §7.5" forecast) |
| 7 | §5.4 prose | `docs/paper/drafts/SECTION_5_4.md` | §7.2 / §7.3 / §7.6 source (DSM-5 v0 scope, Both mode pass-through, F42 direction-only) |
| 8 | §5.5 prose | `docs/paper/drafts/SECTION_5_5.md` | §7.7 source (TF-IDF reproduction Top-1 = 0.610 vs published 0.496) |
| 9 | §6 prose | `docs/paper/drafts/SECTION_6.md` | §7.1 / §7.3 / §7.8 source ("we do not claim deployment readiness", "not an ensemble", scope phrasing) |

### Connector source-map (per round 21a)

| Limitation block | Cross-section anchor (already committed) |
|---|---|
| §7.1 Synthetic-only | §6 "evaluated on synthetic / curated test data" |
| §7.2 DSM-5 v0 | §5.4 "we document the DSM-5 v0 unverified scope explicitly in §7.2" |
| §7.3 Both mode | §5.4 "Both mode is therefore an ICD-10 architectural pass-through with DSM-5 sidecar audit evidence, not an ensemble" |
| §7.4 Rare-class blind spots | §5.1 "fine-grained 12-class classification" comparator framing |
| §7.5 F32/F41 residual | §5.3 "we document this residual asymmetry as a limitation in §7.5" |
| §7.6 F42/OCD | §5.4 "magnitude depends on the slice or class definition and is reported in §7.6" |
| §7.7 TF-IDF reproduction | §5.5 "11.4 percentage-point gap that we have not fully isolated" |
| §7.8 AIDA-Path / clinician review | (NEW — not yet referenced in §5/§6 prose; will need cross-section consistency check before §7 prose) |

---

## ITEM 2 — Global forbidden wording (cumulative + §7-specific)

```
GLOBAL FORBIDDEN (per GPT round 39 spec):
❌ "clinically validated"
❌ "clinical deployment"
❌ "ready for clinical use"
❌ "DSM-5 improves robustness"
❌ "Both mode ensemble"
❌ "bias solved"
❌ "comprehensive 12-class coverage"
❌ "F42 −40pp on both datasets"
❌ "AIDA-Path validation completed"
❌ "clinician-reviewed criteria"

CUMULATIVE CARRY-FORWARD (rounds 14-38):
❌ "deployment-ready" / "deployed model" / "deployed system" / "deployment threshold"
❌ "DSM-5 generalizes" / "DSM-5 superiority" / "DSM-5 wins"
❌ Both mode as ensemble (any framing)
❌ Aggressive mechanism verbs (Trap 8 stems): drives, achieves, delivers, yields, improves, demonstrates, proves, causes, leads to, carries (all inflections)
❌ "bias robustness" as a property claim — must be qualified (e.g. "F32/F41 bias-asymmetry reduction")
❌ Class-level claims with n<30 stated as primary evidence
❌ "189× collapse" without raw 189/1 counts
❌ "clinically appropriate" / "clinical performance"
❌ "lower baseline accuracy" (round 36 mechanism error)
❌ "different primary-output models" (round 38 perspective error)
```

---

## ITEM 3 — Global allowed replacement patterns

```
✅ "benchmark evidence"
✅ "synthetic / curated test data"
✅ "audit observation"
✅ "requires prospective clinical validation"
✅ "definition-specific F42 magnitudes"
✅ "pending AIDA-Path structural alignment"
✅ "pending clinician review"
✅ "external synthetic distribution-shift dataset"
✅ "curated benchmark"
✅ "LLM-drafted v0 formalization"
✅ "architectural pass-through"
✅ "sidecar audit evidence"
✅ "rare-class blind spots" / "low-N class coverage limitation"
✅ "substantially reduces but does not eliminate"
✅ "disclosed reproduction gap" / "stricter reproduced baseline"
```

---

## ITEM 4 — 8 Limitation Blocks

### §7.1 — Synthetic / curated data only

**Source artifact**: §5.1, §5.3, §5.4, §6 prose; LingxiDiag-16K + MDD-5k dataset descriptions.

**Locked claim**: All current evidence comes from synthetic / curated test data (LingxiDiag-16K test_final N = 1000; MDD-5k synthetic distribution-shift dataset N = 925).
The pipeline has not been evaluated on real clinical encounters; no prospective clinical deployment validation has been performed.

**Allowed wording**:
- ✅ "synthetic / curated test data"
- ✅ "external synthetic distribution-shift dataset"
- ✅ "curated benchmark"
- ✅ "requires prospective clinical validation"
- ✅ "no prospective clinical deployment validation"

**Forbidden wording**:
- ❌ "clinical deployment"
- ❌ "clinical effectiveness"
- ❌ "ready for clinical use"
- ❌ "deployment-ready"
- ❌ "real-world validation completed"

**Reviewer attack + response**:

> Attack: "All your numbers are from synthetic data, so the claims don't apply to clinical reality."
> Response: "We agree that the present evidence is benchmark-only. Section 7.1 makes this explicit: all §5 / §6 numbers are observed on LingxiDiag-16K and MDD-5k synthetic / curated test data, and we do not claim clinical deployment readiness. Prospective clinical validation is scoped out of the present paper and listed as required future work."

**Connector**: §7.1 reinforces the §6 explicit "we do not claim deployment readiness" framing; §7.1 is the consolidated home for synthetic-only scope across §5 + §6.

---

### §7.2 — DSM-5 v0 unverified criteria

**Source artifact**: `src/culturedx/ontology/data/dsm5_criteria.json` (version `0.1-DRAFT`, source_note "LLM-drafted v0 based on DSM-5-TR concepts. UNVERIFIED."); §5.4 prose.

**Locked claim**: The DSM-5 criteria schema used in §5.4 / §6.2 is an LLM-drafted v0 formalization based on DSM-5-TR concepts; it has not been reviewed or validated by clinicians.
DSM-5 outputs throughout the paper are experimental audit observations, not clinically validated DSM-5 diagnoses.
AIDA-Path structural alignment and clinician review of the DSM-5 schema are listed as parallel future work (§7.8).

**Allowed wording**:
- ✅ "LLM-drafted v0 formalization"
- ✅ "experimental audit observations"
- ✅ "audit observation under unverified LLM-drafted criteria"
- ✅ "pending AIDA-Path structural alignment"
- ✅ "pending clinician review"

**Forbidden wording**:
- ❌ "DSM-5 diagnosis" (when describing our outputs)
- ❌ "clinically validated DSM-5"
- ❌ "DSM-5 superiority"
- ❌ "DSM-5 generalizes better"
- ❌ "DSM-5 v0 verified" / "DSM-5 v0 reviewed"

**Reviewer attack + response**:

> Attack: "Your DSM-5 results aren't clinically meaningful because the criteria are LLM-drafted."
> Response: "Section 7.2 is explicit: the DSM-5 criteria schema is v0 LLM-drafted and not clinically reviewed. We therefore frame all DSM-5 outputs as experimental audit observations rather than clinically validated DSM-5 diagnoses. The §5.4 dual-standard audit and §6.2 diagnostic-standard discordance triage support this scoped interpretation; they do not assert DSM-5 clinical validity."

**Connector**: §7.2 anchors the v0 unverified scope referenced repeatedly in §5.4 ("LLM-drafted v0 ... UNVERIFIED ... experimental audit observations rather than clinically validated DSM-5 diagnoses") and §6.2 ("DSM-5 v0 results in §6.2 use the LLM-drafted unverified `dsm5_criteria.json` schema").

---

### §7.3 — Both mode is an architectural pass-through, not an ensemble

**Source artifact**: §5.4 prose; `results/dual_standard_full/{lingxidiag16k,mdd5k}/pilot_comparison.json`; `results/analysis/metric_consistency_report.json`.

**Locked claim**: Both mode is an ICD-10 architectural pass-through with DSM-5 sidecar audit evidence; it is not an ensemble.
Pairwise agreement between Both mode and ICD-10 mode is 1000/1000 on LingxiDiag-16K and 925/925 on MDD-5k; all 15 reported metric keys match exactly between the two modes on both datasets.
We do not claim accuracy gain from combining ICD-10 and DSM-5 reasoning.

**Allowed wording**:
- ✅ "architectural pass-through"
- ✅ "sidecar audit evidence"
- ✅ "ICD-10 primary output with DSM-5 sidecar"
- ✅ "not an ensemble"

**Forbidden wording**:
- ❌ "Both mode ensemble"
- ❌ "ensemble gain"
- ❌ "combined prediction" (when describing Both mode)
- ❌ "dual-standard ensemble"
- ❌ "DSM-5 reasoning improves ICD-10 prediction" (when describing Both mode)

**Reviewer attack + response**:

> Attack: "If Both mode is just ICD-10 pass-through, what is the value of dual-standard reasoning?"
> Response: "Both mode preserves the ICD-10 primary output and attaches DSM-5 sidecar audit evidence on the same case (§5.4); the value of dual-standard reasoning lies in the audit evidence — including the per-case diagnostic-standard discordance signal in §6.2 — not in an accuracy gain. We document the lack of accuracy gain explicitly: §5.4 Table 5.4c shows 0 / 15 metric-key differences between Both and ICD-10 modes on both datasets."

**Connector**: §7.3 reinforces §5.4's central guardrail ("Both mode is therefore an ICD-10 architectural pass-through with DSM-5 sidecar audit evidence, not an ensemble") and prevents reviewers from re-reading §6.2 dual-standard results as combined-prediction evidence.

---

### §7.4 — Rare-class / "Others" blind spots

**Source artifact**: §5.1 prose (12-class fine-grained framing, MAS-only DtV 0.516 vs reproduced TF-IDF 0.610 comparators); per-class recall tables (in §5.1 / §5.2 source materials).

**Locked claim**: Several low-frequency paper classes show near-zero recall in the present pipeline.
Macro-F1 remains modest relative to Top-1 / Top-3 because several low-frequency paper classes have near-zero recall; clinical coverage is correspondingly limited by these rare-class blind spots.
Class-level performance claims with n < 30 are reported descriptively only and are not used as primary evidence.

**Allowed wording**:
- ✅ "rare-class blind spots"
- ✅ "low-N class coverage limitation"
- ✅ "macro-F1 limited by rare-class recall"
- ✅ "near-zero recall on low-frequency classes"
- ✅ "descriptive-only at small N"

**Forbidden wording**:
- ❌ "comprehensive 12-class coverage"
- ❌ "detects all categories"
- ❌ "uniform per-class performance"
- ❌ "rare classes resolved"
- ❌ "balanced macro-F1"

**Reviewer attack + response**:

> Attack: "Macro-F1 around 0.30 is too low for clinical use — your system can't handle most diagnoses."
> Response: "We agree macro-F1 is limited and we document this in §7.4 as a rare-class blind-spot limitation.
> Several low-frequency paper classes have near-zero recall, which constrains macro-F1 and clinical coverage.
> The paper's primary claims focus on aggregate benchmark performance, F32/F41 directional asymmetry, and audit / triage behavior rather than uniform coverage across all 12 paper classes; where class-specific claims are made, we report raw counts and scope them to the relevant high-frequency or pre-specified diagnostic pair."

**Connector**: §7.4 explicates the §5.1 framing of "fine-grained 12-class classification" and the per-class recall context that justifies §5.4's "class-level differences are not used as a primary §5.4 claim because per-class sample sizes are too small for stable comparisons".

---

### §7.5 — Residual F32/F41 asymmetry

**Source artifact**: `docs/analysis/MDD5K_F32_F41_ASYMMETRY_V4.md`; §5.3 prose.

**Locked claim**: MAS ICD-10 v4 reduces the MDD-5k F41→F32 / F32→F41 asymmetry ratio from 189× (single LLM, 189/1) to 3.97× (151/38, 95% bootstrap CI [2.82, 6.08]).
This 47.7-fold reduction in the asymmetry ratio is substantial but not complete: 3.97× remains an asymmetric error pattern, and F41→F32 remains the dominant misclassification direction within this F32/F41 error pair.
We do not claim that F32/F41 bias is solved.

**Allowed wording**:
- ✅ "substantially reduces but does not eliminate"
- ✅ "47.7-fold reduction in the asymmetry ratio"
- ✅ "residual asymmetry"
- ✅ "F41→F32 remains the dominant direction"
- ✅ "asymmetric error pattern, not a resolved one"

**Forbidden wording**:
- ❌ "solves bias"
- ❌ "removes F32/F41 bias"
- ❌ "bias robustness achieved"
- ❌ "F32/F41 asymmetry resolved"
- ❌ "47.7× improvement" (lesson 18 — should be "47.7-fold reduction in the asymmetry ratio", not improvement)

**Reviewer attack + response**:

> Attack: "If MAS still has 3.97× asymmetry, your bias-mitigation claim is overstated."
> Response: "We agree 3.97× is not symmetric. Section 5.3 reports both the magnitude (3.97×, CI [2.82, 6.08]) and the residual direction (F41→F32 remains dominant); §7.5 documents this residual asymmetry explicitly. Our bias-asymmetry claim is a 47.7-fold reduction relative to the 189× single-LLM baseline, not a claim that asymmetry is resolved. We frame this as substantial reduction, not elimination."

**Connector**: §7.5 picks up §5.3's explicit forecast: "we document this residual asymmetry as a limitation in §7.5". The §5.3 prose closing sentence already carries this hand-off.

---

### §7.6 — F42/OCD DSM-5 v0 limitation

**Source artifact**: `docs/limitations/F42_DSM5_COLLAPSE_2026_04_25.md`; §5.4 prose; §5.4 prep `SECTION_5_4_PREP.md`.

**Locked claim**: F42/OCD recall decreases under DSM-5-only mode on both LingxiDiag-16K and MDD-5k.
The exact magnitude is definition-specific: under the paper-parent per-class definition, the LingxiDiag-16K decrease is approximately −40 percentage points (n = 25, descriptive); under the v4 slice metric, the LingxiDiag-16K decrease is approximately −30.6 percentage points (n = 36).
On MDD-5k, the decrease under both definitions is approximately −23 percentage points at small N (paper-parent n = 13, v4 slice n = 21).
We treat this as a v0 schema limitation rather than evidence against dual-standard auditing in general, and we adopt a conservative evidence policy where the LLM marks insufficient F42 evidence rather than over-asserting OCD criteria.

**Allowed wording**:
- ✅ "definition-specific F42 magnitudes"
- ✅ "F42/OCD recall decreases under DSM-5 v0"
- ✅ "conservative evidence policy"
- ✅ "v0 schema limitation"
- ✅ "requires clinician validation of the DSM-5 v0 F42 criterion-D exclusion / differential-diagnosis handling"

**Forbidden wording**:
- ❌ "F42 −40pp on both datasets" (factually wrong; only the LingxiDiag paper-parent value)
- ❌ "LLM correctly marks insufficient evidence" (overstates "correctness" — we adopted a policy, not a clinical correctness claim)
- ❌ "clinically appropriate F42 handling"
- ❌ "F42 criterion-D resolved"
- ❌ Unqualified "F42 collapse" without definition / dataset context

**Reviewer attack + response**:

> Attack: "Your DSM-5 mode breaks F42/OCD detection — that's a serious clinical safety issue."
> Response: "We agree F42/OCD recall decreases under DSM-5 v0 mode on both datasets, and §7.6 documents this as a v0 schema limitation.
> The exact magnitude is definition-specific; we report ranges rather than a single number, and we acknowledge that all F42-related observations rest on the v0 LLM-drafted unverified criteria (§7.2).
> We adopt a conservative evidence policy in DSM-5 v0 mode such that the LLM marks insufficient F42 evidence rather than over-asserting OCD criteria; this is a policy choice, not a claim of clinical correctness.
> F42 outputs are not used as primary clinical evidence anywhere in the paper."

**Connector**: §7.6 is the consolidated home for F42 magnitudes that §5.4 deliberately defers. §5.4 prose explicitly says "the magnitude depends on the slice or class definition and is reported in §7.6, where we treat F42/OCD as a v0 schema limitation".

---

### §7.7 — TF-IDF reproduction gap

**Source artifact**: `docs/paper/drafts/SECTION_5_5.md`; `docs/audit/AUDIT_RECONCILIATION_2026_04_25.md` (post-v4 reconciliation); `scripts/train_tfidf_baseline.py`. Historical audit context only: `docs/analysis/AUDIT_REPORT_2026_04_22.md` (superseded by post-v4 reconciliation).

**Locked claim**: Our reproduced TF-IDF baseline reaches Top-1 = 0.610 on LingxiDiag-16K test_final, an 11.4 percentage-point gain over the published TF-IDF baseline (Top-1 = 0.496).
We have not fully isolated the cause of this reproduction gap.
The §5.1 parity claim deliberately uses our stronger reproduced baseline (Stacker LGBM 0.612 vs reproduced TF-IDF 0.610) rather than the weaker published baseline; reviewers may inspect both comparisons.

**Allowed wording**:
- ✅ "disclosed reproduction gap"
- ✅ "stricter reproduced baseline"
- ✅ "11.4 percentage-point gap that we have not fully isolated"
- ✅ "our parity claim depends only on the stricter comparison"
- ✅ "plausible contributors" (when listing tokenization / hyperparameters)

**Forbidden wording**:
- ❌ "paper baseline wrong" / "published baseline incorrect"
- ❌ "exact reproduction"
- ❌ "TF-IDF reproduction validated"
- ❌ "we identified the cause"
- ❌ Treating the published 0.496 baseline as our primary comparator

**Reviewer attack + response**:

> Attack: "Why does your TF-IDF outperform the published baseline by 11 points? Your reproduction is suspect."
> Response: "Section 7.7 makes the reproduction gap explicit.
> We disclose the 11.4 percentage-point gain over the published 0.496 baseline rather than treating it as our primary evidence of model strength.
> Plausible contributors are listed in §5.5 (tokenization, character n-gram configuration, `min_df` / `max_df`, `sublinear_tf`, logistic-regression hyperparameters, label normalization, split handling).
> Our §5.1 parity claim uses the stricter reproduced 0.610 baseline; we do not rely on the easier published 0.496 baseline."

**Connector**: §7.7 anchors the reproduction-gap framing already established in §5.5 ("we have not fully isolated"); §7.7 makes the disclosure explicit at the limitations level.

---

### §7.8 — AIDA-Path / clinician review pending

**Source artifact**: Project plan (no committed manuscript section yet); §5.4 / §7.2 v0 unverified scope.

**Locked claim**: AIDA-Path structural alignment and independent clinician review are listed as pending validation anchors, not as completed evidence.
The DSM-5 v0 schema (§7.2) and the F42/OCD criterion-D handling (§7.6) are the primary targets for these pending validations.
We do not present any AIDA-Path or clinician-review result as part of the present paper's evidence.

**Allowed wording**:
- ✅ "planned structural alignment"
- ✅ "pending AIDA-Path overlap analysis"
- ✅ "pending clinician review"
- ✅ "future-work validation anchor"
- ✅ "scope limitation of the present paper"

**Forbidden wording**:
- ❌ "AIDA-Path validated" (until / unless completed)
- ❌ "AIDA-Path validation completed"
- ❌ "clinician-reviewed criteria"
- ❌ "clinician review results show ..."
- ❌ "AIDA-Path overlap supports ..." (preemptively claiming a finding from a not-yet-run analysis)

**Reviewer attack + response**:

> Attack: "Without AIDA-Path or clinician review, none of your DSM-5 results are trustworthy."
> Response: "Section 7.8 acknowledges this explicitly.
> AIDA-Path structural alignment and clinician review are pending future-work anchors, not present evidence.
> The paper's DSM-5-related claims are scoped accordingly: DSM-5 outputs are framed as experimental audit observations under v0 LLM-drafted unverified criteria (§5.4, §7.2), and we do not claim clinical validity.
> The value of the present paper lies in the bias-asymmetry, dual-standard audit, and disagreement-triage findings (§§5.3, 5.4, 6) that hold under this scoped interpretation."

**Connector**: §7.8 closes the limitations chain by explicitly listing what would be needed to upgrade the §5.4 / §6.2 audit observations into clinically validated claims, without preemptively asserting any of those validations as done.

**Future revision note (prep-only, not for prose)**: If AIDA-Path structural alignment is completed before submission, update §7.8 from "pending validation anchor" to a scoped external structural-alignment result; do not leave both versions simultaneously. Same applies if independent clinician review of the DSM-5 v0 schema is completed.

---

## ITEM 5 — Cross-section consistency map

For each limitation block, the corresponding §5 / §6 prose anchor that hands off to §7:

| Block | §5 / §6 anchor (committed) | §7 follow-through |
|---|---|---|
| §7.1 | §6 "evaluated on synthetic / curated test data; we do not claim deployment readiness" | Consolidates synthetic-only scope |
| §7.2 | §5.4 "we document the DSM-5 v0 unverified scope explicitly in §7.2" | Direct hand-off |
| §7.3 | §5.4 "Both mode is therefore an ICD-10 architectural pass-through with DSM-5 sidecar audit evidence, not an ensemble" | Reinforces guardrail |
| §7.4 | §5.1 "fine-grained 12-class classification" + §5.4 small-N caveats | Consolidates rare-class scope |
| §7.5 | §5.3 closing: "we document this residual asymmetry as a limitation in §7.5" | Direct hand-off |
| §7.6 | §5.4 "magnitude depends on the slice or class definition and is reported in §7.6" | Direct hand-off |
| §7.7 | §5.5 "11.4 percentage-point gap that we have not fully isolated" | Reinforces disclosure |
| §7.8 | §7.2 cross-reference (NEW — needs check) | Closes limitations chain |

**Cross-section consistency check (lesson 25c / 31a)**: All §7 references in §5 / §6 prose verified to exist except §7.8 — which is a new limitation block not previously forecast in §5 / §6. No retro-edits to §5 / §6 are required because §7.8 is additive, not corrective.

---

## ITEM 6 — Prose plan (NO PROSE)

Per GPT round 39 explicit:
> "Do not start §7 prose directly."

When §7 prose is authorized (post round 40 review), structure:

| Subsection | Estimated words | Notes |
|---|---:|---|
| §7.1 Synthetic / curated data only | 80–120 | Clean opening; direct synthetic-only scope statement |
| §7.2 DSM-5 v0 unverified criteria | 100–150 | Most-referenced limitation; needs explicit version + source-note citation |
| §7.3 Both mode is not an ensemble | 80–120 | Includes Table 5.4c metric-key match summary |
| §7.4 Rare-class blind spots | 80–120 | Avoid stating macro-F1 number as headline; frame as scope, not failure |
| §7.5 Residual F32/F41 asymmetry | 100–150 | Includes 189 / 1 / 151 / 38 raw counts + 3.97× CI [2.82, 6.08] |
| §7.6 F42/OCD DSM-5 v0 limitation | 150–200 | Needs definition-specific magnitudes; conservative evidence policy framing |
| §7.7 TF-IDF reproduction gap | 100–150 | Echo §5.5 disclosure + §5.1 parity caveat |
| §7.8 AIDA-Path / clinician review pending | 80–120 | Closes limitations chain; explicit "no preemptive validation claim" |

**Total estimate**: ~770–1130 words (no tables; §7.3 may inline-cite Table 5.4c numbers without a new table).

**Format discipline (lesson 33a)**: Sentence-level line breaks from initial draft. Apply during drafting, not as post-hoc cleanup.

**Mechanism-precision (lessons 35a / 36a)**: Each magnitude / mechanism statement verified against source artifact cells (§7.5 against MDD5K_F32_F41_ASYMMETRY_V4.md table; §7.6 against F42_DSM5_COLLAPSE doc; §7.7 against §5.5 prose).

---

## ITEM 7 — Round 40 review request (per GPT round 39 spec)

```
§7 prep committed at <hash>.

Round 40 narrow review:
1. Are all major limitations from §5/§6 represented?
2. Does §7 avoid undermining the main claims while remaining honest?
3. Are DSM-5 v0 and F42 limitations scoped correctly?
4. Are synthetic-only / no-clinical-validation limitations strong enough for JAMIA / npj?
5. Can we start §7 prose?
```

---

## Cumulative round 14-39 lessons applied

This prep applies all cumulative lessons from §5.4 + §6 arcs explicitly. Notable applications:

| Lesson | Application in §7 prep |
|---|---|
| 16 / 22d / 27a / 27b | "deployed" / "clinically validated" only in negated/forbidden context (Item 2 global forbidden) |
| 18 / 22a-c | Stem-aware verb forbidden list (Trap 8 carry-forward in Item 2) |
| 19 / 20 | Connectors drafted FIRST (Item 1 connector source-map; Item 5 cross-section consistency) |
| 21a | Source list includes connector source-map (Item 1) |
| 22e | Bootstrap CI explicitly stated (§7.5 "CI [2.82, 6.08]") |
| 23b | "Comparable" / "substantial reduction" — quantifier scope bound (§7.5 "47.7-fold reduction") |
| 25a/c/d | Every claim traced to source artifact line/table (Item 1 + Item 5) |
| 25b / 32a / 38a | Mode terminology: "DSM-5 v0 schema" / "primary-output perspective" / "audit observation" — distinct from "DSM-5 diagnosis" |
| 26b / 27c / 28a / 29a / 36a (escalation) | Bare-stem grep + 5+ location class sweep applied to forbidden list |
| 31a | Cross-section directional convention: §7.5 cites F41→F32 / F32→F41 direction matching §5.3 |
| 33a | Format-during-draft: sentence-level line breaks throughout this prep |
| 35a | Mechanism precision: §7.6 F42 magnitudes are definition-specific (paper-parent vs v4 slice) |
| 36a (escalation) | Round-38 Option 2 precedent: parallel-location residue sweep is now standard for any content-level claim |
| 38b | Scope-limit comparative claims: §7.5 "substantially reduces but does not eliminate" rather than "improves" |

§7 prep has the most prep guardrails of any section — full lessons stack from rounds 14-39.

§7 prose v1 (when authorized) will benefit from all 9 cumulative lessons in Source verification + 5 in Mode terminology + 7 in Quantifier discipline + 5 in Hygiene + 1 in Causal-language hedging.

---

## Sequential discipline status

```
✓ §5 fully closed
✓ §6 fully closed (5 commits / 5 review rounds, rounds 34-38)
□ §7 prep ← awaiting your push
□ Round 40 narrow review
□ §7 prose v1 ← if 5/5 pass
```

§7 prep is structurally largest of any prep file to date (8 limitation blocks vs §6 prep's effectively 4 connector slots). Estimated 600–800 lines when committed.
