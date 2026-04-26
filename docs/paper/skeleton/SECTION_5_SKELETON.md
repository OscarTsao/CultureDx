# CultureDx Paper — Section 5 Skeleton

**Format**: (b) section-by-section with paste markers + Allowed/Forbidden wording guards
**Status**: skeleton ONLY (no prose). Sync commit landed. Use `NARRATIVE_REFRAME.md`, `metric_consistency_report.json`, `DISAGREEMENT_AS_TRIAGE.md`, and `MDD5K_F32_F41_ASYMMETRY_V4.md` as current sources.
**Per GPT round 10–14**: format-(b) skeleton greenlit; full prose may proceed from current sources.

---

## Section 5 — Architecture Results

### Overall narrative arc for Section 5

> Stacker LGBM achieves accuracy parity with our reproduced TF-IDF (not superiority), exceeds published baselines, and provides four deployment properties unavailable to pure TF-IDF: (1) feature decomposition for transparency, (2) cross-dataset bias robustness, (3) dual-standard audit traces, (4) disagreement triage signal (Section 6).

### Order of subsections

```
5.1 Main benchmark (Table 5)
5.2 Feature ablation (MAS vs TF-IDF contribution)
5.3 Bias robustness (47.7× cascade)
5.4 Dual-standard audit (trade-off, not robustness)
5.5 TF-IDF reproduction gap (limitation, transparently disclosed)
5.6 Confidence-gated ensemble (null result)
```

Class coverage limitations moved to §7.4.

---

## §5.1 — Main Benchmark

### Source artifacts
- `docs/paper/NARRATIVE_REFRAME.md` Section 5.1
- `results/analysis/metric_consistency_report.json` canonical values
- `results/rebase_v2.5/stacker_lgbm/metrics.json` (Stacker LGBM canonical)
- `results/validation/tfidf_baseline/metrics.json` (TF-IDF v4 canonical)
- `results/rebase_v2.5/dtv_test_final/metrics.json` (MAS-only DtV v4)

### Table 5 placeholder

```
| System | 2c | 4c | 12c Top-1 | 12c Top-3 | F1_macro | F1_w | Overall |
| Paper TF-IDF | .753 | .476 | .496 | .645 | .295 | .520 | .533 |
| Paper best LLM | .841 | .470 | .487 | .574 | .197 | .439 | .521 |
| Our TF-IDF | .713 | .491 | .610 | .829 | .352 | .585 | .555 |
| MAS-only (DtV) | .803 | .419 | .516 | .796 | .179 | .440 | .513 |
| Stacker LGBM (deployed) | 0.753 | 0.546 | 0.612 | 0.925 | 0.334 | 0.573 | 0.617 |
| Stacker LR | .619 | .538 | .538 | .887 | .360 | .558 | .572 |
```

### Key claims to make

1. Stacker LGBM Top-1 = 0.612 matches our TF-IDF Top-1 = 0.610 (Δ +0.002, McNemar p ≈ 1.0)
2. Stacker LGBM exceeds Paper TF-IDF by +11.6pp Top-1 and +28.0pp Top-3
3. Stacker LGBM exceeds Paper best LLM by +12.5pp Top-1 and +35.1pp Top-3
4. MAS-only (DtV) underperforms TF-IDF on Top-1 (-9.4pp) but stronger on 2-class (+9pp)
5. Stacker LGBM passes the pre-specified ±5pp non-inferiority margin against our reproduced TF-IDF baseline. Stacker LR is retained as a macro-F1-oriented comparator, not as the deployed accuracy model.

### Allowed wording

- ✅ "matches our reproduced TF-IDF baseline within ±5pp non-inferiority margin"
- ✅ "Stacker LGBM passes ±5pp non-inferiority margin; LR does not and is retained as a macro-F1-oriented comparator"
- ✅ "exceeds published paper baselines"
- ✅ "achieves accuracy parity with our stronger reproduced TF-IDF"
- ✅ "the supervised features carry most of the Top-1 accuracy weight"
- ✅ "deployment trade-off"
- ✅ "statistical parity, not superiority"

### Forbidden wording

- ❌ Forbidden: MAS beats TF-IDF on accuracy
- ❌ "Stacker outperforms TF-IDF" (without context)
- ❌ "SOTA"
- ❌ "best published" (without "while remaining tied with our reproduced TF-IDF")
- ❌ "MAS architecture is more accurate"
- ❌ "improvement of 11.6pp" (without disclosing TF-IDF reproduction gap)
- ❌ "LR and LGBM both satisfy the ±5pp margin"
- ❌ "Stacker LR is non-inferior to TF-IDF"
- ❌ "Stacker LR achieves accuracy parity"

### Reviewer attacks + responses

**Q1**: "Why is your TF-IDF stronger than the paper's?"
**A**: See Section 5.5 — disclosed as a limitation. Cause not fully identified; likely preprocessing or split differences. We claim parity against our stronger reproduced baseline, not against the paper's number.

**Q2**: "If TF-IDF achieves parity, why use MAS at all?"
**A**: See Sections 5.3 (bias robustness), 5.4 (dual-standard audit), and 6 (disagreement triage). MAS architecture provides deployment properties unavailable to TF-IDF, not Top-1 improvement.

**Q3**: "Is McNemar p ≈ 1.0 evidence of equivalence?"
**A**: It is failure to reject the null at α=0.05 with our 1000 cases, consistent with Stacker LGBM parity within our pre-specified ±5pp margin. We do not claim formal equivalence — we claim non-inferiority for Stacker LGBM.

### Length target

~250 words + 1 table

---

## §5.2 — Feature Ablation (MAS Contribution)

### Source artifacts
- `docs/analysis/MAS_vs_LGBM_CONTRIBUTION.md`
- Stacker LGBM feature importance (TF-IDF block 88.1%, MAS block 11.9%)

### Key claims

1. TF-IDF features carry 88.1% of LGBM importance; MAS features carry 11.9%
2. MAS features modestly improve macro-F1 (rare-class signal)
3. MAS does NOT improve Top-1 over TF-IDF-alone

### Allowed wording

- ✅ "MAS features contribute 11.9% of stacker decision weight"
- ✅ "supervised features dominate Top-1 accuracy"
- ✅ "transparent decomposition"
- ✅ "modest rare-class macro-F1 gains"

### Forbidden wording

- ❌ "MAS architecture provides accuracy gains" (it doesn't, on Top-1)
- ❌ "MAS replaces TF-IDF" (it doesn't, it's complementary)
- ❌ Use feature ablation F_macro values without explicit "feature ablation evaluator" caveat (per GPT round 6: ablation values were 0.367 vs final v4 0.334)

### Reviewer attack + response

**Q**: "If MAS contributes only 11.9% importance, is the architecture worth it?"
**A**: Top-1 alone does not justify MAS. The justification comes from Sections 5.3 / 5.4 / 6 (deployment properties). Section 5.2 is reported transparently to prevent overclaiming MAS's accuracy contribution.

### Length target

~150 words

---

## §5.3 — Cross-Dataset Bias Robustness (THE BIG ONE)

### Source artifacts
- `docs/analysis/MDD5K_F32_F41_ASYMMETRY_V4.md` (canonical post-sync)
- `results/analysis/mdd5k_f32_f41_asymmetry_v4.json` (numerical source)
- `docs/paper/NARRATIVE_REFRAME.md` Section 5.3

### Cascade table placeholder

```
| Step | System | Asymmetry | 95% CI | Cumulative improvement |
|---|---|---:|:---:|---:|
| 0 | Single LLM (Qwen3-32B-AWQ) | 189× | (degenerate, n=1) | baseline |
| 1 | MAS architecture (T1) | 8.94× | n/a | 21× |
| 2 | + Somatization-aware prompting (R6v2) | 5.58× | n/a | 33× |
| 3 | + Infrastructure / evaluation contract repair | 3.97× | [2.82, 6.08] | 47.7× |
```

### Key claims

1. Single-LLM baseline collapses to 189× F32/F41 asymmetry on MDD-5k (catastrophic)
2. MAS architecture alone bounds this to 8.94× (21× improvement)
3. Somatization-aware prompting (R6v2) reaches 5.58× (33× cumulative)
4. v4 infrastructure + evaluation contract repair achieves 3.97× (47.7× cumulative)
5. MAS ICD-10 v4 = current best asymmetry result; R6v2 = cascade stepping stone

### Allowed wording

- ✅ "189× → 3.97× under v4 evaluation contract"
- ✅ "47.7× cumulative improvement"
- ✅ "v4 number is the current paper contract; R6v2 remains an intermediate historical measurement"
- ✅ "infrastructure / evaluation-contract repair" (separate from "model behavior change")
- ✅ "MAS ICD-10 v4 reaches 3.97×"

### Forbidden wording

- ❌ "v4 evaluator changed scoring" (clarify: prediction views, not score formula)
- ❌ Drop R6v2 from narrative entirely (it's still cascade evidence)
- ❌ "MAS solves bias" (it bounds, doesn't eliminate)
- ❌ "Asymmetry is now resolved" (3.97× is still asymmetric)
- ❌ "A specific repair caused the full cascade" (without ablation evidence)
- ❌ "Each step represents the isolated effect of a single repair"

### Reviewer attack + response

**Q1**: "Did v4 evaluator repair improve scores artificially?"
**A**: The asymmetry metric itself is unchanged: F41→F32 divided by F32→F41. The v4 value is reported under the current paper evaluation contract and current pipeline state. We present the cascade descriptively rather than attributing the full change to any single repair.

**Q2**: "Why include R6v2 if MAS ICD-10 v4 is better?"
**A**: R6v2 demonstrates that prompt-level mitigation transfers across datasets. MAS ICD-10 v4 demonstrates that infrastructure repair compounds with prompt mitigation. Both are evidence of the cascade.

**Q3**: "Is 95% CI [2.82, 6.08] robust enough to claim 3.97×?"
**A**: 1000 bootstrap resamples, seed=20260420. CI width reflects denominator size (38 F32→F41 cases). We additionally report asymmetric excess (+113 cases, CI [+87, +139]) which is more stable to small-denominator effects.

### Length target

~400 words + 1 cascade table

---

## §5.4 — Dual-Standard Audit (LOCKED to Trade-off Framing)

### Source artifacts
- `docs/paper/NARRATIVE_REFRAME.md` Section 5.4
- `docs/analysis/MDD5K_F32_F41_ASYMMETRY_V4.md` (asymmetry findings)
- `results/dual_standard_full/{lingxidiag16k,mdd5k}/mode_*/pilot_*/metrics.json`

### Two main tables

#### Table A — LingxiDiag dual-standard

```
| Mode | 12c Top-1 | 12c Top-3 | F1_m | F1_w | 2c | 4c | Overall |
| ICD-10 | 0.507 | 0.800 | 0.199 | 0.457 | 0.778 | 0.447 | 0.5145 |
| DSM-5 | 0.471 | 0.803 | 0.188 | 0.421 | 0.767 | 0.476 | 0.5065 |
| Both | 0.507 | 0.800 | 0.199 | 0.457 | 0.778 | 0.447 | 0.5145 |
```

#### Table B — MDD-5k dual-standard

```
| Mode | 12c Top-1 | 12c Top-3 | F1_m | F1_w | 2c | 4c | Overall | F32/F41 asym |
| ICD-10 | 0.597 | 0.853 | 0.197 | 0.514 | 0.890 | 0.444 | 0.566 | 3.97× |
| DSM-5 | 0.581 | 0.842 | 0.230 | 0.526 | 0.912 | 0.520 | 0.584 | 7.24× |
| Both | 0.597 | 0.853 | 0.197 | 0.514 | 0.890 | 0.444 | 0.566 | 3.97× |
```

### Key claims (LOCKED)

1. Both mode is ICD-10 pass-through, NOT ensemble (1925/1925 match across LingxiDiag + MDD-5k + asymmetry)
2. DSM-5 v0 LOSES Top-1 in both datasets and Top-3 on MDD-5k
3. DSM-5 v0 WINS aggregate metrics (F1_m, F1_w, 2c, 4c, Overall) on MDD-5k only (not LingxiDiag Overall)
4. DSM-5 v0 amplifies F32/F41 asymmetry by ~83% on both datasets (paired bootstrap CI excludes 0)
5. Aggregate-metric advantages on MDD-5k are STANDARD-SENSITIVE LABEL-SET RESTRUCTURING, not bias robustness or clinical validity
6. F42 OCD recall collapses from ICD-10 52% to DSM-5 12% on LingxiDiag (40pp drop)

### Allowed wording

- ✅ "DSM-5 v0 shows dataset-dependent metric trade-offs"
- ✅ "DSM-5 v0 amplifies F32/F41 asymmetry by ~83% relative to ICD-10"
- ✅ "audit feature, not ensemble"
- ✅ "metric trade-off, not bias robustness"
- ✅ "DSM-5 v0 partially undoes prompt-level bias mitigation gains"
- ✅ "standard-sensitive label-set restructuring"
- ✅ "DSM-5 v0 stubs are LLM-drafted (UNVERIFIED_LLM_DRAFT)"

### Forbidden wording

- ❌ Forbidden: DSM-5 generalizes better
- ❌ "DSM-5 wins on MDD-5k" (without specifying WHICH metrics)
- ❌ Forbidden: DSM-5 improves robustness under shift
- ❌ "DSM-5 v0 is clinically valid"
- ❌ "Dual-standard mode is an ensemble"
- ❌ Any framing connecting DSM-5 advantages to bias claim

### Reviewer attacks + responses

**Q1**: "Why does DSM-5 win on aggregate metrics but lose on Top-1?"
**A**: DSM-5 v0 reasoning produces different multilabel structure (broader gold-set coverage) while having weaker primary-pick ranking. This is consistent with v0 criteria being LLM-drafted toward depression-class structure. We report this as a documented trade-off, not as superiority.

**Q2**: "Is Both mode's identity to ICD-10 a bug?"
**A**: No, it's architectural — Both mode emits DSM-5 reasoning as sidecar evidence while preserving ICD-10 as primary decision. Confirmed across 5 independent metric families on 1925 cases.

**Q3**: "Why is DSM-5 worse on F32/F41 asymmetry but better on 2-class accuracy?"
**A**: 2-class accuracy doesn't penalize confusion within the F32/F41 binary (depression-anxiety mixed). Asymmetry directly measures it. The two metrics measure different properties.

**Q4**: "Should we be using DSM-5 v0 results at all if criteria are unverified?"
**A**: We label all DSM-5 v0 stubs as UNVERIFIED_LLM_DRAFT throughout the paper. Section 7 limitations explicitly states clinical validity requires Chang Gung clinician review and AIDA-Path structural alignment, both pending. The dual-standard infrastructure is the contribution; v0 criteria are research-grade only.

### Length target

~600 words + 2 tables

---

## §5.5 — TF-IDF Reproduction Gap (Limitation)

### Source artifacts
- `docs/analysis/EVALUATION_PROVENANCE.md`
- Paper TF-IDF Top-1 = 0.496 vs our reproduction 0.610 = +11.4pp gap

### Key claims

1. Our reproduced TF-IDF outperforms the paper's by +11.4pp Top-1
2. Cause not fully identified — likely preprocessing or train/dev/test split differences
3. Disclosed openly as a limitation
4. Stacker parity claim is against our stronger reproduction, not against paper number

### Allowed wording

- ✅ "We disclose openly"
- ✅ "Cause not fully identified"
- ✅ "Likely preprocessing or split differences"
- ✅ "Parity is claimed against our reproduced TF-IDF, not against the published number"

### Forbidden wording

- ❌ "Our TF-IDF is the correct one"
- ❌ "The paper's TF-IDF was buggy" (we don't know that)
- ❌ Hide this in appendix

### Length target

~150 words

---

## §5.6 — Confidence-Gated Ensemble Null Result

### Source artifact
- `results/ensemble/final_metrics.json` (commit `6ba6e02`)

### Locked claim

Dev-tuned confidence gating selected TF-IDF-only; no ensemble gain.

### Allowed wording

- ✅ "Per-class routing did not improve F1_macro over TF-IDF alone"
- ✅ "Selected rule on dev: TF-IDF only; ensemble collapses to baseline"

### Forbidden wording

- ❌ "Ensemble improves accuracy"
- ❌ "Confidence gate yields meaningful gains"

### Pointer

Class coverage limitations moved to §7.4.

### Length target

~200 words

---

## Section 5 total length target

~1,750 words + 4 tables (Table 5 main, Tables A+B dual-standard, cascade table)
