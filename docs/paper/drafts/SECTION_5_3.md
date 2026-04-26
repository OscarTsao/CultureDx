# Section 5.3 — Cross-Dataset Bias Robustness

We evaluate whether the MAS pipeline mitigates a specific diagnostic error-asymmetry pattern under cross-dataset distribution shift. On MDD-5k synthetic vignettes, the single-LLM baseline (Qwen3-32B-AWQ) collapses asymmetrically: 189 F41→F32 errors versus 1 F32→F41 error, an asymmetry ratio of 189× in the bias-transfer analysis. We pair the ratio with raw counts because a denominator of 1 makes the ratio mathematically unstable; the substantive observation is the directional collapse, not the ratio magnitude alone. This bias pattern is the property §5.3 examines.

## Cascade across pipeline states

The MDD-5k F32/F41 asymmetry observed under successive pipeline states is reported descriptively below. Each row corresponds to the asymmetry measured under a specific pipeline configuration and paper artifact; we do not provide per-fix ablation evidence, so we do not attribute the change between any two adjacent rows to a single repair.

| System                        | F41→F32 | F32→F41 |  Ratio |
| ----------------------------- | ------: | ------: | -----: |
| Single LLM (Qwen3-32B-AWQ)    |     189 |       1 |   189× |
| MAS T1 baseline               |     152 |      17 |  8.94× |
| MAS R6v2 (somatization-aware) |     145 |      26 |  5.58× |
| MAS ICD-10 v4 (current)       |     151 |      38 |  3.97× |

The current paper-contract result is **MAS ICD-10 v4: 151/38 = 3.97× (95% bootstrap CI [2.82, 6.08])**, a 47.7-fold reduction in the asymmetry ratio relative to the single-LLM baseline. The bootstrap CI is reported only for the v4 ICD-10 endpoint; the historical cascade is reported descriptively across system states because pre-v4 baselines were not re-bootstrapped under the current evaluation contract. R6v2 (5.58×) is retained as a cascade step documenting the somatization-aware prompt-mitigation checkpoint; MAS ICD-10 v4 is the current best asymmetry result, not R6v2.

## DSM-5 v0 explicitly excluded from this claim

Switching to DSM-5 v0 reasoning increases the MDD-5k asymmetry to 181/25 = 7.24× (95% CI [5.03, 11.38]). A paired bootstrap of (DSM-5 − ICD-10) on MDD-5k gives Δratio +3.24, 95% CI [+1.12, +6.89]; the same paired bootstrap on LingxiDiag-16K gives +3.13 [+1.12, +7.21]. Both intervals exclude 0, so the directional widening from ICD-10 to DSM-5 is statistically detectable under paired bootstrap. We therefore exclude DSM-5 v0 from this bias-robustness claim and report it as a dual-standard audit trade-off in §5.4. Both-mode results inherit ICD-10 by architectural pass-through and are not an ICD-10/DSM-5 ensemble.

## Relation to other findings

This bias-robustness result does not contradict the §5.1 accuracy-parity result: Top-1 parity and F32/F41 error asymmetry measure different deployment properties, and the MAS pipeline is retained for the second, not the first. The 11.9% MAS feature-importance share documented in §5.2 is consistent with MAS having limited measured split utility for stacker Top-1; it does not negate MAS's role as an auditable reasoning pipeline for cross-dataset bias analysis. Finally, 3.97× remains an asymmetric error pattern, not a resolved one — F41→F32 misclassification remains the dominant direction within this F32/F41 error pair under MDD-5k shift — and we document this residual asymmetry as a limitation in §7.5.
