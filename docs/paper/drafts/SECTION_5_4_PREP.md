# §5.4 Dual-Standard Audit — Prep Package (NOT prose yet)

**Date**: 2026-04-26
**Per GPT round 24**: §5.3 closed, start §5.4 prep only (no prose).
**Per GPT round 24 strict scope**: 5 prep items — sources, locked tables, connectors, allowed wording, forbidden wording.
**Length target for §5.4 prose** (when written later): ~500-700 words + 2-3 tables.

---

## ITEM 1 — Source artifacts (all 7 confirmed exist)

| Artifact | Path | Status | Role |
|---|---|:---:|---|
| LingxiDiag dual-standard metrics | `results/dual_standard_full/lingxidiag16k/mode_{icd10,dsm5,both}/pilot_*/metrics_summary.json` | ✓ | Mode comparison N=1000 |
| MDD-5k dual-standard metrics | `results/dual_standard_full/mdd5k/mode_{icd10,dsm5,both}/pilot_*/metrics_summary.json` | ✓ | Mode comparison N=925 |
| Pilot comparison + agreement | `results/dual_standard_full/{lingxidiag16k,mdd5k}/pilot_comparison.json` | ✓ | Agreement / pass-through registry |
| F42 limitation doc | `docs/limitations/F42_DSM5_COLLAPSE_2026_04_25.md` | ✓ | LingxiDiag paper-parent F42/OCD decrease 52%→12% under DSM-5; definition-specific details for §7.6 |
| F32/F41 asymmetry registry | `docs/analysis/MDD5K_F32_F41_ASYMMETRY_V4.md` + `results/analysis/mdd5k_f32_f41_asymmetry_v4.json` | ✓ | DSM-5 worsens F32/F41 (already used in §5.3) |
| Disagreement triage analysis | `docs/analysis/DISAGREEMENT_AS_TRIAGE.md` | ✓ | Diagnostic-standard discordance numbers (for §6.2 connector) |
| DSM-5 v0 unverified marker | `src/culturedx/ontology/data/dsm5_criteria.json` | ✓ | version `0.1-DRAFT`, source_note: "UNVERIFIED" |

### Per round 21a lesson — connector sources also listed

| Connector | References | Source (already in list above) |
|---|---|---|
| §5.4 → §5.1 (parity) | §5.1 primary ICD-10-labelled hybrid stacker benchmark | committed `SECTION_5_1.md` (in `docs/paper/drafts/`) |
| §5.4 → §5.3 (DSM-5 NOT in bias claim) | 7.24× MDD-5k DSM-5 asymmetry | mdd5k_f32_f41_asymmetry_v4.json ✓ |
| §5.4 → §6.2 (disagreement triage) | 2.06×/35.1% recall when DSM-5 v0 is the primary-output model on MDD-5k | DISAGREEMENT_AS_TRIAGE.md ✓ |
| §5.4 → §7.6 (F42 limitation) | definition-aware F42/OCD decrease under DSM-5 v0; exact magnitudes in §7.6 | F42_DSM5_COLLAPSE_2026_04_25.md ✓ |
| §5.4 → §7.2 (v0 unverified) | DSM-5 v0 = `0.1-DRAFT, UNVERIFIED` | dsm5_criteria.json ✓ |

---

## ITEM 2 — Locked tables (numbers verified from artifacts)

### Table 5.4a — LingxiDiag-16K dual-standard pilot (N=1000)

| Mode | 2c_Acc | 4c_Acc | Top-1 | Top-3 | F1_macro | F1_weighted | Overall |
|---|---:|---:|---:|---:|---:|---:|---:|
| ICD-10 | 0.778 | 0.447 | 0.507 | 0.800 | 0.199 | 0.457 | 0.514 |
| DSM-5 | 0.767 | 0.476 | 0.471 | 0.803 | 0.188 | 0.421 | 0.506 |
| Both | 0.778 | 0.447 | 0.507 | 0.800 | 0.199 | 0.457 | 0.514 |

### Table 5.4b — MDD-5k dual-standard pilot (N=925)

| Mode | 2c_Acc | 4c_Acc | Top-1 | Top-3 | F1_macro | F1_weighted | Overall |
|---|---:|---:|---:|---:|---:|---:|---:|
| ICD-10 | 0.890 | 0.444 | 0.597 | 0.853 | 0.197 | 0.514 | 0.566 |
| DSM-5 | 0.912 | 0.520 | 0.581 | 0.842 | 0.230 | 0.526 | 0.584 |
| Both | 0.890 | 0.444 | 0.597 | 0.853 | 0.197 | 0.514 | 0.566 |

### Table 5.4c — DSM-5 vs ICD-10 deltas (descriptive trade-off)

| Metric | LingxiDiag (in-domain) | MDD-5k (synthetic shift) |
|---|---:|---:|
| 2-class accuracy | −1.1pp | **+2.2pp** |
| 4-class accuracy | **+2.9pp** | **+7.6pp** |
| 12-class Top-1 | −3.6pp | −1.6pp |
| 12-class Top-3 | ≈ +0.3pp | −1.1pp |
| 12-class F1_macro | −1.1pp | **+3.3pp** |
| 12-class F1_weighted | −3.6pp | **+1.3pp** |
| Overall | −0.8pp | **+1.8pp** |
| F32/F41 asymmetry ratio (paired bootstrap (DSM-5 − ICD-10)) | Δratio +3.13, CI [+1.12, +7.21] (excludes 0) | Δratio +3.24, CI [+1.12, +6.89] (excludes 0); ICD-10 3.97× → DSM-5 7.24× |
| F42 recall (paper-parent per-class) | −40pp (LingxiDiag, n=25) | −23.1pp (n=13, small-N exploratory only) |
| F42 Top-1 (v4 slice) | −30.6pp (n=36) | −23.8pp (n=21) |
| §5.4 locked F42 claim | direction-only: decreases under DSM-5 v0 | direction-only: decreases under DSM-5 v0 |

Pattern: **dataset-dependent, metric-specific trade-offs** — not "DSM-5 wins" / "DSM-5 loses".

### Table 5.4d — Pairwise agreement (Both = ICD-10 pass-through verified)

| Pair | LingxiDiag-16K (N=1000) | MDD-5k (N=925) |
|---|---:|---:|
| ICD-10 vs DSM-5 | 749/1000 agree (74.9%) | 733/925 agree (79.2%) |
| ICD-10 vs Both | 1000/1000 (100%) | 925/925 (100%) |
| DSM-5 vs Both | 749/1000 (74.9%) | 733/925 (79.2%) |
| Metric-key differences (ICD-10 vs Both) | 0/15 keys differ | 0/15 keys differ |

Both mode is verified ICD-10 architectural pass-through across both datasets and all 15 metric keys.

---

## ITEM 3 — Narrative connectors (drafted FIRST per round 19 lesson)

Per round 20 lesson — connector inventory must use 4-tier matrix.

### Tier 1 (mandatory): foundational/setup section

#### Connector A — to §5.1 parity narrative
> "§5.1 reports the primary ICD-10-labelled hybrid stacker benchmark. §5.4 evaluates standard-specific MAS reasoning modes as audit outputs and does not reframe the §5.1 primary-model claim. DSM-5-only mode provides metric-specific trade-off measurements; Both mode preserves ICD-10 primary output and exposes DSM-5 sidecar audit evidence."

### Tier 2 (mandatory): adjacent quantitative claims

#### Connector B — to §5.3 bias robustness
> "The §5.3 bias-robustness claim is scoped to MAS ICD-10 v4 (3.97×). DSM-5 v0 increases MDD-5k F32/F41 asymmetry to 7.24× (paired bootstrap (DSM-5 − ICD-10) 95% CI excludes 0); §5.4 reports DSM-5 v0 evaluation including this trade-off rather than as a robustness improvement."

#### Connector C — to §6.2 disagreement triage
> "Diagnostic-standard discordance — disagreement between ICD-10-mode and DSM-5-mode predictions on the same case — is reported in §6.2 as an audit triage signal (MDD-5k: 2.06× error enrichment / 35.1% recall when DSM-5 v0 is treated as the primary-output model; 1.83× / 32.4% when ICD-10 is the primary-output model). §5.4 establishes the metric-level dual-standard structure that §6.2 uses."

### Tier 3 (mandatory): limitation pointers

#### Connector D — to §7.6 F42 limitation
> "On LingxiDiag paper-parent per-class analysis (n=25), DSM-5 v0 F42/OCD recall decreases from 52% under ICD-10 to 12% under DSM-5. We document this in §7.6 as a limitation of the v0 DSM-5 criterion-D exclusion structure, not as evidence against dual-standard auditing in general."

### Tier 4 (mandatory): scope conflict / unverified claims

#### Connector E — to §7.2 v0 unverified caveat
> "The DSM-5 criterion templates used here are v0 LLM drafts (`dsm5_criteria.json` version `0.1-DRAFT`, source-note `UNVERIFIED`). All §5.4 DSM-5 numbers are reported as audit observations under this experimental v0, not as clinically validated DSM-5 diagnostic performance. We document this scope explicitly in §7.2."

---

## ITEM 4 — Allowed wording

### Framing
- ✅ "dual-standard audit"
- ✅ "DSM-5 v0 audit observations"
- ✅ "audit output / sidecar evidence"
- ✅ "experimental DSM-5 v0 formalization"
- ✅ "standard-sensitive diagnostic structure"
- ✅ "metric-specific, dataset-dependent trade-off"
- ✅ "DSM-5 v0 reasoning" / "DSM-5 mode" / "ICD-10 mode"
- ✅ "Both mode is an ICD-10 architectural pass-through (0 of 15 metric-keys differ on both datasets)"

### Quantitative reporting
- ✅ "On LingxiDiag-16K (in-domain, N=1000), DSM-5 mode shows lower Top-1 (0.471 vs 0.507) and lower F1-weighted (0.421 vs 0.457) than ICD-10 mode, but slightly higher 4-class accuracy (0.476 vs 0.447)."
- ✅ "On MDD-5k (synthetic distribution shift, N=925), DSM-5 mode shows higher 2-class (0.912 vs 0.890), 4-class (0.520 vs 0.444), F1-macro (0.230 vs 0.197), and Overall (0.584 vs 0.566), but lower Top-1 (0.581 vs 0.597) and Top-3 (0.842 vs 0.853)."
- ✅ "the measured DSM-5 vs ICD-10 difference is +X.Xpp on metric Y" (descriptive)
- ✅ "The pattern of DSM-5 mode performance is dataset-dependent and metric-specific."

### Connectors / scope
- ✅ "DSM-5 v0 is reported as an audit observation, not a clinically validated diagnostic standard."
- ✅ "DSM-5 v0 is excluded from the §5.3 bias-robustness headline (paired-bootstrap (DSM-5 − ICD-10) CI excludes 0)."
- ✅ "On LingxiDiag paper-parent per-class analysis, F42/OCD recall decreases from 52% under ICD-10 to 12% under DSM-5; v4 slice metrics and MDD-5k show the same direction but different magnitudes. We treat F42 as a v0 schema limitation and defer exact definition-specific magnitudes to §7.6."

### CI / statistical
- ✅ "statistically detectable under paired bootstrap" (per round 22e)
- ✅ "the directional widening from ICD-10 to DSM-5 in F32/F41 asymmetry is statistically detectable"
- ✅ "we do not claim significance for the per-metric in-domain trade-off because we did not pre-register paired tests at the metric level for §5.4"

### Both mode framing
- ✅ "Both mode preserves the ICD-10 primary output and exposes DSM-5 as sidecar audit evidence"
- ✅ "Both mode is an ICD-10 architectural pass-through"
- ✅ "Both mode inherits ICD-10 metrics by design (0/15 metric keys differ)"
- ✅ "Both mode is not an ICD-10/DSM-5 ensemble"
- ✅ "Both pairwise-agreement with ICD-10 is 1000/1000 on LingxiDiag and 925/925 on MDD-5k"
- ✅ "DSM-5-only mode reveals dataset-dependent, metric-specific trade-offs"
- ✅ "DSM-5 v0 audit evidence" / "DSM-5 sidecar audit evidence" (only in Both context)

---

## ITEM 5 — Forbidden wording

### Trap 1 — "DSM-5 wins" framing
- ❌ "DSM-5 wins"
- ❌ "DSM-5 is better"
- ❌ "DSM-5 generalizes better"
- ❌ "DSM-5 reasoning improves performance"
- ❌ "DSM-5 outperforms ICD-10"

### Trap 2 — "DSM-5 robustness" framing (conflicts with §5.3)
- ❌ "DSM-5 improves robustness"
- ❌ "DSM-5 is more robust under shift"
- ❌ "DSM-5 generalizes to MDD-5k"
- ❌ Any claim that DSM-5 helps the §5.3 bias claim

### Trap 3 — "Clinical validity" framing (round 16 + round 22d)
- ❌ "clinically validated DSM-5"
- ❌ "DSM-5 clinical performance"
- ❌ "clinical DSM-5 reasoning"
- ❌ "clinical diagnostic validity"
- ❌ "clinical bias / clinical asymmetry" anywhere referring to DSM-5 v0 results
- ❌ "DSM-5 mode meets clinical standards"

### Trap 4 — Both mode misframed (carry forward from §5.3 Trap 5)
- ❌ "Both mode is an ensemble"
- ❌ "Both mode combines ICD-10 and DSM-5"
- ❌ "Both mode picks the better of two predictions"
- ❌ "Dual-standard ensemble"

### Trap 5 — F42 collapse causality / patches
- ❌ "We patched the F42 threshold"
- ❌ "F42 was fixed in v0.2"
- ❌ "F42 recall is corrected"
- ❌ "F42 collapse is solved"
- ❌ "F42 loss is small"
- ✅ Only allowed: "F42 collapse is a v0 schema limitation; we document in §7.6 and do not claim F42 readiness."

### Trap 6 — v0 schema treated as clinical
- ❌ "DSM-5 criteria implementation"
- ❌ "DSM-5 schema"
- ❌ "DSM-5-grounded diagnosis"
- ❌ "DSM-5-validated reasoning"
- ✅ Only allowed: "DSM-5 v0 (LLM-drafted, unverified) criterion templates"

### Trap 7 — Aggressive mechanism verbs (round 18 + round 22)
Per stem-aware grep before commit:
- ❌ drives, drive, driving, driven
- ❌ achieves, achieve, achieving, achieved
- ❌ delivers, deliver, delivered, delivering
- ❌ yields, yield, yielded, yielding
- ❌ improves, improve, improved, improving
- ❌ demonstrates, demonstrate, demonstrating, demonstrated
- ❌ proves, prove, proved, proving
- ❌ causes, cause, caused, causing
- ❌ leads to, leading to
- ❌ carries, carry, carried, carrying

### Trap 8 — "is significant" (round 22e)
- ❌ "is significant" (without naming test)
- ❌ "DSM-5 vs ICD-10 difference is significant"
- ✅ Allowed: "statistically detectable under paired bootstrap" / "paired-bootstrap CI excludes 0"
- ✅ Allowed: "we do not claim per-metric significance for in-domain DSM-5 vs ICD-10; we report as descriptive trade-off"

### Trap 9 — Quantifier scope without bound (round 23b)
- ❌ "DSM-5 is the better choice" (unscoped)
- ❌ "DSM-5 performs better" (unscoped)
- ❌ "the dominant pattern is..." (must scope to dataset/metric)
- ✅ Allowed: "On MDD-5k, DSM-5 mode shows higher [metric] than ICD-10 mode by X.Xpp"

### Trap 10 — F42 recall numbers without context
- ❌ "F42 recall is 12%" (without ICD-10 baseline 52% + v0 caveat + §7.6 pointer)
- ❌ "DSM-5 F42 collapse" without "v0 schema limitation" qualifier
- ✅ Allowed: "On LingxiDiag paper-parent per-class analysis (n=25), DSM-5 mode F42/OCD recall decreases from 52% (ICD-10) to 12% (DSM-5), a 40pp drop attributable to the v0 schema's criterion-D exclusion structure; v4 slice metrics and MDD-5k show the same direction with smaller magnitudes (see Trap 12 and §7.6)"

### Trap 11 — "Comparable" used loosely
- ❌ "DSM-5 Top-3 is comparable to ICD-10" (without numerical bound)
- ✅ Allowed: "On LingxiDiag, DSM-5 Top-3 (0.803) and ICD-10 Top-3 (0.800) differ by 0.3pp"

### Trap 12 — Per-class vs slice-definition mismatch + source-aware claims (round 25/26 addition)
**Trap**: Reporting "F42 recall drops by X pp" without specifying whether X comes from paper-parent per-class analysis or v4 slice metrics, or denying that a definition exists when it does.
**Why dangerous**: F42 numbers differ across definitions and source files:
- LingxiDiag paper-parent per-class (n=25, from F42 limitation doc): 52% → 12% = −40pp
- LingxiDiag v4 slice metrics (n=36): 50.0% → 19.4% = −30.6pp
- MDD-5k paper-parent per-class (n=13, in `pilot_comparison.json` `per_mode_metrics.{icd10,dsm5}.per_class.F42`): 38.5% → 15.4% = −23.1pp
- MDD-5k v4 slice metrics (n=21): 47.6% → 23.8% = −23.8pp

A single "−40pp" claim is inaccurate for MDD-5k and conflates definitions. Saying "MDD paper-parent F42 was not measured" is also wrong because it exists in `pilot_comparison.json` — it just should not be used as a locked §5.4 headline metric (small N=13).

**Required disclosure**: Always name the definition AND source file when citing F42 magnitude. If a definition exists but is exploratory, say "exploratory only" — not "not measured".

**Allowed**:
- ✅ "F42/OCD recall decreases under DSM-5 v0 in both datasets; exact magnitude depends on the class/slice definition and is detailed in §7.6."
- ✅ "On LingxiDiag paper-parent per-class analysis (n=25, F42 limitation doc), F42 recall drops from 52% to 12% (−40pp); v4 slice metrics show smaller drops on both datasets."
- ✅ "MDD-5k paper-parent per-class F42 exists in `pilot_comparison.json` (5/13 → 2/13 = −23.1pp), but small N and we do not use it as a locked §5.4 headline metric."

**Forbidden**:
- ❌ "F42 recall drops by 40pp on both datasets"
- ❌ "F42 collapses by X pp" without naming the definition
- ❌ Quoting a single F42 magnitude as if it were dataset-invariant
- ❌ "MDD-5k paper-parent F42 was not measured" — it exists in `pilot_comparison.json`; the correct framing is "small-N exploratory, not used as locked claim"
- ❌ Claiming a metric doesn't exist when it exists in any of the four §5.4 source files (paper-parent per-class, v4 slice metrics, table4, F32/F41 asymmetry)

### Trap 13 — Small-N class claims (round 25 addition)
**Trap**: Citing apparent DSM-5 advantages on small-N classes (F45, F51, Z71, etc.) as primary evidence
**Why dangerous**: Class-level sample sizes are small in MDD-5k (often single digits or low double digits per class). A 1-2 case difference can flip the directional claim. These are not stable advantages.
**Required disclosure**: Treat small-N class observations as exploratory only; do not promote to primary §5.4 claim
**Allowed**:
- ✅ "Some small-N classes show apparent DSM-5 gains; we treat these as exploratory error-pattern observations and do not use them as primary evidence."
- ✅ "Class-level sample sizes are too small for stable per-class trade-off claims; we report aggregate metric-level trade-offs only."
**Forbidden**:
- ❌ "DSM-5 improves minor-class detection."
- ❌ "DSM-5 is better on F45 / F51 / Z71."
- ❌ Any class-level §5.4 claim that depends on n < 30 cases without explicit small-N caveat

---

## §5.4 LOCKED FRAMING (for round 25 confirmation)

> "DSM-5-only mode reveals dataset-dependent, metric-specific trade-offs relative to ICD-10 mode. On LingxiDiag-16K (in-domain, N=1000), DSM-5 mode underperforms ICD-10 mode on most metrics (Top-1 −3.6pp, F1-weighted −3.6pp, Overall −0.8pp; 4-class +2.9pp is the only DSM-5 directional win). On MDD-5k (synthetic shift, N=925), DSM-5 mode performs better on 2-class, 4-class, F1-macro, F1-weighted, and Overall, but worse on Top-1 and Top-3, and worsens F32/F41 asymmetry on both datasets (paired bootstrap (DSM-5 − ICD-10) Δratio CI excludes 0; see §5.3). Both mode preserves the ICD-10 primary output and exposes DSM-5 as sidecar audit evidence; final predictions match ICD-10 across all 15 metric keys on both datasets, so Both is an architectural pass-through, not an ensemble. DSM-5 v0 also degrades F42/OCD recall in both datasets, with magnitude depending on slice/class definition and detailed in §7.6. All DSM-5 numbers are audit observations under v0 LLM-drafted unverified criteria; clinical validity claims are scoped out per §7.2."

---

## §5.4 prose plan summary (when later authorized)

| ¶ | Topic | Length |
|---|---|---:|
| 1 | Setup: §5.1 primary ICD-10-labelled hybrid stacker benchmark; §5.4 standard-specific MAS audit modes; DSM-5 v0 unverified caveat | ~80w |
| 2 | LingxiDiag-16K table 5.4a + descriptive trade-off (DSM-5 worse on most metrics in-domain) | ~100w |
| 3 | MDD-5k table 5.4b + descriptive trade-off (DSM-5 mixed: better on F1-macro/F1-weighted/Overall, worse on Top-1/Top-3) | ~100w |
| 4 | Both = ICD-10 pass-through verified (table 5.4d); not ensemble | ~70w |
| 5 | Trade-off summary (table 5.4c) — dataset-dependent, metric-specific; cross-link to §5.3 (F32/F41 asymmetry) and §7.6 (F42 collapse) | ~100w |
| 6 | Connectors A–E (parity, bias scope, triage, F42 limitation, v0 unverified) | ~100w |

Estimated: ~550 words + 4 tables. Within ~500-700 target.

---

## DO NOT WRITE PROSE YET

This is the prep package only. Per GPT round 24:
> "現在可以開始 §5.4 Dual-Standard Audit prep package，但不要直接寫 prose."
> "Round 25 應該只 review §5.4 prep: source completeness、locked claims、connectors、overclaim traps."

After round 25 reviews and approves this prep, §5.4 prose v1 can be drafted.

---

## Round 25 review request (ready to send)

> §5.3 closed at `8a38344`. §5.4 prep package committed at `docs/paper/drafts/SECTION_5_4_PREP.md`.
>
> Round 25 review targets:
> 1. Item 1: 7 source artifacts authoritative? Connector sources covered (round 21a)?
> 2. Item 2: 4 locked tables — numbers correct? Both = ICD-10 pass-through verification adequate?
> 3. Item 3: 5 connectors A-E (4-tier matrix per round 20) — complete? redundant? missing?
> 4. Item 4: Allowed wording — too liberal? missing categories?
> 5. Item 5: 11 traps — anything missed?
> 6. Locked framing matches GPT round 24 verbatim?
>
> Targeted prose length: ~550 words + 4 tables.
>
> Awaiting round 25 verdict before §5.4 prose v1.

---

## My self-knowledge applied to this prep

All 24 rounds of cumulative lessons embedded:

| Lesson | Application |
|---|---|
| 16: clinical/deployment overclaim | Trap 3 forbids "clinical validity"/"clinical performance"/"clinical DSM-5" |
| 18: hedging language scrutiny | Trap 7 stem-aware verb list (10 verbs × all inflections) |
| 19: explicit narrative connectors | 5 connectors drafted FIRST as Item 3, before any prose |
| 20: connector inventory completeness | 4-tier matrix used (Tier 1-4 explicit) |
| 21a: source list includes connector sources | Connector source map appended to Item 1 |
| 21b: measurement language not achievement | "the measured X is Y" pattern in allowed wording |
| 22a: stem-aware grep | 10 verb stems × all inflections in Trap 7 |
| 22d: "clinical" adjective risk | Trap 3 expanded — even "clinical bias" forbidden |
| 22e: "is significant" alone | Trap 8 with paired-bootstrap requirement |
| 23a: table column-width hygiene | All 4 prep tables aligned (column widths match) |
| 23b: quantifier scope | Trap 9 forbids unscoped "dominant" / "better" / "comparable" |
| 23c: prep-prose sync | Allowed wording matches the future prose plan in Item 6 |
| 24a: paragraphs as single thoughts | Will apply when writing prose; not relevant for prep table-heavy structure |
| 24b: GitHub raw caching | Will verify with curl after future prose commit |
| 24c: defensive interpretation | Will assume reviewer reports of "broken formatting" are real |

§5.4 is the highest-risk section. Prep is over-engineered to compensate.
