# Run Summary: r20_nos_variant

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.4380
- top1_accuracy: 0.4870
- top3_accuracy: 0.4870
- macro_f1: 0.2239
- weighted_f1: 0.4488
- overall: 0.4169

### comorbidity
- hamming_accuracy: 0.4640
- subset_accuracy: 0.4380
- comorbidity_detection_f1: 0.0000
- label_coverage: 0.4640
- label_precision: 0.4910
- avg_predicted_labels: 1.0000
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3540
- macro_f1: 0.2090
- weighted_f1: 0.2610
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.7484
- 2class_F1_macro: 0.7674
- 2class_F1_weighted: 0.7976
- 4class_Acc: 0.4510
- 4class_F1_macro: 0.3702
- 4class_F1_weighted: 0.3783
- 12class_Acc: 0.4380
- 12class_Top1: 0.4910
- 12class_Top3: 0.4910
- 12class_F1_macro: 0.1857
- 12class_F1_weighted: 0.4269
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.5041

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.7946 |
| F42 | 36 | 0.0000 | 0.5000 |
| somatized_expression | 998 | 0.0000 | 0.4870 |
| direct_expression | 2 | 0.0000 | 0.5000 |
