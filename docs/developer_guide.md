# Developer Guide

This guide is the fast path for contributors who need to understand how
CultureDx executes a case, where major behaviors live, and which files to read
before changing a subsystem.

## Recommended Reading Order

If you are new to the repo, read in this order:

1. [README.md](/home/user/YuNing/CultureDx/README.md)
2. [AGENTS.md](/home/user/YuNing/CultureDx/AGENTS.md)
3. [architecture.md](/home/user/YuNing/CultureDx/docs/architecture.md)
4. [operations.md](/home/user/YuNing/CultureDx/docs/operations.md)
5. The subsystem you plan to change:
   - routing: [triage-routing.md](/home/user/YuNing/CultureDx/docs/triage-routing.md)
   - somatization benchmark: [somatization_benchmark.md](/home/user/YuNing/CultureDx/docs/somatization_benchmark.md)

## Package Map And Responsibilities

- `src/culturedx/core`
  shared dataclasses, config models, failure/output schemas.
- `src/culturedx/data/adapters`
  dataset-specific loaders that emit `ClinicalCase`.
- `src/culturedx/evidence`
  transcript-to-evidence pipeline: extraction, somatization, temporal
  features, retrieval, matching, and brief assembly.
- `src/culturedx/agents`
  LLM-backed task specialists such as triage, criterion checking, judge, and
  differential disambiguation.
- `src/culturedx/diagnosis`
  deterministic and statistical decision layers:
  logic engine, calibrator, pairwise ranker, comorbidity.
- `src/culturedx/modes`
  orchestration layers that combine agents, evidence, and diagnosis logic.
- `src/culturedx/pipeline`
  CLI entrypoints, runner, artifact emission, and sweep support.
- `src/culturedx/eval`
  metrics, calibration evaluation, reports, and analysis helpers.

## Main Execution Paths

### CLI Run Path

The common local entry path is:

1. [cli.py](/home/user/YuNing/CultureDx/src/culturedx/pipeline/cli.py)
2. config overlays from `configs/`
3. dataset adapter from `src/culturedx/data/adapters`
4. optional [pipeline.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/pipeline.py)
5. selected mode, usually [hied.py](/home/user/YuNing/CultureDx/src/culturedx/modes/hied.py)
6. [runner.py](/home/user/YuNing/CultureDx/src/culturedx/pipeline/runner.py)
7. canonical artifacts under `outputs/`

### HiED Diagnosis Path

The primary research path is `HiEDMode.diagnose()`:

1. resolve benchmark/manual vs production/open-set semantics
2. resolve candidate disorders by manual scope, triage, or all-supported scope
3. run criterion checker fanout
4. apply deterministic ICD-10 threshold logic
5. calibrate confidence and split primary/comorbid/abstain/rejected
6. optionally rerank or differentially disambiguate close calls
7. resolve comorbidity exclusions and emit `DiagnosisResult`

Start reading in:

- [hied.py](/home/user/YuNing/CultureDx/src/culturedx/modes/hied.py)
- [logic_engine.py](/home/user/YuNing/CultureDx/src/culturedx/diagnosis/logic_engine.py)
- [calibrator.py](/home/user/YuNing/CultureDx/src/culturedx/diagnosis/calibrator.py)
- [comorbidity.py](/home/user/YuNing/CultureDx/src/culturedx/diagnosis/comorbidity.py)

### Evidence Path

`EvidencePipeline.extract()` is the evidence orchestration entrypoint:

1. resolve effective disorder scope
2. extract symptom spans from patient turns
3. apply Chinese somatization normalization when enabled
4. extract temporal features when enabled and clinically relevant
5. retrieve and match candidate criteria evidence
6. assemble an `EvidenceBrief`
7. attach machine-readable failures and stage timings

Start reading in:

- [pipeline.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/pipeline.py)
- [extractor.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/extractor.py)
- [somatization.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/somatization.py)
- [temporal.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/temporal.py)
- [criteria_matcher.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/criteria_matcher.py)

### Triage And Calibration Path

Triage routing has two layers:

- [triage.py](/home/user/YuNing/CultureDx/src/culturedx/agents/triage.py)
  parses LLM output into broad diagnostic categories.
- [triage_routing.py](/home/user/YuNing/CultureDx/src/culturedx/agents/triage_routing.py)
  calibrates category scores, expands them into disorder codes, and computes
  routing metrics.

Diagnosis confidence calibration lives in:

- [calibrator.py](/home/user/YuNing/CultureDx/src/culturedx/diagnosis/calibrator.py)
- [calibration.py](/home/user/YuNing/CultureDx/src/culturedx/eval/calibration.py)

## Where To Change Common Behaviors

- Change benchmark/manual vs production semantics:
  [hied.py](/home/user/YuNing/CultureDx/src/culturedx/modes/hied.py),
  [pipeline.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/pipeline.py),
  [config.py](/home/user/YuNing/CultureDx/src/culturedx/core/config.py)
- Change evidence extraction or mapping:
  `src/culturedx/evidence/*`, especially `extractor.py`,
  `somatization.py`, `temporal.py`, `criteria_matcher.py`
- Change diagnosis decisioning:
  `logic_engine.py`, `calibrator.py`, `comorbidity.py`
- Change run artifacts or reports:
  `pipeline/artifacts.py`, `runner.py`, `eval/report.py`
- Change serving/runtime behavior:
  `llm/client.py`, `llm/runtime.py`, `llm/vllm_client.py`

## Tests By Subsystem

- HiED and orchestration:
  [test_hied_mode.py](/home/user/YuNing/CultureDx/tests/test_hied_mode.py),
  [test_hied_e2e.py](/home/user/YuNing/CultureDx/tests/test_hied_e2e.py)
- Evidence pipeline:
  [test_evidence_pipeline.py](/home/user/YuNing/CultureDx/tests/test_evidence_pipeline.py),
  [test_somatization.py](/home/user/YuNing/CultureDx/tests/test_somatization.py),
  [test_temporal.py](/home/user/YuNing/CultureDx/tests/test_temporal.py)
- Triage and calibration:
  [test_triage.py](/home/user/YuNing/CultureDx/tests/test_triage.py),
  [test_calibrator.py](/home/user/YuNing/CultureDx/tests/test_calibrator.py),
  [test_calibration.py](/home/user/YuNing/CultureDx/tests/test_calibration.py)
- Runner and artifact schema:
  [test_runner_artifacts.py](/home/user/YuNing/CultureDx/tests/test_runner_artifacts.py),
  [test_cli.py](/home/user/YuNing/CultureDx/tests/test_cli.py)

## Safety Invariants To Preserve

- Never silently narrow the disorder scope in production-style paths.
- Keep benchmark/manual scope explicit when `target_disorders` is set.
- Prefer machine-readable abstention/failure reasons over silent fallthrough.
- Do not fabricate metrics, artifacts, trained parameters, or benchmark claims.
- If an artifact is missing, document and exercise the safe fallback path.

## Useful Local Commands

```bash
make check
uv run pytest -q
uv run pytest tests/test_hied_mode.py tests/test_evidence_pipeline.py tests/test_runner_artifacts.py -q
uv run culturedx --help
uv run culturedx smoke
```
