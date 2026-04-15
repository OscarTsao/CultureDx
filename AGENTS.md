# AGENTS.md

This file is the repo-level operating manual for contributors and coding
agents working in CultureDx.

## Repo Map

- `src/culturedx/core`
  config models, shared dataclasses, registry helpers, and target-disorder
  utilities.
- `src/culturedx/data/adapters`
  dataset adapters for `lingxidiag16k`, `mdd5k`, `pdch`, and `edaic`.
- `src/culturedx/llm`
  client construction, caching, runtime helpers, JSON parsing, and vLLM
  integration.
- `src/culturedx/agents`
  triage, diagnostician, criterion checker, differential, contrastive, and
  routing helpers.
- `src/culturedx/diagnosis`
  deterministic logic engine, calibrator, comorbidity resolver, and evidence
  verification helpers.
- `src/culturedx/modes`
  checked-in orchestrators for `hied` and `single`.
- `src/culturedx/ontology`
  ICD-10 criteria, shared-criteria logic, symptom map, and demographic priors.
- `src/culturedx/pipeline`
  CLI entrypoints, experiment runner, sweep logic, reproducibility helpers, and
  canonical artifact schemas.
- `src/culturedx/retrieval`
  FAISS-backed similar-case retrieval used by RAG variants.
- `configs`
  base config, dataset overlays, model-pool overlays, targets, and ablations.
- `prompts/agents`, `prompts/single`, `prompts/paper_static`
  prompt templates. The checked-in prompt assets are primarily Chinese.
- `tests`
  deterministic local test suite and fixtures.
- `scripts`
  evaluation, ablation, bootstrap, and paper-report utilities.
- `results/validation`
  committed validation analyses and reference notes.
- `paper`
  drafts, tables, figures, preprints, and supplementary materials.

## Current Branch Caveat

- `src/culturedx/evidence` exists as a package directory, but in this branch
  the checked-in tree only contains compiled `__pycache__` artifacts, not the
  source `.py` modules.
- CLI and runner code still reference `culturedx.evidence.*`.
- Before changing evidence-related flows, verify whether the required source
  files are present in the working tree or need to be restored from another
  branch or commit.

## Key Architecture Components

- `HiEDMode`
  resolves scope semantics, runs triage or manual candidate selection, optionally
  uses the diagnostician DtV path, fans out criterion checking, then applies the
  logic engine, calibrator, differential logic, and comorbidity resolution.
- `SingleModelMode`
  single-call baseline with optional RAG retrieval and optional
  evidence-conditioned prompting.
- `DiagnosticLogicEngine`
  deterministic ICD-10 threshold logic over checker outputs.
- `ConfidenceCalibrator`
  confidence scoring, abstention, and primary/comorbid selection.
- `ComorbidityResolver`
  forbidden-pair filtering and final primary/comorbid split.
- `ExperimentRunner`
  bounded-concurrency case execution plus canonical artifact, metric, and
  summary emission.
- `RunManifest`, `CaseSelectionManifest`, `PredictionRecord`,
  `FailureRecord`, `StageTimingRecord`, `MetricsSummary`
  canonical output schemas in `src/culturedx/pipeline/artifacts.py`.

## How To Run Tests

Fast repo check:

```bash
make check
```

Full suite:

```bash
make test
```

Targeted examples:

```bash
uv run pytest tests/test_hied_mode.py -q
uv run pytest tests/test_single_mode.py tests/test_runner_artifacts.py -q
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

Run the paper-aligned HiED config:

```bash
uv run culturedx run \
  -c configs/base.yaml \
  -c configs/vllm_awq.yaml \
  -c configs/v2.4_final.yaml \
  -d lingxidiag16k \
  --data-path data/raw/lingxidiag16k \
  -n 1000
```

Run the single-model baseline:

```bash
uv run culturedx run \
  -c configs/base.yaml \
  -c configs/vllm_awq.yaml \
  -c configs/single_baseline.yaml \
  -d lingxidiag16k \
  --data-path data/raw/lingxidiag16k \
  -n 1000
```

Plan a sweep without executing it:

```bash
uv run culturedx sweep \
  -c configs/base.yaml \
  -c configs/datasets/lingxidiag16k.yaml \
  -d lingxidiag16k \
  --dry-run
```

Common Make targets:

```bash
make eval-v24
make eval-single
make table4-all
make results-table
```

## Coding Conventions

- Python 3.11+ with type hints.
- Prefer deterministic tests and lightweight fixtures.
- Use explicit `encoding="utf-8"` for file I/O.
- Keep failure behavior machine-readable with `FailureInfo` where practical.
- Keep scope semantics explicit; do not reintroduce hidden closed-set defaults.
- Do not assume English prompt templates exist just because some code paths
  accept `language="en"`.
- Keep diffs reviewable and avoid unrelated refactors.

## Review Checklist

- `mode.target_disorders`, `scope_policy`, and `execution_mode` semantics are
  explicit in config, output, or both.
- New or changed outputs preserve canonical artifacts, or the compatibility
  impact is documented.
- `predictions.jsonl`, `failures.jsonl`, and `stage_timings.jsonl` remain
  machine-joinable by `run_id` and `case_id`.
- Tests are added or updated for changed behavior.
- Commands in docs and comments use config files that actually exist in this
  branch.
- Benchmark and paper claims are grounded in committed artifacts, not fixtures
  or demo data.

## Artifact And Output Conventions

Canonical run artifacts:

- `run_manifest.json`
- `case_selection.json`
- `predictions.jsonl`
- `failures.jsonl`
- `stage_timings.jsonl`
- `metrics_summary.json`
- `summary.md`

Compatibility artifacts still emitted by `ExperimentRunner`:

- `run_info.json`
- `metrics.json`

Current prediction records include:

- `schema_version`
- `run_id`
- `case_id`
- `order_index`
- `dataset`
- `gold_diagnoses`
- `primary_diagnosis`
- `comorbid_diagnoses`
- `confidence`
- `decision`
- `mode`
- `model_name`
- `prompt_hash`
- `language_used`
- `routing_mode`
- `scope_policy`
- `candidate_disorders`
- `decision_trace`
- `stage_timings`
- `failures`

Current failure rows include:

- `schema_version`
- `run_id`
- `case_id`
- `source`
- `code`
- `stage`
- `message`
- `recoverable`
- `details`

Evidence is not written as a standalone canonical artifact by the current
runner. Evidence-derived failures and timings are flattened into
`failures.jsonl` and `stage_timings.jsonl`.

## Clinical Safety And Abstention Rules

- This repository is for research and system development, not clinical use.
- Prefer abstention when language is unsupported, routing fails, or evidence is
  weak.
- Do not silently narrow the disorder search space in production-style paths.
- Do not invent diagnoses, confidence numbers, or empirical claims not backed
  by committed artifacts.

## Benchmark Mode vs Production Mode

- In `HiEDMode`, `scope_policy: auto` resolves to `manual` when
  `mode.target_disorders` is set; otherwise it resolves to `triage`.
- In `HiEDMode`, `execution_mode: auto` resolves to
  `benchmark_manual_scope` for manual scope and `production_open_set`
  otherwise.
- `manual` scope requires explicit `target_disorders`.
- Open-set production runs must not set `target_disorders`.
- `all_supported` is available when the caller explicitly wants the full
  supported ontology instead of triage filtering.

## Result And Fixture Hygiene

- `results/validation/*` contains committed validation analyses; treat those as
  reference artifacts, not autogenerated scratch output.
- Synthetic fixtures under `tests/fixtures/` are for deterministic testing only.
- Do not report fixture-driven outputs as empirical benchmark results.

## Further Reading

- `README.md`
  top-level repo overview and primary run examples.
- `results/validation/README.md`
  committed validation summary and analysis notes.
- `paper/README.md`
  paper-material layout and reproduction context.
- `prompts/CHANGELOG.md`
  prompt-history notes for agent and single-model templates.
