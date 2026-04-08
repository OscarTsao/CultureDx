# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CultureDx:** Culture-Adaptive Diagnostic MAS with Evidence Grounding for Chinese psychiatric differential diagnosis and comorbidity detection.

**Core thesis:** Evidence-grounded MAS outperforms single LLMs for Chinese psychiatric diagnosis because LLMs have weak parametric knowledge of Chinese clinical presentations, somatization requires explicit culture-aware mapping, and differential/comorbid diagnosis requires genuine agent asymmetry.

This is a research/prototype codebase, not a validated clinical product.

## Commands

```bash
# Setup
uv sync
uv pip install -e ".[retrieval]"   # optional: adds BGE-M3 retriever

# Fast repo check (core tests only)
make check

# Full test suite
uv run pytest -q

# Single test file / specific test
uv run pytest tests/test_hied_mode.py -v
uv run pytest tests/test_calibrator.py::test_abstention -v

# Skip tests requiring Ollama
uv run pytest -m "not integration"

# CLI
uv run culturedx --help
uv run culturedx smoke
```

### Running experiments

Configs layer with multiple `-c` flags (later files override earlier):

```bash
# HiED benchmark (closed-set, manual scope)
uv run culturedx run -c configs/base.yaml -c configs/hied.yaml -d mdd5k --data-path data/raw/mdd5k

# With evidence extraction
uv run culturedx run -c configs/base.yaml -c configs/hied.yaml -d mdd5k --with-evidence --data-path data/raw/mdd5k

# Ablation sweep (dry-run first)
uv run culturedx sweep -c configs/base.yaml -c configs/hied.yaml -d mdd5k --dry-run
uv run culturedx sweep -c configs/base.yaml -d mdd5k --modes hied,single -n 50
```

## Architecture

Source lives in `src/culturedx/`. Entry point: `pipeline/cli.py` (Click CLI) → `pipeline/runner.py` (ExperimentRunner).

### Data flow

All datasets (LingxiDiag16k, MDD-5k, E-DAIC) normalize to `ClinicalCase` via adapters in `data/adapters/`. The PDCH adapter exists but is unused (restricted data).

### Diagnosis modes (in `modes/`)

6 modes, all subclass `BaseModeOrchestrator`:

- **`hied`** — Primary research path. 4-stage pipeline:
  1. Scope resolution → triage (open-set) or manual scope (benchmark)
  2. Criterion checker fanout (one per candidate disorder, uses `agents/criterion_checker.py`)
  3. Logic engine — deterministic ICD-10 threshold rules (`diagnosis/logic_engine.py`, no LLM)
  4. Calibrator — statistical confidence scoring + abstention (`diagnosis/calibrator.py`, no LLM) → comorbidity resolver (`diagnosis/comorbidity.py`)
- **`single`** — Single-model baseline (zero-shot/few-shot)
- **`mas`** — Criterion checker + differential synthesis
- **`psycot`** — Flat criterion checking, no triage (checks ALL disorders)
- **`specialist`** — Triage → specialist agents → LLM judge
- **`debate`** — 4 perspectives (bio/psych/social/cultural) × 2 rounds → judge

### Evidence pipeline (in `evidence/`)

Separate from diagnosis modes; activated with `--with-evidence`:

extract symptoms → somatize (Chinese only, via `ontology/symptom_map.py` then LLM fallback) → match criteria → assemble `EvidenceBrief`

### LLM layer (in `llm/`)

`OllamaClient` supports Ollama and vLLM backends. All calls are greedy (temperature=0.0, top_k=1). Responses cached in SQLite keyed by `{provider}:{model}:{prompt_hash}:{language}:{input_hash}`.

### Prompts

Bilingual (Chinese/English) Jinja2 templates in `prompts/agents/`.

## Benchmark Mode vs Production Mode

Two execution semantics that must stay explicit in configs and outputs:

- **Closed-set benchmark** (`scope_policy: manual`): set `mode.target_disorders` explicitly. HiED reports `routing_mode=benchmark_manual_scope`.
- **Production open-set** (`scope_policy: triage` or `all_supported`): omit `mode.target_disorders`. HiED uses triage or full ontology. Reports `routing_mode=production_open_set`.

For evidence pipeline, `scope_policy: auto` resolves to `manual` when targets configured, otherwise `all_supported`. It does NOT silently narrow to F32/F41.1.

## Key Invariants

1. `DiagnosisResult.decision` is always `"diagnosis"` or `"abstain"`
2. No gold features at inference — system never peeks at ground truth
3. Logic engine uses ICD-10 threshold dispatch: `core_total`, `first_rank`, `min_symptoms`, etc.
4. Comorbidity hierarchy: F33 supersedes F32, F31 supersedes F32/F33, F20 supersedes F22
5. Somatization mapper: ontology lookup first, LLM fallback only for unknown somatic symptoms
6. Do not silently narrow disorder search space in production-style paths
7. Prefer abstention when routing fails or evidence is weak

## Run Artifacts

Each run directory produces:

- `run_manifest.json`, `predictions.jsonl`, `failures.jsonl`, `stage_timings.jsonl` — canonical outputs
- `metrics_summary.json`, `summary.md` — when ground truth available
- `run_info.json`, `metrics.json` — legacy-compatible

## Code Conventions

- Python 3.11+, PEP 8, max line length 100
- Type hints everywhere
- All file I/O: explicit `encoding="utf-8"`
- Tests: deterministic (fixed seeds), no GPU required, no private data
- Keep diffs reviewable; avoid unrelated refactors
- Do not fabricate benchmark numbers, calibration artifacts, or learned weights
