# Run Summary: t3_manual_fixed

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.3400
- top1_accuracy: 0.5250
- top3_accuracy: 0.5850
- macro_f1: 0.2145
- weighted_f1: 0.4619
- overall: 0.4253

### comorbidity
- hamming_accuracy: 0.4619
- subset_accuracy: 0.3400
- comorbidity_detection_f1: 0.1256
- label_coverage: 0.5610
- label_precision: 0.4855
- avg_predicted_labels: 1.3120
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3870
- macro_f1: 0.2484
- weighted_f1: 0.3175
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.8055
- 2class_F1_macro: 0.7815
- 2class_F1_weighted: 0.8213
- 4class_Acc: 0.4480
- 4class_F1_macro: 0.4009
- 4class_F1_weighted: 0.4158
- 12class_Acc: 0.3400
- 12class_Top1: 0.5300
- 12class_Top3: 0.5900
- 12class_F1_macro: 0.1900
- 12class_F1_weighted: 0.4504
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.5248

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.8622 |
| F42 | 36 | 0.0000 | 0.5000 |
| somatized_expression | 998 | 0.0000 | 0.5251 |
| direct_expression | 2 | 0.0000 | 0.5000 |
