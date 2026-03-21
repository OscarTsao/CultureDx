# CultureDx Bootstrap Confidence Intervals

**Bootstrap parameters:** B=10000 replicates, seed=42, 95% CI (percentile method)
**Parent-code matching:** F32 gold matched by F32/F33 predictions.

## Table 1: Main Results with 95% Bootstrap CIs

> Metrics computed on N=200 per dataset. Parent-code matching: F32 gold is satisfied by F32/F33 predictions. All CIs use B=10,000 bootstrap replicates, percentile method, seed=42.

| Dataset | Mode | N | Top-1 Acc [95% CI] | F41 Recall [95% CI] | F41 n | F32 Recall [95% CI] | F32 n | Macro F1 [95% CI] | ECE [95% CI] |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LingxiDiag (Baseline) | HiED | 200 | 36.0% [29.5%, 42.5%] | 18.3% [9.9%, 26.8%] | 71 | 77.0% [67.6%, 86.5%] | 74 | 0.082 [0.064, 0.110] | 0.399 [0.326, 0.472] |
| LingxiDiag (Baseline) | PsyCoT | 200 | 41.0% [34.5%, 48.0%] | 35.2% [23.9%, 46.5%] | 71 | 74.3% [63.5%, 83.8%] | 74 | 0.094 [0.076, 0.129] | 0.343 [0.271, 0.417] |
| LingxiDiag (Baseline) | Single | 200 | 41.5% [34.5%, 48.5%] | 25.4% [15.5%, 35.2%] | 71 | 85.1% [77.0%, 93.2%] | 74 | 0.078 [0.054, 0.117] | 0.445 [0.376, 0.513] |
| LingxiDiag (V10) | HiED | 200 | 41.0% [34.0%, 48.0%] | 38.0% [26.8%, 49.3%] | 71 | 71.6% [60.8%, 81.1%] | 74 | 0.091 [0.074, 0.124] | 0.367 [0.296, 0.440] |
| LingxiDiag (V10) | PsyCoT | 200 | 38.0% [31.5%, 44.5%] | 32.4% [21.1%, 43.7%] | 71 | 68.9% [58.1%, 79.7%] | 74 | 0.084 [0.068, 0.116] | 0.386 [0.315, 0.456] |
| MDD-5k (Baseline) | HiED | 200 | 51.5% [44.5%, 58.5%] | 38.8% [26.9%, 50.7%] | 67 | 84.1% [76.1%, 90.9%] | 88 | 0.072 [0.060, 0.120] | 0.308 [0.236, 0.380] |
| MDD-5k (Baseline) | PsyCoT | 200 | 50.0% [43.0%, 57.0%] | 58.2% [46.3%, 70.1%] | 67 | 67.0% [56.8%, 76.1%] | 88 | 0.067 [0.055, 0.115] | 0.328 [0.258, 0.399] |
| MDD-5k (Baseline) | Single | 200 | 53.5% [46.5%, 60.5%] | 20.9% [11.9%, 31.3%] | 67 | 100.0% [100.0%, 100.0%] | 88 | 0.130 [0.084, 0.200] | 0.382 [0.315, 0.452] |
| LingxiDiag (Baseline) | HiED+Single (Ensemble) | 200 | 39.0% [32.0%, 46.0%] | 22.5% [12.7%, 32.4%] | 71 | 81.1% [71.6%, 89.2%] | 74 | 0.064 [0.055, 0.100] | 0.420 [0.351, 0.486] |
| MDD-5k (Baseline) | HiED+Single (Ensemble) | 200 | 55.5% [48.5%, 62.5%] | 38.8% [28.4%, 50.7%] | 67 | 93.2% [87.5%, 97.7%] | 88 | 0.077 [0.065, 0.130] | 0.309 [0.240, 0.377] |

## Table 2: V10 vs Baseline Delta with 95% Bootstrap CIs

> Delta = V10 top-1 correct rate minus baseline top-1 correct rate, computed per case (paired bootstrap). Sig. = 95% CI excludes 0.

| Dataset | Mode | Baseline Top-1 | V10 Top-1 | Delta Top-1 [95% CI] | Interpretation |
| :--- | :--- | ---: | ---: | ---: | :--- |
| LingxiDiag | HiED | 36.0% | 41.0% | +5.0% [+0.0%, +10.0%] | n.s. |
| LingxiDiag | PsyCoT | 41.0% | 38.0% | -3.0% [-8.0%, +2.0%] | n.s. |

## Table 3: ECE with 95% Bootstrap CIs

> ECE computed on non-abstaining predictions only. Bootstrap resamples confidence/correctness pairs jointly.

| Dataset | Mode | N (non-abstain) | ECE [95% CI] |
| :--- | :--- | ---: | ---: |
| LingxiDiag (Baseline) | HiED | — | 0.399 [0.326, 0.472] |
| LingxiDiag (Baseline) | PsyCoT | — | 0.343 [0.271, 0.417] |
| LingxiDiag (Baseline) | Single | — | 0.445 [0.376, 0.513] |
| LingxiDiag (V10) | HiED | — | 0.367 [0.296, 0.440] |
| LingxiDiag (V10) | PsyCoT | — | 0.386 [0.315, 0.456] |
| MDD-5k (Baseline) | HiED | — | 0.308 [0.236, 0.380] |
| MDD-5k (Baseline) | PsyCoT | — | 0.328 [0.258, 0.399] |
| MDD-5k (Baseline) | Single | — | 0.382 [0.315, 0.452] |
| LingxiDiag (Baseline) | HiED+Single (Ensemble) | — | 0.420 [0.351, 0.486] |
| MDD-5k (Baseline) | HiED+Single (Ensemble) | — | 0.309 [0.240, 0.377] |

## Notes

- **HiED+Single (Ensemble):** HiED primary prediction used; Single mode prediction substituted when HiED abstains.
- **F32/F33 grouping:** Gold F32 is matched by predicted F32 or F33 (these are clinically equivalent at the parent-code level in ICD-10-CM).
- **Abstentions:** Treated as incorrect for accuracy; excluded from ECE.
- **Macro F1:** Labels include 'ABSTAIN' for abstaining predictions; class-averaged including rare labels.
