# Plan v1.3.3 — BETA-2b CPE Equivalence and V3 Deferral Amendment

**Status:** Plan-only. Non-binding. Not adopted as canonical paper policy.
**Source HEAD when drafted:** `a08ebb3` (`origin/feature/gap-e-beta2-implementation`)
**Parent plans:**
- `docs/paper/integration/Plan_v1.3_GapE.md` (`3d5e014` on `main-v2.4-refactor`)
- `docs/paper/integration/Plan_v1.3.2_BETA2b_Patch.md` (`1bef878` on `feature/gap-e-beta2-implementation`)
**Frozen tag (must not move):** `paper-integration-v0.1 → c3b0a46`
**Engineering history branch (must not be merged into):** `main-v2.4-refactor → 3d5e014`
**Feature branch (this plan lives here):** `feature/gap-e-beta2-implementation → a08ebb3`
**Scope:** Post-CPE amendment recording BETA-2b code-path equivalence closure and V3 GPU full canonical deferral rationale.

---

## 0. Scope and non-execution status

This document is a **plan amendment**, not an execution. It records the verdict of the Round 132 BETA-2b code-path equivalence (CPE) audit and locks the rationale for deferring V3 GPU full canonical re-evaluation.

**Non-binding scope statement:**

> This plan does NOT modify any production code, manuscript file, or canonical metric artifact. It does NOT modify `src/`, `paper/`, `docs/paper/drafts/`, `docs/paper/repro/REPRODUCTION_README.md`, `results/analysis/metric_consistency_report.json`, or any committed BETA-2a / BETA-2b prediction artifact. It does NOT move the `paper-integration-v0.1` tag. It does NOT merge any artifact to `main-v2.4-refactor`. It does NOT adopt BETA-2b as canonical paper policy.

The single artifact produced by this plan is the present markdown file. Adoption of any policy or evidence statement in this plan is gated by the §6 path-forward sub-options and §7 trigger taxonomy.

**Relationship to Plan v1.3 and Plan v1.3.2:**

- Plan v1.3 (parent) is the high-level Gap E redesign gate.
- Plan v1.3.2 is the BETA-2b production patch implementation gate, including feature-flag spec, touch map, native-output invariants, projection-equivalence validation requirements, stacker dependency analysis, and rollback / fail-loud criteria.
- Plan v1.3.3 (this file) is a narrowly scoped amendment recording the closure of Plan v1.3.2 §6 V1+V2 smoke gate (Round 128) and §6.1 V4 equivalence (Round 132 CPE), plus the deferral status of §6.1 V3 GPU full canonical.

This amendment does NOT supersede Plan v1.3.2; it records its forward progress.

---

## 1. Accepted evidence ladder

The Gap E BETA-2b track has accumulated the following commit-cited evidence on `origin/feature/gap-e-beta2-implementation`:

| Round | Commit | Subject | Meaning |
|---|---|---|---|
| 118 | `d446836` | docs(paper): audit Round 114 canonical run isolation | Upstream drift isolated — 5775/5775 upstream fields bit-identical between Round 114 BETA-2a canonical and paper-integration-v0.1 baseline; Plan v1.3 §3 clauses #1, #4 identified as not yet implemented (veto path active) |
| 120 | `a960616` | results(gap-e): BETA-2b CPU projection (primary-locked, 6 modes) | BETA-2b CPU projection generated; 5775 records transformed under primary-locked policy |
| 120 | `082c3f9` | docs(paper): audit BETA-2b CPU projection convergence | Projection convergence verified — all 6 invariants × 6 modes pass (5775/5775); sandbox R3-α convergence within ±2pp; LingxiDiag DSM-5 −5.9pp outlier resolved |
| 124 | `1bef878` | docs(paper): plan BETA-2b production patch | Production patch gate (Plan v1.3.2) — feature-flag spec `final_output_policy = "beta2b_primary_locked"`, touch map at hied.py:1430-1475, native-output invariants, stacker dependency analysis (NOT NEEDED), rollback / fail-loud criteria |
| 128 | `b1c4474` | feat(hied): add BETA-2b final-output policy behind feature flag | Feature flag implementation — production code patch landed on feature branch (config.py +1, hied.py +10, cli.py +2, artifacts.py +6, configs/overlays/final_output_beta2b.yaml NEW) |
| 128 | `ae413c4` | docs(paper): audit BETA-2b native smoke | V1 BETA-2b smoke + V2 default regression — 120/120 invariants × 6 modes; V2 byte-identical to BETA-2a; Both-mode pass-through preserved; projection equivalence 118/120 (vLLM `--enforce-eager` non-determinism on 2/120 cases) |
| 132 | `3482021` | refactor(hied): extract BETA-2b finalization helper | Production helper `apply_beta2b_finalization` extracted as module-level pure function; behavior-preserving refactor; helper importable for offline audit |
| 132 | `a08ebb3` | docs(paper): audit BETA-2b native offline equivalence | CPE audit — production helper output equals Round 120 CPU projection on 5775/5775 records; primary == diagnostician_ranked[0] 5775/5775; comorbid_diagnoses == [] 5775/5775; audit_comorbid present 5775/5775; upstream stacker-input fields preserved 5775/5775; Both ≡ ICD-10 1925/1925 |

**The main statement to lock:**

> Round 118 + Round 120 + Round 128 + Round 132 together establish that BETA-2b final-output policy effect is isolated from upstream inference drift, implemented behind a feature flag, smoke-tested in native execution, and matched by the production helper to the full 5775-record CPU projection.

---

## 2. CPE equivalence verdict

**BETA-2b CPE is accepted: production helper output equals Round 120 CPU projection on 5775/5775 records.**

This is **code-path equivalence**, not GPU re-run equivalence. Specifically:

- The Round 132 audit (commit `a08ebb3`) demonstrates that the production helper `apply_beta2b_finalization`, when applied offline to the cached BETA-2a Round 114 prediction records, produces output bit-identical to the Round 120 standalone CPU projection on (`primary_diagnosis`, `comorbid_diagnoses`, `audit_comorbid`, `schema_version`, `diagnostician_ranked`, `decision_trace.raw_checker_outputs`, `decision_trace.logic_engine_confirmed_codes`).
- The Round 118 isolation audit (commit `d446836`) demonstrates that the upstream LLM / checker / logic-engine fields between Round 114 BETA-2a canonical and the paper-integration-v0.1 baseline are byte-identical on all 5775 records, so the helper-applied transform is the only systematic difference.
- The Round 128 smoke audit (commit `ae413c4`) demonstrates that the in-pipeline native execution under feature flag produces output satisfying all V1 invariants on N=20 × 6 modes, with default-flag V2 regression byte-identical to BETA-2a.

**Boundary clarification:**

> CPU projection / helper-derived output is canonical-equivalent for evaluating the BETA-2b final-output policy effect, but it is not yet manuscript-canonical.

This distinction matters: §3 deferral and §5 manuscript adoption gate both depend on this boundary.

---

## 3. V3 GPU full canonical deferral rationale

**Verdict:** V3 full GPU canonical can be deferred.

**Precise wording (binding for plan trail):**

> V3 full GPU canonical can be deferred because it is no longer required to validate the final-output policy effect. V3 remains available if PI, reviewer, or submission policy requires a fresh end-to-end inference run.

**Rationale:**

The original purpose of V3 (per Plan v1.3.2 §6.1) was to validate that production-code native output reproduces the BETA-2b CPU projection at canonical scale (N=1000 LingxiDiag + N=925 MDD-5k × 3 modes each). Three independent evidence sources now substitute for V3:

- **CPE audit (Round 132)**: production helper output equals CPU projection on 5775/5775 records (full canonical N), verified offline.
- **Native smoke (Round 128)**: in-pipeline native execution under feature flag produces V1 invariant-satisfying output on N=20 × 6 modes; this provides the in-pipeline integration evidence that CPE alone does not.
- **Upstream isolation (Round 118)**: 5775/5775 upstream fields byte-identical between Round 114 BETA-2a canonical and paper-integration-v0.1 baseline, so the only systematic difference is the BETA-2b finalization step itself.

Together, these three substitute V3's validation purpose without requiring a fresh ~5-7 hr GPU run.

**Wording to avoid:**

- "V3 is unnecessary forever"
- "V3 is cancelled"
- "GPU validation is irrelevant"

V3 is **deferred, not erased**. If at any later round (e.g., during PI review, reviewer revisions, or submission policy clarification), a fresh end-to-end GPU run is requested, V3 remains a valid trigger per Plan v1.3.2 §10 trigger 2 ("Go run BETA-2b V3 full canonical (after V1+V2 pass)").

**Optional V3 reactivation triggers (non-exhaustive):**

- PI / advisor explicitly requests V3 for sign-off.
- A target submission venue requires fresh end-to-end inference for reproducibility verification.
- A reviewer query specifically about vLLM `--enforce-eager` non-determinism (the 2/120 V1 smoke divergence) requires expanded-N native validation.
- The cleanup branch (Round 130+ planning, separate track) requires V3 as part of paper-clean reproducibility scripts.

---

## 4. Stacker dependency closure

**Verdict:** Stacker retrain is closed as NOT NEEDED for Gap E only.

Per Plan v1.3.2 §7 analysis (using stacker `build_features.py` schema from `origin/clean/v2.5-eval-discipline`), the 31-feature stacker input vector decomposes as:

- Block 1 (12 dims): TF-IDF class probabilities — independent of `hied.py`
- Block 2 (5 dims): `decision_trace.diagnostician_ranked` confidences — preserved by BETA-2b (Plan v1.3.2 invariant I8)
- Block 3 (12 dims): `decision_trace.raw_checker_outputs.met_ratio` — preserved by BETA-2b (invariant I6)
- Block 4 (1 dim): `tfidf_top1_margin` — independent of `hied.py`
- Block 5 (1 dim): `dtv_abstain_flag` — computed upstream of veto block (preserved by upstream isolation, Round 118 CHECK B)

The Round 132 CPE audit (commit `a08ebb3`) re-confirmed at full canonical scale: BETA-2b modifies only the post-emission fields `primary_diagnosis`, `comorbid_diagnoses`, `audit_comorbid`, and `schema_version`. None of these are stacker input fields.

**Caveat (must remain in plan trail):**

> This does not resolve the older Gap A TF-IDF-only LGBM attribution-control blocker.

The Gap A blocker (Stage 0 stacker-training-infrastructure missing — `build_features.py` lives on `origin/clean/v2.5-eval-discipline` but not on `origin/feature/gap-e-beta2-implementation` or `origin/main-v2.4-refactor`) is independent of Gap E and remains unaddressed. It does not gate this plan, but it gates any future stacker re-evaluation. See Plan v1.3.2 §7.5 for full description.

---

## 5. Manuscript adoption gate

**This amendment does NOT trigger manuscript adoption.**

The following remain prohibited until the §6 path-forward gates clear:

```
❌ No §5.4 Table 4 update.
❌ No Abstract update.
❌ No §1-§7 source file modification.
❌ No Table 2 modification.
❌ No REPRODUCTION_README update.
❌ No metric_consistency_report.json update.
❌ No paper-integration-v0.1 tag movement (must remain at c3b0a46).
❌ No merge to main-v2.4-refactor (must remain at 3d5e014).
❌ No master branch modification (must remain at 3d3c079).
❌ No claim that BETA-2b is clinically validated.
❌ No claim that EM +40pp / Top-1 +1.7-5.9pp / mF1 changes are paper-canonical.
```

Adoption of BETA-2b as canonical paper policy requires:

1. **Manuscript-impact simulation completed** (which Table 4 values change; whether §5.4 / §7 / Abstract narrative shifts).
2. **PI / advisor sign-off obtained** (per Plan v1.3 §8 Gate 8.1 + 8.5).
3. **Explicit canonical-adoption trigger issued** by user.
4. **Updated table / prose / repro artifacts reviewed as one bundle** (no piecemeal manuscript edits).

The dependency order remains:

```
CPE acceptance (this plan) → manuscript-impact simulation → PI sign-off → manuscript-impact PR → new tag (paper-integration-v0.2)
```

---

## 6. Path-forward sub-options

After Plan v1.3.3 commit, the recommended next step is **NOT** GPU work, **NOT** main merge, and **NOT** manuscript edit. The recommended next step per Round 133 verdict is:

**Path α — Manuscript-impact simulation**

Trigger: `Go run manuscript-impact simulation for adopting BETA-2b.`

The simulation must answer (in chat or as an uncommitted markdown draft, not as a manuscript file edit):

1. Which Table 4 values change under BETA-2b adoption?
2. Does §5.4 dual-standard interpretation change? (If yes, in what direction.)
3. Does the DSM-5 v0 caveat strengthen, weaken, or shift?
4. Does F32 / F41 asymmetry discussion change? (Round 120 BETA-2b numbers showed asymmetry per-mode; Round 114 baseline numbers preserved.)
5. Does F42 recall discussion change?
6. Does Abstract need to stay unchanged? (Recommended: yes, unless EM is quantitatively cited.)
7. What exact files would need revision if PI approves adoption?
8. What is the smallest revision footprint that preserves narrative integrity?

**Path β — Defer all post-CPE work**

Trigger: `Hold BETA-2b canonical adoption pending PI/advisor verdict.`

Effect: Plan v1.3.3 commits and feature branch state is the resting state. No further work until PI input.

**Path γ — V3 reactivation**

Trigger: `Go run BETA-2b V3 full canonical (after V1+V2 pass).` (This is Plan v1.3.2 §10 trigger 2; reactivable from this plan.)

Effect: Run V3 GPU re-run on `feature/gap-e-beta2-implementation` for reproducibility validation. Estimated 5-7 hr GPU. Output: `results/gap_e_canonical_beta2b_<TS>/`. This is independent of the manuscript-impact simulation.

**Path δ — Cleanup branch planning**

Trigger: `Begin paper-clean branch USAGE_AUDIT.` (Per Round 115 Phase B + Round 130 sequencing.)

Effect: Start Round 130+ planning track for paper-clean branch on `master` or new branch, after Phase A (BETA-2b adoption) is closed. This is downstream of Path α + manuscript-impact PR + tag bump, not parallel to current state.

**Recommended next trigger (per Round 133 verdict):** Path α.

---

## 7. Trigger taxonomy for Plan v1.3.3 closure

The following are the canonical triggers for Plan v1.3.3 progression. Each is **explicit**; none is auto-fired.

| Trigger | Action authorized | When valid |
|---|---|---|
| `Go run manuscript-impact simulation for adopting BETA-2b` | Path α; produce simulation markdown (uncommitted or feature-branch-only) answering the 8 questions in §6 | After Plan v1.3.3 commit |
| `Hold BETA-2b canonical adoption pending PI/advisor verdict` | Path β; no-op | Any time |
| `Go run BETA-2b V3 full canonical (after V1+V2 pass)` | Path γ; reactivate V3 GPU re-run | Any time after smoke pass (already true) |
| `Begin paper-clean branch USAGE_AUDIT` | Path δ; start cleanup phase planning | After Phase A closure (BETA-2b canonical adoption + tag bump), not before |
| `Begin paper-integration-v0.2 adoption planning` | Authorize separate Plan v1.3.4 (or equivalent) for canonical adoption + manuscript-impact PR + tag bump | After manuscript-impact simulation completed (Path α) |
| `Close BETA-2b track — PI rejected` | Append v1.3.3.1 amendment recording rejection | If PI / advisor rejects BETA-2b adoption |

**Triggers NOT in this taxonomy require a new plan amendment (v1.3.3.1 or v1.3.4).**

The following are explicitly NOT triggers under Plan v1.3.3:

- Adopting BETA-2b numbers as paper canonical based on CPE alone (without PI sign-off).
- Updating Abstract / §5.4 Table 4 / REPRODUCTION_README from BETA-2b numbers.
- Merging `feature/gap-e-beta2-implementation` to `main-v2.4-refactor` without separate authorization.
- Force-pushing `main-v2.4-refactor` or `master` under any circumstance.
- Running BETA-1 (multi-label benchmark output) experiments — hard-forbidden per Plan v1.3.2 §1.4.
- Modifying stacker code or retraining the stacker (per §4 verdict above; Gap A blocker is separate).
- Starting cleanup-phase / paper-clean-branch work — defer to Path δ per ordering above.

---

## End of Plan v1.3.3

This amendment was drafted at `feature/gap-e-beta2-implementation @ a08ebb3`. It will be committed as a single new file at `docs/paper/integration/Plan_v1.3.3_BETA2b_CPE_deferral.md` with no other tree changes.

To revisit or amend this plan, create `Plan_v1.3.3.1_BETA2b_CPE_amendment.md` referencing this file. Do NOT in-place edit this file after commit.
