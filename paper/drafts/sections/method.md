# 3. Method

## 3.1 System Architecture

CultureDx implements the **HiED** (Hierarchical Evidence-grounded Diagnosis) pipeline:

```
Clinical Transcript
        │
        ▼
┌─────────────────┐
│ Evidence Pipeline │  extract → somatize → retrieve → match
└────────┬────────┘
         ▼
┌─────────────────┐
│  1. Triage       │  LLM: broad ICD-10 category routing
│  2. Checkers     │  LLM: per-disorder criterion evaluation
│  3. Logic Engine │  Deterministic: ICD-10 threshold rules
│  4. Calibrator   │  Statistical: confidence scoring
│  5. Comorbidity  │  Rule-based: ICD-10 exclusions
└────────┬────────┘
         ▼
   DiagnosisResult
```

### Triage Agent
- Broad ICD-10 category classification (F2x, F3x, F4x)
- Reduces downstream checker fanout from 15 to ~3-5 disorders
- Bilingual prompt templates (Chinese/English)

### Criterion Checker Agent
- Per-disorder ICD-10 criterion evaluation
- Structured output: met/unmet per criterion with confidence scores
- Evidence-grounded: receives EvidenceBrief with matched criteria

### Diagnostic Logic Engine (Deterministic)
- ICD-10 threshold dispatch (core_total, first_rank, min_symptoms, etc.)
- No LLM involvement — fully deterministic and auditable
- Per-disorder rule sets for all 15 supported ICD-10 codes

### Confidence Calibrator (Statistical)
- Logistic regression on checker features
- Abstention when confidence below threshold
- Comorbidity candidate splitting

### Comorbidity Resolver
- ICD-10 exclusion rules (F33 supersedes F32, F31 supersedes F32/F33, F20 supersedes F22)
- Confidence-weighted primary/comorbid assignment

## 3.2 Evidence Pipeline

### Symptom Span Extraction
- LLM-based symptom identification from clinical transcripts
- Bilingual support (Chinese and English)

### Chinese Somatization Mapping
- 150-entry ontology: Chinese somatic expressions → ICD-10 criteria
- Ontology lookup first, LLM fallback for unknown somatic symptoms
- Examples:
  - "胸闷" (chest tightness) → F41.1 criterion (GAD somatic symptoms)
  - "头晕" (dizziness) → F32 criterion (depression somatic features)
  - "睡不着" (cannot sleep) → F51 / F32 criteria

### Temporal Extraction
- 3-layer hybrid: regex patterns + ChineseTimeNLP + stanza NER
- Duration normalization for ICD-10 time criteria (e.g., F32 requires ≥2 weeks)

### Negation Detection
- Scope-aware negation: handles Chinese positive-negation idioms (睡不着 = insomnia, not negation)
- Clause boundary detection
- Double negation resolution

### Hybrid Retrieval
- BGE-M3: native dense + sparse + ColBERT fusion
- Criterion-specific evidence matching with somatization boost

## 3.3 Alternative MAS Architectures

| Mode | Architecture | Key Difference |
|------|-------------|----------------|
| HiED | Triage → Checkers → Logic → Calibrator | Primary pipeline, hierarchical |
| PsyCoT | Checkers (all) → Logic → Calibrator | No triage, checks all 15 disorders |
| Specialist | Triage → Specialists → Judge | Free-form reasoning per disorder |
| Debate | 4 perspectives × 2 rounds → Judge | Bio/psych/social/cultural viewpoints |
| Single | Zero-shot/few-shot LLM | Baseline, no agent decomposition |

<!-- TODO: Write full method prose, add formal notation -->
