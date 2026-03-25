# Cross-Lingual Evidence Gap Analysis

18-condition sweep: 3 modes x 3 evidence variants x 2 datasets.

## 1. Evidence Delta Summary (parent-normalized Top-1)

| Dataset | Mode | No Evidence | + Evidence | + Ev (no somat) | Delta(ev-no) | Delta(ev-ns) |
|---------|------|-------------|------------|-----------------|--------------|--------------|
| LingxiDiag | hied | 0.410 | 0.450 | 0.415 | +4.0pp | +3.5pp |
| LingxiDiag | psycot | 0.415 | 0.415 | 0.410 | +0.0pp | +0.5pp |
| LingxiDiag | single | 0.405 | 0.405 | 0.395 | +0.0pp | +1.0pp |
| MDD-5k | hied | 0.520 | 0.460 | 0.450 | -6.0pp | +1.0pp |
| MDD-5k | psycot | 0.510 | 0.450 | 0.475 | -6.0pp | -2.5pp |
| MDD-5k | single | 0.525 | 0.470 | 0.470 | -5.5pp | +0.0pp |

### Average delta across modes

| Dataset | Avg Delta(evidence vs none) Top-1 | Avg Delta(evidence vs no_somat) Top-1 |
|---------|-----------------------------------|---------------------------------------|
| LingxiDiag | +1.3pp | +1.7pp |
| MDD-5k | -5.8pp | -0.5pp |

## 2. Per-Disorder Top-1 Accuracy (HiED mode)

### LingxiDiag

| Disorder | N | No Evidence | + Evidence | + Ev (no somat) | Delta(ev-no) |
|----------|---|-------------|------------|-----------------|--------------|
| F31 | 2 | 0.000 | 0.000 | 0.000 | +0.0pp |
| F32 | 74 | 0.770 | 0.797 | 0.838 | +2.7pp |
| F39 | 12 | 0.000 | 0.000 | 0.000 | +0.0pp |
| F41 | 71 | 0.324 | 0.394 | 0.254 | +7.0pp |
| F42 | 5 | 0.400 | 0.600 | 0.600 | +20.0pp |
| F43 | 2 | 0.000 | 0.000 | 0.000 | +0.0pp |
| F45 | 2 | 0.000 | 0.000 | 0.000 | +0.0pp |
| F51 | 7 | 0.000 | 0.000 | 0.000 | +0.0pp |
| F98 | 6 | 0.000 | 0.000 | 0.000 | +0.0pp |
| Others | 17 | 0.000 | 0.000 | 0.000 | +0.0pp |
| Z71 | 2 | 0.000 | 0.000 | 0.000 | +0.0pp |

### MDD-5k

| Disorder | N | No Evidence | + Evidence | + Ev (no somat) | Delta(ev-no) |
|----------|---|-------------|------------|-----------------|--------------|
| F20 | 1 | 1.000 | 1.000 | 1.000 | +0.0pp |
| F22 | 1 | 0.000 | 1.000 | 1.000 | +100.0pp |
| F23 | 1 | 0.000 | 0.000 | 0.000 | +0.0pp |
| F28 | 1 | 0.000 | 1.000 | 1.000 | +100.0pp |
| F30 | 1 | 0.000 | 0.000 | 0.000 | +0.0pp |
| F31 | 2 | 0.000 | 0.000 | 0.000 | +0.0pp |
| F32 | 88 | 0.875 | 0.625 | 0.591 | -25.0pp |
| F34 | 1 | 1.000 | 0.000 | 1.000 | -100.0pp |
| F39 | 14 | 0.000 | 0.000 | 0.000 | +0.0pp |
| F41 | 67 | 0.343 | 0.478 | 0.478 | +13.4pp |
| F42 | 3 | 0.667 | 0.667 | 0.667 | +0.0pp |
| F43 | 2 | 0.000 | 0.000 | 0.000 | +0.0pp |
| F45 | 2 | 0.000 | 0.000 | 0.000 | +0.0pp |
| F48 | 1 | 0.000 | 0.000 | 0.000 | +0.0pp |
| F50 | 2 | 0.000 | 0.000 | 0.000 | +0.0pp |
| F51 | 4 | 0.000 | 0.000 | 0.000 | +0.0pp |
| F90 | 1 | 0.000 | 0.000 | 0.000 | +0.0pp |
| F93 | 1 | 0.000 | 0.000 | 0.000 | +0.0pp |
| F98 | 4 | 0.000 | 0.000 | 0.000 | +0.0pp |
| G47 | 1 | 0.000 | 0.000 | 0.000 | +0.0pp |
| Z71 | 2 | 0.000 | 0.000 | 0.000 | +0.0pp |

## 3. Prediction Flip Analysis (evidence vs no_evidence)

Good flip = wrong->right with evidence. Bad flip = right->wrong with evidence.

### Summary

| Dataset | Mode | Good Flips | Bad Flips | Net | Stable Correct | Stable Wrong |
|---------|------|------------|-----------|-----|----------------|--------------|
| LingxiDiag | hied | 21 | 13 | +8 | 69 | 97 |
| LingxiDiag | psycot | 14 | 14 | +0 | 69 | 103 |
| LingxiDiag | single | 15 | 15 | +0 | 66 | 104 |
| MDD-5k | hied | 25 | 37 | -12 | 67 | 71 |
| MDD-5k | psycot | 24 | 36 | -12 | 66 | 74 |
| MDD-5k | single | 5 | 16 | -11 | 89 | 90 |

### Per-disorder flips (HiED mode)

#### LingxiDiag

| Disorder | N | Good | Bad | Net | Stable-R | Stable-W |
|----------|---|------|-----|-----|----------|----------|
| F31 | 2 | 0 | 0 | +0 | 0 | 2 |
| F32 | 74 | 9 | 7 | +2 | 50 | 8 |
| F39 | 12 | 0 | 0 | +0 | 0 | 12 |
| F41 | 71 | 11 | 6 | +5 | 17 | 37 |
| F42 | 5 | 1 | 0 | +1 | 2 | 2 |
| F43 | 2 | 0 | 0 | +0 | 0 | 2 |
| F45 | 2 | 0 | 0 | +0 | 0 | 2 |
| F51 | 7 | 0 | 0 | +0 | 0 | 7 |
| F98 | 6 | 0 | 0 | +0 | 0 | 6 |
| Others | 17 | 0 | 0 | +0 | 0 | 17 |
| Z71 | 2 | 0 | 0 | +0 | 0 | 2 |

#### MDD-5k

| Disorder | N | Good | Bad | Net | Stable-R | Stable-W |
|----------|---|------|-----|-----|----------|----------|
| F20 | 1 | 0 | 0 | +0 | 1 | 0 |
| F22 | 1 | 1 | 0 | +1 | 0 | 0 |
| F23 | 1 | 0 | 0 | +0 | 0 | 1 |
| F28 | 1 | 1 | 0 | +1 | 0 | 0 |
| F30 | 1 | 0 | 0 | +0 | 0 | 1 |
| F31 | 2 | 0 | 0 | +0 | 0 | 2 |
| F32 | 88 | 5 | 27 | -22 | 50 | 6 |
| F34 | 1 | 0 | 1 | -1 | 0 | 0 |
| F39 | 14 | 0 | 0 | +0 | 0 | 14 |
| F41 | 67 | 18 | 9 | +9 | 14 | 26 |
| F42 | 3 | 0 | 0 | +0 | 2 | 1 |
| F43 | 2 | 0 | 0 | +0 | 0 | 2 |
| F45 | 2 | 0 | 0 | +0 | 0 | 2 |
| F48 | 1 | 0 | 0 | +0 | 0 | 1 |
| F50 | 2 | 0 | 0 | +0 | 0 | 2 |
| F51 | 4 | 0 | 0 | +0 | 0 | 4 |
| F90 | 1 | 0 | 0 | +0 | 0 | 1 |
| F93 | 1 | 0 | 0 | +0 | 0 | 1 |
| F98 | 4 | 0 | 0 | +0 | 0 | 4 |
| G47 | 1 | 0 | 0 | +0 | 0 | 1 |
| Z71 | 2 | 0 | 0 | +0 | 0 | 2 |

## 4. Somatization Mapper Contribution

Compares full evidence (with somatization) vs evidence without somatization mapper.

### Summary

| Dataset | Mode | Ev+Somat Top-1 | Ev-Somat Top-1 | Somat Delta | Good Flips | Bad Flips |
|---------|------|----------------|---------------- |-------------|------------|-----------|
| LingxiDiag | hied | 0.450 | 0.415 | +3.5pp | 14 | 7 |
| LingxiDiag | psycot | 0.415 | 0.410 | +0.5pp | 2 | 1 |
| LingxiDiag | single | 0.405 | 0.395 | +1.0pp | 2 | 0 |
| MDD-5k | hied | 0.460 | 0.450 | +1.0pp | 7 | 5 |
| MDD-5k | psycot | 0.450 | 0.475 | -2.5pp | 2 | 7 |
| MDD-5k | single | 0.470 | 0.470 | +0.0pp | 0 | 0 |

### Per-disorder somatization effect (HiED mode)

#### LingxiDiag

| Disorder | N | Ev+Somat | Ev-Somat | Delta | Good | Bad |
|----------|---|----------|----------|-------|------|-----|
| F31 | 2 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| F32 | 74 | 0.797 | 0.838 | -4.0pp | 1 | 4 |
| F39 | 12 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| F41 | 71 | 0.394 | 0.254 | +14.1pp | 13 | 3 |
| F42 | 5 | 0.600 | 0.600 | +0.0pp | 0 | 0 |
| F43 | 2 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| F45 | 2 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| F51 | 7 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| F98 | 6 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| Others | 17 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| Z71 | 2 | 0.000 | 0.000 | +0.0pp | 0 | 0 |

#### MDD-5k

| Disorder | N | Ev+Somat | Ev-Somat | Delta | Good | Bad |
|----------|---|----------|----------|-------|------|-----|
| F20 | 1 | 1.000 | 1.000 | +0.0pp | 0 | 0 |
| F22 | 1 | 1.000 | 1.000 | +0.0pp | 0 | 0 |
| F23 | 1 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| F28 | 1 | 1.000 | 1.000 | +0.0pp | 0 | 0 |
| F30 | 1 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| F31 | 2 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| F32 | 88 | 0.625 | 0.591 | +3.4pp | 3 | 0 |
| F34 | 1 | 0.000 | 1.000 | -100.0pp | 0 | 1 |
| F39 | 14 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| F41 | 67 | 0.478 | 0.478 | +0.0pp | 4 | 4 |
| F42 | 3 | 0.667 | 0.667 | +0.0pp | 0 | 0 |
| F43 | 2 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| F45 | 2 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| F48 | 1 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| F50 | 2 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| F51 | 4 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| F90 | 1 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| F93 | 1 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| F98 | 4 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| G47 | 1 | 0.000 | 0.000 | +0.0pp | 0 | 0 |
| Z71 | 2 | 0.000 | 0.000 | +0.0pp | 0 | 0 |

## 5. Key Findings

1. **Evidence helps LingxiDiag but hurts MDD-5k (HiED Top-1):** LingxiDiag +4.0pp, MDD-5k -6.0pp.
2. **Average across modes:** LingxiDiag +1.3pp, MDD-5k -5.8pp.
3. **Somatization mapper (HiED):** LingxiDiag +3.5pp, MDD-5k +1.0pp.
4. **Net prediction flips (HiED evidence vs none):** LingxiDiag +8, MDD-5k -12.

### Disorders most affected by evidence (HiED, |delta| >= 5pp)

| Dataset | Disorder | N | Delta(ev-no) | Direction |
|---------|----------|---|--------------|-----------|
| LingxiDiag | F41 | 71 | +7.0pp | HELPED |
| LingxiDiag | F42 | 5 | +20.0pp | HELPED |
| MDD-5k | F32 | 88 | -25.0pp | HURT |
| MDD-5k | F41 | 67 | +13.4pp | HELPED |

### Top-3 accuracy gap

| Dataset | Mode | No Evidence Top-3 | + Evidence Top-3 | Delta |
|---------|------|-------------------|------------------|-------|
| LingxiDiag | hied | 0.630 | 0.740 | +11.0pp |
| LingxiDiag | psycot | 0.625 | 0.740 | +11.5pp |
| LingxiDiag | single | 0.525 | 0.730 | +20.5pp |
| MDD-5k | hied | 0.715 | 0.615 | -10.0pp |
| MDD-5k | psycot | 0.670 | 0.600 | -7.0pp |
| MDD-5k | single | 0.765 | 0.625 | -14.0pp |
