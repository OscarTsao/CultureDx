# CultureDx Paper Reproduction Guide

**Date**: 2026-04-29
**Purpose**: Reviewer-facing reproduction guide. Answers what reviewers, PI, and future-you need to know to navigate the manuscript artifacts, canonical metric sources, evaluation contract, and deprecated claim residues.
**Per GPT round 73 (Phase 2 Step 5e trigger)**: This is a navigation document, NOT a recompute-from-scratch manual. Pointers to canonical sources, not metric duplication.

---

## 1. Repository state

| Anchor | Value |
|---|---|
| Repository | `OscarTsao/CultureDx` |
| Branch | `main-v2.4-refactor` |
| Empirical table-integration commit | `eea8cf1` (Step 5d-apply: table renumbering) |
| Citation closure commit | `2b17aa3` (Step 5b-mini: unresolved-source mini-pass) |
| AIDA-Path slot decision commit | `57e4b02` (Step 5c: Path B locked) |
| This README commit | recorded at git push time |

Reviewers should use `main-v2.4-refactor` exclusively. The `main` branch may not yet reflect post-v4 evaluation contract changes; do not use `main` for review.

---

## 2. Manuscript artifacts

The 12 manuscript prose files at `docs/paper/drafts/`:

| File | Manuscript section |
|---|---|
| `SECTION_1.md` | §1 Introduction |
| `SECTION_2.md` | §2 Background |
| `SECTION_3.md` | §3 Datasets and task definition |
| `SECTION_4.md` | §4 Methods + Box 1 (post-v4 evaluation contract) |
| `SECTION_5_1.md` | §5.1 Main benchmark results (Table 2) |
| `SECTION_5_2.md` | §5.2 Feature ablation / feature contribution |
| `SECTION_5_3.md` | §5.3 F32/F41 cross-dataset asymmetry (Table 3) |
| `SECTION_5_4.md` | §5.4 Dual-standard ICD-10/DSM-5 audit (Table 4) |
| `SECTION_5_5.md` | §5.5 Reproduction + published-baseline framing |
| `SECTION_5_6.md` | §5.6 Confidence-gated ensemble null result |
| `SECTION_6.md` | §6 Model-discordance + standard-discordance triage (Tables 5 + 6) |
| `SECTION_7.md` | §7 Limitations |

§5 is segmented across §5.1-§5.6 for editorial control. Final manuscript may merge or reflow these.

---

## 3. Integration artifacts

5 integration artifacts at `docs/paper/integration/` document the cross-section assembly, table numbering, citation pass, and AIDA-Path slot decision:

| Artifact | Step | Commit | Purpose |
|---|---|---|---|
| `SECTION_5_7_INTEGRATION_REVIEW.md` | Step 1 | early Phase 2 | §5-§7 continuous integration review |
| `FULL_MANUSCRIPT_ASSEMBLY_REVIEW.md` | Step 5a | `82bd2a4` | Cross-section consistency review |
| `TABLE_NUMBERING_PLAN.md` | Step 5d-plan | `3bdc4af` | Final table label/numbering plan |
| `CITATION_PASS_PLAN.md` | Step 5b-plan | `bca33ce` | Citation pass plan + source-of-truth mapping |
| `AIDAPATH_SLOT_DECISION.md` | Step 5c | `57e4b02` | AIDA-Path Path B decision lock |

References infrastructure at `docs/paper/references/`:

| Artifact | Purpose |
|---|---|
| `CITATION_LEDGER.md` | 20 unique source keys / 30 inline markers / per-marker verification status |
| `references.bib` | 20 verified BibTeX entries (3 Bucket B + 3 Bucket C + 3 Bucket D + 3 Bucket E + 6 Bucket F + 2 Bucket A round-69 additions) |

---

## 4. Canonical metric sources

**Reviewers should treat the files below as authoritative for any metric value cited in the manuscript.**

| Manuscript element | Canonical source |
|---|---|
| Box 1 — v4 evaluation contract | `docs/paper/drafts/SECTION_4.md` (lines 46-65); supporting code at `src/culturedx/eval/lingxidiag_paper.py` and `scripts/compute_table4.py` |
| Table 1 — datasets | `docs/paper/drafts/SECTION_3.md` |
| Table 2 — main benchmark | `results/analysis/metric_consistency_report.json` (Stacker LGBM, Stacker LR, dual-standard); `outputs/tfidf_baseline/metrics.json` (Reproduced TF-IDF); audit-traced DtV values at `docs/audit/AUDIT_RECONCILIATION_2026_04_25.md` |
| Table 3 — F32/F41 cascade | `docs/analysis/MDD5K_F32_F41_ASYMMETRY_V4.md`; `results/analysis/mdd5k_f32_f41_asymmetry_v4.json`; `results/generalization/bias_transfer_analysis.json` |
| Table 4 — dual-standard audit (Panels A/B/C) | dual-standard `metrics.json` files referenced by `docs/paper/drafts/SECTION_5_4.md` |
| Table 5 — model-discordance triage | `docs/analysis/DISAGREEMENT_AS_TRIAGE.md`; `docs/paper/drafts/SECTION_6.md` |
| Table 6 — standard-discordance | `docs/paper/drafts/SECTION_6.md`; dual-standard predictions / analysis artifacts |
| F42 limitation | `docs/limitations/F42_DSM5_COLLAPSE_2026_04_25.md`; §7 lines 15-19, 27 |

**This README does NOT recompute these values.** Numbers in the manuscript should match the canonical source files at the recorded commits. If a number does not match, the canonical source is authoritative; the manuscript needs revision, not the source.

---

## 5. How to reproduce Box 1 and Tables 1-6

This section is a navigation map, not a step-by-step recompute manual. CultureDx evaluation depends on Qwen3-32B-AWQ inference (RTX 5090 32GB recommended; vLLM serving) and persistent prediction artifacts; full re-evaluation takes hours and is not within reviewer expected scope.

| Element | Reproduction path |
|---|---|
| Box 1 | Read `docs/paper/drafts/SECTION_4.md` lines 46-65; verify against `src/culturedx/eval/lingxidiag_paper.py` (paper-parent normalization) and `scripts/compute_table4.py` (composite Overall metric under v4 contract). |
| Table 1 (datasets) | Read `docs/paper/drafts/SECTION_3.md`. Dataset access: LingxiDiag-16K (per arXiv:2602.09379 / `Lingxi-mental-health/LingxiDiagBench` GitHub); MDD-5k (per arXiv:2408.12142 / `lemonsis/MDD-5k` GitHub). |
| Table 2 (main benchmark) | Read row metric values from canonical files in §4 above; do NOT delta-infer missing published-baseline cells. |
| Table 3 (F32/F41 cascade) | Read 47.7-fold-reduction value from `results/analysis/mdd5k_f32_f41_asymmetry_v4.json`; bootstrap CI [2.82, 6.08] is computed by the analysis script using percentile bootstrap. |
| Table 4 (dual-standard audit, Panels A/B/C) | Read panel-level metrics from dual-standard `metrics.json` artifacts; both-mode pass-through verification: 1000/1000 LingxiDiag + 925/925 MDD-5k pairwise; 0/15 metric-key differences. |
| Table 5 (model-discordance triage) | Read 26.4% equal-budget review-burden value and 2.06× enrichment from `docs/analysis/DISAGREEMENT_AS_TRIAGE.md`; CI on advantage includes 0. |
| Table 6 (standard-discordance) | Read LingxiDiag 25.1% / MDD-5k 20.8% values from §6 prose and dual-standard analysis artifacts. |

---

## 6. Evaluation contract v4 (Box 1 reference)

The post-v4 evaluation contract supersedes pre-v4 audit artifacts. Reviewers should use ONLY post-v4 metrics for current claims.

### 6.1 Class-scheme evaluation rules

| Slice | Mapping rule | Gold field |
|---|---|---|
| 12-class Top-1 / Top-3 | paper-parent normalized labels | normalized labels |
| 2-class | primary mapped to binary category | raw `DiagnosisCode`; F41.2 excluded |
| 4-class | predicted label set mapped to four-class category | raw `DiagnosisCode`; F41.2 → Mixed |
| Top-3 | ranked prediction list | NOT primary + comorbids shortcut |
| Overall | Table 4 composite under v4 contract | per-slice composite as defined in `compute_table4.py` |

### 6.2 Sample-size differences (v4 vs pre-v4)

| Slice | v4 (current) | pre-v4 (deprecated) |
|---|---:|---:|
| 2-class N (LingxiDiag) | 473 (after F41.2 + mixed exclusion) | 696 (parent-collapsed; F41.2 conflated) |
| 2-class N (MDD-5k) | 490 (after F41.2 + mixed exclusion) | n/a |
| 4-class N (LingxiDiag) | 1000 (all cases retained) | 1000 |
| 4-class N (MDD-5k) | 925 | 925 |

The v4 contract documentation lives in §4 lines 46-65. Pre-v4 `2class_n=696` numbers are deprecated and must not be cited as current claims. Use v4 `2class_n=473` (LingxiDiag) / `2class_n=490` (MDD-5k) only.

### 6.3 Statistical procedures (Box 1)

| Procedure | Purpose | Reference |
|---|---|---|
| Paired McNemar | paired Top-1 comparisons | `[CITE mcnemar1947note]` (DOI `10.1007/BF02295996`) |
| Percentile bootstrap CI | asymmetry ratios + metric differences | `[CITE efron1979bootstrap]` (DOI `10.1214/aos/1176344552`) |
| ±5 percentage-point non-inferiority margin | Top-1 parity claims | post-v4 contract definition; not a regulatory NI test |

---

## 7. F41.2 / F33 / raw-code handling

This is the single highest-confusion area for reviewers; pay attention to this section.

### 7.1 F41.2 disambiguation

`F41.2` (mixed anxiety and depressive disorder) is the primary post-v4 raw-code disambiguation pattern:

- **2-class slice**: F41.2 cases are EXCLUDED from the binary-class evaluation (n = 1000 → 473 on LingxiDiag; n = 925 → 490 on MDD-5k). This is because F41.2 cannot be cleanly assigned to either pure depression or pure anxiety under binary-class semantics. Mixed F32+F41 comorbid cases are similarly excluded from the 2-class task per §3 line 51.
- **4-class slice**: F41.2 cases are MAPPED to the "Mixed" category per §4 line 54 of the manuscript (n = 1000 / 925 both retained). Mixed F32+F41 comorbid cases are also counted as Mixed in the 4-class task per §3 line 51.
- **12-class slice**: F41.2 follows paper-parent normalization (collapses to F41 parent under standard ICD-10 paper-parent rules).

Pre-v4 `2class_n=696` was computed by parent-collapsing F41.2 into F41 and then evaluating binary depression-vs-anxiety, which conflated mixed and pure-anxiety cases. This is a deprecated handling pattern.

### 7.2 F33 handling

F33 is **not** a standalone label in the 12-class paper taxonomy used for the main benchmark.

Under the current v4 evaluation contract, F33 is routed to the `Others` bucket via `to_paper_parent` in `src/culturedx/eval/lingxidiag_paper.py`, consistent with the LingxiDiag report's original taxonomy locked in §3 and Box 1.

The empirical impact is negligible: F33 cases occur 0/1000 in LingxiDiag-16K and 2/925 in MDD-5k. The DSM-5 v0 ontology retains an F33 stub for system extensibility, but it is not a 12-class evaluation label.

**Reviewer-facing rule**:
- Do not treat F33 as an independent 12-class paper label.
- Do not use F33 to expand the binary depression/anxiety slice.
- Do not describe F33 as collapsing to F32 — it does not.
- Use the v4 evaluation contract and §3 taxonomy description as the source of truth.

### 7.3 Raw-code-aware evaluation

The post-v4 contract uses the raw `DiagnosisCode` field for 2-class and 4-class evaluations rather than parent-collapsed labels. This preserves F41.2-vs-F41 distinction for auxiliary tasks while leaving the 12-class paper-parent task unchanged.

The script `src/culturedx/eval/lingxidiag_paper.py` implements paper-parent normalization for the 12-class slice; `scripts/compute_table4.py` implements raw-code evaluation for 2-class and 4-class.

---

## 8. Audit reconciliation and deprecated artifacts

### 8.1 Audit reconciliation

The canonical audit reconciliation document is `docs/audit/AUDIT_RECONCILIATION_2026_04_25.md`. This document reconciles older audit artifacts (which used pre-v4 evaluation conventions) with the post-v4 metric-consistency report. Reviewers should use this reconciliation document to interpret older audit values (e.g. DtV Top-1 0.516 / 2-class 0.803) in the current evaluation contract.

### 8.2 Deprecated artifacts table

| Deprecated / historical artifact | Status | Replacement |
|---|---|---|
| `AUDIT_REPORT_2026_04_22.md` original metric values | historical audit only | `docs/audit/AUDIT_RECONCILIATION_2026_04_25.md` |
| pre-v4 Top-3 values | deprecated | v4 `compute_table4_metrics_v2` results |
| pre-v4 `2class_n=696` | deprecated | raw-code-aware `2class_n=473` (LingxiDiag) / `2class_n=490` (MDD-5k) |
| old local table labels `5.4a/b/c`, `6.1a/b`, `6.2a` | historical / draft labels | final Box 1 + Tables 1-6 (per `TABLE_NUMBERING_PLAN.md`) |
| `[CITE — verify]` placeholders | resolved | `docs/paper/references/CITATION_LEDGER.md` + `references.bib` |
| `[CITE LingxiDiag paper]` / similar generic placeholders | resolved | round-69 mini-pass entries in `references.bib` |
| pre-v4 silent-fallback pipeline files | deprecated (per fallback-cleanup decision) | explicit-mode flag pipeline at `src/culturedx/` |
| `apa2013dsm5` / DSM-5 (5th Ed.) 2013 | superseded | `apa2022dsm5tr` / DSM-5-TR 2022 (DOI `10.1176/appi.books.9780890425787`) |

If a number or claim in the manuscript appears to use a deprecated artifact, treat the canonical replacement as authoritative. The manuscript should be updated to match, not the other way around.

---

## 9. Citation and references

| Artifact | Location | Status at HEAD |
|---|---|---|
| Citation pass plan | `docs/paper/integration/CITATION_PASS_PLAN.md` | committed at `bca33ce` |
| Per-marker source ledger | `docs/paper/references/CITATION_LEDGER.md` | 20 unique source keys / 30 inline markers / 0 unresolved (closed at round 70) |
| BibTeX bibliography | `docs/paper/references/references.bib` | 20 verified entries via direct primary-source web fetch |

Citation buckets:

| Bucket | Theme | Count |
|---|---|---:|
| A | Paper / dataset | 2 (LingxiDiag, MDD-5k) |
| B | Standards / formal criteria | 3 (WHO ICD-10, APA DSM-5-TR, AIDA-Path) |
| C | Clinical / psychiatric LLM caution | 3 (Chen 2026, Hager 2024, Omar 2024) |
| D | Multi-agent clinical reasoning | 3 (Tang 2024 MedAgents, Kim 2024 MDAgents, Chen 2025 MAC) |
| E | Classical clinical NLP / TF-IDF baselines | 3 (Tavabi 2024, Patel 2024, Wang 2019) |
| F | Methods / tools | 6 (Qwen3, vLLM, BGE-M3, LightGBM, McNemar, Efron) |

All entries carry a verified DOI / arXiv / proceedings identifier as appropriate; no fabricated metadata. Per Citation Pass Plan v1.1 §8: arXiv-only / model-card / software-resource identifiers are recorded as such; no DOI is invented for entries that do not have one.

---

## 10. AIDA-Path status

**AIDA-Path overlap analysis is not completed in the current manuscript package.**

The manuscript treats AIDA-Path as a pending external structural-alignment anchor.

No AIDA-Path validation claim is made.

The Path B decision is locked at `docs/paper/integration/AIDAPATH_SLOT_DECISION.md` (commit `57e4b02`). The decision artifact enumerates the 5 trigger conditions under which a future revision could move from Path B to Path A; until those conditions are met, the manuscript continues operating under Path B wording.

---

## 11. What not to claim

Reviewers should NOT interpret the CultureDx manuscript or codebase as making any of the following claims. These are forbidden in §1-§7 prose and must remain forbidden in any reviewer-facing summary, abstract draft, or press-release-style description:

```
❌ CultureDx is clinically deployment-ready
❌ CultureDx is ready for clinical use
❌ CultureDx is a clinically validated diagnostic tool
❌ DSM-5 v0 outputs are clinically validated DSM-5 diagnoses
❌ DSM-5 superiority over ICD-10 / DSM-5 generalizes better
❌ Both mode is an ensemble or produces ensemble gain
❌ AIDA-Path validated CultureDx
❌ AIDA-Path integration completed
❌ clinician-reviewed DSM-5 criteria
❌ external structural validation completed
❌ MAS proves interpretability
❌ first multi-agent psychiatric diagnosis system
❌ TF-IDF generally beats deep models / TF-IDF generally beats BERT
❌ pre-v4 `2class_n=696` cited as a current value
```

Allowed scoping language:

```
✅ Chinese psychiatric differential-diagnosis benchmark system
✅ Top-1 parity with reproduced TF-IDF under post-v4 evaluation contract
✅ MAS-enabled audit properties under ICD-10 MAS pipeline
✅ pending AIDA-Path structural alignment
✅ external criteria-formalization anchor
✅ DSM-5 v0 schema with `UNVERIFIED` source-note
✅ synthetic / curated benchmark evaluation, NOT clinical validation
✅ external synthetic distribution-shift evaluation (MDD-5k specifically)
```

---

## 12. Reviewer quick checklist

```
- [ ] Use branch `main-v2.4-refactor`, not `main`.
- [ ] Treat `metric_consistency_report.json` and post-v4 metrics as canonical for Table 2.
- [ ] Use `AUDIT_RECONCILIATION_2026_04_25.md` to interpret older audit values.
- [ ] Use raw-code-aware `2class_n=473` (LingxiDiag) / `2class_n=490` (MDD-5k); do not use pre-v4 `2class_n=696`.
- [ ] Do not infer Table 2 missing published-baseline cells from deltas.
- [ ] Do not interpret Both mode as an ensemble or expect ensemble gain.
- [ ] Do not interpret DSM-5 v0 outputs as clinically validated DSM-5 diagnoses.
- [ ] Do not interpret AIDA-Path as completed validation; current state is Path B per `AIDAPATH_SLOT_DECISION.md`.
- [ ] LingxiDiag-16K and MDD-5k are synthetic / curated benchmarks; treat as distribution-shift evaluation, not external clinical validation.
- [ ] F42 recall drop under DSM-5-only is a v0 schema limitation (criterion-D handling), NOT a generalizable DSM-5 finding.
- [ ] F41.2 disambiguation: excluded from 2-class; mapped to Mixed in 4-class; collapsed to F41 in 12-class.
- [ ] If a value or claim contradicts a canonical source file, the canonical source is authoritative.
- [ ] Citation ledger and references.bib are at `docs/paper/references/`; 20 verified entries, 0 unresolved.
```

---

## 13. Sequential discipline status

```
✓ §1-§7 all closed (manuscript body complete)
✓ Phase 2 Step 5a: assembly review v1.1                              (82bd2a4)
✓ Phase 2 Step 5d-plan: table numbering plan v1.2                   (3bdc4af)
✓ Phase 2 Step 5d-apply: table-renumbering apply-pass v1.1           (eea8cf1)
✓ Phase 2 Step 5b-plan: citation pass plan v1.1                      (bca33ce)
✓ Phase 2 Step 5b-apply: citation apply-pass v1.2                    (d4992cc)
✓ Phase 2 Step 5b-mini: unresolved-source mini-pass v1.1             (2b17aa3)
✓ Phase 2 Step 5c: AIDA-Path slot decision (Path B)                  (57e4b02)
✓ Phase 2 Step 5e: this README                                       ← this commit
□ Phase 2 Step 5f: Abstract drafting (LAST)
□ Phase 2 Step 6: PI / advisor review
```

Per round 73 explicit:
- NO Abstract drafting in this commit (Step 5f LAST)
- NO new analyses
- NO AIDA-Path wording updates
- NO Table 2 metric modifications
