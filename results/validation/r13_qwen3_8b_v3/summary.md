# Run Summary: r13_qwen3_8b_v3

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.0220
- top1_accuracy: 0.4050
- top3_accuracy: 0.4800
- macro_f1: 0.1513
- weighted_f1: 0.3367
- overall: 0.2790

### comorbidity
- hamming_accuracy: 0.2472
- subset_accuracy: 0.0240
- comorbidity_detection_f1: 0.1457
- label_coverage: 0.4630
- label_precision: 0.2545
- avg_predicted_labels: 1.8610
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3360
- macro_f1: 0.1881
- weighted_f1: 0.2589
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.7019
- 2class_F1_macro: 0.6137
- 2class_F1_weighted: 0.7149
- 4class_Acc: 0.4130
- 4class_F1_macro: 0.3244
- 4class_F1_weighted: 0.3550
- 12class_Acc: 0.0240
- 12class_Top1: 0.4080
- 12class_Top3: 0.4810
- 12class_F1_macro: 0.1680
- 12class_F1_weighted: 0.3385
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.4129

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.8703 |
| F42 | 36 | 0.0000 | 0.3333 |
| somatized_expression | 998 | 0.0000 | 0.4048 |
| direct_expression | 2 | 0.0000 | 0.5000 |
