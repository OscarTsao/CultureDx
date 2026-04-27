# Section 5.4 — Dual-Standard Audit

## Setup and scope

Section 5.1 reports the primary ICD-10-labelled hybrid stacker benchmark. In §5.4 we evaluate three standard-specific MAS reasoning modes as audit outputs that complement, but do not replace, that benchmark: ICD-10 mode runs MAS reasoning under the ICD-10 standard; DSM-5-only mode runs the same MAS architecture under the v0 DSM-5 templates; Both mode preserves ICD-10 as the primary output and exposes DSM-5 reasoning as sidecar audit evidence on the same case. The DSM-5 templates are LLM-drafted v0 (`dsm5_criteria.json`, version `0.1-DRAFT`, source-note `UNVERIFIED`); we therefore treat DSM-5 outputs as experimental audit observations rather than clinically validated DSM-5 diagnoses. We compare the three modes on LingxiDiag-16K (in-domain, N = 1000) and MDD-5k (an external synthetic distribution-shift dataset, N = 925).

## In-domain trade-off on LingxiDiag-16K

**Table 5.4a — LingxiDiag-16K mode comparison (N = 1000).**

| Mode | 2-class | 4-class | Top-1 | Top-3 | macro-F1 | weighted-F1 | Overall |
|------|--------:|--------:|------:|------:|---------:|------------:|--------:|
| ICD-10 | .778 | .447 | .507 | .800 | .199 | .457 | .514 |
| DSM-5 | .767 | .476 | .471 | .803 | .188 | .421 | .506 |
| Both | .778 | .447 | .507 | .800 | .199 | .457 | .514 |

On LingxiDiag-16K, DSM-5-only mode is lower than ICD-10 mode on Top-1 (0.471 vs 0.507, −3.6pp), weighted-F1 (0.421 vs 0.457, −3.6pp), Overall (0.506 vs 0.514, −0.8pp), macro-F1 (0.188 vs 0.199, −1.1pp), and 2-class accuracy (0.767 vs 0.778, −1.1pp), and slightly higher on 4-class accuracy (0.476 vs 0.447, +2.9pp) and Top-3 (0.803 vs 0.800, +0.3pp). We report these metric deltas descriptively and reserve inferential claims in §5.4 for the paired-bootstrap F32/F41 asymmetry analysis.

## Distribution-shift trade-off on MDD-5k

**Table 5.4b — MDD-5k mode comparison (N = 925).**

| Mode | 2-class | 4-class | Top-1 | Top-3 | macro-F1 | weighted-F1 | Overall |
|------|--------:|--------:|------:|------:|---------:|------------:|--------:|
| ICD-10 | .890 | .444 | .597 | .853 | .197 | .514 | .566 |
| DSM-5 | .912 | .520 | .581 | .842 | .230 | .526 | .584 |
| Both | .890 | .444 | .597 | .853 | .197 | .514 | .566 |

On MDD-5k, DSM-5-only mode is lower than ICD-10 mode on Top-1 (0.581 vs 0.597, −1.6pp) and Top-3 (0.842 vs 0.853, −1.1pp), but higher on 2-class (0.912 vs 0.890, +2.2pp), 4-class (0.520 vs 0.444, +7.6pp), macro-F1 (0.230 vs 0.197, +3.3pp), weighted-F1 (0.526 vs 0.514, +1.3pp), and Overall (0.584 vs 0.566, +1.8pp). Class-level differences are not used as a primary §5.4 claim because per-class sample sizes are too small for stable comparisons. The DSM-5-only vs ICD-10 pattern is dataset-dependent and metric-specific.

## Both mode is an ICD-10 architectural pass-through

**Table 5.4c — Both vs ICD-10 agreement.**

| Pair | LingxiDiag-16K | MDD-5k |
|------|---------------:|-------:|
| ICD-10 vs Both pairwise agreement | 1000 / 1000 | 925 / 925 |
| Metric-key differences | 0 / 15 | 0 / 15 |

Both mode and ICD-10 mode produce identical primary outputs on every case in both datasets, and all 15 reported metric keys match exactly between the two modes. Both mode is therefore an ICD-10 architectural pass-through with DSM-5 sidecar audit evidence, not an ensemble.

## Trade-off summary and limitation pointers

DSM-5-only mode widens the F32/F41 diagnostic-error asymmetry described in §5.3 on both datasets. On MDD-5k, the F41→F32 / F32→F41 asymmetry ratio increases from 3.97× under ICD-10 mode to 7.24× under DSM-5-only mode; on LingxiDiag-16K, the paired bootstrap of (DSM-5 − ICD-10) Δratio is +3.13 with a 95% CI of [+1.12, +7.21] (CI excludes zero). DSM-5-only mode also reduces F42/OCD recall on both datasets; the magnitude depends on the slice or class definition and is reported in §7.6, where we treat F42/OCD as a v0 schema limitation rather than evidence against dual-standard auditing in general. Diagnostic-standard discordance — disagreement between ICD-10 mode and DSM-5-only mode predictions on the same case — is used as an audit triage signal in §6.2. These results support dual-standard auditing as a way to expose standard-sensitive trade-offs, not as evidence that DSM-5 v0 is superior or more robust; we document the DSM-5 v0 unverified scope explicitly in §7.2 and treat all DSM-5 numbers in §5.4 as audit observations under LLM-drafted unverified criteria.
