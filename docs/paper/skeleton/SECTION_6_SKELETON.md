# CultureDx Paper — Section 6 Skeleton (Disagreement-as-Triage)

**Format**: (b) section-by-section with paste markers + Allowed/Forbidden wording guards
**Per GPT round 10–13**: skeleton greenlit; prose AFTER sync commit
**Note**: §6.2 source NARRATIVE_REFRAME currently STALE — wait for sync commit before writing prose

---

## Section 6 — Disagreement as Triage

### Overall narrative arc

> Disagreement signals (model discordance and diagnostic-standard discordance) provide reviewer-routing signal that is comparable to confidence-based triage and complementary to it. We do NOT claim disagreement beats confidence — bootstrap CI on the edge includes 0. Union policy is the strongest single rule.

---

## §6.1 — Model Discordance Triage

### Source artifacts
- `docs/analysis/DISAGREEMENT_AS_TRIAGE.md` (post-sync)
- `results/analysis/triage_metrics.json`
- Bootstrap CI computation: same script as §5.3

### Table 6 placeholder

```
| Triage rule | Flag rate | Acc unflagged | Acc flagged | Error enrichment | Error recall |
| TF-IDF/Stacker disagreement | 26.4% | 0.697 | 0.375 | 2.06× | 42.5% |
| Lowest 26.4% Stacker confidence (baseline) | 26.4% | 0.688 | 0.402 | 1.92× | 40.7% |
| Disagreement OR low confidence (union) | 38.9% | 0.733 | 0.422 | 2.17× | 58.0% |
| Disagreement AND low confidence (intersection) | 13.9% | 0.663 | 0.295 | 2.09× | 25.3% |
```

### Bootstrap CI placeholder

```
Δ enrichment (disagreement - confidence): 95% CI [-0.204, +0.473]  — INCLUDES 0
Δ error recall (disagreement - confidence): 95% CI [-0.043, +0.073]  — INCLUDES 0
Jaccard overlap (disagreement ∩ confidence flag sets): 0.360
```

### Key claims (LOCKED)

1. TF-IDF/Stacker disagreement at 26.4% flag rate yields 2.06× error enrichment, 42.5% recall
2. Stacker confidence baseline at same flag rate: 1.92× / 40.7%
3. Bootstrap CI on the disagreement-vs-confidence edge INCLUDES 0 — therefore comparable, NOT superior
4. Jaccard 0.360 — flag sets are 36% overlapping, 64% complementary
5. Union policy (disagreement OR low confidence) at 38.9% flag captures 58.0% of errors at 2.17× enrichment — strongest single rule
6. Architecture pair triage (TF-IDF/MAS-only deployed=MAS-only): 44.0% flag, 2.78× enrichment, 68.6% recall

### Allowed wording

- ✅ "Disagreement and confidence triage rules are statistically comparable at equal flag rate"
- ✅ "Statistically similar + complementary"
- ✅ "Union policy captures 58% of errors at 38.9% flag rate"
- ✅ "Reviewer-routing signal"
- ✅ "Triage signal, not accuracy-improving ensemble"
- ✅ "Bootstrap CI includes zero"
- ✅ "Comparable in magnitude"

### Forbidden wording

- ❌ "Disagreement beats confidence"
- ❌ "Disagreement is significantly better than confidence"
- ❌ "Disagreement is the optimal triage signal"
- ❌ "TF-IDF/Stacker disagreement detects errors with 99% precision" (the round-4-corrected tautology)
- ❌ "Disagreement enables ensemble improvement" (it's triage, not ensemble)

### Reviewer attacks + responses

**Q1**: "Why include disagreement triage if it's no better than confidence?"
**A**: It's complementary (Jaccard 0.360 = 64% non-overlap) and the union of the two policies achieves the highest single-rule recall (58%). The contribution is a complementary triage rule + the union policy operating point, not a superior single rule.

**Q2**: "What's the operational use case?"
**A**: Routing reviewer attention. At 26.4% flag, a clinician reviewing only flagged cases sees 42.5% of system errors with 2.06× density above baseline. Useful for cost-bounded clinical audit.

**Q3**: "Is bootstrap CI on triage edge robust enough?"
**A**: 1000 resamples, paired by case_id, seed-fixed. CI [-0.204, +0.473] indicates substantial variance — small bias toward disagreement (+0.14× point estimate) but indistinguishable at α=0.05. We report this transparently rather than claiming superiority.

**Q4**: "Can disagreement triage be combined with active learning or human-in-the-loop?"
**A**: Yes — the architecture pair triage (TF-IDF/MAS-only) when MAS-only is deployed yields 2.78× enrichment, suggesting deployment scenarios where MAS-only is the production model could route 44% of cases to TF-IDF cross-checking with 68.6% error recall.

### Length target

~350 words + Table 6

---

## §6.2 — Diagnostic-Standard Discordance Audit

### Source artifacts
- `docs/analysis/DISAGREEMENT_AS_TRIAGE.md` (cross-dataset section)
- `docs/paper/NARRATIVE_REFRAME.md` Section 6.2 (post-sync — currently STALE)

### Table 7 placeholder

```
| Dataset | Deployed | N | Flag rate | Acc unflagged | Acc flagged | Enrichment | Error recall |
| LingxiDiag | ICD-10 | 1000 | 25.1% | 0.549 | 0.382 | 1.37× | 31.4% |
| LingxiDiag | DSM-5 | 1000 | 25.1% | 0.549 | 0.239 | 1.69× | 36.1% |
| MDD-5k | ICD-10 | 925 | 20.8% | 0.656 | 0.370 | 1.83× | 32.4% |
| MDD-5k | DSM-5 | 925 | 20.8% | 0.656 | 0.292 | 2.06× | 35.1% |
```

### Key claims (LOCKED with round-9 caution)

1. ICD-10/DSM-5 disagree on 25.1% of LingxiDiag cases, 20.8% of MDD-5k cases
2. Diagnostic-standard discordance triage signal is meaningful across both datasets (1.37–2.06×)
3. Cross-dataset signal magnitude is COMPARABLE IN MAGNITUDE (not "same") to in-domain model-discordance
4. Higher enrichment under DSM-5 deployment reflects DSM-5's lower baseline accuracy on MDD-5k, NOT DSM-5-specific triage value
5. Both deployment perspectives reported to avoid cherry-picking
6. Cross-dataset enrichment ratios should be interpreted cautiously (different deployed models, baselines, and distribution)

### Allowed wording

- ✅ "Comparable in magnitude" (NOT "same triage power" — round 9 correction)
- ✅ "Generalizes across datasets but with caveats"
- ✅ "Cross-dataset enrichment ratios should be interpreted cautiously"
- ✅ "Higher enrichment under DSM-5 deployment reflects DSM-5's lower baseline accuracy"
- ✅ "Different deployed models, datasets, and baseline error rates"
- ✅ "Both deployment perspectives reported to avoid cherry-picking"

### Forbidden wording

- ❌ "Same triage power" (round 9 correction — caused overclaim)
- ❌ "DSM-5 deployment is better for triage"
- ❌ "MDD-5k confirms LingxiDiag triage finding" (different signal magnitudes)
- ❌ "Diagnostic-standard discordance is more informative than model discordance"
- ❌ "DSM-5 v0 has triage-improving properties"

### Reviewer attacks + responses

**Q1**: "Why does enrichment increase from 1.37× (LingxiDiag) to 1.83-2.06× (MDD-5k)?"
**A**: MDD-5k has lower baseline accuracy (~0.6 vs ~0.55 for in-domain ICD-10). Lower baseline = more headroom for enrichment. We report this transparently rather than attributing it to DSM-5-specific value.

**Q2**: "DSM-5 deployment yields higher enrichment than ICD-10 deployment — is DSM-5 better?"
**A**: No. DSM-5 deployment has lower unflagged accuracy (0.549 → 0.239 on LingxiDiag), so the SAME flag set yields higher relative enrichment. This is arithmetic, not DSM-5 superiority. The Section 5.4 result (DSM-5 amplifies F32/F41 asymmetry) further argues against DSM-5 deployment for primary diagnosis.

**Q3**: "Why is the ICD-10/DSM-5 flag rate different from model-discordance flag rate (25.1% vs 26.4%)?"
**A**: Different signals capturing different uncertainty types — ICD-10/DSM-5 captures standard-level reasoning conflict; TF-IDF/Stacker captures model-level prediction conflict. Both are reported separately because they identify different case populations.

### Length target

~300 words + Table 7

---

## Section 6 total length target

~650 words + 2 tables (Table 6 model discordance, Table 7 diagnostic-standard discordance)

---

## §6 SOURCE-DEPENDENCY NOTE

Before writing §6.2 prose, NARRATIVE_REFRAME.md §6.2 must be sync'd from `DISAGREEMENT_AS_TRIAGE.md`. Currently NARRATIVE still says:
> "A formal MDD-5k error-enrichment triage table remains a next zero-GPU analysis."

This will be fixed in the round-13 sync commit. Skeleton is safe to write now (it doesn't depend on stale narrative); prose drafting waits for sync.
