# Citation Pass Plan

**Date**: 2026-04-28
**Per GPT round 65**: Phase 2 Step 5b trigger — Citation pass plan only.
**Status**: Plan / ledger artifact only. No `[CITE *]` replacement, no bibliography file, no AIDA-Path slot decision, no Abstract drafting in this commit.

This file is a planning artifact at `docs/paper/integration/CITATION_PASS_PLAN.md`. The apply-pass that actually replaces `[CITE *]` markers in §1-§7 prose and adds bibliography is a SEPARATE later commit, after round 66 narrow review of this plan.

---

## 1. Current citation-placeholder inventory

Verified at HEAD `eea8cf1` using both detection methods (lesson 58a generalized to citations).

### 1.1 Method 1 — explicit `[CITE *]` markers

```bash
grep -RnoE "\[CITE [^]]+\]" docs/paper/drafts/SECTION_*.md
```

**19 occurrences across 4 files; 14 unique citation keys.**

| File | Line | Placeholder | Bucket |
|---|---:|---|:---:|
| SECTION_2.md | 8 | `[CITE LingxiDiag paper]` | A |
| SECTION_2.md | 8 | `[CITE MDD-5k paper]` | A |
| SECTION_2.md | 14 | `[CITE Chen 2026 Nat Med]` | C |
| SECTION_2.md | 15 | `[CITE Hager 2024 Nat Med]` | C |
| SECTION_2.md | 16 | `[CITE Omar 2024 Front Psychiatry]` | C |
| SECTION_2.md | 21 | `[CITE Tang 2024 ACL MedAgents]` | D |
| SECTION_2.md | 22 | `[CITE Kim 2024 NeurIPS MDAgents]` | D |
| SECTION_2.md | 23 | `[CITE Chen 2025 npj MAC]` | D |
| SECTION_2.md | 29 | `[CITE PLOS One 2024 clinical NLP coding]` | E |
| SECTION_2.md | 29 | `[CITE JMIR AI 2024 BOW vs Bio-Clinical-BERT]` | E |
| SECTION_2.md | 30 | `[CITE Wang 2019 BMC clinical text classification]` | E |
| SECTION_2.md | 36 | `[CITE WHO ICD-10]` | B |
| SECTION_2.md | 36 | `[CITE APA DSM-5]` | B |
| SECTION_2.md | 42 | `[CITE Strasser-Kirchweger 2026 npj Digital Medicine]` | B |
| SECTION_3.md | 7 | `[CITE LingxiDiag paper]` | A |
| SECTION_3.md | 23 | `[CITE LingxiDiag paper]` | A |
| SECTION_5_1.md | 3 | `[CITE LingxiDiag paper]` | A |
| SECTION_5_1.md | 11 | `[CITE LingxiDiag paper]` | A |
| SECTION_5_1.md | 12 | `[CITE LingxiDiag paper]` | A |

**Sections with NO `[CITE *]` markers at HEAD**: §1, §4, §5.2, §5.3, §5.4, §5.5, §5.6, §6, §7. Of these, several mention citation-bearing entities (ICD-10, DSM-5, AIDA-Path, Qwen3, vLLM, LightGBM, BGE-M3, McNemar test, bootstrap method) without inline citation. The under-citation gap is addressed in §2 of this plan.

### 1.2 Method 2 — structural sweep for unmarked external claims

```bash
grep -RniE "ICD-10|DSM-5|LingxiDiag|MDD-5k|AIDA-Path|Qwen|vLLM|LightGBM|BGE-M3|McNemar|bootstrap" docs/paper/drafts/SECTION_*.md
```

Reveals many mentions of citation-bearing entities in §1, §4, §5-§7 prose where no `[CITE *]` marker exists. These are not necessarily defects: some entities (e.g. ICD-10, DSM-5, LingxiDiag) are referenced repeatedly across the manuscript and the convention can be to cite at first mention only. The decision-point is whether each first-mention is in §2 (with citation) or in §1 / §4 / §5+ (currently uncited).

This question is addressed in §2 below.

---

## 2. Unmarked claims that need citations

The under-citation gap is concentrated in two patterns.

### 2.1 First-mention citations missing in §1 / §4 / §7

§1 mentions ICD-10, DSM-5, AIDA-Path, LingxiDiag-16K, MDD-5k before §2 introduces them with explicit `[CITE *]` markers. Convention varies by venue:

- **Convention X** — repeat first-mention citation in every section that uses the entity
- **Convention Y** — cite only at first manuscript-level mention in §2 (the literature-review locus); §1 / §4 / §5+ cite back via "(see §2)"-style references
- **Convention X-lite (default proposal, round 66)** — cite at the first manuscript-level mention of each external entity or literature-backed claim; do not repeat citations in later sections unless the later section makes a new claim

Default rules under Convention X-lite:
- Datasets / standards / major external methods first mentioned in §1 → cite in §1.
- Technical tools first described in Methods (§4) → cite in §4, not §1.
- §2 remains the literature-review locus, but is not the only place citations can appear.
- Do not repeat the same citation in every later section.

This is more reviewer-safe than Convention Y because clinical / digital-medicine reviewers who read §1 first will see external entities (LingxiDiag, ICD-10, DSM-5, AIDA-Path, clinical LLM caution literature) cited inline rather than awaiting §2.

### 2.2 Methods / tools NOT cited at all in §4

§4 mentions **Qwen3-32B-AWQ** (line 10), **vLLM** (line 10), **BGE-M3** (line 10), **LightGBM** (line 16), **McNemar** (lines 65-72), **bootstrap CI** (line 65). None has a `[CITE *]` marker.

For methods/tools, citation discipline depends on whether the venue treats software/library references as citations or footnote URLs:

- For Qwen3-32B-AWQ → cite Qwen3 paper / model card (Bucket F)
- For vLLM → cite Kwon et al. 2023 SOSP (Bucket F)
- For LightGBM → cite Ke et al. 2017 NeurIPS (Bucket F)
- For BGE-M3 → cite Chen et al. 2024 BAAI (Bucket F)
- For McNemar → optional; if cited, McNemar 1947 Psychometrika (Bucket F)
- For bootstrap CI → optional; if cited, Efron 1979 / Efron-Tibshirani 1993 (Bucket F)

This is the largest bloc of currently-missing citations. Apply pass should add `[CITE *]` markers AND verify external sources for each.

### 2.3 Statistical / methodological references in §4

§4 references "non-inferiority margin" (line 25, 65, 70) and the "post-v4 evaluation contract". The contract itself is internal (Box 1), but the non-inferiority methodology is from clinical-trials literature. If venue requires methodological citation:

- Optional: Schumi & Wittes 2011 Trials, "Through the looking glass: understanding non-inferiority"
- Optional: Piaggio et al. 2012 JAMA, "Reporting of Noninferiority and Equivalence Randomized Trials"

Default: do NOT add unless reviewer asks. CultureDx is not a clinical trial; "non-inferiority margin" is used here as benchmark parity discipline, not regulatory NI testing. Flagged for round 66 (Question 6).

---

## 3. Citation buckets

Per round 65 explicit, 6 buckets:

| Bucket | Theme | Where used in §1-§7 |
|:---:|---|---|
| **A** | Paper / dataset citations | §3 datasets, §5.1, §5.5 |
| **B** | Standards / formal criteria | §2.5 standards, §2.6 AIDA-Path, §3 task definition, §4 dual-standard infrastructure, §5.4 DSM-5 v0 audit, §7.2 DSM-5 limitations |
| **C** | Clinical / psychiatric LLM caution | §1 motivation, §2.2 clinical / psychiatric LLM caution, §7 deployment caveat |
| **D** | Multi-agent clinical reasoning | §2.3 multi-agent diagnostic reasoning, §4.1 MAS architecture background |
| **E** | Classical clinical NLP / TF-IDF baselines | §2.4 classical baselines, §5.1 / §5.5 strong reproduced TF-IDF framing |
| **F** | Methods / tools | §4.1 backbone / inference, §4.2 stacker, §4.5 statistical analysis, §5.1 non-inferiority / paired comparison, §5.3 bootstrap CI, §6 disagreement-vs-confidence bootstrap |

### 3.1 Bucket A — Paper / dataset

**Allowed claims**: dataset provenance, published baseline numbers, in-domain / external distribution-shift framing.

**Forbidden claims**: clinical validation of these datasets (they are synthetic / curated); MDD-5k as cross-lingual evaluation (it is Chinese-only); E-DAIC as an evaluated dataset (round 65 explicit: "if mentioned as unused" — §3.5 explicitly says we do NOT evaluate on E-DAIC).

### 3.2 Bucket B — Standards / formal criteria

**Allowed claims**: ICD-10 standard definition, DSM-5 standard definition, AIDA-Path as published paper (Strasser-Kirchweger et al. 2026 npj Digital Medicine), AIDA-Path as code/data resource, AIDA-Path as external structural-alignment anchor (pending future overlap analysis).

**Forbidden claims**: AIDA-Path validated CultureDx; AIDA-Path integration completed; DSM-5 criteria are clinician-reviewed; CultureDx implements AIDA-Path methodology.

The AIDA-Path special handling is in §5 of this plan.

### 3.3 Bucket C — Clinical / psychiatric LLM caution

**Allowed claims**: clinical LLM evaluations remain heavily benchmark / simulated / retrospective; psychiatric LLMs have potential but require caution and validation; CultureDx is benchmark-only and does not claim clinical readiness.

**Forbidden claims**: clinical LLMs are validated for deployment; psychiatric LLM diagnosis is clinically validated; CultureDx is ready for clinical use; LLMs are SOTA in clinical reasoning; LLMs replace clinicians.

### 3.4 Bucket D — Multi-agent clinical reasoning

**Allowed claims**: multi-agent and modular systems have been explored for structuring medical reasoning; CultureDx belongs to this family but focuses on Chinese psychiatric benchmark diagnosis and audit traces; multi-agent reasoning is one of several architectural approaches.

**Forbidden claims**: CultureDx is the first multi-agent psychiatric diagnosis system; MAS proves interpretability; multi-agent diagnosis is clinically validated; multi-agent systems outperform single-LLM baselines in general.

### 3.5 Bucket E — Classical clinical NLP / TF-IDF baselines

**Allowed claims**: TF-IDF / lexical / supervised baselines remain serious comparators in clinical NLP; CultureDx compares against a strong reproduced TF-IDF baseline; supervised stackers can match or exceed LLM-only systems on benchmark Top-1.

**Forbidden claims**: TF-IDF is weak; TF-IDF generally beats BERT; classical ML is sufficient for clinical diagnosis; classical baselines are insufficient.

### 3.6 Bucket F — Methods / tools

**Allowed claims**: Qwen3 as inference backbone; vLLM as serving infrastructure; LightGBM as stacker; BGE-M3 as retrieval utility (broader system, not a benchmark contributor); McNemar as paired-discordance test; bootstrap CI as resampling-based confidence interval.

**Forbidden claims**: BGE-M3 drives benchmark performance (round 65 explicit); retrieval improves CultureDx results; Qwen3 enables MAS interpretability; vLLM is a CultureDx contribution; bootstrap CI implies clinical equivalence.

---

## 4. Source-of-truth mapping

Each `[CITE *]` placeholder mapped to an external source candidate. **All entries marked `[CITE — verify]` until a citation apply-pass round confirms title / venue / DOI / arXiv ID.**

Status legend:
- **verified** — DOI / arXiv / venue / year confirmed via direct artifact check (not training-data recall)
- **needs DOI verification** — DOI candidate identified; needs direct fetch confirmation
- **needs arXiv verification** — arXiv preprint candidate identified; needs direct fetch confirmation
- **needs arXiv / venue verification** — multiple identifier types possible; needs source-class decision and verification
- **needs venue/proceedings verification** — paper exists but proceedings entry / archival link not confirmed
- **needs exact edition** — book or standards document with multiple revisions; needs edition decision
- **needs exact venue** — paper exists but venue/year specifics uncertain
- **needs source check** — placeholder name plausible but source identification unconfirmed
- **optional** — citation is recommended but not required for the manuscript claim
- **defer** — placeholder needs decision later, not now

Per round 66: if a source has only an arXiv / model-card / software-resource identifier and no DOI, record the appropriate identifier explicitly rather than inventing a DOI. The `verified` status applies once any single appropriate identifier is direct-fetch confirmed; DOI is not mandatory for arXiv-only papers, model cards, or software-resource entries.

| Placeholder | Section / Line | Claim supported | Bucket | Source candidate (unverified) | Status |
|---|---|---|:---:|---|:---:|
| `[CITE LingxiDiag paper]` | §2 L8, §3 L7, §3 L23, §5.1 L3, §5.1 L11, §5.1 L12 (×6) | dataset provenance + published TF-IDF / LLM baseline | A | LingxiDiag report (Chinese psychiatric clinical-dialogue benchmark); user has direct access to this artifact in the project. | needs DOI verification |
| `[CITE MDD-5k paper]` | §2 L8 | external synthetic distribution-shift dataset | A | MDD-5k paper / dataset release | needs source check |
| `[CITE WHO ICD-10]` | §2 L36 | ICD-10 international standard | B | World Health Organization (WHO), International Classification of Diseases, 10th revision (ICD-10) | verified (well-known standard); needs WHO catalog reference |
| `[CITE APA DSM-5]` | §2 L36 | DSM-5 / DSM-5-TR diagnostic standard | B | American Psychiatric Association, Diagnostic and Statistical Manual of Mental Disorders, Fifth Edition or DSM-5-TR | needs exact edition (DSM-5 vs DSM-5-TR) |
| `[CITE Strasser-Kirchweger 2026 npj Digital Medicine]` | §2 L42 | AIDA-Path symptom-space formalization | B | Strasser-Kirchweger et al., "Machine-actionable criteria chart the symptom space of mental disorders," npj Digital Medicine 9, Article 271, 2026 | DOI candidate `10.1038/s41746-026-02451-6` (round 66); needs DOI verification |
| `[CITE Chen 2026 Nat Med]` | §2 L14 | clinical LLM systematic review | C | Chen et al. 2026 Nature Medicine clinical LLM systematic review | needs DOI verification |
| `[CITE Hager 2024 Nat Med]` | §2 L15 | realistic clinical decision-making caution | C | Hager et al. 2024 Nature Medicine | needs DOI verification |
| `[CITE Omar 2024 Front Psychiatry]` | §2 L16 | psychiatry-specific LLM review | C | Omar et al. 2024 Frontiers in Psychiatry | needs DOI verification |
| `[CITE Tang 2024 ACL MedAgents]` | §2 L21 | multi-agent medical-reasoning approach | D | Tang et al. 2024 ACL MedAgents | needs DOI verification |
| `[CITE Kim 2024 NeurIPS MDAgents]` | §2 L22 | multi-agent medical-reasoning approach | D | Kim et al. 2024 NeurIPS MDAgents | needs DOI verification |
| `[CITE Chen 2025 npj MAC]` | §2 L23 | multi-agent clinical-reasoning approach | D | Chen et al. 2025 npj Digital Medicine MAC | needs DOI verification |
| `[CITE PLOS One 2024 clinical NLP coding]` | §2 L29 | classical clinical NLP / TF-IDF baseline | E | PLOS One 2024 clinical notes / TF-IDF | needs source check |
| `[CITE JMIR AI 2024 BOW vs Bio-Clinical-BERT]` | §2 L29 | BOW/TF-IDF competitiveness vs Bio-Clinical-BERT | E | JMIR AI 2024 nurse triage | needs source check |
| `[CITE Wang 2019 BMC clinical text classification]` | §2 L30 | clinical text classification baseline | E | Wang et al. 2019 BMC | needs DOI verification |

**Bucket F — additions proposed (currently NO `[CITE *]` markers in §4)**:

Round 66 source-metadata refinement: not all method/tool sources have DOIs. Some are arXiv preprints, software papers, or model cards. Apply-pass should NOT force DOI on every entry; record the appropriate identifier per source.

| Proposed marker | Section / Line | Claim supported | Source candidate | Identifier (round 66 candidates) | Status |
|---|---|---|---|---|:---:|
| `[CITE Qwen3]` | §4 L10, §5.3 L3, §5.3 L17 | Qwen3-32B-AWQ inference backbone | Qwen team, "Qwen3 Technical Report" (2025) | arXiv:2505.09388 (preprint); Hugging Face `Qwen/Qwen3-32B-AWQ` model card as resource | needs arXiv verification |
| `[CITE vLLM]` | §4 L10 | vLLM serving infrastructure | Kwon et al., "Efficient Memory Management for Large Language Model Serving with PagedAttention" | arXiv:2309.06180; SOSP 2023 venue if accessible | needs arXiv / venue verification |
| `[CITE LightGBM]` | §1 L16, §4 L16 | LightGBM stacker | Ke et al. 2017, "LightGBM: A Highly Efficient Gradient Boosting Decision Tree" | NeurIPS/NIPS 2017 proceedings; ACM archival link acceptable | needs venue/proceedings verification |
| `[CITE BGE-M3]` | §4 L10 | retrieval utility (broader system, not benchmark contributor) | Chen et al., "BGE M3-Embedding: Multi-Lingual, Multi-Functionality, Multi-Granularity Text Embeddings Through Self-Knowledge Distillation" | arXiv:2402.03216 | needs arXiv verification |
| `[CITE McNemar 1947]` | §4 L65, L66, L70-72 | paired-discordance test | McNemar 1947 Psychometrika, "Note on the sampling error of the difference between correlated proportions or percentages" | DOI candidate: `10.1007/BF02295996` | needs DOI verification |
| `[CITE Efron 1979]` | §4 L65, L68, L75; §5.3 L13, L22; §6 several | bootstrap resampling methodology | Efron 1979 Annals of Statistics, "Bootstrap Methods: Another Look at the Jackknife" | DOI candidate: `10.1214/aos/1176344552` | needs DOI verification |

Per round 66: if a source has only an arXiv / model-card / software-resource identifier and no DOI, record that explicitly rather than inventing a DOI.

**Caution**: All Bucket F entries above are proposed first-mention markers; the apply pass should NOT add markers to every subsequent mention. Citation density discipline applies (lesson 50a generalized to citations).

---

## 5. AIDA-Path special handling

Per round 65 explicit:
> "Is AIDA-Path cited as paper + resource without implying completed validation?"
> "Do not update §2 / §7 to completed validation unless Step 5c completes an actual overlap analysis."

### 5.1 Current paper state

AIDA-Path overlap analysis is **NOT completed**. The §2.6 prose at HEAD is:

> "Strasser-Kirchweger et al. formalize narrative DSM-5 criteria into machine-actionable symptom-space representations, providing a deterministic external criteria-formalization reference; the associated code and data resource is named AIDA-Path [CITE Strasser-Kirchweger 2026 npj Digital Medicine].
> We treat this as a relevant external structural anchor, but the present paper does not present any AIDA-Path overlap result as part of its evidence; structural alignment between the v0 DSM-5 schema and the AIDA-Path symptom-space representation is planned future work (§7.8)."

This wording is correct as-is and must be preserved. The citation pass should NOT modify §2.6 wording; it should only resolve the `[CITE Strasser-Kirchweger 2026 npj Digital Medicine]` marker to a verified bibliographic entry.

### 5.2 Allowed AIDA-Path-related wording (preserve at apply-pass)

```
✅ pending structural alignment
✅ external criteria-formalization anchor
✅ associated AIDA-Path code/resource
✅ planned future work
✅ external structural anchor (without claiming alignment is achieved)
```

### 5.3 Forbidden AIDA-Path-related wording (block at apply-pass)

```
❌ AIDA-Path validated CultureDx
❌ AIDA-Path integration completed
❌ clinician-reviewed DSM-5 criteria
❌ CultureDx implements AIDA-Path methodology
❌ overlap analysis completed
❌ AIDA-Path supports CultureDx claims
```

Cumulative forbidden patterns from rounds 1-65 already include "AIDA-Path validation completed" and "AIDA-Path integration completed". Citation pass apply must run cross-section forbidden grep on these patterns post-edit.

### 5.4 Bibliographic entry style

Per round 66: paper mandatory; resource optional.

**Mandatory bibliography entry**:
Strasser-Kirchweger et al., "Machine-actionable criteria chart the symptom space of mental disorders," npj Digital Medicine 9, Article 271, 2026 (DOI candidate `10.1038/s41746-026-02451-6`, needs DOI verification).
This is used for the Bucket B citation in §2.6 and §7.8.

**Optional resource entry**:
AIDA-Path / `raoul-k/AIDA-Path` repository.
Include this only if §2.6 or §7.8 prose explicitly references the code/data resource (rather than only the formal paper).
At HEAD `eea8cf1`, §2.6 prose says "the associated code and data resource is named AIDA-Path" — this is a name-level mention, not a citation-level dependency on the resource.
Apply-pass default: paper-only entry unless reviewer or revision explicitly adds a code/resource citation.

Note: the formal paper title is "Machine-actionable criteria chart the symptom space of mental disorders"; "AIDA-Path" is the name of the associated code/data resource, NOT the paper title. Apply-pass must not conflate these.

---

## 6. Methods/tool citation mapping

| Tool / method | First mention | Proposed marker | Citation discipline |
|---|---|---|---|
| Qwen3-32B-AWQ | §4 L10 | `[CITE Qwen3]` | First mention only; subsequent mentions in §5.3 / §5.4 reference back without re-citing |
| vLLM | §4 L10 | `[CITE vLLM]` | First mention only |
| BGE-M3 | §4 L10 | `[CITE BGE-M3]` | First mention only; explicit no-benchmark-contribution caveat preserved per round 65 |
| LightGBM | §1 L16 OR §4 L16 | `[CITE LightGBM]` | First-mention venue decision (§1 vs §4) flagged for round 66 |
| McNemar | §4 L65 | `[CITE McNemar 1947]` | OPTIONAL per round 65; default propose YES (one citation, methods context) |
| Bootstrap | §4 L65 | `[CITE Efron 1979]` OR `[CITE Efron-Tibshirani 1993]` | OPTIONAL per round 65; default propose YES (one citation, methods context) |

**Default citation density target**: 1 first-mention citation per tool. Subsequent mentions reference back without citation. This matches lesson 50a generalized to citations: avoid over-citation.

---

## 7. Citation replacement apply-pass plan

This section is the SCOPE for the future apply-pass commit, NOT executed in this plan.

### 7.1 Apply-pass scope (when triggered)

1. Resolve every `[CITE *]` placeholder in §1-§7 prose to a verified bibliography reference, OR keep `[CITE — verify]` for unverified entries (NEVER hallucinate DOI / venue).
2. Add `[CITE *]` markers for §4 methods/tools per §6 of this plan.
3. Apply Convention X-lite (per §2.1, default after round 66): cite at the first manuscript-level mention of each entity / literature-backed claim; do not repeat citations in later sections unless the later section makes a new claim. Datasets / standards / major external methods cited in §1 if first mentioned there; technical tools cited in §4 methods.
4. Build new bibliography artifacts:
   - `docs/paper/references/CITATION_LEDGER.md` — human-readable per-marker source mapping
   - `docs/paper/references/references.bib` — BibTeX file for venue submission
5. Re-run cross-section forbidden grep on AIDA-Path / clinical-validation / DSM-5-superiority drift patterns (lesson 43a).
6. Confirm citation count and check for duplicate references.
7. Verify no `[CITE *]` placeholder remains unresolved at commit time. Each placeholder is either resolved to a real bib entry, or kept as `[CITE — verify]` with explicit rationale in CITATION_LEDGER.md.

### 7.2 New artifacts (separate apply-pass commit)

- `docs/paper/references/CITATION_LEDGER.md` — per-marker source mapping with verification status
- `docs/paper/references/references.bib` — BibTeX
- Modified `docs/paper/drafts/SECTION_1.md` to `SECTION_7.md` with placeholder replacements

### 7.3 NOT in apply-pass scope

- Abstract drafting (Step 5f, deferred)
- AIDA-Path slot decision (Step 5c, deferred — round 65 explicit)
- Reproduction README (Step 5e, deferred)
- New experimental analyses
- §1-§7 wording / structural changes beyond placeholder replacement
- PI / advisor review (Step 6, deferred)

### 7.4 Deferred decisions (round 66 will adjudicate)

- First-mention convention (X vs Y) — affects how many sections add citations
- Methods/tool citation count — McNemar, bootstrap, non-inferiority methodology cites are optional
- AIDA-Path resource entry (paper-only vs paper + GitHub resource)
- Whether to add inline citations to §1 / §4 / §7 (currently 0 markers there) or rely on §2 / §3 / §5.1 carrying central citations

---

## 8. External source verification rules

Citation pass apply must NOT use training-data recall as the source of truth. Each external source requires direct artifact verification.

### 8.1 Required fields per citation

For every external source, the citation entry must specify:

```
Author / organization
Year
Title
Venue or publisher
DOI / URL / arXiv / PubMed if available
Which claim it supports (manuscript section + line)
```

### 8.2 If verification fails at apply-pass time

Mark as `[CITE — verify]` rather than fabricating a citation. The marker stays in the manuscript until source is verified out-of-band.

This is lesson 21a applied to citation pass. Hallucinated citations (correct-looking author + venue + year + DOI but actually different paper) are a known LLM failure mode and are an absolute red line.

### 8.3 Allowed verification methods

- Direct fetch of paper landing page (DOI link, journal website, arXiv abstract page)
- Direct fetch of dataset repository / GitHub / Zenodo
- Direct fetch of standard organization page (WHO ICD-10, APA DSM-5)
- Confirmation via known-canonical bibliography of an authoritative review (e.g. an explicit reference list in a verified survey paper that contains the candidate citation)

### 8.4 Forbidden verification methods

- Memorized recall ("I know Hager et al. 2024 is in Nature Medicine because that's a famous paper")
- Inference from title / topic plausibility ("this title sounds like it would be in NeurIPS")
- Reverse-search against a fragment without confirming the full bibliographic record
- Generated DOI / URL that fits the format but is not actually the paper

---

## 9. Forbidden citation drift

Per round 65 explicit:

```
❌ Citing review papers as if they directly validate CultureDx
❌ Citing AIDA-Path as completed CultureDx validation
❌ Citing clinical LLM papers as evidence of clinical deployment readiness
❌ Citing MedAgents / MDAgents as proof CultureDx is first
❌ Citing TF-IDF papers as proof TF-IDF generally beats deep models
❌ Filling Table 2 published-baseline cells from citation prose instead of direct table source
❌ Replacing uncertainty with invented DOI / venue metadata
```

Allowed citation framings:

```
✅ "supports background motivation"
✅ "provides methodological precedent"
✅ "is used as an external structural anchor"
✅ "is cited for dataset provenance"
✅ "is cited for official diagnostic standard definition"
✅ "is one of several modular approaches"
✅ "documents a published baseline"
```

### 9.1 Cross-section forbidden grep (post-apply-pass)

After the citation apply-pass commit lands, run lesson 43a sweep for:

- "AIDA-Path validated" / "AIDA-Path integration completed" → 0 hits in §1-§7 prose
- "clinically validated" without negation → 0 positive hits
- "DSM-5 superiority" / "DSM-5 generalizes" → 0 hits
- "first multi-agent" → 0 hits
- "deployment-ready" without negation → 0 positive hits
- "clinician-reviewed criteria" → 0 hits

These are the cumulative forbidden patterns from rounds 1-65 still in force.

### 9.2 NEW forbidden patterns introduced in this plan

```
❌ Resolving [CITE *] to fabricated DOI / arXiv ID
❌ Citing a different paper than the one named in the placeholder ("plausible-substitute" hallucination)
❌ Adding citations to §1 / §4 / §7 without verifying the cited entity is the same as in §2 first-mention
❌ Promoting "needs source check" entries to "verified" without out-of-band verification
❌ Citing methods/tools without confirming the referenced paper actually introduces that method
❌ Filling Table 2 published-baseline cells from citation prose
❌ Delta-inferring Table 2 cells during citation replacement
```

These extend the cumulative forbidden list to citation-pass-specific concerns.

### 9.3 Table 2 protection rule (round 66 explicit operational rule)

Citation pass may verify published LingxiDiag bibliographic metadata, but may not populate missing Table 2 published-baseline metric cells unless the original paper table is directly inspected and the metric value is directly reported.

No delta-inferred values during citation replacement.

This prevents citation pass from accidentally becoming another metric table apply-pass.

Specifically, the apply-pass must NOT:
- Use citation context to fill cells in Table 2's "Published TF-IDF" or "Published best LLM" rows beyond what is already populated at HEAD `eea8cf1`.
- Reverse-engineer published comparator values from §5.1 prose deltas (e.g. "+12.5pp on Top-1" → 0.487 inferred).
- Treat citation replacement as license to update table values.

---

## 10. Round 66 review request

Six narrow questions:

1. Are all 19 existing `[CITE *]` occurrences accounted for? Inventory: 19 existing occurrences across 4 files / 14 unique existing citation keys / 6 proposed Bucket F method/tool keys / 20 total unique keys after proposed method/tool additions. Are they assigned to the right buckets (A/B/C/D/E/F)?
2. Confirm Convention X-lite as the citation policy: cite at first manuscript-level mention (§1 / §4 / §7 add citations where they introduce a new entity or claim; §2 remains literature-review locus but not exclusive). Are there any sections where Convention X (repeat-citation in every section) is preferred over X-lite?
3. Are the proposed Bucket F methods/tool citations complete (Qwen3 / vLLM / LightGBM / BGE-M3) and correct? Should McNemar 1947 / Efron 1979 be added as well, or left as "optional"?
4. Should AIDA-Path bibliography include both the paper (Strasser-Kirchweger 2026) AND the resource entry (`raoul-k/AIDA-Path` GitHub), or only the paper?
5. Is the §5 AIDA-Path special handling (current wording preserved; no "validated" / "completed" claims; only `[CITE *]` resolution) correct? Is anything in current §2.6 / §7.8 prose at risk of drifting toward "completed validation" framing during citation replacement?
6. Are the §8 verification rules (required fields, fail-mode `[CITE — verify]` policy, forbidden verification methods) sufficient to prevent hallucinated citations?

Bonus question (optional):

7. Should I draft the apply-pass execution plan (which files touched, how `[CITE — verify]` markers handled) as a separate review item before the actual apply-pass, similar to the table-numbering plan-then-apply pattern from Step 5d?

---

## 11. Lesson application during this plan

| Lesson | Application |
|---|---|
| **21a (source verification)** | §8 explicitly forbids training-data recall as the source of truth; mandates direct artifact verification |
| 25a-d | §4 placeholder mapping ties each `[CITE *]` to specific section + line + claim |
| 31a | §3.6 BGE-M3 wording aligns with §4 prose ("retrieval utility, not a benchmark contributor"); §5.2 AIDA-Path wording aligns with §2.6 / §7.8 prose ("planned future work") |
| **33a** | All caption/source-mapping cells use sentence-level format; long lines avoided |
| 38b | All venue/convention/citation-density decisions framed as round-66 review questions, not unilateral commitments |
| 40a | Markers without verifiable source → `[CITE — verify]` rather than fabricated entries |
| 43a | §9.1 specifies post-apply-pass cross-section sweep on cumulative forbidden patterns |
| 44a | Round-65 nuances captured: AIDA-Path special handling (§5); Methods/tool optional citation policy (§6) |
| **50a** (extended) | Citation density target stated explicitly: 1 first-mention citation per entity; avoid over-citation |
| **58a** (extended) | Both-detection-method discipline applied to citations: explicit `[CITE *]` markers + structural sweep for unmarked claims |

No new lesson this round. Cumulative count remains **36 lessons**.

---

## 12. Sequential discipline status

```
✓ §1-§7 all closed (manuscript body complete)
✓ Phase 2 Step 5a: assembly review v1.1 (82bd2a4)
✓ Phase 2 Step 5d-plan: table numbering plan v1.2 (3bdc4af)
✓ Phase 2 Step 5d-apply: table-renumbering apply-pass v1.1 (eea8cf1)
✓ Phase 2 Step 5b-plan: this commit (citation pass plan)
□ Round 66 narrow review (6 questions)
□ Phase 2 Step 5b-apply: citation replacement + bibliography (separate commit)
□ Phase 2 Step 5c: AIDA-Path slot decision
□ Phase 2 Step 5e: reproduction README
□ Phase 2 Step 5f: Abstract drafting (LAST)
□ Phase 2 Step 6: PI / advisor review
```

Per round 65 explicit:
- Do NOT directly replace `[CITE *]` placeholders during this plan commit
- Do NOT build BibTeX file during this plan commit
- Do NOT do AIDA-Path slot decision (Step 5c, separate)
- Do NOT write Abstract (Step 5f, separate, LAST)
- Do NOT run new experiments

Citation replacement apply-pass is the next step after round 66 review of this plan.
