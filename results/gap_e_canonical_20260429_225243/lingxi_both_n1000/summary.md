# Run Summary: lingxi_both_n1000

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### table4
- 2class_Acc: 0.7780
- 2class_F1_macro: 0.7680
- 2class_F1_weighted: 0.8096
- 4class_Acc: 0.4510
- 4class_F1_macro: 0.3645
- 4class_F1_weighted: 0.3778
- 12class_Acc: 0.4520
- 12class_Top1: 0.5070
- 12class_Top3: 0.8000
- 12class_F1_macro: 0.1845
- 12class_F1_weighted: 0.4298
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.5384

### diagnostics_internal
- diagnosis: {'accuracy': 0.453, 'top1_accuracy': 0.502, 'top3_accuracy': 0.502, 'macro_f1': 0.2230418762354871, 'weighted_f1': 0.45155291535324676, 'overall': 0.4263189583177468}
- comorbidity: {'hamming_accuracy': 0.4799999999999999, 'subset_accuracy': 0.453, 'comorbidity_detection_f1': 0.0, 'label_coverage': 0.4799999999999999, 'label_precision': 0.508, 'avg_predicted_labels': 1.0, 'avg_gold_labels': 1.091}
- four_class: {'accuracy': 0.368, 'macro_f1': 0.20650846003271392, 'weighted_f1': 0.2625701230793983, 'n_cases': 1000}

### metric_definitions
- paper_canonical_top1: table4.12class_Top1 (multi-label paper alignment)
- diagnostics_internal.diagnosis.top1_accuracy: primary == first gold (single-label, deprecated for paper citation)
- diagnostics_internal.pilot_comparison_top1: parent(primary) == parent(first gold) (single-label parent)

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.8378 |
| F42 | 36 | 0.0000 | 0.5000 |
| somatized_expression | 998 | 0.0000 | 0.5020 |
| direct_expression | 2 | 0.0000 | 0.5000 |
