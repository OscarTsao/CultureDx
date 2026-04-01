# Architecture

## End-To-End Flow

```text
ClinicalCase
  -> optional EvidencePipeline
     -> symptom extraction
     -> Chinese somatization mapping
     -> criteria retrieval/matching
     -> EvidenceBrief
  -> Mode orchestrator
     -> scope resolution
     -> triage or manual candidate selection
     -> criterion checker fanout
     -> deterministic logic engine
     -> calibrator
     -> optional differential / rerank
     -> comorbidity resolver
     -> DiagnosisResult
```

## Evidence Flow

`EvidencePipeline` in `src/culturedx/evidence/pipeline.py` orchestrates:

1. Patient-turn extraction from `ClinicalCase`.
2. Optional LLM symptom span extraction.
3. Optional Chinese somatization normalization.
4. Optional temporal signal extraction for anxiety-duration handling.
5. Criteria matching across the resolved disorder scope.
6. Contrastive evidence scoring for shared vs unique support.
7. `EvidenceBrief` assembly.

Important current behavior:

- Evidence scope is explicit:
  `manual`, `triage`, or `all_supported`.
- `auto` no longer silently falls back to `F32/F41.1`.
- Partial failures are returned as machine-readable `failures` on
  `EvidenceBrief`.

## Diagnosis Flow

`HiEDMode` is the main hierarchical path:

1. Resolve execution semantics:
   `benchmark_manual_scope` or `production_open_set`.
2. Resolve candidate scope:
   manual target disorders, triage-derived scope, or full supported scope.
3. Run criterion checkers in parallel.
4. Apply `DiagnosticLogicEngine` thresholds.
5. Apply `ConfidenceCalibrator`.
6. Optionally apply pairwise reranking and LLM differential disambiguation.
7. Apply `ComorbidityResolver`.
8. Emit `DiagnosisResult`.

Other modes:

- `MASMode`
  checker plus differential pipeline without HiED routing/calibration stack.
- `PsyCoTMode`
  flat criterion-checking path.
- `specialist`, `debate`, `single`
  alternative baselines/ensembles.

## Calibration Flow

Current calibration is split into two layers:

- Logic layer:
  deterministic threshold checks in `diagnosis/logic_engine.py`.
- Confidence layer:
  statistical calibrator in `diagnosis/calibrator.py`.

The calibrator currently exposes:

- `primary`
- `comorbid`
- `abstained`
- `rejected`

Each calibrated diagnosis can carry:

- raw confidence summary fields
- placement
- decision reason
- decision trace

## Serving And Runtime Components

- `OllamaClient`
  OpenAI-incompatible but simple local generation backend.
- `VLLMClient`
  OpenAI-compatible backend aimed at higher concurrency/throughput.
- `LLMCache`
  SQLite-backed response cache.
- `culturedx.pipeline.cli`
  CLI entry point.
- `ExperimentRunner`
  execution and output writer.

## Failure Modes And Abstention

Machine-readable failure codes now appear where practical. Common examples:

- `unsupported_language`
- `triage_failed`
- `scope_resolution_failed`
- `checker_failed`
- `evidence_unavailable`
- `evidence_extraction_failed`
- `rule_abstain`

Design intent:

- degrade explicitly rather than silently narrowing scope
- return recoverable failures alongside successful outputs when fallback worked
- prefer abstention over overclaiming on weak evidence
