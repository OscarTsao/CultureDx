# Section 6 — Disagreement Triage

## 6.1 Model-discordance triage

Section 5.1 reports the primary ICD-10-labelled hybrid stacker benchmark on aggregate test-set metrics.
Section 6.1 examines whether the same primary outputs have uneven error concentration across cases.
The primary-output model for §6.1 = Stacker LGBM; all accuracy, enrichment, and recall figures below are computed against Stacker LGBM Top-1 predictions and gold labels on LingxiDiag-16K test_final (N = 1000).

**Table 5 — Model-discordance and confidence-based triage on LingxiDiag-16K (N = 1000).**
Disagreement and confidence are compared at the same 26.4% review budget; the union policy is reported as a higher-recall operating point at 38.9% review burden.

| Triage rule | Flag rate | Acc unflagged | Acc flagged | Error enrichment | Error recall |
|------|--------:|-------:|-------:|-------:|-------:|
| TF-IDF/Stacker disagreement | 26.4% | 0.697 | 0.375 | 2.06× | 42.5% |
| Lowest 26.4% Stacker confidence | 26.4% | 0.688 | 0.402 | 1.92× | 40.7% |

We compare two case-level triage signals at the same 26.4% review budget: TF-IDF/Stacker model-discordance flags cases where the supervised TF-IDF baseline and the Stacker LGBM disagree on the predicted label, and the confidence-quantile baseline flags the lowest 26.4% of cases by Stacker probability.
At equal 26.4% review budget, model-discordance flags cases at 2.06× the unflagged error rate and recovers 42.5% of all Stacker errors; the confidence-quantile baseline reaches 1.92× enrichment and 40.7% recall.
A paired bootstrap (1000 resamples, seed 20260420) on the disagreement-vs-confidence advantage gives Δ enrichment 95% CI [−0.204, +0.473] and Δ recall 95% CI [−0.043, +0.073]; both intervals include zero.
At equal review budget, model-discordance shows no statistically detectable advantage over confidence by paired bootstrap.

*Union policy continued from Table 5:*

| Policy | Flag rate | Error enrichment | Error recall | Jaccard with model-discordance |
|------|--------:|--------:|--------:|-------:|
| Disagreement only | 26.4% | 2.06× | 42.5% | 1.000 |
| Confidence only | 26.4% | 1.92× | 40.7% | 0.357 |
| Disagreement OR low-confidence | 38.9% | 2.17× | 58.0% | 0.679 |

The two signals flag partially complementary flagged populations (Jaccard 0.357 between disagreement and confidence sets).
The union policy captures 58.0% of errors at 38.9% flag rate, exceeding either single signal on error recall while requiring higher review burden.

§5.1 parity on aggregate metrics does not imply uniform reliability across cases: a 26.4% subset of LingxiDiag-16K has 2.06× the Stacker error rate.
The §5.2 analysis assigns MAS reasoning an aggregate 11.9% feature-importance share in the Stacker; the hybrid stacker output, which includes MAS-derived features, can be compared with TF-IDF predictions to expose a model-discordance signal; this case-level signal is distinct from aggregate feature-importance accounting.
We treat the disagreement and union policies as configurable review-burden operating points evaluated on synthetic / curated test data; we do not claim deployment readiness.

## 6.2 Diagnostic-standard discordance triage

Section 5.4 reports metric-level trade-offs between ICD-10 mode and DSM-5-only mode on LingxiDiag-16K and MDD-5k.
Section 6.2 asks whether per-case ICD-10/DSM-5 mode disagreement — the diagnostic-standard discordance — flags error-prone cases under each primary-output perspective.

On LingxiDiag-16K (N = 1000), ICD-10 mode and DSM-5-only mode disagree on the predicted label in 25.1% of cases.
Under the ICD-10 primary-output perspective, the flagged 25.1% have 1.37× the unflagged error rate and recover 31.4% of all errors; under the DSM-5 v0 primary-output perspective, the flagged subset reaches 1.69× enrichment and 36.1% recall.

**Table 6 — ICD-10 / DSM-5 diagnostic-standard discordance across datasets.**
Rows report whether ICD-10 / DSM-5 mode disagreement identifies error-enriched case subsets under each primary-output perspective.
Cross-dataset enrichment ratios are descriptive because datasets, primary-output perspectives, baseline error rates, and diagnostic distributions differ.

| Dataset | Primary-output | N | Flag rate | Acc unflagged | Acc flagged | Error enrichment | Error recall |
|------|------|---:|--------:|-------:|-------:|-------:|-------:|
| LingxiDiag-16K | ICD-10 | 1000 | 25.1% | 0.549 | 0.382 | 1.37× | 31.4% |
| LingxiDiag-16K | DSM-5 v0 | 1000 | 25.1% | 0.549 | 0.239 | 1.69× | 36.1% |
| MDD-5k | ICD-10 | 925 | 20.8% | 0.656 | 0.370 | 1.83× | 32.4% |
| MDD-5k | DSM-5 v0 | 925 | 20.8% | 0.656 | 0.292 | 2.06× | 35.1% |

On MDD-5k (N = 925), ICD-10 mode and DSM-5-only mode disagree on 20.8% of cases.
The flagged subset has 1.83× enrichment and 32.4% recall under the ICD-10 primary-output perspective and 2.06× enrichment and 35.1% recall under the DSM-5 v0 primary-output perspective.
The higher enrichment under the DSM-5 primary-output perspective reflects lower DSM-5 accuracy within flagged ICD-10/DSM-5 disagreement cases (Table 6 flagged-subset accuracy: LingxiDiag 0.239 DSM-5 vs 0.382 ICD-10; MDD-5k 0.292 DSM-5 vs 0.370 ICD-10), not DSM-5-specific triage value.
Within-dataset unflagged accuracy is identical between perspectives on the same gold labels (LingxiDiag 0.549, MDD-5k 0.656), so the higher DSM-5-perspective enrichment is not a baseline-accuracy gap.

Diagnostic-standard discordance functions as an audit signal that complements the §5.4 metric-level trade-off, not as evidence that DSM-5 is superior.
Cross-dataset enrichment ratios span 1.37×–2.06×; we report this range as descriptive because the comparisons involve different datasets, primary-output perspectives, baseline error rates, and diagnostic-distribution concentration (MDD-5k has 77% F32+F41 vs LingxiDiag's 72%, which may partly reflect why the MDD-5k disagreement rate is lower).
DSM-5 v0 results in §6.2 use the LLM-drafted unverified `dsm5_criteria.json` schema; we document this scope limitation in §7.2 and treat all §6 numbers as observations on synthetic / curated test data without claiming deployment readiness.
