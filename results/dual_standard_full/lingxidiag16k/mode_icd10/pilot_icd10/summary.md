# Run Summary: pilot_icd10

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.0460
- top1_accuracy: 0.5020
- top3_accuracy: 0.6390
- macro_f1: 0.2230
- weighted_f1: 0.4516
- overall: 0.3723

### comorbidity
- hamming_accuracy: 0.3371
- subset_accuracy: 0.0470
- comorbidity_detection_f1: 0.1583
- label_coverage: 0.6165
- label_precision: 0.3480
- avg_predicted_labels: 1.9250
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3800
- macro_f1: 0.2523
- weighted_f1: 0.3242
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.7780
- 2class_F1_macro: 0.7680
- 2class_F1_weighted: 0.8096
- 4class_Acc: 0.4470
- 4class_F1_macro: 0.4140
- 4class_F1_weighted: 0.4334
- 12class_Acc: 0.0460
- 12class_Top1: 0.5070
- 12class_Top3: 0.6440
- 12class_F1_macro: 0.1987
- 12class_F1_weighted: 0.4572
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.5003

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.8378 |
| F42 | 36 | 0.0000 | 0.5000 |
| somatized_expression | 998 | 0.0000 | 0.5020 |
| direct_expression | 2 | 0.0000 | 0.5000 |
