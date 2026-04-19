# Run Summary: r21_evidence_stacked

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.0700
- top1_accuracy: 0.3370
- top3_accuracy: 0.3670
- macro_f1: 0.1555
- weighted_f1: 0.2749
- overall: 0.2409

### comorbidity
- hamming_accuracy: 0.2149
- subset_accuracy: 0.0710
- comorbidity_detection_f1: 0.1622
- label_coverage: 0.3525
- label_precision: 0.2210
- avg_predicted_labels: 1.5060
- avg_gold_labels: 1.0910

### four_class
- accuracy: 0.2450
- macro_f1: 0.1293
- weighted_f1: 0.2061
- n_cases: 1000.0000

### table4
- 2class_Acc: 0.5095
- 2class_F1_macro: 0.4188
- 2class_F1_weighted: 0.5769
- 4class_Acc: 0.4330
- 4class_F1_macro: 0.2735
- 4class_F1_weighted: 0.3326
- 12class_Acc: 0.0670
- 12class_Top1: 0.3340
- 12class_Top3: 0.3630
- 12class_F1_macro: 0.1524
- 12class_F1_weighted: 0.2585
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.3381

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.2649 | 0.7054 |
| F42 | 36 | 0.4444 | 0.3611 |
| somatized_expression | 998 | 0.4449 | 0.3377 |
| direct_expression | 2 | 1.0000 | 0.0000 |
