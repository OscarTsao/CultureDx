# Run Summary: mdd_both_n925

- Dataset: mdd5k
- Cases: 925

## Metrics

### diagnostics_internal
- diagnosis: {'accuracy': 0.5416216216216216, 'top1_accuracy': 0.5848648648648649, 'top3_accuracy': 0.5848648648648649, 'macro_f1': 0.20577153483846497, 'weighted_f1': 0.5308778899614535, 'overall': 0.48960015523025396}
- comorbidity: {'hamming_accuracy': 0.5686486486486486, 'subset_accuracy': 0.5416216216216216, 'comorbidity_detection_f1': 0.0, 'label_coverage': 0.5686486486486486, 'label_precision': 0.5967567567567568, 'avg_predicted_labels': 1.0, 'avg_gold_labels': 1.0908108108108108}

### metric_definitions
- paper_canonical_top1: table4.12class_Top1 (multi-label paper alignment)
- diagnostics_internal.diagnosis.top1_accuracy: primary == first gold (single-label, deprecated for paper citation)
- diagnostics_internal.pilot_comparison_top1: parent(primary) == parent(first gold) (single-label parent)

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 410 | 0.0000 | 0.8780 |
| F33 | 2 | 0.0000 | 0.0000 |
| F42 | 21 | 0.0000 | 0.4762 |
| somatized_expression | 925 | 0.0000 | 0.5849 |
