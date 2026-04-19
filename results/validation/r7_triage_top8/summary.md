# Run Summary: r7_triage_top8

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.0620
- top1_accuracy: 0.4960
- top3_accuracy: 0.6430
- macro_f1: 0.2103
- weighted_f1: 0.4574
- overall: 0.3737

### comorbidity
- hamming_accuracy: 0.3469
- subset_accuracy: 0.0620
- comorbidity_detection_f1: 0.1568
- label_coverage: 0.6217
- label_precision: 0.3575
- avg_predicted_labels: 1.8450
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3430
- macro_f1: 0.2436
- weighted_f1: 0.3146
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.7357
- 2class_F1_macro: 0.7352
- 2class_F1_weighted: 0.7833
- 4class_Acc: 0.4220
- 4class_F1_macro: 0.4029
- 4class_F1_weighted: 0.4217
- 12class_Acc: 0.0590
- 12class_Top1: 0.4950
- 12class_Top3: 0.6420
- 12class_F1_macro: 0.2170
- 12class_F1_weighted: 0.4588
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.4884

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0676 | 0.8081 |
| F42 | 36 | 0.0556 | 0.5000 |
| somatized_expression | 998 | 0.1002 | 0.4960 |
| direct_expression | 2 | 0.5000 | 0.5000 |
