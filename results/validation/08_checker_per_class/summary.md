# Run Summary: 08_checker_per_class

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.2030
- top1_accuracy: 0.5150
- top3_accuracy: 0.5920
- macro_f1: 0.2049
- weighted_f1: 0.4634
- overall: 0.3957

### comorbidity
- hamming_accuracy: 0.3944
- subset_accuracy: 0.2030
- comorbidity_detection_f1: 0.1564
- label_coverage: 0.5705
- label_precision: 0.4105
- avg_predicted_labels: 1.5660
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3740
- macro_f1: 0.2403
- weighted_f1: 0.3068
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.7759
- 2class_F1_macro: 0.7628
- 2class_F1_weighted: 0.8012
- 4class_Acc: 0.4520
- 4class_F1_macro: 0.4085
- 4class_F1_weighted: 0.4232
- 12class_Acc: 0.2030
- 12class_Top1: 0.5200
- 12class_Top3: 0.5970
- 12class_F1_macro: 0.1794
- 12class_F1_weighted: 0.4536
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.5070

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.8108 |
| F42 | 36 | 0.0000 | 0.5000 |
| somatized_expression | 998 | 0.0000 | 0.5150 |
| direct_expression | 2 | 0.0000 | 0.5000 |
