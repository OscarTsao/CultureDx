# Run Summary: r16_bypass_logic

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.0450
- top1_accuracy: 0.5230
- top3_accuracy: 0.6670
- macro_f1: 0.2270
- weighted_f1: 0.4625
- overall: 0.3849

### comorbidity
- hamming_accuracy: 0.3506
- subset_accuracy: 0.0470
- comorbidity_detection_f1: 0.1596
- label_coverage: 0.6437
- label_precision: 0.3605
- avg_predicted_labels: 1.9290
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3970
- macro_f1: 0.2533
- weighted_f1: 0.3348
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.8203
- 2class_F1_macro: 0.7957
- 2class_F1_weighted: 0.8355
- 4class_Acc: 0.4480
- 4class_F1_macro: 0.3968
- 4class_F1_weighted: 0.4263
- 12class_Acc: 0.0470
- 12class_Top1: 0.5270
- 12class_Top3: 0.6690
- 12class_F1_macro: 0.2209
- 12class_F1_weighted: 0.4524
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.5126

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.8919 |
| F42 | 36 | 0.0000 | 0.5000 |
| somatized_expression | 998 | 0.0040 | 0.5230 |
| direct_expression | 2 | 0.0000 | 0.5000 |
