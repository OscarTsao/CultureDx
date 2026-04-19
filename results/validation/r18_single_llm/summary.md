# Run Summary: r18_single_llm

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.0190
- top1_accuracy: 0.4650
- top3_accuracy: 0.6390
- macro_f1: 0.2066
- weighted_f1: 0.4167
- overall: 0.3493

### comorbidity
- hamming_accuracy: 0.3110
- subset_accuracy: 0.0190
- comorbidity_detection_f1: 0.1562
- label_coverage: 0.6242
- label_precision: 0.3183
- avg_predicted_labels: 2.0940
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3280
- macro_f1: 0.1920
- weighted_f1: 0.2652
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.7526
- 2class_F1_macro: 0.7080
- 2class_F1_weighted: 0.7746
- 4class_Acc: 0.4040
- 4class_F1_macro: 0.3788
- 4class_F1_weighted: 0.3997
- 12class_Acc: 0.2490
- 12class_Top1: 0.4780
- 12class_Top3: 0.5750
- 12class_F1_macro: 0.1667
- 12class_F1_weighted: 0.4141
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.4819

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.8541 |
| F42 | 36 | 0.0000 | 0.4444 |
| somatized_expression | 998 | 0.0000 | 0.4659 |
| direct_expression | 2 | 0.0000 | 0.0000 |
