# Full Manuscript Assembly Review

**Date**: 2026-04-28
**Per GPT round 57**: §2 closed at `f192eaa`. Full major-section draft set complete. Phase 2 Step 5 trigger — assembly review (NOT new prose, NOT abstract, NOT new experiments).
**Status**: Inventory + ledgers + decision points across §1-§7 prose at HEAD `f192eaa`. This is a checklist artifact, not an authoring deliverable.

---

## 1. Section inventory

12 prose files at HEAD `f192eaa`. Total 6,882 words across full manuscript body.

| § | File | Lines | Words | Role |
|---|---|---:|---:|---|
| 1 | SECTION_1.md | 30 | 736 | Introduction (5 contributions) |
| 2 | SECTION_2.md | 44 | 810 | Related Work (6 subsections, 14 citations) |
| 3 | SECTION_3.md | 44 | 668 | Task & Datasets |
| 4 | SECTION_4.md | 73 | 1213 | Methods (architecture, systems, modes, evaluation contract) |
| 5.1 | SECTION_5_1.md | 7 | 312 | Main benchmark results |
| 5.2 | SECTION_5_2.md | 3 | 170 | Feature ablation |
| 5.3 | SECTION_5_3.md | 30 | 495 | F32/F41 asymmetry |
| 5.4 | SECTION_5_4.md | 58 | 701 | Dual-standard mode comparison |
| 5.5 | SECTION_5_5.md | 3 | 153 | TF-IDF reproduction gap |
| 5.6 | SECTION_5_6.md | 3 | 158 | Top-3 / coverage |
| 6 | SECTION_6.md | 60 | 825 | Disagreement triage + standard-discordance |
| 7 | SECTION_7.md | 29 | 641 | Limitations |
| **TOTAL** | | **424** | **6,882** | |

**§5 internal balance observation**: §5.1, §5.2, §5.5, §5.6 are short (~150-310 words each); §5.3 (495) and §5.4 (701) carry most §5 content. This is intentional — bias-asymmetry analysis (§5.3) and dual-standard analysis (§5.4) are core empirical contributions. §5.1 is anchor-only (parity claim + baseline numbers). §5.5 / §5.6 are short qualifiers (reproduction gap disclosure, Top-3 stability).

**Per round 57 explicit**: do NOT add a new §8 Discussion / Conclusion; §5-§7 already carry Results + Discussion + Limitations functions. At assembly time, a short concluding paragraph after §7 may be added, OR the venue template's Discussion / Conclusion slot may absorb existing §7 content. **Decision deferred to PI / venue selection.**

---

## 2. Table ledger

| Local label | Section | Caption / scope | Current status | Manuscript-level number (TBD at assembly) |
|---|---|---|---|:---:|
| (unlabeled) | §4.4 | v4 evaluation contract — Metric family / Prediction source / Gold source (Top-1, Top-3, F1, 2-class, 4-class, Overall) | unlabeled local methods table (markdown pipe table at §4 lines 46-53) | Table N (assign caption + manuscript number, OR convert to boxed methods definition) |
| (unlabeled) | §5.3 | F32/F41 asymmetry cascade — System / F41→F32 / F32→F41 / Ratio across single-LLM, MAS T1, MAS R6v2, MAS ICD-10 v4 | unlabeled local results table (markdown pipe table at §5.3 lines 11-16) | Table N+1 (assign caption + manuscript number; ensure cited before interpretation) |
| Table 5.4a | §5.4 | LingxiDiag-16K mode comparison (N=1000) | labeled local table | Table N+2 |
| Table 5.4b | §5.4 | MDD-5k mode comparison (N=925) | labeled local table | Table N+3 |
| Table 5.4c | §5.4 | Both vs ICD-10 agreement (1000/1000, 925/925, 0/15) | labeled local table | Table N+4 |
| Table 6.1a | §6 | Model-discordance vs confidence baseline (LingxiDiag-16K, N=1000) | labeled local table | Table N+5 |
| Table 6.1b | §6 | Union policy (model-discordance OR low-confidence) | labeled local table | Table N+6 |
| Table 6.2a | §6 | Diagnostic-standard discordance across datasets (LingxiDiag + MDD-5k) | labeled local table | Table N+7 |

**Total**: 8 current markdown tables before manuscript-level renumbering — 6 labeled (Table 5.4a/b/c, 6.1a/b, 6.2a) plus 2 unlabeled markdown pipe tables (§4.4 evaluation contract, §5.3 F32/F41 cascade). The 2 unlabeled tables are integral to Methods and Results respectively and must receive captions and manuscript-level table numbers at assembly time (round 58 Fix 1+2 — table inventory must include unlabeled pipe tables, not only `Table X.Y`-captioned tables).

**Markdown pipe-table detection rule (round 58 Fix 3)**: Table inventory must search for markdown pipe tables (`grep -c "^|"`) as well as explicit `Table X.Y` captions. Unlabeled pipe tables in Methods or Results sections must be counted before renumbering. At HEAD `f192eaa`, sections with markdown pipe tables are §4 (8 rows = §4.4 evaluation contract), §5.3 (6 rows = F32/F41 cascade), §5.4 (14 rows = Tables 5.4a/b/c), and §6 (15 rows = Tables 6.1a/b + 6.2a).

**Cross-section table references** (assembly must verify these survive renumbering):
- §1 references "Table 5.4c": none in §1 prose currently — §1 ¶4 C4 references the pass-through claim conceptually, no table number cited
- §4 line 33 references "Table 5.4c" for 1000/1000 + 925/925 + 0/15 — must update to manuscript-level number
- §5.4 internally references its own tables 5.4a/b/c
- §6 line 55 references "Table 6.2a flagged-subset accuracy: LingxiDiag 0.239 DSM-5 vs 0.382 ICD-10..." — must update to manuscript-level number
- §7 references no table numbers directly; references claims by section (§5.4 / §5.3 / §6.2)

**Renumbering rule at assembly**: replace `Table 5.4a` / `Table 5.4b` / `Table 5.4c` / `Table 6.1a` / `Table 6.1b` / `Table 6.2a` with `Table 1` / `Table 2` / `Table 3` / `Table 4` / `Table 5` / `Table 6` (or per venue convention). Cross-section references must be updated in lockstep.

**Discipline at assembly**: do not add new tables in this pass. If a venue requires a "Table 1 — Datasets" or "Table 2 — Systems" summary table that does not currently exist, decide BEFORE the table-number pass whether to add or reference §3 / §4 prose inline.

---

## 3. Figure ledger

**Zero figures in current prose.**

The manuscript body has 0 figures across §1-§7. All evidence is text + tables. No figures referenced anywhere in §1-§7 prose.

**Possible figures to consider AT assembly time** (NOT decided here; flagged for PI review):

| Candidate | Source | Pros | Cons |
|---|---|---|---|
| Architecture diagram (multi-agent pipeline) | §4.1 | Standard for multi-agent papers; helps non-NLP psychiatry reviewers | None of §1-§7 prose currently references one; would need a new figure |
| F32/F41 asymmetry visualization (single LLM 189× → MAS 3.97×) | §5.3 | Strong visual hook for the §1 Contribution 2 claim | Two bars / one ratio plot; risk of looking thin |
| Mode comparison heatmap (ICD-10 / DSM-5 / Both × metrics × datasets) | §5.4 | Synthesizes Tables 5.4a + 5.4b | Tables already present; figure may be redundant |
| Disagreement vs confidence Venn / Jaccard | §6.1 | Visualizes Jaccard 0.357 + union 38.9% | Tables 6.1a/b already present |

**Decision deferred**: figures are venue-dependent. If submitting to a clinical-NLP venue (npj Digital Medicine, JAMIA, Nat Med format), 1-2 figures expected. If submitting to a more text-heavy venue (ACL, EMNLP), 0 figures acceptable.

---

## 4. Repeated-number ledger

Every number that appears in 2+ sections must be identical across all appearances. Verified at HEAD `f192eaa`:

| Anchor | Sections | Status |
|---|---|:---:|
| **Top-1 = 0.612 (Stacker LGBM)** | §1 (×2), §5.1, §5.5, §7 | ✓ identical |
| **Top-1 = 0.610 (reproduced TF-IDF)** | §1 (×2), §5.1 (×2), §5.5, §7 | ✓ identical |
| **+0.2 percentage points** (paired diff) | §1, §5.1 | ✓ identical |
| **±5 percentage point margin (NI)** | §1, §5.1, §5.5, §7 (multiple) | ✓ identical |
| **0.496 (published TF-IDF)** | §1, §5.1, §5.5 | ✓ identical |
| **11.4 percentage points (reproduction gap)** | §1, §5.5, §7 | ✓ identical |
| **88.1% TF-IDF / 11.9% MAS feature share** | §1, §5.2 | ✓ identical |
| **189× single LLM asymmetry** | §1, §5.3 (×2), §7 | ✓ identical |
| **3.97× MAS ICD-10 v4 asymmetry** | §1, §5.3 (×3), §5.4, §7 (×2) | ✓ identical |
| **151/38 raw F41→F32 / F32→F41** | §5.3, §7 | ✓ identical |
| **95% bootstrap CI [2.82, 6.08]** | §5.3, §7 | ✓ identical |
| **47.7-fold reduction** | §5.3, §7 | ✓ identical |
| **7.24× DSM-5 MDD-5k asymmetry (181/25)** | §5.3, §5.4 | ✓ identical |
| **DSM-5 95% CI [5.03, 11.38]** | §5.3 | (single occurrence — no consistency check needed) |
| **Δratio +3.24 / +3.13 paired bootstrap** | §5.3, §5.4 | ✓ identical |
| **CI [+1.12, +6.89] / [+1.12, +7.21]** | §5.3, §5.4 | ✓ identical |
| **26.4% flag / 2.06× / 42.5% recall** | §1, §6 (multiple) | ✓ identical |
| **1.92× / 40.7% confidence baseline** | §6 (×2) | (within §6 only) |
| **Jaccard 0.357** | §6 | (within §6 only) |
| **38.9% union flag / 2.17× / 58.0% recall** | §1, §6 | ✓ identical |
| **25.1% LingxiDiag standard-discordance** | §6 (×2) | (within §6 only) |
| **20.8% MDD-5k standard-discordance** | §6 | (single occurrence) |
| **1000/1000 LingxiDiag pass-through** | §1 prep / §4, §5.4, §7 | ✓ identical |
| **925/925 MDD-5k pass-through** | §1 prep / §4, §5.4, §7 | ✓ identical |
| **0/15 metric-key differences** | §4, §5.4, §7 | ✓ identical |
| **F42 52% → 12% (LingxiDiag paper-parent, n=25)** | §5.4, §7.6 | ✓ identical |
| **F42 −30.6pp (LingxiDiag v4 slice, n=36)** | §5.4, §7.6 | ✓ identical |
| **F42 −23.1pp (MDD-5k paper-parent, n=13)** | §5.4 | (single occurrence) |
| **F42 −23.8pp (MDD-5k v4 slice, n=21)** | §5.4 | (single occurrence) |
| **0.617 Overall, 0.925 Top-3 (Stacker)** | §5.1 | (single occurrence) |
| **5.58× R6v2 (somatization-aware checkpoint)** | §5.3 | (single occurrence) |

**Conclusion**: no inconsistencies detected. All numbers identical across all appearances. Lesson 40a discipline preserved through full manuscript draft.

**Round 57 explicit review point — do these numbers make sense in §1 ¶4?**

§1 ¶4 (round-50-compressed contribution bullets) mentions:
- C1: 0.612 / 0.610 / +0.2pp / ±5pp ← parity essentials
- C2: 189× → 3.97× ← bias-asymmetry headline
- C3: 26.4% / 2.06× / 58.0% ← discordance triage essentials

These are the 9 hero numbers retained in §1 after round 50 compression. Density check: 9 anchors / 234 ¶4 words = 1 anchor per 26 words. This is the **upper end of acceptable §1 density** but balanced by deliberately omitting ~20 anchors that round 50 caught (Jaccard, raw counts, 7.24×, +3.24, CI ranges, 1000/1000, 0/15, n=473, n=490, etc.).

**Assembly decision deferred**: do NOT touch §1 ¶4 anchor density at this pass. It was settled at round 50 and is internally consistent.

---

## 5. Claim-boundary ledger

| Claim | Supported by | Forbidden overclaim |
|---|---|---|
| LGBM parity with reproduced TF-IDF | §5.1 (0.612 vs 0.610, +0.2pp within ±5pp); McNemar p≈1.0 paired-discordance context | NOT superiority; NOT McNemar-as-equivalence-proof; NOT "MAS beats TF-IDF" |
| Reproduction gap disclosure | §5.5 (0.610 reproduced vs 0.496 published, 11.4pp) | NOT "TF-IDF is weak"; NOT "our parity claim depends on the published comparison" |
| Hybrid-system framing | §1 ¶3, §4.2, §5.2 (88.1% TF-IDF / 11.9% MAS) | NOT "LLM-only system"; NOT "MAS-only would also reach parity" |
| F32/F41 asymmetry reduction (ICD-10 MAS) | §5.3 (189× → 3.97×, 47.7-fold, CI [2.82, 6.08]) | NOT "bias solved"; NOT "asymmetry resolved"; NOT "MAS proves robustness" |
| F32/F41 residual asymmetry remains | §5.3 line 30, §7.5 | NOT "F41→F32 misclassification eliminated" |
| DSM-5 v0 dual-standard exposes trade-offs | §5.3 (7.24×), §5.4 (Tables 5.4a/b) | NOT "DSM-5 superiority"; NOT "DSM-5 improves robustness"; NOT "DSM-5 generalizes better" |
| DSM-5 v0 is NOT clinically validated | §1 Contribution 5, §4.3, §7.2 | NOT "DSM-5 clinical diagnosis"; NOT "clinically validated DSM-5 criteria" |
| Both mode is architectural pass-through | §4 line 33, §5.4 Table 5.4c (1000/1000, 925/925, 0/15), §7.3 | NOT "Both mode ensemble"; NOT "ensemble gain"; NOT "dual-standard accuracy improvement" |
| Model-discordance flags error-enriched cases | §6 Table 6.1a (26.4%/2.06×/42.5%) | NOT "disagreement beats confidence" (CI on advantage includes zero); NOT "deployment-ready triage" |
| Union policy increases error recall at higher review burden | §6 Table 6.1b (38.9%/2.17×/58.0%) | NOT "union strictly dominates either signal"; NOT "free-lunch error recall" |
| Standard-discordance flags error-enriched cases | §6.2 (25.1% LingxiDiag, 20.8% MDD-5k, 2.06× peak) | NOT "DSM-5 has independent diagnostic value"; NOT "DSM-5 outperforms ICD-10 on flagged subset" |
| F42 finding scoped to v0 schema | §5.4 line 16-19, §7.6 | NOT "F42/OCD inherently fails in MAS"; NOT "OCD criterion-D is unmodelable" |
| Synthetic / curated benchmark only | §1 ¶5, §3.2.1, §3.2.2, §7.1 | NOT "real-world clinical validation"; NOT "prospective clinical cohort"; NOT "clinically deployed diagnosis" |
| AIDA-Path pending external structural anchor | §1 ¶5, §2.6, §7.8 | NOT "AIDA-Path validated CultureDx"; NOT "AIDA-Path integration completed"; NOT "clinician-reviewed DSM-5 criteria" |
| Evaluation contract scoped post-v4 | §3, §4 (multiple), §7 | NOT "old audit was wrong"; NOT "previous numbers are invalid"; NOT "all metrics use paper-parent" |
| F41.2 excluded from binary depression/anxiety | §3, §4 | NOT "F41.2 is anxiety in 2-class"; NOT "F33 is a paper class" |

**Total**: 16 claim-boundary rows. Each maps to specific section anchors and a forbidden overclaim that abstract / discussion writing must NOT introduce.

This ledger is the **single most important artifact for Abstract drafting**. Round 57 explicit: "Abstract is the most prone to overclaim" — this ledger constrains the Abstract claim-set.

---

## 6. Citation-placeholder ledger

15 `[CITE *]` markers across §2 + §3 + §5.1 prose.

| # | Marker | Section | Lit audit bucket | Status |
|---:|---|---|:---:|:---:|
| 1 | `[CITE LingxiDiag paper]` | §2.1 line 8 | 1 | known reference; needs DOI/citation string |
| 2 | `[CITE LingxiDiag paper]` | §3.1 line 7 | 1 | same as above (reused) |
| 3 | `[CITE LingxiDiag paper]` | §3.2.1 line 14 | 1 | same as above (reused) |
| 4 | `[CITE LingxiDiag paper]` | §5.1 line 3 | 1 | same as above (reused) |
| 5 | `[CITE MDD-5k paper]` | §2.1 line 8 | 2 | known reference; needs DOI/citation string |
| 6 | `[CITE Chen 2026 Nat Med]` | §2.2 line 14 | 3.1 | from lit audit (`5e6435e`) |
| 7 | `[CITE Hager 2024 Nat Med]` | §2.2 line 15 | 3.2 | from lit audit |
| 8 | `[CITE Omar 2024 Front Psychiatry]` | §2.2 line 16 | 3.3 | from lit audit |
| 9 | `[CITE Tang 2024 ACL MedAgents]` | §2.3 line 21 | 4.1 | from lit audit |
| 10 | `[CITE Kim 2024 NeurIPS MDAgents]` | §2.3 line 22 | 4.2 | from lit audit |
| 11 | `[CITE Chen 2025 npj MAC]` | §2.3 line 23 | 4.3 | from lit audit |
| 12 | `[CITE PLOS One 2024 clinical NLP coding]` | §2.4 line 29 | 5.1 | from lit audit |
| 13 | `[CITE JMIR AI 2024 BOW vs Bio-Clinical-BERT]` | §2.4 line 29 | 5.2 | from lit audit |
| 14 | `[CITE Wang 2019 BMC clinical text classification]` | §2.4 line 30 | 5.3 | from lit audit |
| 15 | `[CITE WHO ICD-10]` | §2.5 line 36 | 6 | authoritative reference |
| 16 | `[CITE APA DSM-5]` | §2.5 line 36 | 6 | authoritative reference |
| 17 | `[CITE Strasser-Kirchweger 2026 npj Digital Medicine]` | §2.6 line 42 | 7.1 | from lit audit |

**Tools / models without `[CITE *]` markers** (mentioned 3-17 times in §1-§7 prose; need citations added at citation pass):

| # | Tool / model | Sections | Citations needed |
|---:|---|---|---|
| 18 | Qwen3-32B-AWQ | §1, §4.1, §5.3 (3 mentions) | Qwen3 model card / paper |
| 19 | vLLM | §4.1 (1 mention) | vLLM paper or repo |
| 20 | BGE-M3 | §4.1 (1 mention; "supports retrieval utilities ... reported metrics do not depend on a retrieval ablation") | BGE-M3 paper if cited |
| 21 | LightGBM / LGBM | §1, §4.2, §5.1, §5.2 (17+ mentions) | LightGBM paper |

**Statistical methods without `[CITE *]` markers** (mentioned 8-10 times across prose):

| # | Method | Sections | Citations needed |
|---:|---|---|---|
| 22 | McNemar's test | §1 prep / §5.1, §7.4 (8 mentions) | original McNemar 1947 / a modern clinical-NLP citation |
| 23 | Bootstrap CI (95%, 1000 resamples) | §5.3, §5.4, §7.4 (10 mentions) | Efron bootstrap citation |
| 24 | Non-inferiority margin (±5 percentage points) | §1, §5.1, §5.5, §7 (multiple) | non-inferiority methodology citation if venue requires |

**Decision needed at citation pass**: tool / model / statistical-method citations are typically optional in conference papers (inline `\texttt{}` references) but expected in npj / JAMIA-style journal papers. **PI review may decide.**

**Total citation pass scope**: 17 named-paper placeholders + 4-7 tool / method citations = ~21-24 distinct references.

---

## 7. AIDA-Path slot decision

**Current state at HEAD `f192eaa`**: Mode A (pending). All §1, §2.6, §7.8 prose treats AIDA-Path as a planned external structural anchor, NOT a completed validation.

**Mode A wording in committed prose**:

| Section | Wording |
|---|---|
| §1 ¶5 line 25 | "AIDA-Path structural alignment and clinician review remain pending future work" |
| §1 ¶5 line 29 | "AIDA-Path structural alignment and clinician review of the DSM-5 v0 schema are pending future work" |
| §2.6 line 42 | "the associated code and data resource is named AIDA-Path [CITE Strasser-Kirchweger 2026 npj Digital Medicine]" (citation only; no validation claim) |
| §2.6 line 43 | "the present paper does not present any AIDA-Path overlap result as part of its evidence; structural alignment ... is planned future work" |
| §2.6 line 44 | "We do not claim AIDA-Path validation of CultureDx; if the planned overlap analysis completes before submission, §2.6 and §7.8 will be updated to a scoped external structural-alignment result" |
| §7.8 line 27 | "AIDA-Path structural alignment ... has been planned but not yet completed" |
| §7.8 line 28 | "We do not present any AIDA-Path overlap result or clinician-reviewed criterion as part of the present paper's evidence" |

**Binary decision required before submission**:

- **Path A (current default)**: keep Mode A wording exactly as is. No additional analysis needed for submission.
- **Path B (conditional)**: run overlap analysis between `dsm5_criteria.json` and AIDA-Path symptom-space representation. If completed, update §2.6 + §7.8 + §1 ¶5 to scoped external structural-alignment result. Round 52 §2 prep already documents the Mode A / Mode B switch protocol.

**Recommendation (deferred to PI / time budget)**:
- Path A is safe and submission-ready as-is
- Path B adds 1 scoped result (likely 2-3 days work for overlap computation + 1 figure or short table) but requires careful claim scoping ("structural-overlap measurement" not "clinical validation")

**Round 57 explicit guardrail**: "Do not write AIDA-Path completed wording." Manuscript assembly must NOT silently switch from Mode A to Mode B without explicit decision + actual overlap analysis.

---

## 8. Repo / reproducibility checklist

Reviewer-facing reproduction questions a JAMIA / npj reviewer would expect answered:

| # | Question | Where it's answered now | Needs reviewer-facing summary? |
|---:|---|---|:---:|
| 1 | Which branch / commit is the canonical paper version? | `main-v2.4-refactor` branch; HEAD as of submission | YES (in reproduction README) |
| 2 | How to reproduce Stacker LGBM Top-1 = 0.612 on LingxiDiag-16K? | §4.2 references training pipeline; §5.5 references `scripts/train_tfidf_baseline.py` | YES (single command) |
| 3 | How to reproduce reproduced TF-IDF Top-1 = 0.610? | §5.5 line 3 mentions `scripts/train_tfidf_baseline.py` | YES (single command) |
| 4 | Where are canonical metric outputs? | (TBD — needs explicit `outputs/` or `evaluation/` path documented) | YES |
| 5 | Which files are deprecated (pre-v4)? | §5.5 mentions `docs/analysis/AUDIT_REPORT_2026_04_22.md`; (full deprecated-files list TBD) | YES |
| 6 | What is the v4 evaluation contract? | §4.4 (Table 4 metric definitions) | YES (single-page summary) |
| 7 | How is F41.2 handled? | §3 line 32 (paper-parent F41.2 → F41); §3 line 14-15 (F41.2 excluded from binary 2-class) | YES (concise rule) |
| 8 | Where is the audit reconciliation? | §5.5 references "post-v4 audit reconciliation" | YES (file path) |
| 9 | What is the DSM-5 v0 schema source-of-truth? | §4.3 references `src/culturedx/ontology/data/dsm5_criteria.json` version `0.1-DRAFT` source-note `UNVERIFIED` | YES (file path + version) |
| 10 | What is the Both mode pass-through definition? | §4 line 33; §5.4 Table 5.4c | already in prose |

**Recommended reproduction README structure** (NOT drafted here; this is just the inventory):

```
README_REPRODUCTION.md
1. Quick start (one command per main result)
2. Branch / commit / data-version pinning
3. v4 evaluation contract one-pager
4. F41.2 handling rule
5. Deprecated files (pre-v4)
6. DSM-5 v0 schema disclaimer
7. Audit reconciliation pointer
8. Per-section reproduction map (which script produces which §X table)
```

This README is a **separate artifact from the manuscript**. Likely lives at `docs/REPRODUCTION.md` or `REPRODUCTION.md` at repo root; submission package includes a link.

---

## 9. Abstract claim constraints

Abstract is the LAST writing task per round 51 / 54 / 57 explicit. This ledger constrains the abstract claim-set.

### Allowed abstract claims (mapped to §1-§7 anchors)

| Claim | Anchor | Suggested abstract phrasing |
|---|---|---|
| Chinese psychiatric differential-diagnosis benchmark system | §1 ¶1, §3.1 | "We present CultureDx, a Chinese psychiatric differential-diagnosis benchmark system" |
| Multi-agent + hybrid-stacker architecture | §1 ¶3, §4.1, §4.2 | "combining a multi-agent reasoning pipeline with a hybrid supervised + MAS stacker" |
| Top-1 parity vs reproduced TF-IDF | §1 C1, §5.1 | "reaches Top-1 parity with a strong reproduced TF-IDF baseline (0.612 vs 0.610 within a ±5 percentage-point non-inferiority margin)" |
| F32/F41 cross-dataset asymmetry reduction | §1 C2, §5.3 | "reduces single-LLM F32/F41 directional asymmetry from 189× to 3.97× under MAS ICD-10 reasoning, with residual asymmetry" |
| Disagreement-based audit triage | §1 C3, §6.1 | "TF-IDF/Stacker disagreement flags 26.4% of cases at 2.06× error enrichment, complementary to confidence-based triage" |
| Dual-standard ICD-10 / DSM-5 audit (Both = pass-through) | §1 C4, §5.4, §7.3 | "Both mode preserves the ICD-10 primary output and attaches DSM-5 sidecar audit evidence on the same case" |
| Synthetic / curated benchmark scope + DSM-5 v0 unverified | §1 C5, §7.1, §7.2 | "We scope all results to synthetic / curated benchmark data and treat the DSM-5 v0 schema as unverified" |
| AIDA-Path / clinician review pending | §1 ¶5, §7.8 | "AIDA-Path structural alignment and clinician review of the DSM-5 v0 schema remain pending future work" |

**Abstract hero-number budget (lesson 50a applied)**: 3-5 hero numbers maximum. Suggested hero numbers:
1. 0.612 vs 0.610 (parity)
2. 189× → 3.97× (asymmetry reduction)
3. 26.4% / 2.06× (disagreement triage)

**Abstract word target**: 150-250 words depending on venue. Each hero number consumes ~10-20 words of context; budget allows ~5 hero numbers max under tight constraints.

### Forbidden abstract claims

```
❌ "SOTA LLM" / "LLM SOTA" / "outperforms LLM baselines"
❌ "MAS beats TF-IDF" / "MAS outperforms supervised baselines"
❌ "first multi-agent psychiatric diagnosis system"
❌ "clinically validated" (positive sense) / "clinical deployment" / "ready for clinical use"
❌ "DSM-5 superiority" / "DSM-5 improves robustness" / "DSM-5 generalizes better"
❌ "Both mode ensemble" / "dual-standard ensemble accuracy gain"
❌ "AIDA-Path validated CultureDx" / "AIDA-Path integration completed"
❌ "disagreement beats confidence"
❌ "bias solved" / "asymmetry resolved"
❌ "real-world clinical validation"
❌ "novel" / "first" without literature audit support
❌ McNemar p ≈ 1.0 as equivalence proof
❌ Aggressive verbs: drives / achieves / proves / demonstrates / yields / leads to
```

These 15+ forbidden patterns are the same set enforced across §1-§7 cumulative forbidden grep (lesson 43a). Abstract must pass the same grep.

### Round 57 explicit on Abstract

> "Abstract 是最容易 overclaim 的地方。要等 assembly pass 後再寫。"

Abstract drafting starts AFTER:
1. Citation pass complete (all `[CITE *]` markers resolved)
2. Table-number pass complete (manuscript-level numbers)
3. AIDA-Path slot decision (Mode A confirmed or Mode B activated)
4. PI review of full §1-§7 + assembly review

Abstract is NOT drafted in this assembly review.

---

## 10. Required edits before manuscript assembly

### Mandatory before submission

1. **Citation pass** — resolve 17 `[CITE *]` markers + 4-7 tool / method citations → `references.bib` or equivalent
2. **Table-number pass** — 8 current markdown tables (§4.4 evaluation contract unlabeled + §5.3 F32/F41 cascade unlabeled + Table 5.4a/b/c + Table 6.1a/b + Table 6.2a) → manuscript-level Table 1-8 (or per venue); 2 unlabeled tables need captions added
3. **AIDA-Path slot decision** — Path A (default) or Path B (run overlap analysis); update §2.6 + §7.8 + §1 ¶5 accordingly
4. **Reviewer-facing reproduction README** — per Item 8 checklist; lives at repo root or `docs/REPRODUCTION.md`
5. **Abstract drafting** — per Item 9 constraint ledger; LAST writing task

### Optional / deferred to PI review

6. **Concluding paragraph after §7** — round 57 explicit: do NOT add a new §8; a short concluding paragraph at end of §7 may absorb Discussion / Conclusion role
7. **1-2 figures** — per Item 3 figure-ledger discussion; venue-dependent
8. **Tools / models citation** — per Item 6 #18-21; venue-dependent (npj / JAMIA expects; ACL / EMNLP optional)
9. **Statistical-methods citations** — per Item 6 #22-24; usually expected in clinical-NLP venues

### Forbidden during assembly (per round 57 explicit)

❌ Write Abstract prose now
❌ Add new experiments
❌ Claim AIDA-Path completed without running overlap analysis
❌ Substantially modify §1-§7 prose
❌ Add new major section (§8 Discussion)
❌ Weaken §7 limitations

### Cross-section forbidden grep (lesson 43a) — re-run after any edit

After any §1-§7 prose change during assembly, re-run cross-section grep across all 12 prose files:

```
SOTA LLM / LLM SOTA
MAS beats TF-IDF
clinically validated (positive sense)
clinical deployment
DSM-5 superiority / DSM-5 improves robustness / DSM-5 generalizes better
Both mode ensemble / ensemble gain
bias solved / asymmetry resolved
AIDA-Path validated / AIDA-Path integration completed
clinician-reviewed DSM-5 criteria
TF-IDF is weak / TF-IDF beats BERT generally
MAS proves interpretability
first multi-agent / first Chinese psychiatric
deployment-ready / deployment properties
F41.2 is anxiety in 2-class / F33 is a paper class
```

These are the cumulative forbidden patterns from rounds 14-56. Currently 0 hits across all 12 prose files (verified at HEAD `f192eaa`).

---

## Round 58 narrow review request

```
Full manuscript assembly review committed at <hash>.

Status:
- 12 prose files, 6,882 words total
- 8 current markdown tables (6 labeled + 2 unlabeled at §4.4 / §5.3) requiring manuscript-level renumbering and caption assignment for unlabeled ones
- 0 figures currently; 1-2 candidate figures flagged for PI review
- 17 [CITE *] paper markers + 4-7 tool/method citations = ~21-24 references at citation pass
- AIDA-Path Mode A (pending) currently locked across §1, §2.6, §7.8
- Cross-section forbidden grep clean: 0 hits across 12 prose files

Round 58 narrow review:
1. Is the section inventory acceptable as the canonical manuscript scope?
2. Is the table-number renumbering plan reasonable?
3. Are the figure-ledger candidates (or 0-figure default) acceptable?
4. Is the claim-boundary ledger complete enough to constrain Abstract drafting?
5. Is AIDA-Path Mode A confirmed for this submission, or should we plan Mode B?
6. Is the citation-pass scope (~21-24 refs) and discipline acceptable?
7. Is the reproduction-README outline acceptable for the submission package?
8. Any §1-§7 cross-reference inconsistency caught during this assembly review?
```

If 8/8 pass → next deliverable is **citation pass** (Step 5b) OR **AIDA-Path Mode B execution** (Step 5c) depending on which is greenlit first.

If <8 pass → §1-§7 polish round to fix specific cross-reference / consistency issues caught.

---

## Sequential discipline status

```
✓ §3 + §4 closed (972f689)
✓ §5 + §6 + §7 closed (Phase 1)
✓ §1 closed (2c1bf73)
✓ §2 prep + lit audit + prose closed (70f8332, 5e6435e, f192eaa)
✓ Phase 2 Steps 1-4 complete
✓ Full major-section draft set complete
✓ Full manuscript assembly review prepared (this artifact)
□ Commit ← awaiting your push
□ Round 58 narrow review (8 questions)
□ Phase 2 Step 5 sub-steps:
  □ 5b: Citation pass (~21-24 references)
  □ 5c: AIDA-Path Mode A confirmation OR Mode B execution
  □ 5d: Table-number pass
  □ 5e: Reproduction README
  □ 5f: Abstract drafting (LAST)
□ Phase 2 Step 6: PI / advisor review
```

After this commit, manuscript-body authoring is done. Remaining work is integration, citation, reproduction, and abstract — all of which depend on this assembly review as the truth-ledger.
