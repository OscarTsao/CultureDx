# Round 150 Tier 2A — LLM Re-Prompt on Ambiguous Cases (Audit)

**Date:** 2026-04-30 23:09:57
**Branch:** feature/gap-e-beta2-implementation @ HEAD
**Status:** Sandbox audit. No production code changes. No commit. No tag movement.
**Total wall time:** 10.9 minutes
**Model:** Qwen/Qwen3-32B-AWQ via vLLM at http://localhost:8000/v1
**Temperature:** 0.0
**Ambiguity criterion:** `abs(met_ratio[r1] - met_ratio[r2]) < 0.05` AND `r2 in DOMAIN_PAIRS[r1]` AND `r2 in confirmed_codes`

---

## 1. Setup

Re-prompt template (zh case + en options):

```
Given the following clinical case description, decide:
CASE: {case_text}
Is the most appropriate diagnosis:
A) Primary only: {primary_code}
B) Primary + comorbid: {primary_code} + {rank2_code}
Respond with exactly "A" or "B", followed by a one-sentence justification.
```

DOMAIN_PAIRS:

```python
  "F32": ['F41'],
  "F41": ['F32', 'F42'],
  "F42": ['F41'],
  "F33": ['F41'],
  "F51": ['F32', 'F41'],
  "F98": ['F41'],
```

---

## 2. Ambiguous case statistics

| Mode | N total | N ambiguous | % ambig | Top (primary,rank2) pair |
|---|---:|---:|---:|---|
| lingxi_icd10 | 1000 | 61 | 6.1% | F32+F41 |
| lingxi_dsm5 | 1000 | 230 | 23.0% | F32+F41 |
| mdd_icd10 | 925 | 60 | 6.5% | F41+F32 |
| mdd_dsm5 | 925 | 72 | 7.8% | F41+F32 |

---

## 3. LLM verdict distribution

| Mode | A (primary only) | B (primary+comorbid) | Unknown | A% | B% |
|---|---:|---:|---:|---:|---:|
| lingxi_icd10 | 22 | 39 | 0 | 36.1% | 63.9% |
| lingxi_dsm5 | 65 | 165 | 0 | 28.3% | 71.7% |
| mdd_icd10 | 8 | 52 | 0 | 13.3% | 86.7% |
| mdd_dsm5 | 14 | 58 | 0 | 19.4% | 80.6% |

---

## 4. Final metrics per mode

| Mode | Policy | emit% | EM | F1 | P | R | sgEM | mgEM | mgR | sizeM |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| lingxi_icd10 | BETA-2b primary-only | 0.0% | 0.452 | 0.488 | 0.507 | 0.479 | 0.495 | 0.000 | 0.314 | 0.914 |
| lingxi_icd10 | **2A re-prompt** | 3.9% | 0.435 | 0.488 | 0.502 | 0.487 | 0.476 | 0.000 | 0.326 | 0.881 |
| lingxi_icd10 | Δ vs BETA-2b | — | -0.017 | -0.000 | — | — | — | — | +0.012 | — |
| lingxi_dsm5 | BETA-2b primary-only | 0.0% | 0.419 | 0.453 | 0.471 | 0.445 | 0.458 | 0.000 | 0.297 | 0.914 |
| lingxi_dsm5 | **2A re-prompt** | 16.5% | 0.353 | 0.462 | 0.456 | 0.494 | 0.379 | 0.081 | 0.349 | 0.783 |
| lingxi_dsm5 | Δ vs BETA-2b | — | -0.066 | +0.008 | — | — | — | — | +0.052 | — |
| mdd_icd10 | BETA-2b primary-only | 0.0% | 0.542 | 0.578 | 0.597 | 0.569 | 0.594 | 0.000 | 0.309 | 0.912 |
| mdd_icd10 | **2A re-prompt** | 5.6% | 0.507 | 0.573 | 0.583 | 0.579 | 0.555 | 0.012 | 0.321 | 0.865 |
| mdd_icd10 | Δ vs BETA-2b | — | -0.035 | -0.005 | — | — | — | — | +0.012 | — |
| mdd_dsm5 | BETA-2b primary-only | 0.0% | 0.528 | 0.563 | 0.581 | 0.554 | 0.578 | 0.000 | 0.300 | 0.912 |
| mdd_dsm5 | **2A re-prompt** | 6.3% | 0.498 | 0.561 | 0.570 | 0.567 | 0.543 | 0.037 | 0.319 | 0.856 |
| mdd_dsm5 | Δ vs BETA-2b | — | -0.029 | -0.002 | — | — | — | — | +0.019 | — |

---

## 5. Comparison vs sandbox candidates

Sandbox baseline numbers per `ROUND150_SANDBOX_AUDIT.md` (BETA-2b primary-only, 1B-α veto, Combo 1B+1F):

| Mode | BETA-2b F1 | 1B-α F1 | Combo F1 | 2A re-prompt F1 |
|---|---:|---:|---:|---:|
| lingxi_icd10 | 0.488 | 0.493 | 0.493 | **0.488** |
| lingxi_dsm5 | 0.453 | 0.504 | 0.504 | **0.462** |
| mdd_icd10 | 0.578 | 0.583 | 0.588 | **0.573** |
| mdd_dsm5 | 0.563 | 0.566 | 0.566 | **0.561** |

---

## 6. Verdict

**LLM judgment does NOT outperform hand-crafted gates.** Stick with 1B-α / Combo for adoption decisions.

Per Q3 (Round 149): EM placement remains supplement-only regardless of policy choice.

---

## 7. Files NOT modified

- `src/culturedx/modes/hied.py` — UNTOUCHED
- `paper-integration-v0.1` tag — UNTOUCHED
- All committed predictions — UNTOUCHED (read-only)
- Manuscript drafts — UNTOUCHED
