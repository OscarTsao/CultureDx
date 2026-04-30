# Gap E BETA-2b — PI-facing Summary

**Audience:** PI / advisor reviewing Gap E status before paper-integration-v0.2 adoption.
**Length target:** 1 page. Decision-oriented. References full simulation; not a substitute for it.
**Source artifact:** `docs/paper/integration/GAP_E_BETA2B_MANUSCRIPT_IMPACT_SIMULATION.md` (committed at `ab12e7e` on `feature/gap-e-beta2-implementation`, 367 lines).
**Frozen tag:** `paper-integration-v0.1 → c3b0a46` (manuscript baseline).
**Status:** PI-facing review artifact on the Gap E feature branch. Adoption requires PI sign-off + Plan v1.3.4 + manuscript-impact PR + tag bump.

---

## What Gap E does

Gap E redesigns the final-output layer of the Full HiED pipeline so that the benchmark prediction set is **primary-only** and strict comorbidity candidates are emitted only as a **separate audit annotation field**. The current pipeline (paper-integration-v0.1) emits multi-label comorbidity into the benchmark prediction set in 90-93% of cases, which causes exact-match (EM) to collapse to 3-6% under the single-label evaluation contract.

BETA-2b is the production-ready variant of Gap E with two design properties:

1. `primary_diagnosis = diagnostician_ranked[0]` (Plan v1.3 §3 design lock #1, #4 fully implemented)
2. `comorbid_diagnoses = []` in benchmark output; strict-gated comorbid moves to `audit_comorbid` sidecar (Plan v1.3 §3 design lock #5, #6)

BETA-2b implementation is committed behind a feature flag (commits `b1c4474`, `3482021`). Code-path equivalence (CPE) with CPU projection is validated 5775/5775 (commit `a08ebb3`). V3 GPU full canonical re-run is deferred per Plan v1.3.3 §3 because CPE substitutes for V3's validation purpose.

## What changes if BETA-2b is adopted

Per the simulation §1, §2, §4, §5 (cited from `ab12e7e`):

- **Top-1 / Top-3 / Overall**: shift modestly across modes (most within ±2 pp; LingxiDiag DSM-5 +5.9 pp).
- **EM**: rises from 3-6% to 46-59% across all 6 modes. Largest single improvement; not currently in Table 4.
- **§5.4 dual-standard interpretation**: LingxiDiag DSM-5 flips from «mostly worse than ICD-10» to «slightly better» on primary-output metrics. MDD-5k DSM-5 vs ICD-10 gaps narrow to within ±2 pp.
- **F32/F41 asymmetry**: LingxiDiag direction reverses (DSM-5 = 4.82 vs ICD-10 = 6.61, formerly DSM-5 = 7.87 vs ICD-10 = 4.90). MDD-5k same direction, smaller gap (6.54 vs 5.15, formerly 7.24 vs 3.97). Paired bootstrap CI on LingxiDiag must be recomputed.
- **F42 recall**: largest single narrative shift. LingxiDiag DSM-5 = 56% under BETA-2b (was 12%). MDD-5k DSM-5 = 38.5% (was 15.4%). Current §5.4 claim «DSM-5-only mode reduces F42/OCD recall on both datasets» becomes false on LingxiDiag and disappears on MDD-5k.
- **Abstract**: 1 quantitative number changes (3.97× → 5.15× on MDD-5k F32/F41 ratio). All other Abstract claims unchanged.
- **Stacker / TF-IDF**: unchanged. Gap E does not touch stacker input fields (Plan v1.3.3 §4 verdict, CPE-validated).

## Estimated revision footprint

~10 manuscript files modified, ~100-200 lines of prose / table changes, 1 metric file regeneration, 1 new annotated tag (`paper-integration-v0.2`), 1 new plan file (`Plan_v1.3.4_BETA2b_canonical_adoption.md`). Detailed file list in simulation §7.

## Three questions for PI

The decision is plan-level, not engineering-level. The engineering side (BETA-2b implementation + CPE + smoke + projection) is complete. PI input is needed on:

1. **Should BETA-2b be adopted for `paper-integration-v0.2`?**
   The change is not cosmetic. It improves narrative consistency (Plan v1.3 §3 design lock fully implemented; F42 collapse explained as veto artifact, not DSM-5 schema effect; LingxiDiag DSM-5 outlier resolved). It also requires §5.4 / §5.3 / §7 narrative re-examination and recomputation of paired bootstrap statistics.

2. **If yes, is CPE evidence sufficient, or do you require V3 full GPU canonical?**
   CPE evidence: production helper output equals CPU projection on 5775/5775 records (commit `a08ebb3`). V3 would re-run the full N=1000 + N=925 × 6 modes on GPU (~5-7 hr). V3 is reactivable but not technically required to validate the policy effect. Some submission venues or reviewer panels may prefer V3 for end-to-end reproducibility verification.

3. **If yes, should EM be added to Table 4, or kept as engineering-correctness evidence only?**
   Current Table 4 columns: 2c / 4c / Top-1 / Top-3 / mF1 / wF1 / Overall. EM is not displayed. BETA-2b improves EM from 3-6% to 46-59%. Adding EM strengthens the «primary-only benchmark contract is now correctly implemented» story but invites the question of why EM was previously absent. Keeping EM out preserves the parity-plus-audit framing without inviting new questions; the EM improvement still holds engineering value as evidence that the design lock is correctly implemented.

## What PI does NOT need to weigh in on

These are already plan-locked or engineering-closed:

- **R3-α vs R3-β BETA-1 vs BETA-2 framing**: locked to BETA-2 = primary-only with audit-annotation sidecar (Plan v1.3.3 §1.4). BETA-1 is hard-forbidden from canonical adoption (Plan v1.3.3 §7).
- **Stacker retrain**: closed as not needed for Gap E (Plan v1.3.3 §4). Stacker numbers in §5.1 / Abstract are unchanged.
- **Both-mode pass-through framing**: preserved bit-perfectly (1925/1925 cases). §5.4 «Both mode is therefore an ICD-10 architectural pass-through» claim survives.
- **Production code change scope**: confined to `src/culturedx/modes/hied.py` finalization helper + 1 config overlay. No checker / calibrator / logic-engine / stacker changes.
- **Frozen baseline**: `paper-integration-v0.1@c3b0a46` is preserved as historical reference regardless of v0.2 adoption decision.

## Recommended PI deliberation path

If PI accepts BETA-2b adoption: trigger `Begin paper-integration-v0.2 adoption planning`. This produces Plan v1.3.4 (canonical adoption record), then a manuscript-impact PR (§5.3 / §5.4 / §7 / Abstract / REPRODUCTION_README revisions reviewed as one bundle), then the `paper-integration-v0.2` tag bump.

If PI defers or rejects: trigger `Hold BETA-2b canonical adoption pending PI/advisor verdict` (no-op; current state at `ab12e7e` is the resting state) or `Close BETA-2b track — PI rejected` (appends Plan v1.3.3.1 amendment; manuscript stays on `paper-integration-v0.1`).

If PI requests V3 first: trigger `Go run BETA-2b V3 full canonical (after V1+V2 pass)`. Estimated ~5-7 hr GPU on RTX 5090 + Qwen3-32B-AWQ. V3 output augments evidence ladder; manuscript adoption decision still requires separate PI sign-off.

## What this summary explicitly does not do

This summary does **not** modify any manuscript source file, recompute paired statistics, write Plan v1.3.4, run GPU, move any tag, or merge any branch. It is a decision-surfacing artifact for PI review only. The full quantitative grounding lives in the committed simulation at `ab12e7e`.
