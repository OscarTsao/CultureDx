# CultureDx: Culture-Adaptive Diagnostic MAS with Evidence Grounding

**Date:** 2026-03-18
**Status:** Approved (Review Pass 2)
**Author:** YuNing + Claude

---

## 1. Core Thesis

Evidence-grounded MAS outperforms single LLMs for Chinese psychiatric diagnosis because:

1. LLMs have weak parametric knowledge of Chinese clinical presentations
2. Somatization requires explicit culture-aware symptom-to-criteria mapping that zero-shot cannot provide
3. Differential and comorbid diagnosis requires genuine agent asymmetry (expertise per disorder) that single models collapse

### Experimental Claims

1. HiED-MAS beats LingxiDiagBench baselines on 12-way differential (>28.5%) and comorbidity (>43%)
2. Evidence delta on Chinese datasets is significantly larger than on English datasets (cross-lingual evidence gap)
3. The system produces auditable, criterion-grounded diagnoses meeting regulatory transparency requirements

### MAS Modes (All Configurable)

| Mode | Key | Description |
|---|---|---|
| `hied` | Primary | Hierarchical triage + PsyCoT criterion checking + deterministic logic |
| `psycot` | Alt B | Flat criterion checkers across all disorders + logic engine |
| `specialist` | Alt A | Triage + free-form disorder specialists + LLM judge |
| `debate` | Alt C | Biopsychosocial perspective debate + consensus |
| `single` | Baseline | Single-model zero-shot with evidence variants |

---

## 2. Architecture — Culture-Aware Evidence Extractor

Shared foundation across all MAS modes.

```
Input Transcript (Chinese or English)
    |
    v
+-------------------------------------+
|  Culture-Aware Evidence Extractor   |
|                                     |
|  1. Language Detection & Routing    |
|     - Chinese -> CN pipeline        |
|     - English -> EN pipeline        |
|                                     |
|  2. Symptom Span Extraction         |
|     - LLM-based NER on turns        |
|     - Output: [(span, turn_id,      |
|       symptom_type)]                |
|                                     |
|  3. Somatization Mapper (CN only)   |
|     - Maps somatic complaints to    |
|       psychiatric criteria          |
|     - Uses symptom ontology +       |
|       LLM fallback                  |
|                                     |
|  4. Criteria Matcher                |
|     - Evidence retrieval per        |
|       ICD-10/DSM-5 criterion        |
|     - BGE-M3 or Qwen3-Embedding    |
|     - Optional: P3 GNN reranker     |
|                                     |
|  5. Evidence Brief Assembly         |
|     - Per-criterion evidence sets   |
|     - Confidence scores             |
|     - Source turn references        |
+-------------------------------------+
    |
    v
Evidence Brief (structured JSON per criterion per disorder)
```

### Key Design Decisions

- **Somatization Mapper** is the novel component. No off-the-shelf solution exists. Build a Chinese psychiatric symptom ontology from CCMD-3 + ICD-11 Chinese translation + CMeKG, with LLM fallback for unseen expressions. Tested as ablation (with/without mapper).
- **Retrieval is model-agnostic.** Start with BGE-M3 (proven in Chinese medical RAG). Sweep against Qwen3-Embedding and NV-Embed-v2 (English baseline).
- **P3 GNN reranker is optional.** Requires full retraining on Chinese data — the existing checkpoint is coupled to NV-Embed-v2 (4096-dim) and English RedSM5 corpus. Node features (embedding dim, reranker scores, rank stats) must be rebuilt for each retriever. This is a Phase 4 sub-task, not a simple port. If the ablation goal is 'does graph reranking help Chinese?', start with a simpler reranking baseline before investing in GNN retraining.
- **Evidence Brief format** is language-independent, enabling cross-lingual comparison.

Specific retriever candidates and their resource profiles:
- `BAAI/bge-m3` (570M params, 1024-dim, ~1.5GB) — proven in Chinese medical RAG
- `Qwen/Qwen3-Embedding-8B` (8B params, 4096-dim, ~5GB Q4) — SOTA multilingual
- `nvidia/NV-Embed-v2` (7.8B params, 4096-dim, ~5GB Q4) — English baseline from prior work

Note: P3 GNN input dimension must match the retriever's output dimension. Switching retrievers requires GNN retraining (see CRITICAL-1 fix).

---

## 3. Architecture — HiED-MAS (Primary Mode)

Hierarchical triage + PsyCoT criterion checking + deterministic logic engine.

### Stage 1: Triage Agent

- **Input:** Full evidence brief + transcript summary (first/last 3 turns)
- **Task:** Classify into 1-3 broad ICD-10 chapter F categories:
  - Mood (F30-F39)
  - Anxiety (F40-F42)
  - Stress-related (F43)
  - Somatoform (F45)
  - Psychotic (F20-F29)
  - Sleep (F51)
  - Other (F9x, Z71)
- **Output:** Ranked categories + confidence
- **Multi-label:** Yes (enables comorbidity path)
- **Model pool:** Mid-size (14B class)
- **Error mitigation:** Top-3 by default when top-1 confidence < 0.7
- **Output format:** JSON with ranked list of {category, logit, calibrated_probability}
- **Calibration:** Temperature scaling on validation set (fit T on val, apply at inference)
- **Cascading logic:** Activate all categories with calibrated_probability >= 0.2 OR top-3, whichever activates more. This over-activates specialists at compute cost but prevents cascade errors. The Logic Engine naturally filters false positives (unmet criteria -> no diagnosis).
- **Threshold tuning:** The 0.7 and 0.2 thresholds are hyperparameters tuned on the validation set via grid search over [0.3, 0.5, 0.7, 0.9] × [0.1, 0.2, 0.3]. Report sensitivity analysis.

### Stage 2: Criterion Checker Agents

One agent per candidate disorder, activated by triage.

- Receives ONLY its disorder's relevant evidence from the Evidence Brief
- Checks each criterion: `met` / `not_met` / `insufficient_evidence`
- Uses PsyCoT: explicit symptom-to-criterion chain of reasoning
- Cites source turns for each decision
- Model pool: small-mid (4B-14B class)

**Output per agent:**

```json
{
  "disorder": "F32",
  "criteria": {
    "A1": {"status": "met", "evidence": "Turn 12: ...", "confidence": 0.9},
    "A2": {"status": "not_met", "evidence": null, "confidence": 0.8}
  },
  "criteria_met_count": 6,
  "criteria_required": 5
}
```

### Stage 3: Diagnostic Logic Engine (Deterministic)

No LLM. Applies ICD-10 threshold rules:

- F32 MDD: >= 5 of A1-A9, must include A1 or A2
- F41.1 GAD: >= 3 of 6 symptoms + duration >= 6 months
- F43.1 PTSD: Criterion A + >= 1 from each of B, C, D, E
- Handles comorbidity: check ALL activated disorder thresholds
- Apply exclusion rules (e.g., bereavement exclusion)

Full ICD-10 rule set will be encoded as a separate appendix document (`docs/icd10_diagnostic_rules.json`) covering all disorders in scope. Starting point: the Machine-Actionable Criteria framework (npj Digital Medicine 2026).

Disorders in scope for Phase 3 (MDD-5k):
- F20 Schizophrenia, F22 Persistent delusional disorder
- F31 Bipolar affective disorder
- F32 Depressive episode, F33 Recurrent depressive disorder
- F40 Phobic anxiety disorders, F41.0 Panic disorder, F41.1 GAD
- F42 OCD, F43.1 PTSD, F43.2 Adjustment disorder
- F45 Somatoform disorders
- F51 Sleep disorders

ICD-10 vs ICD-11 note: Each dataset's diagnostic coding system will be documented in the dataset adapter config. The Logic Engine loads rules matching the dataset's coding system. Where datasets use ICD-11 (newer Chinese datasets), rules account for changes (e.g., bereavement exclusion removed in ICD-11, GAD duration criterion changed).

### Stage 4: Confidence Calibrator (Statistical)

No LLM. Computes diagnosis confidence from:

- Criterion checker agreement rates
- Evidence coverage (% criteria with sufficient evidence)
- Somatization mapper hit rate
- Abstention threshold: if confidence < threshold -> refer to clinician
- AURC-optimized

Output format in DiagnosisResult:
- `confidence: float` (0.0-1.0, calibrated probability)
- `decision: Literal["diagnosis", "abstain"]`
- Abstained cases are excluded from accuracy/F1 metrics but included in AURC computation
- Threshold selection: choose threshold on validation set that maximizes area under the selective accuracy curve
- Comorbidity interaction: if one disorder is confident and another abstains, output the confident diagnosis with a flag noting partial abstention

### Why HiED Avoids Prior Failure Modes

| Prior Failure | How HiED Avoids It |
|---|---|
| Reasoner/judge were pass-through (Project 3) | Criterion Checkers have genuine expertise asymmetry |
| MAS added noise (Optimization Paradox) | Logic Engine is deterministic, no LLM-to-LLM information loss |
| Evidence didn't help regression | Task is classification, not regression |
| Single model collapses to most common diagnosis | Triage forces consideration of multiple categories |
| Debate was theater | No debate: structured criterion checking with verifiable outputs |

---

## 4. Architecture — Alternative MAS Modes

All share the same Evidence Extractor and output format.

### Mode B: PsyCoT-MAS (`psycot`)

Drops triage. All Criterion Checkers run sequentially (I/O-overlapped) across all supported disorders (see VRAM Budget, Section 7). Same Logic Engine and Calibrator. Slower but no triage cascade risk.

### Mode A: Specialist-MAS (`specialist`)

Triage + free-form disorder specialist agents + LLM judge. Closest to prior MoodAngels pattern. Included as comparison condition.

### Mode C: Debate-MAS (`debate`)

Four perspective agents (Biological, Psychological, Social, Cultural) see same full evidence. Two debate rounds. Consensus judge. Cultural agent is the Chinese-specific contribution.

### Baseline: Single-Model (`single`)

Single LLM call. Variants: zero-shot, zero-shot+evidence, few-shot, few-shot+evidence. All MAS modes must beat this.

---

## 5. Datasets

| Dataset | Task | Labels | Disorders | Language | Access | Coding System |
|---|---|---|---|---|---|---|
| MDD-5k | Differential diagnosis | ICD-10 codes | 25+ | Chinese | GitHub (free) | ICD-10 |
| LingxiDiag-16K | 12-way differential + comorbidity | 12 ICD-10 categories | 12 + combos | Chinese | Contact authors | ICD-10 |
| PsyCoTalk | Comorbidity detection | 4 disorders + 6 combos | 10 labels | Chinese | Contact authors | ICD (version TBD — verify with authors) |
| D4 | Depression severity + suicide risk | Depression 0-5, suicide 0-4 | Depression | Chinese | DUA required | ICD-11 + DSM-5 |
| PDCH | HAMD-17 scoring | 17 item-level scores | Depression | Chinese | SciDB (free) | HAMD-17 (no ICD code labels) |
| E-DAIC | PHQ-8 scoring | 8 item-level scores | Depression | English | Existing | PHQ-8 (no ICD code labels) |

Note: MDD-5k uses 25+ ICD-10 codes. LingxiDiag-16K uses 12 broad categories. A mapping table from MDD-5k fine-grained codes to LingxiDiag's 12 categories will be maintained in `configs/datasets/label_mapping.yaml` for cross-dataset evaluation. The Logic Engine supports configurable disorder scopes via the mode config YAML.

### Unified Data Adapter

All datasets normalize to `ClinicalCase`:

```python
@dataclass
class ClinicalCase:
    case_id: str
    transcript: list[Turn]        # [(speaker, text, turn_id)]
    language: str                  # "zh" | "en"
    dataset: str
    transcript_format: str        # "dialogue" | "monologue" | "clinical_structured"
    coding_system: str            # "icd10" | "icd11" | "dsm5" | "ccmd3"

    # Ground truth (evaluation only)
    diagnoses: list[str]           # ICD-10/11 codes
    severity: dict | None
    comorbid: bool
    suicide_risk: int | None
    metadata: dict | None          # Dataset-specific fields
```

### 5.1 Dataset Access Risk & Contingency

| Dataset | Access Status | Gate | Contingency |
|---|---|---|---|
| MDD-5k | Free on GitHub | Phase 1 | Primary development dataset |
| PDCH | Free CC BY-NC 4.0 | Phase 1 | Primary Chinese severity dataset |
| E-DAIC | Already available | Phase 1 | English control |
| D4 | DUA required (email authors) | Phase 2 gate: send DUA request before Phase 1 ends | Use MDD-5k depression subset |
| LingxiDiag-16K | Contact authors (Feb 2026 paper) | Phase 1 gate: email authors immediately | Report MDD-5k 25-disorder results instead; redefine success criteria against MDD-5k baselines |
| PsyCoTalk | Contact authors (2025 paper) | Phase 2 gate | Use MDD-5k ICD-10 co-occurrence as comorbidity proxy |

Action items before Phase 1 begins:
1. Email LingxiDiag-16K authors requesting access (cite their arXiv paper)
2. Email D4 authors requesting DUA
3. Email PsyCoTalk authors requesting access
   - When emailing PsyCoTalk authors, also request confirmation of their ICD/diagnostic coding system version
4. Confirm MDD-5k GitHub download works and labels match documented format

If LingxiDiag-16K is unavailable, success criteria shift to:
- Beat MDD-5k single-model baseline on 25-disorder macro F1 (target: MAS > single by >= 0.05, p < 0.05)
- All other criteria (cross-lingual gap, evidence delta, somatization ablation) remain unchanged

---

## 6. Evaluation Framework

### Differential Diagnosis Metrics (MDD-5k, LingxiDiag-16K)

- Top-1 accuracy (primary diagnosis correct)
- Top-3 accuracy (correct in top 3)
- Macro F1 across disorder categories
- Hierarchical F1 (credit for correct broad category)

### Comorbidity Metrics (PsyCoTalk, LingxiDiag-16K)

- Subset accuracy (exact match of full label set)
- Hamming accuracy (per-disorder correctness)
- Comorbidity detection F1 (binary: comorbid vs single)

### Severity Scoring Metrics (PDCH, E-DAIC)

- MAE, RMSE, Pearson r, CCC
- Binary F1 (severity threshold)
- AURC (selective prediction)

### Evidence Quality Metrics (New)

- Criterion coverage: % of ground-truth criteria with evidence found
- Evidence precision: % of extracted evidence matching a real criterion
- Somatization ablation: downstream diagnostic macro F1 with/without somatization mapper (CN only). This is a downstream accuracy test, not a standalone precision/recall metric, because no annotated ground truth exists for the somatic-to-criterion mapping. Creating such annotations requires domain expert time and is deferred to future work. The mapper is evaluated by its effect on diagnostic accuracy, not intrinsically.

### Cross-Lingual Evidence Gap Test

Use binary classification metrics (severity threshold F1, AUROC) for the paired comparison, NOT regression metrics. Prior work proved evidence does not help English regression — using regression here would test a hypothesis already known to fail.

```
Evidence_delta = BinaryF1(with_evidence) - BinaryF1(without_evidence)

H0: Evidence_delta_Chinese = Evidence_delta_English
H1: Evidence_delta_Chinese > Evidence_delta_English

Test: paired bootstrap or permutation test (10,000 resamples)
Datasets: PDCH binary (HAMD-17 total >= 8 -> positive) vs E-DAIC binary (PHQ-8 total >= 10 -> positive)
Metric: Binary F1 and AUROC (not MAE or Pearson r)
```

Additionally, if MDD-5k classification results are available alongside an English multi-disorder dataset, run the gap test on classification macro F1 as well.

### Ablation Matrix

| Ablation | Tests |
|---|---|
| HiED vs single-model | Does MAS help? |
| With evidence vs without | Does evidence help? |
| With somatization mapper vs without | Does culture-aware mapping help? |
| Chinese vs English (same architecture) | Cross-lingual evidence gap |
| HiED vs psycot vs specialist vs debate | Which MAS mode wins? |
| BGE-M3 vs Qwen3-Embedding vs NV-Embed-v2 | Which retriever for Chinese? |
| With P3 GNN vs without | Does GNN reranking help Chinese? |
| Triage top-1 vs top-3 | Error mitigation cost/benefit |
| 4B vs 14B vs 32B checkers | Model scale x evidence interaction |

### Success Criteria

| Claim | Metric | Target | Baseline |
|---|---|---|---|
| Beat LingxiDiag 12-way | Top-1 accuracy (contingency: see §5.1) | > 0.30 | 0.285 (LingxiDiagBench reported accuracy) |
| Beat LingxiDiag comorbidity | Subset accuracy (contingency: see §5.1) | > 0.45 | 0.430 |
| MAS > single on Chinese | Macro F1 gap | > 0.05 (p < 0.05) | 0.0 |
| Evidence helps Chinese | Evidence delta CN | > 0 (p < 0.05) | -- |
| Evidence delta cross-lingual | delta CN - delta EN | > 0 (p < 0.05) | -- |
| Somatization mapper helps | delta with/without | > 0 on CN, = 0 on EN | -- |

---

## 7. Project Structure

```
CultureDx/
├── CLAUDE.md
├── README.md
├── pyproject.toml               # uv, Python 3.11+
├── configs/
│   ├── base.yaml
│   ├── paths.yaml
│   ├── datasets/                # One yaml per dataset
│   ├── modes/                   # One yaml per MAS mode
│   ├── model_pools/
│   ├── retrieval/
│   ├── sweeps/
│   └── experiments/
├── src/culturedx/
│   ├── core/
│   │   ├── config.py            # Pydantic config models
│   │   ├── models.py            # ClinicalCase, EvidenceBrief, DiagnosisResult
│   │   └── registry.py          # Model pool registry
│   ├── data/
│   │   ├── adapters/            # One adapter per dataset
│   │   └── splits.py
│   ├── evidence/
│   │   ├── extractor.py         # Symptom span extraction
│   │   ├── somatization.py      # CN somatization mapper
│   │   ├── criteria_matcher.py  # Evidence -> criteria matching
│   │   ├── retriever.py         # BGE-M3 / Qwen3-Embed / NV-Embed
│   │   ├── reranker.py          # Optional P3 GNN reranker (retrain required)
│   │   └── brief.py             # Evidence Brief assembly
│   ├── ontology/
│   │   ├── icd10.py
│   │   ├── dsm5.py
│   │   ├── symptom_map.py
│   │   └── data/                # Ontology JSON files
│   ├── agents/
│   │   ├── base.py
│   │   ├── triage.py
│   │   ├── criterion_checker.py
│   │   ├── specialist.py
│   │   ├── perspective.py
│   │   └── judge.py
│   ├── diagnosis/
│   │   ├── logic_engine.py      # Deterministic ICD-10 rules
│   │   ├── comorbidity.py
│   │   └── calibrator.py
│   ├── modes/
│   │   ├── base.py
│   │   ├── hied.py
│   │   ├── psycot.py
│   │   ├── specialist.py
│   │   ├── debate.py
│   │   └── single.py
│   ├── llm/
│   │   ├── client.py
│   │   ├── cache.py
│   │   └── json_utils.py
│   ├── eval/
│   │   ├── metrics.py
│   │   ├── cross_lingual.py
│   │   └── report.py
│   └── pipeline/
│       ├── runner.py
│       ├── sweep.py
│       └── cli.py
├── prompts/
│   ├── triage/
│   ├── criterion_checker/
│   ├── specialist/
│   ├── debate/
│   └── evidence/
├── data/
│   ├── raw/                     # gitignored
│   ├── processed/
│   ├── cache/
│   └── ontology/
├── outputs/
│   ├── runs/
│   ├── sweeps/
│   └── reports/
├── scripts/
│   ├── download_datasets.py
│   ├── build_ontology.py
│   └── run_sweep.py
├── tests/
│   ├── test_adapters.py
│   ├── test_evidence.py
│   ├── test_logic_engine.py
│   ├── test_modes.py
│   ├── test_metrics.py
│   └── fixtures/
└── docs/
    └── superpowers/
        └── specs/
```

### Tech Stack

| Component | Choice | Rationale |
|---|---|---|
| Package manager | uv | Fast, matches Project 3 |
| Python | 3.11+ | Match Project 3 |
| Config | Pydantic + OmegaConf layered YAML | Validated, composable |
| LLM inference | Ollama (primary) + vLLM (optional) | Local-first, existing setup |
| Embeddings | BGE-M3 (primary), Qwen3-Embedding, NV-Embed-v2 | Sweep all three |
| Prompts | Jinja2 templates | Language-specific, testable |
| Cache | SQLite (LLM), disk (embeddings) | Proven in prior projects |
| Eval analytics | DuckDB | Proven in Project 1 |
| Testing | pytest | Standard |
| CLI | click or typer | culturedx run, culturedx sweep |
| Hardware | RTX 5090 (32GB GDDR7) | Verified current machine |

### VRAM Budget Analysis (RTX 5090, 32GB GDDR7)

| Mode | Concurrent Models | Est. VRAM (Q4) | Feasibility |
|---|---|---|---|
| `single` | 1 x 14B | ~9GB | Feasible |
| `hied` | 1 x 14B triage, then 1-3 x 4B checkers (sequential via Ollama) | ~9GB peak | Feasible |
| `psycot` | 12 x 4B checkers (sequential, not parallel) | ~2.5GB per call | Feasible but slow (~2-3 min/case) |
| `specialist` | 1 x 14B triage + 1 x 14B specialist (sequential) + 1 x 14B judge | ~9GB peak | Feasible |
| `debate` | 4 x 14B perspective agents (sequential) + 1 x 14B judge | ~9GB peak | Feasible but slow |
| Ablation: 32B checker | 1 x 32B | ~20GB | Feasible (serial only) |

Note: "Parallel" in this spec means asynchronous I/O-overlapped sequential execution via Ollama, NOT concurrent GPU inference of multiple models. True multi-model parallelism would require multi-GPU or vLLM continuous batching (future optimization). All latency estimates assume sequential model loading.

For the retriever: BGE-M3 (570M, ~1.5GB) can remain loaded alongside the LLM. NV-Embed-v2 (7.8B, ~5GB Q4) requires unloading the LLM during encoding.

### Key Interfaces

```python
class BaseModeOrchestrator(ABC):
    @abstractmethod
    def diagnose(self, case: ClinicalCase, evidence: EvidenceBrief) -> DiagnosisResult: ...

class BaseDatasetAdapter(ABC):
    @abstractmethod
    def load(self, split: str) -> list[ClinicalCase]: ...

class BaseAgent(ABC):
    @abstractmethod
    def run(self, input: AgentInput) -> AgentOutput: ...
```

### 7.1 Prompt Governance

- All prompts stored in `prompts/` as Jinja2 templates with YAML frontmatter containing: version, language, target_disorder (if applicable), model_size_class (if model-specific variants exist)
- Every experiment run logs the SHA-256 hash of each prompt template used
- LLM cache key extended to: `{provider}:{model}:{prompt_hash}:{language}` — changing any prompt invalidates cached responses for that combination
- Language-specific variants co-located per task: `prompts/criterion_checker/psycot_zh.jinja` and `prompts/criterion_checker/psycot_en.jinja`
- Prompt iteration tracked in `prompts/CHANGELOG.md` with version bumps
- Few-shot examples (if used) stored in `prompts/examples/` as separate JSONL files, referenced by prompt templates, versioned independently

---

## 8. Phased Delivery

### Phase 1: Foundation

Project scaffold, configs, CLI. Data adapters for MDD-5k + PDCH + E-DAIC. Core data models. LLM client + cache. Single-model baseline mode. Basic metrics. Smoke test on MDD-5k fixtures.

### Phase 2: Evidence Layer

Symptom span extractor. BGE-M3 retriever. Criteria matcher. Chinese somatization mapper + ontology. Evidence Brief assembly. Evidence quality metrics. Single-model + evidence on real data.

### Phase 3: HiED-MAS

Triage agent. Criterion Checker agents with PsyCoT. Diagnostic Logic Engine. Comorbidity resolver. Confidence calibrator. HiED end-to-end on MDD-5k.

### Phase 4: Alternative Modes + Full Evaluation

PsyCoT-MAS, Specialist-MAS, Debate-MAS modes. Cross-lingual evidence gap experiment. Full ablation sweep. Additional dataset adapters as access comes.

### Phase 5: Analysis + Paper-Readiness

DuckDB analytics. Cross-mode comparisons. Statistical tests. Results tables and figures. Open-source cleanup.

### Out of Scope

- Model fine-tuning / LoRA (zero-shot/few-shot only)
- Interactive interview generation
- Audio/video processing (text-only)
- Real-time clinical deployment
- Web UI / API server
- Custom embedding training

---

## 9. Prior Work Lessons Incorporated

| Lesson (from 3 prior projects) | How CultureDx addresses it |
|---|---|
| Evidence doesn't help English regression | Task is Chinese classification where evidence should help |
| MAS fails without genuine asymmetry | Disorder-specialist agents have expertise asymmetry |
| Reasoner/judge are pass-through | Deterministic Logic Engine replaces LLM judge |
| RAG adds noise on well-known tasks | Chinese psychiatric assessment is poorly known to LLMs |
| Prompt engineering > architecture | Invest heavily in PsyCoT prompts per disorder |
| Evidence quality never measured | Explicit evidence quality metrics in eval framework |
| Somatization is the key Chinese signal | Novel somatization mapper as core contribution |
| P3 GNN works for retrieval reranking | Optional retrain on Chinese data, tested as ablation |
| Zero-shot paradox on English | English is the control condition proving the paradox |

---

## 10. SOTA Methods Referenced

| Method | Source | What we use |
|---|---|---|
| MDAgents | NeurIPS 2024 | Hierarchical triage pattern |
| MAGI | ACL Findings 2025 | PsyCoT criterion checking, structured interview agents |
| MedAgent-Pro | ICLR 2026 | Disease-level plan -> case-level execution |
| Optimization Paradox | Stanford 2025 | Why deterministic logic engine beats LLM judge |
| MoodAngels | NeurIPS 2025 | RAG-enhanced debate (comparison baseline) |
| LingxiDiagBench | arXiv 2026 | Benchmark baselines to beat |
| MDD-5k | AAAI 2025 | Neuro-symbolic dialogue generation, 25+ disorder labels |
| PsyCoTalk | arXiv 2025 | Comorbidity-aware dialogue dataset |
| BGE-M3 | BAAI 2024 | Chinese medical RAG retrieval |
| Chinese MentalBERT | ACL Findings 2024 | Chinese mental health text encoder |
| Machine-Actionable Criteria | npj Digital Medicine 2026 | Computable diagnostic criteria framework |
