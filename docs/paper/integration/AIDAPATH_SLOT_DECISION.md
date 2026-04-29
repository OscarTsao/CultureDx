# AIDA-Path Slot Decision

**Date**: 2026-04-29
**Per GPT round 71 trigger**: Phase 2 Step 5c — AIDA-Path slot decision, Path B.
**Decision artifact location**: `docs/paper/integration/AIDAPATH_SLOT_DECISION.md`
**Status**: Decision-only artifact. NO new AIDA-Path overlap analysis run inside this step (per round 71 explicit). NO §1, §2.6, §7.8 prose modifications.

---

## 1. Current state

AIDA-Path overlap analysis is **not completed** in the current manuscript package at HEAD `2b17aa3`.

The CultureDx DSM-5 v0 schema (`src/culturedx/ontology/data/dsm5_criteria.json`, version `0.1-DRAFT`, source-note `UNVERIFIED`) is an LLM-drafted formalization of DSM-5-TR concepts. It has not been structurally aligned with the AIDA-Path symptom-space representation, and it has not been independently reviewed by a clinician.

The current §1, §2.6, and §7 manuscript prose at HEAD `2b17aa3` already reflects this state:

- §1 line 25: "AIDA-Path structural alignment and clinician review remain pending future work (§4.4, §7.1, §7.2)"
- §1 line 29: "AIDA-Path structural alignment and clinician review of the DSM-5 v0 schema are pending future work"
- §2.6 line 43: "the present paper does not present any AIDA-Path overlap result as part of its evidence; structural alignment between the v0 DSM-5 schema and the AIDA-Path symptom-space representation is planned future work (§7.8)"
- §2.6 line 44: "We do not claim AIDA-Path validation of CultureDx"
- §7 line 27: "AIDA-Path structural alignment ... has been planned but not yet completed"
- §7 line 28: "We do not present any AIDA-Path overlap result or clinician-reviewed criterion as part of the present paper's evidence"

This decision artifact codifies that the manuscript continues operating under that wording mode.

---

## 2. Decision

**Path B — preserve AIDA-Path as a pending external structural-alignment anchor.**

This decision is binding for the current manuscript assembly pass.

The companion (rejected) Path A — completed scoped structural-alignment result — is documented in §6 below as the trigger conditions under which a future revision could move from Path B to Path A.

---

## 3. Manuscript wording mode

Path B requires that all sections referencing AIDA-Path use the "pending external structural-alignment anchor" framing.

Sections required to maintain Path B wording:

- §1 (Introduction) — first-mention citation `[CITE strasser2026machine]` with "pending future work" qualifier
- §2.6 (AIDA-Path and external structural anchors) — paper-only citation; "pending overlap analysis" framing
- §4.4 (Evaluation contract scope) — AIDA-Path future-work reference where the contract describes what is and is not currently audited
- §7.1, §7.2, §7.8 (Limitations) — explicit "AIDA-Path overlap not completed" / "clinician review pending" framing

The Path B wording mode is preserved verbatim from HEAD `2b17aa3`. This decision artifact does NOT modify any §1-§7 prose.

---

## 4. Forbidden wording (must be 0 in any positive context across §1-§7)

```
❌ AIDA-Path validated CultureDx
❌ AIDA-Path integration completed
❌ clinician-reviewed DSM-5 criteria
❌ external structural validation completed
❌ clinical validation via AIDA-Path
❌ AIDA-Path-validated criterion-level audit
❌ overlap analysis completed
❌ AIDA-Path supports CultureDx claims
❌ scoped structural-alignment result (when introduced as a present-tense claim)
```

Each pattern above is verifiable via grep across `docs/paper/drafts/SECTION_*.md`. Round 65 / 66 / 67 / 68 cumulative forbidden-list discipline is preserved here.

Note: any of these phrases may appear in this decision artifact itself **inside the Forbidden wording block above** (definitional listing) without violating the rule — the rule applies to positive-context use in §1-§7 manuscript prose.

---

## 5. Allowed wording

```
✅ pending AIDA-Path structural alignment
✅ pending external structural-alignment anchor
✅ external criteria-formalization anchor
✅ associated AIDA-Path code/resource
✅ planned overlap analysis
✅ planned future work
✅ future clinician review
✅ no completed validation claim
✅ AIDA-Path symptom-space representation (as a referenced external concept, not a CultureDx claim)
```

---

## 6. If Path A happens later (trigger conditions for revision)

Path A — completed scoped structural-alignment result — would require ALL of the following before the manuscript can adopt completed-validation framing:

1. Actual structural-alignment analysis run between the CultureDx DSM-5 v0 schema (`dsm5_criteria.json` v0.1-DRAFT) and the AIDA-Path symptom-space representation
2. Quantitative overlap result with a defined coverage metric (e.g. criterion coverage percentage, symptom-mapping accuracy, residue diff)
3. Documented residue / gap analysis for criteria that fail to align
4. Update of the DSM-5 v0 schema source-note from `UNVERIFIED` to a status that accurately reflects the alignment outcome
5. New artifact at `docs/paper/integration/AIDAPATH_OVERLAP_ANALYSIS.md` (or equivalent) documenting the analysis

If and only if all five conditions are met, the following manuscript updates apply:

- §1 scope statement: "AIDA-Path structural alignment ... pending future work" → scoped completed-alignment statement with overlap percentage
- §2.6 AIDA-Path paragraph: replace "the present paper does not present any AIDA-Path overlap result" with the scoped result
- §7.8 limitation: replace the Path B "planned but not yet completed" wording with a Path A "scoped structural-alignment result with limitations" wording
- Citation ledger: add a resource entry for `raoul-k/AIDA-Path` GitHub repository if §2.6 prose explicitly cites the resource (per Citation Pass Plan v1.1 §5.4 optional resource entry)
- Box 1 (post-v4 evaluation contract): add a row documenting the AIDA-Path alignment scope if it affects the contract
- Abstract: revise scope wording to acknowledge the completed alignment, with appropriate hedging

Path A vs Path B wording must NEVER coexist. If Path A is adopted, all Path B wording in §1-§7 prose must be replaced; the decision artifact must be updated to reflect the new state.

---

## 7. Cumulative discipline preserved

This decision artifact preserves the following cumulative disciplines from rounds 1-70:

- **Round 65 explicit**: AIDA-Path is published paper + optional resource; not validated CultureDx
- **Round 66 §5 (Citation Pass Plan v1.1)**: AIDA-Path special handling — paper mandatory, GitHub resource optional, "pending external structural-alignment anchor" wording preserved
- **Round 67 §5 (Citation Pass Plan v1.1)**: §2.6 / §7.8 prose preserved verbatim during citation pass; no drift to "validated/completed"
- **Round 70 §C5 (CITATION_LEDGER)**: §6 Table 2 protection verification documents Path B preservation across all citation pass commits
- **DSM-5 v0 schema status**: continues as `0.1-DRAFT` / source-note `UNVERIFIED`. Path B does not change this status.

---

## 8. Next step

Per round 71 explicit:

> "Proceed to reviewer-facing reproduction README after this decision is committed."
> "Step 5e — reviewer-facing reproduction README. Not Abstract yet."

The reproduction README (Step 5e) should answer:

- Which branch / commit should reviewers use?
- Where are canonical metrics?
- How to reproduce Table 2 / Box 1 / Tables 3-6?
- What files are deprecated?
- What is the v4 evaluation contract?
- How is F41.2 handled?
- Where is audit reconciliation?
- Where is citation ledger / references.bib?

Step 5c does NOT include reproduction README work; Step 5e is a separate commit.

---

## 9. Round 72 review request

After commit, send:

```
AIDA-Path slot decision committed at <hash>.

Sanity:
- Decision: Path B (preserve pending)
- Forbidden wording in §1-§7 prose: 0 positive hits
- Allowed wording present in artifact: yes
- §1, §2.6, §4.4, §7 prose unchanged: verified via diff (this commit only adds the decision artifact)
- AIDA-Path overlap analysis: NOT run inside this step (per round 71 explicit)
- DSM-5 v0 schema status: unchanged (still v0.1-DRAFT / UNVERIFIED)
- Long lines: 0

Round 72 review:
1. Is Path B the correct decision given current manuscript state?
2. Are the §6 Path A trigger conditions sufficiently strict to prevent premature adoption?
3. Should this decision artifact be referenced from §2.6 / §7.8 prose, or kept standalone?
4. Are forbidden wording patterns complete vs cumulative rounds 65-70 discipline?
5. Greenlight to proceed to Step 5e (reproduction README)?
```

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
✓ Phase 2 Step 5c: AIDA-Path slot decision (Path B)                  ← this commit
□ Phase 2 Step 5e: reviewer-facing reproduction README              ← next
□ Phase 2 Step 5f: Abstract drafting (LAST)
□ Phase 2 Step 6: PI / advisor review
```

Per round 71 explicit:
- NO new AIDA-Path overlap analysis run inside this step
- NO §1-§7 prose modifications
- NO Abstract drafting
- NO new experiments
