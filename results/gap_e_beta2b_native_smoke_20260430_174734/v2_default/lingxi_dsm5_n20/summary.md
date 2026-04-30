# Run Summary: lingxi_dsm5_n20

- Dataset: lingxidiag16k
- Cases: 20

## Metrics

### table4
- 2class_Acc: 0.5000
- 2class_F1_macro: 0.5750
- 2class_F1_weighted: 0.5750
- 4class_Acc: 0.2000
- 4class_F1_macro: 0.1716
- 4class_F1_weighted: 0.1373
- 12class_Acc: 0.2500
- 12class_Top1: 0.3500
- 12class_Top3: 0.6500
- 12class_F1_macro: 0.0716
- 12class_F1_weighted: 0.2951
- 2class_n: 8.0000
- 4class_n: 20.0000
- 12class_n: 20.0000
- Overall: 0.3432

### diagnostics_internal
- diagnosis: {'accuracy': 0.25, 'top1_accuracy': 0.35, 'top3_accuracy': 0.35, 'macro_f1': 0.13233082706766916, 'weighted_f1': 0.3178947368421053, 'overall': 0.2800451127819549}
- comorbidity: {'hamming_accuracy': 0.3, 'subset_accuracy': 0.25, 'comorbidity_detection_f1': 0.0, 'label_coverage': 0.3, 'label_precision': 0.35, 'avg_predicted_labels': 1.0, 'avg_gold_labels': 1.1}
- four_class: {'accuracy': 0.2, 'macro_f1': 0.13725490196078433, 'weighted_f1': 0.13725490196078433, 'n_cases': 20}

### metric_definitions
- paper_canonical_top1: table4.12class_Top1 (multi-label paper alignment)
- diagnostics_internal.diagnosis.top1_accuracy: primary == first gold (single-label, deprecated for paper citation)
- diagnostics_internal.pilot_comparison_top1: parent(primary) == parent(first gold) (single-label parent)

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 6 | 0.0000 | 0.8333 |
| somatized_expression | 20 | 0.0000 | 0.3500 |
