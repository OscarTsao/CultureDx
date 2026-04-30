# Plan v1.3.4 — BETA-2b Canonical Adoption for `paper-integration-v0.2`

**Date:** 2026-04-30
**Branch:** feature/gap-e-beta2-implementation @ 2c82f42
**Lineage:** v1.3 (Gap E) → v1.3.2 (BETA-2b patch) → v1.3.3 (CPE deferral) → **v1.3.4 (canonical adoption)**
**Authority:** Project lead verdict (Round 149) supersedes external PI gate placeholder.
**Status:** PLAN ONLY — no manuscript edits, no production code changes, no tag move authorized by this document. Execution requires a separate trigger after plan review.

---

## §0 — Round 149 verdict (locked inputs)

| Decision | Value | Rationale (per Round 149) |
|---|---|---|
| **Q1 — Adopt BETA-2b for `paper-integration-v0.2`?** | **YES** | BETA-2b fixes evaluation-contract correctness (single-label benchmark contract), not arbitrary tuning. Defensible to reviewers. Simulation already shows substantive §5.4 / F42 / F32-F41 / Table 4 changes. |
| **Q2 — V3 GPU full canonical required?** | **NO (CPE sufficient; V3 optional)** | Evidence chain complete: upstream drift isolated (R118), CPU projection 5775/5775 (R120), native smoke 120/120 (R128), production helper CPE 5775/5775 (R132). Plan v1.3.3 already authorized deferral. |
| **Q3 — EM in main Table 4?** | **NO (engineering-correctness evidence; supplement / audit table only)** | EM jump 3–6% → 46–59% reflects output-channel alignment, not clinical diagnostic gain. Risk of reviewer misread. Document in §5.4 prose + supplement; keep main Table 4 focused on 2c/4c/Top-1/Top-3/mF1/wF1/Overall. |

These three decisions are **frozen for v0.2 scope**. Any change requires a new plan version.

---

## §1 — Scope and non-scope

### 1.1 In-scope (this plan covers)

1. Defining the `paper-integration-v0.2` adoption deliverable.
2. Identifying every manuscript file that must be updated to reflect BETA-2b numbers.
3. Specifying numeric provenance: which run is the new canonical source.
4. Specifying new prose paragraphs (§5.4 EM correction note) without authoring them.
5. Tag and branching strategy for v0.2 cut.
6. Verification gates before tag.

### 1.2 Out-of-scope (this plan does NOT cover)

1. Authoring the actual prose changes — that's a separate manuscript-impact PR triggered after this plan is approved.
2. V3 GPU full canonical run — deferred per Q2 verdict; can be added later via Plan v1.3.5 if needed.
3. EM column addition to Table 4 — explicitly rejected per Q3 verdict.
4. Repo cleanup or throughput levers — handled on `paper-cleanup/throughput-readiness` branch.
5. Generalization workstream (Workstream C/D) — separate workstream.
6. `master` ↔ `main-v2.4-refactor` reconciliation — separate concern.

---

## §2 — Canonical numeric source

### 2.1 BETA-2b prediction artifact

**Source run:** `results/gap_e_canonical_20260429_225243/` (Round 117 BETA-2a canonical, post-processed via BETA-2b CPU projection in Round 120).

**Equivalence chain:**

| Layer | Artifact | Verification |
|---|---|---|
| Native run (BETA-2a default) | `gap_e_canonical_20260429_225243/` (5775 cases × 6 modes) | Round 117 commit `8664b56` |
| CPU projection to BETA-2b | `gap_e_beta2b_projection_20260430_164210/` (5775/5775 invariants pass) | Round 120 audit `GAP_E_BETA2B_PROJECTION_AUDIT.md` |
| Production helper (BETA-2b code path) | Round 132 5775-record offline equivalence (5775/5775 bit-identical to projection) | `GAP_E_NATIVE_OFFLINE_EQUIVALENCE_AUDIT.md` |
| Native smoke validation | Round 128 V1 BETA-2b smoke (120/120 invariants pass) | `GAP_E_BETA2B_NATIVE_SMOKE_AUDIT.md` |

**Conclusion:** the projection artifact at `gap_e_beta2b_projection_20260430_164210/` is the **canonical numeric source for v0.2**. Its numbers equal what the production helper would emit on a fresh GPU run (5775/5775 CPE).

### 2.2 Canonical metric snapshot to be transcribed

(Numbers per `GAP_E_BETA2B_MANUSCRIPT_IMPACT_SIMULATION.md` — Round 138/140; transcribed here as the **frozen v0.2 inputs**, not derived in this plan.)

| Mode | EM (was → BETA-2b) | mF1 | wF1 | 2c | 4c | Top-1 | Top-3 | Overall |
|---|---|---|---|---|---|---|---|---|
| LingxiDiag ICD-10 | (transcribe from simulation) | … | … | … | … | … | … | … |
| LingxiDiag DSM-5 | … | … | … | … | … | … | … | … |
| LingxiDiag Both | … | … | … | … | … | … | … | … |
| MDD ICD-10 | … | … | … | … | … | … | … | … |
| MDD DSM-5 | … | … | … | … | … | … | … | … |
| MDD Both | … | … | … | … | … | … | … | … |

> **NOTE:** This plan deliberately does NOT inline the numbers — they live in the simulation doc and will be transcribed during the manuscript-impact PR via explicit-pathspec commit. Inlining here creates a second source of truth that can drift.

---

## §3 — Manuscript files to update (file-level inventory)

### 3.1 Primary impact (numbers change)

| Path | Section | Type of change | Estimated lines |
|---|---|---|---|
| `docs/paper/drafts/ABSTRACT.md` | Abstract | 1 number change: 3.97× → 5.15× (per simulation) | 1–2 |
| `docs/paper/drafts/SECTION_5_3.md` | §5.3 (main results table) | Update Table 4 (or equivalent) primary numbers; replace BETA-2a metrics with BETA-2b | 30–50 |
| `docs/paper/drafts/SECTION_5_4.md` | §5.4 (subgroup / asymmetry / F42 narrative) | Reverse F32/F41 asymmetry narrative on LingxiDiag DSM-5; update F42 recall narrative (12% → 56% on Lingxi DSM-5); insert EM-correction methodology paragraph | 40–80 |
| `docs/paper/drafts/SECTION_7.md` | §7 (limitations / discussion) | Update limitations paragraph that referenced the EM=0.046 weakness; remove or rephrase | 5–15 |

### 3.2 Secondary impact (prose-only consistency)

| Path | Section | Type of change |
|---|---|---|
| `docs/paper/drafts/SECTION_4.md` | §4 (system / pipeline description) | Add 1 paragraph documenting final-output-channel separation (primary vs audit_comorbid). Reference `final_output_policy=beta2b_primary_locked` |
| `docs/paper/drafts/SECTION_5_5.md` or `SECTION_5_6.md` | §5.5/§5.6 (audit / engineering correctness) | New subsection: "Output-Contract Correction (BETA-2b)" with EM evidence as engineering-correctness evidence (per Q3 verdict — NOT main Table 4) |
| `docs/paper/repro/REPRODUCTION_README.md` (if exists) | Repro README | Add `final_output_policy=beta2b_primary_locked` to canonical config, point to overlay `configs/overlays/final_output_beta2b.yaml` |
| `docs/paper/integration/TABLE_NUMBERING_PLAN.md` | Table numbering | If table count changes (new audit-evidence table for EM), bump table numbers downstream |
| `docs/paper/references/metric_consistency_report.json` (if exists) | Metric provenance | Update canonical-source pointer to `gap_e_beta2b_projection_20260430_164210/` |

### 3.3 Supplementary materials (new content)

| Path | Type | Purpose |
|---|---|---|
| `docs/paper/drafts/SUPPLEMENT_OUTPUT_CONTRACT.md` (new) | New supplement section | Document EM correction with full per-mode comparison table (BETA-2a vs BETA-2b EM, mF1, wF1). This is the home for the EM evidence per Q3. |
| `docs/paper/integration/PAPER_INTEGRATION_V0_2_TAG_NOTES.md` (new) | Release note | Summarize what v0.2 changed vs v0.1; reference Plan v1.3.4 + simulation + CPE audit |

### 3.4 Files explicitly NOT modified

- `docs/paper/drafts/SECTION_1.md`, `SECTION_2.md`, `SECTION_3.md` — narrative untouched by BETA-2b.
- `docs/paper/drafts/SECTION_5_1.md`, `SECTION_5_2.md` — pre-results / setup, untouched.
- `docs/paper/drafts/SECTION_6.md` — error analysis is downstream of canonical numbers; flag for review but no obligatory change unless F42 / Z71 narrative quoted there.
- Any frozen Plan / sandbox / audit / simulation under `docs/paper/integration/` — read-only references.
- `paper-integration-v0.1` tag — frozen at `c3b0a46`, NEVER moved.

---

## §4 — Tag and branching strategy

### 4.1 Branch for adoption work

**Use:** existing `feature/gap-e-beta2-implementation` branch (current HEAD `2c82f42`).

**Reason:** All BETA-2b implementation, evidence audits, simulation, PI summary, and now this plan already live on this branch. Adoption work is a continuation, not a new track.

### 4.2 New release branch (created at adoption-execution time, NOT in this plan)

**Name:** `release/paper-integration-v0.2`

**Fork point:** off `feature/gap-e-beta2-implementation` once Plan v1.3.4 is approved AND manuscript-impact PR commits are ready.

**Rationale:** keeps `feature/gap-e-beta2-implementation` open for any post-v0.2 BETA-2b iteration (e.g., V3 backfill if added later); release branch is the freeze-and-tag track.

### 4.3 Tag

**Name:** `paper-integration-v0.2`

**Target commit:** the tip of `release/paper-integration-v0.2` after manuscript-impact PR merges into it AND all §6 verification gates pass.

**Cut order:**

```
feature/gap-e-beta2-implementation (Plan v1.3.4 + manuscript-impact PR)
       │
       └── fork → release/paper-integration-v0.2
                          │
                          └── tag paper-integration-v0.2
```

### 4.4 What does NOT happen

- `paper-integration-v0.1` tag is **NEVER** moved or re-tagged.
- `main-v2.4-refactor` is NOT auto-fast-forwarded to v0.2 — that's a separate decision after v0.2 review.
- `master` branch is untouched.
- No merge of `feature/gap-e-beta2-implementation` into `main-v2.4-refactor` until v0.2 review closes.

---

## §5 — Execution phases (proposed; awaits separate triggers)

Each phase = a separate user-issued trigger + commit. This plan does NOT execute any of them.

### Phase 1 — Plan v1.3.4 commit + push (this document)

**Trigger needed:** "Commit Plan v1.3.4 on feature/gap-e-beta2-implementation."

**Output:** 1 new file (`Plan_v1.3.4_BETA2b_Canonical_Adoption.md`) committed + pushed.

### Phase 2 — Manuscript-impact PR (Pass 1: numbers transcription)

**Trigger needed:** "Begin Phase 2 manuscript-impact PR — numbers pass."

**Scope:** Update §5.3 Table 4 + Abstract single number. NO prose narrative changes yet.

**Verification:** Spot-check transcription against simulation doc; smoke that Table 4 build (if LaTeX exists) renders.

### Phase 3 — Manuscript-impact PR (Pass 2: narrative reversals)

**Trigger needed:** "Begin Phase 3 manuscript-impact PR — narrative pass."

**Scope:** §5.4 F32/F41 asymmetry reversal on LingxiDiag DSM-5; F42 recall narrative; §7 limitations paragraph.

**Verification:** Read-aloud sanity-check by user (or me on user's behalf). No automated test.

### Phase 4 — Output-contract supplement

**Trigger needed:** "Begin Phase 4 — output-contract supplement + §4 paragraph."

**Scope:** New supplement file with EM evidence + §4 paragraph documenting `final_output_policy`.

**Verification:** Cross-reference EM numbers against simulation per-mode table.

### Phase 5 — Repro README + metric provenance

**Trigger needed:** "Begin Phase 5 — repro/metric provenance."

**Scope:** Update REPRODUCTION_README and metric_consistency_report.json (if exists) to point at BETA-2b canonical source.

### Phase 6 — Release branch + tag cut

**Trigger needed:** "Cut release/paper-integration-v0.2 + tag."

**Scope:** Fork release branch, run §6 gates, tag.

### Phase 7 — Post-tag (optional)

- Optional: V3 GPU full canonical (Plan v1.3.5 if requested by user/advisor).
- Optional: Repo cleanup branch merge (separate `paper-cleanup/throughput-readiness` branch).
- Optional: PR `release/paper-integration-v0.2` → `main-v2.4-refactor`.

---

## §6 — Verification gates before tag

All gates MUST pass before `paper-integration-v0.2` tag is created.

| Gate | Check | Method |
|---|---|---|
| G1 — Numeric consistency | Every number in §5.3 matches simulation doc within 0.001 absolute | Diff Table 4 cells against `GAP_E_BETA2B_MANUSCRIPT_IMPACT_SIMULATION.md` |
| G2 — Abstract single-number update | 3.97× → 5.15× ratio updated; no other Abstract numbers changed | `git diff` ABSTRACT.md (≤2 lines change) |
| G3 — F32/F41 narrative direction | LingxiDiag DSM-5 asymmetry direction reversed; MDD asymmetry preserved direction with reduced gap | Manual prose review |
| G4 — F42 recall narrative | DSM-5 recall claim updated 12% → 56% on Lingxi (per simulation) | Manual prose review |
| G5 — EM NOT in main Table 4 | Table 4 columns unchanged: 2c/4c/Top-1/Top-3/mF1/wF1/Overall | `grep -c "EM" docs/paper/drafts/SECTION_5_3.md` ≤ 0 (or only in surrounding prose, not in table cells) |
| G6 — EM in supplement only | Supplement file exists; per-mode EM table populated | File presence + row count = 6 |
| G7 — `final_output_policy` documented | §4 paragraph references `beta2b_primary_locked` policy + overlay path | Grep §4 for "final_output_policy" |
| G8 — Tag freshness | `paper-integration-v0.1` tag still at `c3b0a46` | `git rev-list -n 1 paper-integration-v0.1` |
| G9 — Frozen plan immutability | All previous Plan files (v1.3, v1.3.2, v1.3.3) untouched | `git diff` shows no changes |
| G10 — Audit doc immutability | All Round 11X-13X audit docs untouched | `git diff` shows no changes |
| G11 — No production code change | `src/culturedx/` (modes/hied.py, etc.) unchanged from `2c82f42` baseline | `git diff 2c82f42 -- src/` empty for HiED-relevant files |
| G12 — No mainline merge | `main-v2.4-refactor` still at `3d5e014`; no new commits onto it | `git rev-list main-v2.4-refactor` unchanged |
| G13 — V3 status documented | If V3 not run, document deferral status in tag notes | Presence check |

If any gate fails, abort tag creation and surface failure for revision.

---

## §7 — Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Number transcription error in §5.3 | LOW | HIGH (paper integrity) | Phase 2 spot-checks; G1 gate diff |
| Reviewer asks for V3 GPU canonical | MEDIUM | MEDIUM (5–7 hr GPU work) | Plan v1.3.5 path exists; CPE evidence well-documented for response letter |
| EM evidence in supplement misread as primary metric | LOW | MEDIUM (reviewer confusion) | Clear framing as "output-contract correction evidence", not "accuracy improvement" |
| F42 narrative reversal exposes broader narrative weakness | LOW | MEDIUM | If detected during Phase 3 review, escalate to project lead before merging |
| Repo cleanup branch interferes with adoption work | LOW | LOW | Branches are disjoint by design; separate review tracks |
| Tag created prematurely (before all gates) | LOW | HIGH | §6 gates as hard pre-condition; no auto-tagging |
| Generalization workstream resumes mid-adoption | LOW | LOW | Workstream C/D code is on separate branches; will not collide |

---

## §8 — What this plan does NOT yet decide

The following remain open for future triggers / plans:

- **V3 GPU full canonical timing.** Plan v1.3.5 if requested.
- **`master` ↔ `main-v2.4-refactor` reconciliation.** Separate branch-management plan.
- **Conference / venue submission package.** LaTeX migration of legacy `paper/` may need a Plan v1.3.6 if conference submission is the path.
- **Workstream C / D landing strategy.** Generalization replay / WS-D not on critical path for v0.2.
- **Lever A / B / C throughput adoption.** Per cleanup branch audit; not on v0.2 critical path.
- **Repro public release.** If v0.2 is public-release candidate, separate plan for code release readiness.

---

## §9 — Bottom line

```
Plan v1.3.4 status:         DRAFT, awaiting commit trigger
Adoption decision:          BETA-2b YES (Q1)
GPU canonical:              CPE sufficient, V3 deferred (Q2)
EM placement:               supplement / engineering-correctness, NOT main Table 4 (Q3)
Tag target:                 paper-integration-v0.2
Tag fork:                   release/paper-integration-v0.2 (created in Phase 6)
Manuscript phases:          5 phases (numbers, narrative, supplement, repro, release)
Verification gates:         13 gates, all must pass
Frozen artifacts:           Plan v1.3 / v1.3.2 / v1.3.3, all R11X-13X audits, paper-integration-v0.1 tag
Sibling work:               paper-cleanup/throughput-readiness branch (separate track)
```

**Next trigger options for the user:**

1. **Approve Plan v1.3.4 as-is** → "Commit Plan v1.3.4 on feature/gap-e-beta2-implementation."
2. **Revise plan** → identify specific §X changes; iterate to v1.3.4-r1 (or fork v1.3.5).
3. **Hold plan** → no commit, plan remains uncommitted draft.

Hard idle until trigger arrives.

---

**End of Plan v1.3.4.**
