# §5.3 Bias Robustness — Prep Package (NOT prose yet)

**Date**: 2026-04-26
**Per GPT round 20 strict scope**: 4 items only — verify sources, draft connectors, list traps, NO prose
**Purpose**: Send to GPT round 21 for review BEFORE writing §5.3 prose

---

## ITEM 1 — §5.3 source artifact verification (all 5 confirmed exist)

| Artifact | Path | Status | Role |
|---|---|:---:|---|
| Locked-numbers analysis doc | `docs/analysis/MDD5K_F32_F41_ASYMMETRY_V4.md` | ✓ exists | Primary numerical source |
| Synced narrative | `docs/paper/NARRATIVE_REFRAME.md` §5.3 (post-`ae02558`) | ✓ exists | Prose template (cascade table + framing) |
| Canonical metric registry | `results/analysis/metric_consistency_report.json` | ✓ exists | Cross-check authority |
| Pre-v4 bias baselines | `results/generalization/bias_transfer_analysis.json` | ✓ exists | Single LLM (189×), MAS T1 (8.94×), R6v2 (5.58×) |
| v4 dual-standard CI registry | `results/analysis/mdd5k_f32_f41_asymmetry_v4.json` | ✓ exists | 3.97× CI [2.82, 6.08]; paired bootstrap |

### Canonical numbers locked for §5.3

| System | Ratio | 95% CI | Source |
|---|---:|:---:|---|
| Single LLM (Qwen3-32B-AWQ) | 189× | (degenerate, n=1) | bias_transfer_analysis.json |
| MAS T1 baseline (pre-fix) | 8.94× | n/a | bias_transfer_analysis.json |
| MAS R6v2 (somatization prompt) | 5.58× | n/a | bias_transfer_analysis.json |
| **MAS ICD-10 v4** | **3.97×** | **[2.82, 6.08]** | mdd5k_f32_f41_asymmetry_v4.json |
| MAS DSM-5 v4 | 7.24× | [5.03, 11.38] | mdd5k_f32_f41_asymmetry_v4.json |
| MAS Both v4 | 3.97× | [2.82, 6.08] | mdd5k_f32_f41_asymmetry_v4.json (= ICD-10 pass-through) |

### Headline ratios with raw directional counts

| System        | F41→F32 | F32→F41 | Ratio |
| ------------- | ------: | ------: | ----: |
| Single LLM    |     189 |       1 |  189× |
| MAS T1        |     152 |      17 | 8.94× |
| R6v2          |     145 |      26 | 5.58× |
| MAS ICD-10 v4 |     151 |      38 | 3.97× |
| MAS DSM-5 v4  |     181 |      25 | 7.24× |

### Cumulative improvement chain (from NARRATIVE §5.3)

```
189× → 8.94× → 5.58× → 3.97× → 47.7× cumulative reduction
                                       ^^^^^^
                              headline bias-robustness result
```

### Paired bootstrap (DSM-5 − ICD-10)

- LingxiDiag: Δratio +3.13, 95% CI [+1.12, +7.21] → excludes 0
- MDD-5k: Δratio +3.24, 95% CI [+1.12, +6.89] → excludes 0

---

## ITEM 2 — Narrative connectors (drafted FIRST, before body)

Per round 19 lesson: explicit narrative connectors at section ends prevent implicit framing drift.

### Connector A — to §5.1 parity narrative (preempts "wait, you said parity not superiority")

> "This bias-robustness result does not contradict the §5.1 accuracy-parity result. Top-1 parity (§5.1) and F32/F41 error asymmetry (this section) measure different deployment properties: §5.1 evaluates fine-grained 12-class ranking on the held-out test set, while this section evaluates a specific clinical bias pattern under cross-dataset distribution shift. The MAS pipeline contributes the second property, not the first."

### Connector B — to §5.4 dual-standard caveat (preempts "is DSM-5 part of bias claim?")

> "We deliberately scope this bias-robustness claim to the MAS ICD-10 v4 pipeline. DSM-5 v0 reasoning increases F32/F41 asymmetry to 7.24× on MDD-5k (paired bootstrap 95% CI excludes 0; see §5.4), so DSM-5 v0 results are not part of the bias-robustness headline; their evaluation is reported as a dual-standard audit trade-off in §5.4 rather than as a robustness improvement."

### Connector C — to §7.5 limitation (preempts "you call 3.97× robust?")

> "We note that 3.97× remains an asymmetric error pattern, not a resolved one. The 47.7× reduction is from a catastrophic single-LLM baseline (189×); F41→F32 misclassification remains the dominant error mode under MDD-5k distribution shift, and we document this residual asymmetry as a limitation in §7.5."

### Connector D — to §5.3.1 framing of the cascade

> "We present the cascade descriptively rather than attributing the 5.58× → 3.97× change to any single repair, since per-fix ablation evidence is not provided. Each row reflects pipeline state at a specific commit; we report all milestones because they jointly support the claim that architectural and infrastructural changes compound."

### Connector E — to §5.2 feature-importance interpretation

**Connector E: §5.3 → §5.2** — The small MAS feature-importance share in the stacker does not imply the MAS pipeline has no value. §5.2 evaluates MAS as a feature block for in-domain Top-1; §5.3 evaluates MAS as an independent reasoning pipeline under cross-dataset F32/F41 error asymmetry. These are different claims.

- ✅ Allowed: "The 11.9% feature-importance share explains why MAS does not drive stacker Top-1 gains, but does not eliminate its value as an auditable reasoning pipeline for cross-dataset bias analysis."
- ❌ Forbidden: "The 11.9% feature importance proves MAS robustness."
- ❌ Forbidden: "Feature importance and bias robustness measure the same thing."

---

## ITEM 3 — Overclaim traps specific to §5.3

These are §5.3-specific failure modes I must avoid. Skeleton already has the universal Forbidden lists; this is the §5.3-specific layer.

### Trap 1 — Causal attribution to specific fixes
**Trap**: Claiming "F32/F33 threshold fix and DSM-5 checker template fix caused 3.97×"
**Why dangerous**: Not all fixes between R6v2 and v4 ICD-10 are listed; no per-fix ablation
**Locked language**: "v4 number is reported under the current paper evaluation contract and current pipeline state"
**Required disclosure**: "per-fix ablation evidence is not provided" (round 14 micro-fix)
**Allowed**: descriptive cascade reporting
**Forbidden**:
- ❌ "F32/F33 fix caused the 3.97× improvement"
- ❌ "Each step represents the effect of a single repair"
- ❌ "The improvement reflects [specific fixes A and B]"

### Trap 2 — Claiming asymmetry resolved
**Trap**: Calling 3.97× "robust" or "solved" because it's 47× better than 189×
**Why dangerous**: 3.97× is still asymmetric; F41→F32 ≈ 4× more frequent than F32→F41
**Locked language**: "47.7× cumulative reduction" not "asymmetry resolved"
**Required disclosure**: residual asymmetry pointer to §7.5
**Allowed**:
- ✅ "47.7× cumulative reduction"
- ✅ "189× → 3.97× is a substantial reduction"
- ✅ "asymmetry persists at 3.97×"
**Forbidden**:
- ❌ "asymmetry resolved"
- ❌ "MAS solves bias"
- ❌ "Bias eliminated"
- ❌ "Robust" without quantitative bound

### Trap 3 — R6v2 wrong-headline confusion
**Trap**: Treating R6v2 (5.58×) as the final/best result
**Why dangerous**: MAS ICD-10 v4 (3.97×) supersedes R6v2 in current pipeline
**Locked language**: "MAS ICD-10 v4 is the current best asymmetry; R6v2 is a cascade step"
**Required disclosure**: explicit "v4 number is the current paper contract; R6v2 is intermediate historical measurement"
**Allowed**:
- ✅ "headline best asymmetry: MAS ICD-10 v4 (3.97×)"
- ✅ "R6v2 (5.58×) is a cascade step demonstrating prompt-level transferability"
- ✅ "different mitigation mechanisms"
**Forbidden**:
- ❌ "R6v2 reaches the best F32/F41 asymmetry"
- ❌ "Our mitigation strategy is somatization-aware prompting" (incomplete; v4 also)
- ❌ "5.58× is the final result"

### Trap 4 — Connecting DSM-5 to bias robustness
**Trap**: Linking DSM-5 advantages (Section 5.4 F1 wins) to bias-robustness claim
**Why dangerous**: DSM-5 v0 amplifies F32/F41 asymmetry (7.24× vs 3.97×); paired bootstrap excludes 0
**Locked language**: "DSM-5 v0 is explicitly NOT part of the bias-robustness claim"
**Required disclosure**: connector to §5.4 (Connector B above)
**Allowed**:
- ✅ "DSM-5 v0 increases asymmetry to 7.24×"
- ✅ "DSM-5 v0 is reported as a dual-standard audit trade-off (§5.4)"
- ✅ "DSM-5 v0 is not part of the bias-robustness headline"
**Forbidden**:
- ❌ "DSM-5 generalizes better"
- ❌ "DSM-5 improves robustness under shift"
- ❌ "Both modes show bias improvement" (Both = ICD-10 pass-through, only ICD-10 has 3.97×)
- ❌ Any framing that connects DSM-5 v0 to robustness improvement

### Trap 5 — Both mode misframed as ensemble
**Trap**: Claiming Both mode is an ensemble of ICD-10 and DSM-5
**Why dangerous**: Both = ICD-10 pass-through (1925/1925 across all metric families)
**Locked language**: "Both = ICD-10 architectural pass-through, NOT ensemble"
**Allowed**:
- ✅ "Both mode is an ICD-10 pass-through"
- ✅ "Both = ICD-10 across 5 independent metric families"
- ✅ "Both inherits ICD-10 asymmetry (3.97×) by architectural design"
**Forbidden**:
- ❌ "Both mode is an ensemble"
- ❌ "Both mode combines ICD-10 and DSM-5"
- ❌ "Dual-standard reasoning improves bias"

### Trap 6 — Hedging-language scrutiny (round 18 lesson)
**Trap**: Soft mechanism verbs that overclaim ("MAS captures...", "the cascade demonstrates...")
**Why dangerous**: Round 18 caught "carries most signal" as too strong even with "most"
**Required usage**: Descriptive verbs only
**Allowed verbs**: tested, observed, reported, measured, computed, quantified
**Forbidden verbs**: drives, captures, demonstrates, proves, causes, leads to

### Trap 7 — Inconsistent CI reporting
**Trap**: Reporting 3.97× without CI [2.82, 6.08]
**Why dangerous**: Single-system CI is wide because F32→F41 denominator is small (n=38)
**Required**: Always pair point estimate with CI for the headline 3.97× claim
**Required**: Use **paired bootstrap** for DSM-5 vs ICD-10 comparison (single-system CIs overlap)
**Allowed**:
- ✅ "3.97× (95% CI [2.82, 6.08])"
- ✅ "Paired bootstrap of (DSM-5 − ICD-10) 95% CI excludes 0"
- ✅ Report counts and ratios together.
- ✅ "The current v4 ICD-10 ratio is 3.97× [2.82, 6.08]; the historical cascade is reported descriptively across system states."
**Forbidden**:
- ❌ "3.97×" (without CI)
- ❌ "DSM-5 (7.24×) is significantly worse than ICD-10 (3.97×)" using only single-system CIs
- ❌ Reporting asymmetry ratios without raw F41→F32 / F32→F41 counts.
- ❌ "The full 189× → 3.97× cascade is statistically significant."

---

## ITEM 4 — Do NOT write §5.3 prose yet

Per GPT round 20 verbatim:
> "**Do not write prose yet.** §5.3 是 high-risk. 等 §5.6 commit 後，可以先送一個 §5.3 prep package，我再幫你檢查 source mapping 和 allowed/forbidden list，再寫正式 prose."

This document IS the §5.3 prep package. After GPT round 21 reviews:
- Source map (Item 1)
- Connectors (Item 2)
- Trap list (Item 3)

→ Then write §5.3 prose v1.

---

## §5.3 LOCKED FRAMING (for round 21 confirmation)

Per GPT round 20 verbatim:
> "MAS ICD-10 v4 is the bias-robustness headline: 189× → 3.97×. R6v2 is a cascade step, not the endpoint. DSM-5 v0 is explicitly not part of the bias-robustness claim because it increases F32/F41 asymmetry to 7.24× on MDD-5k."

- I commit to this exact framing.
- §5.3 prose will open with single LLM 189× collapse on MDD-5k under distribution shift.
- Build cascade descriptively (4 rows: 189× → 8.94× → 5.58× → 3.97×).
- Headline = MAS ICD-10 v4 (3.97×, 95% CI [2.82, 6.08]), 47.7× cumulative.
- R6v2 (5.58×) explicitly framed as cascade step.
- DSM-5 v0 (7.24×) explicitly excluded from bias-robustness claim with paired-bootstrap evidence.
- Both = ICD-10 pass-through noted.
- Residual asymmetry → §7.5 limitation pointer.
- Connector A (parity vs robustness ≠ contradiction) at end.

---

## Length target for §5.3 prose

Skeleton target: ~400 words.

Given 7 traps + 5 connectors + cascade table + 3 numerical claims with CI, a 400-word target is tight. May need 450-500 words.

I'll target **400-500 words** with cascade table inline.

---

## Round 21 review request

- Send to GPT after §5.6 v3 commits + this prep package committed.
- §5.6 v3 committed (Optional micro-edit applied: "MAS-routing variants" → "class-routing variants").
- §5.3 prep package committed at `docs/paper/drafts/SECTION_5_3_PREP.md`.
- Round 21 review target 1: Item 1 — Are 5 source artifacts the right authoritative set?
- Round 21 review target 2: Item 2 — Connectors A, B, C, D, E; are any redundant or missing?
- Round 21 review target 3: Item 3 — 7 traps + Allowed/Forbidden; anything missing?
- Round 21 review target 4: Item 4 — Locked framing matches round 20 verbatim?
- Targeted length for prose: 400-500 words.
- Awaiting round 21 verdict before writing §5.3 prose.

---

## What this prep package is NOT

- ❌ NOT prose
- ❌ NOT a partial draft
- ❌ NOT scenarios for cascade interpretation
- ❌ NOT an analysis re-run (no new numbers computed)

It IS:
- ✓ Source map (where every number comes from)
- ✓ Connectors (drafted explicit framing-bridge sentences)
- ✓ Trap inventory (§5.3-specific overclaim risks)
- ✓ Locked framing (matches GPT round 20 directive)

---

## §5.3 prose plan summary

Once round 21 confirms this prep, §5.3 prose will be ~5 paragraphs:

| ¶ | Topic | Length |
|---|---|---:|
| 1 | Distribution shift setup + single-LLM collapse | ~80w |
| 2 | Cascade table + descriptive framing | ~120w + table |
| 3 | MAS ICD-10 v4 = 3.97× headline + CI | ~80w |
| 4 | DSM-5 v0 explicitly excluded + paired bootstrap | ~80w |
| 5 | Connector A (parity vs robustness) + Connector C (residual) | ~80w |

Estimated total: ~440 words + cascade table.

Within 400-500 target.

---

## My self-knowledge — pre-§5.3 plan

Round 18+19 lessons combined:

1. **Hedging language scrutiny**: every verb that asserts mechanism must be data-supported
2. **Explicit narrative connectors**: write connectors FIRST, body second

Pre-§5.3 self-discipline:
- I will draft Connector A/B/C/D/E first (above), then write paragraphs that LEAD INTO each
- I will run grep on every paragraph for the 7 trap forbidden lists before integrating
- I will source-attribute every number to one of the 5 source artifacts
- I will NOT use any verb stronger than "tested/observed/reported/measured/computed"

If I fail any of these, the prose is sent back to draft, not to GPT.
