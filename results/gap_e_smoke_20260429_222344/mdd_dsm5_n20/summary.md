# Run Summary: mdd_dsm5_n20

- Dataset: mdd5k
- Cases: 20

## Metrics

### diagnostics_internal
- diagnosis: {'accuracy': 0.6, 'top1_accuracy': 0.6, 'top3_accuracy': 0.6, 'macro_f1': 0.315018315018315, 'weighted_f1': 0.5377289377289377, 'overall': 0.5305494505494505}
- comorbidity: {'hamming_accuracy': 0.625, 'subset_accuracy': 0.6, 'comorbidity_detection_f1': 0.0, 'label_coverage': 0.625, 'label_precision': 0.65, 'avg_predicted_labels': 1.0, 'avg_gold_labels': 1.1}

### metric_definitions
- paper_canonical_top1: table4.12class_Top1 (multi-label paper alignment)
- diagnostics_internal.diagnosis.top1_accuracy: primary == first gold (single-label, deprecated for paper citation)
- diagnostics_internal.pilot_comparison_top1: parent(primary) == parent(first gold) (single-label parent)

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 9 | 0.0000 | 0.8889 |
| F42 | 2 | 0.0000 | 0.5000 |
| somatized_expression | 20 | 0.0000 | 0.6000 |
