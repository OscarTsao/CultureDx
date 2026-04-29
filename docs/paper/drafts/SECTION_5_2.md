# Section 5.2 — Feature Ablation: TF-IDF vs MAS Contribution

A feature-block analysis of the Stacker LGBM model shows that supervised TF-IDF-derived features account for 88.1% of total feature importance, while MAS-derived features account for the remaining 11.9%.
This distribution is consistent with the §5.1 benchmark result: the stacker reaches Top-1 parity with the reproduced TF-IDF baseline, not superiority, while most measured split utility comes from the supervised feature block.
McNemar's test on the paired predictions of Stacker LGBM versus a TF-IDF-only stacker variant gives p ≈ 1.0, indicating that MAS feature inclusion does not produce a statistically detectable Top-1 improvement at our sample size.
We treat this 11.9% importance share as descriptive rather than as causal attribution: feature-importance values reflect tree-split utility within the LGBM model, not a counterfactual estimate of MAS necessity.
The case for retaining the MAS block does not rest on Top-1; it rests on the system-oriented audit properties examined in subsequent sections — bias robustness under distribution shift (§5.3), dual-standard audit traces (§5.4), and disagreement-driven triage signals (§§6.1–6.2).
