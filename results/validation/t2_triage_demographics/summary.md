# Run Summary: t2_triage_demographics

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.2850
- top1_accuracy: 0.5210
- top3_accuracy: 0.6160
- macro_f1: 0.2171
- weighted_f1: 0.4614
- overall: 0.4201

### comorbidity
- hamming_accuracy: 0.4507
- subset_accuracy: 0.2880
- comorbidity_detection_f1: 0.1282
- label_coverage: 0.5930
- label_precision: 0.4720
- avg_predicted_labels: 1.4290
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3770
- macro_f1: 0.2571
- weighted_f1: 0.3251
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.8013
- 2class_F1_macro: 0.7865
- 2class_F1_weighted: 0.8223
- 4class_Acc: 0.4290
- 4class_F1_macro: 0.4016
- 4class_F1_weighted: 0.4138
- 12class_Acc: 0.2880
- 12class_Top1: 0.5260
- 12class_Top3: 0.6190
- 12class_F1_macro: 0.2012
- 12class_F1_weighted: 0.4507
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.5218

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.8432 |
| F42 | 36 | 0.0000 | 0.5278 |
| somatized_expression | 998 | 0.0000 | 0.5210 |
| direct_expression | 2 | 0.0000 | 0.5000 |
