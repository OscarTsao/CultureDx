# Run Summary: dtv_test_final

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.5458
- top1_accuracy: 0.5458
- top3_accuracy: 0.6781
- macro_f1: 0.2181
- weighted_f1: 0.5021
- overall: 0.4979

### comorbidity
- hamming_accuracy: 0.3711
- subset_accuracy: 0.0750
- comorbidity_detection_f1: 0.1625
- label_coverage: 0.6531
- label_precision: 0.3914
- avg_predicted_labels: 1.8357
- avg_gold_labels: 1.1003

### four_class
- accuracy: 0.3570
- macro_f1: 0.2518
- weighted_f1: 0.3169
- n_cases: 1000.0000

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.8432 |
| F42 | 36 | 0.0000 | 0.5000 |
| somatized_expression | 998 | 0.0000 | 0.5459 |
| direct_expression | 2 | 0.0000 | 0.5000 |
