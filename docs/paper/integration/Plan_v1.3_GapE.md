# Plan v1.3 — Gap E: Logic-Engine Final-Output Redesign

**Status:** Plan-only. Non-binding. Not adopted.
**Source HEAD when drafted:** `df05637` (docs(paper): add logic-engine final-output sandbox report)
**Source-of-truth predecessors:** Plan v1.2 (`692246a`) covering Gaps A / B / C
**Frozen tag (must not move):** `paper-integration-v0.1 → c3b0a46`
**Author context:** CultureDx project, Round 106 plan-track gate
**Scope:** Engineering plan for a candidate final-output redesign track. Adoption requires explicit PI sign-off and a separate execution PR.

---

## 0. Scope and non-binding status

This document is a **plan**, not an execution. It records the design conclusions reached in the Round 96-104 sandbox track (committed at `df05637` as `docs/paper/integration/LOGIC_ENGINE_FINAL_OUTPUT_SANDBOX_REPORT.md`) and proposes a candidate Gap E — *Logic-Engine Final-Output Redesign* — for future PI review.

**Non-binding scope statement:**

> This plan does NOT modify production code, does NOT update any §1-§7 / Abstract / Table 2 / Table 4 / `metric_consistency_report.json` / `REPRODUCTION_README.md`, does NOT move the `paper-integration-v0.1` tag, and does NOT adopt R3-α / R3-β as canonical policy. Adoption of any policy listed in §4 requires:
>   1. PI sign-off
>   2. A separate execution-track PR with frozen-policy declaration
>   3. Canonical re-evaluation under a predeclared protocol
>   4. A separate manuscript-impact PR
>   5. A new integration tag (e.g., `paper-integration-v0.2`)

The contents of this plan that DO concern code/manuscript change (§3 design lock, §4 candidate policies) are **statements of design intent under the conditions of adoption**, not adopted decisions. The contents that are immediately binding are the gates: §5 (anti-leakage), §6 (production-code gate), §7 (manuscript-impact gate).

**Relationship to Plan v1.2:**

Plan v1.2 (Gaps A / B / C) remains the source of truth for stacker MAS attribution, DtV vs Full HiED clarification, and the multi-backbone out-of-scope decision. Plan v1.3 introduces a **new, parallel track** (Gap E) and does NOT modify or supersede Plan v1.2. Both plans are in scope simultaneously; Gap E does not depend on Gap A / B execution and vice versa.

**Why "Gap E" and not "Gap D":**

Gap D (evidence-pipeline ablation: somatization / verifier / RAG on/off) was declared out-of-scope per Round 91 / 92 verdicts and remains out-of-scope. Gap E is a separate engineering-design track concerning final-output channel separation, not evidence-pipeline component ablation.

---

## 1. Current problem

Under the current Full HiED pipeline, the benchmark prediction set mixes two functionally distinct outputs:

- The **primary diagnosis** (single-label, intended for Top-1 / Top-3 / 12-class classification metrics)
- The **comorbidity emissions** (multi-label clinical-audit annotations, currently emitted in 90.3-93.5% of cases per `df05637` cross-dataset replay)

Under the v4 evaluation contract (12-class paper-parent Top-1 / Top-3 from primary; 2-class / 4-class from raw `DiagnosisCode`), exact-match (EM) is computed as set-equality between the predicted diagnosis set and the gold parent set. The current pipeline's high comorbidity emission rate causes the predicted set to exceed the gold set size in ≥ 90% of cases, where 91-92% of gold sets are size-1.

Numerical symptoms (canonical at `df05637`):

| Mode | Top-1 | Top-3 | EM | Multilabel emit rate |
|---|---:|---:|---:|---:|
| LingxiDiag-16K × ICD-10 | 0.5070 | 0.8000 | 0.0460 | 92.5% |
| LingxiDiag-16K × DSM-5 | 0.4710 | 0.8040 | 0.0290 | 91.9% |
| MDD-5k × ICD-10 | 0.5968 | 0.8530 | 0.0638 | 90.3% |
| MDD-5k × DSM-5 | 0.5805 | 0.8422 | 0.0357 | 93.5% |

Top-1 and Top-3 are not catastrophically broken; EM is. The signal is detection-positive (gold appears in Diagnostician top-5 at 86.8% in LingxiDiag ICD-10) but emission-saturated (the comorbidity gate is too permissive).

**This is an output-channel design problem, not a detection problem.**

---

## 2. Sandbox evidence

The Round 96-101 sandbox is committed at `df05637` and consists of:

- `docs/paper/integration/LOGIC_ENGINE_FINAL_OUTPUT_SANDBOX_REPORT.md` (455 lines, 13 sections) — main artifact
- `results/sandbox/cross_dataset_replay_20260429_121100.json` — raw 6-mode × 4-policy replay
- `results/sandbox/cross_dataset_replay_20260429_121100.md` — markdown summary
- `scripts/sandbox/*.py` — 9 sandbox scripts (L0/L1/L2/L3 + value audit + cross-dataset replay)

**Status of these artifacts:** engineering-diagnosis evidence. NOT canonical paper metrics. The non-canonical disclaimer is preserved in the sandbox report §1 and §13 and must remain.

**Key sandbox findings (cited from `LOGIC_ENGINE_FINAL_OUTPUT_SANDBOX_REPORT.md`):**

- **L0 module oracles**: Diagnostician = Union ceiling (Top-1 = 0.524). Checker / logic engine signals are strictly weaker. Pipeline override is net −17 Top-1 cases (the 0.524 → 0.507 gap).
- **L0 failure taxonomy**: Type F (137 cases, gold-as-comorbid) + Type G (131 cases, gold-in-confirmed-not-primary) account for 27% of all cases — recoverable in principle, but not by deterministic rule reordering.
- **L1 deterministic rule replay**: Rule K (no override) Pareto-dominates baseline (Top-1 +1.7pp, EM +42.3pp on LingxiDiag ICD-10 N=1000). Checker-rerank-DtV catastrophically fails (Top-1 0.5070 → 0.3110).
- **L2 sweeps + L2-redesign (Round 99)**: Threshold sweeps cannot improve Top-1 beyond 0.524 ceiling. Checker reranking of rank 2-5 degrades Top-3 / MRR. Conservative veto has no useful firing condition.
- **L3 learnable ranker**: LR / LGBM cannot exceed Diagnostician ceiling. LambdaRank trades Top-1 for mF1 via class-prior bias (negative result).
- **Cross-dataset replay (4 unique mode/dataset cells, after Both = ICD-10 duplication)**: R3-α universally improves Top-1 (+0.76pp to +5.90pp) and EM (+42 to +51pp); mF1 / F32-F41 asymmetry / F42 recall vary by mode. R3-β preserves or improves mF1 in 3 of 4 unique cells.

These findings are **inputs to this plan**, not adopted as paper claims.

---

## 3. Design lock

Under the conditions of adoption (per §0, §6, §7), the candidate redesign locks the following six-clause policy:

```
Diagnostician-primary / checker-audited output

1. Diagnostician rank-1 = benchmark primary.
2. Diagnostician original ranking = Top-k differential.
3. Checker = audit trace, evidence explanation, uncertainty signal.
4. Checker does not freely rerank or override primary.
5. Comorbidity annotations live in a separate field, not in the benchmark prediction set.
6. Benchmark prediction set is primary-only (single-label).
```

This policy is **conditional**. It becomes binding only after the §6 production-code gate and §7 manuscript-impact gate are cleared.

**Stop-decisions** (binding regardless of adoption decision):

```
STOP — these design lines are refuted by sandbox L1 / L2 evidence:

- checker free primary override (current pipeline behavior; net −17 Top-1)
- checker rank 2-5 reranking by met_ratio / decisive / composite (degrades Top-3 / MRR)
- checker conservative veto under any tested margin / decisive threshold
- DtV-rerank-by-checker (Top-1 collapse to 0.3110)
- forced single-label EM via current-primary keep (Rule H; Pareto-dominated by Rule K)
```

These stop-decisions apply immediately and do not require PI sign-off — they are negative findings from a frozen sandbox.

---

## 4. Candidate policies

The candidate-policy set (NONE adopted by this plan) is:

| Policy | Definition | Sandbox Top-1 (LingxiDiag ICD-10) | Sandbox EM | Sandbox mF1 |
|---|---|---:|---:|---:|
| `current` | Current Full HiED pipeline | 0.5070 | 0.0460 | 0.1987 |
| **R3-α** | Diagnostician[0] only; comorbid emissions disabled in benchmark output | 0.5240 | 0.4690 | 0.1814 |
| **R3-β** | Diagnostician[0] + strict gate (decisive ≥ 0.85, ICD-10 dominance, criterion A met, in-confirmed) | 0.5240 | 0.2880 | 0.1863 |
| `oracle` | Gold-size-aware upper bound (NEVER candidate; reference only) | 0.5240 | 0.5090 | 0.2396 |

All numbers cited above are sandbox / non-canonical and may shift under canonical re-evaluation. They must NOT be cited in any manuscript claim location until adoption.

**Policy selection criteria (deferred to adoption phase):**

- Top-1 / Top-3 / 12-class accuracy: R3-α and R3-β tie (Diagnostician ceiling)
- EM: R3-α > R3-β > current
- mF1 cross-mode stability: R3-β > current > R3-α (per cross-dataset replay §8.6)
- F32 / F41 asymmetry: shifts mode-dependently for both R3-α and R3-β; requires explicit per-mode reporting (§7)
- F42 recall: mode-dependent under R3-α; relatively stable under R3-β

The plan does NOT pre-select between R3-α and R3-β. Selection is a §8 / §9 trigger.

---

## 5. Anti-leakage rule

**Sandbox use of gold (allowed):**

- Failure taxonomy classification of test cases (`stage_L0_audit.py` Types A-H)
- Module oracle computation (parent-collapsed Top-k under each signal source)
- Clinically-constrained rule-family discovery (R3-α, R3-β derived from ICD-10 dominance, criterion A, decisive confidence)

**Sandbox use of gold (NOT allowed as canonical claim):**

- Test-set threshold tuning post-hoc reported as generalization
- Selecting between R3-α and R3-β by viewing test-set metrics
- Tuning `decisive ≥ T` threshold by sweeping on the final test split

**Discipline that must hold for any future canonical adoption:**

```
1. Sandbox gold use is engineering diagnosis. It does not produce canonical numbers.
2. Threshold parameters (e.g., decisive threshold in R3-β) must be either
   (a) preregistered before the canonical run, or
   (b) selected on a separate dev split with frozen policy at evaluation.
3. The canonical run reports a single frozen policy. No post-hoc retuning.
4. The sandbox report's non-canonical disclaimer (§1 / §13) is preserved
   verbatim in any cross-reference.
```

This anti-leakage rule is **binding immediately**. Any future PR that proposes Gap E execution must explicitly demonstrate compliance.

---

## 6. Production-code gate

**No production code change is authorized by this plan.**

Specifically prohibited:

- Modification of `src/culturedx/modes/hied.py`
- Modification of `src/culturedx/diagnosis/calibrator.py`
- Modification of `src/culturedx/diagnosis/comorbidity.py`
- Any change to evaluation contracts in `src/culturedx/eval/lingxidiag_paper.py`
- Any change to scripts under `scripts/` other than the sandbox additions already committed at `df05637`

Production-code modification under Gap E requires:

1. Explicit PI / advisor sign-off, OR an explicit engineering trigger from the user under a separate round verdict
2. A new PR scoped solely to the production-code change (with the frozen policy named)
3. Canonical re-evaluation across all reported modes (LingxiDiag-16K × ICD-10 / DSM-5 / Both; MDD-5k × ICD-10 / DSM-5 / Both) at the canonical N values (1000 / 925)
4. Re-run of stacker training pipeline IF the comorbidity emission change affects the 12 checker met_ratio features in stacker input
5. Update of `results/dual_standard_full/.../predictions.jsonl` with the post-policy outputs
6. Recomputation of all metric files that depend on these predictions (`metric_consistency_report.json`, `results/stacker/*`, etc.)

Until all of (1)-(6) are met, no production-code commit may carry a Gap E label.

---

## 7. Manuscript-impact gate

**No manuscript change is authorized by this plan.**

Specifically prohibited:

- Modification of any §1-§7 source file (Introduction, Related Work, Methods, Experiments, Results, Discussion, Limitations)
- Modification of Abstract
- Modification of Table 2 (subgroup attribution) or Table 4 (Full HiED parity benchmark)
- Insertion of R3-α / R3-β numbers into any claim location
- Modification of `REPRODUCTION_README.md`
- Modification of `metric_consistency_report.json`
- Movement of `paper-integration-v0.1` tag from `c3b0a46`

Under conditions of adoption, the following sections MAY require revision (subject to a separate manuscript-impact PR):

- **§4 Methods**: describe the benchmark-primary output policy and its separation from the audit-only comorbidity annotation channel; describe Checker's role as audit / evidence / uncertainty rather than ranking authority
- **§5.4 Table 4**: recompute Top-1 / Top-3 / EM / 12-class Acc / macro-F1 / weighted-F1 / Overall under the new policy across all reported modes
- **§5.x F32 / F41 narrative**: revisit the asymmetry framing — R3-α changes asymmetry direction in 2 of 4 unique cells (sandbox §8.6); a frozen-policy canonical run may differ
- **§5.x F42 framing**: revisit any F42 recall claim if the canonical run reproduces the sandbox cross-mode variance
- **§7 Limitations**: add explanation that the previous final-output layer over-emitted comorbidity annotations under the single-label benchmark contract; describe the channel separation as a design correction, not a model improvement
- **`REPRODUCTION_README.md`**: update the final-output policy / evaluation-contract description and reference the new integration tag
- **Abstract**: only if the EM / 12-class number is referenced quantitatively; if Abstract avoids EM-specific claims, no change is required

The manuscript-impact PR is **separate** from the production-code PR. The dependency order is:

```
production-code PR → canonical re-evaluation → manuscript-impact PR → new tag (paper-integration-v0.2)
```

No "silent" manuscript change is permitted.

---

## 8. Decision criteria for adoption

Adoption of any policy in §4 requires the following gates to clear in order:

**Gate 8.1 — PI / advisor verdict on Gap E scope**

- Outcome A: PI approves Gap E execution → proceed to Gate 8.2
- Outcome B: PI defers Gap E → Plan v1.3 remains in plan track only; no further execution
- Outcome C: PI rejects Gap E → STOP; close Gap E; record rejection in plan file as v1.3.1 amendment

**Gate 8.2 — Policy preregistration**

Before any canonical run, the user / PI selects ONE of:

- R3-α (no comorbid)
- R3-β with explicitly frozen `decisive ≥ T` threshold (T value declared)
- A new policy not in §4, with its rule family written down

This selection is recorded in a preregistration file (`docs/paper/integration/Plan_v1.3_GapE_preregistration.md`) and committed BEFORE the canonical run.

**Gate 8.3 — Canonical re-evaluation execution**

Per §6 conditions (1)-(6). The canonical run produces:

- New `results/dual_standard_full/.../predictions.jsonl` files for all 6 mode/dataset combinations
- New `metric_consistency_report.json`
- Optional: re-trained stacker if the 12 checker met_ratio features changed semantics

**Gate 8.4 — Sanity check on cross-mode stability**

Before manuscript-impact PR, verify:

- Top-1 / Top-3 / EM directional change matches sandbox prediction (or document discrepancy)
- F32 / F41 asymmetry per-mode reported
- F42 recall per-mode reported
- 4-class / 2-class metrics from raw `DiagnosisCode` re-derived correctly

**Gate 8.5 — Manuscript-impact PR**

Per §7 conditions. Reviewed by PI. Includes:

- Diff of all manuscript sections changed
- Explicit reference to the new integration tag (e.g., `paper-integration-v0.2`)
- Limitations wording covering the design-correction framing

**Gate 8.6 — Tag bump**

After Gate 8.5 PI approval, create `paper-integration-v0.2` annotated tag at the merge commit. Do NOT move `paper-integration-v0.1`; it remains the historical reference for the pre-Gap-E artifact.

---

## 9. Trigger taxonomy for next round

The following are the canonical triggers for Gap E progression. Each is **explicit**; none is auto-fired.

| Trigger phrase | Action it authorizes | Who can issue |
|---|---|---|
| `Go surface Plan v1.3 to PI for review` | Generate a PI-facing summary of Plan v1.3, no PR, no commit beyond the summary | User |
| `Go preregister R3-α as Gap E candidate policy` | Create `Plan_v1.3_GapE_preregistration.md` selecting R3-α with frozen rules | User (after Gate 8.1 outcome A) |
| `Go preregister R3-β as Gap E candidate policy with T_decisive=0.85` | Create preregistration selecting R3-β with explicit T value | User (after Gate 8.1 outcome A) |
| `Go execute Gap E canonical re-evaluation` | Run `hied.py` modification + canonical eval on all 6 modes | User (after Gate 8.2) |
| `Go draft manuscript-impact PR for Gap E` | Draft §4 / §5.4 / §7 / README revisions; no merge | User (after Gate 8.4) |
| `Hold Gap E pending PI verdict` | No-op | User |
| `Close Gap E — PI rejected` | Append v1.3.1 amendment to this plan recording rejection | User (after Gate 8.1 outcome C) |

**Triggers NOT in this taxonomy require a new plan amendment (v1.3.1 / v1.4).**

The following are explicitly NOT triggers under Plan v1.3:

- Adopting R3-α or R3-β based on sandbox numbers
- Updating Abstract / §5.4 Table 4 from sandbox numbers
- Re-running L0 / L1 / L2 sandbox without a new question
- Starting Gap D (evidence-pipeline ablation; remains out-of-scope per Round 91 / 92)
- Starting multi-backbone (Gap C; remains out-of-scope per Plan v1.2)

---

## End of Plan v1.3

This plan was drafted at HEAD `df05637`. It will be committed as a single new file at `docs/paper/integration/Plan_v1.3_GapE.md` with no other tree changes. Adoption of any conditional content (§3, §4) is gated by §8.

To revisit or amend this plan, create `Plan_v1.3.1_GapE_amendment.md` referencing this file.
