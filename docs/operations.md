# Operations

## Local Development

Install dependencies:

```bash
uv sync
```

Optional retrieval extras:

```bash
uv pip install -e ".[retrieval]"
```

Basic validation:

```bash
make check
uv run pytest -q
uv run culturedx smoke
```

## Ollama Setup

Default local backend:

```bash
ollama serve
```

Typical CultureDx run config points at:

- base URL: `http://localhost:11434`
- model examples: `qwen3:14b`, `qwen3:32b`

## vLLM Setup

Example from repo config comments:

```bash
vllm serve Qwen/Qwen3-32B --tensor-parallel-size 1 --max-model-len 32768 \
  --gpu-memory-utilization 0.9 --dtype auto --port 8000
```

Then run:

```bash
uv run culturedx run -c configs/base.yaml -c configs/vllm_32b.yaml -d mdd5k --data-path data/raw/mdd5k
```

## Recommended Test Commands

Fast targeted checks:

```bash
uv run pytest tests/test_cli.py tests/test_evidence_pipeline.py tests/test_calibrator.py tests/test_comorbidity.py tests/test_hied_mode.py -q
```

Mode/e2e checks:

```bash
uv run pytest tests/test_hied_mode.py tests/test_hied_e2e.py -q
```

Full local suite:

```bash
uv run pytest -q
```

## Artifact Schema Overview

Current run directories normally contain:

- `run_manifest.json`
  canonical run metadata including config fingerprint.
- `run_info.json`
  legacy-compatible metadata mirror.
- `predictions.jsonl`
  serialized `DiagnosisResult` rows.
- `failures.jsonl`
  flattened machine-readable failure events.
- `stage_timings.jsonl`
  flattened evidence/diagnosis stage timing rows.
- `metrics.json`
  legacy-compatible metrics file.
- `metrics_summary.json`
  canonical metrics artifact with slice summaries.
- `summary.md`
  reviewer-friendly markdown summary.

Current `DiagnosisResult` fields of operational interest:

- `decision`
- `confidence`
- `routing_mode`
- `scope_policy`
- `candidate_disorders`
- `decision_trace`
- `failure` / `failures`

Current `EvidenceBrief` fields of operational interest:

- `scope_policy`
- `target_disorders`
- `failures`
- `stage_timings`

## Rollout, Canary, And Shadow-Eval Guidance

For any production-style routing change:

1. Preserve a benchmark/manual-scope baseline for comparison.
2. Run shadow evaluation before changing default routing behavior.
3. Track abstention rate, candidate set size, and failure-code frequency.
4. Review error slices manually before enabling broader traffic.
5. Do not treat fallback-to-all-supported as equivalent to a validated
   open-set router.

## Clinical Safety Rules

- No fabricated benchmark claims.
- No fabricated trained artifacts.
- Unsupported language should abstain, not guess.
- Hidden disorder-scope narrowing is not acceptable in production-style paths.
