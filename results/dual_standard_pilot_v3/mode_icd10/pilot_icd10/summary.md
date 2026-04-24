# Run Summary: pilot_icd10

- Dataset: lingxidiag16k
- Cases: 100

## Metrics

### diagnosis
- accuracy: 0.0900
- top1_accuracy: 0.5200
- top3_accuracy: 0.6700
- macro_f1: 0.1711
- weighted_f1: 0.4617
- overall: 0.3826

### comorbidity
- hamming_accuracy: 0.3667
- subset_accuracy: 0.0900
- comorbidity_detection_f1: 0.2000
- label_coverage: 0.6300
- label_precision: 0.3800
- avg_predicted_labels: 1.8900
- avg_gold_labels: 1.1100

### four_class
- accuracy: 0.3700
- macro_f1: 0.2256
- weighted_f1: 0.3190
- n_cases: 100.0000

### table4
- 2class_Acc: 0.7708
- 2class_F1_macro: 0.7329
- 2class_F1_weighted: 0.7795
- 4class_Acc: 0.4400
- 4class_F1_macro: 0.3891
- 4class_F1_weighted: 0.4242
- 12class_Acc: 0.0900
- 12class_Top1: 0.5200
- 12class_Top3: 0.6700
- 12class_F1_macro: 0.2020
- 12class_F1_weighted: 0.4704
- 2class_n: 48.0000
- 4class_n: 100.0000
- 12class_n: 100.0000
- Overall: 0.4990

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 37 | 0.0000 | 0.9189 |
| F42 | 3 | 0.0000 | 0.3333 |
| somatized_expression | 100 | 0.0000 | 0.5200 |
