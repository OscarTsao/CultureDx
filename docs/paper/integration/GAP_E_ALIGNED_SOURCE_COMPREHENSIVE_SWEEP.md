# Round 159 — Aligned-Source Comprehensive Sandbox Sweep

**Date:** 2026-05-01 14:58:22
**Branch:** feature/gap-e-beta2-implementation
**Status:** Sandbox audit. CPU-only. No production code change. Uncommitted.
**Source family:** `results/gap_e_beta2b_projection_20260430_164210/` (BETA-2b CPU projection, schema_version v2b, real-pipeline intermediate signals).
**Predecessor (contaminated):** `dual_standard_full/` — used in ROUND150 sandbox; baseline contaminated by BETA-2a calibrator-veto.

## 0. TL;DR

Tests every previously-tried emission/primary-selection policy against the BETA-2b primary-only baseline on the aligned source. Verdict per policy at the end.

---

## 1. Policies tested

- **BETA-2b (baseline)**
- **1B-α (conservative veto)**
- **1F (combined strict gate, 1B primary)**
- **1F-on-BETA-2b (combined strict, no veto)**
- **Combo (1B-α + 1F)**
- **1E (per-class threshold)**
- **1A-α (cross-mode disagree)**
- **1A-β (cross-mode pair emission)**
- **1A-δ (cross-mode strict)**
- **2C-α (calibrator disagreement)**
- **2A (LLM re-prompt overlay)**

---

## 2. Per-mode results

### lingxi_icd10

| Policy | emit% | Top-1 | Top-3 | EM | mF1 | wF1 | Overall | mgEM | mgR | Δ EM | Δ Top-1 | net_em |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **BETA-2b** | 0.0% | 0.5200 | 0.7930 | 0.4690 | 0.1988 | 0.4558 | 0.3915 | 0.0000 | 0.3140 | +0.0000 | +0.0000 | +0 |
| 1B-α (conservative veto) | 0.0% | 0.5060 | 0.7930 | 0.4580 | 0.1967 | 0.4520 | 0.3849 | 0.0000 | 0.3081 | -0.0110 | -0.0140 | -11 |
| 1F (combined strict gate, 1B primary) | 5.2% | 0.5060 | 0.7930 | 0.4370 | 0.1967 | 0.4520 | 0.3849 | 0.0116 | 0.3256 | -0.0320 | -0.0140 | -32 |
| 1F-on-BETA-2b (combined strict, no veto) | 5.2% | 0.5200 | 0.7930 | 0.4480 | 0.1988 | 0.4558 | 0.3915 | 0.0116 | 0.3314 | -0.0210 | +0.0000 | -21 |
| Combo (1B-α + 1F) | 5.2% | 0.5060 | 0.7930 | 0.4370 | 0.1967 | 0.4520 | 0.3849 | 0.0116 | 0.3256 | -0.0320 | -0.0140 | -32 |
| 1E (per-class threshold) | 14.5% | 0.5200 | 0.7930 | 0.4070 | 0.1988 | 0.4558 | 0.3915 | 0.0698 | 0.3605 | -0.0620 | +0.0000 | -62 |
| 1A-α (cross-mode disagree) | 9.8% | 0.5200 | 0.7930 | 0.4460 | 0.1988 | 0.4558 | 0.3915 | 0.0233 | 0.3488 | -0.0230 | +0.0000 | -23 |
| 1A-β (cross-mode pair emission) | 48.1% | 0.5200 | 0.7930 | 0.2390 | 0.1988 | 0.4558 | 0.3915 | 0.1512 | 0.4302 | -0.2300 | +0.0000 | -230 |
| 1A-δ (cross-mode strict) | 25.8% | 0.5200 | 0.7930 | 0.3720 | 0.1988 | 0.4558 | 0.3915 | 0.1279 | 0.4167 | -0.0970 | +0.0000 | -97 |
| 2C-α (calibrator disagreement) | 68.5% | 0.5200 | 0.7930 | 0.1870 | 0.1988 | 0.4558 | 0.3915 | 0.2791 | 0.5581 | -0.2820 | +0.0000 | -282 |
| 2A (LLM re-prompt overlay) | 3.9% | 0.5200 | 0.7930 | 0.4530 | 0.1988 | 0.4558 | 0.3915 | 0.0000 | 0.3256 | -0.0160 | +0.0000 | -16 |

### lingxi_dsm5

| Policy | emit% | Top-1 | Top-3 | EM | mF1 | wF1 | Overall | mgEM | mgR | Δ EM | Δ Top-1 | net_em |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **BETA-2b** | 0.0% | 0.5260 | 0.7990 | 0.4720 | 0.2171 | 0.4652 | 0.4028 | 0.0000 | 0.3314 | +0.0000 | +0.0000 | +0 |
| 1B-α (conservative veto) | 0.0% | 0.5190 | 0.7990 | 0.4670 | 0.1851 | 0.4591 | 0.3878 | 0.0000 | 0.3198 | -0.0050 | -0.0070 | -5 |
| 1F (combined strict gate, 1B primary) | 22.1% | 0.5190 | 0.7990 | 0.3800 | 0.1851 | 0.4591 | 0.3878 | 0.1163 | 0.3876 | -0.0920 | -0.0070 | -92 |
| 1F-on-BETA-2b (combined strict, no veto) | 22.3% | 0.5260 | 0.7990 | 0.3850 | 0.2171 | 0.4652 | 0.4028 | 0.1163 | 0.3992 | -0.0870 | +0.0000 | -87 |
| Combo (1B-α + 1F) | 22.1% | 0.5190 | 0.7990 | 0.3800 | 0.1851 | 0.4591 | 0.3878 | 0.1163 | 0.3876 | -0.0920 | -0.0070 | -92 |
| 1E (per-class threshold) | 17.0% | 0.5260 | 0.7990 | 0.3740 | 0.2171 | 0.4652 | 0.4028 | 0.0233 | 0.3430 | -0.0980 | +0.0000 | -98 |
| 1A-α (cross-mode disagree) | 9.8% | 0.5260 | 0.7990 | 0.4460 | 0.2171 | 0.4652 | 0.4028 | 0.0233 | 0.3488 | -0.0260 | +0.0000 | -26 |
| 1A-β (cross-mode pair emission) | 37.5% | 0.5260 | 0.7990 | 0.3000 | 0.2171 | 0.4652 | 0.4028 | 0.1279 | 0.4380 | -0.1720 | +0.0000 | -172 |
| 1A-δ (cross-mode strict) | 29.2% | 0.5260 | 0.7990 | 0.3500 | 0.2171 | 0.4652 | 0.4028 | 0.1395 | 0.4283 | -0.1220 | +0.0000 | -122 |
| 2C-α (calibrator disagreement) | 75.8% | 0.5260 | 0.7990 | 0.1390 | 0.2171 | 0.4652 | 0.4028 | 0.3256 | 0.5872 | -0.3330 | +0.0000 | -333 |
| 2A (LLM re-prompt overlay) | 16.5% | 0.5260 | 0.7990 | 0.4040 | 0.2171 | 0.4652 | 0.4028 | 0.0814 | 0.3779 | -0.0680 | +0.0000 | -68 |

### lingxi_both

| Policy | emit% | Top-1 | Top-3 | EM | mF1 | wF1 | Overall | mgEM | mgR | Δ EM | Δ Top-1 | net_em |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **BETA-2b** | 0.0% | 0.5200 | 0.7930 | 0.4690 | 0.1988 | 0.4558 | 0.3915 | 0.0000 | 0.3140 | +0.0000 | +0.0000 | +0 |
| 1B-α (conservative veto) | 0.0% | 0.5060 | 0.7930 | 0.4580 | 0.1967 | 0.4520 | 0.3849 | 0.0000 | 0.3081 | -0.0110 | -0.0140 | -11 |
| 1F (combined strict gate, 1B primary) | 5.2% | 0.5060 | 0.7930 | 0.4370 | 0.1967 | 0.4520 | 0.3849 | 0.0116 | 0.3256 | -0.0320 | -0.0140 | -32 |
| 1F-on-BETA-2b (combined strict, no veto) | 5.2% | 0.5200 | 0.7930 | 0.4480 | 0.1988 | 0.4558 | 0.3915 | 0.0116 | 0.3314 | -0.0210 | +0.0000 | -21 |
| Combo (1B-α + 1F) | 5.2% | 0.5060 | 0.7930 | 0.4370 | 0.1967 | 0.4520 | 0.3849 | 0.0116 | 0.3256 | -0.0320 | -0.0140 | -32 |
| 1E (per-class threshold) | 14.5% | 0.5200 | 0.7930 | 0.4070 | 0.1988 | 0.4558 | 0.3915 | 0.0698 | 0.3605 | -0.0620 | +0.0000 | -62 |
| 1A-α (cross-mode disagree) | 0.0% | 0.5200 | 0.7930 | 0.4690 | 0.1988 | 0.4558 | 0.3915 | 0.0000 | 0.3140 | +0.0000 | +0.0000 | +0 |
| 1A-β (cross-mode pair emission) | 42.9% | 0.5200 | 0.7930 | 0.2850 | 0.1988 | 0.4558 | 0.3915 | 0.1512 | 0.4438 | -0.1840 | +0.0000 | -184 |
| 1A-δ (cross-mode strict) | 31.2% | 0.5200 | 0.7930 | 0.3540 | 0.1988 | 0.4558 | 0.3915 | 0.1395 | 0.4341 | -0.1150 | +0.0000 | -115 |
| 2C-α (calibrator disagreement) | 68.5% | 0.5200 | 0.7930 | 0.1870 | 0.1988 | 0.4558 | 0.3915 | 0.2791 | 0.5581 | -0.2820 | +0.0000 | -282 |
| 2A (LLM re-prompt overlay) | 0.0% | 0.5200 | 0.7930 | 0.4690 | 0.1988 | 0.4558 | 0.3915 | 0.0000 | 0.3140 | +0.0000 | +0.0000 | +0 |

### mdd_icd10

| Policy | emit% | Top-1 | Top-3 | EM | mF1 | wF1 | Overall | mgEM | mgR | Δ EM | Δ Top-1 | net_em |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **BETA-2b** | 0.0% | 0.5924 | 0.8422 | 0.5514 | 0.0909 | 0.5326 | 0.4053 | 0.0000 | 0.2963 | +0.0000 | +0.0000 | +0 |
| 1B-α (conservative veto) | 0.0% | 0.5903 | 0.8422 | 0.5470 | 0.0893 | 0.5322 | 0.4039 | 0.0000 | 0.3086 | -0.0043 | -0.0022 | -4 |
| 1F (combined strict gate, 1B primary) | 6.4% | 0.5903 | 0.8422 | 0.5092 | 0.0893 | 0.5322 | 0.4039 | 0.0123 | 0.3210 | -0.0422 | -0.0022 | -39 |
| 1F-on-BETA-2b (combined strict, no veto) | 6.4% | 0.5924 | 0.8422 | 0.5135 | 0.0909 | 0.5326 | 0.4053 | 0.0123 | 0.3086 | -0.0378 | +0.0000 | -35 |
| Combo (1B-α + 1F) | 6.4% | 0.5903 | 0.8422 | 0.5092 | 0.0893 | 0.5322 | 0.4039 | 0.0123 | 0.3210 | -0.0422 | -0.0022 | -39 |
| 1E (per-class threshold) | 27.1% | 0.5924 | 0.8422 | 0.4119 | 0.0909 | 0.5326 | 0.4053 | 0.1235 | 0.4053 | -0.1395 | +0.0000 | -129 |
| 1A-α (cross-mode disagree) | 13.5% | 0.5924 | 0.8422 | 0.5027 | 0.0909 | 0.5326 | 0.4053 | 0.0494 | 0.3395 | -0.0486 | +0.0000 | -45 |
| 1A-β (cross-mode pair emission) | 54.6% | 0.5924 | 0.8422 | 0.2465 | 0.0909 | 0.5326 | 0.4053 | 0.1852 | 0.4609 | -0.3049 | +0.0000 | -282 |
| 1A-δ (cross-mode strict) | 48.0% | 0.5924 | 0.8422 | 0.3027 | 0.0909 | 0.5326 | 0.4053 | 0.1728 | 0.4609 | -0.2486 | +0.0000 | -230 |
| 2C-α (calibrator disagreement) | 79.5% | 0.5924 | 0.8422 | 0.1286 | 0.0909 | 0.5326 | 0.4053 | 0.2840 | 0.5514 | -0.4227 | +0.0000 | -391 |
| 2A (LLM re-prompt overlay) | 5.6% | 0.5924 | 0.8422 | 0.5157 | 0.0909 | 0.5326 | 0.4053 | 0.0123 | 0.3086 | -0.0357 | +0.0000 | -33 |

### mdd_dsm5

| Policy | emit% | Top-1 | Top-3 | EM | mF1 | wF1 | Overall | mgEM | mgR | Δ EM | Δ Top-1 | net_em |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **BETA-2b** | 0.0% | 0.5795 | 0.8324 | 0.5351 | 0.0967 | 0.5116 | 0.3959 | 0.0000 | 0.3004 | +0.0000 | +0.0000 | +0 |
| 1B-α (conservative veto) | 0.0% | 0.5741 | 0.8324 | 0.5297 | 0.0808 | 0.5013 | 0.3854 | 0.0000 | 0.3066 | -0.0054 | -0.0054 | -5 |
| 1F (combined strict gate, 1B primary) | 7.8% | 0.5741 | 0.8324 | 0.4941 | 0.0808 | 0.5013 | 0.3854 | 0.0370 | 0.3251 | -0.0411 | -0.0054 | -38 |
| 1F-on-BETA-2b (combined strict, no veto) | 7.8% | 0.5795 | 0.8324 | 0.4995 | 0.0967 | 0.5116 | 0.3959 | 0.0370 | 0.3189 | -0.0357 | +0.0000 | -33 |
| Combo (1B-α + 1F) | 7.8% | 0.5741 | 0.8324 | 0.4941 | 0.0808 | 0.5013 | 0.3854 | 0.0370 | 0.3251 | -0.0411 | -0.0054 | -38 |
| 1E (per-class threshold) | 16.6% | 0.5795 | 0.8324 | 0.4432 | 0.0967 | 0.5116 | 0.3959 | 0.0494 | 0.3374 | -0.0919 | +0.0000 | -85 |
| 1A-α (cross-mode disagree) | 13.5% | 0.5795 | 0.8324 | 0.5027 | 0.0967 | 0.5116 | 0.3959 | 0.0494 | 0.3395 | -0.0324 | +0.0000 | -30 |
| 1A-β (cross-mode pair emission) | 60.2% | 0.5795 | 0.8324 | 0.2032 | 0.0967 | 0.5116 | 0.3959 | 0.1975 | 0.4938 | -0.3319 | +0.0000 | -307 |
| 1A-δ (cross-mode strict) | 48.3% | 0.5795 | 0.8324 | 0.2919 | 0.0967 | 0.5116 | 0.3959 | 0.1852 | 0.4671 | -0.2432 | +0.0000 | -225 |
| 2C-α (calibrator disagreement) | 76.8% | 0.5795 | 0.8324 | 0.1297 | 0.0967 | 0.5116 | 0.3959 | 0.2963 | 0.5453 | -0.4054 | +0.0000 | -375 |
| 2A (LLM re-prompt overlay) | 6.3% | 0.5795 | 0.8324 | 0.5059 | 0.0967 | 0.5116 | 0.3959 | 0.0370 | 0.3189 | -0.0292 | +0.0000 | -27 |

### mdd_both

| Policy | emit% | Top-1 | Top-3 | EM | mF1 | wF1 | Overall | mgEM | mgR | Δ EM | Δ Top-1 | net_em |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **BETA-2b** | 0.0% | 0.5924 | 0.8422 | 0.5514 | 0.0909 | 0.5326 | 0.4053 | 0.0000 | 0.2963 | +0.0000 | +0.0000 | +0 |
| 1B-α (conservative veto) | 0.0% | 0.5903 | 0.8422 | 0.5470 | 0.0893 | 0.5322 | 0.4039 | 0.0000 | 0.3086 | -0.0043 | -0.0022 | -4 |
| 1F (combined strict gate, 1B primary) | 6.4% | 0.5903 | 0.8422 | 0.5092 | 0.0893 | 0.5322 | 0.4039 | 0.0123 | 0.3210 | -0.0422 | -0.0022 | -39 |
| 1F-on-BETA-2b (combined strict, no veto) | 6.4% | 0.5924 | 0.8422 | 0.5135 | 0.0909 | 0.5326 | 0.4053 | 0.0123 | 0.3086 | -0.0378 | +0.0000 | -35 |
| Combo (1B-α + 1F) | 6.4% | 0.5903 | 0.8422 | 0.5092 | 0.0893 | 0.5322 | 0.4039 | 0.0123 | 0.3210 | -0.0422 | -0.0022 | -39 |
| 1E (per-class threshold) | 27.1% | 0.5924 | 0.8422 | 0.4119 | 0.0909 | 0.5326 | 0.4053 | 0.1235 | 0.4053 | -0.1395 | +0.0000 | -129 |
| 1A-α (cross-mode disagree) | 0.0% | 0.5924 | 0.8422 | 0.5514 | 0.0909 | 0.5326 | 0.4053 | 0.0000 | 0.2963 | +0.0000 | +0.0000 | +0 |
| 1A-β (cross-mode pair emission) | 69.2% | 0.5924 | 0.8422 | 0.1859 | 0.0909 | 0.5326 | 0.4053 | 0.2469 | 0.5267 | -0.3654 | +0.0000 | -338 |
| 1A-δ (cross-mode strict) | 60.3% | 0.5924 | 0.8422 | 0.2389 | 0.0909 | 0.5326 | 0.4053 | 0.2222 | 0.5144 | -0.3124 | +0.0000 | -289 |
| 2C-α (calibrator disagreement) | 79.5% | 0.5924 | 0.8422 | 0.1286 | 0.0909 | 0.5326 | 0.4053 | 0.2840 | 0.5514 | -0.4227 | +0.0000 | -391 |
| 2A (LLM re-prompt overlay) | 0.0% | 0.5924 | 0.8422 | 0.5514 | 0.0909 | 0.5326 | 0.4053 | 0.0000 | 0.2963 | +0.0000 | +0.0000 | +0 |

---

## 3. Per-policy summary across 6 modes

| Policy | modes EM ≥ baseline | modes EM > baseline | total net_em across 6 modes | aggregate ΔEM | aggregate Δmacro-F1 | verdict |
|---|:---:|:---:|---:|---:|---:|:---:|
| 1B-α (conservative veto) | 0/6 | 0/6 | -40 | -0.0411 | -0.0553 | RED |
| 1F (combined strict gate, 1B primary) | 0/6 | 0/6 | -272 | -0.2814 | -0.0553 | RED |
| 1F-on-BETA-2b (combined strict, no veto) | 0/6 | 0/6 | -232 | -0.2404 | +0.0000 | RED |
| Combo (1B-α + 1F) | 0/6 | 0/6 | -272 | -0.2814 | -0.0553 | RED |
| 1E (per-class threshold) | 0/6 | 0/6 | -565 | -0.5928 | +0.0000 | RED |
| 1A-α (cross-mode disagree) | 2/6 | 0/6 | -124 | -0.1301 | +0.0000 | RED |
| 1A-β (cross-mode pair emission) | 0/6 | 0/6 | -1513 | -1.5882 | +0.0000 | RED |
| 1A-δ (cross-mode strict) | 0/6 | 0/6 | -1078 | -1.1383 | +0.0000 | RED |
| 2C-α (calibrator disagreement) | 0/6 | 0/6 | -2054 | -2.1478 | +0.0000 | RED |
| 2A (LLM re-prompt overlay) | 2/6 | 0/6 | -144 | -0.1489 | +0.0000 | RED |

---

## 4. Multi-gold (mgEM) recovery — does any policy actually rescue size>=2 cases?

| Policy | lingxi_icd10 mgEM | lingxi_dsm5 mgEM | lingxi_both | mdd_icd10 | mdd_dsm5 | mdd_both | total mg cases recovered |
|---|---:|---:|---:|---:|---:|---:|---:|
| BETA-2b (baseline) | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| 1B-α (conservative veto) | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| 1F (combined strict gate, 1B primary) | 0.0116 | 0.1163 | 0.0116 | 0.0123 | 0.0370 | 0.0123 | 17 |
| 1F-on-BETA-2b (combined strict, no veto) | 0.0116 | 0.1163 | 0.0116 | 0.0123 | 0.0370 | 0.0123 | 17 |
| Combo (1B-α + 1F) | 0.0116 | 0.1163 | 0.0116 | 0.0123 | 0.0370 | 0.0123 | 17 |
| 1E (per-class threshold) | 0.0698 | 0.0233 | 0.0698 | 0.1235 | 0.0494 | 0.1235 | 38 |
| 1A-α (cross-mode disagree) | 0.0233 | 0.0233 | 0.0000 | 0.0494 | 0.0494 | 0.0000 | 12 |
| 1A-β (cross-mode pair emission) | 0.1512 | 0.1279 | 0.1512 | 0.1852 | 0.1975 | 0.2469 | 88 |
| 1A-δ (cross-mode strict) | 0.1279 | 0.1395 | 0.1395 | 0.1728 | 0.1852 | 0.2222 | 82 |
| 2C-α (calibrator disagreement) | 0.2791 | 0.3256 | 0.2791 | 0.2840 | 0.2963 | 0.2840 | 146 |
| 2A (LLM re-prompt overlay) | 0.0000 | 0.0814 | 0.0000 | 0.0123 | 0.0370 | 0.0000 | 11 |

Reference: BETA-2b mgEM = 0 always (single-label contract, never matches multi-gold sets).

---

## 5. Definitive ranking (best → worst aggregate ΔEM)

| Rank | Policy | aggregate ΔEM | aggregate Δmacro-F1 | total net_em | verdict |
|---:|---|---:|---:|---:|:---:|
| 1 | 1B-α (conservative veto) | -0.0411 | -0.0553 | -40 | RED |
| 2 | 1A-α (cross-mode disagree) | -0.1301 | +0.0000 | -124 | RED |
| 3 | 2A (LLM re-prompt overlay) | -0.1489 | +0.0000 | -144 | RED |
| 4 | 1F-on-BETA-2b (combined strict, no veto) | -0.2404 | +0.0000 | -232 | RED |
| 5 | 1F (combined strict gate, 1B primary) | -0.2814 | -0.0553 | -272 | RED |
| 6 | Combo (1B-α + 1F) | -0.2814 | -0.0553 | -272 | RED |
| 7 | 1E (per-class threshold) | -0.5928 | +0.0000 | -565 | RED |
| 8 | 1A-δ (cross-mode strict) | -1.1383 | +0.0000 | -1078 | RED |
| 9 | 1A-β (cross-mode pair emission) | -1.5882 | +0.0000 | -1513 | RED |
| 10 | 2C-α (calibrator disagreement) | -2.1478 | +0.0000 | -2054 | RED |

---

## 6. Verdict — is there ANY policy that improves over BETA-2b on aligned data?

**NO — all tested policies are RED on aligned source.** Every one has aggregate ΔEM < 0 OR fails the ≥2 modes ≥ baseline gate.

Implication: the multi-label gold ceiling on this dataset is structural at the ~9% level. Pure post-hoc gating over the existing BETA-2b decision_trace cannot close it without harming single-gold accuracy more than it helps. Any meaningful improvement requires either (a) modifying the LLM prompt itself (Tier 2B hierarchical), (b) adding a multi-label-specialized agent (Tier 4A), or (c) reframing the evaluation contract (Tier 4C).

---

## 7. Hard-constraint compliance

- ✅ No production code modified
- ✅ No commit, no push (audit uncommitted)
- ✅ No tag move
- ✅ No GPU run, no prediction regeneration
- ✅ Source = BETA-2b CPU projection (real pipeline intermediate signals, CPE-validated)
- ✅ Verdict driven by data, not pre-supposed
