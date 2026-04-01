# AGENTS.md

This file is the repo-level operating manual for human contributors and coding
agents working in CultureDx.

## Repo Map

- `src/culturedx/core`
  config models and shared dataclasses.
- `src/culturedx/data/adapters`
  dataset adapters that normalize raw sources into `ClinicalCase`.
- `src/culturedx/llm`
  Ollama/vLLM clients, cache, and JSON parsing helpers.
- `src/culturedx/evidence`
  symptom extraction, somatization mapping, retrieval, criteria matching, and
  evidence brief assembly.
- `src/culturedx/agents`
  triage, criterion checker, differential, specialist, and judge agents.
- `src/culturedx/diagnosis`
  logic engine, calibrator, pairwise ranker, and comorbidity resolver.
- `src/culturedx/modes`
  orchestration layers for `single`, `mas`, `hied`, `psycot`, `specialist`,
  and `debate`.
- `src/culturedx/pipeline`
  CLI, runner, and sweep tooling.
- `src/culturedx/eval`
  metrics, calibration, evidence metrics, reports, and statistical tests.
- `configs`
  base config and mode/backend overlays.
- `prompts`
  bilingual Jinja templates used by agents/evidence components.
- `tests`
  local deterministic test suite; no private data or GPU required.
- `scripts`
  research utilities, calibration helpers, and analysis scripts.

## Key Architecture Components

- `EvidencePipeline`
  extract -> somatize -> match -> assemble.
- `HiEDMode`
  scope resolution -> triage or manual scope -> checker fanout -> logic engine
  -> calibrator -> optional rerank/differential -> comorbidity resolver.
- `DiagnosticLogicEngine`
  deterministic ICD-10 threshold logic.
- `ConfidenceCalibrator`
  confidence scoring, abstention, and primary/comorbid/rejected split.
- `ComorbidityResolver`
  exclusion rules, confidence filters, optional allowed-pair enforcement.
- `ExperimentRunner`
  case execution, prediction writing, and metric emission.

## How To Run Tests

Fast repo check:

```bash
make check
```

Full suite:

```bash
uv run pytest -q
```

Targeted examples:

```bash
uv run pytest tests/test_hied_mode.py -q
uv run pytest tests/test_evidence_pipeline.py tests/test_calibrator.py -q
uv run culturedx smoke
```

## Local Dev Workflows

Install dependencies:

```bash
uv sync
```

Run CLI help:

```bash
uv run culturedx --help
```

Run HiED benchmark/manual scope:

```bash
uv run culturedx run -c configs/base.yaml -c configs/hied.yaml -d mdd5k --data-path data/raw/mdd5k
```

Run with evidence:

```bash
uv run culturedx run -c configs/base.yaml -c configs/hied.yaml -d mdd5k --with-evidence --data-path data/raw/mdd5k
```

Dry-run sweep:

```bash
uv run culturedx sweep -c configs/base.yaml -c configs/hied.yaml -d mdd5k --dry-run
```

## Coding Conventions

- Python 3.11+ with type hints.
- Prefer deterministic tests and lightweight fixtures.
- Use explicit `encoding="utf-8"` for file I/O.
- Keep diffs reviewable; avoid unrelated refactors.
- Do not reintroduce hidden clinical-scope defaults.
- Keep failure behavior machine-readable when practical.

## Review Checklist

- Scope semantics explicit:
  benchmark/manual vs production/open-set must be visible in config or output.
- No fabricated benchmark numbers, calibration artifacts, or learned weights.
- Failure handling explicit:
  abstentions and degradations should expose codes/reasons where practical.
- Tests added or updated for changed behavior.
- Commands in docs/configs match the actual CLI and project layout.
- Backward compatibility considered; breaking changes documented.

## Artifact And Output Conventions

Current run outputs usually include:

- `run_manifest.json`
- `run_info.json`
- `predictions.jsonl`
- `metrics.json`
- `failures.jsonl`
- `stage_timings.jsonl`
- `metrics_summary.json`
- `summary.md`

Current prediction records may contain:

- `case_id`
- `primary_diagnosis`
- `comorbid_diagnoses`
- `decision`
- `routing_mode`
- `scope_policy`
- `candidate_disorders`
- `decision_trace`
- `failure` / `failures`

Current evidence records may contain:

- `scope_policy`
- `target_disorders`
- `failures`
- `stage_timings`

Prefer the canonical artifacts for new work:

- `run_manifest.json`
- `predictions.jsonl`
- `failures.jsonl`
- `stage_timings.jsonl`
- `metrics_summary.json`
- `summary.md`

## Clinical Safety And Abstention Rules

- This repository is for research and system development, not clinical use.
- Prefer abstention when language is unsupported, routing fails, or evidence is
  weak.
- Do not silently narrow the disorder search space in production-style paths.
- Do not invent diagnoses, confidence numbers, or empirical claims not backed
  by committed artifacts.

## Benchmark Mode vs Production Mode

- `benchmark_manual_scope`
  set `mode.target_disorders`; use for closed-set benchmarking or controlled
  experiments.
- `production_open_set`
  omit `mode.target_disorders`; allow triage or explicit all-supported scope to
  route the case.

For `EvidencePipeline`:

- `manual`
  requires explicit target disorders.
- `triage`
  requires triage-provided candidate disorders from the caller.
- `all_supported`
  uses the full supported ontology set.
- `auto`
  resolves to `manual` when targets are configured, otherwise `all_supported`.

## Somatization Benchmark

Research/annotation work for Chinese somatization normalization now lives in:

- [somatization_benchmark.md](/home/user/YuNing/CultureDx/docs/somatization_benchmark.md)
- [somatization_dataset.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/somatization_dataset.py)
- [somatization_benchmark.py](/home/user/YuNing/CultureDx/src/culturedx/evidence/somatization_benchmark.py)

Synthetic/demo fixtures under `tests/fixtures/somatization_*` are not real
benchmark artifacts and must not be reported as empirical results.

## Further Reading

- [developer_guide.md](/home/user/YuNing/CultureDx/docs/developer_guide.md)
  quickest code-reading path for new contributors.
- [study_overview.md](/home/user/YuNing/CultureDx/docs/study_overview.md)
  consolidated study, experiment, result, and method summary.
- [module_replacement_memo.md](/home/user/YuNing/CultureDx/docs/module_replacement_memo.md)
  module-by-module decision record for package replacement vs hybridization.
