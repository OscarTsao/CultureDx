# Run Summary: lingxi_dsm5_n1000

- Dataset: lingxidiag16k
- Cases: 1000

## Metrics

### table4
- 2class_Acc: 0.7674
- 2class_F1_macro: 0.7353
- 2class_F1_weighted: 0.7937
- 4class_Acc: 0.4580
- 4class_F1_macro: 0.3637
- 4class_F1_weighted: 0.3775
- 12class_Acc: 0.4190
- 12class_Top1: 0.4710
- 12class_Top3: 0.8030
- 12class_F1_macro: 0.1654
- 12class_F1_weighted: 0.3928
- 2class_n: 473.0000
- 4class_n: 1000.0000
- 12class_n: 1000.0000
- Overall: 0.5224

### diagnostics_internal
- diagnosis: {'accuracy': 0.423, 'top1_accuracy': 0.471, 'top3_accuracy': 0.471, 'macro_f1': 0.20432117844889108, 'weighted_f1': 0.42278761134825005, 'overall': 0.39842175795942814}
- comorbidity: {'hamming_accuracy': 0.4485, 'subset_accuracy': 0.423, 'comorbidity_detection_f1': 0.0, 'label_coverage': 0.4485, 'label_precision': 0.475, 'avg_predicted_labels': 1.0, 'avg_gold_labels': 1.091}
- four_class: {'accuracy': 0.363, 'macro_f1': 0.20270966546195904, 'weighted_f1': 0.25854011676396993, 'n_cases': 1000}

### metric_definitions
- paper_canonical_top1: table4.12class_Top1 (multi-label paper alignment)
- diagnostics_internal.diagnosis.top1_accuracy: primary == first gold (single-label, deprecated for paper citation)
- diagnostics_internal.pilot_comparison_top1: parent(primary) == parent(first gold) (single-label parent)

## Slice Metrics

| slice | cases | abstention_rate | top1_accuracy |
|---|---:|---:|---:|
| F32 | 370 | 0.0000 | 0.8811 |
| F42 | 36 | 0.0000 | 0.1944 |
| somatized_expression | 998 | 0.0000 | 0.4709 |
| direct_expression | 2 | 0.0000 | 0.5000 |
