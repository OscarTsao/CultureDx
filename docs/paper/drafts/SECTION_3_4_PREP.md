# §3 Task & Datasets + §4 Methods — Prep Package

**Date**: 2026-04-27
**Per GPT round 43**: Phase 2 Step 2 greenlight. Joint prep for §3 + §4 because Task / Datasets / Methods are tightly coupled (taxonomy, raw-code normalization, F41.2 exclusion, Table 4 v4 contract, dual-standard modes all cross both sections).
**Status**: Prep only. No prose. All numerical and categorical anchors verified against source artifacts at HEAD `35ba6a4`.

---

## ITEM 1 — Source artifacts (consolidated, with connector source-map per lesson 21a)

All 11 sources verified to exist on remote at HEAD `35ba6a4`:

| # | Artifact | Path | Role | Lines |
|---:|---|---|---|---:|
| 1 | Evaluation provenance (canonical) | `docs/analysis/EVALUATION_PROVENANCE.md` | §3 taxonomy + §4.4 v4 contract | 307 |
| 2 | v4 audit reconciliation | `docs/audit/AUDIT_RECONCILIATION_2026_04_25.md` | §4.4 deprecation map (post-v4 supersedes 2026-04-22 audit) | 174 |
| 3 | MAS vs LGBM contribution analysis | `docs/analysis/MAS_vs_LGBM_CONTRIBUTION.md` | §4.2 stacker feature-block setup | 180 |
| 4 | Disagreement-as-triage | `docs/analysis/DISAGREEMENT_AS_TRIAGE.md` | §4.5 triage metric definitions | 264 |
| 5 | F32/F41 asymmetry v4 | `docs/analysis/MDD5K_F32_F41_ASYMMETRY_V4.md` | §4.5 paired bootstrap methodology | 194 |
| 6 | Paper taxonomy / metrics module | `src/culturedx/eval/lingxidiag_paper.py` | §3.3 taxonomy code source-of-truth | 491 |
| 7 | DSM-5 v0 schema | `src/culturedx/ontology/data/dsm5_criteria.json` | §4.3 dual-standard infrastructure | 933 |
| 8 | Table 4 computation | `scripts/compute_table4.py` | §4.4 Top-1 / Top-3 / F1 / 2-class / 4-class wiring | 230 |
| 9 | Dual-standard recompute | `scripts/recompute_dual_standard_metrics.py` | §4.3 dual-standard runner | 197 |
| 10 | Stacker eval | `scripts/stacker/eval_stacker.py` | §4.2 stacker training/eval | 454 |
| 11 | TF-IDF reproduction script | `scripts/train_tfidf_baseline.py` | §4.2 TF-IDF baseline + §5.5 reproduction gap | 207 |

### Connector source-map (per lesson 21a; covers §3-§4 → §5-§7)

| §3 / §4 forward connector | §5-§7 anchor (committed) |
|---|---|
| §3.1 Task definition | §5.1 (12-class fine-grained Top-1 evaluation) |
| §3.2 Datasets | §5.1 (LingxiDiag-16K N=1000) + §5.3 (MDD-5k N=925) + §7.1 (synthetic-only scope) |
| §3.3 Taxonomy / F41.2 exclusion | §5.1 (12-class), §4.4 evaluation contract (2-class N=473 / 4-class) |
| §4.1 MAS architecture | §5.2 (MAS feature block 11.9% importance) + §5.4 (dual-standard modes) |
| §4.2 Baselines and stacker | §5.1 (Stacker LGBM 0.612 / TF-IDF 0.610 / MAS-only 0.516 / Stacker LR 0.538) |
| §4.3 Dual-standard infrastructure | §5.4 (ICD-10 / DSM-5-only / Both modes; Both = pass-through) + §6.2 + §7.2 |
| §4.4 Evaluation contract v4 | §5.1 / §5.4 / §5.5 / §6 / §7 (every metric in committed prose) |
| §4.5 Statistical analysis | §5.1 (McNemar p≈1.0), §5.3 (bootstrap CI [2.82, 6.08]), §6 (CI for triage advantage) |

---

## ITEM 2 — Global forbidden wording (cross-section grep applies per lesson 43a)

```
GLOBAL FORBIDDEN (per round 43 / 14-42 cumulative):
❌ "clinical diagnosis system"
❌ "clinical deployment" / "clinically validated" / "deployed system" / "deployment-ready"
❌ "real patient validation" / "real-world validation" / "prospective cohort"
❌ "DSM-5 diagnosis" (when describing our outputs)
❌ "DSM-5 clinical validity" / "DSM-5 superiority" / "DSM-5 generalizes better" / "DSM-5 improves robustness"
❌ "clinician-reviewed DSM-5 criteria" / "AIDA-Path validation completed"
❌ "Both mode ensemble" / "dual-standard ensemble" / "ensemble gain" / "combined prediction" (Both mode)
❌ "LLM SOTA" / "LLM system achieves" (without hybrid caveat)
❌ "MAS classifier beats supervised baseline"
❌ "MAS beats TF-IDF" / "MAS classifier wins"
❌ "stacker is an ensemble gain"
❌ "Top-3 = primary + comorbids" (round 43 explicit Trap 3 — wrong canonical formula)
❌ "F41.2 counted as anxiety in 2-class" (factually wrong; F41.2 EXCLUDED from 2-class)
❌ "all metrics use paper-parent labels" (factually wrong; 2-class / 4-class use raw `DiagnosisCode`)
❌ "F33 is a paper class" (F33 collapses to `Others`; confirmed in paper taxonomy code)
❌ "criterion-D = OCD time/distress" / "time/distress threshold" (lesson 40a Fix 2)
❌ "McNemar p≈1 proves equivalence" / "bootstrap CI includes zero proves equality"
❌ "disagreement beats confidence" (CI on advantage includes 0 per §6.1)
❌ "deployment properties" / "deployment-oriented properties" (round 43 sync; lesson 42a)
```

---

## ITEM 3 — Global allowed replacement patterns

```
✅ "benchmark differential diagnosis task" / "Chinese psychiatric differential diagnosis"
✅ "synthetic / curated benchmark" / "external synthetic distribution-shift dataset"
✅ "cross-dataset synthetic validation" / "benchmark-level external evaluation"
✅ "primary-output prediction" / "primary diagnosis"
✅ "audit trace" / "criterion-level audit trace"
✅ "structured reasoning pipeline" / "auditability-oriented architecture"
✅ "hybrid supervised + MAS stacker" / "LLM-backed MAS component"
✅ "metric-family-specific prediction views"
✅ "raw-code-aware 2-class / 4-class construction"
✅ "paper-parent normalization for 12-class metrics"
✅ "F41.2 excluded from binary depression/anxiety evaluation"
✅ "DSM-5 v0 audit observation" / "LLM-drafted unverified templates"
✅ "ICD-10 primary output with DSM-5 sidecar audit evidence"
✅ "standard-specific MAS reasoning modes"
✅ "experimental DSM-5 v0 formalization"
✅ "supports parity / non-inferiority under pre-specified margin"
✅ "no statistically detectable advantage"
✅ "paired bootstrap CI excludes zero for DSM-5 asymmetry amplification"
✅ "system properties" / "system-oriented audit properties" (post round 43)
```

---

## §3 PREP CONTENT

### §3.1 — Task definition

**Source**: `EVALUATION_PROVENANCE.md` lines 22-50; §5.1 prose.

**Locked claim**: CultureDx evaluates **Chinese-language psychiatric differential diagnosis** under a **12-class paper taxonomy**, using ICD-10 paper-parent labels for the main 12-class benchmark and raw `DiagnosisCode` information for 2-class / 4-class auxiliary tasks.

**Must include**:
- Input = Chinese psychiatric clinical dialogue / transcript (synthetic; LingxiDiag-16K curated)
- Output = ranked diagnostic candidates + primary diagnosis
- Main benchmark = 12-class parent-level paper taxonomy (Top-1 / Top-3 / F1_macro / F1_weighted)
- Multi-label gold handling (paper-parent multilabel set)
- Top-1 / Top-3 / F1 / Overall = paper-style evaluation metrics consistent with LingxiDiag report
- No claim of real clinical deployment or prospective clinical use

**Allowed wording** (per ITEM 3): "benchmark differential diagnosis task", "paper taxonomy", "primary-output prediction", "audit trace".

**Forbidden** (per ITEM 2): "clinical diagnosis system", "clinical deployment", "real patient validation", "DSM-5 diagnosis" (clinical sense).

---

### §3.2 — Datasets

**Source**: `EVALUATION_PROVENANCE.md` lines 22-60; §5.1 / §5.3 / §7.1 prose; LingxiDiag-16K + MDD-5k schemas.

#### §3.2.1 LingxiDiag-16K

**Locked claim**: Primary in-domain dataset; Chinese psychiatric synthetic / curated dialogues; main test_final split contains **N = 1000 cases**; raw `DiagnosisCode` field used for F41.2-aware auxiliary-task construction.

**Must include**:
- Synthetic / curated Chinese psychiatric dialogues
- N = 1000 test_final (used for primary in-domain benchmark)
- Source: original LingxiDiag report `[CITE LingxiDiag paper]`
- Raw codes preserved for 2-class / 4-class evaluation
- Paper-parent collapse for 12-class evaluation per `to_paper_parent` in `lingxidiag_paper.py`

**Forbidden / allowed**: see ITEM 2 / ITEM 3.

#### §3.2.2 MDD-5k

**Locked claim**: External synthetic distribution-shift dataset; Chinese clinical vignettes; **N = 925 cases**; used for **cross-dataset synthetic validation** of bias-robustness (§5.3) and dual-standard audit (§5.4 / §6.2); **this is external synthetic distribution-shift evaluation, not external clinical validation** (round 44 Fix C — synthetic qualifier is mandatory; "external validation" without "synthetic" risks reviewer reading as clinical-cohort validation).

**Must include**:
- External synthetic distribution-shift dataset
- N = 925
- Used for: F32/F41 bias-asymmetry analysis (§5.3) + dual-standard audit (§5.4) + diagnostic-standard discordance triage (§6.2)
- F33 cases: 2/925 (per `EVALUATION_PROVENANCE.md` line 44; collapse to `Others`)
- Raw `ICD_Code` field for raw-code-aware 2-class / 4-class auxiliary tasks (n=490 after F41.2 exclusion)
- Source: MDD-5k paper `[CITE MDD-5k paper]`

#### §3.2.3 Excluded / unused datasets

**Locked claim**: We mention E-DAIC and other potential cross-lingual datasets as future extensions only; they are **not used** in the present paper. We make no claim on cross-lingual generalization.

**Allowed only**: "future cross-lingual extension" / "scoped out of present paper".

---

### §3.3 — Taxonomy and label normalization (HIGH-RISK)

**Source**: `src/culturedx/eval/lingxidiag_paper.py` lines 17-160; `EVALUATION_PROVENANCE.md` lines 25-60.

This subsection is critical because it establishes the boundary between **12-class paper-parent** (semantic-level) and **2-class / 4-class raw-code-aware** (raw `DiagnosisCode`) tasks. Getting this wrong is exactly the source of the old `2class_n=696 vs 473` bug per `AUDIT_RECONCILIATION_2026_04_25.md` lines 39-40.

#### Locked taxonomy facts (verified against `lingxidiag_paper.py` lines 17-32)

**12 paper classes**: F20, F31, F32, F39, F41, F42, F43, F45, F51, F98, Z71, Others.

**Locked collapse rules** (verified against `to_paper_parent` + `EVALUATION_PROVENANCE.md` lines 47-58):

| Input | Output |
|---|---|
| F32, F32.x | F32 |
| F33, F33.x | **Others** (NOT a 12-class label; F33 cases: 0/1000 LingxiDiag, 2/925 MDD-5k) |
| F41, F41.x **including F41.2** | F41 (for 12-class metric) |
| F43, F43.x | F43 |
| Z71.x | Z71 |
| F34, F70, F90, G47 | Others |
| `""` / None | Others |

**2-class auxiliary task** (verified against `classify_2class_from_raw` lines 103-121):
- Input: raw `DiagnosisCode` string
- F41.2 → **EXCLUDED** (returns `None`; case dropped from 2-class evaluation)
- Mixed F32+F41 → **EXCLUDED** (returns `None`)
- Pure F32 → "Depression"
- Pure F41 (without F41.2) → "Anxiety"
- LingxiDiag expected n = 473; MDD-5k expected n = 490

**4-class auxiliary task** (verified against `classify_4class_from_raw` lines 122-140):
- Input: raw `DiagnosisCode` string
- F41.2 → "Mixed"
- F32+F41 comorbid → "Mixed"
- Pure F32 → "Depression"
- Pure F41 → "Anxiety"
- Else → "Others"

**Critical trap (round 43 Trap 3 explicit)**: Do NOT collapse raw subcodes before 2-class / 4-class gold construction.

**2-class N for MDD-5k under v4 contract** (verified against `AUDIT_RECONCILIATION_2026_04_25.md` line 98): `2class_n = 490` for all modes; F41.2 is excluded from the 2-class task.

**Allowed wording** (per ITEM 3): "raw-code-aware auxiliary-task construction", "paper-parent normalization for 12-class metrics", "F41.2 excluded from binary depression/anxiety evaluation".

**Forbidden** (per ITEM 2): "all F41.x collapse to F41 for every metric", "F41.2 is anxiety in 2-class", "F33 is a paper class".

---

## §4 PREP CONTENT

### §4.1 — CultureDx MAS architecture

**Source**: `src/culturedx/agents/`, `src/culturedx/diagnosis/`, `src/culturedx/modes/`.

**Locked claim**: CultureDx is a multi-agent reasoning architecture with auditable per-criterion evidence traces; the agents collectively implement structured psychiatric reasoning under a configurable diagnostic standard (ICD-10 or v0 DSM-5 templates).

**Must describe** (verified against `src/culturedx/agents/` filesystem):
- **Triage Agent** (`triage.py`)
- **Criterion Checker** (`criterion_checker.py`)
- **Logic Engine** (`diagnosis/logic_engine.py`)
- **Calibrator** (`diagnosis/calibrator.py`)
- **Comorbidity Gate** (`diagnosis/comorbidity.py`)
- **Diagnostician** (`diagnostician.py`) — supports Direct-to-Verdict (DtV) mode (used for MAS-only baseline in §5.1)
- **Pipeline modes**: `hied` (hierarchical evidence-driven, primary) and `single` (DtV-only baseline)
- LLM backbone: Qwen3-32B-AWQ via vLLM
- Retrieval: BGE-M3 (when used in final path)

**Locked terminology**: agents, criterion-level audit trace, structured reasoning pipeline.

**Allowed wording** (per ITEM 3): "criterion-level audit trace", "structured reasoning pipeline", "auditability-oriented architecture".

**Forbidden** (per ITEM 2):
- "MAS beats TF-IDF" / "MAS classifier wins" — §5.1 establishes MAS-only DtV is BELOW TF-IDF on Top-1 (0.516 vs 0.610)
- "criterion traces are clinically faithful" — agents are LLM-backed, not clinician-validated
- "agents are clinically validated"

---

### §4.2 — Baselines and stacker

**Source**: `MAS_vs_LGBM_CONTRIBUTION.md`; `scripts/stacker/eval_stacker.py`; `scripts/train_tfidf_baseline.py`; §5.1 / §5.2 / §5.5 prose.

**Locked claim**: We compare four candidate systems against two LingxiDiag-published reference baselines. Our selected primary system is **Stacker LGBM**, a hybrid supervised + MAS stacker.

#### System lineup

| System | Role | §5.1 Top-1 |
|---|---|---:|
| Stacker LGBM (primary) | hybrid TF-IDF + MAS feature stacker (LightGBM tree booster) | **0.612** |
| Reproduced TF-IDF baseline | logistic-regression on character/word TF-IDF features | **0.610** |
| MAS-only DtV | Direct-to-Verdict diagnostician without supervised features | 0.516 |
| Stacker LR | hybrid TF-IDF + MAS stacker (logistic regression) | 0.538 |
| Published TF-IDF baseline | LingxiDiag report TF-IDF | 0.496 |
| Published best LLM baseline | LingxiDiag report LLM | (per §5.1) |

#### Stacker feature decomposition (verified against `MAS_vs_LGBM_CONTRIBUTION.md` lines 11-18)

**31 total features** =
- **TF-IDF block (13 features)**: TF-IDF per-class probabilities (12) + Top-1 margin (1)
- **MAS block (18 features)**: DtV rank confidences (5) + checker met-ratios per class (12) + abstain flag (1)

**Important §4.2 wording requirement**: Stacker is a hybrid supervised + MAS model, not an LLM-only system. This must be established in §4.2 so §5.1's hybrid caveat ("we treat this as a hybrid-system comparison rather than an LLM-only result") is not surprising to reviewers.

**LR retained as macro-F1-oriented comparator** (Top-1 = 0.538 fails ±5pp non-inferiority but macro-F1 = 0.360 is highest in our evaluation per §5.1).

**TF-IDF reproduction gap** (forward-reference to §5.5): Our reproduced TF-IDF Top-1 = 0.610 vs published 0.496 (11.4pp gap, not fully isolated). Discussed transparently in §5.5.

**Forbidden** (per ITEM 2):
- "LLM system" without hybrid caveat
- "MAS classifier beats supervised baseline" (it doesn't on Top-1)
- "stacker is an ensemble gain" (confidence-gated ensemble § 5.6 is null)

---

### §4.3 — Dual-standard infrastructure

**Source**: `src/culturedx/ontology/data/dsm5_criteria.json` (v0 schema); `src/culturedx/agents/criterion_checker.py` + `diagnostician.py` (DiagnosticStandard enum); `scripts/recompute_dual_standard_metrics.py`; §5.4 / §6.2 / §7.2 prose.

**Locked claim**: The MAS architecture supports three standard-specific operating modes by parameterizing the `DiagnosticStandard` enum (`ICD10`, `DSM5`, `BOTH`):

| Mode | Behavior | Primary output |
|---|---|---|
| **ICD-10 mode** | MAS reasoning uses ICD-10 templates throughout | ICD-10 paper-parent diagnosis |
| **DSM-5-only mode** | Same MAS architecture; reasoning uses v0 DSM-5 templates | DSM-5 v0 diagnosis (audit observation) |
| **Both mode** | ICD-10 reasoning produces primary output; DSM-5 reasoning runs as sidecar audit on the same case | ICD-10 primary + DSM-5 sidecar audit evidence |

**Critical claim** (carries forward to §5.4 / §7.3): Both mode is an **architectural pass-through**, not an ensemble. Pairwise agreement with ICD-10 mode is 1000/1000 on LingxiDiag-16K and 925/925 on MDD-5k; 0/15 metric-key differences (Table 5.4c).

**DSM-5 v0 schema disclosure** (carries forward to §7.2):
- Source-of-truth file: `src/culturedx/ontology/data/dsm5_criteria.json`
- Version: `0.1-DRAFT`
- Source-note: "LLM-drafted v0 based on DSM-5-TR concepts. UNVERIFIED."
- This is an experimental audit formalization, not clinically validated DSM-5 criteria
- AIDA-Path structural alignment + clinician review pending (§7.8)

**Allowed wording** (per ITEM 3): "standard-specific MAS reasoning modes", "DSM-5 sidecar audit evidence", "experimental DSM-5 v0 formalization", "ICD-10 primary output with DSM-5 sidecar audit evidence".

**Code-level vs paper-facing terminology distinction** (round 44 Fix A): For paper readability, ICD-10, DSM-5-only, and Both are referred to as **standard configurations**. In the code, these are standard-dispatch settings (`DiagnosticStandard.{ICD10, DSM5, BOTH}`) within the HiED mode rather than separate `mode=` values; the actual code-level pipeline modes are `hied` and `single` (where `single` is the DtV-only baseline used for MAS-only comparators in §5.1).

**Allowed wording** (round 44 Fix A): "standard configurations", "standard-dispatch settings within the HiED mode".

**Forbidden** (per ITEM 2 + round 44 Fix A): "DSM-5 clinical diagnosis", "dual-standard ensemble", "DSM-5 improves robustness", "Both mode ensemble", "the code has separate `icd10`, `dsm5`, and `both` modes" (factually wrong; they are standard-dispatch settings within HiED, not separate code modes).

---

### §4.4 — Evaluation contract v4 (CRITICAL for reviewer trust)

**Source**: `EVALUATION_PROVENANCE.md` (full document); `AUDIT_RECONCILIATION_2026_04_25.md`; `scripts/compute_table4.py`; `src/culturedx/eval/lingxidiag_paper.py`.

**Locked claim**: All §5 / §6 numbers in the present paper are computed under evaluation contract v4 (post-2026-04-25 reconciliation). Earlier audit values (`docs/analysis/AUDIT_REPORT_2026_04_22.md`) are superseded for numerical claims.

#### §4.4 metric source table (verified against `EVALUATION_PROVENANCE.md` lines 60-110)

| Metric family | Prediction source | Gold source | Notes |
|---|---|---|---|
| 12-class Top-1 | `primary_diagnosis` paper-parent | multilabel paper-parent gold | canonical: `metrics.json -> table4 -> 12class_Top1` |
| 12-class Top-3 | `[primary] + (ranked − {primary})[:2]` | multilabel paper-parent gold | NOT `primary + comorbid_diagnoses` (round 43 Trap 3) |
| 12-class F1 / Exact Match | `primary + threshold-gated comorbid_diagnoses` | multilabel paper-parent gold | NOT ranked Top-3 |
| 2-class | primary prediction mapped to binary category via `classify_2class_prediction` | raw `DiagnosisCode`; F41.2 excluded | LingxiDiag n=473, MDD-5k n=490 |
| 4-class | predicted label set mapped to four-class category via `classify_4class_prediction` | raw `DiagnosisCode`; F41.2 → Mixed | All 925 / 1000 cases retained |
| Overall | mean of all non-`_n` Table 4 metric values | — | recomputed after any metric change |

#### §4.4 deprecated artifacts disclosure (CRITICAL)

**Per `AUDIT_RECONCILIATION_2026_04_25.md` lines 39-65**: pre-v4 audit values used parent-collapsed 2-class gold, which lost F41.2 and falsely included mixed cases (`n=696` instead of `473`). Under v4 contract, F41.2 is excluded per paper definition, and 2-class `n` reverts to the correct value.

| Field | Pre-v4 (audit) | Post-v4 | Reason |
|---|---:|---:|---|
| stacker_lgbm 2class_Acc | 0.685 | **0.7526** | F41.2 excluded; n=696 → 473 |
| stacker_lgbm 2class_n | 696 | **473** | F41.2 excluded per paper definition |
| stacker_lgbm 4class_Acc | not in audit | **0.5460** | New under v4 4-class contract |

**Reviewer-facing disclosure required**: paper must state that v4 contract supersedes earlier paper-number artifacts for current claims; readers should not cite pre-v4 numbers from `AUDIT_REPORT_2026_04_22.md`. **Earlier artifacts are retained for provenance; current paper claims use the post-v4 metric-consistency report and audit reconciliation** (round 44 Fix D).

**Allowed wording** (round 44 Fix B + D):
- "raw `DiagnosisCode` is used to construct 2-class / 4-class gold labels; predictions are mapped from model outputs to the corresponding binary or four-class category"
- "Earlier artifacts are retained for provenance; current paper claims use the post-v4 metric-consistency report and audit reconciliation"

**Forbidden** (per ITEM 2 + round 43 Trap 3 + round 44 Fix B + Fix D):
- "Top-3 = primary + comorbids" (factually wrong)
- "F41.2 counted as anxiety in 2-class"
- "all metrics use paper-parent labels"
- "4-class predictions use raw `DiagnosisCode`" (round 44 Fix B; predictions are mapped from model outputs, not read from raw code)
- "old audit was wrong" / "previous numbers are invalid" (round 44 Fix D; superseded ≠ wrong)

---

### §4.5 — Statistical analysis

**Source**: `src/culturedx/eval/statistical_tests.py`; `scripts/bootstrap_ci.py`; `EVALUATION_PROVENANCE.md` lines 130-145; §5.1 / §5.3 / §6 prose.

**Locked methodology**:

| Test | Use | Parameters |
|---|---|---|
| **McNemar paired test** | Paired Top-1 comparison (Stacker LGBM vs reproduced TF-IDF) | continuity correction; p < 0.05 threshold |
| **Bootstrap CI** | Asymmetry ratios; metric differences | 1000 resamples, seed `20260420`, 95% percentile interval |
| **Pre-specified non-inferiority margin** | Parity claim (§5.1) | ±0.05 absolute (5 percentage points) |
| **Paired bootstrap** | F32/F41 asymmetry comparison (DSM-5 vs ICD-10) | per `MDD5K_F32_F41_ASYMMETRY_V4.md` |
| **Disagreement triage metrics** | §6.1 / §6.2 | flag rate, accuracy flagged/unflagged, error enrichment, error recall |

**Non-inferiority / McNemar relationship** (round 44 Fix E):
Non-inferiority is assessed by the paired Top-1 difference relative to the pre-specified ±5pp margin, NOT by the McNemar p-value alone.
McNemar is reported as a paired discordance test (evidence of no detectable paired difference at our sample size), not as an equivalence test.
The parity claim in §5.1 rests on the bounded effect size (+0.2pp Stacker LGBM vs reproduced TF-IDF, well within ±5pp margin), with McNemar p ≈ 1.0 reported as supporting descriptive context.

**Locked claim wording**:

✅ Allowed:
- "supports parity / non-inferiority under pre-specified margin"
- "no statistically detectable advantage" (when CI on advantage includes 0)
- "paired bootstrap CI excludes zero for DSM-5 asymmetry amplification"
- "the small paired Top-1 difference relative to the pre-specified ±5pp margin supports non-inferiority"
- "McNemar p ≈ 1.0 is reported as evidence of no detectable paired difference, not as an equivalence proof" (both bullets together = round 44 Fix E)

❌ Forbidden:
- "McNemar p ≈ 1 proves equivalence" (round 43 explicit + round 44 Fix E; failure to reject ≠ proof of equivalence)
- "bootstrap CI includes zero proves equality"
- "disagreement beats confidence" (CI on advantage in §6.1 includes 0)

---

## ITEM 5 — Cross-section consistency map (lesson 43a temporal-residue check)

For every §3 / §4 fact, the corresponding §5-§7 anchor that it must support:

| §3 / §4 fact | Used in §5-§7 prose at |
|---|---|
| 12-class paper taxonomy (12 codes) | §5.1 (Top-1, Top-3, F1, Overall on 12-class) |
| LingxiDiag-16K N = 1000 | §5.1 / §5.4 / §6 / §7 |
| MDD-5k N = 925 | §5.3 / §5.4 / §6 / §7 |
| F33 collapses to Others (not a paper class) | implicit in 12-class metrics |
| F41.2 excluded from 2-class; → Mixed in 4-class | §4.4 + §3.3 (this prep) |
| 2-class n = 473 (LingxiDiag), 490 (MDD-5k) | this prep — should be cross-referenced if §5 inlines 2-class numbers |
| 31-feature stacker (13 TF-IDF + 18 MAS) | §5.2 (88.1% / 11.9% feature-importance share) |
| Stacker LGBM Top-1 = 0.612 | §5.1 |
| Reproduced TF-IDF Top-1 = 0.610 | §5.1 / §5.5 |
| Published TF-IDF Top-1 = 0.496 | §5.5 |
| MAS-only DtV Top-1 = 0.516 / 2-class = 0.803 | §5.1 |
| Stacker LR Top-1 = 0.538 / macro-F1 = 0.360 | §5.1 |
| 3 modes (ICD-10 / DSM-5-only / Both) | §5.4 / §6.2 |
| Both mode = ICD-10 pass-through (1000/1000, 925/925, 0/15) | §5.4 Table 5.4c / §7 line 10 |
| `dsm5_criteria.json` v0.1-DRAFT / UNVERIFIED | §5.4 line 8 / §7 line 8 |
| McNemar p ≈ 1.0 (Top-1 paired) | §5.1 line 5 / §5.6 |
| Bootstrap 1000 resamples, seed 20260420 | §5.3 (CI [2.82, 6.08]) |
| ±5pp non-inferiority margin | §5.1 line 5 / §5.5 |
| Paired bootstrap (DSM-5 − ICD-10) on MDD-5k Δratio = +3.24 [+1.12, +6.89] | §5.3 line 22 |

**Cross-section consistency check pass criterion**: every fact in §3 / §4 prep traces to either source artifact or §5-§7 prose; nothing fabricated; nothing contradicts §5-§7.

✅ All 19 facts in the table above verified against source artifact OR committed §5-§7 prose during this prep drafting.

---

## ITEM 6 — Reviewer attacks + responses

### Attack 1 — Synthetic data overclaim

> "All your evaluation is synthetic — your claims don't apply to real clinical settings."

**Response**: Section 7.1 makes the synthetic-only scope explicit; we have not yet evaluated CultureDx on clinician-adjudicated real-world clinical transcripts. The §3.2 dataset descriptions reinforce this: LingxiDiag-16K is curated synthetic dialogue and MDD-5k is an external synthetic distribution-shift dataset. We frame all benchmark behavior as audit-relevant system properties, not clinical evidence.

### Attack 2 — F33 missing from 12-class

> "F33 (recurrent depressive disorder) is a major ICD-10 category. Why is it not a paper class?"

**Response**: F33 is collapsed to `Others` per the LingxiDiag paper's original taxonomy (locked by `lingxidiag_paper.py:to_paper_parent`). F33 cases occur 0/1000 in LingxiDiag and 2/925 in MDD-5k, so the empirical impact is negligible. Our DSM-5 v0 ontology retains an F33 stub for system extensibility, but it is not a 12-class evaluation label.

### Attack 3 — 2-class n discrepancy (vs pre-v4 audit)

> "Earlier audit reports list 2-class n = 696, but you report n = 473. Did you change the evaluation?"

**Response**: Yes; `AUDIT_RECONCILIATION_2026_04_25.md` documents the v4 contract correction. Pre-v4 2-class gold was constructed from parent-collapsed labels, which lost F41.2 and falsely included mixed anxiety-depression cases (n = 696). Under the v4 contract, 2-class gold uses raw `DiagnosisCode` and explicitly excludes F41.2 per the paper's binary-task definition (n = 473). All §5-§7 numbers use the v4 contract; pre-v4 audit numbers are not cited.

### Attack 4 — DSM-5 not clinically validated

> "Your DSM-5 results aren't trustworthy because the criteria are LLM-drafted."

**Response**: Section 7.2 acknowledges this explicitly. The DSM-5 schema (`dsm5_criteria.json`, version `0.1-DRAFT`, source-note `UNVERIFIED`) is an LLM-drafted v0 formalization without clinician review. We frame DSM-5 outputs throughout as experimental audit observations rather than clinically validated DSM-5 diagnoses. The §5.4 and §6.2 dual-standard analyses support this scoped interpretation; they do not assert DSM-5 clinical validity.

### Attack 5 — MAS contributes nothing if TF-IDF carries the load

> "Your §5.2 says TF-IDF features account for 88.1% of feature importance. Why retain MAS at all?"

**Response**: We do not claim MAS contributes accuracy gain over TF-IDF on Top-1 (§5.2 + §5.6 confidence-gated null result). The case for retaining MAS rests on system properties not captured by Top-1 alone: F32/F41 cross-dataset bias-asymmetry reduction (§5.3, 47.7-fold reduction), dual-standard audit traces (§5.4), case-level disagreement-triage signals (§§6.1-6.2). Section 5.2 explicitly frames MAS as auditability-oriented infrastructure.

### Attack 6 — McNemar p ≈ 1.0 doesn't prove equivalence

> "Failure to reject the null doesn't prove equivalence."

**Response**: Correct, and we don't claim equivalence from McNemar alone. Section 5.1 supports parity under a pre-specified ±5 percentage-point non-inferiority margin: paired Top-1 difference is +0.2pp (0.612 − 0.610), well within the margin. McNemar p ≈ 1.0 is reported descriptively; the parity claim rests on the bounded effect size, not the p-value.

---

## ITEM 7 — Prose plan (NO PROSE)

Per GPT round 43 explicit:
> "Greenlight §3 / §4 prep package only. Do not write §3 / §4 prose yet."

When §3 / §4 prose is authorized (post round 44), structure:

| Subsection | Estimated words |
|---|---:|
| §3.1 Task definition | 80-120 |
| §3.2.1 LingxiDiag-16K | 100-150 |
| §3.2.2 MDD-5k | 100-150 |
| §3.2.3 Excluded datasets | 40-60 |
| §3.3 Taxonomy + raw-code handling (HIGH-RISK; needs careful precision) | 200-300 |
| §4.1 MAS architecture | 200-300 |
| §4.2 Baselines and stacker | 200-300 |
| §4.3 Dual-standard infrastructure | 150-250 |
| §4.4 Evaluation contract v4 (CRITICAL) | 250-350 |
| §4.5 Statistical analysis | 100-150 |

**Total estimate**: ~1,420-2,130 words across 10 subsections. May trend toward upper end given §3.3 and §4.4 require careful technical precision.

**Format discipline (lesson 33a)**: Sentence-level line breaks from initial draft. Not as post-hoc cleanup.

**Lesson 40a explicit**: every numerical anchor / technical definition must be greppable in source artifact OR §5-§7 prose BEFORE placement. Already verified during this prep.

**Lesson 43a explicit**: at first §3+§4 prose draft, run cross-section forbidden grep against §3 + §4 + §5 + §6 + §7 simultaneously, not just §3 + §4 in isolation.

**No tables in §3.1, §3.2.1, §3.2.2, §3.2.3, §4.5**. Tables likely needed in §3.3 (collapse rules), §4.2 (system lineup + Top-1), §4.4 (metric source + deprecation map). §4.3 may use a 3-row table for the modes.

---

## Round 44 review request (per round 43 spec)

```
§3/§4 prep committed at <hash>.

Round 44 narrow review:
1. Are datasets described without clinical overclaim?
2. Is taxonomy / F41.2 / raw-code handling correct?
3. Is v4 evaluation contract sufficiently explicit?
4. Are MAS / stacker / dual-standard methods separated cleanly?
5. Can we start §3 / §4 prose?
```

---

## Cumulative round 14-43 lessons applied during this prep

| Lesson | Application in §3/§4 prep |
|---|---|
| 21a | All 11 source artifacts listed with paths + roles + connector source-map (Item 1) |
| 22d / 27a/b / 42a | "deployment" / "deployed" only in negated/forbidden context; "system properties" used as positive replacement |
| 23b / 38b | §4.5 quantifier scope: "supports parity" not "proves equivalence"; "no statistically detectable advantage" not "no advantage" |
| 25a-d | Every fact verified against source artifact; F41.2 / 12-class / mode definitions all cited from `lingxidiag_paper.py` lines |
| 25b / 32a / 38a | Mode terminology: "ICD-10 / DSM-5 / Both" framed as standards, not "models"; "DSM-5 v0" / "audit observation" / "primary-output" precision |
| 31a | Cross-section consistency map (Item 5) — every §3/§4 fact traces to §5-§7 anchor |
| 33a | Format-during-draft: sentence-level breaks throughout this prep |
| 35a | Mechanism precision: §4.5 statistical methodology explicitly references Bootstrap parameters (1000 resamples, seed 20260420) per code |
| 36a (escalation) | Bare-stem grep + multi-location-class sweep applied to forbidden list |
| 38a | Distinguish "modes" / "diagnostic standards" / "models" / "configurations" precisely |
| 40a | Every numerical anchor (12 classes, 31 features, n=473/490, etc.) grep-verified in source code/docs BEFORE placement |
| 42a | "deployment properties" not used positively; "system properties" / "system-oriented audit properties" replacements |
| 42b | Paper register: "supports parity" / "we do not claim" / "v4 contract" wording — not internal-discussion register |
| **43a** | Cross-section forbidden grep applies to §3 + §4 + §5 + §6 + §7 simultaneously per Item 5 + Item 7 prose-plan reminder |

§3+§4 prep is the largest prep file to date (10 subsections; covers Methods + Datasets + Task + statistical methods). Inherits all 33 cumulative lessons.

---

## Sequential discipline status

```
✓ §5 fully closed
✓ §6 fully closed
✓ §7 fully closed
✓ Phase 2 Step 1 closed (integration review at 778931f, wording sync at 35ba6a4)
□ Phase 2 Step 2: §3+§4 prep ← awaiting your push
□ Round 44 narrow review
□ §3+§4 prose v1 ← if 5/5 pass
```

§3+§4 prep is structurally largest of any prep file delivered (vs §6 prep's 12 traps, §7 prep's 8 limitation blocks). Estimated ~600-700 lines when committed.
