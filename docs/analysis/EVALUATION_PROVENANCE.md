# Evaluation Provenance — CultureDx Paper Submission (v4)

**Status**: 🟡 CANDIDATE VALUES until P0 metric regeneration commits land. Will become canonical after Step 2 of `02_REGENERATE_AND_RECONCILE.md` passes.

**Target location**: `docs/analysis/EVALUATION_PROVENANCE.md`

**Versioning rule**: Any value labeled "candidate" must be replaced with commit-hash-backed canonical value before paper submission.

---

## 1. Datasets and splits

### 1.1 LingxiDiag-16K — primary benchmark

- **Source**: [TODO: publication, doi, URL]
- **Total**: 16,000 synthetic Chinese psychiatric dialogues
- **Splits**:
  - `train`: [TODO]
  - `dev_hpo`: [TODO] (stacker hyperparameter tuning)
  - `test_final`: **N=1000**, all main metrics
- **Manifest source-of-truth**: `results/dual_standard_full/lingxidiag16k/mode_icd10/pilot_icd10/case_selection.json`
- **Manifest fingerprint**: `59173340f1fa156e`
- **case_ids SHA256**: [TODO from consistency report]
- **Stacker test_final overlap**: 1000/1000 with dual-standard (verified)

### 1.2 MDD-5k — external validation

N=925 (post-filtering). Manifest: [TODO]

---

## 2. Label taxonomy (FIXED)

```python
PAPER_12_CLASSES = ["F20", "F31", "F32", "F39", "F41", "F42", "F43",
                    "F45", "F51", "F98", "Z71", "Others"]
```

**F33 NOT included**. F33 collapses to "Others" via `to_paper_parent`. This is paper-original taxonomy; not negotiable.

DSM-5 ontology maintains F33 stub for system extensibility, but it does not appear in 12-class evaluation. F33 cases: 0/1000 in LingxiDiag, 2/925 in MDD-5k.

### 2.1 Paper-parent collapse rules (verified by `tests/test_evaluation_contract.py`)

| Input | Output |
|---|---|
| F32, F32.x | F32 |
| **F33, F33.x** | **Others** (NOT in PAPER_12_CLASSES) |
| F41, F41.x including F41.2 | F41 |
| F43, F43.x | F43 |
| Z71.x | Z71 |
| F34, F70, F90, G47 | Others (parents not in 12-class) |
| `""`, None | Others |

Note: `to_paper_parent(None)` requires explicit None handling — verify before unit test runs.

---

## 3. Metric contract (CANONICAL — locked by `compute_table4_metrics_v2`)

Per GPT round 5 review, evaluation uses FOUR separate prediction views per metric family:

### 3.1 Top-1 (12-class)

```python
top1 = sum(1 for gold, primary_pred in zip(gold_multilabel, primary_predictions)
           if primary_pred and primary_pred in gold) / n
```

- **Prediction source**: `primary_diagnosis` (paper-parent normalized)
- **Gold source**: multilabel parent set
- **Canonical field**: `metrics.json → table4 → 12class_Top1`

### 3.2 Top-3 (12-class)

```python
# CRITICAL: ensures Top-1 ⊆ Top-3 invariant
canonical_top3 = [primary] + [c for c in ranked if c != primary]
canonical_top3 = canonical_top3[:3]

top3 = sum(1 for gold, top3_list in zip(gold_multilabel, canonical_top3_lists)
           if set(top3_list) & set(gold)) / n
```

- **Prediction source**: `[primary_diagnosis] + (ranked_codes - {primary})[:2]` (paper-parent)
- **Gold source**: multilabel parent set
- **NOT** `[primary] + comorbid_diagnoses` — that list is threshold-gated and typically length 1

### 3.3 F1 / Exact Match (12-class multilabel)

```python
# Multilabel F1 over PAPER_12_CLASSES
mlb = MultiLabelBinarizer(classes=PAPER_12_CLASSES)
y_true = mlb.fit_transform(gold_multilabel)
y_pred = mlb.transform(multilabel_predictions)
```

- **Prediction source**: `[primary] + [comorbid where conf >= 0.3]` (paper-parent multilabel)
- **NOT** ranked top-3 (would predict all classes, breaks F1)

### 3.4 2-class

```python
gold_2c = classify_2class_from_raw(diagnosis_code_full)
# F41.2 → None (excluded)
# F32 + F41 (comorbid) → None (excluded)
pred_2c = classify_2class_prediction(primary_diagnosis)
```

- **Gold source**: raw `DiagnosisCode` (preserves F41.2 for exclusion)
- **Pred source**: primary diagnosis
- **Expected n**: **473** (after F41.2 + comorbid exclusion). NOT 696 (parent-collapsed gold bug).

### 3.5 4-class

```python
gold_4c = classify_4class_from_raw(diagnosis_code_full)
# F41.2 → "Mixed"
# F32 + F41 comorbid → "Mixed"
# Pure F32 → "Depression"
# Pure F41 → "Anxiety"
# Other → "Others"
```

- **Gold source**: raw `DiagnosisCode`
- **Pred source**: primary + raw_pred_codes for F41.2 detection

### 3.6 Overall

```python
Overall = mean(non-_n metric values from table4)
```

**MUST be recomputed after any other metric changes**. v3 mistake: mixed post-fix Top-3 with pre-fix Overall.

### 3.7 Top-1 naming hierarchy

Multiple Top-1 fields exist for different semantic purposes:

| Field | Semantics | Use in paper? |
|---|---|---|
| **`table4.12class_Top1`** | **paper-canonical multilabel** | **YES — only this value** |
| `diagnostics_internal.diagnosis.top1_accuracy` | legacy internal metric | NO |
| `diagnostics_internal.pilot_comparison_top1` | parent-vs-first-gold | NO |

Sanity check enforces: `paper_canonical_top1 == table4.12class_Top1`. **Does NOT** force all Top-1 fields to match (they have different semantics).

### 3.8 Non-inferiority margin

Pre-specified before metric regeneration: **±0.05 absolute (5pp)**.

Parity claim is supported iff 95% bootstrap CI of (our_metric − baseline_metric) ⊆ [−0.05, +0.05].

---

## 4. Bootstrap and tests

- 1000 resamples, seed 20260420, 95% percentile interval
- McNemar with continuity correction, p < 0.05 threshold
- Bias asymmetry: ratio with `max(., 1)` denominator protection

---

## 5. Systems compared

| System | Branch | Architecture |
|---|---|---|
| TF-IDF+LR (paper) | — | published |
| TF-IDF+LR (ours) | clean/v2.5 | reproduced — 0.604 vs paper 0.496, 10.6pp gap unexplained |
| Single LLM | main-v2.4 | Qwen3-32B-AWQ direct |
| MAS-only (DtV) | main-v2.4 | HiED multi-agent |
| Stacker LR | clean/v2.5 | MAS+TFIDF → LR |
| Stacker LGBM | clean/v2.5 | MAS+TFIDF → LGBM |
| ICD-10 mode | main-v2.4 | HiED with ICD-10 reasoning |
| DSM-5 mode | main-v2.4 | HiED with DSM-5 v0 reasoning |
| Both mode | main-v2.4 | ICD-10 primary + DSM-5 sidecar |

### 5.1 TF-IDF reproduction gap (DOCUMENTED CAVEAT)

Our TF-IDF: 0.604. Paper TF-IDF: 0.496. Gap: 10.6pp unexplained. Candidate causes [TODO investigate]: tokenization, n-gram, min_df/max_df, sublinear_tf, LR hyperparameters.

Paper claim qualified accordingly: parity is against our (stronger) reproduced TF-IDF, not paper's.

---

## 6. Canonical results (CANDIDATE — finalized after P0 commits)

### 6.1 LingxiDiag-16K test_final (N=1000)

| System | 2c Acc | 4c Acc | 12c Top-1 | 12c Top-3 | F1_m | F1_w | Overall |
|---|---:|---:|---:|---:|---:|---:|---:|
| Paper TF-IDF | .753 | .476 | .496 | .645 | .295 | .520 | .533 |
| Paper best LLM | .841 | .470 | .487 | .574 | .197 | .439 | .521 |
| Our TF-IDF | [P0] | [P0] | .604 | [P0] | .373 | .602 | [P0] |
| MAS-only | [P0] | [P0] | .516 | [P0] | .171 | .447 | [P0] |
| **Stacker LGBM** | [P0] | [P0] | [P0] | [P0] | [P0] | [P0] | [P0] |
| **Stacker LR** | [P0] | [P0] | [P0] | [P0] | [P0] | [P0] | [P0] |

`[P0]` = candidate value, finalized after evaluation contract repair commit.

**Pre-P0 candidate values (NOT to be cited yet)**:
- Stacker LGBM: Top-1 candidate 0.612, Top-3 candidate 0.925, F1_m candidate 0.334
- Stacker LR: Top-1 candidate 0.538, Top-3 candidate 0.887, F1_m candidate 0.360
- 2-class n MUST become 473 (F41.2 excluded)

**Pre-P0 audit values (DEPRECATED after P0)**:
- Stacker LGBM Top-1 0.605 (single-label, audit) → 0.612 (multilabel, post-P0)

### 6.2 MDD-5k (N=925) — UNCHANGED

| System | Top-1 | F41→F32 | F32→F41 | Asymmetry |
|---|---:|---:|---:|---:|
| Single LLM | .523 | 189 | 1 | 189× |
| MAS (T1) | .558 | 152 | 17 | 8.94× |
| MAS + R6v2 | .571 | 145 | 26 | 5.58× |

### 6.3 Dual-standard (N=1000)

| Mode | Top-1 | Top-3 | F1_m | F1_w | Overall |
|---|---:|---:|---:|---:|---:|
| ICD-10 | 0.507 | [P0] (candidate 0.799) | 0.199 | 0.457 | [P0] |
| DSM-5 | 0.471 | [P0] | 0.188 | 0.421 | [P0] |
| Both | 0.507 | [P0] (= ICD-10) | 0.199 | 0.457 | [P0] |

Pairwise agreement (paper-parent):
- ICD-10 vs DSM-5: 0.749 (251 disagree)
- ICD-10 vs Both: 1.000 (Both = ICD-10 by architecture)
- DSM-5 vs Both: 0.749

### 6.4 Disagreement-as-triage

See `docs/analysis/DISAGREEMENT_AS_TRIAGE_2026_04_25.md`.

---

## 7. Reproducibility checklist

- [x] PAPER_12_CLASSES tested in `test_evaluation_contract.py::TestPaperTaxonomy`
- [x] to_paper_parent unit tests including F33 → Others
- [x] F41.2 exclusion test
- [x] Top-1 ⊆ Top-3 invariant test
- [ ] Case manifest SHA256 in consistency report [POST-P0]
- [x] Top-K source documented (ranked vs threshold-gated)
- [x] F1 source documented (multilabel)
- [x] 2-class source documented (raw codes)
- [x] Bootstrap config documented
- [ ] TF-IDF preprocessing documented [TODO Appendix B]
- [x] Non-inferiority margin pre-specified (±5pp)
- [ ] All sanity checks committed [POST-P0]
- [ ] metric_consistency_report.json committed [POST-P0]
- [ ] AUDIT_RECONCILIATION_2026_04_25.md committed [POST-P0]

---

## 8. Known limitations

### 8.1 Synthetic-only datasets
LingxiDiag and MDD-5k are synthetic. Chang Gung clinical validation pending IRB.

### 8.2 DSM-5 v0 criteria (UNVERIFIED_LLM_DRAFT)
All DSM-5 stubs LLM-drafted. AIDA-Path structural alignment for 5 overlapping disorders pending. Clinician review pending IRB.

### 8.3 F42 collapse in DSM-5 mode
Recall 12% vs ICD-10 52%. Trace shows `all_required: true` + criterion D (exclusion) marked `insufficient_evidence` in 80% of F42-gold cases. Documented in `docs/analysis/F42_DSM5_COLLAPSE_TRACE.md`. **Not fixed for current submission to avoid test-set tuning.**

### 8.4 Class coverage limits
F31, F43, Z71, F98, Others all near-zero recall in both modes (14.3% of test_final). Hard ceiling on aggregate Top-1.

### 8.5 Both-mode is not an ensemble
Both = ICD-10 primary (1000/1000 match with ICD-10 mode). DSM-5 is sidecar evidence.

### 8.6 Stacker feature contribution
TF-IDF 88% / MAS 12% (LGBM importance). Accuracy from supervised features.

### 8.7 Confidence-gated ensemble = null
Selected rule = tfidf_only. McNemar p=1.0. Reported transparently.

### 8.8 Retracted experiments
WS-C Exp 1, Exp 2 documented in `docs/RETRACTION_NOTICE_2026_04_22.md`.

### 8.9 Evaluation contract repair history
This document supersedes pre-2026-04-25 metric values. See `AUDIT_RECONCILIATION_2026_04_25.md` for change trail.

---

## 9. Version control

- v1 audit (2026-04-22): captured then-current numbers
- v2-v3 GPT review rounds: identified contract bugs
- v4 P0 fix (this commit, [TODO hash]): refactored to compute_table4_metrics_v2
- This document v4: locks contract semantics

After P0 commits land, this document becomes canonical reference for paper.

---

**Last updated**: 2026-04-25 (pre-P0 candidate)
**Authors**: YuNing
**Reviewed by**: GPT-5.5-pro rounds 1-5
**Next milestone**: Replace [P0] markers with commit-hash-backed values
