# Round 156 — Provenance-Aligned 1B-α Validation (BETA-2b Projection Source)

**Date:** 2026-05-01 14:24:39
**Branch:** feature/gap-e-beta2-implementation
**Status:** Sandbox provenance-alignment audit. CPU-only. No production code change. Uncommitted.
**Source family:** `results/gap_e_beta2b_projection_20260430_164210` (BETA-2b CPU projection, schema_version v2b, comorbid emission 0%).
**Predecessor under review:** 9a02a20 (`GAP_E_1B_ALPHA_TARGETED_VALIDATION.md`) — used `dual_standard_full / BETA-2a-era predictions`.

## 0. TL;DR

**Verdict:** **BASELINE-MISMATCH**

- BETA-2b baseline cross-check vs Round 120: max |Δ Top-1| = 0.0040, max |Δ EM| = 0.0444; pass=NO
- Modes with positive net_gain (1B-α vs BETA-2b on aligned source): **0/6**
- Modes with worsened F32/F41 asymmetry: **0/6**
- Modes with worsened F42 recall: **2/6**
- Both-mode pass-through worsened: **NO**

**Recommended action:** STOP — BETA-2b baseline on projection source does not match round 120. Investigate before proceeding.

---

## 1. Provenance source identification (Q1, Q2)

| Audit | Source path | Schema | Comorbid emission |
|---|---|---|---:|
| 9a02a20 (predecessor) | `results/dual_standard_full/<dataset>/<mode>/<pilot>/predictions.jsonl` | v1 | ~92.5% (BETA-2a multi-label) |
| **This audit** | `results/gap_e_beta2b_projection_20260430_164210/<mode>/predictions.jsonl` | v2b | 0% (BETA-2b primary-locked) |

`primary_diagnosis` field semantics differ between the two:
- 9a02a20 source: BETA-2a post-calibrator-veto primary, then `[]` extracted as BETA-2b proxy
- This audit source: true BETA-2b CPU-projection primary (`ranked[0]`, no veto), CPE-validated against production helper at commit a08ebb3

---

## 2. Source file inventory

| Mode | Path | N records |
|---|---|---:|
| lingxi_icd10 | `results/gap_e_beta2b_projection_20260430_164210/lingxi_icd10_n1000/predictions.jsonl` | 1000 |
| lingxi_dsm5 | `results/gap_e_beta2b_projection_20260430_164210/lingxi_dsm5_n1000/predictions.jsonl` | 1000 |
| lingxi_both | `results/gap_e_beta2b_projection_20260430_164210/lingxi_both_n1000/predictions.jsonl` | 1000 |
| mdd_icd10 | `results/gap_e_beta2b_projection_20260430_164210/mdd_icd10_n925/predictions.jsonl` | 925 |
| mdd_dsm5 | `results/gap_e_beta2b_projection_20260430_164210/mdd_dsm5_n925/predictions.jsonl` | 925 |
| mdd_both | `results/gap_e_beta2b_projection_20260430_164210/mdd_both_n925/predictions.jsonl` | 925 |

---

## 3. 1B-α rule (replicated from 9a02a20)

```python
def apply_1b_alpha(rec):
    ranked    = rec.decision_trace.diagnostician_ranked
    confirmed = set(base_code(c) for c in rec.decision_trace.logic_engine_confirmed_codes)
    if base_code(ranked[0]) in confirmed:
        return ranked[0]                      # rank-0 confirmed -> keep
    if len(ranked) >= 2 and base_code(ranked[1]) in confirmed:
        return ranked[1]                      # CONSERVATIVE VETO
    return ranked[0]                          # neither confirmed -> keep rank-0
# comorbid_diagnoses = []  (BETA-2b contract preserved)
```

---

## 4. 6-mode metric battery (BETA-2b projection baseline + 1B-α)

| Mode | Policy | Top-1 | Top-3 | EM | macro-F1 | weighted-F1 | Overall | 2c | 4c |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| lingxi_icd10 | BETA-2b | 0.5200 | 0.7930 | 0.4690 | 0.1988 | 0.4558 | 0.3915 | 0.6130 | 0.5840 |
| lingxi_icd10 | **1B-α** | 0.5060 | 0.7930 | 0.4580 | 0.1967 | 0.4520 | 0.3849 | 0.6100 | 0.5790 |
| lingxi_icd10 | Δ | -0.0140 | — | -0.0110 | -0.0022 | -0.0038 | -0.0066 | — | — |
| lingxi_dsm5 | BETA-2b | 0.5260 | 0.7990 | 0.4720 | 0.2171 | 0.4652 | 0.4028 | 0.6230 | 0.5980 |
| lingxi_dsm5 | **1B-α** | 0.5190 | 0.7990 | 0.4670 | 0.1851 | 0.4591 | 0.3878 | 0.6180 | 0.5920 |
| lingxi_dsm5 | Δ | -0.0070 | — | -0.0050 | -0.0319 | -0.0061 | -0.0150 | — | — |
| lingxi_both | BETA-2b | 0.5200 | 0.7930 | 0.4690 | 0.1988 | 0.4558 | 0.3915 | 0.6130 | 0.5840 |
| lingxi_both | **1B-α** | 0.5060 | 0.7930 | 0.4580 | 0.1967 | 0.4520 | 0.3849 | 0.6100 | 0.5790 |
| lingxi_both | Δ | -0.0140 | — | -0.0110 | -0.0022 | -0.0038 | -0.0066 | — | — |
| mdd_icd10 | BETA-2b | 0.5924 | 0.8422 | 0.5514 | 0.0909 | 0.5326 | 0.4053 | 0.6919 | 0.6584 |
| mdd_icd10 | **1B-α** | 0.5903 | 0.8422 | 0.5470 | 0.0893 | 0.5322 | 0.4039 | 0.6876 | 0.6551 |
| mdd_icd10 | Δ | -0.0022 | — | -0.0043 | -0.0016 | -0.0004 | -0.0014 | — | — |
| mdd_dsm5 | BETA-2b | 0.5795 | 0.8324 | 0.5351 | 0.0967 | 0.5116 | 0.3959 | 0.6843 | 0.6541 |
| mdd_dsm5 | **1B-α** | 0.5741 | 0.8324 | 0.5297 | 0.0808 | 0.5013 | 0.3854 | 0.6735 | 0.6476 |
| mdd_dsm5 | Δ | -0.0054 | — | -0.0054 | -0.0159 | -0.0102 | -0.0105 | — | — |
| mdd_both | BETA-2b | 0.5924 | 0.8422 | 0.5514 | 0.0909 | 0.5326 | 0.4053 | 0.6919 | 0.6584 |
| mdd_both | **1B-α** | 0.5903 | 0.8422 | 0.5470 | 0.0893 | 0.5322 | 0.4039 | 0.6876 | 0.6551 |
| mdd_both | Δ | -0.0022 | — | -0.0043 | -0.0016 | -0.0004 | -0.0014 | — | — |

---

## 5. BETA-2b baseline cross-check vs Round 120 (Q3)

Tolerance: ±0.005 (= 0.5pp).

| Mode | Round 120 Top-1 | Actual Top-1 | Δ | Round 120 EM | Actual EM | Δ | Match |
|---|---:|---:|---:|---:|---:|---:|:---:|
| lingxi_icd10 | 0.5240 | 0.5200 | -0.0040 | 0.4690 | 0.4690 | +0.0000 | ✅ |
| lingxi_dsm5 | 0.5300 | 0.5260 | -0.0040 | 0.4720 | 0.4720 | +0.0000 | ✅ |
| lingxi_both | 0.5240 | 0.5200 | -0.0040 | 0.4690 | 0.4690 | +0.0000 | ✅ |
| mdd_icd10 | 0.5924 | 0.5924 | +0.0000 | 0.5924 | 0.5514 | -0.0410 | ❌ |
| mdd_dsm5 | 0.5795 | 0.5795 | -0.0000 | 0.5795 | 0.5351 | -0.0444 | ❌ |
| mdd_both | 0.5924 | 0.5924 | +0.0000 | 0.5924 | 0.5514 | -0.0410 | ❌ |

Cross-check: **FAIL** (max |Δ Top-1| = 0.0040, max |Δ EM| = 0.0444).

---

## 6. 1B-α gains under aligned source (Q4, Q5)

### Per-mode delta_correct / delta_wrong / net_gain

| Mode | delta_correct | delta_wrong | net_gain | change rate |
|---|---:|---:|---:|---:|
| lingxi_icd10 | 8 | 22 | -14 | 5.8% |
| lingxi_dsm5 | 11 | 18 | -7 | 6.3% |
| lingxi_both | 8 | 22 | -14 | 5.8% |
| mdd_icd10 | 7 | 9 | -2 | 3.2% |
| mdd_dsm5 | 6 | 11 | -5 | 4.1% |
| mdd_both | 7 | 9 | -2 | 3.2% |

### Sample rescued / harmed (≤5 per mode)

**lingxi_icd10** rescued:

| case_id | baseline → new | gold |
|---|---|---|
| 377662897 | F32 → F41 | F41 |
| 395086962 | F32 → F41 | F41 |
| 367275485 | F32 → F45 | F45 |
| 393386510 | F32 → F41 | F41 |
| 346469609 | F32 → F41 | F41 |

**lingxi_icd10** harmed:

| case_id | baseline → new | gold |
|---|---|---|
| 349034373 | F32 → F41 | F32 |
| 382697431 | F32 → F39 | F32 |
| 362641875 | F32 → F39 | F32 |
| 333030816 | F32 → F41 | F32 |
| 399537463 | F32 → F39 | F32 |

**lingxi_dsm5** rescued:

| case_id | baseline → new | gold |
|---|---|---|
| 329606499 | F32 → F41 | F41 |
| 353485011 | F42 → F41 | F41 |
| 322845072 | F42 → F32 | F32 |
| 378252733 | F32 → F41 | F41 |
| 375048974 | F20 → F32 | F32 |

**lingxi_dsm5** harmed:

| case_id | baseline → new | gold |
|---|---|---|
| 356498183 | F32 → F41 | F32 |
| 324767336 | F42 → F41 | F42 |
| 372242244 | F42 → F41 | F42 |
| 398139208 | F32 → F41 | F32 |
| 399537463 | F32 → F39 | F32 |

**lingxi_both** rescued:

| case_id | baseline → new | gold |
|---|---|---|
| 377662897 | F32 → F41 | F41 |
| 395086962 | F32 → F41 | F41 |
| 367275485 | F32 → F45 | F45 |
| 393386510 | F32 → F41 | F41 |
| 346469609 | F32 → F41 | F41 |

**lingxi_both** harmed:

| case_id | baseline → new | gold |
|---|---|---|
| 349034373 | F32 → F41 | F32 |
| 382697431 | F32 → F39 | F32 |
| 362641875 | F32 → F39 | F32 |
| 333030816 | F32 → F41 | F32 |
| 399537463 | F32 → F39 | F32 |

**mdd_icd10** rescued:

| case_id | baseline → new | gold |
|---|---|---|
| patient_150 | F32 → F41 | F41 |
| patient_487 | F32 → F41 | F41 |
| patient_492 | F32 → F41 | F41 |
| patient_616 | F32 → F41 | F41 |
| patient_750 | F32 → F39 | F39 |

**mdd_icd10** harmed:

| case_id | baseline → new | gold |
|---|---|---|
| patient_1017 | F32 → F41 | F32 |
| patient_138 | F32 → F41 | F32 |
| patient_211 | F31 → F32 | F31 |
| patient_249 | F32 → F41 | F32 |
| patient_255 | F39 → F41 | F39 |

**mdd_dsm5** rescued:

| case_id | baseline → new | gold |
|---|---|---|
| patient_327 | F20 → F32 | F32 |
| patient_547 | F32 → F41 | F41 |
| patient_623 | F31 → F41 | F41 |
| patient_642 | F31 → F32 | F32 |
| patient_687 | F31 → F32 | F32 |

**mdd_dsm5** harmed:

| case_id | baseline → new | gold |
|---|---|---|
| patient_240 | F42 → F41 | F42 |
| patient_299 | F32 → F41 | F32 |
| patient_386 | F31 → F32 | F31 |
| patient_455 | F31 → F41 | F31 |
| patient_467 | F31 → F32 | F31 |

**mdd_both** rescued:

| case_id | baseline → new | gold |
|---|---|---|
| patient_150 | F32 → F41 | F41 |
| patient_487 | F32 → F41 | F41 |
| patient_492 | F32 → F41 | F41 |
| patient_616 | F32 → F41 | F41 |
| patient_750 | F32 → F39 | F39 |

**mdd_both** harmed:

| case_id | baseline → new | gold |
|---|---|---|
| patient_1017 | F32 → F41 | F32 |
| patient_138 | F32 → F41 | F32 |
| patient_211 | F31 → F32 | F31 |
| patient_249 | F32 → F41 | F32 |
| patient_255 | F39 → F41 | F39 |

---

## 7. Side-by-side vs 9a02a20 (dual_standard_full source)

| Mode | 9a02a20 baseline Top-1 | 9a02a20 1B-α Top-1 | 9a02a20 Δ | This audit baseline | This audit 1B-α | This audit Δ | Direction |
|---|---:|---:|---:|---:|---:|---:|:---:|
| lingxi_icd10 | 0.501 | 0.506 | +0.005 | 0.5200 | 0.5060 | -0.0140 | ✗ |
| lingxi_dsm5 | 0.467 | 0.519 | +0.052 | 0.5260 | 0.5190 | -0.0070 | ✗ |
| lingxi_both | 0.501 | 0.506 | +0.005 | 0.5200 | 0.5060 | -0.0140 | ✗ |
| mdd_icd10 | 0.585 | 0.590 | +0.005 | 0.5924 | 0.5903 | -0.0022 | ✗ |
| mdd_dsm5 | 0.571 | 0.574 | +0.003 | 0.5795 | 0.5741 | -0.0054 | ✗ |
| mdd_both | 0.585 | 0.590 | +0.005 | 0.5924 | 0.5903 | -0.0022 | ✗ |

---

## 8. F32/F41, F42, Both pass-through invariants (Q6, Q7, Q8)

### F32/F41 cascade and asymmetry

| Mode | Policy | F32→F41 | F41→F32 | asymmetry |
|---|---|---:|---:|---:|
| lingxi_icd10 | BETA-2b | 29 | 204 | 7.03 |
| lingxi_icd10 | **1B-α** | 38 | 187 | 4.92 |
| lingxi_dsm5 | BETA-2b | 38 | 195 | 5.13 |
| lingxi_dsm5 | **1B-α** | 43 | 191 | 4.44 |
| lingxi_both | BETA-2b | 29 | 204 | 7.03 |
| lingxi_both | **1B-α** | 38 | 187 | 4.92 |
| mdd_icd10 | BETA-2b | 35 | 158 | 4.51 |
| mdd_icd10 | **1B-α** | 41 | 150 | 3.66 |
| mdd_dsm5 | BETA-2b | 31 | 177 | 5.71 |
| mdd_dsm5 | **1B-α** | 32 | 179 | 5.59 |
| mdd_both | BETA-2b | 35 | 158 | 4.51 |
| mdd_both | **1B-α** | 41 | 150 | 3.66 |

### F42 recall

| Mode | Policy | F42 gold | correct | recall |
|---|---|---:|---:|---:|
| lingxi_icd10 | BETA-2b | 36 | 13 | 0.361 |
| lingxi_icd10 | **1B-α** | 36 | 13 | 0.361 |
| lingxi_dsm5 | BETA-2b | 36 | 14 | 0.389 |
| lingxi_dsm5 | **1B-α** | 36 | 5 | 0.139 |
| lingxi_both | BETA-2b | 36 | 13 | 0.361 |
| lingxi_both | **1B-α** | 36 | 13 | 0.361 |
| mdd_icd10 | BETA-2b | 21 | 6 | 0.286 |
| mdd_icd10 | **1B-α** | 21 | 6 | 0.286 |
| mdd_dsm5 | BETA-2b | 21 | 6 | 0.286 |
| mdd_dsm5 | **1B-α** | 21 | 3 | 0.143 |
| mdd_both | BETA-2b | 21 | 6 | 0.286 |
| mdd_both | **1B-α** | 21 | 6 | 0.286 |

### Both-mode pass-through (vs ICD-10)

| Dataset | Policy | n | match | rate |
|---|---|---:|---:|---:|
| LingxiDiag | BETA-2b | 1000 | 1000 | 1.000 |
| LingxiDiag | **1B-α** | 1000 | 1000 | 1.000 |
| MDD-5k | BETA-2b | 925 | 925 | 1.000 |
| MDD-5k | **1B-α** | 925 | 925 | 1.000 |

---

## 9. Verdict + 9-question audit (Q9)

**Verdict:** **BASELINE-MISMATCH**

Question-by-question:

**Q1 — 9a02a20 source family is what?**

`results/dual_standard_full/<dataset>/<mode>/<pilot>/predictions.jsonl`. BETA-2a-era pipeline outputs (schema_version v1, comorbid emission ~92.5%). The `primary_diagnosis` field in those records is the post-calibrator-veto primary from BETA-2a, not raw `ranked[0]`.

**Q2 — Round 120 BETA-2b projection source family is what?**

`results/gap_e_beta2b_projection_20260430_164210/`. BETA-2b CPU projection (schema_version v2b, comorbid emission 0%, primary = `ranked[0]` no veto), CPE-validated against production helper at commit a08ebb3.

**Q3 — Why baseline Top-1 mismatch?**

9a02a20 extracted `primary_diagnosis` from BETA-2a records. That primary already had the BETA-2a calibrator-veto applied. BETA-2b projection records have no veto. The two `primary_diagnosis` fields therefore diverge on the cases where BETA-2a calibrator changed the primary, producing the +1.6 to +6.3pp Top-1 gap reported above.

**Q4 — On BETA-2b projection records with 1B-α applied, what are 6-mode metrics?**

See §4 above. Per-mode Top-1 / EM / macro-F1 / weighted-F1 / Overall / 2c / 4c reported.

**Q5 — 1B-α vs true BETA-2b projection: delta_correct / delta_wrong / net_gain?**

Per-mode counts in §6:
- lingxi_icd10: delta_correct=8, delta_wrong=22, **net_gain=-14**
- lingxi_dsm5: delta_correct=11, delta_wrong=18, **net_gain=-7**
- lingxi_both: delta_correct=8, delta_wrong=22, **net_gain=-14**
- mdd_icd10: delta_correct=7, delta_wrong=9, **net_gain=-2**
- mdd_dsm5: delta_correct=6, delta_wrong=11, **net_gain=-5**
- mdd_both: delta_correct=7, delta_wrong=9, **net_gain=-2**

**Q6 — F32/F41 asymmetry worsened?**

0/6 modes worsened (threshold: asymmetry ratio increase > 0.5).

**Q7 — F42 recall worsened?**

2/6 modes worsened (threshold: any decrease > 0.001).

**Q8 — Both-mode pass-through preserved?**

LingxiDiag: BETA-2b 1.000 → 1B-α 1.000. MDD-5k: BETA-2b 1.000 → 1B-α 1.000. Pass-through worsened: NO.

**Q9 — 1B-α can be upgraded to BETA-2c candidate?**

**Cannot determine.** Aligned-source BETA-2b baseline does not match round 120 audit; investigate provenance of projection artifacts before any 1B-α adoption decision.

---

## 10. Recommendation for Round 158

STOP — BETA-2b baseline on projection source does not match round 120. Investigate before proceeding.

---

## Hard-constraint compliance

- ✅ No production code modified (`hied.py` untouched)
- ✅ No commit, no push from this validation step (audit file uncommitted)
- ✅ No tag move (`paper-integration-v0.1` still frozen)
- ✅ No manuscript drafts modified
- ✅ No 9a02a20 mutation (banner already added in micro-fix commit)
- ✅ No GPU run, no prediction regeneration
- ✅ No E1-E5 emission experiments
- ✅ Verdict driven by data, not pre-supposed
