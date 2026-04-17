# Run Summary: t1_nos

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.0250
- top1_accuracy: 0.4780
- top3_accuracy: 0.5810
- macro_f1: 0.2261
- weighted_f1: 0.4477
- overall: 0.3515

### comorbidity
- hamming_accuracy: 0.2978
- subset_accuracy: 0.0250
- comorbidity_detection_f1: 0.1529
- label_coverage: 0.5607
- label_precision: 0.3080
- avg_predicted_labels: 1.9210
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3640
- macro_f1: 0.2403
- weighted_f1: 0.3034
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.7294
- 2class_F1_macro: 0.7613
- 2class_F1_weighted: 0.7879
- 4class_Acc: 0.4530
- 4class_F1_macro: 0.4160
- 4class_F1_weighted: 0.4238
- 12class_Acc: 0.0250
- 12class_Top1: 0.4820
- 12class_Top3: 0.5860
- 12class_F1_macro: 0.1866
- 12class_F1_weighted: 0.4421
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.4812

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.7622 |
| F42 | 36 | 0.0000 | 0.5000 |
| somatized_expression | 998 | 0.0000 | 0.4780 |
| direct_expression | 2 | 0.0000 | 0.5000 |
