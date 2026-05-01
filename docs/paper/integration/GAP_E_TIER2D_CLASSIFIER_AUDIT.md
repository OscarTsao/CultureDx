# Round 150 Tier 2D — Two-Stage Emission Classifier (Audit)

**Date:** 2026-04-30 23:08:43
**Branch:** feature/gap-e-beta2-implementation @ HEAD
**Status:** Sandbox audit. CPU-only. No commit, no tag.
**Elapsed:** 0.0 min

---
## 1. Feature engineering

Per-case features extracted from `decision_trace`:

- `primary_met_ratio`
- `rank2_met_ratio`
- `rank3_met_ratio`
- `met_gap_12`
- `primary_in_confirmed`
- `rank2_in_confirmed`
- `rank2_in_pair`
- `confirmed_count`
- `veto_applied`
- `diag_confidence`
- `n_ranked`
- `pc_F32`
- `pc_F33`
- `pc_F41`
- `pc_F42`
- `pc_F43`
- `pc_F45`
- `pc_F51`
- `pc_F98`
- `pc_Z71`
- `pc_F39`
- `pc_F20`
- `pc_F31`
- `pc_OTHER`
- `cross_mode_agree`

Plus `cross_mode_agree` (bool: ICD-10 primary == DSM-5 primary for same case).

---
## 2. Class imbalance

| Mode | train size | dev size | test size | pos_rate |
|---|---:|---:|---:|---:|
| lingxi_icd10 | 699 | 149 | 152 | 0.086 |
| lingxi_dsm5 | 699 | 149 | 152 | 0.086 |
| mdd_icd10 | 646 | 138 | 141 | 0.087 |
| mdd_dsm5 | 646 | 138 | 141 | 0.087 |

Handled via `class_weight` sweep: balanced and explicit ratios up to {0:1, 1:10}.

---
## 3. Hyperparameter sweep (top 5 per mode)

### lingxi_icd10

| cw | C | solver | dev_P | dev_R | dev_F1 | test_F1 |
|---|---:|---|---:|---:|---:|---:|
| {0: 1, 1: 10} | 0.01 | lbfgs | 0.093 | 0.333 | 0.145 | 0.162 |
| {0: 1, 1: 10} | 1.0 | liblinear | 0.091 | 0.333 | 0.143 | 0.162 |
| {0: 1, 1: 10} | 1.0 | lbfgs | 0.091 | 0.333 | 0.143 | 0.162 |
| {0: 1, 1: 10} | 10.0 | liblinear | 0.091 | 0.333 | 0.143 | 0.162 |
| {0: 1, 1: 10} | 10.0 | lbfgs | 0.091 | 0.333 | 0.143 | 0.162 |

### lingxi_dsm5

| cw | C | solver | dev_P | dev_R | dev_F1 | test_F1 |
|---|---:|---|---:|---:|---:|---:|
| {0: 1, 1: 10} | 0.01 | liblinear | 0.118 | 0.833 | 0.206 | 0.144 |
| {0: 1, 1: 10} | 10.0 | liblinear | 0.110 | 0.667 | 0.188 | 0.161 |
| {0: 1, 1: 10} | 10.0 | lbfgs | 0.110 | 0.667 | 0.188 | 0.161 |
| {0: 1, 1: 10} | 0.01 | lbfgs | 0.111 | 0.583 | 0.187 | 0.145 |
| {0: 1, 1: 10} | 0.1 | liblinear | 0.108 | 0.667 | 0.186 | 0.157 |

### mdd_icd10

| cw | C | solver | dev_P | dev_R | dev_F1 | test_F1 |
|---|---:|---|---:|---:|---:|---:|
| {0: 1, 1: 10} | 0.01 | lbfgs | 0.159 | 0.583 | 0.250 | 0.172 |
| balanced | 0.1 | liblinear | 0.148 | 0.667 | 0.242 | 0.219 |
| {0: 1, 1: 10} | 10.0 | liblinear | 0.143 | 0.667 | 0.235 | 0.176 |
| {0: 1, 1: 10} | 10.0 | lbfgs | 0.143 | 0.667 | 0.235 | 0.176 |
| balanced | 1.0 | liblinear | 0.140 | 0.667 | 0.232 | 0.222 |

### mdd_dsm5

| cw | C | solver | dev_P | dev_R | dev_F1 | test_F1 |
|---|---:|---|---:|---:|---:|---:|
| {0: 1, 1: 10} | 1.0 | liblinear | 0.122 | 0.500 | 0.197 | 0.138 |
| {0: 1, 1: 10} | 1.0 | lbfgs | 0.122 | 0.500 | 0.197 | 0.138 |
| {0: 1, 1: 10} | 10.0 | liblinear | 0.122 | 0.500 | 0.197 | 0.138 |
| {0: 1, 1: 10} | 10.0 | lbfgs | 0.122 | 0.500 | 0.197 | 0.138 |
| balanced | 0.1 | liblinear | 0.122 | 0.500 | 0.197 | 0.159 |

---
## 4. Best model per mode

| Mode | cw | C | solver | dev_F1 | test_F1 |
|---|---|---:|---|---:|---:|
| lingxi_icd10 | {0: 1, 1: 1} | 0.01 | liblinear | 0.000 | 0.000 |
| lingxi_dsm5 | {0: 1, 1: 1} | 0.01 | liblinear | 0.000 | 0.000 |
| mdd_icd10 | {0: 1, 1: 1} | 0.01 | liblinear | 0.000 | 0.000 |
| mdd_dsm5 | {0: 1, 1: 1} | 0.01 | liblinear | 0.000 | 0.000 |

---
## 5. Final policy metrics — classifier-gated emission vs BETA-2b primary-only

| Mode | Policy | emit% | EM | F1 | P | R | sgEM | mgEM | mgR | sizeM |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| lingxi_icd10 | BETA-2b | 0.0% | 0.452 | 0.488 | 0.507 | 0.479 | 0.495 | 0.000 | 0.314 | 0.914 |
| lingxi_icd10 | **2D classifier** | 0.0% | 0.452 | 0.488 | 0.507 | 0.479 | 0.495 | 0.000 | 0.314 | 0.914 |
| lingxi_dsm5 | BETA-2b | 0.0% | 0.419 | 0.453 | 0.471 | 0.445 | 0.458 | 0.000 | 0.297 | 0.914 |
| lingxi_dsm5 | **2D classifier** | 0.0% | 0.419 | 0.453 | 0.471 | 0.445 | 0.458 | 0.000 | 0.297 | 0.914 |
| mdd_icd10 | BETA-2b | 0.0% | 0.542 | 0.578 | 0.597 | 0.569 | 0.594 | 0.000 | 0.309 | 0.912 |
| mdd_icd10 | **2D classifier** | 0.0% | 0.542 | 0.578 | 0.597 | 0.569 | 0.594 | 0.000 | 0.309 | 0.912 |
| mdd_dsm5 | BETA-2b | 0.0% | 0.528 | 0.563 | 0.581 | 0.554 | 0.578 | 0.000 | 0.300 | 0.912 |
| mdd_dsm5 | **2D classifier** | 0.0% | 0.528 | 0.563 | 0.581 | 0.554 | 0.578 | 0.000 | 0.300 | 0.912 |

---
## 6. Comparison vs sandbox candidates

Sandbox numbers per `ROUND150_SANDBOX_AUDIT.md`:

| Mode | BETA-2b F1 | 1B-α F1 | Combo F1 | 2D classifier F1 |
|---|---:|---:|---:|---:|
| lingxi_icd10 | 0.488 | 0.493 | 0.493 | **0.488** |
| lingxi_dsm5 | 0.453 | 0.504 | 0.504 | **0.453** |
| mdd_icd10 | 0.578 | 0.583 | 0.588 | **0.578** |
| mdd_dsm5 | 0.563 | 0.566 | 0.566 | **0.563** |

---
## 7. Feature importance (top 5 per mode)

### lingxi_icd10

| Feature | Coefficient |
|---|---:|
| `pc_F39` | +0.050 |
| `pc_F20` | -0.037 |
| `rank2_in_pair` | +0.033 |
| `n_ranked` | +0.031 |
| `confirmed_count` | +0.026 |

### lingxi_dsm5

| Feature | Coefficient |
|---|---:|
| `n_ranked` | -0.065 |
| `rank2_in_confirmed` | +0.041 |
| `pc_F39` | +0.040 |
| `veto_applied` | -0.033 |
| `rank2_in_pair` | +0.031 |

### mdd_icd10

| Feature | Coefficient |
|---|---:|
| `pc_F20` | +0.106 |
| `rank2_in_pair` | +0.048 |
| `pc_F31` | -0.041 |
| `pc_F42` | +0.038 |
| `cross_mode_agree` | -0.035 |

### mdd_dsm5

| Feature | Coefficient |
|---|---:|
| `pc_F20` | +0.085 |
| `rank3_met_ratio` | -0.061 |
| `primary_met_ratio` | +0.045 |
| `met_gap_12` | +0.044 |
| `confirmed_count` | +0.044 |

---
## 8. Verdict

**Hand-crafted gates (1B-α / Combo) outperform learned classifier.** Stick with sandbox candidates.

Caveat: train/dev/test splits within each pilot dataset (70/15/15 stratified). May not generalize to fresh canonical run.

---
## 9. Files NOT modified

- `src/culturedx/modes/hied.py` — UNTOUCHED
- `paper-integration-v0.1` tag — UNTOUCHED
- All committed predictions — UNTOUCHED (read-only)
- Manuscript drafts — UNTOUCHED
