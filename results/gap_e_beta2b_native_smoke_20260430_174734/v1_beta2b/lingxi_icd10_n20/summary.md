# Run Summary: lingxi_icd10_n20

- Dataset: lingxidiag16k
- Cases: 20

## Metrics

### table4
- 2class_Acc: 0.8750
- 2class_F1_macro: 0.9286
- 2class_F1_weighted: 0.9286
- 4class_Acc: 0.4000
- 4class_F1_macro: 0.3563
- 4class_F1_weighted: 0.3100
- 12class_Acc: 0.4000
- 12class_Top1: 0.5000
- 12class_Top3: 0.7500
- 12class_F1_macro: 0.0984
- 12class_F1_weighted: 0.4356
- 2class_n: 8.0000
- 4class_n: 20.0000
- 12class_n: 20.0000
- Overall: 0.5439

### diagnostics_internal
- diagnosis: {'accuracy': 0.4, 'top1_accuracy': 0.5, 'top3_accuracy': 0.5, 'macro_f1': 0.21164021164021163, 'weighted_f1': 0.4523809523809524, 'overall': 0.41280423280423284}
- comorbidity: {'hamming_accuracy': 0.45, 'subset_accuracy': 0.4, 'comorbidity_detection_f1': 0.0, 'label_coverage': 0.45, 'label_precision': 0.5, 'avg_predicted_labels': 1.0, 'avg_gold_labels': 1.1}
- four_class: {'accuracy': 0.35, 'macro_f1': 0.23500000000000001, 'weighted_f1': 0.23500000000000001, 'n_cases': 20}

### metric_definitions
- paper_canonical_top1: table4.12class_Top1 (multi-label paper alignment)
- diagnostics_internal.diagnosis.top1_accuracy: primary == first gold (single-label, deprecated for paper citation)
- diagnostics_internal.pilot_comparison_top1: parent(primary) == parent(first gold) (single-label parent)

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 6 | 0.0000 | 0.8333 |
| somatized_expression | 20 | 0.0000 | 0.5000 |
