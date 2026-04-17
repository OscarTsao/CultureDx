# Run Summary: 07_verifier_on

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.2960
- top1_accuracy: 0.4260
- top3_accuracy: 0.4430
- macro_f1: 0.1935
- weighted_f1: 0.4201
- overall: 0.3557

### comorbidity
- hamming_accuracy: 0.3718
- subset_accuracy: 0.2960
- comorbidity_detection_f1: 0.1245
- label_coverage: 0.4255
- label_precision: 0.3945
- avg_predicted_labels: 1.1710
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.2840
- macro_f1: 0.1987
- weighted_f1: 0.2458
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.6004
- 2class_F1_macro: 0.6911
- 2class_F1_weighted: 0.6941
- 4class_Acc: 0.4060
- 4class_F1_macro: 0.3589
- 4class_F1_weighted: 0.3636
- 12class_Acc: 0.2960
- 12class_Top1: 0.4340
- 12class_Top3: 0.4510
- 12class_F1_macro: 0.1674
- 12class_F1_weighted: 0.4065
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.4426

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.5676 |
| F42 | 36 | 0.0000 | 0.5000 |
| somatized_expression | 998 | 0.0000 | 0.4259 |
| direct_expression | 2 | 0.0000 | 0.5000 |
