# Run Summary: dtv_dev_hpo

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### diagnosis
- accuracy: 0.5998
- top1_accuracy: 0.5998
- top3_accuracy: 0.7078
- macro_f1: 0.2899
- weighted_f1: 0.5629
- overall: 0.5520

### comorbidity
- hamming_accuracy: 0.3954
- subset_accuracy: 0.0882
- comorbidity_detection_f1: 0.1927
- label_coverage: 0.6845
- label_precision: 0.4206
- avg_predicted_labels: 1.8181
- avg_gold_labels: 1.1235

### four_class
- accuracy: 0.3580
- macro_f1: 0.2536
- weighted_f1: 0.3253
- n_cases: 1000.0000

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 385 | 0.0000 | 0.8545 |
| F42 | 34 | 0.0000 | 0.5882 |
| somatized_expression | 999 | 0.0000 | 0.5993 |
| direct_expression | 1 | 0.0000 | 1.0000 |
