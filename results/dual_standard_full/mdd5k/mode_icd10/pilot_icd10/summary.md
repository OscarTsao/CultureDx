# Run Summary: pilot_icd10

- Dataset: mdd5k
- Cases: 925

## Metrics

### comorbidity
- avg_gold_labels: 1.0908
- avg_predicted_labels: 1.9027
- comorbidity_detection_f1: 0.1446
- hamming_accuracy: 0.3976
- label_coverage: 0.7218
- label_precision: 0.4108
- subset_accuracy: 0.0605

### diagnosis
- accuracy: 0.0562
- macro_f1: 0.2058
- overall: 0.4234
- top1_accuracy: 0.5849
- top3_accuracy: 0.7395
- weighted_f1: 0.5309

### table4
- 2class_Acc: 0.8898
- 2class_F1_macro: 0.8709
- 2class_F1_weighted: 0.9071
- 4class_Acc: 0.4443
- 4class_F1_macro: 0.4428
- 4class_F1_weighted: 0.4442
- 12class_Acc: 0.0638
- 12class_Top1: 0.5968
- 12class_Top3: 0.8530
- 12class_F1_macro: 0.1974
- 12class_F1_weighted: 0.5136
- 2class_n: 490.0000
- 4class_n: 925.0000
- 12class_n: 925.0000
- Overall: 0.5658

### metric_definitions
- 12class_Top1_source: primary_diagnosis (paper-parent)
- 12class_Top3_source: [primary] + (ranked_codes - {primary})[:2] (paper-parent)
- 12class_F1_source: primary + threshold-gated comorbid_diagnoses (paper-parent multilabel)
- 12class_exact_match_source: same as F1 (multilabel)
- 2class_gold_source: MDD-5k Label/patient_*_label.json ICD_Code (F41.2 excluded)
- 2class_pred_source: primary_diagnosis (paper-parent)
- 4class_gold_source: MDD-5k Label/patient_*_label.json ICD_Code (F41.2 -> Mixed)
- 4class_pred_source: primary + raw_pred_codes for F41.2 detection
- Overall_source: mean(non-_n metrics)
- post_fix_version: v4 (eval_contract_repair_2026_04_25)
- paper_canonical_top1: table4.12class_Top1 (multi-label paper alignment)
- mdd5k_raw_gold_source: data/raw/mdd5k_repo/Label/patient_*_label.json ICD_Code

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 410 | 0.0000 | 0.8780 |
| F33 | 2 | 0.0000 | 0.0000 |
| F42 | 21 | 0.0000 | 0.4762 |
| somatized_expression | 925 | 0.0000 | 0.5849 |
