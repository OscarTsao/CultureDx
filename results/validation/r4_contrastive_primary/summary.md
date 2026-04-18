# Run Summary: r4_contrastive_primary

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.0560
- top1_accuracy: 0.4730
- top3_accuracy: 0.6260
- macro_f1: 0.1873
- weighted_f1: 0.4161
- overall: 0.3517

### comorbidity
- hamming_accuracy: 0.3357
- subset_accuracy: 0.0570
- comorbidity_detection_f1: 0.1583
- label_coverage: 0.6047
- label_precision: 0.3455
- avg_predicted_labels: 1.8490
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3730
- macro_f1: 0.2553
- weighted_f1: 0.3273
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.7590
- 2class_F1_macro: 0.7216
- 2class_F1_weighted: 0.7819
- 4class_Acc: 0.4440
- 4class_F1_macro: 0.4092
- 4class_F1_weighted: 0.4277
- 12class_Acc: 0.0540
- 12class_Top1: 0.4750
- 12class_Top3: 0.6270
- 12class_F1_macro: 0.1903
- 12class_F1_weighted: 0.4584
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.4862

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0622 | 0.8757 |
| F42 | 36 | 0.0000 | 0.4444 |
| somatized_expression | 998 | 0.0852 | 0.4729 |
| direct_expression | 2 | 0.5000 | 0.5000 |
