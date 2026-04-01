# 1. Introduction

## Motivation

- LLMs have shown strong performance on medical reasoning benchmarks, but their parametric knowledge of non-Western clinical presentations remains weak
- Chinese psychiatric interviews feature pervasive somatic idioms of distress that do not map directly to Western diagnostic criteria
- Single-LLM approaches lack the structured reasoning needed for differential diagnosis and comorbidity detection

## Research Gap

- Existing psychiatric NLP systems are predominantly English-centric and assume Western symptom presentation
- Chinese somatization (e.g., "胸闷" chest tightness for anxiety, "头晕" dizziness for depression) requires explicit cultural mapping that LLMs cannot learn from limited training data
- No existing system combines culture-aware evidence extraction with multi-agent diagnostic reasoning

## Contributions

1. **CultureDx**: A culture-adaptive multi-agent system that decomposes psychiatric diagnosis into specialized agent roles with deterministic ICD-10 logic
2. **Somatization Ontology**: A 150-entry mapping from Chinese somatic expressions to ICD-10 diagnostic criteria
3. **Evidence Pipeline**: 3-layer temporal extraction, scope-aware negation detection, and hybrid retrieval (dense + sparse + ColBERT)
4. **Comprehensive Evaluation**: 5 MAS architectures compared across 2 Chinese psychiatric datasets (LingxiDiag-16K, MDD-5k) covering 15 ICD-10 disorders

<!-- TODO: Write full introduction prose -->
