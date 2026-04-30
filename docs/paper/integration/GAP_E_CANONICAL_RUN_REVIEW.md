# Gap E Canonical-Run Isolation Audit — Round 118 Review

**Status:** Read-only audit on uncommitted feature-branch results. NO production code change. NO commit by audit. NO push.
**Source HEAD:** `8664b56` on `feature/gap-e-beta2-implementation` (not on `main-v2.4-refactor`)
**Frozen tag:** `paper-integration-v0.1 → c3b0a46` (must NOT move)
**Frozen main:** `origin/main-v2.4-refactor → 3d5e014` (must NOT move)
**Predecessors:** Plan v1.3 (`3d5e014`), Round 114 BETA-2 commit (`62622a0`), Round 114 canonical commit (`8664b56`)
**Authorization:** This audit responds to Round 117 NO-GO verdict on Round 114 canonical-run adoption. The 5 issues identified there (A primary=top1, B old-vs-new diff, C F32/F41+F42, D LingxiDiag DSM-5 outlier, E counting) are addressed below.

---

## 1. Scope and read-only status

This audit verifies whether Round 114 canonical run (commit `8664b56` on `feature/gap-e-beta2-implementation`) actually satisfies the full Plan v1.3 §3 design lock and isolates the BETA-2 policy effect from upstream inference drift. It does NOT modify any production code, does NOT run GPU, does NOT commit or push, and does NOT move any tag.

The single file produced is this report at `docs/paper/integration/GAP_E_CANONICAL_RUN_REVIEW.md`. It is staged in working tree but left UNCOMMITTED for user review.

---

## 2. Pre-state verification

| Check | Expected | Observed |
|---|---|---|
| HEAD | `8664b56` | `8664b56` ✓ |
| Branch | `feature/gap-e-beta2-implementation` | `feature/gap-e-beta2-implementation` ✓ |
| Tag `paper-integration-v0.1` | `c3b0a46` | `c3b0a46` ✓ (frozen) |
| `origin/main-v2.4-refactor` | `3d5e014` | `3d5e014` ✓ (frozen) |
| All 12 prediction files load | 6 canonical + 6 baseline, expected row counts | ALL OK ✓ |

Pre-existing dirty tracked files (`configs/vllm_awq.yaml`, `src/culturedx/retrieval/case_retriever.py`) untouched and out of scope.

---

## 3. CHECK A — primary_diagnosis == diagnostician_ranked[0]  (Plan v1.3 §3 clause #1)

**VERDICT: PRIMARY-EQ-TOP1 FAIL — design lock #1 not implemented**

| Mode | N | strict (raw eq) | mismatch | rate | parent eq | parent mismatch |
|---|---:|---:|---:|---:|---:|---:|
| lingxi_icd10 | 1000 | 916 | 84 | **91.60%** | 923 | 77 |
| lingxi_dsm5 | 1000 | 815 | **185** | **81.50%** | 815 | 185 |
| lingxi_both | 1000 | 916 | 84 | 91.60% | 923 | 77 |
| mdd_icd10 | 925 | 871 | 54 | 94.16% | 872 | 53 |
| mdd_dsm5 | 925 | 848 | 77 | 91.68% | 849 | 76 |
| mdd_both | 925 | 871 | 54 | 94.16% | 872 | 53 |

**Plan v1.3 §3 clause #1 mandates 100% equality**. Observed: 81.5% to 94.2% across modes. None of the 6 modes pass.

Sample mismatch (lingxi_dsm5 case `318518739`):
- ranked = `['F32', 'F51', 'F39', 'F41.1', 'F45']`
- primary = `F51`
- confirmed = `['Z71', 'F41.2', 'F51', 'F39']`
- veto_applied = `True`

The primary-selection code path at `src/culturedx/modes/hied.py:1330-1372` overrides `ranked[0]` when veto fires. This is pre-existing baseline pipeline behavior (see CHECK B); BETA-2 did NOT introduce it, and BETA-2 did NOT remove it.

---

## 4. CHECK B — Field-level diff vs baseline (drift isolation)

**VERDICT: DRIFT NONE — pure BETA-2 effect (clean attribution)**

| Mode | matched | primary_chg | rank_chg | top1_chg | checker_chg | confirmed_chg | cd_chg | audit_v2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| lingxi_icd10 | 1000 | **0** | **0** | **0** | **0** | **0** | 925 | 1000 |
| lingxi_dsm5 | 1000 | **0** | **0** | **0** | **0** | **0** | 919 | 1000 |
| lingxi_both | 1000 | **0** | **0** | **0** | **0** | **0** | 925 | 1000 |
| mdd_icd10 | 925 | **0** | **0** | **0** | **0** | **0** | 836 | 925 |
| mdd_dsm5 | 925 | **0** | **0** | **0** | **0** | **0** | 865 | 925 |
| mdd_both | 925 | **0** | **0** | **0** | **0** | **0** | 836 | 925 |

5775/5775 cases bit-identical between canonical (BETA-2) and baseline (paper-integration-v0.1 era) on:
- `primary_diagnosis`
- `decision_trace.diagnostician_ranked`
- `decision_trace.diagnostician_ranked[0]`
- `decision_trace.raw_checker_outputs` (sorted set of (disorder_code, met_ratio) tuples)
- `decision_trace.logic_engine_confirmed_codes`

Only changes (per BETA-2 design):
- `comorbid_diagnoses` cleared in 836-925 cases per mode (where baseline emitted comorbid)
- `decision_trace.audit_comorbid` field added (5550/5550 records)
- `schema_version` bumped to `"v2"` (5550/5550 records)

**Implication:** Round 114 canonical metrics CAN be cleanly attributed to BETA-2 policy effect. There is no upstream LLM drift to confound the result.

---

## 5. CHECK C — F32/F41 asymmetry + F42 recall + extended metrics

Per CHECK B's clean attribution (canonical primary == baseline primary), F32/F41 cascade and F42 recall are EXACTLY identical between baseline and canonical BETA-2:

| Mode | gold_F32 | F32→F41 | gold_F41 | F41→F32 | asym ratio | gold_F42 | F42 recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| lingxi_icd10 | 370 | 36 | 394 | 188 | **4.90** | 25 | **52.0%** |
| lingxi_dsm5 | 370 | 26 | 394 | 218 | **7.87** | 25 | **12.0%** |
| lingxi_both | 370 | 36 | 394 | 188 | 4.90 | 25 | 52.0% |
| mdd_icd10 | 408 | 38 | 308 | 129 | **4.50** | 13 | **38.5%** |
| mdd_dsm5 | 408 | 25 | 308 | 157 | **8.32** | 13 | **15.4%** |
| mdd_both | 408 | 38 | 308 | 129 | 4.50 | 13 | 38.5% |

asymmetry_ratio = (F41→F32 / N(gold=F41)) / (F32→F41 / N(gold=F32))

Cross-standard pattern (consistent with sandbox §8.6):
- DSM-5 mode WORSENS F32/F41 asymmetry vs ICD-10 (7.87 vs 4.90 on Lingxi; 8.32 vs 4.50 on MDD)
- DSM-5 mode COLLAPSES F42 recall vs ICD-10 (12.0% vs 52.0% on Lingxi; 15.4% vs 38.5% on MDD)
- Both-mode equals ICD-10 (architectural pass-through, per Plan §3 #6 + sandbox §8.2)

**These metrics are unchanged by BETA-2.** BETA-2 only touches comorbid emission, not primary selection or cascade behavior.

---

## 6. CHECK D — LingxiDiag DSM-5 -5.9pp outlier root cause

**VERDICT: outlier is structural — exactly the veto-effect, no upstream drift, no BETA-2 issue**

### LingxiDiag DSM-5 (the -5.9pp outlier)

| Metric | Value |
|---|---:|
| N | 1000 |
| Top-1 with veto (canonical primary) | **47.10%** |
| Top-1 no veto (ranked[0] only, sandbox replay) | **53.00%** |
| Veto-effect Top-1 delta | **−5.90pp** |
| Category 1 (upstream drift, ranked[0] differs) | **0** |
| Category 2 (canonical primary differs from baseline) | **0** |
| Category 3 (no change vs baseline) | **1000** |
| Veto fires (primary != ranked[0]) | 185 |
| — veto HURTS (top1 correct → primary wrong) | **84** |
| — veto HELPS (top1 wrong → primary correct) | **25** |
| — veto NEUTRAL (same correctness) | 76 |
| Net veto effect | -84 + 25 = **−59 cases (−5.90pp)** |

### LingxiDiag ICD-10 (-1.7pp control)

| Metric | Value |
|---|---:|
| Top-1 with veto | **50.70%** |
| Top-1 no veto (ranked[0]) | **52.40%** |
| Net veto effect | -26 + 9 = **−17 cases (−1.70pp)** |

### Sample veto-hurts cases (lingxi_dsm5, first 5)

| case | gold | ranked[0:5] | primary | comment |
|---|---|---|---|---|
| 383669635 | F41 | F41.1, F32, F43.2, F39, Z71 | F32 | veto chose F32 over F41.1; F41.1 ∈ gold |
| 300428774 | F20 | F20, F32, F41.1, F45, F31 | F98 | veto chose F98 over F20; F20 ∈ gold |
| 343622973 | F41 | F41.1, F32, F43.2, F45, Z71 | F45 | veto chose F45 over F41.1; F41.1 ∈ gold |
| 372242244 | F43, F42 | F42, F41.1, F32, F51, F98 | F51 | veto chose F51 over F42; F42 ∈ gold |
| 367063123 | F41 | F41.1, F32, F39, F51, F45 | F39 | veto chose F39 over F41.1; F41.1 ∈ gold |

### Root cause

Sandbox R3-α post-hoc replay used `ranked[0]` directly (Rule K, no override). Reported sandbox Top-1 (LingxiDiag DSM-5): **0.530**.

Round 114 canonical run kept the existing veto/fallback path in `src/culturedx/modes/hied.py:1330-1372`. Observed canonical Top-1 (LingxiDiag DSM-5): **0.471**.

The −5.9pp gap = exactly the veto effect (-59 / 1000 cases). The same veto fires in baseline, hence baseline LingxiDiag DSM-5 Top-1 = 0.471 = canonical (CHECK B confirms 0 primary changes).

**The outlier is NOT a BETA-2 regression. It is unimplemented Plan v1.3 §3 clause #1.** To match sandbox R3-α prediction, an ADDITIONAL code change is required to disable veto and force `primary := ranked_codes[0]` always in the DtV path.

---

## 7. CHECK E — Counting fix for Round 114 ±3pp band claim

| Mode | canonical Top-1 | sandbox R3-α | Δ pp | within ±3pp |
|---|---:|---:|---:|:---:|
| lingxi_icd10 | 0.5070 | 0.5240 | −1.70 | YES |
| lingxi_dsm5 | 0.4710 | 0.5300 | −5.90 | **NO** |
| lingxi_both | 0.5070 | 0.5240 | −1.70 | YES |
| mdd_icd10 | 0.5849 | 0.6040 | −1.91 | YES |
| mdd_dsm5 | 0.5708 | 0.5880 | −1.72 | YES |
| mdd_both | 0.5849 | 0.6040 | −1.91 | YES |

- All 6 rows within ±3pp: **5 of 6** (the Round 114 claim — technically correct)
- 4 unique modes within ±3pp (excluding Both = ICD-10 duplicates): **3 of 4** (more honest framing)

The Round 114 "5 of 6" framing inflates the count by including 2 modes (lingxi_both, mdd_both) that are bit-identical to their ICD-10 siblings by Plan §3 #6 + sandbox §8.2 architectural design. Reporting 3 of 4 unique modes is more transparent.

---

## 8. Interpretation: what does Round 114 actually tell us?

| Claim | Status |
|---|---|
| BETA-2 implementation is surgical and isolated | ✅ TRUE — CHECK B confirms 0 upstream drift across 5775 cases |
| BETA-2 schema is BETA-2-compliant (sv=v2, cd=[], audit_comorbid present) | ✅ TRUE — 5550/5550 records pass |
| Both-mode pass-through preserved | ✅ TRUE — 1925/1925 cases bit-identical between Both and ICD-10 |
| Canonical Top-1 matches sandbox R3-α prediction | ⚠ PARTIAL — 3 of 4 unique modes within ±3pp; LingxiDiag DSM-5 −5.9pp |
| Plan v1.3 §3 clause #1 ("Diagnostician rank-1 = benchmark primary") implemented | ❌ FALSE — fails in 5.8-18.5% of cases per mode (CHECK A) |
| Plan v1.3 §3 clause #4 ("Checker does not freely rerank or override primary") implemented | ❌ FALSE — the existing veto code path overrides ranked[0]; same root cause as #1 |

The canonical Round 114 run delivers ONE of the Plan v1.3 §3 design lock changes (#5 + #6 — separate audit field, primary-only benchmark). It does NOT deliver the other two (#1 + #4 — diagnostician rank-1 as primary, no checker override). The sandbox R3-α prediction assumed all 4 clauses; canonical run has only 2.

**This is not a "BETA-2 bug"** — BETA-2 was scoped to comorbid emission only. It is a **scope gap** between Plan v1.3 §3 (which describes the full design lock) and the BETA-2 implementation (which only addressed the final-output channel separation, not the primary-selection veto).

---

## 9. Required pre-merge actions (if any)

For Plan v1.3 §3 to be FULLY implemented, an additional code change is required:

### Required code change: disable primary-selection veto in DtV path

In `src/culturedx/modes/hied.py` around lines 1330-1372 (the `# Pass 1` / `# Pass 2` / `# Pass 3` primary-selection block in the DtV path), replace the veto-driven selection with `primary := ranked_codes[0]` (always). Rename or delete the `veto_applied` / `veto_from` / `veto_to` decision_trace fields, or set them to constants.

This change must be made on a **separate feature branch or commit** (not bundled with BETA-2) so the policy effects remain isolatable.

### Validation requirements after this additional change

1. Smoke test (N=20 × 6 modes) verifying primary == ranked[0] in 100% of cases
2. Full canonical re-evaluation (N=1000 + N=925 × 6 modes) on the disabled-veto + BETA-2 stack
3. Top-1 expected to match sandbox R3-α prediction within ±1pp:
   - LingxiDiag ICD-10: 0.524
   - LingxiDiag DSM-5: 0.530
   - LingxiDiag Both: 0.524
   - MDD ICD-10: 0.604
   - MDD DSM-5: 0.588
   - MDD Both: 0.604
4. Manuscript-impact gate (Plan v1.3 §7) before §5.4 Table 4 + REPRODUCTION_README + paper-integration-v0.2 tag

### Alternative: keep veto, accept partial implementation

If PI decides the existing veto path is clinically valuable (e.g., when ranked[0] is contraindicated by checker evidence, the veto can correct), then:

1. Plan v1.3 §3 must be amended (v1.3.2) to relax clause #1 from "= benchmark primary" to "= benchmark primary unless checker veto applies"
2. The −5.9pp LingxiDiag DSM-5 gap stays as observed (canonical = 0.471, not 0.530)
3. Manuscript narrative must reflect the actual primary-selection logic

---

## 10. Recommendation: GO / NO-GO / CONDITIONAL-GO for paper-integration-v0.2

**CONDITIONAL-GO** — adoption requires either of the following two paths:

### Path A: Full §3 implementation (recommended for narrative consistency)

1. Disable veto in `hied.py` primary-selection block (separate commit on feature branch)
2. Re-run canonical (6 modes × full N) on the disabled-veto + BETA-2 stack
3. Verify Top-1 matches sandbox R3-α prediction within ±1pp
4. Then proceed to manuscript-impact gate + tag bump to v0.2

**Pro:** Plan v1.3 §3 fully implemented; narrative coherent; sandbox numbers reproduced.
**Con:** ~7 hours additional GPU run; net veto effect on Top-1 is ambiguous (helps in 25-9 cases, hurts in 84-26; LingxiDiag ICD-10 control loses 1.7pp, lingxi_dsm5 loses 5.9pp).

### Path B: Plan v1.3.2 amendment (acknowledge partial implementation)

1. Amend Plan v1.3 to clarify that BETA-2 only addresses clauses #5 + #6
2. Document the veto path as preserved baseline behavior (clauses #1 + #4 partial)
3. Adopt Round 114 canonical results as-is (Top-1 reflects veto, not pure ranked[0])
4. §5.4 Table 4 presents the canonical numbers (0.471 etc.), not sandbox R3-α numbers

**Pro:** No additional GPU run; Round 114 results adopted directly; honest about the veto.
**Con:** Plan v1.3 §3 narrative weakened; sandbox §10 ("recommended design lock") not actually adopted.

### Path C (rejected): adopt Round 114 + claim sandbox R3-α numbers

NOT acceptable. Would require citing 0.530 LingxiDiag DSM-5 Top-1 as a paper claim while actual canonical artifact reports 0.471. Reviewers will check.

---

## End of audit

This audit is **read-only**. The only file produced is this report at `docs/paper/integration/GAP_E_CANONICAL_RUN_REVIEW.md`, staged in working tree but UNCOMMITTED. The decision between Path A / Path B is a Plan-level decision, not engineering-level. PI sign-off required before either path proceeds.

