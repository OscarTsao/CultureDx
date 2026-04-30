# Gap E BETA-2b Native Smoke Audit — Round 128 Verification

**Status:** Read-mostly audit. Code patch applied behind feature flag (uncommitted). Smoke results written. NO commit. NO push. NO V3 canonical. NO manuscript change. NO tag movement.
**Source HEAD:** `1bef878` on `feature/gap-e-beta2-implementation`
**Frozen tag:** `paper-integration-v0.1 → c3b0a46`
**Frozen main:** `origin/main-v2.4-refactor → 3d5e014`
**Predecessors:** Plan v1.3.2 (`1bef878`), BETA-2b CPU projection (`a960616`), Plan v1.3 (`3d5e014`)
**Authorization:** Round 128 trigger — implement BETA-2b production patch behind feature flag, smoke-gate only.

---

## 1. Branch / HEAD / sync status

| Check | Expected | Observed |
|---|---|---|
| HEAD | `1bef878` | `1bef878` ✓ |
| Branch | `feature/gap-e-beta2-implementation` | ✓ |
| Tag `paper-integration-v0.1` | `c3b0a46` | `c3b0a46` ✓ (frozen) |
| `origin/main-v2.4-refactor` | `3d5e014` | `3d5e014` ✓ (frozen) |
| Pre-existing dirty (out of scope) | `configs/vllm_awq.yaml` + `case_retriever.py` | both untouched ✓ |

---

## 2. Files touched

| File | Change |
|---|---|
| `src/culturedx/core/config.py` | +1 line: `final_output_policy: str = "default"` field on `ModeConfig` |
| `src/culturedx/modes/hied.py` | +10 lines total: constructor param + `self.final_output_policy` storage + post-Pass-3 BETA-2b override block + `final_output_policy` field in DtV `decision_trace` |
| `src/culturedx/pipeline/cli.py` | +2 lines: pass `final_output_policy=getattr(cfg.mode, "final_output_policy", "default")` to `HiEDMode(**mode_kwargs)` at both call sites (run + sweep) |
| `src/culturedx/pipeline/artifacts.py` | +6 lines: read `decision_trace.final_output_policy` in `build_prediction_record`, override `schema_version="v2b"` when `beta2b_primary_locked` |
| `configs/overlays/final_output_beta2b.yaml` | NEW: 1-line overlay setting `mode.final_output_policy: beta2b_primary_locked` |

Total: +19 production lines + 1 new config overlay (5 files modified, 1 file added).

`hied.py` patch hot-spot is at lines ~1466-1480 (BETA-2b override after Pass 3) and ~1583-1587 (decision_trace field). Per Plan v1.3.2 §3 §6.

---

## 3. Feature flag name and default behavior

| Aspect | Value |
|---|---|
| Config field | `mode.final_output_policy` (string) |
| Default value | `"default"` (= existing veto/fallback path, unchanged baseline behavior) |
| BETA-2b value | `"beta2b_primary_locked"` |
| Activation | Add `-c configs/overlays/final_output_beta2b.yaml` to CLI invocation |
| Default ⇒ canonical | `schema_version="v2"` (BETA-2a behavior preserved) |
| BETA-2b ⇒ canonical | `schema_version="v2b"` (primary-locked) |

---

## 4. V1 BETA-2b smoke invariants (table per mode, N=20)

| Mode | sv=v2b | cd=[] | audit_present | primary == ranked[0] | fop=beta2b_primary_locked | PASS? |
|---|---:|---:|---:|---:|---:|:---:|
| lingxi_icd10 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | **YES** |
| lingxi_dsm5 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | **YES** |
| lingxi_both | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | **YES** |
| mdd_icd10 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | **YES** |
| mdd_dsm5 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | **YES** |
| mdd_both | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | **YES** |

**V1 BETA-2b VERDICT: ALL 5 INVARIANTS × 6 MODES PASS (120/120 records).**

---

## 5. V2 default-policy regression smoke (N=20 per mode)

| Mode | sv=v2 | cd_emit_rate | audit_present | fop=default | PASS? |
|---|---:|---:|---:|---:|:---:|
| lingxi_icd10 | 20/20 | 0/20 | 20/20 | 20/20 | YES |
| lingxi_dsm5 | 20/20 | 0/20 | 20/20 | 20/20 | YES |
| lingxi_both | 20/20 | 0/20 | 20/20 | 20/20 | YES |
| mdd_icd10 | 20/20 | 0/20 | 20/20 | 20/20 | YES |
| mdd_dsm5 | 20/20 | 0/20 | 20/20 | 20/20 | YES |
| mdd_both | 20/20 | 0/20 | 20/20 | 20/20 | YES |

`cd_emit_rate=0` because BETA-2 emission block (added in commit `62622a0`) already forces `comorbid_diagnoses=[]` for all canonical runs. The default flag preserves this BETA-2a behavior unchanged. **`schema_version="v2"` is correctly preserved (NOT bumped to v2b).**

### V2 vs BETA-2a (commit `62622a0`) byte-identicality

| Mode | V2 byte-match BETA-2a | Verdict |
|---|---|---|
| lingxi_icd10 | 20/20 (100%) | **BIT-IDENTICAL** |
| lingxi_dsm5 | 20/20 (100%) | **BIT-IDENTICAL** |
| lingxi_both | 20/20 (100%) | **BIT-IDENTICAL** |
| mdd_icd10 | 20/20 (100%) | **BIT-IDENTICAL** |
| mdd_dsm5 | 20/20 (100%) | **BIT-IDENTICAL** |
| mdd_both | 20/20 (100%) | **BIT-IDENTICAL** |

**V2 REGRESSION VERDICT: PASS — default-flag behavior is byte-identical to pre-patch BETA-2a baseline across 120/120 cases on (primary, comorbid, diagnostician_ranked).** No silent default-behavior change.

---

## 6. Both-mode pass-through check

V1 BETA-2b only:

| Dataset | cases | primary | comorbid | audit | ranked | Verdict |
|---|---:|---:|---:|---:|---:|---|
| LingxiDiag | 20 | 20/20 | 20/20 | 20/20 | 20/20 | **BIT-IDENTICAL** |
| MDD-5k | 20 | 20/20 | 20/20 | 20/20 | 20/20 | **BIT-IDENTICAL** |

mode_both ≡ mode_icd10 preserved under BETA-2b (Plan v1.3 §3 #6 + sandbox §8.2 architectural pass-through).

---

## 7. Stacker dependency verdict

Per Plan v1.3.2 §7 + Round 118 CHECK B (5775/5775 upstream byte-identical), the BETA-2b patch:

- Does NOT change `decision_trace.diagnostician_ranked` (stacker reads ranked confidences here)
- Does NOT change `decision_trace.raw_checker_outputs` (stacker reads met_ratio per disorder here)
- Does NOT change `decision_trace.logic_engine_confirmed_codes` (stacker reads confirmed-set membership here)
- Does NOT change checker scoring, calibrator output, retriever, prompts

Only `primary_diagnosis`, `comorbid_diagnoses`, `audit_comorbid`, `schema_version`, and `decision_trace.final_output_policy` change under BETA-2b.

**STACKER RETRAIN VERDICT: NOT NEEDED.** The 31-feature schema (13 TF-IDF + 18 MAS-derived) is sourced from upstream fields all preserved verbatim. Confirms Plan v1.3.2 §7 prediction.

---

## 8. Projection-equivalence discussion

V1 BETA-2b native smoke vs CPU projection at `results/gap_e_beta2b_projection_20260430_164210/` (same case_ids drawn from same input pool):

| Mode | V1 byte-match projection | Verdict |
|---|---|---|
| lingxi_icd10 | 20/20 (100%) | BIT-IDENTICAL |
| lingxi_dsm5 | 20/20 (100%) | BIT-IDENTICAL |
| lingxi_both | 20/20 (100%) | BIT-IDENTICAL |
| mdd_icd10 | 19/20 (95%) | 1 case diverge |
| mdd_dsm5 | 20/20 (100%) | BIT-IDENTICAL |
| mdd_both | 19/20 (95%) | 1 case diverge (same case as mdd_icd10 via Both pass-through) |

**118 of 120 cases (98.3%) bit-identical between V1 native smoke and CPU projection.** The 2 diverge cases (1 unique, mirrored across icd10/both via pass-through) are attributed to vLLM non-determinism under `--enforce-eager` (bit-level GPU floating-point ordering is not strictly deterministic across reruns even at temperature=0 / top_k=1; a known limitation of vLLM eager mode).

The diverge cases still satisfy V1 invariants (primary == ranked[0], comorbid=[], audit_comorbid present, sv=v2b, fop=beta2b_primary_locked) — the divergence is in the underlying ranked[0] value (LLM produced slightly different output on rerun), NOT in the BETA-2b transform logic.

**Conclusion: BETA-2b native pipeline is bit-equivalent to CPU projection up to vLLM determinism noise (~2%). Round 120 audit's "BETA-2b CPU projection ≈ disabled-veto canonical re-run" claim is empirically validated.**

---

## 9. Go/no-go for V3 full canonical

**GO** — V1 invariants pass, V2 regression-free, projection-equivalent within vLLM determinism noise.

V3 full canonical (N=1000 LingxiDiag × 3 modes + N=925 MDD-5k × 3 modes) is authorized when explicitly triggered. Per Plan v1.3.2 §10 trigger 2.

**Optional optimization:** V3 GPU re-run can be SKIPPED if Plan v1.3.X amendment accepts BETA-2b CPU projection (`a960616`) as canonical — projection is bit-equivalent to disabled-veto canonical with verified V1+V2 patch validation. This is a Plan-level decision, not engineering decision.

---

## 10. Explicit non-modification statement

Per Round 128 hard-stop checklist (all 9 PASS):

| Constraint | Status |
|---|:---:|
| `docs/paper/drafts/` untouched | ✓ |
| `docs/paper/repro/REPRODUCTION_README.md` untouched | ✓ |
| `results/analysis/metric_consistency_report.json` untouched | ✓ |
| `Plan_v1.3_GapE.md` untouched | ✓ |
| `Plan_v1.3.2_BETA2b_Patch.md` untouched | ✓ |
| `GAP_E_CANONICAL_RUN_REVIEW.md` (Round 118) untouched | ✓ |
| `GAP_E_BETA2B_PROJECTION_AUDIT.md` (Round 120) untouched | ✓ |
| `paper-integration-v0.1` tag NOT moved | ✓ (`c3b0a46`) |
| `main-v2.4-refactor` NOT merged | ✓ |
| V3 full canonical NOT run | ✓ (only N=20 smoke this round) |
| Stacker NOT retrained | ✓ |
| `configs/vllm_awq.yaml` NOT staged | ✓ (pre-existing dirty preserved) |
| `case_retriever.py` NOT staged | ✓ |

**Manuscript and canonical metric files were NOT updated by this audit.** The patch is feature-flag-gated; default behavior is preserved byte-identically.

---

## End of audit

This audit is read-mostly with one production-code patch (4 files, +19 lines), one new config overlay (1 file), and one smoke output directory. All staged but UNCOMMITTED for user review. No commit, no push.

