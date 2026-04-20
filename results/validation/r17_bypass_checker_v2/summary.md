# Run Summary: r17_bypass_checker_v2

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.0430
- top1_accuracy: 0.5200
- top3_accuracy: 0.6630
- macro_f1: 0.2170
- weighted_f1: 0.4560
- overall: 0.3798

### comorbidity
- hamming_accuracy: 0.3476
- subset_accuracy: 0.0450
- comorbidity_detection_f1: 0.1594
- label_coverage: 0.6397
- label_precision: 0.3575
- avg_predicted_labels: 1.9300
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3960
- macro_f1: 0.2514
- weighted_f1: 0.3328
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.8203
- 2class_F1_macro: 0.7957
- 2class_F1_weighted: 0.8355
- 4class_Acc: 0.4470
- 4class_F1_macro: 0.3935
- 4class_F1_weighted: 0.4245
- 12class_Acc: 0.0450
- 12class_Top1: 0.5240
- 12class_Top3: 0.6650
- 12class_F1_macro: 0.2121
- 12class_F1_weighted: 0.4452
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.5098

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.8919 |
| F42 | 36 | 0.0000 | 0.5000 |
| somatized_expression | 998 | 0.0000 | 0.5200 |
| direct_expression | 2 | 0.0000 | 0.5000 |
