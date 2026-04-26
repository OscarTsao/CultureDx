# Evaluation Provenance - CultureDx Paper Submission (v5)

**Status**: CANONICAL as of P0 commits `914381b` (clean/v2.5) and `c7f8fa0` (main-v2.4).
**Source of truth**: `results/analysis/metric_consistency_report.json`
**Audit reconciliation**: `docs/audit/AUDIT_RECONCILIATION_2026_04_25.md`

---

## 1. Datasets and Splits

### 1.1 LingxiDiag-16K - Primary Benchmark

- **Source**: LingxiDiag-16K local checkout at `data/raw/lingxidiag16k`; upstream references are listed in `README.md`.
- **Local raw files**:
  - `train`: `data/raw/lingxidiag16k/data/train-00000-of-00001.parquet`, N=14000.
  - `test_final`: `data/raw/lingxidiag16k/data/validation-00000-of-00001.parquet`, N=1000.
  - `dev_hpo`: stacker tuning split described by `results/ensemble/split.json` when present; final paper metrics below use held-out `test_final` only.
- **Manifest source of truth**: `results/dual_standard_full/lingxidiag16k/mode_icd10/pilot_icd10/case_selection.json`
- **Manifest fingerprint**: `59173340f1fa156e`
- **case_ids SHA256**: `2c07267cecbb66a3d1e02394f547f973de5e6f13f5ff014fe244052150245d90`
- **Stacker test_final overlap**: 1000/1000 with dual-standard cases.

### 1.2 MDD-5k - External Validation

- **Source**: local raw label directory `data/raw/mdd5k_repo/Label`.
- **Post-filtering N**: 925.
- **Manifest source of truth**: `results/dual_standard_full/mdd5k/mode_icd10/pilot_icd10/case_selection.json`
- **Case order fingerprint**: `87a7bee4e0b36bb9`
- **case_ids SHA256**: `72512b5448eb8a93245be1f619114eda8c9cd8f1db7f3b5a9cd2e180844a75de`
- **Raw ICD_Code coverage**: 925/925 across all dual-standard modes.

---

## 2. Label Taxonomy

```python
PAPER_12_CLASSES = ["F20", "F31", "F32", "F39", "F41", "F42", "F43",
                    "F45", "F51", "F98", "Z71", "Others"]
```

F33 is not included. F33 collapses to `Others` via `to_paper_parent`. This is
the paper-original taxonomy and is locked by `tests/test_evaluation_contract.py`.
DSM-5 ontology keeps an F33 stub for system extensibility, but it is not a
12-class evaluation label. F33 cases: 0/1000 in LingxiDiag, 2/925 in MDD-5k.

### 2.1 Paper-Parent Collapse Rules

| Input | Output |
|---|---|
| F32, F32.x | F32 |
| F33, F33.x | Others |
| F41, F41.x including F41.2 | F41 |
| F43, F43.x | F43 |
| Z71.x | Z71 |
| F34, F70, F90, G47 | Others |
| `""`, None | Others |

---

## 3. Metric Contract

Evaluation uses four separate prediction views per metric family through
`compute_table4_metrics_v2`.

### 3.1 Top-1 (12-Class)

- **Prediction source**: `primary_diagnosis` normalized to paper-parent.
- **Gold source**: multilabel paper-parent gold set.
- **Canonical field**: `metrics.json -> table4 -> 12class_Top1`.

### 3.2 Top-3 (12-Class)

Top-3 uses the ranked diagnostic view, canonicalized as:

```python
canonical_top3 = [primary] + [c for c in ranked if c != primary]
canonical_top3 = canonical_top3[:3]
```

- **Prediction source**: `[primary_diagnosis] + (ranked_codes - {primary})[:2]`.
- **Gold source**: multilabel paper-parent gold set.
- **Important exclusion**: not `[primary] + comorbid_diagnoses`, which is threshold-gated and usually too short.

### 3.3 F1 / Exact Match (12-Class Multilabel)

- **Prediction source**: `primary + threshold-gated comorbid_diagnoses`.
- **Gold source**: multilabel paper-parent gold set.
- **Important exclusion**: not ranked Top-3, because that would predict all shortlist entries.

### 3.4 2-Class

- **Gold source**: raw `DiagnosisCode` or raw MDD-5k `ICD_Code`, preserving F41.2.
- **Pred source**: primary diagnosis.
- **LingxiDiag expected n**: 473 after F41.2 and mixed F32/F41 exclusion.
- **MDD-5k expected n**: 490 after F41.2 and mixed F32/F41 exclusion.

### 3.5 4-Class

- **Gold source**: raw code.
- **Pred source**: primary plus raw predicted codes for F41.2 detection.
- **Mapping**:
  - F41.2 or F32+F41 comorbid -> Mixed
  - Pure F32 -> Depression
  - Pure F41 -> Anxiety
  - Other -> Others

### 3.6 Overall

`Overall` is the mean of all non-`_n` Table 4 metric values and must be
recomputed after any metric changes.

### 3.7 Top-1 Naming Hierarchy

| Field | Semantics | Use in paper? |
|---|---|---|
| `table4.12class_Top1` | paper-canonical multilabel | Yes |
| `diagnostics_internal.diagnosis.top1_accuracy` | legacy internal metric | No |
| `diagnostics_internal.pilot_comparison_top1` | parent-vs-first-gold | No |

### 3.8 Non-Inferiority Margin

Pre-specified margin: +/-0.05 absolute (5pp). Parity is supported when the
95% bootstrap CI of `our_metric - baseline_metric` lies within that margin.

---

## 4. Bootstrap and Tests

- Bootstrap: 1000 resamples, seed 20260420, 95% percentile interval.
- McNemar: continuity correction, p < 0.05 threshold.
- Bias asymmetry: ratio with `max(., 1)` denominator protection.
- Contract tests: `uv run pytest tests/test_evaluation_contract.py -v`.

---

## 5. Systems Compared

| System | Branch | Architecture |
|---|---|---|
| TF-IDF+LR (paper) | external | published baseline |
| TF-IDF+LR (ours) | clean/v2.5 | reproduced baseline |
| Single LLM | main-v2.4 | Qwen3-32B-AWQ direct |
| MAS-only (DtV) | main-v2.4 | HiED multi-agent |
| Stacker LR | clean/v2.5 | MAS + TF-IDF -> LR |
| Stacker LGBM | clean/v2.5 | MAS + TF-IDF -> LGBM |
| ICD-10 mode | main-v2.4 | HiED with ICD-10 reasoning |
| DSM-5 mode | main-v2.4 | HiED with DSM-5 v0 reasoning |
| Both mode | main-v2.4 | ICD-10 primary + DSM-5 sidecar |

### 5.1 TF-IDF Reproduction Gap

Our reproduced TF-IDF Top-1 is 0.604 to 0.611 depending on the frozen stacker
evaluation artifact; the paper TF-IDF Top-1 is 0.496. The gap is disclosed.
Candidate drivers are tokenization, char n-grams, `min_df`/`max_df`,
`sublinear_tf`, logistic-regression hyperparameters, and split differences.
Appendix B should cite `scripts/train_tfidf_baseline.py` and
`docs/analysis/AUDIT_REPORT_2026_04_22.md`.

---

## 6. Canonical Results

### 6.1 LingxiDiag-16K `test_final` (N=1000)

| System | 2c Acc | 4c Acc | 12c Top-1 | 12c Top-3 | F1_m | F1_w | Overall |
|---|---:|---:|---:|---:|---:|---:|---:|
| Paper TF-IDF | .753 | .476 | .496 | .645 | .295 | .520 | .533 |
| Paper best LLM | .841 | .470 | .487 | .574 | .197 | .439 | .521 |
| Our TF-IDF | not v4-finalized | not v4-finalized | .604-.611 | not v4-finalized | .373 | .602 | not v4-finalized |
| MAS-only | not v4-finalized | not v4-finalized | .516 | not v4-finalized | .171 | .447 | not v4-finalized |
| **Stacker LGBM** | **.753** | **.546** | **.612** | **.925** | **.334** | **.573** | **.6166** |
| **Stacker LR** | **.619** | **.538** | **.538** | **.887** | **.360** | **.558** | **.5722** |

Stacker LGBM matches our reproduced TF-IDF on Top-1 within the pre-specified
+/-5pp non-inferiority margin. MAS-only and TF-IDF rows are retained for
context but are not the commit-backed v4 Table 4 source rows.

### 6.2 MDD-5k Bias Robustness (N=925)

| System | Top-1 | F41 -> F32 | F32 -> F41 | Asymmetry |
|---|---:|---:|---:|---:|
| Single LLM | .523 | 189 | 1 | 189x |
| MAS (T1) | .558 | 152 | 17 | 8.94x |
| MAS + R6v2 | .571 | 145 | 26 | 5.58x |

### 6.3 Dual-Standard LingxiDiag (N=1000) - Post-v4 Contract

| Mode | 12c Top-1 | 12c Top-3 | F1_m | F1_w | 2c Acc | 4c Acc | Overall |
|---|---:|---:|---:|---:|---:|---:|---:|
| ICD-10 | 0.507 | 0.800 | 0.199 | 0.457 | 0.778 | 0.447 | 0.5145 |
| DSM-5 | 0.471 | 0.803 | 0.188 | 0.421 | 0.767 | 0.476 | 0.5065 |
| Both | 0.507 | 0.800 | 0.199 | 0.457 | 0.778 | 0.447 | 0.5145 |

Pairwise agreement (paper-parent):

- ICD-10 vs DSM-5: 0.749 (251 disagree)
- ICD-10 vs Both: 1.000 (Both = ICD-10 by architecture, 1000/1000 match)
- DSM-5 vs Both: 0.749

### 6.4 Dual-Standard MDD-5k (N=925) - Post-v4 Contract

| Mode | 12c Top-1 | 12c Top-3 | F1_m | F1_w | 2c Acc | 4c Acc | Overall |
|---|---:|---:|---:|---:|---:|---:|---:|
| ICD-10 | 0.597 | 0.853 | 0.197 | 0.514 | 0.890 | 0.444 | 0.566 |
| DSM-5 | 0.581 | 0.842 | 0.230 | 0.526 | 0.912 | 0.520 | 0.584 |
| Both | 0.597 | 0.853 | 0.197 | 0.514 | 0.890 | 0.444 | 0.566 |

Dual-standard evaluation showed dataset-dependent metric trade-offs: DSM-5 v0
was weaker than ICD-10 on Top-1 in both datasets and weaker on Top-3 on MDD-5k,
but achieved higher F1_macro, weighted-F1, binary accuracy, four-class accuracy,
and Overall on MDD-5k. We interpret this as standard-sensitive diagnostic
structure under distribution shift, not as DSM-5 clinical validation.

Both = ICD-10 is confirmed at MDD-5k scale (925/925 match). 2class_n = 490.

### 6.5 Disagreement-as-Triage

Canonical analysis: `docs/analysis/DISAGREEMENT_AS_TRIAGE_2026_04_25.md` when
present, with fallback narrative in `docs/analysis/DISAGREEMENT_AS_TRIAGE.md`.

---

## 7. Reproducibility Checklist

- [x] PAPER_12_CLASSES tested in `test_evaluation_contract.py::TestPaperTaxonomy`
- [x] `to_paper_parent` unit tests include F33 -> Others
- [x] F41.2 exclusion test
- [x] Top-1 subset of Top-3 invariant test
- [x] Case manifest SHA256 in `metric_consistency_report.json`: `2c07267cecbb66a3d1e02394f547f973de5e6f13f5ff014fe244052150245d90`
- [x] MDD-5k case manifest SHA256 in `metric_consistency_report.json`: `72512b5448eb8a93245be1f619114eda8c9cd8f1db7f3b5a9cd2e180844a75de`
- [x] Top-K source documented (ranked vs threshold-gated)
- [x] F1 source documented (multilabel)
- [x] 2-class source documented (raw codes)
- [x] Bootstrap config documented
- [x] TF-IDF preprocessing documented in `scripts/train_tfidf_baseline.py` and audit notes
- [x] Non-inferiority margin pre-specified (+/-5pp)
- [x] All v4 sanity checks committed in `results/analysis/metric_consistency_report.json`
- [x] `metric_consistency_report.json` committed
- [x] `docs/audit/AUDIT_RECONCILIATION_2026_04_25.md` added by artifact cleanup v6.1

---

## 8. Known Limitations

### 8.1 Synthetic-Only Datasets

LingxiDiag and MDD-5k are synthetic. Chang Gung clinical validation is pending
IRB.

### 8.2 DSM-5 v0 Criteria

All DSM-5 stubs are LLM-drafted with `UNVERIFIED_LLM_DRAFT` status. AIDA-Path
structural alignment for 5 overlapping disorders and clinician review are
pending.

### 8.3 F42 Collapse in DSM-5 Mode

Recall is 12% vs ICD-10 52% on LingxiDiag. Trace shows `all_required: true`
plus criterion D exclusion marked `insufficient_evidence` in 80% of F42-gold
cases. Documented in `docs/limitations/F42_DSM5_COLLAPSE_2026_04_25.md`. This
is not fixed for the current submission to avoid test-set tuning.

### 8.4 Class Coverage Limits

F31, F43, Z71, F98, and Others have near-zero recall in both modes on
LingxiDiag test_final, representing 14.3% of cases and placing a hard ceiling
on aggregate Top-1.

### 8.5 Both-Mode Is Not an Ensemble

Both = ICD-10 primary on 1925/1925 cases across LingxiDiag and MDD-5k. DSM-5 is
sidecar evidence.

### 8.6 Stacker Feature Contribution

TF-IDF contributes 88.1% and MAS contributes 11.9% by LGBM importance. Accuracy
mostly comes from supervised features.

### 8.7 Confidence-Gated Ensemble Is Null

Selected rule = `tfidf_only`. McNemar p = 1.0. This is reported as a negative
result.

### 8.8 Retracted Experiments

WS-C Exp 1 and Exp 2 are documented in `docs/RETRACTION_NOTICE_2026_04_22.md`.

### 8.9 Evaluation Contract Repair History

This document supersedes pre-2026-04-25 metric values. See
`docs/audit/AUDIT_RECONCILIATION_2026_04_25.md` for the change trail.

---

## 9. Version Control

- v1 audit (2026-04-22): captured then-current numbers.
- v2-v3 GPT review rounds: identified contract bugs.
- v4 P0 fix: refactored to `compute_table4_metrics_v2`.
- v5 cleanup: removes candidate placeholders, fixes F42 path, and links audit reconciliation.

---

**Last updated**: 2026-04-26 (post-P0 canonical)
**P0 commits**: `914381b` (clean/v2.5) + `c7f8fa0` (main-v2.4)
**MDD-5k benchmark commit**: `3a2d6d5` (main-v2.4)
**Cleanup**: artifact cleanup v6.1
