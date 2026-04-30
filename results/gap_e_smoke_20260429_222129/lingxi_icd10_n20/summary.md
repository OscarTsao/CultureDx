# Run Summary: lingxi_icd10_n20

- Dataset: lingxidiag16k
- Cases: 20

## Metrics

### table4
- 2class_Acc: 0.8750
- 2class_F1_macro: 0.9286
- 2class_F1_weighted: 0.9286
- 4class_Acc: 0.3500
- 4class_F1_macro: 0.3125
- 4class_F1_weighted: 0.2750
- 12class_Acc: 0.4500
- 12class_Top1: 0.5500
- 12class_Top3: 0.7500
- 12class_F1_macro: 0.1078
- 12class_F1_weighted: 0.4813
- 2class_n: 8.0000
- 4class_n: 20.0000
- 12class_n: 20.0000
- Overall: 0.5463

### diagnostics_internal
- diagnosis: {'accuracy': 0.45, 'top1_accuracy': 0.55, 'top3_accuracy': 0.55, 'macro_f1': 0.23137254901960783, 'weighted_f1': 0.4964705882352941, 'overall': 0.45556862745098037}
- comorbidity: {'hamming_accuracy': 0.5, 'subset_accuracy': 0.45, 'comorbidity_detection_f1': 0.0, 'label_coverage': 0.5, 'label_precision': 0.55, 'avg_predicted_labels': 1.0, 'avg_gold_labels': 1.1}
- four_class: {'accuracy': 0.35, 'macro_f1': 0.2254545454545455, 'weighted_f1': 0.2254545454545455, 'n_cases': 20}

### metric_definitions
- paper_canonical_top1: table4.12class_Top1 (multi-label paper alignment)
- diagnostics_internal.diagnosis.top1_accuracy: primary == first gold (single-label, deprecated for paper citation)
- diagnostics_internal.pilot_comparison_top1: parent(primary) == parent(first gold) (single-label parent)

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 6 | 0.0000 | 0.8333 |
| somatized_expression | 20 | 0.0000 | 0.5500 |
