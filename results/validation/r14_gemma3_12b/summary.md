# Run Summary: r14_gemma3_12b

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.0930
- top1_accuracy: 0.0930
- top3_accuracy: 0.0930
- macro_f1: 0.0155
- weighted_f1: 0.0158
- overall: 0.0621

### comorbidity
- hamming_accuracy: 0.0930
- subset_accuracy: 0.0930
- comorbidity_detection_f1: 0.0000
- label_coverage: 0.0930
- label_precision: 0.0930
- avg_predicted_labels: 1.0000
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.0000
- macro_f1: 0.0000
- weighted_f1: 0.0000
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.0000
- 2class_F1_macro: 0.0000
- 2class_F1_weighted: 0.0000
- 4class_Acc: 0.2700
- 4class_F1_macro: 0.1063
- 4class_F1_weighted: 0.1148
- 12class_Acc: 0.0850
- 12class_Top1: 0.0850
- 12class_Top3: 0.0850
- 12class_F1_macro: 0.0131
- 12class_F1_weighted: 0.0122
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.0701

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 1.0000 | 0.0000 |
| F42 | 36 | 1.0000 | 0.0000 |
| somatized_expression | 998 | 1.0000 | 0.0932 |
| direct_expression | 2 | 1.0000 | 0.0000 |
