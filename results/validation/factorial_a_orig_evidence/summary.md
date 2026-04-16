# Run Summary: factorial_a_orig_evidence

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.2230
- top1_accuracy: 0.4380
- top3_accuracy: 0.4660
- macro_f1: 0.1942
- weighted_f1: 0.3688
- overall: 0.3380

### comorbidity
- hamming_accuracy: 0.3424
- subset_accuracy: 0.2230
- comorbidity_detection_f1: 0.1508
- label_coverage: 0.4452
- label_precision: 0.3595
- avg_predicted_labels: 1.3650
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.3530
- macro_f1: 0.1905
- weighted_f1: 0.2489
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.7421
- 2class_F1_macro: 0.6753
- 2class_F1_weighted: 0.7579
- 4class_Acc: 0.4460
- 4class_F1_macro: 0.3451
- 4class_F1_weighted: 0.3634
- 12class_Acc: 0.2230
- 12class_Top1: 0.4410
- 12class_Top3: 0.4690
- 12class_F1_macro: 0.1709
- 12class_F1_weighted: 0.3477
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.4529

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.9027 |
| F42 | 36 | 0.0000 | 0.4444 |
| somatized_expression | 998 | 0.0020 | 0.4379 |
| direct_expression | 2 | 0.0000 | 0.5000 |
