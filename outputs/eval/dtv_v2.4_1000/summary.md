# Run Summary: dtv_v2.4_1000

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.2980
- top1_accuracy: 0.5350
- top3_accuracy: 0.6220
- macro_f1: 0.2135
- weighted_f1: 0.4732
- overall: 0.4283

### comorbidity
- hamming_accuracy: 0.4579
- subset_accuracy: 0.2990
- comorbidity_detection_f1: 0.1449
- label_coverage: 0.5949
- label_precision: 0.4800
- avg_predicted_labels: 1.3940
- avg_gold_labels: 1.0930

### four_class
- accuracy: 0.3820
- macro_f1: 0.2606
- weighted_f1: 0.3285
- n_cases: 1000.0000

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 369 | 0.0000 | 0.8889 |
| F42 | 35 | 0.0000 | 0.4857 |
| somatized_expression | 995 | 0.0000 | 0.5357 |
| direct_expression | 5 | 0.0000 | 0.4000 |
