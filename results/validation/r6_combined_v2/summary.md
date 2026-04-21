# Run Summary: r6_combined_v2

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.0350
- top1_accuracy: 0.5030
- top3_accuracy: 0.6290
- macro_f1: 0.2297
- weighted_f1: 0.4555
- overall: 0.3705

### comorbidity
- hamming_accuracy: 0.3262
- subset_accuracy: 0.0360
- comorbidity_detection_f1: 0.1606
- label_coverage: 0.6075
- label_precision: 0.3355
- avg_predicted_labels: 1.9350
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3870
- macro_f1: 0.2568
- weighted_f1: 0.3308
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.7759
- 2class_F1_macro: 0.7713
- 2class_F1_weighted: 0.8098
- 4class_Acc: 0.4570
- 4class_F1_macro: 0.4249
- 4class_F1_weighted: 0.4435
- 12class_Acc: 0.0350
- 12class_Top1: 0.5060
- 12class_Top3: 0.6330
- 12class_F1_macro: 0.1924
- 12class_F1_weighted: 0.4505
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.4999

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.8297 |
| F42 | 36 | 0.0000 | 0.5000 |
| somatized_expression | 998 | 0.0000 | 0.5030 |
| direct_expression | 2 | 0.0000 | 0.5000 |
