# CultureDx Paper — Section 5/6/7 Skeleton

**Date**: 2026-04-26
**Status**: Skeleton ONLY (no prose). Per GPT round 13 explicit greenlight for parallel work.
**Approach**: format-(b) — section-by-section with paste markers + Allowed/Forbidden wording guards + reviewer attack/response notes

---

## GPT round 13 verdict

> **"Empirical results are locked. Repo is ready for Section 5/6 skeleton. But before formal prose, do one tiny narrative/provenance sync commit."**
>
> **"If you want parallelism: You or Codex: tiny sync commit. Claude: skeleton only, no full prose. After sync commit: Section 5.1 prose can start."**

Sync commit landed. Use `NARRATIVE_REFRAME.md`, `metric_consistency_report.json`, `DISAGREEMENT_AS_TRIAGE.md`, and `MDD5K_F32_F41_ASYMMETRY_V4.md` as current sources.

This skeleton is the parallel work. It now tracks the current source set:
- Skeleton lists section structure, source paths, allowed/forbidden wording, reviewer responses
- Final numbers come from `metric_consistency_report.json` which is already canonical

---

## Files in this tarball

```
culturedx_section_5_6_skeleton/
├── README.md                      ← you are here (master plan)
├── SECTION_5_SKELETON.md          ← Section 5 (Architecture Results) skeleton
├── SECTION_6_SKELETON.md          ← Section 6 (Disagreement-as-Triage) skeleton
└── SECTION_7_SKELETON.md          ← Section 7 (Limitations) skeleton
```

---

## Skeleton structure summary

### Section 5 — Architecture Results (~1,750 words + 4 tables)
| Subsection | Topic | Length | Key claim |
|---|---|---:|---|
| 5.1 | Main benchmark | 250 | Stacker LGBM accuracy parity with TF-IDF |
| 5.2 | Feature ablation | 150 | MAS contributes 11.9% importance, modest macro-F1 gain |
| 5.3 | Bias robustness | 400 | 189× → 3.97× cascade (47.7× cumulative) |
| 5.4 | Dual-standard audit | 600 | DSM-5 v0 = trade-off, NOT bias robustness |
| 5.5 | TF-IDF reproduction gap | 150 | Disclosed limitation |
| 5.6 | Confidence-gated ensemble null result | 200 | Dev-tuned gating selected TF-IDF-only; no ensemble gain |

### Section 6 — Disagreement-as-Triage (~650 words + 2 tables)
| Subsection | Topic | Length | Key claim |
|---|---|---:|---|
| 6.1 | Model discordance triage | 350 | 2.06× enrichment, comparable to confidence + complementary |
| 6.2 | Diagnostic-standard discordance | 300 | Cross-dataset 1.37–2.06×, "comparable in magnitude" |

### Section 7 — Limitations (~1,080 words)
| Subsection | Topic | Length |
|---|---|---:|
| 7.1 | Synthetic data | 80 |
| 7.2 | DSM-5 v0 LLM-drafted | 150 |
| 7.3 | TF-IDF reproduction gap | 80 |
| 7.4 | Class coverage | 120 |
| 7.5 | F32/F41 asymmetry persists | 150 |
| 7.6 | F42 OCD collapse mechanism | 200 |
| 7.7 | Statistical caveats | 150 |
| 7.8 | No clinical validation yet | 150 |

**Total**: ~3,480 words + 6 tables (Tables 5, A, B, cascade, 6, 7)

---

## Section dependencies and writing order

```
Sync commit (15 min, doc-only)
    ↓
[skeleton lands]
    ↓
Round 14: GPT review of skeleton
    ↓
Section 5.1 prose (250 words, 60 min) ← FIRST PROSE TEST
    ↓
Round 15: GPT review of §5.1 prose
    ↓
Section 5.5 + 5.2 prose (300 words, 60 min)  ← simpler subsections
Section 5.6 prose (200 words, 30 min)
    ↓
[parallel: AIDA-Path overlap, 2-3 days, zero-GPU]
    ↓
Section 5.3 prose (400 words, 90 min)        ← cascade requires careful wording
Section 5.4 prose (600 words, 120 min)       ← THE BIG ONE
Section 6.1 prose (350 words, 60 min)
Section 6.2 prose (300 words, 60 min)        ← source sync landed
Section 7 prose (1,080 words, 180 min)
    ↓
Round 16-18: GPT review of full §5/6/7 prose
    ↓
PI review
    ↓
Submission (late June 2026)
```

Total prose drafting time: ~12-15 hours of focused work, spread across 2-3 weeks.

---

## Why skeleton-then-prose

Per GPT round 10:
> "用 section-by-section 比較適合快速 review。每段都加 'Do not say' / 'Allowed wording'."

This format prevents the 3 overclaim patterns Claude has demonstrated across rounds 7, 9, 12:
1. "directionally similar" → "same / identical"
2. "model output" → "correct"
3. "mostly complete" → "100% / 10/10"

Each subsection's Allowed/Forbidden lists are pre-locked guard rails. Writing prose with these guards in front prevents drift.

---

## Pre-prose checklist (before writing §5.1)

- [x] Sync commit landed (NARRATIVE_REFRAME §5.3, §6.2 + abstract + F32/F41 doc provenance)
- [x] GPT round 14 review of this skeleton
- [ ] All canonical numbers re-verified against `metric_consistency_report.json`
- [ ] User confirms section order
- [ ] User confirms paragraph budget per subsection

After all 5 boxes checked: §5.1 prose begins.

---

## What this skeleton does NOT include

- **Section 1-4**: introduction, related work, dataset, methods — separate skeletons needed
- **Section 8**: ethics, broader impact, conflicts — separate skeleton needed
- **Abstract**: not yet skeletonized
- **Acknowledgments + references**: bibliography format depends on venue

This skeleton focuses on **the empirically-grounded sections** (5/6/7) where the most overclaim risk lives. Sections 1-4 are introduction/methods (lower overclaim risk; mostly description of pipeline architecture and data).

---

## Round 14 ready

This skeleton is sendable to GPT round 14 immediately for format/structure review. Expected GPT feedback:
- (likely) granular criticism of Allowed/Forbidden lists per subsection
- (likely) addition of forbidden wordings I missed
- (possible) reordering of subsections
- (unlikely) addition of new subsections

After round 14, prose can start with §5.1.

---

## Honesty audit

This skeleton contains 6 reviewer-attack/response patterns per major subsection. If a reviewer's actual attack matches one of these, my response is pre-rehearsed. If a reviewer's attack does NOT match, I'll need new responses on the fly — this is the residual risk.

The 6 attack patterns covered:
1. "Why is your TF-IDF stronger than the paper's?" (§5.5)
2. "If TF-IDF achieves parity, why use MAS?" (§5.1)
3. "Did v4 evaluator repair improve scores artificially?" (§5.3)
4. "Why does DSM-5 win aggregates but lose Top-1?" (§5.4)
5. "Why include disagreement triage if no better than confidence?" (§6.1)
6. "Why does enrichment increase from LingxiDiag to MDD-5k?" (§6.2)

This list is NOT exhaustive. PI review and AIDA-Path results will likely reveal new attacks.

---

## Status after this skeleton

- ✅ Section 5/6/7 structure: complete
- ✅ Allowed/Forbidden wording guards: locked
- ✅ Source artifact paths: documented
- ✅ Reviewer attack/response: 6 covered
- ✅ Length budget: total ~3,480 words
- ✅ Sync commit: landed
- ✅ Round 14 review: micro-fixes applied
- ⏳ Section 5.1 prose: pending user go-ahead
