# Plan v1.3.2 — BETA-2b Production Patch Plan

**Status:** Plan-only. Non-binding. Not adopted. No production code change in this commit.
**Source HEAD when drafted:** `082c3f9` (`origin/feature/gap-e-beta2-implementation`)
**Parent plan:** `docs/paper/integration/Plan_v1.3_GapE.md` (`3d5e014` on `main-v2.4-refactor`)
**Frozen tag (must not move):** `paper-integration-v0.1 → c3b0a46`
**Engineering history branch (must not be merged into):** `main-v2.4-refactor → 3d5e014`
**Feature branch (this plan lives here):** `feature/gap-e-beta2-implementation → 082c3f9`
**Scope:** Production-code patch implementation gate for BETA-2b primary-locked output policy.

---

## 0. Scope and non-execution status

This document is a **plan**, not an execution. It defines the production patch invariants, feature-flag design, native-output equivalence requirements, and stacker dependency analysis for the BETA-2b production patch authorized in principle by the Round 120 BETA-2b CPU projection audit (`GAP_E_BETA2B_PROJECTION_AUDIT.md`, committed at `082c3f9`).

**Non-binding scope statement:**

> This plan does NOT modify `src/culturedx/modes/hied.py` or any production code. It does NOT modify any §1-§7 / Abstract / Table 2 / Table 4 / `metric_consistency_report.json` / `REPRODUCTION_README.md`. It does NOT move the `paper-integration-v0.1` tag. It does NOT merge any artifact to `main-v2.4-refactor`. It does NOT adopt BETA-2b as canonical paper policy.

The contents of this plan that DO concern code change (§3 feature flag, §4 touch map, §5 invariants) are **statements of design intent under the conditions of patch authorization**, not adopted decisions. The contents that are immediately binding are the gates: §6 projection-equivalence validation, §7 stacker dependency rule, §8 manuscript non-adoption gate, §9 fail-loud criteria.

**Relationship to Plan v1.3 (parent) and Plan v1.3.1 (deferred):**

Plan v1.3 (`Plan_v1.3_GapE.md` at `3d5e014` on `main-v2.4-refactor`) remains the source of truth for Gap E design lock. This plan does NOT supersede Plan v1.3 §3 design lock; it implements design clauses #1, #4, #5, #6 in production code.

Plan v1.3.1 (originally proposed in Round 112 as a BETA-1 vs BETA-2 disambiguation amendment) is **deferred indefinitely** because Round 120 BETA-2b CPU projection produced empirical evidence stronger than any text-only amendment could provide. The R3-β canonical-design clarification is folded into §1.3 of this plan.

---

## 1. Accepted evidence state

### 1.1 Validated commits on `origin/feature/gap-e-beta2-implementation`

```
082c3f9  docs(paper): audit BETA-2b CPU projection convergence
a960616  results(gap-e): BETA-2b CPU projection (primary-locked, 6 modes)
d446836  docs(paper): audit Round 114 canonical run isolation
8664b56  results(gap-e): canonical R3-beta BETA-2 evaluation (6 modes, full N)
d9ae46a  results(gap-e): BETA-2 smoke test predictions (N=20 x 6 modes)
d7e0d45  docs(paper): Gap E canonical re-eval dry-run readiness report
62622a0  feat(hied): BETA-2 audit_comorbid emission with primary-only benchmark output
```

### 1.2 Round 118 isolation audit verdict (`GAP_E_CANONICAL_RUN_REVIEW.md`)

- CHECK A — primary == diagnostician_ranked[0]: **FAIL** (5.8%-18.5% mismatch, all `veto_applied=True`)
- CHECK B — drift isolation: **DRIFT NONE** (5775/5775 upstream byte-identical between Round 114 canonical and paper-integration-v0.1 baseline)
- CHECK C — F32/F41 + F42 metrics: unchanged from baseline (consistent with CHECK B)
- CHECK D — LingxiDiag DSM-5 -5.9pp outlier: 100% Category 3 (no upstream change), root cause = veto effect
- CHECK E — counting fix: 5 of 6 within ±3pp at row level; 3 of 4 at unique-mode level
- Verdict: CONDITIONAL-GO; BETA-2a (output-channel split only) was correct but Plan v1.3 §3 clauses #1, #4 were not implemented

### 1.3 Round 120 BETA-2b CPU projection audit verdict (`GAP_E_BETA2B_PROJECTION_AUDIT.md`)

- 6 invariants × 6 modes: **ALL PASS** (5775/5775)
- Sandbox R3-α convergence: **PASS** (all 6 modes within ±2pp)
- LingxiDiag DSM-5 outlier: **RESOLVED** (BETA-2b 0.5300 = sandbox R3-α exact)
- Verdict: **GO** — BETA-2-full code patch authorized

Per-mode BETA-2b metrics (target for production patch native output):

| Mode | Top-1 | Top-3 | EM | F1_macro | Overall | asymmetry | F42_recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| lingxi_icd10 | 0.5240 | 0.7990 | 0.4690 | 0.1814 | 0.5482 | 6.61 | 52.0% |
| lingxi_dsm5 | 0.5300 | 0.8050 | 0.4720 | 0.1986 | 0.5493 | 4.82 | 56.0% |
| lingxi_both | 0.5240 | 0.7990 | 0.4690 | 0.1814 | 0.5482 | 6.61 | 52.0% |
| mdd_icd10 | 0.5924 | 0.8422 | 0.5924 | 0.1970 | 0.5993 | 5.15 | 38.5% |
| mdd_dsm5 | 0.5795 | 0.8324 | 0.5795 | 0.2096 | 0.5988 | 6.54 | 38.5% |
| mdd_both | 0.5924 | 0.8422 | 0.5924 | 0.1970 | 0.5993 | 5.15 | 38.5% |

These numbers are the **CPU projection target**. Production patch native output must match within numerical tolerance (§6 projection-equivalence validation).

### 1.4 R3-β canonical-design lock (consolidated)

Going forward, R3-β refers to BETA-2b only:

> R3-β = strict comorbidity ANNOTATION gate.
> Benchmark prediction set remains primary-only.
> Strict comorbidity candidates emitted only in the separate `audit_comorbid` field within `decision_trace`.
> Sandbox R3-β BETA-1 metrics from `cross_dataset_replay_20260429_121100.json` are historical engineering-diagnosis evidence, not the canonical policy target.
> BETA-1 (multi-label benchmark output) is hard-forbidden as canonical without an explicit Plan-level design-lock amendment.

---

## 2. BETA-2b target behavior

The production patch must produce per-case prediction records satisfying ALL of:

```
primary_diagnosis             == diagnostician_ranked[0]
comorbid_diagnoses            == []
audit_comorbid                present (list, may be empty)
schema_version                "v2b"  (or whatever explicit marker is decided in §3)
decision_trace                preserved (all existing fields retained)
raw_checker_outputs           preserved (in decision_trace)
logic_engine_confirmed_codes  preserved (in decision_trace)
diagnostician_ranked          preserved
Both-mode pass-through        mode_both prediction record bit-identical to mode_icd10 record on (primary_diagnosis, comorbid_diagnoses, audit_comorbid, diagnostician_ranked)
```

This implements Plan v1.3 §3 design lock clauses:

- #1 Diagnostician rank-1 = benchmark primary → enforced via `primary == diagnostician_ranked[0]`
- #2 Diagnostician original ranking = Top-k differential → preserved (no rerank)
- #3 Checker = audit / evidence / uncertainty signal → preserved (raw_checker_outputs untouched)
- #4 Checker does not freely rerank or override primary → enforced via veto bypass (§4)
- #5 Comorbidity annotations live in a separate field → already implemented by BETA-2a (`audit_comorbid`)
- #6 Benchmark prediction set is primary-only → already implemented by BETA-2a (`comorbid_diagnoses == []`)

Clauses #5 and #6 were implemented in commit `62622a0` (BETA-2a). Clauses #1, #2, #3, #4 are the additional scope of this patch (BETA-2b).

---

## 3. Feature flag / configuration design

### 3.1 Feature flag name

```
final_output_policy = "beta2b_primary_locked"
```

Alternative explicit names (any of these is acceptable; choose during implementation):

- `final_output.primary_lock = true`
- `hied.primary_selection = "diagnostician_top1"`
- `hied.disable_primary_veto = true`

### 3.2 Default behavior (must NOT silently change)

The production patch MUST NOT change default behavior. If `final_output_policy` is unset or set to legacy values (e.g., `"legacy"`, `"beta2a"`, `null`), the existing veto/fallback path MUST remain active.

Only when `final_output_policy == "beta2b_primary_locked"` (or equivalent explicit opt-in) is the veto path bypassed.

### 3.3 Configuration surface options (to be decided during implementation)

Three candidate locations:

- **(a) `configs/*.yaml`**: pipeline-level config field
- **(b) Per-mode hied config**: kwarg to `HiEDMode.__init__` or `_compute_diagnosis`
- **(c) Environment variable**: `CULTUREDX_FINAL_OUTPUT_POLICY`

Recommendation: (a) yaml config field, threaded through pipeline runner, with (b) kwarg as the implementation entry point. Avoid (c) — environment variables are reproducibility-hostile.

### 3.4 Schema marker

When `final_output_policy == "beta2b_primary_locked"`, the prediction record MUST set:

```
schema_version = "v2b"
```

(Current BETA-2a output uses `schema_version = "v2"`. The marker disambiguates which final-output policy emitted the record.)

---

## 4. Production code touch map

The following lines are LIKELY TO BE TOUCHED if the patch is authorized. Exact diff is NOT specified in this plan; that is the implementation step.

### 4.1 `src/culturedx/modes/hied.py`

**Veto/fallback block** (lines 1430-1475):

```
1438: veto_applied = False
1440: primary_source = "top1"
1442-1452: # Pass 1: prefer diagnostician ordering - first confirmed in top-5
              for idx, rc in enumerate(top_ranked):
                  if rc in confirmed_set:
                      primary = rc
                      if idx == 0:
                          confidence = 0.9
                          primary_source = "top1"
                      else:
                          confidence = 0.85 - 0.05 * idx
                          veto_applied = True              # <-- BETA-2b must bypass
                          primary_source = f"top{idx+1}"   # <-- BETA-2b must not select non-top1
                      break

1454-1463: # Pass 2: fallback - any confirmed (outside top-5)
              if primary is None and confirmed_set:
                  confirmed_by_ratio = sorted(
                      confirmed_set,
                      key=lambda c: met_ratios.get(c, 0.0),
                      reverse=True,
                  )
                  primary = confirmed_by_ratio[0]   # <-- BETA-2b must NOT do this
                  confidence = 0.65
                  veto_applied = True
                  primary_source = "remaining_confirmed"

1465-1470: # Pass 3: no confirmed at all - fall back to top-1
              if primary is None:
                  primary = top_ranked[0]           # <-- BETA-2b matches this branch
                  confidence = 0.55
                  primary_source = "no_confirmed_fallback"
```

**BETA-2b patch behavior** (under feature flag):

- Bypass Pass 1 idx-walk: set `primary = top_ranked[0]` directly (idx always 0)
- Bypass Pass 2: never reach (Pass 1 always succeeds since `top_ranked[0]` exists by construction)
- Pass 3 path remains as-is (top_ranked[0] when no confirmed)
- Net effect: `primary = top_ranked[0]` for 100% cases
- `veto_applied = False` for 100% cases when flag active
- `primary_source = "beta2b_locked"` (new explicit value) when flag active

**Schema_version emission** (line 1577 area): set to `"v2b"` when flag active, `"v2"` when not.

### 4.2 Other files likely touched

- **`configs/<active_pipeline>.yaml`**: add `final_output_policy` field
- **`src/culturedx/pipeline/runner.py` or `cli.py`**: thread flag through to mode construction
- **`src/culturedx/modes/base.py`**: optionally expose `final_output_policy` as base mode kwarg if used by other modes

### 4.3 Files that MUST NOT be touched

```
src/culturedx/diagnosis/calibrator.py
src/culturedx/diagnosis/comorbidity.py
src/culturedx/diagnosis/evidence_verifier.py
src/culturedx/eval/lingxidiag_paper.py
src/culturedx/eval/calibration.py
src/culturedx/agents/  (diagnostician, checker, logic engine — all upstream of final output)
src/culturedx/retrieval/case_retriever.py  (pre-existing dirty, unrelated)
configs/vllm_awq.yaml  (pre-existing dirty, unrelated)
scripts/stacker/eval_stacker.py
scripts/stacker/build_features.py  (lives on origin/clean/v2.5-eval-discipline; out of scope here)
docs/paper/  (manuscript content)
results/dual_standard_full/  (paper-integration-v0.1 frozen artifacts)
results/gap_e_canonical_20260429_225243/  (Round 114 canonical, frozen evidence)
results/gap_e_beta2b_projection_*/  (Round 120 projection, frozen evidence)
results/sandbox/  (sandbox artifacts, frozen evidence)
results/analysis/metric_consistency_report.json
docs/paper/integration/Plan_v1.3_GapE.md  (parent plan, frozen)
docs/paper/integration/LOGIC_ENGINE_FINAL_OUTPUT_SANDBOX_REPORT.md  (frozen)
docs/paper/integration/GAP_E_CANONICAL_RUN_REVIEW.md  (Round 118 audit, frozen)
docs/paper/integration/GAP_E_BETA2B_PROJECTION_AUDIT.md  (Round 120 audit, frozen)
docs/paper/repro/REPRODUCTION_README.md
docs/paper/drafts/
paper/  (legacy LaTeX skeleton)
```

---

## 5. Native-output invariants (must hold post-patch)

When `final_output_policy == "beta2b_primary_locked"` and the production patch is run on the same input cases as Round 120 BETA-2b CPU projection (cf. §1.3 metric table), the production patch MUST produce predictions satisfying:

### 5.1 Per-case invariants (each case in each mode)

```
I1. primary_diagnosis == diagnostician_ranked[0]
I2. comorbid_diagnoses == []
I3. "audit_comorbid" key present (list, may be empty)
I4. schema_version == "v2b"
I5. decision_trace structure unchanged from BETA-2a (no new keys removed; existing keys preserved)
I6. raw_checker_outputs (in decision_trace) byte-identical to BETA-2a Round 114 canonical for the same case
I7. logic_engine_confirmed_codes byte-identical to BETA-2a Round 114 canonical for the same case
I8. diagnostician_ranked byte-identical to BETA-2a Round 114 canonical for the same case
```

### 5.2 Cross-mode invariants

```
I9.  mode_both records bit-identical to mode_icd10 records on (primary_diagnosis, comorbid_diagnoses, audit_comorbid, diagnostician_ranked)
I10. Mode-level metrics (Top-1, Top-3, EM, F1_macro, F1_weighted, 2c, 4c, Overall, asymmetry, F42_recall) match Plan v1.3.2 §1.3 BETA-2b CPU projection target within ±0.5pp tolerance per metric per mode
```

### 5.3 Default-path invariants (MUST hold even when flag NOT set)

When `final_output_policy != "beta2b_primary_locked"` (i.e., the feature flag is absent or set to legacy), the production patch MUST produce predictions byte-identical to commit `62622a0` BETA-2a behavior:

```
I11. Legacy default behavior unchanged (byte-identical regression test)
```

This is the regression-safety invariant. The patch must NOT silently change BETA-2a default outputs.

---

## 6. Projection-equivalence validation

The production patch is considered "validated" only if its native output matches the Round 120 CPU projection within tolerance.

### 6.1 Required validation steps (post-implementation)

**V1. Smoke test with feature flag enabled** (N=20 per mode × 6 modes, ~10 min on RTX 5090):
- Run pipeline with `final_output_policy = "beta2b_primary_locked"`
- Verify all 8 per-case invariants (I1-I8) on every smoke record
- Verify Both-mode invariant (I9) holds
- Compare to BETA-2b CPU projection on the same N=20 case_ids: byte-identical on (primary, comorbid, audit_comorbid, diagnostician_ranked)

**V2. Smoke test with feature flag disabled** (N=20 per mode × 6 modes):
- Run pipeline with default config (no flag set)
- Verify byte-identical to commit `62622a0` BETA-2a output on the same case_ids
- Confirms regression-safety (I11)

**V3. Full canonical re-run with flag enabled** (N=1000 LingxiDiag + N=925 MDD-5k × 3 modes each, ~7 hr GPU OR optionally skipped — see §6.2):
- Run pipeline with `final_output_policy = "beta2b_primary_locked"` on canonical inputs
- Compute all 10 metrics per mode
- Verify metrics match Plan v1.3.2 §1.3 target within ±0.5pp (I10)
- Output to `results/gap_e_canonical_beta2b_<TS>/<dataset>_<mode>_n<N>/predictions.jsonl`

**V4. Native vs CPU-projection equivalence diff** (read-only, ≤5 min CPU after V3):
- For each of 6 modes, diff native V3 output vs Round 120 CPU projection
- Expected: byte-identical on (primary, comorbid, audit_comorbid, schema_version, diagnostician_ranked, raw_checker_outputs, logic_engine_confirmed_codes)
- Allowed differences: timestamps, run_id, model_name (if expected non-determinism)
- If any case differs on the listed fields, surface and STOP

### 6.2 Optional V3 skip (Plan-level decision)

Per Round 120 audit verdict §14, the CPU projection is "bit-equivalent to disabled-veto canonical re-run." If V1 + V2 + a sample of V4 (e.g., 3 modes × 10 random cases) demonstrate byte-equivalence to projection, the full V3 GPU re-run MAY be skipped.

The decision to skip V3 is a SEPARATE Plan-level decision and requires explicit user authorization. Default expectation: V3 is run for paper-integration-v0.2 reproducibility.

---

## 7. Stacker dependency audit

This section provides the explicit code-path evidence requested by Round 124 §«Surface 2».

### 7.1 Stacker feature schema (confirmed via `origin/clean/v2.5-eval-discipline:scripts/stacker/build_features.py`)

The stacker consumes a 31-dimension feature vector composed of:

```
Block 1 (12 dims): TF-IDF class probabilities       — independent of hied.py
Block 2 (5 dims):  DtV diagnostician top-5 ranked confidences
                   source: decision_trace.diagnostician_ranked
Block 3 (12 dims): DtV criterion checker met_ratio per class
                   source: decision_trace.raw_checker_outputs[*].met_ratio
Block 4 (1 dim):   tfidf_top1_margin
                   source: TF-IDF prediction record
Block 5 (1 dim):   dtv_abstain_flag
                   source: decision_trace (computed from checker coverage / diagnostician failure)
```

### 7.2 Per-block BETA-2b impact analysis

| Feature block | Source field | Touched by BETA-2b patch? |
|---|---|:---:|
| TF-IDF probs (12) | TF-IDF prediction record | NO (separate model) |
| DtV ranked confidences (5) | `decision_trace.diagnostician_ranked` | NO (preserved by I8) |
| DtV checker met_ratios (12) | `decision_trace.raw_checker_outputs.met_ratio` | NO (preserved by I6) |
| TF-IDF margin (1) | TF-IDF prediction record | NO (separate model) |
| DtV abstain flag (1) | `decision_trace` upstream of veto | NO (computed before line 1438) |

### 7.3 Verdict: Stacker retrain NOT NEEDED

All 31 stacker features have source fields that are either (a) external to hied.py, or (b) computed upstream of the veto/fallback block at lines 1438-1470, or (c) preserved bit-identical by BETA-2b invariants I6, I7, I8.

The stacker stores `primary_diagnosis` and `comorbid_diagnoses` in its own `predictions.jsonl` output (`scripts/stacker/eval_stacker.py:260-261`) but these are derived from the stacker model's own probability output, not from hied.py's primary or comorbid emission. Stacker output is independent of BETA-2b patch.

### 7.4 STOP-and-surface clause

If during V1 smoke test, ANY of the following conditions is observed, STOP and surface (do not proceed to V3):

- A stacker feature value differs between BETA-2a (`62622a0`) and BETA-2b (patched) outputs on the same case_id
- A new field is added to or removed from `decision_trace` by the patch
- `raw_checker_outputs` ordering or content differs

This is a defensive check; §7.1-7.3 analysis predicts no such difference, but the smoke test is the authoritative validator.

### 7.5 Stage 0 stacker-infra-missing blocker (independent)

Round 88 user memory + Round 119 audit note an independent stacker-training-infrastructure blocker: `scripts/stacker/build_features.py` lives on `origin/clean/v2.5-eval-discipline` but NOT on `origin/feature/gap-e-beta2-implementation` or `origin/main-v2.4-refactor`. This blocker is **independent** of BETA-2b patch and is NOT addressed by this plan. It will need to be addressed before any stacker re-evaluation, but it does not gate this patch.

---

## 8. Manuscript and canonical-metric non-adoption gate

**This plan does NOT authorize manuscript changes or canonical metric adoption.**

Even after V1 + V2 + V3 + V4 all pass, the following remain prohibited:

```
❌ Modifying any §1-§7 source file (Introduction, Related Work, Methods, Experiments, Results, Discussion, Limitations)
❌ Modifying Abstract
❌ Modifying Table 2 (subgroup attribution) or Table 4 (Full HiED parity benchmark)
❌ Inserting BETA-2b numbers into any claim location
❌ Modifying REPRODUCTION_README.md
❌ Modifying metric_consistency_report.json
❌ Moving paper-integration-v0.1 tag from c3b0a46
❌ Merging feature/gap-e-beta2-implementation into main-v2.4-refactor
❌ Force-pushing or rewriting history on main-v2.4-refactor or master
```

Adoption of BETA-2b as canonical paper policy requires a separate plan (Plan v1.3.3 or equivalent) and a separate authorization track that includes:

1. Manuscript-impact PR (§4 Methods, §5.4 Table 4, §7 Limitations)
2. New integration tag (e.g., `paper-integration-v0.2`)
3. PI / advisor sign-off on the tag bump

The dependency order remains:

```
production-code patch (this plan) → V1-V4 validation → manuscript-impact PR (separate plan) → new tag (separate plan)
```

---

## 9. Rollback and fail-loud criteria

### 9.1 Rollback plan

The production patch is delivered as a single squashable commit (or short commit chain) on `feature/gap-e-beta2-implementation`. Rollback:

```bash
# If patch fails any V1-V4 check:
git revert <patch-commit-sha>
git push origin feature/gap-e-beta2-implementation
```

Or for a short commit chain:

```bash
git reset --hard 082c3f9  # back to current HEAD
git push --force-with-lease origin feature/gap-e-beta2-implementation
```

Force-push is acceptable on `feature/gap-e-beta2-implementation` because it is a feature branch with no downstream dependency. Force-push is FORBIDDEN on `main-v2.4-refactor` and `master`.

### 9.2 Fail-loud criteria

Any of the following triggers immediate STOP + surface + DO NOT push:

```
F1. Any smoke V1 case violates I1-I8 (primary, comorbid, audit_comorbid, schema_version, decision_trace, raw_checker_outputs, logic_engine_confirmed_codes, diagnostician_ranked)
F2. Smoke V2 (default flag) shows any byte-difference vs BETA-2a output on same case_ids (I11)
F3. Both-mode pass-through I9 violated in any mode
F4. Stacker feature value differs between BETA-2a and BETA-2b on same case (§7.4)
F5. Full canonical V3 (if run) metrics deviate >0.5pp from §1.3 target on any metric
F6. V4 native-vs-projection diff shows differences outside the allowed-difference list (§6.1 V4)
F7. Any pre-existing dirty file (configs/vllm_awq.yaml, src/culturedx/retrieval/case_retriever.py) accidentally staged
F8. Any forbidden file (§4.3) modified
F9. paper-integration-v0.1 tag movement detected
F10. Any commit appears on main-v2.4-refactor or master before user authorization
```

### 9.3 Surface threshold

Even if no fail-loud triggers, the following warrant explicit surface to user before V3:

- Smoke V1 audit_comorbid emission rate differs from §1.3 expected per-mode rate by >5pp
- Smoke V1 metrics on N=20 differ from §1.3 target by >5pp on any metric (small-N noise expected, but >5pp warrants investigation)
- Patch diff is larger than expected (~50-100 lines of net change); larger diff suggests scope creep

---

## 10. Next-trigger taxonomy

The following are the canonical triggers for BETA-2b production patch progression. Each is **explicit**; none is auto-fired.

| Trigger | Action authorized | When valid |
|---|---|---|
| `Go implement BETA-2b production patch (V1 smoke gate)` | Implement patch on feature/gap-e-beta2-implementation per §3-§5; run V1 + V2 smoke; STOP at smoke gate; await user review | After Plan v1.3.2 commit |
| `Go run BETA-2b V3 full canonical (after V1+V2 pass)` | Run V3 full GPU canonical re-evaluation per §6.1 V3 | After V1+V2 explicit pass |
| `Skip V3 — adopt CPU projection as canonical (sub-plan decision)` | Explicit Plan-level decision to skip V3 GPU re-run; requires written justification in commit message | After V1+V2+V4-sample pass |
| `Go run V4 native-vs-projection diff` | Run §6.1 V4 byte-equivalence check between V3 native output and Round 120 CPU projection | After V3 complete |
| `Rollback BETA-2b patch — failed validation` | Per §9.1 rollback steps | After any F1-F10 fail-loud trigger |
| `Hold BETA-2b patch pending PI / advisor verdict` | No-op | Any time before V3 |
| `Close BETA-2b patch — superseded by Plan v1.3.X` | Append v1.3.X amendment to this plan recording supersession | After higher-priority decision |
| `Begin paper-integration-v0.2 adoption planning` | Authorize separate Plan v1.3.3 for canonical adoption + manuscript-impact + tag bump | After V1-V4 all pass + PI sign-off |

**Triggers NOT in this taxonomy require a new plan amendment (v1.3.2.1 or similar).**

The following are explicitly NOT triggers under Plan v1.3.2:

- Adopting BETA-2b numbers as paper canonical based solely on CPU projection
- Updating Abstract / §5.4 Table 4 from BETA-2b numbers
- Merging feature/gap-e-beta2-implementation to main-v2.4-refactor without separate authorization
- Force-pushing main-v2.4-refactor or master under any circumstance
- Running BETA-1 (multi-label benchmark output) experiments — hard-forbidden per §1.4
- Modifying stacker code or retraining the stacker (per §7 verdict, not needed)
- Starting cleanup phase / paper-clean branch work — defer to Round 130+ per Round 115 sequencing

---

## End of Plan v1.3.2

This plan was drafted at `feature/gap-e-beta2-implementation @ 082c3f9`. It will be committed as a single new file at `docs/paper/integration/Plan_v1.3.2_BETA2b_Patch.md` with no other tree changes. Adoption of any conditional content (§3-§6) is gated by §10 explicit triggers.

To revisit or amend this plan, create `Plan_v1.3.2.1_BETA2b_amendment.md` referencing this file. Do NOT in-place edit this file after commit.
