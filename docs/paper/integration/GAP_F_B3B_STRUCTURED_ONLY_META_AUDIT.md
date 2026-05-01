# Gap F B3b — Structured-Only Meta-Reasoning (Qwen3 reading only top-5 + checker, NO transcript)

**Date:** 2026-05-02
**Branch:** tier2b/hierarchical-prompt @ HEAD
**Status:** Sandbox audit. Uncommitted.

## TL;DR — NEGATIVE result

Qwen3 reading only structured signals (top-5 ranked + met_ratios + confirmed_codes + per-criterion confidences) WITHOUT case transcript produces WORSE primary decisions.

- N=1000 cases (LingxiDiag-ICD10)
- Baseline (Qwen3 BETA-2a primary): Top-1 = 0.5010, EM = 0.4520
- B3b structured-only: Top-1 = 0.4810, EM = 0.4330
- Δ Top-1: -0.0200 (-2.0pp)
- Cases B3b changed primary: 70/1000 (7.0%)
  - Delta_correct (B3b right, baseline wrong): 11
  - Delta_wrong (baseline right, B3b wrong):    31
  - **Net change: -20 cases** (negative = harm)

---

## §Sample cases

**Cases where B3b helped (changed primary correctly):**

| case_id | baseline → B3b | gold |
|---|---|---|
| 371811674 | F39 → F41 | F41 |
| 356164633 | F51 → F41 | F41 |
| 375065461 | F32 → F41 | F41 |

**Cases where B3b hurt (changed primary wrongly):**

| case_id | baseline → B3b | gold |
|---|---|---|
| 377662897 | F41 → F51 | F41 |
| 329547625 | F41 → F32 | F41 |
| 374056166 | F32 → F41 | F32 |

---

## §Conclusion

Removing the case transcript from the Diagnostician's input — even when providing all aggregated downstream signals (top-5 ranking, met_ratios, confirmed codes, per-criterion confidence) — degrades primary diagnosis accuracy.

This is informative for MAS architecture: structured agent outputs are insufficient substitutes for raw evidence. Any meta-reasoning agent that operates 'over' upstream agent outputs without re-reading the case text loses information.

Implication: a useful primary-fix or meta-reasoning agent must include both the case transcript AND the structured upstream signals. Pure 'paradigm-different reasoner' (no transcript) underperforms the original Diagnostician — counter-intuitive at first, but consistent with the principle that text content carries information not preserved in structured features.
