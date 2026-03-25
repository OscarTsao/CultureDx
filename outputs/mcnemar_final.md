# McNemar Exact Test Results (Final Sweep)

**Family-wise alpha:** 0.05  
**Bonferroni-corrected alpha:** 0.0083 (6 comparisons)  
**Parent-code matching:** Gold F32.x matched by F32/F33; Gold F41.x matched by F41. Abstain = incorrect.

| Dataset | Comparison | A_top1 | B_top1 | b (A✓B✗) | c (A✗B✓) | χ² | p-value | Bonf. sig |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| LingxiDiag | Evidence effect | 44.5% | 40.5% | 21 | 13 | 1.44 | 0.2295 |  |
| LingxiDiag | Somatization effect | 44.5% | 41.0% | 15 | 8 | 1.57 | 0.2100 |  |
| LingxiDiag | MAS vs Single | 40.5% | 41.5% | 15 | 17 | 0.03 | 0.8601 |  |
| LingxiDiag | HiED vs PsyCoT | 40.5% | 41.0% | 9 | 10 | 0.00 | 1.0000 |  |
| LingxiDiag | MAS+ev vs Single+ev | 44.5% | 41.5% | 22 | 16 | 0.66 | 0.4177 |  |
| LingxiDiag | HiED+ev vs PsyCoT+ev | 44.5% | 41.0% | 23 | 16 | 0.92 | 0.3368 |  |
| MDD-5k | Evidence effect | 43.5% | 53.0% | 21 | 40 | 5.31 | 0.0204 |  |
| MDD-5k | Somatization effect | 43.5% | 43.0% | 5 | 4 | 0.00 | 1.0000 |  |
| MDD-5k | MAS vs Single | 53.0% | 53.5% | 15 | 16 | 0.00 | 1.0000 |  |
| MDD-5k | HiED vs PsyCoT | 53.0% | 53.5% | 14 | 15 | 0.00 | 1.0000 |  |
| MDD-5k | MAS+ev vs Single+ev | 43.5% | 45.5% | 31 | 35 | 0.14 | 0.7122 |  |
| MDD-5k | HiED+ev vs PsyCoT+ev | 43.5% | 43.0% | 9 | 8 | 0.00 | 1.0000 |  |

## Notes

- **b (A✓B✗):** Cases where condition A is correct and condition B is wrong (discordant favoring A).
- **c (A✗B✓):** Cases where condition A is wrong and condition B is correct (discordant favoring B).
- **χ²:** McNemar chi-squared statistic with continuity correction: (|b-c|-1)^2 / (b+c).
- **p-value:** Exact two-sided p-value from binomial test on discordant pairs (H0: b = c).
- **Bonf. sig:** ✔ if p < alpha_corrected.
