# Run Summary: factorial_c_improved_evidence

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.2710
- top1_accuracy: 0.4610
- top3_accuracy: 0.4880
- macro_f1: 0.2023
- weighted_f1: 0.3982
- overall: 0.3641

### comorbidity
- hamming_accuracy: 0.3782
- subset_accuracy: 0.2710
- comorbidity_detection_f1: 0.1327
- label_coverage: 0.4652
- label_precision: 0.3990
- avg_predicted_labels: 1.3060
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3620
- macro_f1: 0.1977
- weighted_f1: 0.2544
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.7611
- 2class_F1_macro: 0.7101
- 2class_F1_weighted: 0.7771
- 4class_Acc: 0.4540
- 4class_F1_macro: 0.3605
- 4class_F1_weighted: 0.3751
- 12class_Acc: 0.2710
- 12class_Top1: 0.4650
- 12class_Top3: 0.4920
- 12class_F1_macro: 0.1790
- 12class_F1_weighted: 0.3771
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.4747

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.8973 |
| F42 | 36 | 0.0000 | 0.5000 |
| somatized_expression | 998 | 0.0020 | 0.4609 |
| direct_expression | 2 | 0.0000 | 0.5000 |
