# Logic Engine Final-Output Sandbox Report

**Status:** Sandbox / engineering diagnosis. **NOT** canonical paper metrics.
**Date:** 2026-04-29
**Source HEAD:** `692246a` (paper-integration-v0.1 frozen at `c3b0a46`)
**Author context:** CultureDx project, Round 96-101 chat-internal sandbox sweeps
**Scope:** Read-only analysis of existing prediction files; no GPU; no LLM rerun; no code modification

---

## 1. Scope and non-canonical status

This report consolidates findings from a chat-internal sandbox conducted across Rounds 96-101 to diagnose the gap between Full HiED's 12-class exact-match (EM) score (≈ 0.046-0.064 across modes) and its higher Top-1 (0.502-0.597) and Top-3 (0.780-0.853) scores. The sandbox produced **engineering-design findings**, not canonical evaluation results.

**Non-canonical disclaimer (must remain prominent in any downstream use):**

> The sandbox results in this report were obtained by replaying *existing* prediction files (`results/dual_standard_full/.../predictions.jsonl`) under alternative final-output policies.
> Threshold tuning was performed on a deterministic 50/50 dev/test split (seed=42) of the LingxiDiag-16K ICD-10 file only.
> **No new LLM inference was performed. No production code (`src/culturedx/modes/hied.py`, `src/culturedx/diagnosis/calibrator.py`, etc.) was modified.**
> These numbers must NOT be inserted into Abstract, §5.4 Table 4, REPRODUCTION_README, or any other manuscript-claim location until a frozen-policy evaluation is run under a predeclared replay protocol with PI sign-off.

**Allowed uses of this report:**
- Diagnose where the current pipeline loses signal
- Define a clinically-constrained candidate policy family
- Inform the scope of a future Plan v1.3 (Gap E) decision
- Surface manuscript-impact gates

**Not allowed:**
- Direct citation of these EM/F1 numbers as paper results
- Treating sandbox-tuned thresholds as production thresholds without re-frozen evaluation
- Claiming "we improve EM by +40pp" without running canonical pipeline change

---

## 2. L0 — Module oracles and failure taxonomy

### 2.1 Module oracle metrics (LingxiDiag-16K ICD-10, N=1000)

For each per-case signal source, compute Top-k accuracy by parent-collapse (12-class paper-parent labels). This shows the detection ceiling of each module independently.

| Source | Top-1 | Top-3 | Top-5 |
|---|---:|---:|---:|
| Final pipeline (current) | 0.5070 | 0.8010 | 0.8680 |
| **Diagnostician (DtV ranked)** | **0.5240** | **0.7990** | **0.8680** |
| Checker met_ratio top | 0.4010 | 0.7120 | 0.8410 |
| Checker met_count top | 0.3410 | 0.5920 | 0.8110 |
| Checker mean criterion confidence | 0.1300 | 0.3710 | 0.5560 |
| Logic engine confirmed (mr-sorted) | 0.4010 | 0.7100 | 0.8370 |
| **UNION ORACLE (any source contains gold)** | **0.5240** | **0.7990** | **0.8710** |

**Key observation:** UNION ORACLE Top-1 = Diagnostician Top-1 = 0.5240. Checker / logic engine signals are strictly weaker than Diagnostician at the module-oracle level and provide no additive Top-1 detection coverage.

### 2.2 Failure taxonomy (per-case classification of 493 wrong Top-1 cases)

| Type | Count | % wrong | % all | Description |
|---|---:|---:|---:|---|
| F | 137 | 27.8% | 13.7% | gold appears as comorbid; primary wrong |
| G | 131 | 26.6% | 13.1% | gold in confirmed_set; not picked as primary |
| E | 105 | 21.3% | 10.5% | all modules wrong (truly hard) |
| B | 41 | 8.3% | 4.1% | checker top-3 has gold; final top-3 lost it |
| A | 34 | 6.9% | 3.4% | checker met_ratio top-1 correct; final wrong |
| C | 22 | 4.5% | 2.2% | DtV top-1 correct; pipeline overrode |
| D | 0 | 0.0% | 0.0% | subcode-mapping issue |
| H | 0 | 0.0% | 0.0% | malformed output |
| OTHER | 23 | 4.7% | 2.3% | residual |

### 2.3 Pipeline override is net-negative on Top-1

In 77 cases the pipeline's `primary_diagnosis` differs (parent-level) from `diagnostician_ranked[0]`. Outcome breakdown:

- 26 cases: Diagnostician right, pipeline overrode to wrong → cost
- 9 cases: Diagnostician wrong, pipeline overrode to right → benefit
- 2 cases: both right
- 40 cases: both wrong

**Net effect: −17 Top-1 cases**, exactly accounting for the 0.5240 → 0.5070 gap.

---

## 3. L1 — Deterministic rule replay (LingxiDiag-16K ICD-10, N=1000)

| Rule | Top-1 | Top-3 | EM | mF1 | wF1 |
|---|---:|---:|---:|---:|---:|
| Baseline (current pipeline) | 0.5070 | 0.8000 | 0.0460 | 0.1987 | 0.4572 |
| A. Checker met_ratio top-1 | 0.4010 | 0.7990 | 0.3540 | 0.1824 | 0.3735 |
| B. Checker met_count top-1 | 0.3410 | 0.7860 | 0.3020 | 0.1692 | 0.2932 |
| **C. DtV top-1 only (no override)** | **0.5240** | 0.7990 | **0.4690** | 0.1814 | 0.4332 |
| D. Agreement-first | 0.5240 | 0.7990 | 0.4690 | 0.1814 | 0.4332 |
| E. DtV candidates + checker rerank | 0.3110 | 0.7990 | 0.2740 | 0.1652 | 0.3149 |
| F. Checker-veto-DtV (dom only) | 0.5240 | 0.7990 | 0.4690 | 0.1814 | 0.4332 |
| G. Soft-score fusion | 0.4250 | 0.8000 | 0.3790 | 0.1670 | 0.3893 |
| H. Force single (current primary) | 0.5070 | 0.8000 | 0.4520 | 0.1845 | 0.4298 |
| **K. NO override (= C)** | **0.5240** | 0.7990 | **0.4690** | 0.1814 | 0.4332 |
| L. K + strict D13 comorbid (decisive ≥ 0.85) | 0.5240 | 0.7990 | 0.2880 | 0.1863 | 0.4380 |
| M. K + calibrated comorbid (≥ 0.9 × primary) | 0.5240 | 0.7990 | 0.0550 | 0.1970 | 0.4564 |
| Oracle: knows gold size | 0.5070 | 0.8000 | 0.4620 | 0.1933 | 0.4415 |
| Oracle: oracle primary | 0.8940 | 0.8940 | 0.8080 | 0.6644 | 0.8175 |

### Key L1 conclusions

- Rule K (no override) Pareto-dominates baseline (Top-1 +1.7pp, EM +42.3pp, mF1 −1.7pp).
- Rule E (checker-rerank-DtV) catastrophic: Top-1 drops from 0.5070 to 0.3110.
- Oracle primary ceiling = 0.894 (Top-1 detection signal exists across multiple sources, but ranking cannot be improved by deterministic rules).

---

## 4. L2 — Threshold sweeps + L2-redesign (Round 99 framework)

### 4.1 L2 (Round 96 §10.L2) summary

Threshold sweeps on dev split (seed=42 50/50, dev N=500) for K + comorbid threshold T or relative R. **Top-1 frozen at 0.512 across all sweeps** because primary selection is held at Diagnostician[0]. Comorbid threshold tuning produces a Pareto trade-off between EM and mF1 but does not move Top-1 / Top-3 / MRR.

### 4.2 L2-redesign (Round 99) — primary-locked checker-audited

#### L2-R1: Top-1 locked, checker reranks rank 2-5 (TEST split, N=500)

| Strategy | Top-1 | Top-3 | Top-5 | MRR |
|---|---:|---:|---:|---:|
| **identity (= original Diagnostician)** | **0.5120** | **0.7800** | **0.8500** | **0.6444** |
| met_ratio rerank | 0.5120 | 0.7200 | 0.8500 | 0.6267 |
| decisive rerank | 0.5120 | 0.6540 | 0.8500 | 0.6163 |
| mean_evid_conf rerank | 0.5120 | 0.6560 | 0.8500 | 0.6159 |
| composite (mr+dec+conf) | 0.5120 | 0.6940 | 0.8500 | 0.6248 |
| confirmed_priority | 0.5120 | 0.7240 | 0.8500 | 0.6269 |
| confirmed_priority + crit_A | 0.5120 | 0.7060 | 0.8500 | 0.6256 |

**Verdict: Diagnostician's original rank 2-5 order is optimal.** All checker-aware reranking strategies degrade Top-3 and MRR. Top-5 is invariant (set membership unchanged by reordering within top-5).

#### L2-R2: Conservative veto sweep

30 parameter combinations (margin_p × T_alt × dom_only) on dev split. Result: most settings are no-ops; loose settings (margin_p=1.1 with permissive thresholds) drop Top-1 from 0.512 to 0.474. **No setting where conservative veto helps.**

#### L2-R3: Comorbidity annotation gate (TEST split, N=500)

| Gate | Top-1 | Top-3 | EM | MRR | mF1 | wF1 | pred_size_dist |
|---|---:|---:|---:|---:|---:|---:|---|
| Current pipeline | 0.5120 | 0.7800 | 0.0500 | 0.6444 | **0.1715** | **0.4501** | {1: 36, 2: 464} |
| **R3-α: no comorbid** | 0.5120 | 0.7800 | **0.4580** | 0.6444 | 0.1542 | 0.4192 | {1: 500} |
| R3-β: T_dec ≥ 0.70 | 0.5120 | 0.7800 | 0.1060 | 0.6444 | 0.1677 | 0.4419 | {1: 123, 2: 377} |
| R3-β: T_dec ≥ 0.85 | 0.5120 | 0.7800 | 0.2680 | 0.6444 | 0.1548 | 0.4187 | {1: 286, 2: 214} |
| R3-β: T_dec ≥ 0.90 | 0.5120 | 0.7800 | 0.4000 | 0.6444 | 0.1584 | 0.4202 | {1: 415, 2: 85} |
| Oracle (gold-size aware) | 0.5120 | 0.7800 | 0.4720 | 0.6444 | 0.1690 | — | {1: 464, 2: 36} |

---

## 5. L3 — Learnable ranker (Round 96 §9.1)

Three model classes (LogReg, LightGBM LambdaRank, LightGBM binary classifier) trained on per-(case, candidate) feature vectors with `is_gold_parent` label. Dev split N=500 (X.shape=3870×27), TEST split N=500 (X.shape=3869×27).

| Model | Top-1 | Top-3 | EM (force_single) | mF1 | wF1 |
|---|---:|---:|---:|---:|---:|
| Current pipeline | 0.5020 | 0.7820 | 0.0480 | 0.1741 | 0.4498 |
| Rule K (force single) | 0.5120 | 0.7800 | 0.4580 | 0.1542 | 0.4192 |
| LR Ranker | 0.5140 | 0.7680 | 0.4580 | 0.0982 | 0.4423 |
| LGBM LambdaRank | 0.4560 | 0.7740 | 0.4000 | **0.2020** | 0.4261 |
| LGBM Binary | 0.4880 | 0.7740 | 0.4320 | 0.1234 | 0.4385 |

**Verdict:** LR ranker improves Top-1 by +0.2pp over Rule K (statistically insignificant on N=500). LGBM LambdaRank trades Top-1 for mF1 via class-prior bias. **No learnable model exceeds Diagnostician ceiling 0.524.**

---

## 6. Stop-decisions (Round 100)

Based on L0/L1/L2/L3, the following design lines are **STOP**ped:

| Hypothesis | L2 evidence | Status |
|---|---|:---:|
| Checker reranks rank 2-5 | All strategies degrade Top-3/MRR | ⛔ STOP |
| Checker primary veto | No useful firing condition | ⛔ STOP |
| Checker free primary override | Net −17 Top-1 cases | ⛔ STOP |
| DtV-rerank-by-checker | Top-1 collapse 0.507 → 0.311 | ⛔ STOP |

These should not be re-tested with deterministic rules unless a fundamentally new contradiction-detection model becomes available.

---

## 7. Recommended design lock (Round 100 §10)

```
Policy: Diagnostician-primary, checker-audited output

1. Benchmark primary prediction = Diagnostician rank-1 (locked, no override)
2. Top-k differential = Diagnostician original ranking (no checker rerank)
3. Checker = audit trace + per-criterion evidence + uncertainty signal
            (NOT a ranking authority)
4. Comorbidity = SEPARATE annotation field, NOT in benchmark prediction set
5. Benchmark EM uses primary-only single-label prediction
6. Audit output preserves checker traces and conservative annotations
```

This design satisfies:
- Uses Diagnostician's strongest signal as primary
- Retains Checker for audit / interpretability / future triage
- Decouples benchmark prediction from clinical-audit annotations
- Conforms to single-label evaluation contract

---

## 8. Cross-dataset replay protocol and results

### 8.1 Protocol

- **Datasets × Modes:** LingxiDiag-16K and MDD-5k × {ICD-10, DSM-5, Both} = 6 prediction files
- **Policies tested:**
  - `current` — current pipeline (`primary_diagnosis` + `comorbid_diagnoses`)
  - `R3-α` — Diagnostician[0] only (no comorbid)
  - `R3-β` — Diagnostician[0] + strict gate (decisive ≥ 0.85, dominance, criterion A, in-confirmed)
  - `oracle` — gold-size-aware upper bound
- **Metrics:** Top-1, Top-3, EM, MRR, mF1, wF1, F32→F41, F41→F32, F42 recall, multilabel emit rate
- **Source:** `results/sandbox/cross_dataset_replay_20260429_121100.json`

### 8.2 Both-mode primary-output duplication note

For both LingxiDiag-16K and MDD-5k, `mode_both` and `mode_icd10` are **bit-identical** for the prediction fields used by this replay (`primary_diagnosis`, `comorbid_diagnoses`, and `diagnostician_ranked`; 1000/1000 and 925/925 cases respectively). The only observed difference at the prediction-record level is the *ordering* of `raw_checker_outputs` list (same set, different order).

This is consistent with the locked Both-mode pass-through framing at the primary-output metric level (Both mode preserves ICD-10 primary output with DSM-5 sidecar audit evidence; Both mode is not an ensemble). Therefore, on the prediction fields evaluated here, `mode_both` cells in the tables below match `mode_icd10` cells by design, and the cross-mode comparison effectively reduces to "DSM-5 vs ICD-10" for the metric set computed in this replay.

If future work needs to evaluate DSM-5 sidecar audit evidence under Both mode, sidecar-specific trace fields should be audited separately. The replay did not inspect sidecar-only audit payload differences; therefore this finding should not be interpreted as absence of DSM-5 sidecar evidence unless sidecar fields are separately audited.

This duplication does not invalidate the design conclusions in this report (the design lock concerns final-output behavior, not standard-mode disambiguation), but it limits the *primary-output-metric*-based cross-mode generalization claim to the four unique cells (LingxiDiag × {ICD-10, DSM-5}, MDD-5k × {ICD-10, DSM-5}).

### 8.3 Per-mode results

#### LingxiDiag-16K × ICD-10 (N=1000)

Gold size dist: `{1: 914, 2: 81, 3: 5}`

| Policy | Top-1 | Top-3 | EM | MRR | mF1 | wF1 | F32→F41 | F41→F32 | F42 recall | multi_emit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| current | 0.5070 | 0.8000 | 0.0460 | 0.6569 | 0.1987 | 0.4572 | 36 | 188 | 0.4167 | 0.9250 |
| R3-α | 0.5240 | 0.7990 | 0.4690 | 0.6569 | 0.1814 | 0.4332 | 29 | 204 | 0.3611 | 0.0000 |
| R3-β | 0.5240 | 0.7990 | 0.2880 | 0.6569 | 0.1863 | 0.4380 | 29 | 204 | 0.3611 | 0.4170 |
| oracle | 0.5240 | 0.7990 | 0.5090 | 0.6569 | 0.2396 | 0.4937 | 29 | 204 | 0.3611 | 0.0860 |

#### LingxiDiag-16K × DSM-5 (N=1000)

Gold size dist: `{1: 914, 2: 81, 3: 5}`

| Policy | Top-1 | Top-3 | EM | MRR | mF1 | wF1 | F32→F41 | F41→F32 | F42 recall | multi_emit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| current | 0.4710 | 0.8040 | 0.0290 | 0.6638 | 0.1882 | 0.4210 | 26 | 218 | 0.0833 | 0.9190 |
| R3-α | 0.5300 | 0.8050 | 0.4720 | 0.6638 | 0.1986 | 0.4426 | 38 | 195 | 0.3889 | 0.0000 |
| R3-β | 0.5300 | 0.8050 | 0.3990 | 0.6638 | 0.2124 | 0.4609 | 38 | 195 | 0.3889 | 0.2300 |
| oracle | 0.5300 | 0.8050 | 0.5140 | 0.6638 | 0.2665 | 0.5032 | 38 | 195 | 0.3889 | 0.0830 |

#### LingxiDiag-16K × Both (N=1000) [duplicate of ICD-10 — see §8.2]

| Policy | Top-1 | Top-3 | EM | MRR | mF1 | wF1 | F32→F41 | F41→F32 | F42 recall | multi_emit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| current | 0.5070 | 0.8000 | 0.0460 | 0.6569 | 0.1987 | 0.4572 | 36 | 188 | 0.4167 | 0.9250 |
| R3-α | 0.5240 | 0.7990 | 0.4690 | 0.6569 | 0.1814 | 0.4332 | 29 | 204 | 0.3611 | 0.0000 |
| R3-β | 0.5240 | 0.7990 | 0.2880 | 0.6569 | 0.1863 | 0.4380 | 29 | 204 | 0.3611 | 0.4170 |
| oracle | 0.5240 | 0.7990 | 0.5090 | 0.6569 | 0.2396 | 0.4937 | 29 | 204 | 0.3611 | 0.0860 |

#### MDD-5k × ICD-10 (N=925)

Gold size dist: `{1: 874, 2: 47, 3: 4}`

| Policy | Top-1 | Top-3 | EM | MRR | mF1 | wF1 | F32→F41 | F41→F32 | F42 recall | multi_emit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| current | 0.5968 | 0.8530 | 0.0638 | 0.7276 | 0.1974 | 0.5136 | 38 | 151 | 0.3810 | 0.9027 |
| R3-α | 0.6043 | 0.8519 | 0.5632 | 0.7276 | 0.1900 | 0.5250 | 35 | 158 | 0.2857 | 0.0000 |
| R3-β | 0.6043 | 0.8519 | 0.2411 | 0.7276 | 0.2229 | 0.5337 | 35 | 158 | 0.4762 | 0.5914 |
| oracle | 0.6043 | 0.8519 | 0.5957 | 0.7276 | 0.2539 | 0.5676 | 35 | 158 | 0.3333 | 0.0541 |

#### MDD-5k × DSM-5 (N=925)

Gold size dist: `{1: 874, 2: 47, 3: 4}`

| Policy | Top-1 | Top-3 | EM | MRR | mF1 | wF1 | F32→F41 | F41→F32 | F42 recall | multi_emit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| current | 0.5805 | 0.8422 | 0.0357 | 0.7126 | 0.2303 | 0.5264 | 25 | 181 | 0.1429 | 0.9351 |
| R3-α | 0.5881 | 0.8411 | 0.5470 | 0.7126 | 0.1980 | 0.5015 | 31 | 177 | 0.2857 | 0.0000 |
| R3-β | 0.5881 | 0.8411 | 0.1373 | 0.7126 | 0.2499 | 0.5349 | 31 | 177 | 0.2857 | 0.7546 |
| oracle | 0.5881 | 0.8411 | 0.5849 | 0.7126 | 0.2891 | 0.5502 | 31 | 177 | 0.4286 | 0.0551 |

#### MDD-5k × Both (N=925) [duplicate of ICD-10 — see §8.2]

| Policy | Top-1 | Top-3 | EM | MRR | mF1 | wF1 | F32→F41 | F41→F32 | F42 recall | multi_emit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| current | 0.5968 | 0.8530 | 0.0638 | 0.7276 | 0.1974 | 0.5136 | 38 | 151 | 0.3810 | 0.9027 |
| R3-α | 0.6043 | 0.8519 | 0.5632 | 0.7276 | 0.1900 | 0.5250 | 35 | 158 | 0.2857 | 0.0000 |
| R3-β | 0.6043 | 0.8519 | 0.2411 | 0.7276 | 0.2229 | 0.5337 | 35 | 158 | 0.4762 | 0.5914 |
| oracle | 0.6043 | 0.8519 | 0.5957 | 0.7276 | 0.2539 | 0.5676 | 35 | 158 | 0.3333 | 0.0541 |

### 8.4 Δ summary: R3-α vs current per dataset/mode

| Dataset | Mode | N | ΔTop-1 | ΔTop-3 | ΔEM | ΔmF1 | ΔwF1 | ΔF32→F41 | ΔF41→F32 | ΔF42_rec |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LingxiDiag-16K | ICD-10 | 1000 | +0.0170 | −0.0010 | +0.4230 | −0.0174 | −0.0241 | −7 | +16 | −0.0556 |
| LingxiDiag-16K | DSM-5 | 1000 | +0.0590 | +0.0010 | +0.4430 | +0.0104 | +0.0215 | +12 | −23 | +0.3056 |
| LingxiDiag-16K | Both | 1000 | +0.0170 | −0.0010 | +0.4230 | −0.0174 | −0.0241 | −7 | +16 | −0.0556 |
| MDD-5k | ICD-10 | 925 | +0.0076 | −0.0011 | +0.4995 | −0.0074 | +0.0114 | −3 | +7 | −0.0952 |
| MDD-5k | DSM-5 | 925 | +0.0076 | −0.0011 | +0.5114 | −0.0324 | −0.0249 | +6 | −4 | +0.1429 |
| MDD-5k | Both | 925 | +0.0076 | −0.0011 | +0.4995 | −0.0074 | +0.0114 | −3 | +7 | −0.0952 |

### 8.5 Δ summary: R3-β vs current per dataset/mode

| Dataset | Mode | N | ΔTop-1 | ΔTop-3 | ΔEM | ΔmF1 | ΔwF1 | ΔF32→F41 | ΔF41→F32 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LingxiDiag-16K | ICD-10 | 1000 | +0.0170 | −0.0010 | +0.2420 | −0.0124 | −0.0192 | −7 | +16 |
| LingxiDiag-16K | DSM-5 | 1000 | +0.0590 | +0.0010 | +0.3700 | +0.0242 | +0.0399 | +12 | −23 |
| LingxiDiag-16K | Both | 1000 | +0.0170 | −0.0010 | +0.2420 | −0.0124 | −0.0192 | −7 | +16 |
| MDD-5k | ICD-10 | 925 | +0.0076 | −0.0011 | +0.1773 | +0.0255 | +0.0201 | −3 | +7 |
| MDD-5k | DSM-5 | 925 | +0.0076 | −0.0011 | +0.1016 | +0.0195 | +0.0086 | +6 | −4 |
| MDD-5k | Both | 925 | +0.0076 | −0.0011 | +0.1773 | +0.0255 | +0.0201 | −3 | +7 |

### 8.6 Cross-mode observations (excluding `Both` duplicates)

Effective unique cells: 4 (LingxiDiag ICD-10/DSM-5 + MDD-5k ICD-10/DSM-5).

**Top-1 (R3-α)**:
- All 4 modes: positive Δ (+0.76pp to +5.90pp)
- Largest gain: LingxiDiag DSM-5 (+5.90pp)
- Smallest gain: MDD-5k (+0.76pp on both standards)
- **Sign: consistently positive across all modes**

**EM (R3-α)**:
- All 4 modes: massively positive (+42-51pp)
- MDD-5k modes have larger EM gains than LingxiDiag (because MDD-5k has even higher current multilabel emission rate, 90.3-93.5%, that gets fully suppressed)
- **Sign: consistently positive across all modes**

**mF1 (R3-α)**:
- LingxiDiag ICD-10: −1.74pp (loss)
- LingxiDiag DSM-5: +1.04pp (gain)
- MDD-5k ICD-10: −0.74pp (loss)
- MDD-5k DSM-5: −3.24pp (largest loss)
- **Sign: inconsistent. R3-α hurts mF1 in 3 of 4 modes.**

**mF1 (R3-β)**:
- LingxiDiag ICD-10: −1.24pp
- LingxiDiag DSM-5: +2.42pp (largest gain)
- MDD-5k ICD-10: +2.55pp
- MDD-5k DSM-5: +1.95pp
- **Sign: 3 of 4 modes positive. R3-β preserves or improves mF1 in 3 of 4 modes.**

**F32/F41 asymmetry (both R3-α and R3-β)**:
- LingxiDiag ICD-10: F41→F32 INCREASES from 188 → 204 (+16, asymmetry worsens)
- LingxiDiag DSM-5: F41→F32 DECREASES from 218 → 195 (−23, asymmetry improves)
- MDD-5k ICD-10: F41→F32 INCREASES from 151 → 158 (+7)
- MDD-5k DSM-5: F41→F32 DECREASES from 181 → 177 (−4)
- **Pattern: ICD-10 modes worsen asymmetry; DSM-5 modes improve asymmetry. This is significant for paper §F32/F41 narrative.**

**F42 recall**:
- Highly variable across modes, both gains and losses
- LingxiDiag DSM-5 gains +30.6pp; ICD-10 modes both lose F42 recall
- Implications for any §F42 limitation framing

### 8.7 Cross-dataset stability verdict

| Question | Answer |
|---|---|
| Is Top-1 improvement stable across modes? | Yes — all 4 unique modes gain Top-1 |
| Is EM improvement stable across modes? | Yes — all 4 unique modes gain EM (>+40pp) |
| Is mF1 stable under R3-α? | **No** — 3 of 4 modes lose mF1 |
| Is mF1 stable under R3-β? | Mostly yes — 3 of 4 modes preserve or improve mF1 |
| Is F32/F41 asymmetry stable? | **No** — ICD-10 worsens, DSM-5 improves |
| Is F42 recall stable? | **No** — varies by mode |
| Is `mode_both` an independent test? | No — bit-identical to `mode_icd10` on the primary-output fields used here, consistent with Both-mode pass-through framing (see §8.2) |

**Bottom line:** R3-α gives the largest EM gains but trades mF1 in most modes. **R3-β is more stable across the cross-mode metric set** and is therefore the more defensible policy for paper canonical adoption.

---

## 9. Leakage / test-set caution

This sandbox used gold labels in the L0 failure taxonomy and L2 oracle analysis. This is **legitimate engineering diagnosis**, not test-set tuning, provided that:

1. Final-claim numbers are produced by a frozen policy in a single evaluation pass.
2. Threshold choices are dev-only and use a predeclared composite criterion.
3. The policy family (R3-α / R3-β) is motivated by clinical and evaluation-contract reasoning, not by maximizing test metrics.

The following uses of this report are **NOT** allowed:

- Reporting any sandbox metric as a paper-level result without re-frozen evaluation
- Tuning further thresholds on the held-out test split
- Selecting between R3-α and R3-β post-hoc by viewing test-set metrics

The following uses ARE allowed:

- Using R3-α or R3-β as a preregistered candidate policy for a future canonical run
- Using the failure-taxonomy and module-oracle counts as descriptive findings
- Citing the design lock (Section 7) as a methodological commitment

---

## 10. Manuscript-impact gate

**This report does not modify the manuscript.** Adoption of R3-α or R3-β as canonical policy would trigger the following review checkpoints, all gated on PI sign-off and a separate manuscript-impact PR:

- **§4 Methods:** describe benchmark-primary output policy vs audit-only comorbidity annotations
- **§5.4 Table 4:** recompute exact match / macro-F1 / weighted-F1 / Overall / 12-class Acc under the new policy across all reported modes
- **§5.x F32/F41 narrative:** revisit asymmetry framing — R3-α changes asymmetry direction in 2 of 4 unique modes
- **§5.x F42 framing:** F42 recall changes are mode-dependent
- **§7 Limitations:** add explanation that the previous final-output layer over-emitted comorbidity annotations under the single-label benchmark contract
- **REPRODUCTION_README:** update final-output policy / evaluation-contract description
- **Abstract:** check that any quantitative claim referencing EM is consistent with the new policy
- **paper-integration tag:** require new tag (e.g., `paper-integration-v0.2`) — the current `paper-integration-v0.1@c3b0a46` should remain frozen for reference

**No part of this list is executed by this report.** Each item is a precondition for a future Plan v1.3 (Gap E) decision and an associated manuscript-impact review.

---

## 11. Recommendations

### 11.1 Strict-priority order (do not skip)

1. **Surface this report to PI** for sign-off on whether to enter Plan v1.3 (Gap E).
2. **Note Both-mode primary-output duplication** (Section 8.2): the `mode_both` and `mode_icd10` prediction records used here are bit-identical, consistent with the locked Both-mode pass-through framing. If a future evaluation needs DSM-5 sidecar evidence under Both mode, audit the sidecar trace fields separately — this is not a precondition for adopting R3-α / R3-β.
3. **If PI approves Plan v1.3:** preregister R3-α vs R3-β decision, freeze policy, run full canonical pipeline (with hied.py modification + N=1000 LingxiDiag re-evaluation + N=925 MDD-5k re-evaluation + re-stacker training if stacker features depend on comorbid emission).
4. **Manuscript-impact PR:** only after frozen-policy canonical results are in hand.

### 11.2 Policy preference (subject to PI verdict)

Based on cross-mode stability (Section 8.7):

- **If paper priority is EM + Top-1:** R3-α (no comorbid)
- **If paper priority is mF1 stability + reviewer defensibility:** R3-β (T_dec ≥ 0.85)
- **If paper priority is F32/F41 asymmetry preservation:** neither — both shift asymmetry in mode-dependent ways. May require explicit per-mode reporting rather than a single policy choice.

### 11.3 What this report does NOT recommend

- ⛔ Do NOT rerun checker reranking variants
- ⛔ Do NOT rerun primary-veto variants  
- ⛔ Do NOT add new learnable rankers without first re-evaluating with new (post-policy-fix) prediction files
- ⛔ Do NOT silently merge any change to `hied.py` or `calibrator.py`
- ⛔ Do NOT cite sandbox numbers in paper body or Abstract

---

## 12. Artifacts

This report references the following files in the working tree (not committed by this report):

- `results/sandbox/cross_dataset_replay_20260429_121100.json` — raw cross-dataset replay data
- `results/sandbox/cross_dataset_replay_20260429_121100.md` — markdown summary of cross-dataset replay
- `scripts/sandbox/stage_L0_audit.py` — L0 module oracles + failure taxonomy script
- `scripts/sandbox/stage_L0_deepdive.py` — Type F + G deep dive
- `scripts/sandbox/stage_L1_replay.py` — L1 deterministic rule replay
- `scripts/sandbox/stage_L2_sweep.py` — L2 (Round 96) threshold sweeps
- `scripts/sandbox/stage_L2_redesign.py` — L2-R1 + L2-R2 (Round 99 redesign)
- `scripts/sandbox/stage_L2_R3R4.py` — L2-R3 + L2-R4
- `scripts/sandbox/stage_L3_ranker.py` — L3 learnable ranker
- `scripts/sandbox/checker_value_audit.py` — Round 100 supplementary 5-dimension audit
- `scripts/sandbox/cross_dataset_replay.py` — Round 101 cross-dataset replay

These will be packaged in the round 101 deliverable tarball under `/mnt/user-data/outputs/`.

---

## 13. Sign-off

**This report is a sandbox / engineering diagnosis only.** It does not modify the canonical pipeline, does not update the manuscript, and does not move the `paper-integration-v0.1` tag. Adoption of any recommendation requires PI sign-off and a separate manuscript-impact review.

End of report.
