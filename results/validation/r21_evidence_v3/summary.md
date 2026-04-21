# Run Summary: r21_evidence_v3

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.0260
- top1_accuracy: 0.3610
- top3_accuracy: 0.4220
- macro_f1: 0.1749
- weighted_f1: 0.3127
- overall: 0.2593

### comorbidity
- hamming_accuracy: 0.2197
- subset_accuracy: 0.0260
- comorbidity_detection_f1: 0.1603
- label_coverage: 0.4048
- label_precision: 0.2280
- avg_predicted_labels: 1.8870
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.2830
- macro_f1: 0.1767
- weighted_f1: 0.2392
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.5835
- 2class_F1_macro: 0.5470
- 2class_F1_weighted: 0.6526
- 4class_Acc: 0.4430
- 4class_F1_macro: 0.3325
- 4class_F1_weighted: 0.3737
- 12class_Acc: 0.0260
- 12class_Top1: 0.3640
- 12class_Top3: 0.4250
- 12class_F1_macro: 0.1617
- 12class_F1_weighted: 0.3135
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.3839

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.7459 |
| F42 | 36 | 0.0000 | 0.4722 |
| somatized_expression | 998 | 0.0000 | 0.3617 |
| direct_expression | 2 | 0.0000 | 0.0000 |
