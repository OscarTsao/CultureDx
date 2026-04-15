# Run Summary: t1_triage_no_meta

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.2910
- top1_accuracy: 0.5290
- top3_accuracy: 0.6190
- macro_f1: 0.2024
- weighted_f1: 0.4667
- overall: 0.4216

### comorbidity
- hamming_accuracy: 0.4531
- subset_accuracy: 0.2910
- comorbidity_detection_f1: 0.1240
- label_coverage: 0.5960
- label_precision: 0.4730
- avg_predicted_labels: 1.4300
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3860
- macro_f1: 0.2629
- weighted_f1: 0.3315
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.8118
- 2class_F1_macro: 0.7950
- 2class_F1_weighted: 0.8285
- 4class_Acc: 0.4360
- 4class_F1_macro: 0.4069
- 4class_F1_weighted: 0.4180
- 12class_Acc: 0.2910
- 12class_Top1: 0.5300
- 12class_Top3: 0.6200
- 12class_F1_macro: 0.1732
- 12class_F1_weighted: 0.4507
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.5237

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.8568 |
| F42 | 36 | 0.0000 | 0.5278 |
| somatized_expression | 998 | 0.0000 | 0.5291 |
| direct_expression | 2 | 0.0000 | 0.5000 |
