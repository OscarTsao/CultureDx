# §2 Related Work / Background — Prep Package

**Date**: 2026-04-28
**Per GPT round 51**: §1 closed at `2c1bf73`. Phase 2 Step 4 greenlight. §2 Related Work prep only.
**Status**: Prep-only deliverable. 6 thematic subsections + 8 citation source buckets + global trap list + 5 round-52 review questions. All references to §1-§7 verified at HEAD `2c1bf73`. Lesson 50a applied proactively (citation-density target ≈ 1 citation per 50-80 words, not literature dump).

---

## ITEM 1 — Section purpose

§2 Related Work is **not a literature dump**. It serves the paper story locked in §1 thesis sentence:

> "CultureDx reaches Top-1 parity with a strong reproduced TF-IDF baseline while adding MAS-enabled audit properties: cross-dataset F32/F41 bias-asymmetry reduction under ICD-10 MAS, model/standard-discordance triage, and dual-standard ICD-10/DSM-5 audit output."

§2's job is to bring readers to five conclusions:

1. **Psychiatric NLP / LLM diagnosis evaluation should not be Top-1-only** (motivates §1 ¶1-¶2)
2. **Strong supervised baselines deserve respect, not dismissal** (motivates §1 ¶2 + Contribution 1 parity claim)
3. **MAS value must be argued via auditability / disagreement / standard sensitivity, not accuracy dominance** (motivates §1 ¶3 + Contributions 3-4)
4. **DSM-5 / ICD-10 formalization is a real research question, but DSM-5 v0 in this paper is NOT clinical validation** (motivates §1 Contribution 4 scope + §7.2)
5. **AIDA-Path is an external structural anchor — pending if not yet completed; scoped if completed** (motivates §1 ¶5 + §7.8)

Each subsection contributes to one or more of these positioning conclusions. No subsection can be removed without weakening §1.

---

## ITEM 2 — 8 citation source buckets

§2 needs literature citations rather than repo source-of-truth artifacts (unlike §3-§7 prep). Source buckets must be inventoried explicitly to avoid §2 prose hallucinating references. Each `[CITE *]` placeholder in committed §1-§7 prose corresponds to one of these buckets.

| # | Bucket | Role in §2 | Existing `[CITE *]` markers in repo |
|---:|---|---|---|
| 1 | LingxiDiag paper / benchmark source | §2.1 Chinese psychiatric NLP | §3.1 line 7, §3.2.1 line 14, §5.1 line 3 (`[CITE LingxiDiag paper]` ×3) |
| 2 | MDD-5k dataset source | §2.1 Chinese psychiatric NLP / §2.5 distribution-shift evaluation | §3.2.2 (no `[CITE MDD-5k paper]` marker yet — TBD: confirm by literature audit) |
| 3 | Psychiatric LLM diagnosis / clinical LLM caution literature | §2.2 LLMs for psychiatric diagnosis | none in repo; literature audit needed |
| 4 | Multi-agent / agentic clinical reasoning literature | §2.3 MAS and auditability | none in repo; literature audit needed |
| 5 | Classical supervised baselines / TF-IDF in clinical NLP | §2.4 Classical baselines and hybrid systems | none in repo; literature audit needed |
| 6 | ICD-10 / DSM-5 official descriptions and ontology / criteria-formalization literature | §2.5 Diagnostic standards | none in repo; literature audit needed |
| 7 | AIDA-Path paper / repo / npj Digital Medicine paper | §2.6 AIDA-Path positioning | §7.8 line 27 mentions AIDA-Path by name; §1 ¶5 line 29 mentions; no `[CITE *]` marker in current draft |
| 8 | Tools / models if mentioned in related work: Qwen, vLLM, BGE-M3, LightGBM | brief Methods-cross-reference; possibly §2.4 hybrid-stacker context | mentioned in §4.1 / §4.2 / §1 ¶3; no `[CITE *]` marker yet |

**Bucket 7 citation-naming note (round 52 Fix D)**:
The formal paper title and venue is the primary reference: Strasser-Kirchweger et al., "Machine-actionable criteria chart the symptom space of mental disorders," *npj Digital Medicine*, 2026.
"AIDA-Path" is the associated code / data resource name (GitHub `raoul-k/AIDA-Path`).
Cite the paper as the primary reference; use "AIDA-Path" as the resource name only when supported by the paper or repository.
This avoids writing as if "AIDA-Path" is the article title.

**Citation discipline note**: Buckets 3, 4, 5 require literature audit before §2 prose drafting. Until that audit completes, §2 prep cannot finalize specific citations and must use bucket-typed `[CITE *]` placeholders (e.g. `[CITE psychiatric LLM diagnosis]`, `[CITE MAS clinical reasoning]`, `[CITE TF-IDF clinical NLP]`). This is distinct from §3-§7 prep where source-of-truth was repo-internal.

**Lesson 50a application** (citation-density target): §2 prose targets 1 citation per ~50-80 words. At 600-900 words total, that means 8-15 distinct citations across §2. NOT 30+. NOT one citation per sentence. Citations should support positioning claims, not exhaustively map the field.

---

## ITEM 3 — Global forbidden wording (Related Work-specific)

```
GLOBAL FORBIDDEN (Related Work is most prone to "first / SOTA / dismiss" framings):
❌ "first" / "first multi-agent" / "first Chinese psychiatric"
❌ "novel" / "novel contribution" used loosely without literature audit support
❌ "to our knowledge" UNLESS literature audit explicitly supports it
❌ "SOTA LLM" / "LLM SOTA" / "state-of-the-art LLM"
❌ "MAS beats TF-IDF" / "MAS outperforms supervised baselines"
❌ "TF-IDF is weak" / "classical baselines are insufficient" / "supervised baselines fail"
❌ "previous work fails to" / "no prior work has" / "this is the first"
❌ "clinically validated" (positive sense) / "clinical deployment" / "ready for clinical use"
❌ "DSM-5 superiority" / "DSM-5 improves robustness" / "DSM-5 generalizes better"
❌ "DSM-5 clinical diagnosis" (when describing CultureDx outputs)
❌ "AIDA-Path validated CultureDx" / "AIDA-Path integration completed"
❌ "clinician-reviewed DSM-5 criteria"
❌ "MAS proves interpretability"
❌ "criterion traces are clinically faithful"
❌ "comprehensive review of psychiatric NLP" (we are NOT writing a survey)
❌ "the literature on X is divided" / "there is no consensus on Y" without sources
❌ "§2 restates CultureDx result numbers such as 0.610, 0.612, 11.4pp, 189×, or 3.97×" (round 52 Fix C — Related Work motivates why dimensions matter; CultureDx-specific numerical evidence belongs in §5 / §6)
```

---

## ITEM 4 — Global allowed replacement patterns

```
✅ "to our knowledge" — ONLY if literature audit (Item 2 buckets 3, 4, 5) supports the claim
✅ "benchmark-level evaluation" / "Chinese psychiatric differential-diagnosis benchmark"
✅ "synthetic / curated dialogue data"
✅ "audit-oriented architecture" / "audit-relevant system properties"
✅ "modular / multi-agent diagnostic reasoning"
✅ "criterion-level trace outputs" / "criterion-level audit trace"
✅ "strong supervised baseline" / "remarkably competitive lexical baseline"
✅ "hybrid supervised + MAS stacker" / "hybrid system rather than LLM-only"
✅ "accuracy parity rather than superiority"
✅ "standard-specific reasoning" / "criteria formalization"
✅ "experimental DSM-5 v0 audit formalization" / "LLM-drafted v0 schema"
✅ "sidecar audit evidence" / "ICD-10 primary output with DSM-5 sidecar audit"
✅ "pending clinical validation" / "pending clinician review"
✅ "pending structural alignment" / "planned AIDA-Path overlap analysis"
✅ "external criteria-formalization reference"
✅ "complementary to" / "extends prior work along dimension X"
✅ "differs from prior work in scope X"
✅ "§2 motivates why these dimensions matter; CultureDx-specific numerical evidence belongs in §5 / §6" (round 52 Fix C — lesson 50a applied to Related Work: citation and anchor density both controlled)
```

---

## §2 PREP CONTENT — 6 thematic subsections

Per GPT round 51 explicit, §2 has 6 thematic subsections each serving one or more of the 5 positioning conclusions in Item 1.

---

### §2.1 — Chinese psychiatric NLP and LingxiDiag-style benchmarks

**Purpose**: Establish task background; motivate why Chinese psychiatric differential diagnosis is a benchmark task with synthetic-data caveats.

**Source**: Bucket 1 (LingxiDiag) + Bucket 2 (MDD-5k) + general Chinese clinical-NLP literature.

**Locked claims**:
- Chinese psychiatric NLP has emerging benchmark datasets covering psychiatric clinical dialogue / transcripts
- LingxiDiag-style benchmarks adopt a paper-parent ICD-10 12-class taxonomy with Top-1 / Top-3 / F1 / Overall metrics
- The datasets used in the present study (LingxiDiag-16K and MDD-5k) are synthetic or curated rather than clinician-adjudicated real-world clinical transcripts (round 52 Fix A — scoped to this study, not generalized over the Chinese psychiatric NLP field)
- Distinction between **benchmark evaluation** (what current datasets enable) and **clinical validation** (what they don't)

**Allowed wording** (per Item 4): "Chinese psychiatric differential-diagnosis benchmark", "synthetic / curated dialogue data", "paper taxonomy", "benchmark-level evaluation".

**Forbidden** (per Item 3): "real-world clinical validation", "prospective clinical cohort", "clinically deployed diagnosis", "comprehensive review of psychiatric NLP" (avoid survey framing).

**Estimated length**: 100-130 words.

---

### §2.2 — LLMs for psychiatric / clinical diagnosis

**Purpose**: Motivate why LLM psychiatric diagnosis must be evaluated cautiously; support §1 ¶1-¶2's "Top-1 alone is insufficient" framing.

**Source**: Bucket 3 (psychiatric LLM diagnosis / clinical LLM caution literature). **Literature audit required before prose drafting.**

**Locked claims**:
- LLMs can produce diagnostic suggestions and reasoning traces, but psychiatric diagnosis is high-stakes and context-sensitive
- LLM clinical reasoning literature documents both potential and risks, including hallucination, overconfidence, and lack of structured uncertainty
- This motivates transparent evaluation, uncertainty disclosure, and explicit limitation framing — which is the posture CultureDx adopts in §7
- Benchmark-level LLM diagnostic evaluation is NOT clinical validation

**Allowed wording**: "LLM-backed diagnostic reasoning", "benchmark diagnostic suggestion", "audit trace", "requires clinical validation".

**Forbidden**: "LLM psychiatrist", "clinically validated LLM diagnosis", "ready for clinical use", "LLM SOTA".

**Estimated length**: 100-130 words.

---

### §2.3 — Multi-agent diagnostic systems and auditability

**Purpose**: Position CultureDx's MAS architecture as one of several modular / agent-based approaches in clinical reasoning literature; AVOID "first / best / clinically validated" framing.

**Source**: Bucket 4 (multi-agent / agentic clinical reasoning literature). **Literature audit required.**

**Locked claims**:
- Multi-agent and modular diagnostic systems can decompose diagnostic reasoning into inspectable subtasks; CultureDx operationalizes this idea through criterion checking, logic, calibration, and comorbidity handling (round 52 Fix B — prior work credited only with general modular decomposition, not CultureDx's specific stages)
- These systems aim to expose intermediate evidence (criterion-level traces) for inspection, supporting auditability
- CultureDx's contribution is the **empirical decomposition of accuracy versus audit properties** under cross-dataset distribution shift, NOT a claim of being the first or best multi-agent psychiatric diagnosis system
- Audit-oriented multi-agent architecture is complementary to, not strictly superior to, supervised baselines on Top-1

**Allowed wording**: "multi-agent diagnostic reasoning", "modular audit pipeline", "criterion-level trace", "audit-oriented architecture".

**Forbidden**: "first multi-agent psychiatric diagnosis system" (without literature audit), "clinically faithful reasoning", "MAS proves interpretability".

**Estimated length**: 100-130 words.

---

### §2.4 — Classical baselines, TF-IDF, and hybrid systems

**Purpose**: Frame TF-IDF respectfully and motivate §1 Contribution 1 parity claim. CRITICAL — this section is the one most likely to be misread as dismissive of supervised baselines if mishandled.

**Source**: Bucket 5 (classical supervised baselines in clinical NLP). **Literature audit required.**

**Locked claims**:
- Classical lexical / supervised baselines (character n-gram TF-IDF, simple bag-of-words, logistic regression) remain remarkably competitive on synthetic clinical-NLP benchmarks
- This includes the original LingxiDiag report's TF-IDF baseline at Top-1 = 0.496, and our reproduced TF-IDF at 0.610 (§5.5)
- Hybrid supervised + MAS / supervised + LLM systems combine classical and learned features rather than replacing supervised feature extraction with LLMs
- CultureDx Stacker LGBM is a hybrid system whose 88.1% feature-importance share comes from the supervised TF-IDF block (§5.2); MAS retention is justified on audit grounds rather than Top-1 contribution

**Allowed wording**: "strong supervised baseline", "hybrid supervised + MAS stacker", "accuracy parity rather than superiority", "remarkably competitive lexical baseline".

**Forbidden**: "TF-IDF is weak", "LLM-only SOTA", "MAS beats TF-IDF", "supervised baselines fail", "classical baselines are insufficient".

**Estimated length**: 130-160 words. (Slightly longer because this is the highest-misread-risk subsection.)

**Anti-results-dump guardrail (round 52 Fix C)**: §2.4 prose should usually avoid CultureDx-specific result numbers (0.610, 0.612, 11.4pp, 11.9%, etc.). These are §1 ¶2 and §5.1 / §5.2 / §5.5 anchors; §2.4 motivates **why** strong supervised baselines and hybrid systems matter without recapping our own benchmark numbers. A short forward pointer ("we report this hybrid-system comparison in §5") is acceptable; a numerical recap is not.

---

### §2.5 — Diagnostic standards: ICD-10, DSM-5, and formal criteria

**Purpose**: Support §1 Contribution 4 + §5.4 dual-standard claims. Position DSM-5 v0 schema correctly as audit formalization, NOT clinical validation.

**Source**: Bucket 6 (ICD-10 / DSM-5 official descriptions, criteria-formalization literature). Mostly authoritative descriptions; some recent computational ontology work.

**Locked claims**:
- ICD-10 and DSM-5 are the two predominant diagnostic standards used in psychiatric clinical reasoning, with structural and criterion-level differences
- Computationally formalizing diagnostic criteria enables criterion-level audit; the **quality of formalization matters** — LLM-drafted formalization is a starting point, not a clinically validated artifact
- CultureDx's DSM-5 v0 schema is an LLM-drafted formalization (`dsm5_criteria.json`, version `0.1-DRAFT`, source-note `UNVERIFIED`) used as experimental audit formalization
- Both mode treats DSM-5 reasoning as **sidecar audit evidence on the ICD-10 primary output**, NOT as a dual-standard ensemble

**Allowed wording**: "standard-specific reasoning", "criteria formalization", "experimental DSM-5 v0 audit formalization", "sidecar audit evidence", "ICD-10 primary output with DSM-5 sidecar audit".

**Forbidden**: "DSM-5 clinical diagnosis", "DSM-5 superiority", "DSM-5 improves robustness", "dual-standard ensemble", "clinically validated DSM-5".

**Estimated length**: 110-140 words.

---

### §2.6 — AIDA-Path and external criteria formalization

**Purpose**: Position AIDA-Path correctly. CRITICAL because §1 ¶5 + §7.8 commit to AIDA-Path / clinician review as **pending future work**; §2.6 must NOT contradict that by implying overlap analysis or validation has happened.

**Source**: Bucket 7 (AIDA-Path paper / npj Digital Medicine paper).

**Locked claims** (TWO modes — depends on whether overlap analysis is completed by submission time):

**Mode A — overlap analysis NOT completed before submission** (default current state per §7.8 "planned but not yet completed"):
- AIDA-Path is a relevant external structural anchor for psychiatric criteria formalization
- Structural alignment between CultureDx's DSM-5 v0 schema and AIDA-Path is **planned but not yet completed**
- We do not present any AIDA-Path overlap result as part of the present paper's evidence (consistent with §7.8 line 28)

**Mode B — overlap analysis IS completed before submission** (conditional; only if §7.8 changes):
- AIDA-Path provides external criteria-formalization reference; we present a **scoped external structural-alignment result** (location TBD if this mode is triggered)
- Result is a structural overlap measurement, not clinical validation of either schema

**Default writing assumption**: Mode A (pending). Switch to Mode B requires §7.8 update FIRST. Do NOT pre-emptively write Mode B prose.

**Allowed wording**: "pending structural alignment", "external criteria-formalization reference", "planned AIDA-Path overlap analysis", "complementary to".

**Forbidden**: "AIDA-Path validated CultureDx", "AIDA-Path integration completed" (Mode A), "clinician-reviewed DSM-5 criteria".

**Estimated length**: 80-110 words (Mode A; shorter because pending statement is brief).

---

## ITEM 5 — Cross-section consistency map

For every §2 positioning claim, the corresponding §1-§7 anchor that it must support without contradicting:

| §2 subsection | §1-§7 anchor | Status |
|---|---|---|
| §2.1 Chinese psychiatric NLP / LingxiDiag-style benchmarks | §1 ¶1 (Chinese psychiatric differential diagnosis); §3.1 (task definition); §3.2.1 LingxiDiag-16K | ✓ |
| §2.1 synthetic-data caveat | §1 ¶5 scope statement; §3.2.2 (MDD-5k synthetic); §7.1 (synthetic-only) | ✓ |
| §2.2 LLM diagnostic reasoning + caution | §1 ¶2 (Top-1 alone insufficient); §7.2 (DSM-5 v0 unverified) | ✓ |
| §2.3 MAS architecture as one of several approaches | §1 ¶3 (HiED + hybrid stacker); §4.1 (MAS architecture); §1 Contribution 3 (model-discordance) | ✓ |
| §2.3 audit-oriented framing not "first MAS" | §1 ¶5 (scope statement); §1 Contribution 4 (sidecar audit) | ✓ |
| §2.4 strong TF-IDF, hybrid stacker | §1 ¶2 (TF-IDF strong); §1 Contribution 1 (parity); §4.2 (5 systems); §5.1 (Top-1 = 0.610 vs 0.612); §5.2 (88.1% feature share); §5.5 (reproduction gap) | ✓ |
| §2.4 MAS share modest, value elsewhere | §1 ¶2 (11.9% MAS share); §1 ¶3 (system properties not captured by Top-1) | ✓ |
| §2.5 ICD-10 vs DSM-5 standards differ | §1 Contribution 4 (dual-standard); §4.3 (3 modes); §5.4 (dual-standard analysis) | ✓ |
| §2.5 DSM-5 v0 audit formalization NOT clinical | §1 Contribution 5 (LLM-drafted unverified); §4.3 (`dsm5_criteria.json` v0); §7.2 (DSM-5 v0 unverified) | ✓ |
| §2.5 Both mode = sidecar, not ensemble | §1 Contribution 4 (ICD-10 primary + DSM-5 sidecar); §4.3 (Both = pass-through); §5.4 (1000/1000, 925/925, 0/15) | ✓ |
| §2.6 AIDA-Path pending | §1 ¶5 (AIDA-Path pending future work); §7.8 (planned but not yet completed) | ✓ |
| §2.6 No AIDA-Path validation result claimed | §7.8 line 28 ("we do not present any AIDA-Path overlap result") | ✓ |

✅ All 12 §2 positioning claims trace to committed §1-§7 prose. **No new §2 claim that doesn't exist downstream or upstream.**

---

## ITEM 6 — Reviewer attack matrix

5 attacks anticipated for §2 Related Work:

### Attack 1 — "You missed citing prior work X on multi-agent psychiatric diagnosis"

> Response: §2.3 cites Bucket 4 (multi-agent / agentic clinical reasoning literature) without claiming exhaustive coverage. We frame CultureDx as **one of several modular approaches** rather than the first or best, and we welcome reviewer pointers to additional prior work for inclusion. We do NOT claim "first multi-agent psychiatric diagnosis system" anywhere; if the reviewer suggests a specific missing citation, we incorporate it without changing the positioning claim.

### Attack 2 — "Your TF-IDF framing dismisses classical NLP unfairly"

> Response: §2.4 explicitly frames TF-IDF as "strong supervised baseline" and "remarkably competitive lexical baseline"; the §1 Contribution 1 parity claim (Top-1 = 0.612 vs 0.610) and §5.5 reproduction gap disclosure (0.610 vs 0.496 published) reinforce this. CultureDx's primary system is a **hybrid supervised + MAS stacker** with 88.1% feature-importance share from the supervised TF-IDF block (§5.2); we do not dismiss TF-IDF, we build on it.

### Attack 3 — "DSM-5 v0 not validated — why include it at all?"

> Response: §2.5 + §1 Contribution 4 + §7.2 are explicit that DSM-5 v0 is an LLM-drafted formalization (`dsm5_criteria.json`, version `0.1-DRAFT`, source-note `UNVERIFIED`) used as **experimental audit formalization, not clinical validation**.
> Including it provides a controlled comparison point for §5.4 dual-standard analysis and §6.2 standard-discordance triage; the metric-specific trade-offs and 7.24× DSM-5 asymmetry on MDD-5k are scoped findings, not DSM-5 superiority claims.
> The §7.2 limitation explicitly acknowledges this scope.

### Attack 4 — "What is AIDA-Path's role here?"

> Response: §2.6 positions AIDA-Path as a **pending external structural anchor**, not a present-paper validation. §1 ¶5 + §7.8 commit AIDA-Path overlap analysis to future work. We do NOT claim AIDA-Path validates CultureDx, and we do NOT present any AIDA-Path overlap result. If overlap analysis completes before submission, §2.6 + §7.8 will switch to a scoped external structural-alignment result framing.

### Attack 5 — "Your Related Work is too thin / too thick"

> Response: §2 targets ~600-900 words across 6 subsections, with citation density ≈ 1 per 50-80 words (lesson 50a).
> This is intentionally compact: §2 supports §1's positioning, not a comprehensive psychiatric NLP literature survey.
> If a reviewer requests a longer Related Work, we extend specific subsections (most likely §2.4 or §2.5) rather than padding generally.
> If a reviewer requests trimming, we compress §2.1 / §2.6 first because those are the lowest-density positioning blocks.

---

## ITEM 7 — Prose plan (NO PROSE)

When §2 prose is authorized (post-round-52), suggested structure:

| Subsection | Estimated words | Citation count target |
|---|---:|---:|
| §2.1 Chinese psychiatric NLP / LingxiDiag-style benchmarks | 100-130 | 2-3 |
| §2.2 LLMs for psychiatric / clinical diagnosis | 100-130 | 2-3 |
| §2.3 Multi-agent diagnostic systems and auditability | 100-130 | 2-3 |
| §2.4 Classical baselines, TF-IDF, and hybrid systems | 130-160 | 2-3 |
| §2.5 Diagnostic standards: ICD-10, DSM-5, and formal criteria | 110-140 | 2-3 |
| §2.6 AIDA-Path and external criteria formalization | 80-110 | 1-2 |

**Total estimate**: ~620-800 words; ~11-17 citations across §2.

**Density check** (lesson 50a applied proactively): 11 citations ÷ 620 words = 1 per 56 words ✓; 17 citations ÷ 800 words = 1 per 47 words (slightly above density target of 50-80 — would need consolidation if upper-bound triggers). Target ranges set accordingly.

**Format discipline (lesson 33a)**: Sentence-level line breaks from initial draft. Not as post-hoc cleanup.

**Lesson 40a explicit (CRITICAL for §2)**: literature audit required for buckets 3, 4, 5 BEFORE prose drafting. Do NOT hallucinate paper titles, authors, or claims.

**Lesson 43a explicit**: at §2 prose v1 delivery, run cross-section forbidden grep against §1 + §2 + §3 + §4 + §5 + §6 + §7 simultaneously (now 12 prose files including §2).

**Lesson 44a explicit**: any factual nuance surfaced during literature audit that doesn't fit a primary structure slot must be captured here as a one-line trap or note before §2 prose drafting.

**Lesson 50a explicit (NEW from round 50)**: §2 prose targets 1 citation per ~50-80 words; 11-17 citations across 620-800 words. Resist the urge to add citations to demonstrate literature breadth — citations should support positioning claims, not exhaust the field.

---

## ITEM 8 — Round 52 narrow review request (per GPT round 51 spec)

```
§2 prep committed at <hash>.

Round 52 narrow review:
1. Does §2 support the Introduction story without adding new claims?
2. Are TF-IDF / classical baselines framed respectfully enough?
3. Is MAS positioned as audit-oriented rather than accuracy-dominant?
4. Is AIDA-Path positioned correctly as pending or scoped structural alignment?
5. Can we start §2 prose?
```

If 5/5 pass → §2 prose v1 authorized, conditional on completing literature audit for buckets 3, 4, 5 BEFORE drafting.

---

## ITEM 9 — Pre-prose literature audit checklist (lesson 40a + 50a application)

Before §2 prose drafting authorization, the following literature audit must complete (this is the §2 analogue of lesson 40a's "grep-before-placement" requirement):

### Bucket 3 — Psychiatric LLM diagnosis / clinical LLM caution

**Search target**: 2-3 representative recent (2022-2026) papers covering LLMs for psychiatric or clinical diagnosis, including at least one paper that documents LLM limitations / hallucination / overconfidence in clinical settings.

### Bucket 4 — Multi-agent / agentic clinical reasoning

**Search target**: 2-3 representative recent papers on multi-agent or modular clinical reasoning systems, especially those that decompose reasoning into criterion / logic / calibration stages or expose intermediate audit traces.

### Bucket 5 — Classical supervised baselines / TF-IDF in clinical NLP

**Search target**: 2-3 representative papers documenting TF-IDF or classical lexical baseline strength in clinical NLP, especially those reporting comparisons to LLM or transformer baselines.

### Buckets 1, 2, 7

LingxiDiag and MDD-5k papers and AIDA-Path paper are known references; verify exact citation strings during prose drafting.

### Bucket 6

ICD-10 and DSM-5 official descriptions are authoritative references; recent computational criteria-formalization literature optional but useful.

### Bucket 8

Tools (Qwen, vLLM, BGE-M3, LightGBM) cited only if §2 references them in positioning context; otherwise deferred to §4 Methods.

**This audit is the prerequisite for §2 prose drafting**. Without it, §2 prose risks hallucinating citations or misrepresenting bucket claims.

---

## Lesson application during this prep

| Lesson | Application |
|---|---|
| 21a | All 8 source buckets listed with role + existing repo-marker mapping (Item 2); §2 has the most explicit source-bucket structure of any prep so far because §2 sources are external |
| 25a-d | Repo-internal references to §1-§7 verified at HEAD `2c1bf73` (Item 5) |
| 31a | Cross-section consistency map (Item 5) — 12 §2 positioning claims traced to §1-§7 anchors |
| 33a | Sentence-level breaks throughout this prep |
| 36a (escalation) | Forbidden list (Item 3) has 16+ patterns vs §1 prep's 18 — Related Work also faces high overclaim risk but on different vectors ("first / SOTA / dismiss" rather than "MAS beats / clinical / DSM-5 superior") |
| 38b | Scope-limited claims throughout: "complementary to" / "differs from prior work in scope X" / "extends prior work along dimension Y" |
| 40a (CRITICAL for §2) | Item 9 literature audit checklist prerequisite to prose drafting; §2 buckets 3, 4, 5 require external citation verification not repo grep |
| 42a | "deployment" only in negation/forbidden lists |
| 42b | Paper register: "to our knowledge" only with literature support; "pending clinical validation" / "pending structural alignment" |
| 43a | Cross-section forbidden grep planned for §2 prose vs all 12 prose files (Item 7) |
| 44a | Drafting-context observations explicitly captured (Item 9 audit prerequisite); Item 6 attack 5 acknowledges length flexibility based on reviewer feedback |
| **50a (NEW from round 50)** | Citation-density target ≈ 1 per 50-80 words; §2 prose plan budgets 11-17 citations across 620-800 words; explicit anti-pattern: "do not add citations to demonstrate literature breadth — citations should support positioning claims, not exhaust the field" |

§2 prep inherits all 35 cumulative lessons. **Lesson 50a applied proactively** for the first time (rather than retroactively as in §1).

---

## Sequential discipline status

```
✓ §3 + §4 closed (972f689)
✓ §5 + §6 + §7 closed
✓ §1 closed (2c1bf73)
✓ Phase 2 Step 1 closed (integration review)
✓ Phase 2 Step 2 closed (§3+§4)
✓ Phase 2 Step 3 closed (§1)
□ Phase 2 Step 4: §2 Related Work prep ← awaiting your push
□ Round 52 narrow review (5 questions)
□ Bucket 3, 4, 5 literature audit (prerequisite to §2 prose)
□ §2 prose v1 ← if 5/5 pass + literature audit complete
□ Phase 2 Step 5: AIDA-Path slotting decision
□ Phase 2 Step 6: PI / advisor review
```

§2 is the LAST major section prep. After §2 closes, only AIDA-Path slotting + PI review + Abstract + citation pass remain before submission package.

---

## Estimated convergence trajectory

§2 Related Work has **moderate-to-high overclaim risk** — Related Work sections are where reviewers expect to see their own work cited, and where "first / novel / SOTA" framings creep in. But the locked thesis sentence + 6-subsection structure + literature audit prerequisite should keep the arc compact.

Convergence estimate: 4-6 review rounds.

- Round 52: prep narrow review (this submission)
- Round 53: prep polish (literature audit may flag missing buckets / wording adjustments)
- Round 54-55: §2 prose v1 + revision
- Round 56: §2 closed; transition to Phase 2 Step 5 (AIDA-Path slotting decision)

This trajectory is comparable to §1 (2 commits / 4 rounds) given mature lessons stack, BUT extended by 1-2 rounds because of the literature audit prerequisite.
