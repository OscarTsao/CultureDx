# Run Summary: r6_combined

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.4650
- top1_accuracy: 0.5170
- top3_accuracy: 0.5170
- macro_f1: 0.2389
- weighted_f1: 0.4576
- overall: 0.4391

### comorbidity
- hamming_accuracy: 0.4930
- subset_accuracy: 0.4650
- comorbidity_detection_f1: 0.0000
- label_coverage: 0.4930
- label_precision: 0.5220
- avg_predicted_labels: 1.0000
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3830
- macro_f1: 0.2114
- weighted_f1: 0.2648
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.8097
- 2class_F1_macro: 0.7905
- 2class_F1_weighted: 0.8293
- 4class_Acc: 0.4530
- 4class_F1_macro: 0.3580
- 4class_F1_weighted: 0.3664
- 12class_Acc: 0.4650
- 12class_Top1: 0.5220
- 12class_Top3: 0.5220
- 12class_F1_macro: 0.2000
- 12class_F1_weighted: 0.4360
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.5229

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.8757 |
| F42 | 36 | 0.0000 | 0.5000 |
| somatized_expression | 998 | 0.0010 | 0.5170 |
| direct_expression | 2 | 0.0000 | 0.5000 |
