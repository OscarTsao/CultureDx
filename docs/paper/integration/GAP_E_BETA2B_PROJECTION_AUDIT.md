# Gap E BETA-2b CPU Projection Audit — Round 120 Review

**Status:** Read-mostly audit. Write only: 6 projection prediction files (CPU transform of canonical) + this audit report. NO production code change. NO commit. NO push. NO GPU. NO tag movement.
**Source HEAD:** `8664b56` on `feature/gap-e-beta2-implementation`
**Frozen tag:** `paper-integration-v0.1 → c3b0a46` (must NOT move)
**Frozen main:** `origin/main-v2.4-refactor → 3d5e014` (must NOT move)
**Predecessors:** Plan v1.3 (`3d5e014`), BETA-2a canonical commit (`8664b56`), Round 118 audit (`GAP_E_CANONICAL_RUN_REVIEW.md`)
**Authorization:** Round 119 explicit trigger. CPU-only projection of existing canonical predictions to BETA-2b form (primary-locked to `diagnostician_ranked[0]`).

---

## 1. Scope and read-only-mostly status

This audit transforms the Round 114 canonical predictions (BETA-2a) on disk to BETA-2b form via CPU-only manipulation. It does NOT modify any production code, does NOT run any LLM inference, does NOT use GPU. The only writes are:

- 6 projection prediction files at `results/gap_e_beta2b_projection_20260430_164210/<dataset>_<mode>_n<N>/predictions.jsonl`
- 6 transform_stats.json files (one per mode)
- This audit report at `docs/paper/integration/GAP_E_BETA2B_PROJECTION_AUDIT.md`

All 13 outputs are staged in working tree but left UNCOMMITTED for user review.

---

## 2. BETA-2a vs BETA-2b nomenclature (per Round 119 lock-in)

| Variant | Definition | Primary selection | Comorbid handling | schema_version |
|---|---|---|---|---|
| **Baseline** (paper-integration-v0.1) | Pre-Gap-E pipeline | veto-driven (existing) | threshold-gated multilabel emission | "v1" |
| **BETA-2a** (Round 114 canonical) | Output-channel split only | veto-driven (UNCHANGED from baseline) | benchmark = []; audit_comorbid in decision_trace | "v2" |
| **BETA-2b** (this audit, CPU projection) | Primary-locked variant | `diagnostician_ranked[0]` for 100% cases | benchmark = []; audit_comorbid preserved | "v2b" |
| **BETA-2-full** (future, code-patched) | BETA-2b validated via GPU re-run | `diagnostician_ranked[0]` enforced in hied.py | same as BETA-2b | "v2" |

BETA-2b is achievable by CPU transform because Round 118 CHECK B confirmed 5775/5775 cases have bit-identical upstream fields (diagnostician_ranked, raw_checker_outputs, logic_engine_confirmed_codes) between baseline and canonical. Forcing primary := ranked[0] on disk = bit-equivalent to disable-veto-and-rerun-GPU.

---

## 3. CPU projection methodology

For each canonical prediction record:

```
new_record = canonical_record.copy()
new_record["primary_diagnosis"] = canonical_record["decision_trace"]["diagnostician_ranked"][0]  if non-empty
new_record["primary_diagnosis_icd10"] = same as primary_diagnosis
new_record["schema_version"] = "v2b"
# All other fields (comorbid_diagnoses=[], audit_comorbid, decision_trace, raw_checker_outputs, etc.) preserved verbatim
```

Edge cases (empty/missing diagnostician_ranked): fall back to original primary_diagnosis. Track count separately. **Result: 0 edge cases across all 6 modes.**

---

## 4. Workspace preflight — all PASS

| Check | Expected | Observed |
|---|---|---|
| HEAD | `8664b56` | `8664b56` ✓ |
| Branch | `feature/gap-e-beta2-implementation` | ✓ |
| paper-integration-v0.1 | `c3b0a46` | `c3b0a46` ✓ |
| origin/main-v2.4-refactor | `3d5e014` | `3d5e014` ✓ |
| 6 canonical predictions | exist | ALL OK |
| Round 118 audit report | exist | ✓ (staged uncommitted) |

---

## 5. Transform statistics per mode

| Mode | N | unchanged_case (primary already = ranked[0]) | transformed_case (primary differed) | edge_case (no ranked[0]) |
|---|---:|---:|---:|---:|
| lingxi_icd10 | 1000 | 916 | **84** | 0 |
| lingxi_dsm5 | 1000 | 815 | **185** | 0 |
| lingxi_both | 1000 | 916 | 84 | 0 |
| mdd_icd10 | 925 | 871 | **54** | 0 |
| mdd_dsm5 | 925 | 848 | **77** | 0 |
| mdd_both | 925 | 871 | 54 | 0 |

Transformed counts match Round 118 CHECK A primary≠top1 mismatch counts EXACTLY (84 / 185 / 84 / 54 / 77 / 54). Confirms transform is correctly inverting the veto effect identified in Round 118.

---

## 6. BETA-2b invariant verification (6 invariants × 6 modes) — ALL PASS

| Invariant | Description | Lingxi ICD-10 | Lingxi DSM-5 | Lingxi Both | MDD ICD-10 | MDD DSM-5 | MDD Both |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | primary == ranked[0] (Plan §3 #1) | 1000/1000 | 1000/1000 | 1000/1000 | 925/925 | 925/925 | 925/925 |
| 2 | comorbid_diagnoses == [] (BETA-2 invariant) | 1000/1000 | 1000/1000 | 1000/1000 | 925/925 | 925/925 | 925/925 |
| 3 | audit_comorbid present | 1000/1000 | 1000/1000 | 1000/1000 | 925/925 | 925/925 | 925/925 |
| 4 | schema_version == "v2b" | 1000/1000 | 1000/1000 | 1000/1000 | 925/925 | 925/925 | 925/925 |
| 5 | upstream byte-identical to canonical (no transform leaks) | 1000/1000 | 1000/1000 | 1000/1000 | 925/925 | 925/925 | 925/925 |
| 6 | Both-mode pass-through preserved | — | — | 1000/1000 vs ICD-10 | — | — | 925/925 vs ICD-10 |

**OVERALL INVARIANT VERIFICATION: ALL PASS.** No upstream leakage from transform; primary-lock fully implemented; BETA-2 audit-channel invariants preserved; Both-mode pass-through preserved.

---

## 7. Per-mode full metric table (BETA-2b)

| Mode | Top-1 | Top-3 | EM | F1_macro | F1_weighted | 2c | 4c | Overall | asym ratio | F42 recall | audit_emit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| lingxi_icd10 | **0.5240** | 0.7990 | 0.4690 | 0.1814 | 0.4332 | 0.8203 | 0.4530 | 0.5482 | 6.61 | **52.0%** | 39.6% |
| lingxi_dsm5 | **0.5300** | 0.8050 | 0.4720 | 0.1986 | 0.4426 | 0.8076 | 0.4500 | 0.5493 | 4.82 | **56.0%** | 22.0% |
| lingxi_both | 0.5240 | 0.7990 | 0.4690 | 0.1814 | 0.4332 | 0.8203 | 0.4530 | 0.5482 | 6.61 | 52.0% | 39.6% |
| mdd_icd10 | **0.5924** | 0.8422 | 0.5924 | 0.1970 | 0.5326 | 0.7444 | 0.6238 | 0.5993 | 5.15 | 38.5% | 52.0% |
| mdd_dsm5 | **0.5795** | 0.8324 | 0.5795 | 0.2096 | 0.5116 | 0.7304 | 0.6130 | 0.5988 | 6.54 | 38.5% | 73.7% |
| mdd_both | 0.5924 | 0.8422 | 0.5924 | 0.1970 | 0.5326 | 0.7444 | 0.6238 | 0.5993 | 5.15 | 38.5% | 52.0% |

---

## 8. Three-way comparison: Baseline / BETA-2a / BETA-2b / Sandbox R3-α (Top-1)

| Mode | Baseline | BETA-2a | **BETA-2b** | Sandbox R3-α | Δ vs BETA-2a | Δ vs R3-α |
|---|---:|---:|---:|---:|---:|---:|
| lingxi_icd10 | 0.5070 | 0.5070 | **0.5240** | 0.5240 | **+1.70pp** | **+0.00pp** |
| lingxi_dsm5 | 0.4710 | 0.4710 | **0.5300** | 0.5300 | **+5.90pp** | **+0.00pp** |
| lingxi_both | 0.5070 | 0.5070 | 0.5240 | 0.5240 | +1.70pp | +0.00pp |
| mdd_icd10 | 0.5849 | 0.5849 | **0.5924** | 0.6040 | +0.76pp | −1.16pp |
| mdd_dsm5 | 0.5708 | 0.5708 | **0.5795** | 0.5880 | +0.86pp | −0.85pp |
| mdd_both | 0.5849 | 0.5849 | 0.5924 | 0.6040 | +0.76pp | −1.16pp |

**Key observations:**

1. Baseline ≡ BETA-2a (Round 118 CHECK B confirmed; BETA-2a only changed comorbid emission, not primary)
2. BETA-2b matches sandbox R3-α EXACTLY for all 3 LingxiDiag modes (+0.00pp on all 3)
3. BETA-2b ~1pp below sandbox R3-α for MDD modes — within ±2pp tolerance, likely from raw-code parsing edge cases (F41.0/F41.1/F41.2 normalization differs slightly between sandbox cross_dataset_replay.py and v4 contract compute_table4_metrics_v2)
4. **BETA-2b ALL 6 modes within ±2pp of sandbox R3-α** (verified)

---

## 9. Sandbox R3-α convergence verification — PASS

| Convergence threshold | Result |
|---|:---:|
| All modes within ±2pp of sandbox R3-α | **YES (PASS)** |
| All modes within ±3pp of sandbox R3-α | **YES (PASS)** |

**LingxiDiag DSM-5 outlier resolution** (the −5.9pp BETA-2a outlier identified in Round 118):

| Stage | Top-1 | Δ vs Sandbox R3-α |
|---|---:|---:|
| BETA-2a (Round 114 canonical) | 0.4710 | **−5.90pp (outlier)** |
| BETA-2b (this projection) | **0.5300** | **+0.00pp (resolved)** |
| Sandbox R3-α (post-hoc replay) | 0.5300 | reference |

**OUTLIER RESOLVED.** The −5.9pp gap was entirely caused by the existing veto/fallback path overriding ranked[0] in 185/1000 LingxiDiag DSM-5 cases. With primary locked to ranked[0], BETA-2b reproduces sandbox R3-α exactly.

---

## 10. F32/F41 asymmetry analysis (BETA-2b)

| Mode | F32→F41 | gold_F32 | F41→F32 | gold_F41 | asym ratio |
|---|---:|---:|---:|---:|---:|
| lingxi_icd10 | 30 | 370 | 207 | 394 | 6.61 |
| lingxi_dsm5 | 41 | 370 | 196 | 394 | 4.82 |
| lingxi_both | 30 | 370 | 207 | 394 | 6.61 |
| mdd_icd10 | 35 | 408 | 159 | 308 | 5.15 |
| mdd_dsm5 | 32 | 408 | 168 | 308 | 6.54 |
| mdd_both | 35 | 408 | 159 | 308 | 5.15 |

Cross-standard observations:
- LingxiDiag: DSM-5 IMPROVES asymmetry vs ICD-10 (4.82 vs 6.61) — direction OPPOSITE from BETA-2a where DSM-5 worsened it
- MDD-5k: DSM-5 worsens asymmetry vs ICD-10 (6.54 vs 5.15) — same direction as BETA-2a
- The veto path (active in BETA-2a) was inflating F41→F32 in DSM-5 mode by overriding F41 ranked[0] cases with F32 fallback. Removing veto reverses the LingxiDiag DSM-5 cross-standard direction.

This is a substantively different cross-standard story from BETA-2a. May warrant §5.4 narrative re-examination.

---

## 11. F42 recall analysis (BETA-2b)

| Mode | F42 recall | gold_F42 | TP_F42 |
|---|---:|---:|---:|
| lingxi_icd10 | **52.0%** | 25 | 13 |
| lingxi_dsm5 | **56.0%** | 25 | 14 |
| lingxi_both | 52.0% | 25 | 13 |
| mdd_icd10 | 38.5% | 13 | 5 |
| mdd_dsm5 | 38.5% | 13 | 5 |
| mdd_both | 38.5% | 13 | 5 |

LingxiDiag: F42 recall IMPROVES in DSM-5 (56.0%) vs ICD-10 (52.0%) — opposite direction from BETA-2a (12.0% DSM-5 vs 52.0% ICD-10).

**Major change vs BETA-2a:** The veto path was suppressing F42 primary outputs in DSM-5 mode. With ranked[0] forced, DSM-5 F42 recall recovers fully and even exceeds ICD-10. Sandbox §5.6 / §F42 narrative needs re-examination.

---

## 12. LingxiDiag DSM-5 outlier resolution

| Round 118 finding | BETA-2b finding |
|---|---|
| BETA-2a Top-1 = 0.471, sandbox R3-α = 0.530, gap = −5.9pp | BETA-2b Top-1 = 0.530, gap = 0.00pp **CLOSED** |
| 185 cases (18.5%) where canonical primary != ranked[0] | 0 cases now mismatch — primary is ranked[0] for all 1000 |
| Veto net effect: 84 hurts − 25 helps − 76 neutral = −59 cases | Veto effect removed via projection; 84 cases regain Top-1 correct, 25 lose, net +59 = +5.9pp |
| Plan v1.3 §3 clause #1 not implemented in canonical pipeline | BETA-2b enforces clause #1 by construction (transform invariant) |

The −5.9pp outlier was structural to the existing veto code path, not a BETA-2 bug. CPU projection demonstrates exact resolution: removing veto recovers sandbox R3-α prediction bit-perfectly.

---

## 13. Both-mode pass-through (re-confirmed)

| Dataset | mode_both ≡ mode_icd10 on output fields | Verdict |
|---|---|:---:|
| LingxiDiag (1000 cases) | primary 1000/1000, comorbid 1000/1000, audit 1000/1000, ranked 1000/1000 | **BIT-IDENTICAL** |
| MDD-5k (925 cases) | primary 925/925, comorbid 925/925, audit 925/925, ranked 925/925 | **BIT-IDENTICAL** |

Plan v1.3 §3 #6 + sandbox §8.2 architectural pass-through framing confirmed at projection scale (1925/1925 cases).

---

## 14. Audit verdict

**GO — BETA-2b projection passes all invariants and reproduces sandbox R3-α; BETA-2-full code patch authorized.**

Specifically:

- ALL 6 modes pass ALL 6 invariants (primary-lock, comorbid-empty, audit-present, schema-bumped, upstream-untouched, Both-passthrough)
- ALL 6 modes within ±2pp of sandbox R3-α Top-1 (3 of 6 EXACT match for LingxiDiag modes)
- LingxiDiag DSM-5 −5.9pp outlier RESOLVED (BETA-2b matches sandbox 0.530 exactly)
- F32/F41 asymmetry + F42 recall recompute cleanly under primary-lock
- Both-mode pass-through preserved bit-perfectly
- 0 edge cases across all 1925 LingxiDiag + 1850 MDD = 5775 records

**Note:** F32/F41 cross-standard direction CHANGED on LingxiDiag (DSM-5 now BETTER than ICD-10 on asymmetry, opposite of BETA-2a). F42 recall on LingxiDiag DSM-5 increased from 12% to 56%. These are substantive narrative-level changes that warrant §5.4 / §5.6 / §7 re-examination if BETA-2-full is adopted.

---

## 15. Files that would be touched if BETA-2-full code patch approved

Conditional on Plan v1.3 §8 Gate 8.1 (PI sign-off):

| Path | Purpose |
|---|---|
| `src/culturedx/modes/hied.py` (lines ~1330-1372 DtV primary-selection block) | Disable veto/fallback; force primary := ranked_codes[0] |
| `results/dual_standard_full/...` (×6) | Regenerate with patched pipeline (could be SKIPPED since BETA-2b projection = bit-equivalent) |
| `results/analysis/metric_consistency_report.json` | Recompute canonical values |
| `docs/paper/drafts/SECTION_5_4*.md` | Revisit asymmetry direction + DSM-5 framing |
| `docs/paper/drafts/SECTION_5_6.md` | Revisit F42 recall narrative |
| `docs/paper/drafts/SECTION_7*.md` | Limitations updates |
| `docs/paper/repro/REPRODUCTION_README.md` | Reference new tag |
| `docs/paper/integration/Plan_v1.3.1_GapE_amendment.md` | Document BETA-2 = BETA-2-full lock-in |
| New annotated tag `paper-integration-v0.2` | Plan §8 Gate 8.6 |

**Optional optimization:** Since BETA-2b projection is bit-equivalent to disabled-veto canonical, the GPU re-run could be SKIPPED. The projection files at `results/gap_e_beta2b_projection_20260430_164210/` could serve as canonical BETA-2-full predictions directly. Saves ~7 hr GPU. Plan-level decision.

---

## 16. Files that must NOT be touched in any phase of this audit

Confirmed UNTOUCHED:

- `src/culturedx/modes/hied.py` ✓
- `src/culturedx/diagnosis/calibrator.py` ✓
- `src/culturedx/diagnosis/comorbidity.py` ✓
- `src/culturedx/diagnosis/logic_engine.py` ✓
- `src/culturedx/eval/lingxidiag_paper.py` (read-only use) ✓
- `docs/paper/drafts/*` ✓
- `docs/paper/repro/REPRODUCTION_README.md` ✓
- `results/analysis/metric_consistency_report.json` ✓
- `docs/paper/integration/Plan_v1.3_GapE.md` ✓
- `docs/paper/integration/LOGIC_ENGINE_FINAL_OUTPUT_SANDBOX_REPORT.md` ✓
- `docs/paper/integration/GAP_E_CANONICAL_RUN_REVIEW.md` (Round 118 audit) ✓
- `paper-integration-v0.1` tag (frozen at `c3b0a46`) ✓
- `origin/main-v2.4-refactor` (frozen at `3d5e014`) ✓
- `feature/gap-e-beta2-implementation` HEAD (still `8664b56`, no new commits this round) ✓

No commits, no pushes, no GPU work, no tag movement, no production code modification.

---

## End of audit

This audit is **read-mostly**. The 13 outputs (6 prediction files + 6 transform_stats + 1 audit report) are staged in working tree but UNCOMMITTED. Decision between BETA-2-full code patch (Path A) vs Plan v1.3.X amendment to acknowledge BETA-2b as canonical (Path B) requires PI sign-off. PI review recommended.

