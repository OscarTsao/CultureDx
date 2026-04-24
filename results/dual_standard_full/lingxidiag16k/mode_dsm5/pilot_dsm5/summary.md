# Run Summary: pilot_dsm5

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.0310
- top1_accuracy: 0.4710
- top3_accuracy: 0.5910
- macro_f1: 0.2043
- weighted_f1: 0.4228
- overall: 0.3440

### comorbidity
- hamming_accuracy: 0.3062
- subset_accuracy: 0.0330
- comorbidity_detection_f1: 0.1652
- label_coverage: 0.5718
- label_precision: 0.3135
- avg_predicted_labels: 1.9190
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3880
- macro_f1: 0.2554
- weighted_f1: 0.3391
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.7674
- 2class_F1_macro: 0.7353
- 2class_F1_weighted: 0.7937
- 4class_Acc: 0.4760
- 4class_F1_macro: 0.4292
- 4class_F1_weighted: 0.4575
- 12class_Acc: 0.0290
- 12class_Top1: 0.4710
- 12class_Top3: 0.5890
- 12class_F1_macro: 0.1882
- 12class_F1_weighted: 0.4210
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.4870

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.8811 |
| F42 | 36 | 0.0000 | 0.1944 |
| somatized_expression | 998 | 0.0000 | 0.4709 |
| direct_expression | 2 | 0.0000 | 0.5000 |
