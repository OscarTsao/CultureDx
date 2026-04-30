# Gap E BETA-2b Manuscript-Impact Simulation — Round 138

**Status:** Simulation only. Read-mostly. Single new uncommitted file. NOT a manuscript edit. NOT a commit. NOT a PR.
**Source HEAD:** `34ca778` on `origin/feature/gap-e-beta2-implementation`
**Frozen tag:** `paper-integration-v0.1 → c3b0a46` (must NOT move)
**Frozen main:** `origin/main-v2.4-refactor → 3d5e014` (must NOT move)
**Authorization:** Plan v1.3.3 §6 Path α + Round 137 verdict.
**Scope:** Answer the 8 questions in Plan v1.3.3 §6 Path α to surface what would change in the manuscript IF BETA-2b is adopted as canonical. No manuscript-source files are modified by this simulation.

---

## 0. Adoption-status disclaimer (must remain prominent)

> The numbers below are projected from BETA-2b CPU projection (commit `a960616`) and CPE-validated against the production helper (commit `a08ebb3`). They are NOT manuscript-canonical. They become manuscript-canonical only after PI sign-off + manuscript-impact PR + `paper-integration-v0.2` tag bump per Plan v1.3 §8 Gate sequence. This file is a simulation, not an adoption.

The simulation is grounded on:
- **Current canonical** = `paper-integration-v0.1@c3b0a46` SECTION_5_4.md (byte-identical between paper-integration-v0.1 and current feature-branch HEAD)
- **BETA-2b** = projection numbers from `GAP_E_BETA2B_PROJECTION_AUDIT.md` §7 (CPE-validated per `a08ebb3`)

V3 GPU full canonical is deferred per Plan v1.3.3 §3. CPE evidence substitutes for V3 in this simulation.

---

## 1. Which Table 4 values change under BETA-2b adoption?

### Panel A — LingxiDiag-16K (N=1000)

| Mode | Metric | Current canonical (c3b0a46) | BETA-2b projection | Δ |
|---|---|---:|---:|---:|
| ICD-10 | 2-class | .778 | **.820** | **+4.2pp** |
| ICD-10 | 4-class | .447 | .453 | +0.6pp |
| ICD-10 | Top-1 | .507 | **.524** | **+1.7pp** |
| ICD-10 | Top-3 | .800 | .799 | −0.1pp |
| ICD-10 | macro-F1 | .199 | .181 | −1.8pp |
| ICD-10 | weighted-F1 | .457 | .433 | −2.4pp |
| ICD-10 | Overall | .514 | .548 | +3.4pp |
| DSM-5 | 2-class | .767 | **.808** | **+4.1pp** |
| DSM-5 | 4-class | .476 | .450 | −2.6pp |
| DSM-5 | Top-1 | .471 | **.530** | **+5.9pp** |
| DSM-5 | Top-3 | .803 | .805 | +0.2pp |
| DSM-5 | macro-F1 | .188 | .199 | +1.1pp |
| DSM-5 | weighted-F1 | .421 | .443 | +2.2pp |
| DSM-5 | Overall | .506 | .549 | +4.3pp |
| Both | (all) | (= ICD-10) | (= ICD-10) | — |

### Panel B — MDD-5k (N=925)

| Mode | Metric | Current canonical (c3b0a46) | BETA-2b projection | Δ |
|---|---|---:|---:|---:|
| ICD-10 | 2-class | .890 | .744 | **−14.6pp** |
| ICD-10 | 4-class | .444 | **.624** | **+18.0pp** |
| ICD-10 | Top-1 | .597 | .592 | −0.5pp |
| ICD-10 | Top-3 | .853 | .842 | −1.1pp |
| ICD-10 | macro-F1 | .197 | .197 | 0.0pp |
| ICD-10 | weighted-F1 | .514 | .533 | +1.9pp |
| ICD-10 | Overall | .566 | .599 | +3.3pp |
| DSM-5 | 2-class | .912 | .730 | **−18.2pp** |
| DSM-5 | 4-class | .520 | **.613** | **+9.3pp** |
| DSM-5 | Top-1 | .581 | .580 | −0.1pp |
| DSM-5 | Top-3 | .842 | .832 | −1.0pp |
| DSM-5 | macro-F1 | .230 | .210 | −2.0pp |
| DSM-5 | weighted-F1 | .526 | .512 | −1.4pp |
| DSM-5 | Overall | .584 | .599 | +1.5pp |
| Both | (all) | (= ICD-10) | (= ICD-10) | — |

### Panel C — Both-mode pass-through (Both vs ICD-10 agreement)

| Pair | LingxiDiag-16K | MDD-5k |
|---|---:|---:|
| Current canonical: 1000/1000 + 925/925 (15/15 metric keys identical) | unchanged | unchanged |
| BETA-2b: 1000/1000 + 925/925 (4/4 output fields bit-identical) | unchanged | unchanged |

Both-mode pass-through framing is preserved. No change to §5.4 «Both mode is therefore an ICD-10 architectural pass-through» claim.

### Headline observations

1. **EM is not in current Table 4** — current §5.4 Table 4 reports {2c, 4c, Top-1, Top-3, mF1, wF1, Overall}. EM (+40 to +53 percentage points under BETA-2b) is the most dramatic improvement but does not currently appear in Table 4. Adding EM is a separate manuscript decision, not forced by Gap E.
2. **Top-1 changes are modest** (−0.5 to +5.9pp). The headline LingxiDiag DSM-5 outlier (+5.9pp) is the largest single-mode shift; all others are within ±2pp.
3. **2-class and 4-class metrics shift in OPPOSITE directions on MDD-5k** (2c down 14-18pp; 4c up 9-18pp). This is a substantive narrative-level change that needs explanation in §5.4 (likely root cause: BETA-2b's primary-locked output makes more F41.1 → F41 collapse decisions explicit, changing the 2c F41.2-exclusion arithmetic).
4. **macro-F1 / weighted-F1 directional changes are mixed**, generally within ±2pp.

---

## 2. Does §5.4 dual-standard interpretation change?

### Current §5.4 SECTION_5_4.md narrative claims that would need re-examination

Three current §5.4 claims are **directionally affected** by BETA-2b. Quoting from current draft (`paper-integration-v0.1:docs/paper/drafts/SECTION_5_4.md`):

**Current claim 1 (line 25):**
> "On LingxiDiag-16K, DSM-5-only mode is lower than ICD-10 mode on Top-1 (0.471 vs 0.507, −3.6pp), weighted-F1 (0.421 vs 0.457, −3.6pp), Overall (0.506 vs 0.514, −0.8pp), macro-F1 (0.188 vs 0.199, −1.1pp), and 2-class accuracy (0.767 vs 0.778, −1.1pp), and slightly higher on 4-class accuracy (0.476 vs 0.447, +2.9pp) and Top-3 (0.803 vs 0.800, +0.3pp)."

**BETA-2b version**: «DSM-5-only mode is **slightly higher than** ICD-10 mode on Top-1 (0.530 vs 0.524, **+0.6pp**), Top-3 (0.805 vs 0.799, +0.6pp), macro-F1 (0.199 vs 0.181, +1.8pp), weighted-F1 (0.443 vs 0.433, +1.0pp), Overall (0.549 vs 0.548, +0.1pp), and slightly **lower on** 4-class (0.450 vs 0.453, −0.3pp) and 2-class (0.808 vs 0.820, −1.2pp).»

**Direction reversal**: under BETA-2b, DSM-5 mode is no longer uniformly worse on the primary-prediction metrics on LingxiDiag. The original «DSM-5 lower on most metrics» narrative weakens substantially.

**Current claim 2 (line 38):**
> "On MDD-5k, DSM-5-only mode is lower than ICD-10 mode on Top-1 (0.581 vs 0.597, −1.6pp) and Top-3 (0.842 vs 0.853, −1.1pp), but higher on 2-class (0.912 vs 0.890, +2.2pp), 4-class (0.520 vs 0.444, +7.6pp), macro-F1 (0.230 vs 0.197, +3.3pp), weighted-F1 (0.526 vs 0.514, +1.3pp), and Overall (0.584 vs 0.566, +1.8pp)."

**BETA-2b version**: «On MDD-5k, DSM-5-only mode is slightly lower on Top-1 (0.580 vs 0.592, −1.2pp) and Top-3 (0.832 vs 0.842, −1.0pp), 2-class (0.730 vs 0.744, −1.4pp), 4-class (0.613 vs 0.624, −1.1pp), and macro-F1 (0.210 vs 0.197, +1.3pp), with very small Overall gap (0.599 vs 0.599).»

**Convergence**: under BETA-2b, the LingxiDiag-vs-MDD pattern flips less cleanly. MDD-5k DSM-5 is no longer broadly stronger than ICD-10; differences are within ±2pp on most metrics.

**Current claim 3 (line 56-57):**
> "DSM-5-only mode widens the F32/F41 diagnostic-error asymmetry described in §5.3 on both datasets. On MDD-5k, the F41→F32 / F32→F41 asymmetry ratio increases from 3.97× under ICD-10 mode to 7.24× under DSM-5-only mode; on LingxiDiag-16K, the paired bootstrap of (DSM-5 − ICD-10) Δratio is +3.13 with a 95% CI of [+1.12, +7.21] (CI excludes zero)."

**BETA-2b version** (per `GAP_E_BETA2B_PROJECTION_AUDIT.md` §10 + §5.3 cascade table):

| Mode | F32→F41 | gold_F32 | F41→F32 | gold_F41 | asymmetry ratio |
|---|---:|---:|---:|---:|---:|
| Lingxi ICD-10 (BETA-2b) | 30 | 370 | 207 | 394 | 6.61 |
| Lingxi DSM-5 (BETA-2b) | 41 | 370 | 196 | 394 | **4.82** |
| MDD ICD-10 (BETA-2b) | 35 | 408 | 159 | 308 | 5.15 |
| MDD DSM-5 (BETA-2b) | 32 | 408 | 168 | 308 | 6.54 |

- LingxiDiag: DSM-5 **IMPROVES** asymmetry (4.82 vs 6.61) — **direction reversed** vs current
- MDD-5k: DSM-5 **worsens** asymmetry but less (6.54 vs 5.15, +1.39 instead of +3.27) — same direction

The MDD claim («3.97 → 7.24 ICD-10 → DSM-5») becomes «5.15 → 6.54» under BETA-2b, with smaller asymmetry gap. The LingxiDiag paired-bootstrap claim («Δratio = +3.13, CI excludes zero») would likely **flip sign** under BETA-2b (DSM-5 becomes lower than ICD-10), and the bootstrap CI must be recomputed.

**Verdict for §5.4 dual-standard interpretation**: The current «DSM-5 widens F32/F41 asymmetry on both datasets» claim becomes «MDD-5k preserves the direction with smaller magnitude; LingxiDiag direction reverses» — substantively different narrative.

---

## 3. Does the DSM-5 v0 caveat strengthen, weaken, or shift?

**Current §5.4 caveat (line 8 + line 62):**
> "The DSM-5 templates are LLM-drafted v0 (`dsm5_criteria.json`, version `0.1-DRAFT`, source-note `UNVERIFIED`); we therefore treat DSM-5 outputs as experimental audit observations rather than clinically validated DSM-5 diagnoses."

> "These results support dual-standard auditing as a way to expose standard-sensitive trade-offs, not as evidence that DSM-5 v0 is superior or more robust"

**Effect of BETA-2b adoption on this caveat:**

The caveat **must remain** and arguably **shifts in framing**:

- Under current canonical: DSM-5 looks broadly worse than ICD-10 on most LingxiDiag metrics → the «not superior» claim is well-supported by raw numbers.
- Under BETA-2b: DSM-5 is slightly better than ICD-10 on LingxiDiag Top-1 (+0.6pp), F32/F41 asymmetry, and F42 recall → the «not superior» claim risks looking inconsistent with the table.

**Recommended caveat wording shift**:

The §5.4 caveat should add a line clarifying that **the BETA-2b primary-locked output exposes a different DSM-5 / ICD-10 trade-off pattern than the BETA-2a (veto-driven) baseline**, and that **none of the DSM-5 numbers — improved or worsened — should be interpreted as clinical validation of the v0 schema**.

This is a **shift, not a weakening**: the caveat's clinical-validation point remains, but the empirical-pattern wording must change to reflect BETA-2b's reversal of LingxiDiag DSM-5 trade-offs.

The §7.2 «DSM-5 v0 unverified scope» disclaimer stays unchanged.

---

## 4. Does F32/F41 asymmetry discussion change?

**Yes, substantively.** Three places in the current manuscript reference F32/F41 asymmetry that would shift:

### 4.1 Abstract (line 13)
> "On MDD-5k, the F32/F41 error-asymmetry ratio decreased from 189× under a single-LLM baseline to 3.97× under MAS ICD-10."

Under BETA-2b, MAS ICD-10 ratio on MDD-5k = **5.15** (not 3.97). The «189× → 3.97×» becomes «189× → 5.15×» — **still a large decrease but the precise number changes**. Abstract claim type («single-LLM baseline → MAS ICD-10 dramatic improvement») stays valid; specific ratio value changes.

### 4.2 §5.4 (line 57)
> "On MDD-5k, the F41→F32 / F32→F41 asymmetry ratio increases from 3.97× under ICD-10 mode to 7.24× under DSM-5-only mode"

Under BETA-2b: MDD-5k ICD-10 = 5.15, DSM-5 = 6.54. The «3.97× → 7.24×» becomes «5.15× → 6.54×» — same direction, smaller gap.

### 4.3 §5.4 (line 57, second sentence)
> "on LingxiDiag-16K, the paired bootstrap of (DSM-5 − ICD-10) Δratio is +3.13 with a 95% CI of [+1.12, +7.21] (CI excludes zero)."

Under BETA-2b: LingxiDiag ICD-10 = 6.61, DSM-5 = 4.82. The Δratio sign **likely flips** (DSM-5 becomes LOWER asymmetry than ICD-10). The paired bootstrap must be recomputed; the CI may now include zero or be entirely negative.

**Footprint of F32/F41 narrative changes:**

- 1 abstract number (189× → 3.97× becomes 189× → 5.15×)
- 1 §5.4 ratio pair (3.97×/7.24× becomes 5.15×/6.54×)
- 1 §5.4 paired-bootstrap result (sign and CI must be recomputed; current «+3.13, CI excludes zero» is BETA-2a-conditional)
- §5.3 narrative about F32/F41 cascade: needs targeted wording change to reflect that BETA-2b weakens the «DSM-5 worsens asymmetry» claim
- §5.3 paired McNemar / bootstrap stats: must be recomputed on BETA-2b predictions

This is **substantive narrative re-examination**, not a one-number-swap.

---

## 5. Does F42 recall discussion change?

**Yes, dramatically — this is the largest narrative shift.** F42 recall changes are referenced in:

### Current state (per BETA-2a / paper-integration-v0.1)

| Mode | F42 recall (current canonical) | F42 recall (BETA-2b) | Δ |
|---|---:|---:|---:|
| Lingxi ICD-10 | 52.0% | 52.0% | 0.0pp |
| Lingxi DSM-5 | **12.0%** | **56.0%** | **+44.0pp** |
| MDD ICD-10 | 38.5% | 38.5% | 0.0pp |
| MDD DSM-5 | **15.4%** | 38.5% | **+23.1pp** |

### Current §5.4 claim (line 59)
> "DSM-5-only mode also reduces F42/OCD recall on both datasets; the magnitude depends on the slice or class definition and is reported in §7.6, where we treat F42/OCD as a v0 schema limitation rather than evidence against dual-standard auditing in general."

**Under BETA-2b: this claim becomes FALSE on LingxiDiag** (DSM-5 = 56.0% > ICD-10 = 52.0%) and **dramatically reduced on MDD-5k** (DSM-5 = 38.5% = ICD-10 = 38.5%, no gap).

The «DSM-5-only mode reduces F42/OCD recall on both datasets» claim must either be **deleted** or **rewritten** to reflect that the F42 recall collapse was a veto-effect artifact, not a DSM-5 schema effect.

### §7.6 (F42 limitation)

§7.6 currently treats F42 as a «v0 schema limitation». Under BETA-2b, the F42 recall problem **does not exist on LingxiDiag DSM-5** — it was caused by the veto path overriding `ranked[0]` F42 candidates. §7.6 framing must be adjusted: F42 might still be a v0 schema limitation in some sense, but it is no longer empirically supported by the recall numbers.

**Footprint of F42 narrative changes:**

- 1 §5.4 claim (DSM-5 reduces F42 recall on both datasets) — **delete or rewrite**
- §7.6 «F42 v0 schema limitation» framing — **adjust** (still acknowledge v0 schema is unverified; remove empirical recall-collapse evidence)
- Any §5 limitation prose referencing F42 collapse — re-examine

The F42 narrative shift is **the largest single piece of work** triggered by BETA-2b adoption.

---

## 6. Does Abstract need to stay unchanged?

**Recommended: Abstract remains unchanged in 4 of 5 quantitative claims; 1 claim shifts a number.**

Going through current Abstract (`docs/paper/drafts/ABSTRACT.md`) line-by-line:

| Line | Current claim | BETA-2b verdict |
|---|---|---|
| 12 | "Stacker LGBM reached Top-1 0.612 versus reproduced TF-IDF 0.610" | **UNCHANGED** — Gap E doesn't touch stacker (per Plan v1.3.3 §4) |
| 13 | "F32/F41 error-asymmetry ratio decreased from 189× under a single-LLM baseline to 3.97× under MAS ICD-10" | **CHANGED** — 3.97 → 5.15 (still big decrease) |
| 14 | "TF-IDF/Stacker model-discordance flagged 26.4% of LingxiDiag cases at 2.06× error enrichment" | **UNCHANGED** — TF-IDF stacker independent of Gap E |
| 15 | "Dual-standard evaluation exposed DSM-5-v0 metric-specific trade-offs while Both mode preserved ICD-10 primary output with DSM-5 sidecar audit evidence, not an ensemble" | **UNCHANGED in framing**; the «trade-offs» wording survives both veto-driven and primary-locked analyses |
| 22 | "CultureDx supports a parity-plus-audit framing rather than an accuracy-superiority or clinical-deployment claim" | **UNCHANGED** — top-line conclusion is parity-plus-audit, neither version of BETA-2 affects parity |

**Verdict: Abstract requires 1 quantitative number update (line 13: 3.97 → 5.15) and remains otherwise unchanged.** This is the smallest possible Abstract footprint.

If PI prefers to mention EM (the +40-53pp improvement), an additional line could be added under «Results». But this is a stylistic decision, not a forced change.

---

## 7. What exact files would need revision if PI approves adoption?

Cross-referencing `GAP_E_BETA2B_PROJECTION_AUDIT.md` §15 and §16 with the §1-§6 analysis above:

### 7.1 Required revisions (cannot avoid under BETA-2b adoption)

| File | Change scope | Estimated diff size |
|---|---|---|
| `docs/paper/drafts/SECTION_5_4.md` | Re-derive Panel A + Panel B numerical tables; rewrite §5.4 lines 25, 38 narrative; rewrite F32/F41 asymmetry sentence (line 56-57); rewrite or delete F42 recall claim (line 59); add BETA-2b primary-locked methodology footnote | ~30-40 lines modified |
| `docs/paper/drafts/SECTION_5_4_PREP.md` | Update prep tables and analysis to BETA-2b numbers | ~50-100 lines modified |
| `docs/paper/drafts/ABSTRACT.md` | Line 13: 3.97 → 5.15 | 1 line modified |
| `docs/paper/integration/ABSTRACT_PREP.md` | Sync Abstract prep references to BETA-2b numbers | ~5-10 lines modified |
| `docs/paper/drafts/SECTION_5_3.md` | Re-derive F32/F41 cascade tables and per-mode asymmetry under BETA-2b; recompute paired McNemar / bootstrap statistics | ~20-50 lines modified + statistical recomputation |
| `docs/paper/drafts/SECTION_5_5.md` | Likely small re-examination if it cites BETA-2a-specific numbers (currently 8 lines, low impact) | 0-5 lines modified |
| `docs/paper/drafts/SECTION_5_6.md` | Likely small re-examination (8 lines, low impact) | 0-5 lines modified |
| `docs/paper/integration/SECTION_5_7_INTEGRATION_REVIEW.md` | Re-examine integration review under BETA-2b | ~30-50 lines modified |
| `docs/paper/repro/REPRODUCTION_README.md` | Reference new tag `paper-integration-v0.2`; update predictions.jsonl path / commit reference | ~10-20 lines modified |
| `results/analysis/metric_consistency_report.json` | Recompute canonical values under BETA-2b primary-locked policy | full regeneration |
| New annotated tag `paper-integration-v0.2` | Plan v1.3 §8 Gate 8.6 | 1 tag added |

### 7.2 Required code change

| File | Change |
|---|---|
| `src/culturedx/modes/hied.py` | Already implemented behind feature flag (commit `b1c4474` + `3482021`); requires either flipping default to BETA-2b OR explicit user-facing flag documentation |
| `configs/overlays/final_output_beta2b.yaml` | Already created in `b1c4474`; no further change needed |

### 7.3 Required new plan

| File | Purpose |
|---|---|
| `docs/paper/integration/Plan_v1.3.4_BETA2b_canonical_adoption.md` | Records the canonical-adoption decision; supersedes Plan v1.3.3 on adoption (not before); declares predictions source-of-truth (`results/gap_e_beta2b_projection_20260430_164210/` or new GPU-rerun output if V3 reactivated) |

### 7.4 Files that must NOT be touched (per Plan v1.3.3 §5)

- `paper/` directory (legacy LaTeX skeleton — explicit out of Gap E scope)
- `paper-integration-v0.1` tag (frozen at `c3b0a46`)
- `origin/main-v2.4-refactor` HEAD (frozen at `3d5e014` until merge PR)
- `origin/master` (frozen at `3d3c079`)
- BETA-2a Round 114 prediction files (preserved as historical record on feature branch)
- `docs/paper/integration/Plan_v1.3_GapE.md` (parent plan, frozen)
- `docs/paper/integration/Plan_v1.3.2_BETA2b_Patch.md` (frozen)
- `docs/paper/integration/Plan_v1.3.3_BETA2b_CPE_deferral.md` (frozen, this simulation references it)
- `docs/paper/integration/GAP_E_CANONICAL_RUN_REVIEW.md` (Round 118 audit, frozen)
- `docs/paper/integration/GAP_E_BETA2B_PROJECTION_AUDIT.md` (Round 120 audit, frozen)
- `docs/paper/integration/GAP_E_NATIVE_OFFLINE_EQUIVALENCE_AUDIT.md` (Round 132 CPE audit, frozen)
- `docs/paper/integration/LOGIC_ENGINE_FINAL_OUTPUT_SANDBOX_REPORT.md` (sandbox report, frozen)

---

## 8. Smallest revision footprint that preserves narrative integrity

The smallest viable revision footprint is approximately:

```
1 abstract number (line 13: 3.97 → 5.15)
1 §5.4 panel A table (8 numbers)
1 §5.4 panel B table (8 numbers)
1 §5.4 narrative paragraph (LingxiDiag DSM-5 vs ICD-10 comparison, line 25)
1 §5.4 narrative paragraph (MDD-5k DSM-5 vs ICD-10 comparison, line 38)
1 §5.4 sentence on F32/F41 asymmetry (lines 56-57; needs recomputation of bootstrap CI on LingxiDiag)
1 §5.4 sentence on F42 recall (line 59; delete or rewrite)
1 §5.4 methodology footnote (new — declare BETA-2b primary-locked policy + cite Plan v1.3.4)
1 §5.3 cascade analysis (recompute paired McNemar / bootstrap on BETA-2b predictions)
1 §7.6 F42 limitation paragraph (adjust framing)
1 REPRODUCTION_README tag reference + path update
1 metric_consistency_report.json full regeneration
1 new annotated tag paper-integration-v0.2
1 new Plan v1.3.4 adoption record
```

Approximately **~10 manuscript files touched, ~100-200 lines modified**, plus regenerated metric file and new tag.

This footprint preserves the parity-plus-audit narrative, the dual-standard-not-ensemble framing, the «not clinical validation» disclaimer, the AIDA-Path / clinician-review-pending framing, and §5.1 hybrid stacker primary benchmark.

It changes the F42-collapse narrative (largest single shift), the DSM-5-uniformly-worse narrative on LingxiDiag, and the F32/F41 asymmetry direction on LingxiDiag. None of these are catastrophic but they are not nominal either — the §5.4 dual-standard discussion needs a coherent BETA-2b-conditioned rewrite.

---

## 9. Recommendation summary

### What the simulation suggests

| Question | Verdict |
|---|---|
| 1. Table 4 values change? | YES — most cells shift, several by 5-18pp |
| 2. §5.4 dual-standard interpretation? | YES — direction reverses on LingxiDiag DSM-5 |
| 3. DSM-5 v0 caveat? | SHIFTS framing, must remain |
| 4. F32/F41 asymmetry? | YES — partial direction reversal + ratio recomputation |
| 5. F42 recall? | YES — largest single shift; current claim becomes false on LingxiDiag |
| 6. Abstract unchanged? | MOSTLY — 1 number changes (3.97 → 5.15) |
| 7. Files needed? | ~10 manuscript files + 1 new plan + 1 new tag |
| 8. Smallest footprint? | ~100-200 lines manuscript modification + 1 metric file regeneration |

### Honest framing for PI / advisor review

BETA-2b adoption is **not cosmetic**. It produces:

- ✅ Closer alignment to Plan v1.3 §3 design lock (clauses #1, #4 now implemented)
- ✅ Resolution of LingxiDiag DSM-5 −5.9pp Top-1 outlier
- ✅ Cleaner narrative (F42 recall no longer mysteriously collapses)
- ✅ EM goes from ~3-6% to ~46-59% (largest improvement; not currently in Table 4)
- ⚠ Larger §5.4 narrative rewrite than a single-table number swap
- ⚠ §5.3 statistical results (F32/F41 paired bootstrap) must be recomputed
- ⚠ §7.6 limitation framing needs adjustment

The decision is **not** «adopt or reject». The decision is **«adopt now (Round 138-140)» vs «adopt after PI/advisor sees this simulation» vs «defer adoption past initial submission, document BETA-2b as a follow-up consistency improvement»**.

### What this simulation does NOT do

- Does NOT modify any manuscript source file.
- Does NOT recompute statistical procedures (paired McNemar, bootstrap CI). Those require the actual BETA-2b prediction files + the v4 evaluation contract; they are downstream of this simulation, not part of it.
- Does NOT decide adoption.
- Does NOT trigger any GPU work.
- Does NOT move any tag.
- Does NOT merge any branch.

### Recommended Round 139 trigger

Three honest options:

| Trigger | Effect |
|---|---|
| `Begin paper-integration-v0.2 adoption planning` | Authorize Plan v1.3.4 draft for canonical adoption + manuscript-impact PR + tag bump (per Plan v1.3.3 §7 trigger taxonomy) |
| `Hold BETA-2b canonical adoption pending PI/advisor verdict` | Path β; this simulation file remains as-is until PI input |
| `Surface this simulation to PI` | Generate a 1-page PI-facing summary derived from this simulation; PI reviews; subsequent triggers conditional on PI verdict |

The **strongly recommended** path is to surface this simulation to PI before committing to Plan v1.3.4. The narrative changes (especially F42 + LingxiDiag DSM-5 direction reversal) are substantive enough that PI should weigh in before the manuscript-impact PR is drafted.

---

## End of simulation

This file is **uncommitted** in working tree at `docs/paper/integration/GAP_E_BETA2B_MANUSCRIPT_IMPACT_SIMULATION.md`. No commit, no push, no tag, no merge. Decision between Round 139 trigger options is a Plan-level decision per Plan v1.3.3 §7.
