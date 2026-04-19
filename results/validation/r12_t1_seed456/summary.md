# Run Summary: r12_t1_seed456

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.0590
- top1_accuracy: 0.5040
- top3_accuracy: 0.6300
- macro_f1: 0.2075
- weighted_f1: 0.4636
- overall: 0.3728

### comorbidity
- hamming_accuracy: 0.3385
- subset_accuracy: 0.0600
- comorbidity_detection_f1: 0.1585
- label_coverage: 0.6072
- label_precision: 0.3485
- avg_predicted_labels: 1.8480
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3720
- macro_f1: 0.2558
- weighted_f1: 0.3266
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.7674
- 2class_F1_macro: 0.7658
- 2class_F1_weighted: 0.8076
- 4class_Acc: 0.4540
- 4class_F1_macro: 0.4216
- 4class_F1_weighted: 0.4405
- 12class_Acc: 0.0570
- 12class_Top1: 0.5050
- 12class_Top3: 0.6300
- 12class_F1_macro: 0.1904
- 12class_F1_weighted: 0.4618
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.5001

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0622 | 0.8351 |
| F42 | 36 | 0.0000 | 0.5000 |
| somatized_expression | 998 | 0.0852 | 0.5040 |
| direct_expression | 2 | 0.5000 | 0.5000 |
