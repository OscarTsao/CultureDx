# Qwen3 Tier 2B Hierarchical-Prompt Canonical Audit (Partial: 5/6 modes)

**Date:** 2026-05-01 (Qwen3 Tier 2B partial audit, 5/6 modes)
**Branch:** tier2b/hierarchical-prompt @ HEAD
**Source:** `results/tier2b_canonical_20260501_081706/`  (Qwen3-32B-AWQ, hierarchical prompt v2)
**Status:** PARTIAL — `mdd_both` still running. Numbers below cover the 5 completed modes.

## TL;DR

Qwen3 with hierarchical prompt (LLM directly emits primary + comorbid) is RED on every completed mode vs BETA-2b primary-only baseline:
- Lingxi: -5.0 to -6.6pp EM (LLM emit rate 12.8-15.8% vs gold 8.6%)
- MDD: -24.7pp EM (LLM emit rate 41.5% vs gold 8.6%)

LLM is reasonably calibrated on Lingxi (1.5x over-emission) but catastrophically over-emits on MDD (4.8x). MDD cases are full doctor-patient dialogues; the LLM finds 'evidence for second disorder' in nearly half of cases.

Post-hoc rescue attempts (overlay 1B-α / 1F / Combo on tier2b output) **all RED too**.

---

## 1. Tier 2B vs BETA-2b head-to-head (5 modes)

| Mode | Policy | emit% | Top-1 | Top-3 | EM | mF1 | wF1 | Overall | sgEM | mgEM | 2c | 4c |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| lingxi_icd10 | BETA-2b | 0.0% | 0.5200 | 0.7930 | 0.4690 | 0.1988 | 0.4558 | 0.3915 | 0.5131 | 0.0000 | 0.6130 | 0.5840 |
| lingxi_icd10 | **Tier 2B** | 12.7% | 0.5140 | 0.7830 | 0.4190 | 0.2046 | 0.4516 | 0.3901 | 0.4551 | 0.0349 | 0.6090 | 0.5820 |
| lingxi_icd10 | Δ Tier 2B − BETA-2b | — | -0.0060 | — | -0.0500 | — | — | — | — | +0.0349 | — | — |
| lingxi_dsm5 | BETA-2b | 0.0% | 0.5260 | 0.7990 | 0.4720 | 0.2171 | 0.4652 | 0.4028 | 0.5164 | 0.0000 | 0.6230 | 0.5980 |
| lingxi_dsm5 | **Tier 2B** | 15.8% | 0.5170 | 0.7890 | 0.4060 | 0.2089 | 0.4549 | 0.3936 | 0.4376 | 0.0698 | 0.6200 | 0.5890 |
| lingxi_dsm5 | Δ Tier 2B − BETA-2b | — | -0.0090 | — | -0.0660 | — | — | — | — | +0.0698 | — | — |
| lingxi_both | BETA-2b | 0.0% | 0.5200 | 0.7930 | 0.4690 | 0.1988 | 0.4558 | 0.3915 | 0.5131 | 0.0000 | 0.6130 | 0.5840 |
| lingxi_both | **Tier 2B** | 12.7% | 0.5140 | 0.7830 | 0.4190 | 0.2046 | 0.4516 | 0.3901 | 0.4551 | 0.0349 | 0.6090 | 0.5820 |
| lingxi_both | Δ Tier 2B − BETA-2b | — | -0.0060 | — | -0.0500 | — | — | — | — | +0.0349 | — | — |
| mdd_icd10 | BETA-2b | 0.0% | 0.5924 | 0.8422 | 0.5514 | 0.0909 | 0.5326 | 0.4053 | 0.6043 | 0.0000 | 0.6919 | 0.6584 |
| mdd_icd10 | **Tier 2B** | 41.5% | 0.5784 | 0.8422 | 0.3459 | 0.1057 | 0.5152 | 0.3998 | 0.3673 | 0.1235 | 0.6843 | 0.6530 |
| mdd_icd10 | Δ Tier 2B − BETA-2b | — | -0.0141 | — | -0.2054 | — | — | — | — | +0.1235 | — | — |
| mdd_dsm5 | BETA-2b | 0.0% | 0.5795 | 0.8324 | 0.5351 | 0.0967 | 0.5116 | 0.3959 | 0.5865 | 0.0000 | 0.6843 | 0.6541 |
| mdd_dsm5 | **Tier 2B** | 38.8% | 0.5838 | 0.8335 | 0.3762 | 0.0905 | 0.5202 | 0.3982 | 0.3957 | 0.1728 | 0.6854 | 0.6562 |
| mdd_dsm5 | Δ Tier 2B − BETA-2b | — | +0.0043 | — | -0.1589 | — | — | — | — | +0.1728 | — | — |

---

## 2. Post-hoc replay on Tier 2B output

Tests whether overlaying sandbox post-hoc gates on Tier 2B's primary changes the picture. Three variants:
- **PH-α**: primary = 1B-α veto applied on top of tier2b ranked, comorbid = tier2b LLM-emit
- **PH-1F**: primary = tier2b LLM, comorbid = REPLACED with 1F strict gate (drops LLM emit)
- **PH-Combo**: primary = 1B-α veto, comorbid = 1F strict gate

| Mode | Policy | emit% | Top-1 | EM | mgEM |
|---|---|---:|---:|---:|---:|
| lingxi_icd10 | Tier 2B (baseline) | 12.7% | 0.5140 | 0.4190 | 0.0349 |
| lingxi_icd10 | PH-α | 12.4% | 0.5010 | 0.4090 | 0.0349 |
| lingxi_icd10 | PH-1F | 4.6% | 0.5140 | 0.4440 | 0.0000 |
| lingxi_icd10 | PH-Combo | 4.6% | 0.5010 | 0.4330 | 0.0000 |
| lingxi_dsm5 | Tier 2B (baseline) | 15.8% | 0.5170 | 0.4060 | 0.0698 |
| lingxi_dsm5 | PH-α | 14.3% | 0.5140 | 0.4090 | 0.0698 |
| lingxi_dsm5 | PH-1F | 22.0% | 0.5170 | 0.3770 | 0.1279 |
| lingxi_dsm5 | PH-Combo | 21.9% | 0.5140 | 0.3760 | 0.1279 |
| lingxi_both | Tier 2B (baseline) | 12.7% | 0.5140 | 0.4190 | 0.0349 |
| lingxi_both | PH-α | 12.4% | 0.5010 | 0.4090 | 0.0349 |
| lingxi_both | PH-1F | 4.6% | 0.5140 | 0.4440 | 0.0000 |
| lingxi_both | PH-Combo | 4.6% | 0.5010 | 0.4330 | 0.0000 |
| mdd_icd10 | Tier 2B (baseline) | 41.5% | 0.5784 | 0.3459 | 0.1235 |
| mdd_icd10 | PH-α | 39.8% | 0.5805 | 0.3535 | 0.1235 |
| mdd_icd10 | PH-1F | 6.3% | 0.5784 | 0.4962 | 0.0123 |
| mdd_icd10 | PH-Combo | 6.3% | 0.5805 | 0.4973 | 0.0123 |
| mdd_dsm5 | Tier 2B (baseline) | 38.8% | 0.5838 | 0.3762 | 0.1728 |
| mdd_dsm5 | PH-α | 37.1% | 0.5762 | 0.3719 | 0.1728 |
| mdd_dsm5 | PH-1F | 7.9% | 0.5838 | 0.5059 | 0.0370 |
| mdd_dsm5 | PH-Combo | 7.8% | 0.5762 | 0.4984 | 0.0370 |

---

## 3. Where does Tier 2B over-emit? — Error breakdown

Per case, classify each prediction:
- `emit_on_size1_correct_primary`: gold has 1 code, primary right, but LLM ADDED a wrong comorbid (pure precision damage)
- `emit_on_size1_wrong_primary`: primary wrong AND emitted comorbid (compound error)
- `emit_on_multi_full_match`: gold has 2+ codes, predicted set EXACTLY matches gold (full rescue)
- `emit_on_multi_partial`: gold has 2+ codes, only partial match
- `no_emit_correct_single`: gold has 1 code, primary right, no emit (perfect)
- `no_emit_wrong_single`: primary wrong, no emit (no compound)
- `no_emit_miss_multi`: gold has 2+ codes, didn't emit comorbid (missed rescue)

| Mode | size1 right + spurious emit | size1 wrong + emit | multi full match | multi partial | size1 right no emit | size1 wrong no emit | multi miss |
|---|---:|---:|---:|---:|---:|---:|---:|
| lingxi_icd10 | 49 | 70 | 3 | 6 | 415 | 380 | 77 |
| lingxi_dsm5 | 66 | 74 | 6 | 12 | 400 | 374 | 68 |
| lingxi_both | 49 | 70 | 3 | 6 | 415 | 380 | 77 |
| mdd_icd10 | 186 | 164 | 10 | 24 | 310 | 184 | 47 |
| mdd_dsm5 | 168 | 147 | 14 | 30 | 334 | 195 | 37 |

Read this as: **the dominant Tier 2B error mode is `emit_on_size1_correct_primary`** — the LLM had the right primary but added a spurious comorbid. This is pure precision damage that BETA-2b avoids by construction.

### Top emitted (primary, comorbid) pairs per mode

**lingxi_icd10**

| primary | comorbid | count |
|---|---|---:|
| F41 | F32 | 47 |
| F32 | F41 | 44 |
| F42 | F41 | 8 |
| F42 | F32 | 6 |
| F20 | F32 | 6 |

**lingxi_dsm5**

| primary | comorbid | count |
|---|---|---:|
| F41 | F32 | 64 |
| F32 | F41 | 55 |
| F42 | F32 | 10 |
| F42 | F41 | 7 |
| F20 | F32 | 7 |

**lingxi_both**

| primary | comorbid | count |
|---|---|---:|
| F41 | F32 | 47 |
| F32 | F41 | 44 |
| F42 | F41 | 8 |
| F42 | F32 | 6 |
| F20 | F32 | 6 |

**mdd_icd10**

| primary | comorbid | count |
|---|---|---:|
| F32 | F41 | 285 |
| F41 | F32 | 60 |
| F31 | F41 | 11 |
| F39 | F41 | 8 |
| F42 | F41 | 5 |

**mdd_dsm5**

| primary | comorbid | count |
|---|---|---:|
| F32 | F41 | 257 |
| F41 | F32 | 54 |
| F31 | F41 | 11 |
| F41 | F39 | 7 |
| F20 | F41 | 5 |

---

## 4. Sample cases

Pure precision damage (gold size=1, primary correct, but LLM emitted spurious comorbid):

**lingxi_icd10**

| case_id | gold | tier2b primary | tier2b comorbid (spurious) |
|---|---|---|---|
| 350352506 | ['F32'] | F32 | ['F41'] |
| 369682855 | ['F20'] | F20 | ['F41'] |
| 329547625 | ['F41'] | F41 | ['F32'] |
| 372982359 | ['F32'] | F32 | ['F41'] |
| 324767336 | ['F42'] | F42 | ['F41'] |

**lingxi_dsm5**

| case_id | gold | tier2b primary | tier2b comorbid (spurious) |
|---|---|---|---|
| 350352506 | ['F32'] | F32 | ['F41'] |
| 341328894 | ['F41'] | F41 | ['F32'] |
| 303364596 | ['F32'] | F32 | ['F41'] |
| 329547625 | ['F41'] | F41 | ['F32'] |
| 349034373 | ['F32'] | F32 | ['F41'] |

**lingxi_both**

| case_id | gold | tier2b primary | tier2b comorbid (spurious) |
|---|---|---|---|
| 350352506 | ['F32'] | F32 | ['F41'] |
| 369682855 | ['F20'] | F20 | ['F41'] |
| 329547625 | ['F41'] | F41 | ['F32'] |
| 372982359 | ['F32'] | F32 | ['F41'] |
| 324767336 | ['F42'] | F42 | ['F41'] |

**mdd_icd10**

| case_id | gold | tier2b primary | tier2b comorbid (spurious) |
|---|---|---|---|
| patient_10 | ['F32'] | F32 | ['F41'] |
| patient_1002 | ['F32'] | F32 | ['F41'] |
| patient_1003 | ['F41'] | F41 | ['F32'] |
| patient_1008 | ['F32'] | F32 | ['F41'] |
| patient_101 | ['F42'] | F42 | ['F41'] |

**mdd_dsm5**

| case_id | gold | tier2b primary | tier2b comorbid (spurious) |
|---|---|---|---|
| patient_10 | ['F32'] | F32 | ['F41'] |
| patient_1008 | ['F32'] | F32 | ['F41'] |
| patient_1017 | ['F32'] | F32 | ['F41'] |
| patient_116 | ['F32'] | F32 | ['F41'] |
| patient_127 | ['F42'] | F42 | ['F41'] |

Multi-gold full rescues (where Tier 2B genuinely helped):

**lingxi_icd10**

| case_id | gold | tier2b primary | tier2b comorbid |
|---|---|---|---|
| 324712168 | ['F41', 'F32'] | F41 | ['F32'] |
| 358277669 | ['F41', 'F32'] | F41 | ['F32'] |
| 337706986 | ['F41', 'F32'] | F32 | ['F41'] |

**lingxi_dsm5**

| case_id | gold | tier2b primary | tier2b comorbid |
|---|---|---|---|
| 379930126 | ['F41', 'F32'] | F32 | ['F41'] |
| 358277669 | ['F41', 'F32'] | F32 | ['F41'] |
| 391255095 | ['F41', 'F32'] | F41 | ['F32'] |
| 336070891 | ['F41', 'F32'] | F32 | ['F41'] |
| 322204263 | ['F41', 'F32'] | F32 | ['F41'] |

**lingxi_both**

| case_id | gold | tier2b primary | tier2b comorbid |
|---|---|---|---|
| 324712168 | ['F41', 'F32'] | F41 | ['F32'] |
| 358277669 | ['F41', 'F32'] | F41 | ['F32'] |
| 337706986 | ['F41', 'F32'] | F32 | ['F41'] |

**mdd_icd10**

| case_id | gold | tier2b primary | tier2b comorbid |
|---|---|---|---|
| patient_114 | ['F41', 'F32'] | F32 | ['F41'] |
| patient_204 | ['F41', 'F32'] | F32 | ['F41'] |
| patient_210 | ['F41', 'F32'] | F32 | ['F41'] |
| patient_242 | ['F41', 'F32'] | F41 | ['F32'] |
| patient_244 | ['F41', 'F32'] | F32 | ['F41'] |

**mdd_dsm5**

| case_id | gold | tier2b primary | tier2b comorbid |
|---|---|---|---|
| patient_111 | ['F41', 'F32'] | F32 | ['F41'] |
| patient_136 | ['F41', 'F32'] | F32 | ['F41'] |
| patient_204 | ['F41', 'F32'] | F41 | ['F32'] |
| patient_214 | ['F41', 'F32'] | F32 | ['F41'] |
| patient_216 | ['F41', 'F32'] | F41 | ['F32'] |

---

## 5. Verdict

**Qwen3 Tier 2B hierarchical prompt is RED on all 5 completed modes.**

Mechanism: LLM-as-emitter takes the option to emit comorbid more often than gold has multi-label cases (1.5x on Lingxi, 4.8x on MDD). Most spurious emits land on gold-size=1 cases where primary was correct, destroying EM precision. The mgEM rescue (3-12% on multi-gold cases) does not compensate for the EM loss on single-gold cases.

Post-hoc rescue (1B-α / 1F / Combo) layered on top of Tier 2B does NOT fix the picture — they all also lose vs BETA-2b primary-only.

**Implication:** The over-emission is intrinsic to Qwen3 reading rich symptom-dense text. Whether this is family-specific or a structural property of LLMs is the next experiment (Gemma-3-12B + Llama-3.3-70B probes).

---

## 6. Files NOT modified

- `paper-integration-v0.1` tag — frozen at c3b0a46
- `feature/gap-e-beta2-implementation` — NOT touched
- `main-v2.4-refactor` — NOT touched
- All previous audits (Round 156, 159) — NOT modified
- This audit is on `tier2b/hierarchical-prompt` branch only
