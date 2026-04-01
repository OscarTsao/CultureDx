# CultureDx

CultureDx is a culture-adaptive psychiatric differential-diagnosis research
repo focused on Chinese and English clinical transcripts. The codebase
combines evidence extraction, ICD-10 criterion checking, deterministic logic,
and statistical calibration to produce diagnosis or abstention outputs.

This repository is still a research/prototype codebase, not a validated
clinical product. Do not claim benchmark wins, production readiness, or
clinical efficacy unless the supporting artifacts are committed and
reproducible from this repo.

## What The System Does

- Normalizes multiple datasets into a shared `ClinicalCase` model.
- Extracts evidence from transcripts, including Chinese somatization mapping.
- Routes cases through several diagnosis modes:
  `single`, `mas`, `hied`, `psycot`, `specialist`, and `debate`.
- Applies deterministic ICD-10 threshold rules and a statistical calibrator.
- Emits machine-readable predictions, metrics, and failure/abstention signals.

## Current Architecture

The main research path is `HiED`:

1. Scope resolution:
   `manual` benchmark scope, `triage`-derived scope, or `all_supported`.
2. Triage:
   broad ICD-10 category routing when running production-style open-set flows.
3. Criterion checking:
   per-disorder checker fanout.
4. Logic engine:
   deterministic ICD-10 threshold evaluation.
5. Calibrator:
   statistical confidence scoring, abstention, and comorbidity candidate split.
6. Comorbidity resolver:
   exclusion rules plus confidence/rule-based filtering.

Evidence extraction is a separate pipeline:

1. Symptom span extraction.
2. Chinese somatization normalization.
3. Criterion retrieval/matching.
4. Evidence brief assembly.

See [architecture.md](/home/user/YuNing/CultureDx/docs/architecture.md) for the
system walkthrough.

## Supported Modes

- `single`: single-model baseline.
- `mas`: checker plus differential synthesis.
- `hied`: hierarchical evidence-grounded pipeline; primary path for diagnosis
  logic work.
- `psycot`: flat criterion checking without triage.
- `specialist`: specialist-agent ensemble.
- `debate`: debate-style ensemble with judge.

## Benchmark Mode vs Production Mode

Two execution semantics now matter explicitly:

- Closed-set benchmark/manual scope:
  set `mode.target_disorders` and `mode.scope_policy: manual`.
  `HiED` reports `routing_mode=benchmark_manual_scope`.
- Production-style open-set routing:
  omit `mode.target_disorders`; `HiED` resolves `scope_policy=triage` by
  default and reports `routing_mode=production_open_set`.

For the evidence pipeline, `scope_policy=auto` no longer silently narrows to
`F32/F41.1`. It resolves to:

- `manual` when explicit target disorders are configured.
- `all_supported` when no explicit scope is provided.
- `triage` only when the caller passes triage-derived candidate disorders.

## Maturity Level

What is already present:

- Solid local test coverage for core models, evidence modules, modes, metrics,
  and helpers.
- Deterministic ICD-10 logic and statistical calibration components.
- Ollama and vLLM client support.

What is still research/prototype grade:

- Calibration/training artifacts are not yet standardized across all flows.
- Some routing/calibration/evidence features still rely on heuristics.
- Evaluation scripts and outputs are not yet fully unified.

## Local Setup

```bash
uv sync
```

Optional retrieval extras:

```bash
uv pip install -e ".[retrieval]"
```

## Common Commands

```bash
make check
uv run pytest -q
uv run culturedx --help
uv run culturedx smoke
```

Run HiED in closed-set benchmark/manual mode:

```bash
uv run culturedx run \
  -c configs/base.yaml \
  -c configs/hied.yaml \
  -d mdd5k \
  --data-path data/raw/mdd5k
```

Run with evidence extraction enabled:

```bash
uv run culturedx run \
  -c configs/base.yaml \
  -c configs/hied.yaml \
  -d mdd5k \
  --with-evidence \
  --data-path data/raw/mdd5k
```

Dry-run an ablation sweep:

```bash
uv run culturedx sweep \
  -c configs/base.yaml \
  -c configs/hied.yaml \
  -d mdd5k \
  --dry-run
```

## Evaluation And Artifacts

Current run directories typically contain:

- `run_manifest.json`
- `run_info.json`
- `predictions.jsonl`
- `failures.jsonl`
- `stage_timings.jsonl`
- `metrics.json` when ground truth is available
- `metrics_summary.json`
- `summary.md`

Prediction records come from `DiagnosisResult`. They may include:

- `decision`
- `routing_mode`
- `scope_policy`
- `candidate_disorders`
- `decision_trace`
- `failure` / `failures`

Evidence outputs (`EvidenceBrief`) may include:

- `scope_policy`
- `target_disorders`
- `failures`
- `stage_timings`

`run_info.json` and `metrics.json` remain as legacy-compatible outputs; the
canonical task-6 artifacts are `run_manifest.json`, `metrics_summary.json`,
`failures.jsonl`, and `stage_timings.jsonl`.

## Safety And Reporting Rules

- Treat all diagnosis outputs as research artifacts, not clinical advice.
- Prefer abstention over overclaiming when evidence is weak or routing fails.
- Do not fabricate training results, benchmark numbers, or calibration
  artifacts.
- If a calibration artifact or model is unavailable, use a documented fallback
  path instead of inventing parameters.

## Repo Docs

- [AGENTS.md](/home/user/YuNing/CultureDx/AGENTS.md)
- [developer_guide.md](/home/user/YuNing/CultureDx/docs/developer_guide.md)
- [study_overview.md](/home/user/YuNing/CultureDx/docs/study_overview.md)
- [architecture.md](/home/user/YuNing/CultureDx/docs/architecture.md)
- [operations.md](/home/user/YuNing/CultureDx/docs/operations.md)
- [triage-routing.md](/home/user/YuNing/CultureDx/docs/triage-routing.md)
- [somatization_benchmark.md](/home/user/YuNing/CultureDx/docs/somatization_benchmark.md)
