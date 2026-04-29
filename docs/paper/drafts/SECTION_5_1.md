# Section 5.1 — Main Benchmark Results

We evaluate four candidate systems on LingxiDiag-16K test_final (N=1000) against two reference baselines from the original LingxiDiag report [CITE xu2026lingxidiagbench]: its TF-IDF baseline and its best reported LLM baseline.
Our selected Stacker LGBM achieves Top-1 = 0.612, Top-3 = 0.925, and Overall = 0.617, exceeding the published TF-IDF baseline by 11.6 percentage points on Top-1, 28.0 on Top-3, and 8.4 on Overall, and the published best LLM baseline by 12.5, 35.1, and 9.6 points on the same metrics.
Because this model combines supervised TF-IDF-derived features with MAS outputs, we treat this as a hybrid-system comparison rather than an LLM-only result.

**Table 2 — LingxiDiag-16K main benchmark results under the post-v4 evaluation contract (test_final, N=1000).**

| System | 2-class | 4-class | Top-1 | Top-3 | macro-F1 | weighted-F1 | Overall |
|---|---:|---:|---:|---:|---:|---:|---:|
| Published TF-IDF [CITE xu2026lingxidiagbench] | — | — | .496 | — | — | — | — |
| Published best LLM [CITE xu2026lingxidiagbench] | — | — | — | — | — | — | — |
| Reproduced TF-IDF (ours) | .712 | .491 | .610 | .829 | .352 | .585 | .555 |
| MAS-only DtV | .803 | — | .516 | — | — | — | — |
| **Stacker LGBM (ours, primary)** | **.753** | **.546** | **.612** | **.925** | **.334** | **.573** | **.617** |
| Stacker LR (macro-F1-oriented comparator) | .619 | .538 | .538 | .887 | .360 | .558 | .572 |

Top-1 = 0.612 vs reproduced TF-IDF 0.610 supports parity within the ±5 percentage-point non-inferiority margin defined in the post-v4 evaluation contract; McNemar p ≈ 1.0 is paired-discordance context, not an equivalence proof.
Stacker LGBM is a hybrid supervised + MAS stacker, not an LLM-only system.
CultureDx rows use post-v4 evaluation-contract metrics (Box 1) sourced from the canonical metric-consistency report and reproduced TF-IDF artifact.
MAS-only DtV cells are populated only where audit-reconciliation explicitly traces a value, and other cells are marked `—`.
Published comparator values are taken from the original LingxiDiag report where directly reported; cells without a directly sourced published metric are marked `—`.
Stacker LR is retained as a macro-F1-oriented comparator, not a primary system.

We also report a stronger reproduced TF-IDF baseline (Top-1 = 0.610), against which the Stacker LGBM advantage shrinks to +0.2 percentage points.
McNemar's test on paired predictions gives p ≈ 1.0, indicating failure to reject the null at α = 0.05 with 1000 cases.
Together with the small paired Top-1 difference, this supports a non-inferiority/parity interpretation under the ±5 percentage-point margin defined in the post-v4 evaluation contract, rather than a superiority claim.
The cause of the gap between our reproduced TF-IDF and the published TF-IDF (+11.4 percentage points on Top-1) is not fully identified; we discuss this transparently in §5.5.

We additionally report MAS-only and Stacker LR as comparators rather than primary systems.
MAS-only (DtV) underperforms our reproduced TF-IDF on fine-grained Top-1 (0.516 vs 0.610, −9.4 percentage points) but exceeds it on 2-class accuracy (0.803 vs 0.712, +9.1 percentage points), suggesting that MAS captures coarse-grained diagnostic signal even when it is not competitive for fine-grained 12-class classification.
Stacker LR fails the ±5 percentage-point non-inferiority margin against TF-IDF on Top-1 (0.538, −7.2 percentage points) but achieves the highest macro-F1 in our evaluation (0.360); we retain LR as a macro-F1-oriented comparator.
Stacker LGBM is therefore our selected primary stacker, while §5.2 examines feature-level contributions and §§5.3–5.6 examine system properties not captured by Top-1 alone.
