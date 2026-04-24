# Does MAS Contribute, or is it Just LGBM?

**Critical question you asked.** Answer requires ablation of MAS features vs TF-IDF features
within the stacker. Done below. Honest answer: **MAS contributes a small amount, mostly on
F1_macro, concentrated in rare classes. It is NOT doing the heavy lifting — TF-IDF is.**

---

## The ablation setup

Stacker uses 31 features total:
- **TF-IDF block (13)**: TF-IDF per-class probabilities (12) + top-1 margin (1)
- **MAS block (18)**: DtV rank confidences (5) + checker met-ratios per class (12) + abstain flag (1)

Three models trained on identical dev_hpo (N=1000) → evaluated on identical test_final (N=1000):
- A. LGBM with TF-IDF features only (13)
- B. LGBM with MAS features only (18)
- C. LGBM with all 31 features (what's currently committed)

Plus the same three for LR to verify findings aren't LGBM-specific.

---

## Results

### LGBM (tree-based, handles mixed features well)

| Feature set | Top-1 | F1_m | F1_w |
|---|---:|---:|---:|
| **TF-IDF only (13)** | **0.609** | **0.324** | **0.594** |
| MAS only (18) | 0.403 | 0.209 | 0.404 |
| ALL (31) ← committed | 0.609 | 0.367 | 0.593 |
| **Δ (ALL − TF-IDF-only)** | **+0.000** | **+0.043** | **−0.001** |

### LR (linear, interpretable contribution)

| Feature set | Top-1 | F1_m | F1_w |
|---|---:|---:|---:|
| **TF-IDF only (13)** | **0.511** | **0.335** | **0.538** |
| MAS only (18) | 0.177 | 0.167 | 0.189 |
| ALL (31) | 0.533 | 0.369 | 0.563 |
| **Δ (ALL − TF-IDF-only)** | **+0.022** | **+0.034** | **+0.025** |

### Statistical significance of "adding MAS to TF-IDF"

| Test | LGBM | LR |
|---|---|---|
| McNemar Top-1, ALL vs TF-IDF-only | p=1.00 (null) | p=0.099 (marginal) |
| Bootstrap Top-1, P(>0) | 47% | 94% |
| Bootstrap F1_m, P(>0) | 90% | 97% |

### LGBM feature importance breakdown

- **TF-IDF block: 88.1%** of total importance
- **MAS block: 11.9%** of total importance
- Top 13 features by importance: **all 13 are TF-IDF features**
- Top MAS feature (#14 overall): `dtv_checker_mr__F32`

---

## Per-class analysis (where does MAS help?)

LGBM ALL-features vs TF-IDF-only, F1 per class:

| Class | N | TF-IDF F1 | ALL F1 | Δ | Notes |
|---|---:|---:|---:|---:|---|
| F20 | 5 | 0.000 | 0.429 | **+0.429** | MAS helps (tiny sample) |
| F31 | 9 | 0.000 | 0.000 | 0 | neither model gets these |
| F32 | 365 | 0.697 | 0.700 | +0.003 | negligible |
| F39 | 60 | 0.458 | 0.456 | −0.001 | negligible |
| F41 | 358 | 0.641 | 0.641 | 0 | negligible |
| F42 | 25 | 0.421 | 0.410 | −0.011 | negligible |
| F43 | 11 | 0.143 | 0.286 | **+0.143** | MAS helps |
| F45 | 8 | 0.167 | 0.222 | +0.056 | MAS helps slightly |
| F51 | 36 | 0.163 | 0.167 | +0.003 | negligible |
| F98 | 30 | 0.697 | 0.646 | **−0.051** | MAS hurts |
| Z71 | 8 | 0.000 | 0.000 | 0 | neither gets |
| Others | 85 | 0.497 | 0.448 | −0.049 | MAS slightly hurts |

**MAS signal helps 3 rare classes (F20, F43, F45) and hurts 1 (F98).**

---

## The honest answer

### No, MAS is NOT just LGBM doing everything. But MAS is NOT doing the heavy lifting.

**Quantitative truth**:
- **88% of predictive signal comes from TF-IDF** (feature importance)
- **12% of predictive signal comes from MAS** (feature importance)
- **Top-1 improvement from adding MAS**: 0 pp (LGBM) / +2.2 pp (LR), marginal
- **F1_macro improvement from adding MAS**: +3.4 to +4.3 pp, concentrated in rare classes

**What this means for reviewer defense**:

| Reviewer question | Honest answer |
|---|---|
| "Is Stacker just LGBM on TF-IDF?" | No — MAS features contribute **+3.4pp F1_macro**, statistically marginal (P>0 = 90-97%) |
| "Why not just use TF-IDF+LGBM?" | Three reasons: (1) MAS F1_macro gain on rare classes; (2) interpretability (criterion evidence); (3) prior-bias controllability via prompts |
| "Your stacker LGBM 0.612 is same as TF-IDF 0.611" | True, they are in statistical parity on Top-1. Our gain is on F1_macro (0.358 vs 0.324 LGBM-only) and comes from MAS's rare-class criterion evidence |
| "MAS only contributes 12% feature importance" | Correct. We don't claim MAS is the primary predictor. We claim MAS provides a *necessary complement* that a standalone TF-IDF-only classifier cannot deliver, especially for under-represented classes where supervised training has insufficient data |

### What you CAN claim honestly

1. **Stacker beats DtV MAS raw (significant)**: +8.9 pp Top-1, +18.7 pp F1_m. Supervised signal rescues MAS from F32 bias.
2. **Stacker beats paper's baseline**: 0.605 Top-1 > 0.496 TF-IDF+LR in paper (but your own TF-IDF is also 0.602).
3. **MAS features provide marginal F1_macro gain**: +3.4 pp, concentrated in rare classes (F20, F43, F45). Not statistically significant at 95% but at 90%+.
4. **MAS provides properties TF-IDF cannot**: criterion-level evidence, zero training, prior controllability (empirically shown R6v2 −22% on LingxiDiag, MDD-5k pending).

### What you CAN'T claim honestly

1. ~~"MAS significantly improves accuracy over supervised baseline"~~ — barely significant (P=90%, not 95%)
2. ~~"MAS is the primary predictor in Stacker"~~ — 12% feature importance vs TF-IDF's 88%
3. ~~"Stacker is a better classifier than TF-IDF+LGBM"~~ — parity on Top-1

---

## Paper positioning (revised for this finding)

### Section 5.3: "Feature Ablation"

Frame this as a **transparent ablation** that shows where MAS contributes:

> "To isolate the contribution of MAS features within Stacker, we train three LGBM
> classifiers on the same dev_hpo split: (1) TF-IDF features only (13 features),
> (2) MAS features only (18 features), and (3) all 31 features. On test_final,
> TF-IDF alone achieves Top-1 = 0.609 and F1_macro = 0.324. MAS alone achieves 
> Top-1 = 0.403 and F1_macro = 0.209, confirming that MAS signal is insufficient
> as a standalone classifier. The combined stacker achieves Top-1 = 0.609 and 
> F1_macro = 0.367. The +0.043 F1_macro gain (P(>0) = 90%) concentrated in rare
> classes (F20, F43, F45 improved by 0.06 to 0.43) demonstrates that MAS 
> criterion-level evidence recovers classes where supervised training data is 
> sparse, though the magnitude of improvement is modest."

### Section 5.4: "Interpreting the MAS Role"

Explicitly acknowledge MAS's limited quantitative contribution:

> "Our stacker results show that MAS features contribute roughly 12% of total 
> LGBM importance, with TF-IDF supervised signal dominating at 88%. We interpret
> this as MAS serving as a *complement* rather than a *primary predictor* in 
> accuracy-optimized settings. MAS's distinct value comes from (1) criterion-level
> evidence for clinical interpretability, (2) controllable prior bias via prompt 
> engineering, (3) transferability to new diagnostic standards (e.g., DSM-5) 
> without retraining, and (4) zero-training-data deployment — properties that 
> supervised TF-IDF classifiers cannot provide regardless of accuracy."

---

## What if reviewer pushes harder: "So your MAS is essentially useless for accuracy?"

Answer: "In this specific benchmark configuration, yes — MAS's quantitative accuracy 
contribution is small. But our paper's thesis is that accuracy is not the only 
deployment criterion. We explicitly demonstrate:

- **Interpretability**: Per-criterion evidence enables clinician audit (example cases in Appendix X).
- **Bias control**: R6v2 somatization prompt reduces F32 bias by 22% without retraining.
- **Cross-standard support**: ICD-10 ↔ DSM-5 translator extends to Taiwan clinical workflow.
- **Cross-dataset robustness**: MAS maintains 8.94× bias asymmetry on MDD-5k while single LLM 
  baseline collapses to 189× (21× worse under distribution shift)."

This positions the paper as a **deployment characterization paper** rather than an 
**accuracy optimization paper**. That's defensible and genuinely novel.

---

## Bottom line

**You asked: is MAS contributing or is LGBM doing it?**

**Answer**: LGBM is doing ~88% via TF-IDF features. MAS contributes ~12% (feature 
importance), concentrated in F1_macro for rare classes. The contribution is real 
but small and statistically marginal. 

**The reviewer who asks this question is right to ask**, and you must answer 
honestly. Papers claiming MAS SOTA accuracy get rejected. Papers claiming 
**"MAS provides deployment properties at accuracy parity"** survive review.

Use the ablation table above directly in your paper Section 5.3. Transparency 
here strengthens credibility elsewhere.
