# Module Replacement Memo

This memo answers a narrow engineering question:

> Why has CultureDx not simply replaced its major modules with existing SOTA
> packages, and which modules actually should be replaced, hybridized, or kept
> custom?

The goal is to make replacement decisions explicit, grounded in the current
codebase, and tied to measurable validation gates rather than package hype.

## Decision Labels

- `replace_now`
  a package-backed path already clearly dominates the current custom path, or
  the current custom logic is unnecessary
- `hybridize`
  package capability is useful, but should complement rather than replace the
  repo's current task-specific logic
- `keep_custom`
  the module encodes repo-specific semantics or deterministic rules that should
  remain first-class
- `blocked_by_benchmark`
  replacement may be promising, but the repo does not yet have enough evidence
  to justify switching the primary path

## Summary Table

| Module | Current implementation | External package candidates | Current adoption status | Decision | Why |
|---|---|---|---|---|---|
| Temporal extraction | custom regex/rule stack with optional tool layers | ChineseTimeNLP, stanza, jionlp, dateparser | partial | `hybridize` | external tools help in some cases, but current primary logic is still repo-specific and better controlled |
| Negation detection | custom scope-aware rules, optional stanza support | stanza DEP, negex-style parsers | partial but not primary | `hybridize` | dependency parsing is useful, but current runtime path still depends on custom clause logic and idiom exceptions |
| Somatization mapping | ontology lookup + normalization + fuzzy + optional LLM fallback | HanLP medical NER, SNOMED-like resources, OpenMedicalNER | none as primary path | `hybridize` | package NER is not a direct substitute for concept-to-criterion grounding |
| Text normalization | custom normalization / matching helpers | jieba, spaCy zh, HanLP tokenizer | none | `keep_custom` | the task is lightweight concept normalization, not generic tokenization |
| Symptom extraction | LLM prompt-based structured extraction | HanLP NER, PaddleNLP UIE, spaCy NER | none | `blocked_by_benchmark` | current task expects criterion-oriented structured spans, not just generic entities |
| Criteria retrieval | BGE-M3 retriever, native hybrid via FlagEmbedding when available | FlagEmbedding BGEM3FlagModel | adopted | `keep_custom` package-backed | this is already the clearest successful package integration |
| Criteria matching / reranking | retrieval + custom overlap/negation/somatization-aware reranking | BGE reranker, cross-encoder rerankers | none as primary path | `hybridize` | stronger rerankers may help, but they do not replace task-specific safety logic |
| Logic engine | deterministic ICD-10 threshold rules | none appropriate | N/A | `keep_custom` | this is domain logic, not an NLP subproblem |
| Diagnosis calibrator | custom feature extractor + heuristic / artifact-backed linear calibrator | sklearn logistic / isotonic / Platt scaling | partial via artifact path | `hybridize` | training utilities can use standard libraries, but runtime decision semantics stay repo-specific |
| Comorbidity resolver | deterministic exclusions, allowed pairs, confidence ratio filters | none appropriate | N/A | `keep_custom` | this is repo-specific diagnostic policy logic |
| Code mapping | hand-coded ontology/code mapping | none appropriate | N/A | `keep_custom` | task is repository ontology alignment, not generic modeling |

## Detailed Decisions

### 1. Temporal Extraction

Relevant files:

- [temporal.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/temporal.py)
- [eval_temporal_tools.py](/home/user/YuNing/CultureDx/scripts/eval_temporal_tools.py)
- [temporal_eval_results.json](/home/user/YuNing/CultureDx/outputs/temporal_eval_results.json)

Current state:

- primary path is still custom temporal extraction in
  [temporal.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/temporal.py)
- `ChineseTimeNLP` is wired as a supplementary duration-normalization layer
- `stanza` NER is wired as a fallback layer
- `jionlp` and `dateparser` are only used in the evaluation script, not the
  production pipeline

Why not replace fully:

- the repo's temporal task is not just date extraction
- it needs symptom-duration reasoning relevant to psychiatric criteria, with
  special handling for colloquial Chinese duration cues
- committed evaluation shows external tools are mixed rather than clearly
  dominant

Decision:

- `hybridize`
- keep the custom temporal reasoning layer as primary
- use package outputs only as controlled supplementary signals

Upgrade gate before any full replacement:

- beat the current temporal pipeline on a committed benchmark that measures
  criterion-relevant duration estimation, not just date detection

### 2. Negation Detection

Relevant files:

- [negation.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/negation.py)
- [criteria_matcher.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/criteria_matcher.py)

Current state:

- the negation module supports optional `stanza`
- but the main matcher path currently instantiates
  `NegationDetector(use_dep_parsing=False)`
- that means the repo's active primary path is still rule/scope-based, not
  dependency-parse-driven

Why not replace fully:

- Chinese symptom phrases include many positive expressions with negation-like
  surface forms, such as `睡不着`, `吃不下`, `提不起劲`
- the current module encodes domain-specific exceptions and clause boundaries
  that a generic dependency parse does not replace by itself

Decision:

- `hybridize`
- keep the custom scope-resolution core
- optionally turn on dependency parsing when a benchmark shows it reduces
  clinically relevant false positives without hurting idiomatic positives

Upgrade gate:

- a committed negation benchmark showing that `stanza` or another parser
  improves symptom-level negation accuracy in real Chinese clinical text

### 3. Somatization Mapping

Relevant files:

- [somatization.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/somatization.py)
- [normalization.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/normalization.py)
- [somatization_benchmark.md](/home/user/YuNing/CultureDx/docs/somatization_benchmark.md)

Current state:

- ontology lookup
- normalization
- fuzzy matching
- optional LLM fallback

Why not replace fully:

- CultureDx needs more than entity recognition
- it needs:
  1. detect somatic or idiomatic expression
  2. normalize to a canonical concept
  3. map to candidate ICD-10 criteria
- general medical NER packages usually stop at step 1 or step 2

Decision:

- `hybridize`
- keep the ontology-driven core
- evaluate medical NER only as candidate generation or concept proposal, not as
  a direct replacement

Upgrade gate:

- use the repo's somatization benchmark infrastructure to prove a package-based
  candidate generator improves concept accuracy or criterion recall

### 4. Text Normalization

Relevant files:

- [normalization.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/normalization.py)

Current state:

- lightweight normalization
- concept signatures
- task-specific lexical heuristics

Why not replace:

- the current task is not tokenization for its own sake
- it is small, deterministic preprocessing used by retrievers, somatization,
  and matching logic
- a tokenizer package would not automatically improve criterion grounding

Decision:

- `keep_custom`

When to revisit:

- only if a tokenizer-backed pipeline shows clear gains in the somatization or
  retrieval benchmarks, not just nicer segmentation

### 5. Symptom Extraction

Relevant files:

- [extractor.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/extractor.py)

Current state:

- LLM-based structured extraction
- expects symptom text, turn id, and symptom type

Why not replace yet:

- generic NER/UIE models do not necessarily align with the repo's criterion
  checking format
- the extracted units here are designed to feed downstream criterion grounding
  and evidence assembly, not just recognize named entities

Decision:

- `blocked_by_benchmark`

Upgrade gate:

- build a benchmark comparing current LLM extraction vs package-based span
  extractors on downstream criterion grounding quality, not just entity recall

### 6. Criteria Retrieval

Relevant files:

- [retriever.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/retriever.py)
- [retriever_factory.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/retriever_factory.py)

Current state:

- BGE-M3 retrieval
- native hybrid mode via `FlagEmbedding.BGEM3FlagModel` when available
- lexical and hybrid retriever abstractions

This is the clearest case where the repo **did** adopt an existing package in a
meaningful way.

Decision:

- `keep_custom` package-backed

Interpretation:

- the surrounding abstraction is custom
- the underlying retrieval engine already uses an existing strong external
  package where appropriate

### 7. Criteria Matching And Reranking

Relevant files:

- [criteria_matcher.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/criteria_matcher.py)

Current state:

- retrieval-backed evidence matching
- concept-overlap reranker
- negation-aware penalties
- somatization-aware boosts

Why not replace fully:

- a cross-encoder reranker might improve ordering
- but it would not replace the repo's task-specific logic for contradiction,
  negation, somatization boosts, and criterion-typed hints

Decision:

- `hybridize`

Upgrade gate:

- add a package-backed reranker as an optional stage and compare:
  retrieval recall, downstream Top-1, latency, and error slices

### 8. Logic Engine

Relevant files:

- [logic_engine.py](/home/user/YuNing/CultureDx/src/culturedx/diagnosis/logic_engine.py)

Current state:

- deterministic ICD-10 threshold rules

Decision:

- `keep_custom`

Reason:

- this is not an NLP module
- it is core diagnostic policy logic
- replacing it with a package would remove one of the repo's most important
  interpretability and auditability properties

### 9. Diagnosis Calibrator

Relevant files:

- [calibrator.py](/home/user/YuNing/CultureDx/src/culturedx/diagnosis/calibrator.py)
- [calibration.py](/home/user/YuNing/CultureDx/src/culturedx/eval/calibration.py)

Current state:

- custom feature extraction
- heuristic fallback
- learned artifact path for linear calibration

Why not replace fully:

- standard packages help with fitting models
- but runtime decision semantics here include primary/comorbid/abstain/reject
  splitting, audit traces, and repo-specific failure behavior

Decision:

- `hybridize`

Best path:

- use standard ML libraries for fitting
- keep repo-owned runtime representation and decision policy

### 10. Comorbidity Resolver

Relevant files:

- [comorbidity.py](/home/user/YuNing/CultureDx/src/culturedx/diagnosis/comorbidity.py)

Current state:

- deterministic exclusions
- allowed-pair logic
- confidence-ratio filtering

Decision:

- `keep_custom`

Reason:

- this is policy logic over ICD-10 interactions, not a generic package problem

### 11. Code Mapping

Relevant files:

- [code_mapping.py](/home/user/YuNing/CultureDx/src/culturedx/eval/code_mapping.py)

Decision:

- `keep_custom`

Reason:

- this is repo-specific ontology alignment

## Practical Conclusion

If the question is:

> Why didn't the repo replace everything with existing SOTA packages?

The answer is:

1. several modules are not ordinary NLP subtasks and therefore do not have a
   clean package substitute
2. the package outputs often stop short of the repo's real target:
   criterion grounding, deterministic diagnosis, or comorbidity policy
3. the one place where package integration is a clear fit, retrieval, has
   already been adopted
4. other replacements should be treated as benchmarked hybrid additions, not
   blind rewrites

## Recommended Next Actions

1. `replace_now`
   none, beyond continuing the already-adopted FlagEmbedding retrieval path
2. `hybridize next`
   criteria reranking, somatization candidate generation, negation parsing
3. `benchmark first`
   symptom extraction and any attempt to fully replace temporal reasoning
4. `never outsource`
   logic engine, comorbidity resolver, code mapping
