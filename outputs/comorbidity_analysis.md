# Comorbidity Detection Analysis

## Executive Summary

Current comorbidity detection achieves 20.9% subset accuracy with ratio=0.9 filtering.
Analysis reveals a **structural indistinguishability problem**: criterion-level features
from checker outputs cannot discriminate true comorbidity from false positives, because
shared symptoms produce near-identical confidence profiles in both cases.

**Key finding:** A LightGBM classifier trained on 36 features (5-fold CV, N=3088) achieves
AUC=0.61 and learns to suppress all comorbidity predictions. The optimal strategy for
maximizing subset accuracy on this data is to predict single diagnosis (40.8% subset
accuracy), confirming that the signal for comorbidity is absent from criterion-checker
features alone.

## 1. Scale of the Problem

| Metric | Value |
|--------|-------|
| Gold comorbidity rate | 10.2% (328/3200) |
| Predicted comorbidity rate | 67.0% (2145/3200) |
| Gold avg labels per case | 1.10 |
| Predicted avg labels per case | 1.81 |
| Over-prediction factor | **6.5x** |

The system predicts comorbidity 6.5x more often than gold labels indicate, primarily
due to criterion-overlap-driven false positives.

## 2. Comorbidity Pair Analysis

### Most Common Gold Pairs
| Pair | Count | % of comorbid |
|------|-------|--------------|
| F32+F41 (Depression+Anxiety) | 136 | 41.5% |
| F41+F51 (Anxiety+Sleep) | 40 | 12.2% |
| F41+F42 (Anxiety+OCD) | 24 | 7.3% |

### Predicted vs Gold Pairs
| Pair | Gold | Predicted | TP | FP | Precision | Recall |
|------|------|-----------|----|----|-----------|--------|
| F32+F41 | 136 | 1910 | 73 | 1837 | 3.8% | 53.7% |
| F41+F42 | 24 | 421 | 8 | 413 | 1.9% | 33.3% |
| F32+F42 | 0 | 352 | 0 | 352 | 0.0% | - |
| F41+F43 | 0 | 223 | 0 | 223 | 0.0% | - |
| F32+F43 | 0 | 184 | 0 | 184 | 0.0% | - |

F32+F41 has **3.8% precision** (73 true positives out of 1910 predictions). The system
generates 1837 false F32+F41 comorbidity predictions.

## 3. Criterion Overlap: F32+F41 (Depression+Anxiety)

For the 136 gold F32+F41 comorbid cases:

| Metric | Value |
|--------|-------|
| Mean F32 criteria met | 6.84 / 11 |
| Mean F41 criteria met | 3.18 / 5 |
| Mean shared evidence rate | 32.7% |
| Shared evidence std | 32.5% |

**32.7% of anxiety criteria evidence overlaps with depression criteria evidence**,
using character-level Jaccard > 0.4. This means roughly 1 in 3 anxiety criteria are
met using the same transcript excerpts that support depression criteria, making the
two diagnoses structurally entangled at the evidence level.

## 4. Discriminative Feature Analysis

Comparing feature distributions for true comorbid (TP) vs false positive (FP) cases:

| Feature | True Comorbid (N=222) | False Positive (N=1923) | Delta |
|---------|----------------------|------------------------|-------|
| Confidence ratio | 0.929 +/- 0.092 | 0.916 +/- 0.097 | +0.013 |
| Confidence gap | 0.068 +/- 0.088 | 0.081 +/- 0.093 | -0.013 |
| Evidence overlap | 0.244 +/- 0.296 | 0.262 +/- 0.278 | -0.018 |
| Primary met count | 6.48 +/- 2.35 | 6.50 +/- 2.10 | -0.02 |
| Secondary met count | 4.36 +/- 1.24 | 4.45 +/- 1.52 | -0.09 |
| Primary confidence | 0.969 +/- 0.045 | 0.970 +/- 0.037 | -0.001 |
| Secondary confidence | 0.901 +/- 0.101 | 0.889 +/- 0.104 | +0.012 |
| Cross-domain pair | 0.680 +/- 0.466 | 0.782 +/- 0.413 | -0.102 |

**All deltas are within noise.** The confidence ratio, evidence overlap, and criterion
counts are virtually identical between true comorbid and false positive cases. The
largest delta is cross_domain_pair (-0.10), but the direction is counterintuitive:
false positives are *more* likely to be cross-domain, not less.

## 5. LightGBM Classifier Results

### Binary Comorbidity Detection (has comorbidity vs not)

| Method | Accuracy | Precision | Recall | F1 |
|--------|----------|-----------|--------|-----|
| Ratio=0.0 (keep all) | 35.0% | 10.4% | 70.5% | 18.1% |
| Ratio=0.9 (current) | 48.0% | 10.8% | 56.5% | 18.1% |
| Ratio=1.0 (suppress all) | 83.4% | 11.9% | 9.8% | 10.8% |
| **LightGBM (5-fold CV)** | **89.8%** | **0.0%** | **0.0%** | **0.0%** |

The classifier achieves 89.8% accuracy by predicting "no comorbidity" for every case.
AUC = 0.61 (+/- 0.05) across folds, indicating the features carry very weak signal.

### Multi-Label Subset Accuracy (full diagnostic evaluation)

| Method | Subset Acc | Hamming | Label Cov | Label Prec |
|--------|-----------|---------|-----------|------------|
| Ratio=0.0 | 15.6% | 39.7% | 66.0% | 41.2% |
| Ratio=0.9 (current) | **21.7%** | 40.8% | 61.7% | 42.7% |
| Ratio=1.0 | 37.7% | 43.3% | 46.8% | 46.1% |
| **LightGBM** | **40.8%** | **43.9%** | **43.9%** | **47.0%** |

The classifier improves subset accuracy from 20.9% to 40.8% (+19.9pp) — but this
is entirely achieved by suppressing all comorbidity, not by discriminating.

### Top Feature Importances (LightGBM gain)

| Feature | Importance |
|---------|-----------|
| avg_evidence_length_primary | 316.8 |
| secondary_avg_criterion_conf | 146.0 |
| primary_unique_evidence_count | 141.7 |
| secondary_confidence | 105.0 |
| primary_confidence | 103.0 |
| primary_conf_variance | 83.0 |
| total_criteria_met_all | 61.9 |
| conf_range_across_disorders | 54.8 |

Evidence length and confidence are the most informative features, but none provide
sufficient discriminative power for comorbidity detection.

## 6. Root Cause Analysis

The fundamental problem is **criterion overlap masquerading as comorbidity**:

1. **Depression criteria (F32) overlap extensively with anxiety criteria (F41).**
   Sleep disturbance, concentration difficulty, fatigue, and psychomotor agitation
   appear in both checklists. When a transcript mentions these symptoms, both
   checkers rate them as "met" with high confidence.

2. **The LLM criterion checker cannot distinguish shared-symptom from unique-symptom.**
   When a patient says "I can't sleep and my mind keeps racing," both the F32 checker
   (C5: sleep disturbance) and the F41.1 checker (B4: difficulty concentrating/mind
   going blank) can claim this as evidence, producing overlapping confirmation.

3. **Confidence calibration is disorder-local.** Each disorder's confidence is
   computed independently from its own criteria met/required ratio. There is no
   cross-disorder penalty for using the same evidence for multiple disorders.

4. **The confidence ratio filter (0.9) is too generous.** With both disorders
   typically achieving confidence > 0.85, the 90% ratio rarely triggers exclusion.

## 7. Recommendations

### Immediate (no model changes needed)
1. **Raise ratio threshold to 0.95-1.0.** Subset accuracy increases monotonically:
   0.9 -> 21.7%, 0.95 -> 28.9%, 1.0 -> 37.7%. This sacrifices comorbidity recall
   but dramatically improves overall accuracy.

2. **Suppress comorbidity for specific high-FP pairs.** F32+F42, F32+F43, F41+F43
   have zero true positives across all data. Add these to exclusion rules.

### Medium-term (requires pipeline changes)
3. **Cross-disorder evidence deduplication.** Before calibration, identify evidence
   spans shared between two candidate disorders and penalize the lower-confidence
   disorder for shared evidence. This directly addresses the root cause.

4. **Unique-evidence requirement.** Require the secondary disorder to have at least
   N criteria met with evidence *not* shared with the primary disorder. Gold
   comorbid cases have 3.18 anxiety criteria met on average; requiring >= 2 unique
   criteria could filter many false positives.

5. **Pair-specific comorbidity priors.** Use the gold pair frequencies to set
   pair-specific thresholds. F32+F41 (precision 3.8%) should have a much higher
   bar than F41+F42 (precision 1.9%).

### Long-term
6. **Semantic evidence matching.** Replace character-level Jaccard overlap with
   embedding-based similarity (BGE-M3) for evidence deduplication. The current
   0.4 Jaccard threshold is coarse for Chinese text.

7. **Dedicated comorbidity verification agent.** A final-stage agent that receives
   both candidate disorders and their evidence, then makes a joint determination.
   This is the only approach that can reason about whether symptoms represent one
   disorder or two.
