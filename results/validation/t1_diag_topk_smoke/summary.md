# Run Summary: t1_diag_topk_smoke

- Dataset: lingxidiag16k
- Cases: 50

## Metrics

### diagnosis
- accuracy: 0.0800
- top1_accuracy: 0.5000
- top3_accuracy: 0.6000
- macro_f1: 0.2002
- weighted_f1: 0.4633
- overall: 0.3687

### comorbidity
- hamming_accuracy: 0.3300
- subset_accuracy: 0.0800
- comorbidity_detection_f1: 0.1333
- label_coverage: 0.5700
- label_precision: 0.3400
- avg_predicted_labels: 1.8200
- avg_gold_labels: 1.0800

### four_class
- accuracy: 0.3600
- macro_f1: 0.2506
- weighted_f1: 0.3332
- n_cases: 50.0000

### table4
- 2class_Acc: 0.6923
- 2class_F1_macro: 0.7077
- 2class_F1_weighted: 0.7361
- 4class_Acc: 0.4400
- 4class_F1_macro: 0.4160
- 4class_F1_weighted: 0.4290
- 12class_Acc: 0.0800
- 12class_Top1: 0.5000
- 12class_Top3: 0.6000
- 12class_F1_macro: 0.2550
- 12class_F1_weighted: 0.4641
- 2class_n: 26.0000
- 4class_n: 50.0000
- 12class_n: 50.0000
- Overall: 0.4837

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 19 | 0.0526 | 0.8421 |
| F42 | 1 | 0.0000 | 0.0000 |
| somatized_expression | 50 | 0.1000 | 0.5000 |
