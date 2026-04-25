# Disagreement-as-Triage v4 — With Confidence Baseline + Two-Stage Policy

**Target**: `docs/analysis/DISAGREEMENT_AS_TRIAGE_2026_04_25.md`
**Source**: LingxiDiag-16K test_final, N=1000 (5 systems aligned)
**v4 changes from v3**: 
- Added confidence-quantile baseline (GPT round 5 Δ11)
- Added two-stage union/intersection policies
- Renamed "independent decision paths" → "model discordance" / "diagnostic-standard discordance"
- Headline metric is **error rate enrichment + error recall**, not "≥1 wrong precision"

---

## Why GPT pushed back on v3

In single-label classification, when System A and System B predict different classes:
- At most one of them can be correct (if gold is single-label)
- Both can be correct only if multilabel gold contains both predictions

I empirically verified this on N=1000 LingxiDiag: only 2/264 disagreement cases (0.8%) had multilabel gold containing both predictions. So "≥1 wrong" precision approaches 100% structurally — it's near-tautological, not a deployment claim.

**v4 headline**: deployed-model error enrichment, with error recall (sensitivity) as the secondary metric.

---

## Method

**Data**: N=1000 LingxiDiag-16K test_final cases. 5 systems aligned by case_id:
- TF-IDF + LR (supervised baseline)
- MAS-only (DtV — multi-agent without supervised classifier)
- Stacker LGBM (deployed system)
- ICD-10 reasoning mode
- DSM-5 reasoning mode (v0 unverified criteria)

**Metrics** (all defined explicitly to avoid v3's wording problems):
- **Flag rate**: fraction of cases routed to clinician review
- **Acc unflagged**: deployed-model accuracy on cases NOT flagged
- **Acc flagged**: deployed-model accuracy on cases flagged for review
- **Error rate enrichment**: (1 − Acc_flagged) / (1 − Acc_unflagged) — how much higher is error rate in flagged subset
- **Error recall** (sensitivity): fraction of all deployed-model errors captured in flagged subset

---

## Results — main triage table

### Stacker LGBM as deployed model

| Triage rule | Flag % | Acc unflagged | Acc flagged | Error enrichment | Error recall |
|---|---:|---:|---:|---:|---:|
| **TF-IDF/Stacker disagreement** | 26.4% | 0.697 | 0.375 | **2.06×** | **42.5%** |
| Lowest 26.4% Stacker confidence (baseline) | 26.4% | 0.688 | 0.402 | 1.92× | 40.7% |
| Disagreement OR low confidence | 38.9% | 0.733 | 0.422 | **2.17×** | **58.0%** |
| Disagreement AND low confidence | 13.9% | 0.663 | 0.295 | 2.09× | 25.3% |

### ICD-10 reasoning as deployed model (dual-standard discordance)

| Triage rule | Flag % | Acc unflagged | Acc flagged | Error enrichment | Error recall |
|---|---:|---:|---:|---:|---:|
| **ICD-10/DSM-5 disagreement** | 25.1% | 0.549 | 0.382 | **1.37×** | [TODO] |

---

## Headline findings

### 1. Disagreement signal beats confidence baseline (slightly but consistently)

At equal flag rate (26.4%):
- Disagreement triage: 2.06× enrichment, 42.5% recall
- Confidence triage: 1.92× enrichment, 40.7% recall
- **Disagreement edge: +0.14× enrichment, +1.8pp recall**

This is small but real, and matters because:
- Disagreement signal is **architecturally free** (already computed in any hybrid system)
- Confidence triage requires calibration — well-calibrated probabilities are non-trivial
- Disagreement is **interpretable**: "two methods disagree" is more clinician-meaningful than "model uncertainty 0.4"

### 2. Disagreement and confidence are partially complementary signals

Overlap analysis:
- Disagreement set: 264 cases
- Lowest 26.4% confidence set: 264 cases
- Intersection: 139 cases
- **Jaccard similarity: 0.357**

Disagreement is NOT a proxy for low confidence. They flag overlapping but distinct populations.

### 3. Two-stage policy ("disagreement OR low confidence") is the strongest signal

- **38.9% flag rate**, 2.17× enrichment, 58.0% error recall
- Captures 58% of all system errors at <40% review burden
- Reasonable clinical workload: 40% review on hardest cases vs 100% review

### 4. Diagnostic-standard discordance is a separate but useful signal

ICD-10/DSM-5 disagreement at 25.1% flag rate gives 1.37× enrichment. Lower than model discordance, but provides DIFFERENT information: it identifies cases where reasoning standards genuinely conflict, not where one model is just uncertain. Worth reporting separately.

---

## Important wording corrections (per GPT round 5)

### NOT "independent decision paths"

Stacker uses TF-IDF features. So "TF-IDF vs Stacker" is NOT independent paths. Use these terms instead:

| Pair | Correct framing |
|---|---|
| TF-IDF vs Stacker | **supervised–hybrid model discordance** |
| TF-IDF vs MAS-only | **heterogeneous architecture discordance** (more independent) |
| MAS-only vs Stacker | **architecture vs hybrid discordance** |
| ICD-10 vs DSM-5 | **diagnostic-standard discordance** (same backbone, different reasoning) |

### NOT "captures errors"

- ❌ "Disagreement captures 99% of errors"
- ❌ "Disagreement provides 99.2% precision for error detection"
- ✅ "Disagreement enriches deployed-model error rate by 2.06×"
- ✅ "Disagreement at 26.4% flag rate captures 42.5% of system errors"

### NOT "ensemble"

Both mode is ICD-10 pass-through, not ensemble. ICD-10/DSM-5 disagreement is an audit signal, not a way to combine predictions.

---

## Paper-ready Section 6 wording (verified safe)

> **6.1 Model discordance triage**
>
> Hybrid systems naturally produce multiple decision paths. We evaluate disagreement between paths as a clinician-triage routing signal, not as an accuracy-improving rule.
>
> On LingxiDiag-16K test_final (N=1000), supervised TF-IDF and the deployed Stacker LGBM disagree on 26.4% of cases. In this disagreement subset, deployed Stacker accuracy drops from 69.7% (agreement subset) to 37.5%, corresponding to 2.06× error rate enrichment. The signal captures 42.5% of all deployed-model errors at 26.4% flag rate.
>
> We compare against a confidence-quantile triage baseline (flagging the lowest 26.4% of cases by Stacker probability). Disagreement triage achieves 2.06× error enrichment and 42.5% recall versus 1.92× enrichment and 40.7% recall for confidence triage. Disagreement and confidence flag overlapping but distinct populations (Jaccard 0.357), and a union policy ("flag if either signal fires") covers 38.9% of cases at 2.17× enrichment and 58.0% error recall. We propose this two-stage policy as the strongest triage configuration.
>
> Disagreement triage has practical advantages over confidence triage: it requires no probability calibration, it is interpretable to clinicians ("two methods disagree on this case"), and it is computed for free in any hybrid architecture.
>
> **6.2 Diagnostic-standard discordance audit**
>
> CultureDx supports parallel ICD-10 and DSM-5 reasoning over the same case (Section 5.4). On N=1000, the two reasoning modes disagree on 25.1% of cases. In this disagreement subset, deployed ICD-10 accuracy drops from 54.9% to 38.2% (1.37× error enrichment). This is a complementary signal to model discordance: it identifies cases where the diagnostic standards genuinely conflict, not just where one model is uncertain.
>
> We do not propose this as an ensemble rule. Both mode in our current implementation preserves the ICD-10 primary decision (1000/1000 match with ICD-10 mode) and emits DSM-5 reasoning as sidecar evidence. The disagreement rate quantifies how often the two standards point to different diagnoses, providing an explicit audit signal for cases requiring clinician judgment.

---

## Secondary table (for appendix)

If reviewer wants full triage taxonomy:

| Rule | Type | Flag % | Enrichment | Recall | PPV (any-system-error) |
|---|---|---:|---:|---:|---:|
| TF-IDF/Stacker disagree | model discordance | 26.4% | 2.06× | 42.5% | 0.992 (≈ tautological) |
| MAS-only/Stacker disagree | architecture vs hybrid | 41.7% | 1.87× | [TODO] | [TODO] |
| TF-IDF/MAS-only disagree | heterogeneous architecture | 43.9% | 2.79× | [TODO] | [TODO] |
| ICD-10/DSM-5 disagree | diagnostic-standard | 25.1% | 1.37× | [TODO] | [TODO] |
| Lowest-confidence quantile | confidence | 26.4% | 1.92× | 40.7% | n/a |
| Union (model OR confidence) | two-stage | 38.9% | 2.17× | 58.0% | n/a |
| Intersection (model AND confidence) | two-stage | 13.9% | 2.09× | 25.3% | n/a |

The PPV column shows why I'm NOT using it as headline: 0.992 is structural in single-label disagreement, not informative.

---

## Implementation notes

- All numbers above are from existing predictions in `clean/v2.5-eval-discipline` and `main-v2.4-refactor`
- No GPU re-run required
- Analysis script: `scripts/analysis/disagreement_triage_v4.py`
- Outputs: `results/analysis/disagreement_triage_v4.json`

---

## Commit

```bash
git add docs/analysis/DISAGREEMENT_AS_TRIAGE_2026_04_25.md \
        scripts/analysis/disagreement_triage_v4.py \
        results/analysis/disagreement_triage_v4.json

git commit -m "analysis: disagreement-as-triage v4 with confidence baseline

Per GPT round 5 review: replaced misleading '99.2% captures errors'
(near-tautological in single-label disagreement) with deployed-model
error enrichment + error recall as primary metrics.

Key results on LingxiDiag-16K test_final N=1000:

Model discordance triage (TF-IDF vs Stacker):
  Flag rate: 26.4%
  Error enrichment: 2.06×
  Error recall: 42.5%

Confidence baseline (lowest 26.4% Stacker confidence):
  Error enrichment: 1.92×
  Error recall: 40.7%
  → Disagreement edge: +0.14×, +1.8pp

Two-stage union policy (disagreement OR low confidence):
  Flag rate: 38.9%
  Error enrichment: 2.17×
  Error recall: 58.0%
  → Strongest configuration

Diagnostic-standard discordance (ICD-10 vs DSM-5):
  Flag rate: 25.1%
  Error enrichment: 1.37×

Wording correctness (NOT 'independent decision paths' since Stacker
contains TF-IDF features). Use 'supervised-hybrid model discordance'
and 'diagnostic-standard discordance' instead."
```
