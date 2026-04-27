# §6.1 / §6.2 — Disagreement Triage Prep Package

**Date**: 2026-04-27
**Per GPT round 34**: §5.4 closed at `ee8e3c3`. Greenlight §6.1/§6.2 prep only (NOT prose).
**Length target for §6 prose** (when written later): ~600-800 words + 3 tables across §6.1 + §6.2.
**Format discipline**: Sentence-level line breaks throughout (lesson 33a applied during drafting).

---

## ITEM 1 — Source artifacts

All 7 confirmed exist on remote `ee8e3c3`.

| Artifact | Path | Status | Role |
|---|---|:---:|---|
| Disagreement triage analysis | `docs/analysis/DISAGREEMENT_AS_TRIAGE.md` | ✓ | Primary reference for both §6.1 and §6.2 numbers |
| LingxiDiag dual-standard pilot | `results/dual_standard_full/lingxidiag16k/pilot_comparison.json` | ✓ | ICD-10/DSM-5 mode disagreement at case level (LingxiDiag) |
| MDD-5k dual-standard pilot | `results/dual_standard_full/mdd5k/pilot_comparison.json` | ✓ | ICD-10/DSM-5 mode disagreement at case level (MDD-5k) |
| Metric consistency report | `results/analysis/metric_consistency_report.json` | ✓ | Stacker / TF-IDF paired predictions for §6.1 |
| §5.1 prose | `docs/paper/drafts/SECTION_5_1.md` | ✓ | Connector A target (primary ICD-10-labelled hybrid stacker benchmark) |
| §5.2 prose | `docs/paper/drafts/SECTION_5_2.md` | ✓ | Connector B target (MAS feature-importance share) |
| §5.4 prose | `docs/paper/drafts/SECTION_5_4.md` | ✓ | Connector C target (standard-specific trade-offs) |

### Connector source-map (per round 21a)

| Connector | References | Source |
|---|---|---|
| §6.1 → §5.1 | "primary ICD-10-labelled hybrid stacker benchmark" | committed `SECTION_5_1.md` |
| §6.1 → §5.2 | MAS 11.9% feature-importance share | committed `SECTION_5_2.md` |
| §6.2 → §5.4 | DSM-5-only mode metric trade-offs | committed `SECTION_5_4.md` |
| §6 → §7 | v0 DSM-5 unverified scope; small-N caveat | (planned §7.2 / §7.6) |

---

## ITEM 2 — Locked tables (numbers verified from artifacts)

### Table 6.1a — Model-discordance vs confidence baseline (LingxiDiag-16K test_final, N = 1000)

*Primary-output model for §6.1 = Stacker LGBM. Acc unflagged / Acc flagged / Error enrichment / Error recall are computed against the Stacker LGBM Top-1 predictions and gold labels.*

| Triage rule | Flag rate | Acc unflagged | Acc flagged | Error enrichment | Error recall |
|---|---:|---:|---:|---:|---:|
| TF-IDF/Stacker disagreement | 26.4% | 0.697 | 0.375 | 2.06× | 42.5% |
| Lowest 26.4% Stacker confidence (baseline) | 26.4% | 0.688 | 0.402 | 1.92× | 40.7% |

**Bootstrap (1000 resamples, seed 20260420, paired by case_id):**

| Metric | Δ (disagreement − confidence) | 95% CI | Includes 0? |
|---|---:|:---:|:---:|
| Δ Enrichment | +0.14× | [−0.204, +0.473] | Yes |
| Δ Recall | +0.018 | [−0.043, +0.073] | Yes |

Both CIs include 0; do not claim statistical superiority of disagreement over confidence.

### Table 6.1b — Union policy (model OR confidence)

| Policy | Flag rate | Error enrichment | Error recall | Jaccard with TF-IDF disagreement |
|---|---:|---:|---:|---:|
| TF-IDF/Stacker disagreement | 26.4% | 2.06× | 42.5% | 1.000 (self) |
| Lowest 26.4% confidence | 26.4% | 1.92× | 40.7% | 0.357 |
| Disagreement OR low confidence (union) | 38.9% | 2.17× | 58.0% | 0.679 (with disagreement) |

Two-stage policy ("flag if either signal fires") increases recall to 58.0% at the cost of higher review burden (38.9%).

### Table 6.2a — Diagnostic-standard discordance across datasets

| Dataset | Primary-output model | N | Flag rate | Acc unflagged | Acc flagged | Error enrichment | Error recall |
|---|---|---:|---:|---:|---:|---:|---:|
| LingxiDiag-16K | ICD-10 | 1000 | 25.1% | 0.549 | 0.382 | 1.37× | 31.4% |
| LingxiDiag-16K | DSM-5 v0 | 1000 | 25.1% | 0.549 | 0.239 | 1.69× | 36.1% |
| MDD-5k | ICD-10 | 925 | 20.8% | 0.656 | 0.370 | 1.83× | 32.4% |
| MDD-5k | DSM-5 v0 | 925 | 20.8% | 0.656 | 0.292 | 2.06× | 35.1% |

Enrichment range across the four configurations: 1.37× to 2.06×. Cross-dataset comparison should be interpreted cautiously because of different datasets, primary-output perspectives, baseline error rates, and diagnostic-distribution concentration.

---

## ITEM 3 — Narrative connectors (4-tier matrix, drafted FIRST per round 19/20)

### Connector A — §6.1 → §5.1 (parity ≠ equal risk)

> "The §5.1 primary ICD-10-labelled hybrid stacker benchmark documents aggregate Top-1 / F1 / Overall on the test set. §6.1 shows that the same primary model has materially uneven error concentration across cases: the 26.4% flagged subset (where TF-IDF and Stacker disagree) has 2.06× the error rate of the unflagged subset. Section 5.1 parity does not imply uniform reliability across cases."

### Connector B — §6.1 → §5.2 (MAS small importance ≠ no audit value)

> "The §5.2 stacker importance analysis assigns MAS reasoning an aggregate share of 11.9% across feature blocks; this is a marginal contribution to Top-1 prediction.
> The hybrid stacker output, which includes MAS-derived features, can be compared with TF-IDF predictions to expose a model-discordance signal that flags 26.4% of cases at 2.06× error enrichment in §6.1; this does not imply that the MAS feature block alone causes the disagreement.
> Aggregate feature importance and case-level audit value are different evaluation properties."

### Connector C — §6.2 → §5.4 (standard trade-offs become triage signal)

> "The §5.4 dual-standard audit reports that DSM-5-only mode and ICD-10 mode produce different metric trade-offs on the same cases. §6.2 reframes that finding at the case level: ICD-10/DSM-5 mode disagreement, computed per case, identifies 25.1% of LingxiDiag and 20.8% of MDD-5k cases as audit-priority. Diagnostic-standard discordance is therefore an audit / triage signal that complements the §5.4 metric-level trade-off, not evidence that DSM-5 is superior."

### Connector D — §6 → §7 (limitations / scope)

> "Triage results in §6 are observed on synthetic / curated test data (LingxiDiag-16K test_final and MDD-5k); we do not claim deployment readiness. The diagnostic-standard discordance analysis uses DSM-5 v0 (LLM-drafted, unverified per `dsm5_criteria.json`); we document this scope limitation in §7.2. Cross-dataset enrichment comparisons in §6.2 are descriptive only because the comparisons involve different datasets, primary-output perspectives, and baseline error rates."

---

## ITEM 4 — Allowed wording

### Triage signal terminology

- ✅ "model-discordance signal"
- ✅ "diagnostic-standard discordance"
- ✅ "TF-IDF/Stacker disagreement" (specific component pair)
- ✅ "ICD-10/DSM-5 mode disagreement"
- ✅ "audit / triage signal"
- ✅ "risk-stratification signal"
- ✅ "two-stage triage policy" (for union)
- ✅ "configurable review-burden operating points"

### Comparison framing (disagreement vs confidence)

- ✅ "complementary to confidence triage"
- ✅ "statistically similar to confidence at equal review budget"
- ✅ "partially complementary populations (Jaccard 0.357)"
- ✅ "union policy captures more errors than either alone"
- ✅ "raw point estimate of disagreement enrichment is +0.14× higher than confidence; the bootstrap 95% CI [−0.204, +0.473] includes zero"

### Cross-dataset framing (§6.2)

- ✅ "comparable in magnitude" (with the caveat that datasets differ)
- ✅ "enrichment ratios range from 1.37× to 2.06× across the four configurations"
- ✅ "the higher enrichment under the DSM-5 primary-output perspective reflects lower DSM-5 accuracy within flagged ICD-10/DSM-5 disagreement cases, not DSM-5-specific triage value"
- ✅ "more informative under distribution shift" — only with the caveat that the comparisons involve different datasets, primary-output perspectives, and baselines

### Operating-point reporting

- ✅ "at 26.4% flag rate, disagreement triage achieves 2.06× error enrichment and 42.5% error recall"
- ✅ "the union policy operates at 38.9% flag rate and 58.0% error recall"
- ✅ "we report multiple operating points; choice depends on review budget"

### Scope and limitation

- ✅ "we do not claim deployment readiness"
- ✅ "evaluated on synthetic / curated test data"
- ✅ "DSM-5 v0 is reported as audit observation under unverified LLM-drafted criteria (§7.2)"

---

## ITEM 5 — Forbidden wording / traps

### Trap 1 — "Disagreement beats confidence"

**Trap**: Claiming statistical superiority of disagreement over confidence baseline.
**Why dangerous**: Bootstrap 95% CI includes zero on both Δ enrichment ([−0.204, +0.473]) and Δ recall ([−0.043, +0.073]).
**Forbidden**:
- ❌ "disagreement beats confidence"
- ❌ "statistically better than confidence"
- ❌ "disagreement outperforms confidence triage"
- ❌ "marginal advantage" / "trending toward significance"
**Allowed**:
- ✅ "statistically similar to confidence at equal review budget; raw point estimate +0.14× higher but CI [−0.204, +0.473] includes zero"

### Trap 2 — Overstating recall

**Trap**: Citing recall numbers without flag-rate context, or implying near-complete coverage.
**Forbidden**:
- ❌ "captures 99% of errors"
- ❌ "comprehensive error coverage"
- ❌ "near-perfect triage"
- ❌ "high-recall triage" without naming flag rate
**Allowed**:
- ✅ "captures 42.5% of errors at 26.4% flag rate"
- ✅ "union policy captures 58.0% of errors at 38.9% flag rate"

### Trap 3 — "Independent decision paths" (round 16 carry-forward)

**Trap**: Calling TF-IDF and Stacker independent or implying mechanistic independence.
**Why dangerous**: TF-IDF features are inputs to the Stacker LGBM; they are correlated, not independent. The signal is "model discordance", not "two independent voters".
**Forbidden**:
- ❌ "independent decision paths"
- ❌ "TF-IDF and Stacker vote independently"
- ❌ "two independent classifiers"
**Allowed**:
- ✅ "model-discordance signal between TF-IDF and Stacker predictions"
- ✅ "the two model outputs are correlated; we report disagreement as a triage signal, not as evidence of independence"

### Trap 4 — Deployment claims (cumulative round 16)

**Forbidden**:
- ❌ "deployment-ready triage policy"
- ❌ "clinically validated triage"
- ❌ "production-grade audit signal"
- ❌ "deployed model" / "deployed system" / "deployment threshold"
- ❌ "ready for clinical use"
**Allowed**:
- ✅ "evaluated on synthetic / curated test data"
- ✅ "we do not claim deployment readiness"
- ✅ "configurable review-burden operating points"
- ✅ "primary-output model" (when describing which mode produced the predictions)

### Trap 5 — DSM-5 superiority via diagnostic-standard discordance

**Trap**: Inferring DSM-5 quality from higher diagnostic-standard discordance enrichment under the DSM-5 primary-output perspective.
**Why dangerous**: Higher enrichment under the DSM-5 primary-output perspective reflects lower DSM-5 accuracy within flagged ICD-10/DSM-5 disagreement cases (Table 6.2a: LingxiDiag flagged 0.239 DSM-5 vs 0.382 ICD-10; MDD-5k flagged 0.292 DSM-5 vs 0.370 ICD-10), not DSM-5-specific triage value. Within-dataset unflagged accuracy is identical between perspectives, so the mechanism is not a baseline-accuracy gap.
**Forbidden**:
- ❌ "DSM-5 has stronger triage"
- ❌ "DSM-5 generalizes better"
- ❌ "diagnostic-standard discordance validates DSM-5"
- ❌ "DSM-5 enrichment indicates DSM-5 superiority"
**Allowed**:
- ✅ "the higher enrichment under the DSM-5 primary-output perspective reflects lower DSM-5 accuracy within flagged ICD-10/DSM-5 disagreement cases, not DSM-5-specific triage value"
- ✅ "we report both perspectives because both correspond to legitimate audit configurations under §5.4"

### Trap 6 — Both mode ensemble (cumulative §5.4 carry-forward)

**Forbidden**:
- ❌ "Both mode ensemble"
- ❌ "ensemble triage"
- ❌ "diagnostic-standard ensemble"
**Allowed**:
- ✅ "Both mode preserves ICD-10 primary output and exposes DSM-5 as sidecar audit evidence (§5.4)"
- ✅ "diagnostic-standard discordance is an audit signal, not a way to combine predictions"

### Trap 7 — Cross-dataset enrichment ranking

**Trap**: Treating MDD-5k enrichment > LingxiDiag enrichment as a meaningful comparison.
**Why dangerous**: The comparisons involve different datasets, primary-output perspectives, baseline error rates, and diagnostic-distribution concentration. MDD-5k has more concentrated F32+F41 distribution (77% vs 72% in LingxiDiag), so the 20.8% disagreement subset is enriched for harder cases — this is a structural difference, not a robustness claim.
**Forbidden**:
- ❌ "MDD-5k > LingxiDiag" (or any direct ranking)
- ❌ "diagnostic-standard discordance generalizes better to MDD-5k"
- ❌ "the signal strengthens under distribution shift" (without "may", "appears", and the caveat)
**Allowed**:
- ✅ "enrichment ratios range from 1.37× to 2.06× across the four configurations"
- ✅ "the signal magnitude appears stronger on MDD-5k, but cross-dataset enrichment ratios should be interpreted with caution because they involve different datasets, primary-output perspectives, and baseline error rates"
- ✅ "MDD-5k disagreement rate is 20.8% versus LingxiDiag's 25.1%; this likely reflects MDD-5k's more concentrated diagnostic distribution"

### Trap 8 — Aggressive mechanism verbs (cumulative round 18 / 22)

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

**Allowed mechanism wording**:
- ✅ "produces" / "shows" / "reports" / "documents" / "exposes" / "flags"
- ✅ "captures" (only with explicit flag rate and recall)

### Trap 9 — Bootstrap CI misinterpretation (round 22e + new)

**Forbidden**:
- ❌ "is significant" without naming test
- ❌ "approaches significance"
- ❌ "marginal advantage" / "trending toward significance"
- ❌ "borderline significant"
**Allowed**:
- ✅ "bootstrap 95% CI [−0.204, +0.473] includes zero"
- ✅ "we do not claim statistical superiority"
- ✅ "raw point estimate is +0.14× but CI is consistent with zero"

### Trap 10 — Quantifier scope (round 23b carry-forward)

**Forbidden**:
- ❌ "comparable" without bound (e.g., "comparable triage power")
- ❌ "similar enrichment" without numerical range
**Allowed**:
- ✅ "comparable in magnitude (1.83× and 2.06× on MDD-5k vs 1.37× and 1.69× on LingxiDiag)"
- ✅ "enrichment ratios in the 1.37×–2.06× range across the four configurations"

### Trap 11 — F42 magnitude residue (cumulative §5.4 carry-forward)

§6 should not need to discuss F42 specific magnitudes. If F42/OCD comes up, defer to §7.6.

**Forbidden**:
- ❌ "F42 collapse 52% → 12%" anywhere in §6 prose
- ❌ "F42 −40pp" anywhere in §6 prose
**Allowed**:
- ✅ "F42/OCD details are reported in §7.6"

### Trap 12 — Clinical validity (cumulative round 16 / 22d)

**Forbidden**:
- ❌ "clinically validated triage"
- ❌ "clinical risk stratification"
- ❌ "clinical performance"
**Allowed**:
- ✅ "audit observation under unverified LLM-drafted criteria (§7.2)"
- ✅ "evaluated on synthetic / curated test data"

---

## ITEM 6 — Reviewer attacks + responses

### Attack 1: "26.4% flag rate is too high for clinical deployment"

**Response**: Frame as configurable operating point, not single deployment threshold.
> "We report multiple operating points (26.4% disagreement, 38.9% union, lower-flag-rate confidence quantile). Choice depends on review budget; we do not claim a deployment threshold."

### Attack 2: "Disagreement is just confidence under another name (CI overlap)"

**Response**: Different populations, complementary policy.
> "Bootstrap CI on the disagreement-vs-confidence advantage includes zero, so we do not claim statistical superiority. However, Jaccard 0.357 indicates partially complementary flagged populations, and a union policy captures 58.0% of errors at 38.9% flag rate — strictly more than either signal alone."

### Attack 3: "Higher enrichment under the DSM-5 primary-output perspective proves DSM-5 is better"

**Response**: Flagged-subset accuracy mechanism.
> "The higher enrichment under the DSM-5 primary-output perspective (1.69× / 2.06×) versus the ICD-10 primary-output perspective (1.37× / 1.83×) reflects lower DSM-5 accuracy within the flagged disagreement subset (LingxiDiag flagged accuracy 0.239 DSM-5 vs 0.382 ICD-10; MDD-5k flagged accuracy 0.292 DSM-5 vs 0.370 ICD-10), not DSM-5-specific triage value or DSM-5 superiority.
> Section 5.4 documents that DSM-5-only mode underperforms ICD-10 mode on Top-1 / weighted-F1 / Overall on LingxiDiag and worsens F32/F41 asymmetry on both datasets."

### Attack 4: "MDD-5k disagreement rate is lower (20.8%) — does the signal weaken under shift?"

**Response**: Separate flag rate from signal strength; explain via diagnostic concentration.
> "Flag rate measures how often the two modes disagree, while enrichment measures how concentrated errors are in the disagreement subset.
> MDD-5k disagreement rate (20.8%) is lower than LingxiDiag (25.1%); this may partly reflect MDD-5k's more concentrated diagnostic distribution (77% F32+F41 vs 72% in LingxiDiag), under which the two modes can be expected to agree on the majority cases more often.
> The 20.8% disagreement subset is nevertheless enriched for harder cases, consistent with the higher enrichment ratio (2.06× vs 1.37×).
> Cross-dataset enrichment comparisons remain caveated."

### Attack 5: "Why not also report a confidence baseline for §6.2?"

**Response**: Acknowledge the gap; defer to future work.
> "We computed the confidence-quantile baseline for §6.1 model discordance because TF-IDF and Stacker share the same primary-output target. For §6.2 diagnostic-standard discordance, the two modes have different metric profiles (§5.4), so a single confidence quantile is not the natural baseline. We document this asymmetry as a limitation."

### Attack 6: "What about confidence-disagreement intersection (not union)?"

**Response**: Higher precision, lower recall — included in source doc but not headline claim.
> "The intersection ('flag only if both fire') yields a smaller flagged set with higher per-flag enrichment but lower recall. We focus on the union as the headline two-stage policy because it captures more errors at moderate review burden; the intersection is documented in `DISAGREEMENT_AS_TRIAGE.md` for completeness."

---

## ITEM 7 — Prose plan (NO PROSE)

Per GPT round 34 explicit:
> "Do not draft §6 prose before this prep review."

When authorized, structure (~600-800 words across §6.1 + §6.2 + 3 tables):

### §6.1 — Model-discordance triage (~300-400w + Tables 6.1a + 6.1b)

| ¶ | Topic | Length |
|---|---|---:|
| 1 | Setup: §5.1 reports aggregate parity; §6.1 measures case-level error concentration | ~70w |
| 2 | TF-IDF/Stacker disagreement triage + Table 6.1a (26.4% flag, 2.06× / 42.5%, vs confidence baseline 1.92× / 40.7%; bootstrap CI includes zero) | ~120w |
| 3 | Union policy + Table 6.1b (38.9% / 2.17× / 58.0%; trade-off vs review burden) | ~80w |
| 4 | Connectors A + B (parity ≠ equal risk; aggregate feature importance ≠ case-level audit value); scope limitation | ~80w |

### §6.2 — Diagnostic-standard discordance triage (~300-400w + Table 6.2a)

| ¶ | Topic | Length |
|---|---|---:|
| 1 | Setup: §5.4 metric-level trade-off → §6.2 case-level audit signal | ~70w |
| 2 | LingxiDiag results (25.1% flag; 1.37× / 31.4% ICD-10 perspective; 1.69× / 36.1% DSM-5 perspective) + Table 6.2a top half | ~100w |
| 3 | MDD-5k results (20.8% flag; 1.83× / 32.4% / 2.06× / 35.1%) + Table 6.2a bottom half + diagnostic-concentration explanation | ~120w |
| 4 | Connectors C + D (audit signal not DSM-5 superiority; v0 unverified scope; cross-dataset comparison caveat) | ~100w |

---

## §6 LOCKED FRAMING (for round 35 confirmation)

> "§6.1 reports the TF-IDF/Stacker model-discordance signal as a case-level triage signal that flags 26.4% of LingxiDiag-16K cases at 2.06× error enrichment and 42.5% recall.
> This is statistically similar to a confidence-quantile baseline at equal flag rate (paired bootstrap CI includes zero), but the two signals flag partially complementary populations (Jaccard 0.357), and a union policy captures more errors than either alone (38.9% / 2.17× / 58.0%).
>
> §6.2 reframes the §5.4 dual-standard metric trade-off as a case-level diagnostic-standard discordance signal.
> ICD-10/DSM-5 mode disagreement flags 25.1% of LingxiDiag cases (1.37× / 31.4% under ICD-10 primary-output perspective, 1.69× / 36.1% under DSM-5 primary-output perspective) and 20.8% of MDD-5k cases (1.83× / 32.4% under ICD-10, 2.06× / 35.1% under DSM-5).
> The higher enrichment under the DSM-5 primary-output perspective reflects lower DSM-5 accuracy within flagged ICD-10/DSM-5 disagreement cases (per Table 6.2a flagged-subset accuracy), not DSM-5-specific triage value.
>
> All §6 numbers are observed on synthetic / curated test data; we do not claim deployment readiness."

---

## DO NOT WRITE PROSE YET

Per GPT round 34:
> "Do not draft §6 prose before this prep review."

After round 35 reviews and approves this prep (or requests changes), §6.1 / §6.2 prose can be drafted.

---

## Round 35 review request (to send after commit)

```
§6.1 / §6.2 prep committed at <hash>.

Round 35 narrow review:
1. Are model-discordance and confidence baseline framed correctly?
2. Is the disagreement-vs-confidence CI interpreted correctly?
3. Is diagnostic-standard discordance separated from DSM-5 superiority?
4. Are cross-dataset enrichment comparisons sufficiently cautious?
5. Can we start §6 prose?
```

---

## Self-applied lessons 14-33

Lessons embedded in this prep:

| Lesson | Application |
|---|---|
| 16 / 22d / 27a / 27b | "deployed" / "clinically validated" only in negated/forbidden context (Traps 4, 12) |
| 18 / 22a-c | Stem-aware verb grep target (Trap 8: 10 stems × inflections) |
| 19 / 20 | Connectors drafted FIRST as Item 3, 4-tier matrix |
| 21a | Source list includes connector sources (Item 1 has connector source-map) |
| 21b | Measurement language not achievement |
| 22e | "is significant" alone forbidden (Trap 9 — bootstrap CI must be cited) |
| 23a | All tables column-aligned with right-justified numerics |
| 23b | Quantifier scope (Trap 10 — "comparable" requires numerical bound) |
| 23c | Allowed wording matches future prose plan in Item 7 |
| 25a / 25c / 25d | Every cell in Item 2 verified against `DISAGREEMENT_AS_TRIAGE.md` line numbers; numbers cross-checked against §5.4 connector C |
| 25b / 32a | Mode terminology: "TF-IDF/Stacker disagreement" vs "ICD-10/DSM-5 mode disagreement" — distinct concepts; "primary-output model" used (not "deployed model") |
| 26a | Source-aware claims: §6.1 source list explicitly cites `DISAGREEMENT_AS_TRIAGE.md` line numbers via `metric_consistency_report.json` |
| 26b / 27c / 28a / 29a | 5 location classes consistent throughout (trap descriptions, allowed wording, connector bodies, source artifact roles, connector source-map rows) |
| 31a | Cross-section numerical convention: §6.2 cites the same enrichment direction as §5.4 Connector C (ICD-10 perspective 1.83× / DSM-5 perspective 2.06× on MDD-5k, matching `DISAGREEMENT_AS_TRIAGE.md` table 175) |
| 33a | **Format-during-draft**: this prep file uses sentence-level line breaks throughout; no super-long paragraphs |

§6 is lower-risk than §5.4 (fewer mode-conflation surfaces) but still requires explicit prep-first discipline because of:
- Bootstrap CI interpretation (Trap 9 — easy to overclaim "advantage" when CI includes zero)
- Cross-dataset enrichment ranking (Trap 7 — easy to claim DSM-5/MDD-5k superiority)
- "Independent decision paths" residue (Trap 3 — round 16 forbade, but needs re-screening)
