# Run Summary: r21_evidence_v2

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.0250
- top1_accuracy: 0.3360
- top3_accuracy: 0.3920
- macro_f1: 0.1464
- weighted_f1: 0.2681
- overall: 0.2335

### comorbidity
- hamming_accuracy: 0.2045
- subset_accuracy: 0.0260
- comorbidity_detection_f1: 0.1613
- label_coverage: 0.3748
- label_precision: 0.2125
- avg_predicted_labels: 1.8810
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.2710
- macro_f1: 0.1488
- weighted_f1: 0.2160
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.5497
- 2class_F1_macro: 0.4573
- 2class_F1_weighted: 0.5986
- 4class_Acc: 0.4330
- 4class_F1_macro: 0.2826
- 4class_F1_weighted: 0.3409
- 12class_Acc: 0.0260
- 12class_Top1: 0.3380
- 12class_Top3: 0.3940
- 12class_F1_macro: 0.1439
- 12class_F1_weighted: 0.2670
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.3483

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0054 | 0.7432 |
| F42 | 36 | 0.0000 | 0.4167 |
| somatized_expression | 998 | 0.0050 | 0.3367 |
| direct_expression | 2 | 0.0000 | 0.0000 |
