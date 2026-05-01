# Round 152 — 1B-α Conservative-Veto Targeted Validation (6 modes)

**Date:** 2026-05-01 11:51:02
**Branch:** feature/gap-e-beta2-implementation
**Status:** Historical feature-branch sandbox audit.
CPU-only. No production code change.
Source family is dual_standard_full / BETA-2a-era predictions.
This artifact is NOT BETA-2b-aligned validation and NOT manuscript-canonical.

**Provenance note:** This report evaluates 1B-α against the dual_standard_full source family.
A later provenance-alignment audit is required before using 1B-α as BETA-2c evidence.

## TL;DR

**Verdict:** **GREEN**

- Net gain (delta_correct − delta_wrong) per mode and across 6 modes
- F32/F41 asymmetry direction preserved
- F42 recall preserved
- Both-mode pass-through preserved

Full numbers below.

---

## 1. Predictions verified

| Mode | path | N |
|---|---|---:|
| lingxi_icd10 | `results/dual_standard_full/lingxidiag16k/mode_icd10/pilot_icd10/predictions.jsonl` | 1000 |
| lingxi_dsm5 | `results/dual_standard_full/lingxidiag16k/mode_dsm5/pilot_dsm5/predictions.jsonl` | 1000 |
| lingxi_both | `results/dual_standard_full/lingxidiag16k/mode_both/pilot_both/predictions.jsonl` | 1000 |
| mdd_icd10 | `results/dual_standard_full/mdd5k/mode_icd10/pilot_icd10/predictions.jsonl` | 925 |
| mdd_dsm5 | `results/dual_standard_full/mdd5k/mode_dsm5/pilot_dsm5/predictions.jsonl` | 925 |
| mdd_both | `results/dual_standard_full/mdd5k/mode_both/pilot_both/predictions.jsonl` | 925 |

---

## 2. 1B-α policy implementation

```python
def apply_1b_alpha(record):
    ranked    = decision_trace.diagnostician_ranked
    confirmed = set(base_code(c) for c in decision_trace.logic_engine_confirmed_codes)
    if base_code(ranked[0]) in confirmed:
        return ranked[0]                 # rank-0 confirmed -> keep
    if len(ranked) >= 2 and base_code(ranked[1]) in confirmed:
        return ranked[1]                 # CONSERVATIVE VETO: switch to rank-1 if confirmed
    return ranked[0]                     # neither confirmed -> keep rank-0
# comorbid_diagnoses = []              (same as BETA-2b)
```

---

## 3. Per-mode metric battery

| Mode | Policy | Top-1 | Top-3 | EM | macro-F1 | weighted-F1 | Overall | 2-class | 4-class |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| lingxi_icd10 | BETA-2b | 0.501 | 0.793 | 0.452 | 0.203 | 0.450 | 0.384 | 0.606 | 0.574 |
| lingxi_icd10 | **1B-α** | 0.506 | 0.793 | 0.458 | 0.197 | 0.452 | 0.385 | 0.610 | 0.579 |
| lingxi_icd10 | Δ | +0.005 | — | +0.006 | -0.006 | +0.002 | +0.000 | — | — |
| lingxi_dsm5 | BETA-2b | 0.467 | 0.799 | 0.419 | 0.181 | 0.415 | 0.354 | 0.570 | 0.547 |
| lingxi_dsm5 | **1B-α** | 0.519 | 0.799 | 0.467 | 0.185 | 0.459 | 0.388 | 0.618 | 0.592 |
| lingxi_dsm5 | Δ | +0.052 | — | +0.048 | +0.004 | +0.044 | +0.033 | — | — |
| lingxi_both | BETA-2b | 0.501 | 0.793 | 0.452 | 0.203 | 0.450 | 0.384 | 0.606 | 0.574 |
| lingxi_both | **1B-α** | 0.506 | 0.793 | 0.458 | 0.197 | 0.452 | 0.385 | 0.610 | 0.579 |
| lingxi_both | Δ | +0.005 | — | +0.006 | -0.006 | +0.002 | +0.000 | — | — |
| mdd_icd10 | BETA-2b | 0.585 | 0.842 | 0.542 | 0.087 | 0.531 | 0.401 | 0.681 | 0.642 |
| mdd_icd10 | **1B-α** | 0.590 | 0.842 | 0.547 | 0.089 | 0.532 | 0.404 | 0.688 | 0.655 |
| mdd_icd10 | Δ | +0.005 | — | +0.005 | +0.002 | +0.001 | +0.003 | — | — |
| mdd_dsm5 | BETA-2b | 0.571 | 0.832 | 0.528 | 0.087 | 0.503 | 0.387 | 0.681 | 0.654 |
| mdd_dsm5 | **1B-α** | 0.574 | 0.832 | 0.530 | 0.081 | 0.501 | 0.385 | 0.674 | 0.648 |
| mdd_dsm5 | Δ | +0.003 | — | +0.002 | -0.006 | -0.002 | -0.001 | — | — |
| mdd_both | BETA-2b | 0.585 | 0.842 | 0.542 | 0.087 | 0.531 | 0.401 | 0.681 | 0.642 |
| mdd_both | **1B-α** | 0.590 | 0.842 | 0.547 | 0.089 | 0.532 | 0.404 | 0.688 | 0.655 |
| mdd_both | Δ | +0.005 | — | +0.005 | +0.002 | +0.001 | +0.003 | — | — |

---

## 4. F32/F41 cascade and asymmetry

| Mode | Policy | F32→F41 | F41→F32 | asymmetry (F41→F32 / F32→F41) |
|---|---|---:|---:|---:|
| lingxi_icd10 | BETA-2b | 36 | 188 | 5.22 |
| lingxi_icd10 | **1B-α** | 38 | 187 | 4.92 |
| lingxi_dsm5 | BETA-2b | 26 | 218 | 8.38 |
| lingxi_dsm5 | **1B-α** | 43 | 191 | 4.44 |
| lingxi_both | BETA-2b | 36 | 188 | 5.22 |
| lingxi_both | **1B-α** | 38 | 187 | 4.92 |
| mdd_icd10 | BETA-2b | 38 | 151 | 3.97 |
| mdd_icd10 | **1B-α** | 41 | 150 | 3.66 |
| mdd_dsm5 | BETA-2b | 25 | 181 | 7.24 |
| mdd_dsm5 | **1B-α** | 32 | 179 | 5.59 |
| mdd_both | BETA-2b | 38 | 151 | 3.97 |
| mdd_both | **1B-α** | 41 | 150 | 3.66 |

---

## 5. F42 recall

| Mode | Policy | F42 gold | F42 pred-correct | F42 recall |
|---|---|---:|---:|---:|
| lingxi_icd10 | BETA-2b | 36 | 13 | 0.361 |
| lingxi_icd10 | **1B-α** | 36 | 13 | 0.361 |
| lingxi_dsm5 | BETA-2b | 36 | 3 | 0.083 |
| lingxi_dsm5 | **1B-α** | 36 | 5 | 0.139 |
| lingxi_both | BETA-2b | 36 | 13 | 0.361 |
| lingxi_both | **1B-α** | 36 | 13 | 0.361 |
| mdd_icd10 | BETA-2b | 21 | 6 | 0.286 |
| mdd_icd10 | **1B-α** | 21 | 6 | 0.286 |
| mdd_dsm5 | BETA-2b | 21 | 3 | 0.143 |
| mdd_dsm5 | **1B-α** | 21 | 3 | 0.143 |
| mdd_both | BETA-2b | 21 | 6 | 0.286 |
| mdd_both | **1B-α** | 21 | 6 | 0.286 |

---

## 6. Both-mode pass-through (vs ICD-10)

| Dataset | Policy | n (cases common) | match | match-rate |
|---|---|---:|---:|---:|
| LingxiDiag | BETA-2b | 1000 | 1000 | 1.000 |
| LingxiDiag | **1B-α** | 1000 | 1000 | 1.000 |
| MDD-5k | BETA-2b | 925 | 925 | 1.000 |
| MDD-5k | **1B-α** | 925 | 925 | 1.000 |

---

## 7. Primary change rate

| Mode | n | changed | rate |
|---|---:|---:|---:|
| lingxi_icd10 | 1000 | 23 | 2.3% |
| lingxi_dsm5 | 1000 | 136 | 13.6% |
| lingxi_both | 1000 | 23 | 2.3% |
| mdd_icd10 | 925 | 24 | 2.6% |
| mdd_dsm5 | 925 | 46 | 5.0% |
| mdd_both | 925 | 24 | 2.6% |

---

## 8. Delta analysis (per mode)

| Mode | delta_correct (rescued) | delta_wrong (harmed) | net_gain |
|---|---:|---:|---:|
| lingxi_icd10 | 7 | 2 | +5 |
| lingxi_dsm5 | 68 | 16 | +52 |
| lingxi_both | 7 | 2 | +5 |
| mdd_icd10 | 8 | 3 | +5 |
| mdd_dsm5 | 11 | 8 | +3 |
| mdd_both | 8 | 3 | +5 |

### lingxi_icd10 — sample rescued (≤5)

| case_id | baseline → new | gold |
|---|---|---|
| 354496307 | F39 → F41 | F41 |
| 393759538 | F32 → F41 | F41 |
| 356164633 | F51 → F41 | F41 |
| 374660127 | F39 → F41 | F41 |
| 383528399 | F51 → F41 | F41 |

### lingxi_icd10 — sample harmed (≤5)

| case_id | baseline → new | gold |
|---|---|---|
| 310501159 | F32 → F41 | F32 |
| 329091450 | F51 → F41 | F51 |

### lingxi_dsm5 — sample rescued (≤5)

| case_id | baseline → new | gold |
|---|---|---|
| 300493869 | F45 → F41 | F41 |
| 324224056 | F32 → F41 | F41 |
| 380913193 | F39 → F41 | F41 |
| 393761475 | F39 → F41 | F41 |
| 354219828 | F32 → F41 | F41 |

### lingxi_dsm5 — sample harmed (≤5)

| case_id | baseline → new | gold |
|---|---|---|
| 378576998 | F32 → F41 | F32 |
| 395495143 | F51 → F41 | F51 |
| 309780121 | F32 → F41 | F32 |
| 336404489 | F32 → F41 | F32 |
| 379645537 | F32 → F41 | F32 |

### lingxi_both — sample rescued (≤5)

| case_id | baseline → new | gold |
|---|---|---|
| 354496307 | F39 → F41 | F41 |
| 393759538 | F32 → F41 | F41 |
| 356164633 | F51 → F41 | F41 |
| 374660127 | F39 → F41 | F41 |
| 383528399 | F51 → F41 | F41 |

### lingxi_both — sample harmed (≤5)

| case_id | baseline → new | gold |
|---|---|---|
| 310501159 | F32 → F41 | F32 |
| 329091450 | F51 → F41 | F51 |

### mdd_icd10 — sample rescued (≤5)

| case_id | baseline → new | gold |
|---|---|---|
| patient_176 | F39 → F41 | F41 |
| patient_474 | F39 → F41 | F41 |
| patient_56 | F98 → F31 | F31 |
| patient_567 | F39 → F41 | F41 |
| patient_587 | F39 → F41 | F41 |

### mdd_icd10 — sample harmed (≤5)

| case_id | baseline → new | gold |
|---|---|---|
| patient_218 | F32 → F41 | F32 |
| patient_258 | F32 → F41 | F32 |
| patient_467 | F31 → F32 | F31 |

### mdd_dsm5 — sample rescued (≤5)

| case_id | baseline → new | gold |
|---|---|---|
| patient_191 | F32 → F41 | F41 |
| patient_211 | F41 → F31 | F31 |
| patient_22 | F39 → F41 | F41 |
| patient_237 | F39 → F41 | F41 |
| patient_263 | F39 → F41 | F41 |

### mdd_dsm5 — sample harmed (≤5)

| case_id | baseline → new | gold |
|---|---|---|
| patient_221 | F32 → F41 | F32 |
| patient_295 | F51 → F41 | F51 |
| patient_324 | F41 → F32 | F41 |
| patient_407 | F32 → F41 | F32 |
| patient_408 | F32 → F41 | F32 |

### mdd_both — sample rescued (≤5)

| case_id | baseline → new | gold |
|---|---|---|
| patient_176 | F39 → F41 | F41 |
| patient_474 | F39 → F41 | F41 |
| patient_56 | F98 → F31 | F31 |
| patient_567 | F39 → F41 | F41 |
| patient_587 | F39 → F41 | F41 |

### mdd_both — sample harmed (≤5)

| case_id | baseline → new | gold |
|---|---|---|
| patient_218 | F32 → F41 | F32 |
| patient_258 | F32 → F41 | F32 |
| patient_467 | F31 → F32 | F31 |

---

## 9. Clinical-defensibility check (narrative)

**Q1 — Is the rule signal-driven or test-set tuned?**

Signal-driven. The rule consults `logic_engine_confirmed_codes`, which is computed by the criterion-checker pipeline from clinical evidence — not from gold labels. No threshold parameters are tuned. No dev split is consumed by this rule. The only "choice" is the conservative-veto condition (rank-0 not confirmed AND rank-1 confirmed), and that is a binary structural condition derived from the L2-R1 sandbox hypothesis Pass-3, not a tuned cutoff.

**Q2 — Is the rule clinically defensible?**

Yes. Diagnostician-ranking and criterion-checker confirmation are two independent sources of evidence.
When they disagree on rank-0, the conservative veto defers to whichever candidate has criterion-level
confirmation. This mirrors a clinical second-opinion workflow: when the clinician's first-pass label
lacks criterion support but the second-pass label is criterion-confirmed, switching is the more
conservative position. Crucially, the rule does NOT introduce any trained classifier or hand-tuned
threshold; it is a pure logical rule, and the rule fires only when both rank-0 lacks confirmation
AND rank-1 has confirmation.

---

## 10. Verdict

**GREEN**

Scoring:
- Modes with positive net_gain: **6/6**
- Modes with worsened F32/F41 asymmetry: **0/6**
- Modes with worsened F42 recall: **0/6**
- Both-mode pass-through worsened: **NO**

Recommended action: proceed to BETA-2c production patch planning (Plan v1.3.4-r1 or v1.3.5).

---

## Hard-constraint compliance

- ✅ No production code modified (`hied.py` untouched)
- ✅ No commit, no push from this validation step
- ✅ No tag move (`paper-integration-v0.1` still frozen)
- ✅ No manuscript drafts modified
- ✅ All 9 metric categories computed (Top-1, Top-3, EM, macro-F1, weighted-F1, Overall, 2-class, 4-class, F32/F41 cascade, F42 recall, both pass-through, change rate, delta, clinical check)
- ✅ Output is uncommitted markdown audit at `docs/paper/integration/GAP_E_1B_ALPHA_TARGETED_VALIDATION.md`
