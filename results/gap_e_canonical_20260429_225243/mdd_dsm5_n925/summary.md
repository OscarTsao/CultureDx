# Run Summary: mdd_dsm5_n925

- Dataset: mdd5k
- Cases: 925

## Metrics

### diagnostics_internal
- diagnosis: {'accuracy': 0.5286486486486487, 'top1_accuracy': 0.5718918918918919, 'top3_accuracy': 0.5718918918918919, 'macro_f1': 0.1950020769507863, 'weighted_f1': 0.5056021978742641, 'overall': 0.47460734145149663}
- comorbidity: {'hamming_accuracy': 0.554954954954955, 'subset_accuracy': 0.5286486486486487, 'comorbidity_detection_f1': 0.0, 'label_coverage': 0.554954954954955, 'label_precision': 0.5816216216216217, 'avg_predicted_labels': 1.0, 'avg_gold_labels': 1.0908108108108108}

### metric_definitions
- paper_canonical_top1: table4.12class_Top1 (multi-label paper alignment)
- diagnostics_internal.diagnosis.top1_accuracy: primary == first gold (single-label, deprecated for paper citation)
- diagnostics_internal.pilot_comparison_top1: parent(primary) == parent(first gold) (single-label parent)

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 410 | 0.0000 | 0.9268 |
| F33 | 2 | 0.0000 | 0.0000 |
| F42 | 21 | 0.0000 | 0.2381 |
| somatized_expression | 925 | 0.0000 | 0.5719 |
