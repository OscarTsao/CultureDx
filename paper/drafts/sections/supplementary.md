# Appendix: Supplementary Materials

## A.1 Full ICD-10 Disorder Criteria

| Code | Disorder | Key Criteria |
|------|----------|-------------|
| F20 | Schizophrenia | Schneiderian first-rank symptoms, duration ≥1 month |
| F22 | Delusional disorder | Non-bizarre delusions ≥3 months |
| F31 | Bipolar affective disorder | ≥1 manic + ≥1 depressive episode |
| F32 | Depressive episode | ≥2 core + ≥2 additional symptoms, ≥2 weeks |
| F33 | Recurrent depressive disorder | ≥2 depressive episodes |
| F39 | Unspecified mood disorder | Mood symptoms not meeting other criteria |
| F40 | Phobic anxiety disorders | Marked fear/avoidance of specific situations |
| F41.0 | Panic disorder | Recurrent unexpected panic attacks |
| F41.1 | Generalized anxiety disorder | Excessive worry ≥6 months, ≥3 somatic symptoms |
| F42 | OCD | Obsessions and/or compulsions, time-consuming |
| F43.1 | PTSD | Re-experiencing, avoidance, hyperarousal after trauma |
| F43.2 | Adjustment disorder | Emotional/behavioral symptoms within 3 months of stressor |
| F45 | Somatoform disorders | Persistent physical complaints without medical explanation |
| F51 | Sleep disorders | Primary insomnia, hypersomnia, or sleep-wake schedule disorder |
| F98 | Behavioral/emotional disorders | Usually onset in childhood/adolescence |

## A.2 Somatization Ontology Sample

| Chinese Expression | English | Mapped Criterion | Disorder |
|-------------------|---------|-----------------|----------|
| 胸闷 | Chest tightness | Somatic anxiety symptoms | F41.1 |
| 头晕 | Dizziness | Somatic depression features | F32 |
| 心慌 | Palpitations | Autonomic arousal | F41.0, F41.1 |
| 浑身没劲 | Whole body weakness | Fatigue/loss of energy | F32 |
| 睡不着 | Cannot sleep | Insomnia | F32, F51 |
| 吃不下饭 | Cannot eat | Appetite change | F32 |
| 喘不过气 | Cannot breathe | Respiratory symptoms | F41.0 |
| 肚子不舒服 | Stomach discomfort | Gastrointestinal symptoms | F45 |

*(Full 150-entry ontology available in `src/culturedx/ontology/symptom_map.py`)*

## A.3 Prompt Templates

See `prompts/agents/` directory for all bilingual Jinja2 prompt templates:
- `criterion_checker_zh.jinja` / `criterion_checker_en.jinja`
- `criterion_checker_cot_zh.jinja` (CoT variant)
- `triage_zh.jinja` / `triage_en.jinja`
- `triage_cot_zh.jinja` (CoT variant)
- `differential_zh.jinja` / `differential_en.jinja`

## A.4 Detailed Per-Disorder Results

<!-- TODO: Add per-disorder accuracy, F1, precision, recall tables -->

## A.5 Case Studies

<!-- TODO: Add 3-5 illustrative case studies showing:
  1. Successful somatization mapping
  2. Comorbidity detection
  3. Abstention (appropriate)
  4. Error case analysis
-->
