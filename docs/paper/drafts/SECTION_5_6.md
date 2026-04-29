# Section 5.6 — Confidence-Gated Ensemble (Null Result)

We also evaluated a confidence-gated MAS/TF-IDF ensemble as a negative design finding.
Seven candidate rules — `tfidf_only`, `mas_only`, and five class-routing variants that send F32, F32+F41, F32+F41+F45, F32+F41+F42, or F32+F41+F42+F45 cases to MAS while keeping TF-IDF as the default — were tuned on a 500-case development split.
The dev F1_macro winner was the trivial `tfidf_only` rule (0.331), with all five class-routing variants underperforming pure TF-IDF on dev F1_macro by 5–9 percentage points.
On the held-out 500-case test split, the selected rule's predictions were identical to TF-IDF-only: Top-1 = 0.608 and macro-F1 = 0.296 for both, with paired McNemar p = 1.0 (ensemble-only = 0, TF-IDF-only = 0).
We therefore do not claim an accuracy gain from confidence-gated ensembling.
This null result supports the framing used throughout §5: the MAS pipeline is not retained as a case-level override mechanism for in-domain Top-1 accuracy, but for the audit, bias, and triage properties evaluated in §§5.3–6.2.
