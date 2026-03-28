# Somatization Benchmark

## Purpose

This benchmark turns CultureDx's Chinese somatization normalization capability
from a heuristic module into a measurable research asset.

The task is:

- detect whether an expression is a direct symptom, somatized expression, or a
  context-sensitive non-positive mention
- normalize the expression to a canonical symptom concept when appropriate
- ground the expression to candidate ICD-10 criterion IDs

This repository does not ship real expert-labeled benchmark data. It ships the
schema, loaders, baselines, evaluation harness, review pipeline, and synthetic
demo fixtures needed to build a real benchmark honestly.

## Task Definition

Each example may contain:

- raw transcript segment or utterance text
- optional span text and offsets
- normalized symptom concept
- candidate criterion IDs
- optional disorder relevance labels
- one expression type label
- annotation confidence and notes
- source metadata and locale info

The benchmark can support:

- gold evaluation splits: `train`, `val`, `test`, `gold`
- human-in-the-loop growth splits: `annotation_pool`, `review_pool`

## Expression Types

- `direct_symptom`
  explicit psychiatric symptom wording such as `情绪低落`, `担心很多事情`
- `somatized_expression`
  bodily or idiomatic expression that maps to a psychiatric symptom or
  criterion, such as `胸口发闷`, `心里发慌`
- `metaphorical_or_ambiguous`
  bodily/metaphorical wording that is too vague to normalize confidently
- `negated`
  explicitly denied symptom mention
- `historical_past`
  symptom mention that is historical rather than current
- `family_or_other_person`
  the symptom belongs to someone other than the patient
- `insufficient_context`
  not enough evidence to assign a cleaner label

## Labeling Rules

### What Counts As Somatization

Label `somatized_expression` when:

- the utterance uses bodily or idiomatic wording rather than naming the
  psychiatric symptom directly
- the expression is plausibly attributable to the patient in current context
- the benchmark can map it to a canonical symptom concept or criterion set

Examples:

- `胸口发闷` -> `胸闷`
- `心里发慌` -> `心慌`
- `睡不着` -> `失眠`

### What Counts As Direct Expression

Label `direct_symptom` when the patient directly names the psychiatric symptom
or a near-direct synonym, such as:

- `情绪低落`
- `焦虑`
- `兴趣减退`

### Ambiguous Bodily Complaints

Use `metaphorical_or_ambiguous` when the utterance is too vague to normalize
reliably:

- `浑身都不舒服`
- `说不上来哪里不对劲`

If additional surrounding context makes the concept obvious, prefer the
appropriate positive label instead.

### Negation, Temporality, And Context Leakage

- `negated`: the patient explicitly denies the symptom.
- `historical_past`: the patient describes prior history, not a current active
  symptom.
- `family_or_other_person`: the speaker is discussing another person.

These labels take precedence over direct/somatized positive labels.

### Multi-Label Cases

- Multiple criterion IDs are allowed in `candidate_criterion_ids`.
- Multiple disorders are allowed in `disorder_relevance`.
- Use one primary `expression_type` label per example.
- If a span truly contains two distinct expressions, split it into two examples
  rather than forcing one record to carry two incompatible concept labels.

## File Formats

Canonical format:

- JSONL, one validated example per line

Supported helpers:

- CSV import/export for annotation and review operations

See:

- [src/culturedx/evidence/somatization_dataset.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/somatization_dataset.py)
- [src/culturedx/evidence/somatization_benchmark.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/somatization_benchmark.py)

Synthetic/demo fixtures:

- [somatization_benchmark_demo.jsonl](/home/user/YuNing/CultureDx/tests/fixtures/somatization_benchmark_demo.jsonl)
- [somatization_annotation_template.jsonl](/home/user/YuNing/CultureDx/tests/fixtures/somatization_annotation_template.jsonl)
- [somatization_review_template.jsonl](/home/user/YuNing/CultureDx/tests/fixtures/somatization_review_template.jsonl)

These are not real benchmark data.

## Baseline Methods

Implemented baselines:

- ontology exact match
- ontology + synonym/fuzzy match
- current repo somatization mapper baseline
- optional embedding-assisted concept candidate generation behind a feature flag

Optional model-heavy paths are disabled by default and must not be used to
claim results unless their configuration and artifacts are committed.

## Metrics

The evaluation harness can compute:

- exact concept accuracy
- top-k concept recall
- criterion candidate recall
- span precision / recall / F1 when offsets are available
- label-wise precision / recall / F1 by expression type
- confusion breakdown for somatized vs direct vs ambiguous/contextual
- confidence diagnostics such as Brier score and ECE when confidence is present
- per-concept and per-disorder slices

Outputs:

- machine-readable JSON
- markdown summary
- structured error records

## Review And Adjudication Workflow

1. Build or load a dataset in JSONL.
2. Run multiple baselines.
3. Evaluate and inspect error buckets.
4. Generate a review queue prioritizing disagreement, low confidence,
   ambiguity, underrepresented concepts, and production-linked failures.
5. Export review queues and adjudication records in JSONL or CSV for human
   reviewers.
6. Merge adjudicated results back into `gold` or `review_pool`.

## Active Learning / Review Queue

Current queue scoring can prioritize:

- low confidence
- disagreement between methods
- ontology vs fuzzy/mapper mismatch
- ambiguity-heavy examples
- underrepresented concepts
- production failures or abstentions linked to somatization

## Connection To CultureDx

This benchmark directly supports the evidence layer:

- better somatization normalization improves evidence grounding
- the structured mapper output (`expression_type`, normalized concept,
  candidate criteria, confidence, rationale, ambiguity flags, cache metadata)
  can be fed directly into annotation-pool generation
- stronger criterion grounding reduces checker noise
- fewer over-triggered mappings should improve downstream diagnosis calibration

The goal is to let CultureDx measure intrinsic somatization quality, not only
its downstream diagnostic effect.
