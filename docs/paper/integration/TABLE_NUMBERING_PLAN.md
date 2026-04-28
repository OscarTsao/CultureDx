# Table Numbering Plan

**Date**: 2026-04-28
**Per GPT round 59**: Phase 2 Step 5d trigger — Table-number pass only. Plan / ledger only; no in-text edits applied here.
**Status**: 8-section plan covering 8 current markdown tables + Round 60 review request. All 8 tables verified at HEAD `82bd2a4` using lesson 58a both-detection-methods discipline (caption-based + structural pipe-table).

This file is a planning artifact. NO `Table X.Y` → `Table N` renaming or caption editing is applied to §1-§7 prose during this commit. Apply pass is deferred to a separate commit, after round 60 narrow review of this plan.

---

## 1. Current markdown table inventory

Verified at HEAD `82bd2a4` using both detection methods per lesson 58a (round 58 Fix 3):

```bash
# Method 1 — caption-based:
grep -RhnE "^\*?\*?Table [0-9]" docs/paper/drafts/SECTION_*.md  # 6 captions

# Method 2 — structural pipe-table:
grep -c "^|" docs/paper/drafts/SECTION_*.md                     # 8 sections-with-tables
```

| # | Current location | Current label | Detection | Role | Rough rows |
|---:|---|---|:---:|---|---:|
| 1 | §4.4 | (unlabeled pipe table at lines 46-53) | structural only | v4 metric-family-specific prediction/gold sources (Top-1 / Top-3 / F1 / 2-class / 4-class / Overall) | 7 |
| 2 | §5.3 | (unlabeled pipe table at lines 11-16) | structural only | F32/F41 asymmetry cascade across single-LLM, MAS T1, MAS R6v2, MAS ICD-10 v4 | 5 |
| 3 | §5.4 | Table 5.4a | both | LingxiDiag-16K mode comparison (ICD-10 / DSM-5 / Both × 7 metrics, N=1000) | 4 |
| 4 | §5.4 | Table 5.4b | both | MDD-5k mode comparison (ICD-10 / DSM-5 / Both × 7 metrics, N=925) | 4 |
| 5 | §5.4 | Table 5.4c | both | Both vs ICD-10 pairwise agreement + metric-key match (1000/1000, 925/925, 0/15) | 3 |
| 6 | §6 | Table 6.1a | both | Model-discordance vs confidence baseline (LingxiDiag-16K, N=1000) | 3 |
| 7 | §6 | Table 6.1b | both | Union policy (model-discordance OR low-confidence) | 4 |
| 8 | §6 | Table 6.2a | both | Diagnostic-standard discordance across datasets (LingxiDiag + MDD-5k × ICD-10/DSM-5 perspective) | 5 |

**Total**: 8 current markdown tables (6 labeled + 2 unlabeled at §4.4 / §5.3).

**Sections with NO pipe table at HEAD**: §1, §2, §3, §5.1, §5.2, §5.5, §5.6, §7. Of these:
- §3 may need a new Dataset summary table (decision: see §6 below — "Tables not yet drafted")
- §5.1 currently has the main benchmark numbers in prose only; round 59 explicit recommends a formal Main Benchmark table (decision: see §6 below)
- Others (§1, §2, §5.2, §5.5, §5.6, §7) intentionally have no tables (positioning / disclosure / discussion content)

---

## 2. Proposed manuscript-level table order

I propose **6-7 main tables** (round 59 explicit upper bound). Two design choices marked `[A/B]` for round 60 to decide.

### Decision A: §4.4 evaluation contract — Box vs Table

- **Option A1**: Convert to **Box 1** (preferred — it is a methods contract, not a results table; venues like *npj Digital Medicine* / JAMIA support boxes)
- **Option A2**: Keep as **Table 2** (if venue does not support boxes)

I default to **A1 (Box 1)** unless venue forbids.

### Decision B: §3 Dataset / Task summary table — add or omit

- **Option B1**: Add a new **Table 1** for datasets (N / language / source type / role) — reviewer-friendly, conventional in clinical-NLP papers
- **Option B2**: Omit; §3 prose already covers dataset details

Round 59 explicit: "這張表對 reviewer 友善，但不是必須." I default to **B1 (add Table 1)** for reviewer experience but flag it as optional.

### Proposed manuscript-level table order

| Manuscript number | Source | Caption (proposed) |
|:---:|---|---|
| **Table 1** [B1, optional] | new (synthesizes §3) | "Datasets and roles" — LingxiDiag-16K (N=1000, in-domain benchmark) + MDD-5k (N=925, external synthetic distribution shift) |
| **Box 1** [A1] OR **Table 2** [A2] | §4.4 unlabeled | "v4 evaluation contract — metric-family-specific prediction / gold sources" |
| **Table 2 (or 3)** — Main benchmark | new (synthesizes §5.1, see §6 below) | "LingxiDiag-16K main benchmark results (N=1000)" — Paper TF-IDF / Paper best LLM / Reproduced TF-IDF / MAS-only / Stacker LR / Stacker LGBM × Top-1, Top-3, Overall, 2-class, macro-F1 |
| **Table 3 (or 4)** — F32/F41 cascade | §5.3 unlabeled | "Cross-dataset F32/F41 asymmetry cascade on MDD-5k" — single-LLM, MAS T1, MAS R6v2, MAS ICD-10 v4 × F41→F32 / F32→F41 / Ratio |
| **Table 4 (or 5)** — Dual-standard audit | §5.4a + §5.4b + §5.4c (merged) | "Dual-standard ICD-10 / DSM-5 audit results"; Panel A = LingxiDiag, Panel B = MDD-5k, Panel C = Both-mode pass-through |
| **Table 5 (or 6)** — Model-discordance triage | §6.1a + §6.1b (merged) | "Model-discordance and confidence-based triage on LingxiDiag-16K (N=1000)" |
| **Table 6 (or 7)** — Diagnostic-standard discordance | §6.2a | "ICD-10 / DSM-5 diagnostic-standard discordance across datasets" |

**Final count**: 6 tables + 1 box (preferred A1+B1) OR 7 tables (A2+B1) OR 5 tables + 1 box (A1+B2).

Round 59 explicit cap: "manuscript 控制在 6–7 張主表" → all three options stay within cap.

---

## 3. Merge / convert / appendix decisions

Each current table either survives, merges, converts, or moves to appendix. Decisions below:

| # | Source | Decision | Reasoning |
|---:|---|---|---|
| 1 | §4.4 unlabeled | **Convert to Box 1** (or Table if venue forbids boxes) | Methods contract not result; box format is more conventional |
| 2 | §5.3 unlabeled | **Promote to main Table** (likely Table 3 or 4) with caption | Core result table for §1 Contribution 2; needs caption for cross-reference |
| 3 | §5.4 Table 5.4a | **Merge** into Dual-standard audit table as Panel A | Single LingxiDiag panel; merging avoids 3 closely related tables |
| 4 | §5.4 Table 5.4b | **Merge** into Dual-standard audit table as Panel B | Single MDD-5k panel |
| 5 | §5.4 Table 5.4c | **Merge** into Dual-standard audit table as Panel C | Pass-through verification; can also be inlined as text + footnote, but Panel C keeps it visible to reviewer |
| 6 | §6 Table 6.1a | **Merge** with 6.1b into single Model-discordance triage table | Disagreement and confidence rows are compared at the same 26.4% review budget; the union row is a higher-recall operating point at 38.9% review burden; CI in caption or footnote |
| 7 | §6 Table 6.1b | **Merge** with 6.1a (see above) | — |
| 8 | §6 Table 6.2a | **Keep as standalone** Diagnostic-standard discordance table | Different evaluation question (standard discordance, not model discordance); merging with Table 6 (model-discordance) would create an ambiguous "triage" table that conflates two distinct signals — explicitly forbidden in §7 forbidden-drift list below |

**Cross-reference clarifications for merges**:

- §5.4 merge: Tables 5.4a/b/c → Table N (Dual-standard) Panels A/B/C
- §6.1 merge: Tables 6.1a/b → Table N+1 (Model-discordance) with row layout

**Appendix candidates** (none mandatory):
- §6.1 Jaccard 0.357 detail could move to caption / footnote
- §5.4c metric-key 0/15 could move to footnote on Panel C
- F42 definition-specific magnitudes (52→12, −30.6pp, −23.1pp, −23.8pp) stay scoped to §7.6 (NOT in main results table per round 59 forbidden drift)

---

## 4. Caption requirements

Per round 59 explicit, every caption must specify:

1. **Dataset / N**
2. **Metric family**
3. **Evaluation contract / raw-code caveat if relevant**
4. **Whether values are descriptive or inferential**
5. **Main forbidden interpretation**

### Caption drafts (subject to round 60 review)

**Box 1 (or Table 2) — v4 evaluation contract.**
> Metric-family-specific prediction-source / gold-source contract.
> The 12-class metrics use paper-parent ICD-10 normalization (Method §3.1, §4.4).
> Auxiliary 2-class and 4-class metrics use raw `DiagnosisCode` annotations.
> F41.2 is excluded from 2-class evaluation and mapped to "Mixed" in 4-class evaluation.
> Earlier paper-number artifacts are retained for provenance only; all §5/§6 numerical claims use this v4 contract.

**Table 1 — Datasets and roles.**
> LingxiDiag-16K (N=1000) and MDD-5k (N=925) Chinese psychiatric clinical-dialogue benchmarks used in the present study.
> Both are synthetic / curated rather than clinician-adjudicated real-world clinical transcripts; benchmark-level results are not equivalent to clinical validation (§7.1).

**Table 2 (or 3) — Main benchmark.**
> LingxiDiag-16K main benchmark results (test_final, N=1000).
> Stacker LGBM is a hybrid supervised + MAS stacker, not an LLM-only system.
> Top-1 = 0.612 vs reproduced TF-IDF 0.610 supports parity within the ±5 percentage-point non-inferiority margin defined in the post-v4 evaluation contract; McNemar p ≈ 1.0 is paired-discordance context, not an equivalence proof.
> The 11.4-percentage-point gap between our reproduced TF-IDF and the published baseline is disclosed in §5.5; our parity claim depends only on the reproduced comparison.

**Table 3 (or 4) — F32/F41 asymmetry cascade.**
> Cross-dataset F32/F41 asymmetry on MDD-5k (N=925).
> Asymmetry ratio = F41→F32 errors / F32→F41 errors; pair with raw counts because a denominator of 1 makes the ratio mathematically unstable.
> Bootstrap CI [2.82, 6.08] is reported only for the MAS ICD-10 v4 endpoint.
> Historical pipeline states (T1, R6v2) are reported descriptively across system configurations; we do not attribute the change between adjacent rows to single repairs.
> Residual asymmetry remains; we do not claim the bias is solved (§7.5).

**Table 4 (or 5) — Dual-standard audit.**
> Dual-standard ICD-10 / DSM-5 audit results.
> Panel A: LingxiDiag-16K (N=1000). Panel B: MDD-5k (N=925). Panel C: Both-mode pass-through verification.
> DSM-5-only mode is evaluated as an experimental v0 audit formalization (`dsm5_criteria.json` version 0.1-DRAFT, source-note UNVERIFIED).
> Both mode preserves the ICD-10 primary output and attaches DSM-5 sidecar audit evidence on the same case (1000/1000 and 925/925 pairwise agreement, 0/15 metric-key differences).
> Both mode is therefore an architectural pass-through, not an ensemble.
> Class-level differences are descriptive; per-class sample sizes are too small for inferential primary claims.

**Table 5 (or 6) — Model-discordance triage.**
> Model-discordance and confidence-based triage signals on LingxiDiag-16K (N=1000).
> Disagreement and confidence are compared at the same 26.4% review budget; the union policy is reported as a higher-recall operating point at 38.9% review burden.
> Δ enrichment 95% paired-bootstrap CI [−0.204, +0.473] and Δ recall 95% CI [−0.043, +0.073] for disagreement vs confidence both include zero; we report no statistically detectable advantage.
> Union policy increases error recall at the cost of higher review burden.
> Triage signals are case-level audit aids, not deployment-ready triage.

**Table 6 (or 7) — Diagnostic-standard discordance.**
> ICD-10 / DSM-5 diagnostic-standard discordance across datasets.
> Higher enrichment under the DSM-5 v0 primary-output perspective reflects lower DSM-5 v0 accuracy within flagged disagreement cases, not DSM-5-specific triage value.
> The DSM-5 v0 schema is an experimental audit formalization; results on this table are scoped accordingly (§7.2).

---

## 5. Cross-reference edits required

Edit queue for the apply-pass commit (NOT executed in this plan commit):

| File | Line | Current reference | Proposed reference | Action |
|---|---:|---|---|---|
| SECTION_4.md | 33 | "Table 5.4c" | "Table 4 Panel C" (or Table 5 Panel C, depending on numbering) | rename in-text reference |
| SECTION_4.md | 53 | "Table 4 metric values" | "the contract above" or stable-numbered reference | update — currently uses "Table 4" to refer to a metric-script-output, distinct from manuscript Table 4; likely need disambiguation wording |
| SECTION_4.md | 46-53 (table) | unlabeled pipe table | "Box 1: v4 evaluation contract" caption + boxed format | add caption + format |
| SECTION_5_3.md | 11-16 (table) | unlabeled pipe table | "Table 4. F32/F41 asymmetry cascade on MDD-5k" caption | add caption |
| SECTION_5_4.md | 13 | "Table 5.4a" | "Table 5 Panel A" (or absorb into merged caption) | rename |
| SECTION_5_4.md | 26 | "Table 5.4b" | "Table 5 Panel B" | rename |
| SECTION_5_4.md | 40 | "Table 5.4c" | "Table 5 Panel C" | rename |
| SECTION_6.md | 9 | "Table 6.1a" | "Table 6 (top rows)" or "Table 6" | rename + merge |
| SECTION_6.md | 21 | "Table 6.1b" | "Table 6 (union row)" | merge into Table 6 |
| SECTION_6.md | 44 | "Table 6.2a" | "Table 7" | rename |
| SECTION_6.md | 55 | "Table 6.2a flagged-subset accuracy" | "Table 7 flagged-subset accuracy" | rename |
| SECTION_5_1.md | (new) | (currently prose-only) | new Table 2 (or 3) caption + numbers | add new table from §5.1 prose-extracted numbers |

**Important nuance** for SECTION_4.md line 53: The current line reads "Overall | mean of all non-`_n` Table 4 metric values | (composite)". This "Table 4" is a **script-output identifier** (the script producing the metric ledger), not a manuscript Table 4. After renumbering, this should be disambiguated to e.g. "the metric ledger above" or "the contract above" to avoid collision with manuscript-level Table 4.

---

## 6. Tables not yet drafted but likely needed

Per round 59 spec, two new tables are likely needed:

### New table candidate — Table 1 (Datasets)

**Source**: synthesizes §3.2.1 + §3.2.2 prose into a 2-row dataset table.

**Proposed structure**:

| Dataset | Role | N | Language | Source type | Used for |
|---|---|---:|---|---|---|
| LingxiDiag-16K (test_final) | in-domain benchmark | 1000 | Chinese | synthetic / curated dialogue | main benchmark, model-discordance triage, dual-standard audit |
| MDD-5k | external synthetic distribution shift | 925 | Chinese | synthetic vignette | bias-asymmetry analysis, dual-standard audit |

**Decision (B1 vs B2)**: I default to **B1 (add)** because reviewer experience benefits from a single-glance dataset summary; flagged as optional.

### New table candidate — Table 2 or 3 (Main benchmark)

**Source**: §5.1 currently has the main benchmark numbers in prose only. Round 59 explicit:
> "目前 §5.1 可能是 prose-only，但 manuscript 應該要有 formal main benchmark table."

**Verified at HEAD**: §5.1 has 0 pipe-table rows; all numbers are in prose.

**Proposed schema**:

Columns: System | Top-1 | Top-3 | Overall | 2-class | macro-F1
Rows: Paper TF-IDF (LingxiDiag report) | Paper best LLM (LingxiDiag report) | Reproduced TF-IDF (ours) | MAS-only (DtV) | Stacker LR | **Stacker LGBM (ours, primary)**

**Source rule (round 60 Edit A — revised)**:
Table 2 should be populated from the canonical post-v4 benchmark sources used in §5.1, not from prose extraction alone.
This is manuscript assembly, not new analysis.
If a metric was not reported for a published comparator, mark it as `—`.
If the metric exists in the canonical CultureDx artifact (post-v4 metric-consistency report and audit reconciliation), populate it.

This rule prevents conflating "missing in §5.1 prose" with "not measured" — they are different conditions, and treating them as identical would be an absence-claim risk in the same family as earlier-round lessons.

### Optional (NOT recommended): figure or appendix tables

- F42 definition-specific magnitudes (52→12, −30.6pp, −23.1pp, −23.8pp): stays in §7.6 prose. Forbidden drift (per §7) — do NOT promote to main table.
- F32/F41 cascade per-fix ablation: §5.3 explicitly disclaims per-fix attribution. Do NOT add an ablation table.

---

## 7. Forbidden table-numbering drift

Per round 59 explicit, the following anti-patterns must be blocked at apply-pass:

```
❌ Renumbering local tables without updating in-text references
❌ Dropping the §4.4 evaluation-contract table from inventory
❌ Dropping the §5.3 F32/F41 cascade table from inventory
❌ Treating Both-mode pass-through as ensemble table
❌ Combining model-discordance and diagnostic-standard discordance into one ambiguous "triage" table
❌ Moving F42 definition-specific magnitudes into main table without §7.6 scope
❌ Promoting a single subset CI / Jaccard / metric-key footnote to main table
❌ Introducing new numerical claims at the table-number pass (citation pass / new analysis is separate)
❌ Silently changing manuscript number across distinct apply-pass edits (e.g. inconsistent Table 5 vs Table 5 Panel A reference)
❌ Using "Table 4" in §4 line 53 (script-output identifier) without disambiguation against manuscript Table 4 (round 60 must adjudicate)
❌ Calling Table 2 "main benchmark" without §5.5 reproduction-gap caveat in caption
❌ Calling Table 4/5 dual-standard "ensemble result" anywhere
❌ Skipping caption requirements 1-5 from §4 above
```

Cross-section forbidden grep (lesson 43a) must be re-run AFTER apply-pass commits, including these patterns:
- "Table 5.4a" / "Table 5.4b" / "Table 5.4c" / "Table 6.1a" / "Table 6.1b" / "Table 6.2a" should each occur 0 times in §1-§7 prose after rename
- "ensemble" must remain bounded to §4 + §5.4 + §7.3 (Both mode pass-through context only)
- "Box 1" must occur ≥1 time in §4 after caption add (assuming A1)
- "Table 4" in §4 line 53 must be either disambiguated or removed

---

## 8. Round 60 review request

```
TABLE_NUMBERING_PLAN committed at <hash>.

Round 60 narrow review:
1. Does the plan include all current markdown tables? (8 tables: §4.4 + §5.3 unlabeled + 5.4a/b/c + 6.1a/b + 6.2a)
2. Should §4.4 evaluation contract be Box 1 [A1] or Table 2 [A2]?
3. Should §3 Dataset summary table be added [B1] or omitted [B2]?
4. Should §5.4a/b/c be merged into one dual-standard table with Panels A/B/C?
5. Should §6.1a/b be merged into one model-discordance table with row layout?
6. Should §6.2a stay standalone (vs merge into a single triage table)?
7. Are the 7 caption drafts (Box 1 + Tables 1-6) acceptable?
8. Can we start applying table renumbering edits in a separate commit?
```

If 8/8 pass → next commit is **apply-pass: rename in-text Table references + add captions to §4.4 / §5.3 / §5.1 + merge §5.4a/b/c + merge §6.1a/b**.

If <8 pass → polish round on this plan to fix specific design decisions caught.

---

## 9. Lesson application during this plan

| Lesson | Application |
|---|---|
| 21a | All 8 tables sourced from committed prose grep, not memory |
| 25a-d | Each row of the inventory table maps to a specific file + line range |
| 31a | Cross-reference edit queue (§5) traces every in-text Table mention to its proposed new reference |
| 33a | Sentence-level breaks throughout this plan |
| 38b | Decisions A and B explicitly framed as round-60 review questions, not unilateral commitments |
| 40a | All numerical anchors in caption drafts traced to §5/§6 prose; no new numbers introduced |
| 43a | Forbidden drift list (§7) includes patterns that the apply-pass cross-section grep must verify after rename |
| 44a | Drafting-context observations explicit: §4 line 53 "Table 4" disambiguation; §5.1 missing-numbers fallback to "—" rather than new metric extraction |
| 50a (extended) | Final manuscript table count capped at 6-7; lesson 50a anti-results-dump applied to table count, not just citation density |
| **58a** | Both-detection-method discipline applied at inventory verification step (caption-based + structural pipe-table); explicitly documented in §1 |

No new lesson this round. Cumulative count remains **36 lessons**.

---

## 10. Sequential discipline status

```
✓ §1-§7 all closed (manuscript body complete)
✓ Phase 2 Step 5a: assembly review v1.1 closed (82bd2a4)
✓ Phase 2 Step 5d: table-numbering plan prepared (this artifact)
□ Commit ← awaiting your push
□ Round 60 narrow review (8 questions)
□ Phase 2 Step 5d apply-pass: rename in-text references + add captions + merge tables (separate commit)
□ Phase 2 Step 5b: citation pass
□ Phase 2 Step 5c: AIDA-Path slot decision
□ Phase 2 Step 5e: reviewer-facing reproduction README
□ Phase 2 Step 5f: Abstract drafting (LAST)
□ Phase 2 Step 6: PI / advisor review
```

Per round 59: do NOT do citation pass / Abstract / AIDA-Path wording update yet. Apply-pass for table renumbering is the next step after round 60 review of this plan.
