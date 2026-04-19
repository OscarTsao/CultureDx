# Run Summary: r15_no_rag

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.0540
- top1_accuracy: 0.5030
- top3_accuracy: 0.6240
- macro_f1: 0.2005
- weighted_f1: 0.4581
- overall: 0.3679

### comorbidity
- hamming_accuracy: 0.3361
- subset_accuracy: 0.0590
- comorbidity_detection_f1: 0.1553
- label_coverage: 0.6030
- label_precision: 0.3465
- avg_predicted_labels: 1.8540
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3790
- macro_f1: 0.2579
- weighted_f1: 0.3282
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.7759
- 2class_F1_macro: 0.7680
- 2class_F1_weighted: 0.8073
- 4class_Acc: 0.4590
- 4class_F1_macro: 0.4289
- 4class_F1_weighted: 0.4429
- 12class_Acc: 0.0570
- 12class_Top1: 0.5090
- 12class_Top3: 0.6270
- 12class_F1_macro: 0.1927
- 12class_F1_weighted: 0.4595
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.5025

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0514 | 0.8189 |
| F42 | 36 | 0.0556 | 0.5000 |
| somatized_expression | 998 | 0.0752 | 0.5030 |
| direct_expression | 2 | 0.5000 | 0.5000 |
