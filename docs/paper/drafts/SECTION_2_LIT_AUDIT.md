# Section 2 Literature Audit

**Date**: 2026-04-28
**Per GPT round 54**: Literature audit complete for §2 buckets 3, 4, 5. AIDA-Path naming verified for bucket 7. Citation source map below; §2 prose authorized after this commits.

This file is the citation source-of-truth for §2 Related Work prose. Each bucket lists the recommended primary citations, optional citations, and a "use for §2 prose" framing line that captures the locked positioning claim. **Citations not on this list should not be added to §2 prose without a follow-up audit.**

---

## Bucket 3 — Psychiatric / clinical LLM caution

Supports §2.2 (LLMs for psychiatric / clinical diagnosis).

### 3.1 Chen et al., 2026, *Nature Medicine*

LLM-assisted systematic review of large language models in clinical medicine. Covers 2022-2025 peer-reviewed clinical LLM studies (4,609 papers); only 1,048 use real-world patient data, and only 19 are prospective randomized trials; most are simulated scenarios or exam-style tasks.

Use for §2 prose: "Recent systematic evidence suggests that clinical LLM evaluations remain dominated by simulated or exam-style tasks, with relatively few prospective trials."

Do NOT write: "clinical LLMs are validated enough for deployment."

### 3.2 Hager et al., 2024, *Nature Medicine*

Evaluation and mitigation of the limitations of large language models in clinical decision-making. Uses MIMIC-IV real patient cases in a simulated realistic clinical setting; identifies gaps in information gathering, guideline adherence, and workflow integration that exam-style benchmarks do not measure.

Use for §2 prose: "Medical LLM performance on controlled benchmarks does not remove the need to evaluate information gathering, guideline adherence, and workflow integration."

Do NOT write: "LLMs are unsafe in all clinical contexts."

### 3.3 Omar et al., 2024, *Frontiers in Psychiatry*

Applications of large language models in psychiatry: a systematic review. Searches PubMed / Embase / Web of Science / Scopus through March 2024; 16 included studies. Identifies use cases (clinical reasoning, education, social-media text) and limitations (complex cases, suicide-risk underestimation).

Use for §2 prose: "Psychiatry-specific reviews identify potential uses of LLMs in diagnostic support and education, while emphasizing limitations in complex cases and risk-sensitive settings."

Do NOT write: "psychiatric LLM diagnosis is clinically validated."

### Optional — Agrawal et al., 2025, *npj Digital Medicine*

"The evaluation illusion of large language models in medicine." Argues that benchmark choice, data, tasks, metrics, and translational impact can mislead; calls for rigorous, context-aware evaluations and transparency. Optional citation; useful in §2.2 or §7 if §2 citation density allows.

---

## Bucket 4 — Multi-agent / modular clinical reasoning

Supports §2.3 (Multi-agent diagnostic systems and auditability).

### 4.1 Tang et al., 2024, ACL Findings

MedAgents: Large Language Models as Collaborators for Zero-shot Medical Reasoning. LLM-based role-playing multi-disciplinary collaboration; multi-round discussion / consensus decision; pipeline includes gathering domain experts, individual analyses, summary report, discussion until consensus, final decision.

Use for §2 prose: "Recent LLM-agent work has explored role-specialized, multi-round collaboration for medical reasoning."

Do NOT write: "MedAgents proves clinical interpretability."

### 4.2 Kim et al., 2024, NeurIPS

MDAgents: An Adaptive Collaboration of LLMs for Medical Decision-Making. Adapts collaboration structure (solo / group) by task complexity; medical decision-making benchmark.

Use for §2 prose: "Other medical-agent frameworks adapt collaboration structure or team composition to task complexity; CultureDx instead uses fixed diagnostic-role modules to expose criterion-level audit traces."

Do NOT write: "CultureDx is the first multi-agent medical diagnosis system."

### 4.3 Chen et al., 2025, *npj Digital Medicine*

Enhancing diagnostic capability with multi-agents conversational large language models (MAC). MDT-discussion-inspired multi-agent framework; evaluated on 302 rare-disease cases against GPT-3.5 / GPT-4; improves diagnostic and test-suggestion performance over single models.

Use for §2 prose: "Multi-agent diagnostic systems have been explored in rare-disease and general medical diagnosis settings; CultureDx applies a modular agent design to Chinese psychiatric differential diagnosis."

Do NOT write: "multi-agent diagnosis is clinically validated."

### Optional — Liu et al., 2026, *Nature Health*

Multi-agent framework combining LLMs with medical flowcharts for self-triage. Recent and aligned with audit / triage framing, but self-triage scope differs from psychiatric differential diagnosis. Optional citation; omit if §2 citation density approaches the density-target ceiling.

---

## Bucket 5 — TF-IDF / classical clinical NLP baselines

Supports §2.4 (Classical baselines, TF-IDF, and hybrid systems).

### 5.1 PLOS One 2024 — common NLP techniques to codify clinical notes

Systematic evaluation of common NLP techniques (including TF-IDF vectorization) for clinical-note coding on a large clinical-note corpus.

Use for §2 prose: "Clinical-note classification work commonly evaluates TF-IDF or other lexical representations as reproducible baseline feature spaces."

Do NOT write: "TF-IDF is always competitive with deep models."

### 5.2 JMIR AI 2024 — nurse triage notes: BOW/TF-IDF LR vs Bio-Clinical-BERT

Direct comparison of Bio-Clinical-BERT and bag-of-words logistic regression with TF-IDF for predicting hospitalization from nurse triage notes; motivated by computational resources / system constraints.

Use for §2 prose: "Clinical NLP evaluations often compare BERT-style models with TF-IDF logistic-regression baselines because they represent different computational and interpretability trade-offs."

Do NOT write: "TF-IDF beats BERT generally."

### 5.3 Wang et al., 2019, *BMC Medical Informatics and Decision Making*

A clinical text classification paradigm using weak supervision and deep representation. General anchor for machine-learning approaches in clinical text classification; not TF-IDF-vs-BERT specifically, but provides historical context for classical supervised clinical NLP.

Use for §2 prose: "Machine-learning approaches have long been effective for extracting structured information from clinical narratives."

Do NOT write: "classical ML is sufficient for clinical diagnosis."

### Optional — MDPI Computers 2026 medical note classification comparative study

Reports logistic regression with strongest overall performance and notes that traditional ML remains robust, interpretable, and computationally efficient. Journal quality / recency considerations apply; optional supporting citation only.

---

## Bucket 7 — AIDA-Path

Supports §2.6 (AIDA-Path and external criteria formalization).

### 7.1 Strasser-Kirchweger et al., 2026, *npj Digital Medicine*, article 271

"Machine-actionable criteria chart the symptom space of mental disorders." Formalizes narrative DSM-5 criteria into machine-actionable symptom-space representations using a deterministic framework; analyzes explicit consensus criteria rather than inferring patterns from large corpora.

Citation discipline: cite the paper title / authors / venue as the primary reference. "AIDA-Path" is the associated code / data resource name (GitHub `raoul-k/AIDA-Path`); use "AIDA-Path" as a resource label only when supported by the paper or repository.

Use for §2 prose: "Strasser-Kirchweger et al. formalize narrative DSM-5 criteria into machine-actionable symptom-space representations; we treat this as relevant prior work and a pending external structural-alignment anchor, not as completed CultureDx validation."

Do NOT write: "AIDA-Path validated CultureDx."

---

## Buckets 1, 2, 6 — Existing references

| Bucket | Reference | Notes |
|---:|---|---|
| 1 | LingxiDiag paper | Existing reference; cited in §3.1 / §3.2.1 / §5.1 with `[CITE LingxiDiag paper]`; verify exact citation string at full-manuscript citation pass |
| 2 | MDD-5k paper | Existing reference; cited in §3.2.2 conceptually; add `[CITE MDD-5k paper]` marker at §2 prose drafting |
| 6 | ICD-10 / DSM-5 official descriptions | Authoritative references; recent computational criteria-formalization work optional (§2.5 may cite Bucket 7 here) |

---

## Citation budget (per §2 prep v1.1 + round 54 distribution)

| §2 subsection | Buckets | Citation count |
|---|---|---:|
| §2.1 Chinese psychiatric NLP / benchmarks | 1 + 2 | 2 |
| §2.2 Clinical / psychiatric LLM caution | 3.1 + 3.2 + 3.3 | 3 |
| §2.3 Multi-agent diagnostic systems | 4.1 + 4.2 + 4.3 | 3 |
| §2.4 Classical baselines / TF-IDF | 5.1 + 5.2 (+ 5.3 if needed) | 2-3 |
| §2.5 Standards / criteria formalization | 6 + 7.1 | 2 |
| §2.6 AIDA-Path | 7.1 | 1 |

**Total**: ~13 primary citations across §2 prose. At target 650-850 words this is 1 citation per 50-65 words — within lesson 50a target range (1 per 50-80 words).

Optional citations (Agrawal 2025, Liu 2026, MDPI 2026) NOT included in default budget; add only if §2 prose review explicitly requests broader literature coverage and citation density permits.

---

## Discipline notes for §2 prose drafting

Per round 54 explicit:
- §2 is NOT a survey; each subsection uses 2-3 citations to support positioning, not to map the field
- "Use for §2 prose" lines above are the locked phrasing direction; §2 prose may polish wording but must NOT amplify any "Do NOT write" pattern
- Citation density target: 1 citation per 50-80 words (lesson 50a)
- §2 prose target: 650-850 words across 6 subsections
- Cite primary papers; avoid citing optional / speculative sources unless review explicitly requests
- AIDA-Path naming: cite Strasser-Kirchweger et al. paper; use "AIDA-Path" as resource label only

This source map is the citation prerequisite for §2 prose. After this commits, §2 prose v1 is authorized.
