# Round 150 Sandbox — Comorbid Emission Policy Exhaustive Search

**Status:** Sandbox-only audit. NO file modification, NO commit, NO push, NO GPU, NO server.
**Source HEAD:** `2c82f42` on `feature/gap-e-beta2-implementation`
**Scope:** Test all sandbox-feasible policy variants (Tier 1A/1B/1C/1E/1F/2C/3A-mock/3C-mock) on existing prediction artifacts.
**Authorization:** Round 150 explicit trigger.

---

## 0. TL;DR — what we found

| Finding | Evidence |
|---|---|
| **1B-α (conservative veto) is a free win on DSM-5 modes** | LingxiDiag-DSM5: F1 0.453 → 0.504 (+5.1pp), EM +4.8pp, **0% emit rate** |
| **1B-α also marginally helps ICD-10 modes** | LingxiDiag-ICD10: F1 +0.5pp; MDD5k-ICD10: F1 +0.5pp |
| **1A-δ (cross-mode + pair + confirmed + DSM-top2) recovers some multi-label** | LingxiDiag: F1 +2.2pp, mgEM 11.6%, but sizeM drops 27% |
| **No policy hits gold's 8.6% emission rate** | All emission policies either emit ~0% (1B/1C/1F) or 25-80% (1A/1E/2C) |
| **Per-class threshold (1E) over-emits broadly** | met_ratio signal saturates, 28-56% emit across modes |
| **Combo (1B veto + 1F emit) is on Pareto frontier** | MDD5k-ICD10: F1 0.588, primary_correct 0.636 — best F1 across all |

---

## 1. Tier 1A — Cross-mode ensemble

Cross-mode signal (ICD-10 + DSM-5) provides genuinely new information not available within single mode.

### LingxiDiag (N=1000, 8.6% multi-label gold)

| Policy | emit% | EM | F1 | P | R | sgEM | mgEM | mgR | sizeM |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| REF: BETA-2b primary-only | 0.0% | 0.452 | 0.488 | 0.507 | 0.479 | 0.495 | 0.000 | 0.314 | 0.914 |
| 1A-α primary-disagree → emit both | 25.1% | 0.371 | 0.497 | 0.489 | 0.534 | 0.403 | 0.035 | 0.364 | 0.702 |
| 1A-β ICD primary + DSM rank2 if pair | 46.3% | 0.228 | 0.483 | 0.435 | 0.592 | 0.236 | 0.140 | 0.424 | 0.526 |
| 1A-γ both-modes-top3 + pair | 73.8% | 0.123 | 0.494 | 0.412 | 0.663 | 0.109 | 0.267 | 0.562 | 0.310 |
| **1A-δ rank2+pair+confirmed+DSMtop2** | 23.8% | 0.360 | **0.510** | 0.493 | 0.562 | 0.383 | 0.116 | 0.411 | 0.727 |

### MDD5k (N=925, 8.8% multi-label gold)

| Policy | emit% | EM | F1 | P | R | sgEM | mgEM | mgR | sizeM |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| REF: BETA-2b primary-only | 0.0% | 0.542 | 0.578 | 0.597 | 0.569 | 0.594 | 0.000 | 0.309 | 0.912 |
| 1A-α primary-disagree → emit both | 20.8% | 0.478 | 0.593 | 0.589 | 0.626 | 0.519 | 0.049 | 0.346 | 0.732 |
| 1A-β ICD primary + DSM rank2 if pair | 53.6% | 0.241 | 0.541 | 0.481 | 0.672 | 0.246 | 0.185 | 0.473 | 0.471 |
| 1A-γ both-modes-top3 + pair | 81.1% | 0.101 | 0.531 | 0.431 | 0.734 | 0.081 | 0.309 | 0.551 | 0.240 |
| 1A-δ rank2+pair+confirmed+DSMtop2 | 46.7% | 0.296 | 0.565 | 0.515 | 0.680 | 0.308 | 0.173 | 0.467 | 0.534 |

**Verdict:** 1A-δ on LingxiDiag is the only cross-mode variant with F1 > BETA-2b. On MDD5k, all cross-mode variants have lower F1 than BETA-2b. Cross-mode signal exists but is noisy.

---

## 2. Tier 1B — Conservative veto (THE FREE WIN)

This is the most surprising finding. Re-introducing veto under a strict condition (only veto when rank0 not confirmed AND rank1 confirmed) gives **EM and F1 improvements at zero emission cost**.

### Across all 4 modes

| Mode | BETA-2b EM | 1B-α EM | Δ EM | BETA-2b F1 | 1B-α F1 | Δ F1 |
|---|---:|---:|---:|---:|---:|---:|
| LingxiDiag-ICD10 | 0.452 | 0.458 | **+0.6pp** | 0.488 | 0.493 | +0.5pp |
| **LingxiDiag-DSM5** | 0.419 | **0.467** | **+4.8pp** | 0.453 | **0.504** | **+5.1pp** |
| MDD5k-ICD10 | 0.542 | 0.547 | +0.5pp | 0.578 | 0.583 | +0.5pp |
| MDD5k-DSM5 | 0.528 | 0.530 | +0.2pp | 0.563 | 0.566 | +0.3pp |

**1B-β variants (veto by met-ratio gap)** all WORSEN performance — different signal from 1B-α.

**Why 1B-α works:** When `ranked[0]` is NOT in `confirmed_set`, that's a strong signal Diagnostician's rank-1 is wrong. If `ranked[1]` IS in confirmed_set, switching to it is justified by logic-engine evidence. This is exactly the sandbox L2-R1 hypothesis Pass 3 we never explicitly tested as a standalone primary-selection rule.

**Implication:** BETA-2b's wholesale removal of veto threw out a useful signal. A precision-focused veto recovers most of paper-integration-v0.1's veto helps without the BETA-2a hurts.

---

## 3. Tier 1C — Top-2 abstention

| Mode | emit% | EM | F1 | mgEM |
|---|---:|---:|---:|---:|
| LingxiDiag-ICD10 (1C-α gap<0.02) | 7.4% | 0.425 | 0.484 | 0.047 |
| LingxiDiag-DSM5 (1C-α gap<0.02) | 0.6% | 0.419 | 0.455 | 0.000 |
| MDD5k-ICD10 (1C-α gap<0.02) | 14.9% | 0.475 | 0.578 | 0.074 |
| MDD5k-DSM5 (1C-α gap<0.02) | 2.5% | 0.517 | 0.562 | 0.000 |

**Verdict:** Mixed. On MDD5k-ICD10 emits 14.9% (closer to gold 8.8%) and recovers some mgEM, but EM drops -6.7pp. Top-2 abstention is plausible only if F1_set is the primary metric.

---

## 4. Tier 1E — Per-class threshold

Hand-coded thresholds per primary class (F32: 1.05, F42: 0.90, etc).

| Mode | emit% | EM | F1 | mgEM |
|---|---:|---:|---:|---:|
| LingxiDiag-ICD10 | 28.2% | 0.347 | 0.515 | 0.128 |
| LingxiDiag-DSM5 | 37.8% | 0.259 | 0.466 | 0.186 |
| MDD5k-ICD10 | 56.1% | 0.241 | 0.556 | 0.210 |
| MDD5k-DSM5 | 51.6% | 0.252 | 0.541 | 0.198 |

**Verdict:** Over-emits 28-56%. Per-class threshold concept is sound but **hand-crafted thresholds are wrong** — would need dev-split calibration. Negative result for the hand-crafted version.

---

## 5. Tier 1F — Combined gate (intersection of multiple signals)

All conditions: rank2 in DOMAIN_PAIRS + rank2 in confirmed + rank2_met ≥ 0.95 + |primary_met − rank2_met| ≤ 0.05.

| Mode | emit% | EM | F1 | mgEM | sizeM |
|---|---:|---:|---:|---:|---:|
| LingxiDiag-ICD10 | 3.6% | 0.440 | 0.487 | 0.047 | 0.888 |
| LingxiDiag-DSM5 | 0.0% | 0.419 | 0.453 | 0.000 | 0.914 |
| MDD5k-ICD10 | 11.7% | 0.492 | 0.581 | 0.074 | 0.828 |
| MDD5k-DSM5 | 1.4% | 0.520 | 0.563 | 0.000 | 0.898 |

**Verdict:** Closest emission rate to gold (3.6-11.7%). MDD5k-ICD10 F1 +0.3pp over BETA-2b. LingxiDiag-DSM5 conditions never trigger (0% emit). Most precise of all sandboxed gates.

---

## 6. Tier 2C — Calibrator disagreement (logic_engine vs Diagnostician)

| Mode | Policy | emit% | EM | F1 | mgR |
|---|---|---:|---:|---:|---:|
| LingxiDiag-ICD10 | 2C-α confirmed ∩ pair ∩ top3 | 64.8% | 0.182 | 0.517 | 0.552 |
| LingxiDiag-DSM5 | 2C-α | 74.2% | 0.108 | 0.488 | 0.564 |
| MDD5k-ICD10 | 2C-α | 76.6% | 0.126 | 0.544 | 0.551 |
| MDD5k-DSM5 | 2C-α | 77.1% | 0.124 | 0.538 | 0.545 |

**Verdict:** Over-emits 64-77%. logic_engine_confirmed_codes is too permissive — typically 5-8 codes confirmed per case. Not a useful disagreement signal as constructed.

---

## 7. Combo — 1B-α veto + 1F emission gate (best F1 across modes)

| Mode | emit% | EM | F1 | P | R | sgEM | mgEM |
|---|---:|---:|---:|---:|---:|---:|---:|
| LingxiDiag-ICD10 | (small) | 0.446 | **0.493** | 0.506 | 0.491 | 0.484 | 0.047 |
| LingxiDiag-DSM5 | 0.0% | **0.467** | **0.504** | 0.523 | 0.494 | 0.511 | 0.000 |
| **MDD5k-ICD10** | 11.7% | 0.497 | **0.588** | 0.589 | 0.609 | 0.538 | 0.074 |
| MDD5k-DSM5 | (small) | 0.522 | **0.566** | 0.582 | 0.561 | 0.572 | 0.000 |

**Best F1 across all 4 modes** when combining 1B-α primary selection + 1F-style strict comorbid gate.

---

## 8. Tier 3A mock — F1_set as primary metric (paper framing alternative)

If paper uses F1_set instead of EM as primary metric, BETA-2b is **not** the best. Combo (1B+1F) wins on all 4 modes:

| Mode | BETA-2b F1 | Combo F1 | Δ |
|---|---:|---:|---:|
| LingxiDiag-ICD10 | 0.488 | **0.493** | +0.5pp |
| LingxiDiag-DSM5 | 0.453 | **0.504** | **+5.1pp** |
| MDD5k-ICD10 | 0.578 | **0.588** | **+1.0pp** |
| MDD5k-DSM5 | 0.563 | **0.566** | +0.3pp |

---

## 9. Tier 3C mock — Stratified report by gold size

The cleanest narrative honesty story.

### LingxiDiag-ICD10 stratified

| Bucket (N) | Policy | EM | F1 |
|---|---|---:|---:|
| size=1 (914) | D0 BETA-2b | 0.495 | 0.495 |
| size=1 (914) | 1B-α veto | **0.501** | **0.501** |
| size=1 (914) | Combo (1B+1F) | 0.484 | 0.499 |
| size>=2 (86) | D0 BETA-2b | 0.000 | 0.421 |
| size>=2 (86) | 1B-α veto | 0.000 | 0.413 |
| size>=2 (86) | Combo (1B+1F) | **0.047** | 0.426 |

### LingxiDiag-DSM5 stratified

| Bucket | Policy | EM | F1 |
|---|---|---:|---:|
| size=1 | D0 BETA-2b | 0.458 | 0.458 |
| size=1 | **1B-α veto** | **0.511** | **0.511** |
| size=1 | Combo | **0.511** | **0.511** |
| size>=2 | D0 BETA-2b | 0.000 | 0.397 |
| size>=2 | 1B-α veto | 0.000 | **0.428** |
| size>=2 | Combo | 0.000 | **0.428** |

### Key interpretation

- **size=1 cases (~91%)**: 1B-α veto and Combo dominate. BETA-2b is suboptimal here.
- **size>=2 cases (~9%)**: D0 has EM=0 by construction. Combo recovers tiny EM (4.7-7.4% on a few modes). F1 picks up modestly.
- **No policy is best everywhere** — stratified report exposes the trade-off.

---

## 10. Synthesis — Pareto frontier across all sandbox results

| Policy | LingxiDiag-ICD10 F1 | LingxiDiag-DSM5 F1 | MDD-ICD10 F1 | MDD-DSM5 F1 | Pareto? |
|---|---:|---:|---:|---:|:---:|
| BETA-2b primary-only | 0.488 | 0.453 | 0.578 | 0.563 | dominated |
| 1B-α conservative veto | 0.493 | 0.504 | 0.583 | 0.566 | **YES** |
| 1A-δ cross-mode strict | 0.510 | — | 0.565 | — | partial |
| Combo (1B+1F) | 0.493 | 0.504 | **0.588** | 0.566 | **YES** |
| 1F combined gate | 0.487 | 0.453 | 0.581 | 0.563 | dominated |

**Pareto-optimal candidates: 1B-α and Combo (1B+1F).**

---

## 11. Items NOT tested in sandbox (need server / training)

| Tier | Item | What needed | Time |
|---|---|---|---|
| 1D | Case difficulty signal | Cross-ref dataset original case text | depends on data load |
| 2A | Re-prompt at emission | LLM call on ambiguous cases | ~30 min GPU |
| 2B | Hierarchical primary+comorbid prompt | Full canonical rerun | 5-7 hr GPU |
| 2D | Two-stage classifier | Train classifier on dev split | 1-2 hr CPU + dev data |

Server-side prompts for these items in `/tmp/server_prompts.md`.

---

## 12. Architectural changes (Tier 4) — explained, NOT recommended now

### 4A — Add MultiLabelDiagnostician parallel agent

A new agent runs in parallel with the single-label Diagnostician, specifically prompted/trained for multi-label cases. Pipeline merges the two agents' outputs.

**Cost:** New agent + ~500 lines code + GPU rerun + paper architecture rewrite.
**Why deferred:** Tier 4 work is incompatible with June/August deadline. Not enough engineering bandwidth for new agent + integration + smoke + canonical + manuscript.

### 4B — Reframe pipeline as Detection + Set selection

Two-stage formulation:
1. Detection: high-recall find all candidates (target recall 95%, precision 50%).
2. Set selection: from detected pool, select final set matching gold size.

**Cost:** Full pipeline refactor + new prompts + paper rewrite.
**Why deferred:** Same as 4A. Also breaks all existing artifacts (predictions, baselines, comparisons).

### 4C — Probabilistic output (per-class score + threshold curve)

Instead of emitting set, emit per-class probability. Evaluation uses threshold curve / AUC.

**Cost:** Change evaluation contract, paper rewrite, baselines need re-derivation.
**Why deferred:** Reviewer would expect per-class probabilities to come from calibrated classifier (we have stacker LGBM but it's a 12-class classifier, not per-class probabilities for multi-label).

---

## 13. Recommended next steps

### If user adopts Combo (1B+1F) — projected Δ vs BETA-2b

| Mode | EM Δ | F1 Δ | size>=2 EM | Cost |
|---|---:|---:|---:|---|
| LingxiDiag-ICD10 | -0.6pp | +0.5pp | +4.7pp | helper extension ~30 lines |
| LingxiDiag-DSM5 | +4.8pp | +5.1pp | 0.0pp | same helper |
| MDD5k-ICD10 | -4.5pp | +1.0pp | +7.4pp | same |
| MDD5k-DSM5 | -0.6pp | +0.3pp | 0.0pp | same |

**Mixed.** F1 better on all 4 modes. EM mixed (DSM5 +4.8pp, ICD10 -0.6pp average). size>=2 cases recovered modestly.

### If user adopts only 1B-α (conservative veto, NO emission)

| Mode | EM Δ | F1 Δ | size>=2 EM |
|---|---:|---:|---:|
| LingxiDiag-ICD10 | +0.6pp | +0.5pp | 0.0pp |
| LingxiDiag-DSM5 | +4.8pp | +5.1pp | 0.0pp |
| MDD5k-ICD10 | +0.5pp | +0.5pp | 0.0pp |
| MDD5k-DSM5 | +0.2pp | +0.3pp | 0.0pp |

**Strictly better than BETA-2b on all 4 modes**, no emission, no multi-label change. Safest improvement.

### If user keeps BETA-2b as-is + adopts 3C (stratified report)

No code change. Paper §5.4 adds stratified table by gold size (size=1 vs size>=2). Most honest narrative; surfaces size>=2 limitation explicitly. Still sufficient for paper-integration-v0.2 timeline.

---

## 14. Files NOT modified

- `src/culturedx/modes/hied.py` — UNTOUCHED
- `src/culturedx/modes/*` — UNTOUCHED
- `docs/paper/drafts/*` — UNTOUCHED
- `docs/paper/integration/Plan_v1.3*.md` — UNTOUCHED
- `docs/paper/integration/GAP_E_*.md` — UNTOUCHED
- `paper-integration-v0.1` tag — UNTOUCHED (still at c3b0a46)
- `origin/main-v2.4-refactor` — UNTOUCHED (still at 3d5e014)
- `feature/gap-e-beta2-implementation` HEAD — UNCHANGED (still at 2c82f42)
- All committed prediction artifacts — UNTOUCHED

This audit is read-only. The only files written are scratch scripts in `/tmp/`.
