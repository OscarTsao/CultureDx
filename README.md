# CultureDx: Culture-Adaptive Diagnostic Multi-Agent System with Evidence Grounding

**CultureDx** is a multi-agent system (MAS) for Chinese psychiatric differential diagnosis and comorbidity detection, grounded in ICD-10 clinical criteria and culture-aware evidence extraction.

## Key Contributions

- **Evidence-grounded MAS architecture** that outperforms single-LLM baselines for Chinese psychiatric diagnosis by decomposing clinical reasoning into specialized agent roles
- **Culture-aware somatization mapping** — a 150-entry ontology linking Chinese somatic expressions (e.g., "胸闷", "头晕") to ICD-10 diagnostic criteria, addressing the gap between Chinese clinical presentation and Western diagnostic frameworks
- **Hybrid evidence pipeline** — 3-layer temporal extraction (regex + ChineseTimeNLP + stanza NER), scope-aware negation detection, and BGE-M3 native hybrid retrieval (dense + sparse + ColBERT)
- **Deterministic diagnostic logic** — ICD-10 threshold rules and statistical calibration ensure reproducible, auditable diagnosis decisions separate from LLM uncertainty
- **5 MAS architectures** compared: HiED (hierarchical), PsyCoT (flat), Specialist, Debate, and Single-model baseline

## Architecture

```
                    ┌─────────────┐
                    │  Clinical    │
                    │  Transcript  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Evidence    │  extract → somatize → retrieve → match
                    │  Pipeline    │
                    └──────┬──────┘
                           │
              ┌────────────▼────────────┐
              │     HiED Pipeline       │
              │                         │
              │  1. Triage Agent        │  LLM: broad ICD-10 routing
              │  2. Criterion Checkers  │  LLM: per-disorder evaluation
              │  3. Logic Engine        │  Deterministic: ICD-10 thresholds
              │  4. Calibrator          │  Statistical: confidence scoring
              │  5. Comorbidity         │  Rule-based: ICD-10 exclusions
              │                         │
              └────────────┬────────────┘
                           │
                    ┌──────▼──────┐
                    │  Diagnosis   │
                    │  Result      │  primary + comorbid + abstain
                    └─────────────┘
```

## Supported Disorders (15 ICD-10 codes)

| Category | Disorders |
|----------|-----------|
| Mood | F31 (Bipolar), F32 (Depressive episode), F33 (Recurrent depression), F39 (Unspecified mood) |
| Anxiety | F40 (Phobic), F41.0 (Panic), F41.1 (GAD), F42 (OCD) |
| Stress | F43.1 (PTSD), F43.2 (Adjustment) |
| Psychotic | F20 (Schizophrenia), F22 (Delusional) |
| Other | F45 (Somatoform), F51 (Sleep), F98 (Behavioral/emotional) |

## Datasets

| Dataset | Cases | Language | Source |
|---------|-------|----------|--------|
| [LingxiDiag-16K](https://huggingface.co/datasets/Lingxin-Intelligence/LingxiDiag-16K) | ~14,000 | Chinese | Real clinical transcripts |
| [MDD-5k](https://github.com/linhaowei1/MDD-5k) | 925 | Chinese | Simulated clinical interviews |

## Installation

```bash
# Clone
git clone https://github.com/OscarTsao/CultureDx.git
cd CultureDx

# Install (requires Python >= 3.11)
uv sync

# Optional: retrieval support (BGE-M3)
uv pip install -e ".[retrieval]"

# Verify
uv run pytest -q
uv run culturedx --help
```

## Quick Start

```bash
# Smoke test
uv run culturedx smoke

# Run HiED pipeline on MDD-5k
uv run culturedx run \
  -c configs/base.yaml \
  -c configs/hied.yaml \
  -d mdd5k \
  --data-path data/raw/mdd5k

# Run with evidence extraction
uv run culturedx run \
  -c configs/base.yaml \
  -c configs/hied.yaml \
  -d mdd5k \
  --with-evidence \
  --data-path data/raw/mdd5k

# Ablation sweep
uv run culturedx sweep \
  -c configs/base.yaml \
  -c configs/hied.yaml \
  -d mdd5k \
  --modes hied,single \
  --dry-run
```

## LLM Backend

CultureDx supports two backends:

| Backend | Config | Use Case |
|---------|--------|----------|
| [Ollama](https://ollama.ai) | `configs/base.yaml` | Local development |
| [vLLM](https://docs.vllm.ai) | `configs/vllm_awq.yaml` | Production evaluation |

Recommended models: Qwen3-32B-AWQ (teacher/eval), Qwen3-8B (finetuned student)

## Project Structure

```
src/culturedx/
  core/          Config models, data structures
  data/adapters/ Dataset normalization (LingxiDiag, MDD-5k, E-DAIC)
  llm/           Ollama/vLLM clients, cache, JSON parsing
  evidence/      Symptom extraction, somatization, retrieval, negation
  agents/        Triage, criterion checker, differential, specialist, judge
  diagnosis/     Logic engine, calibrator, comorbidity resolver
  modes/         HiED, PsyCoT, Specialist, Debate, Single orchestrators
  ontology/      ICD-10 criteria definitions, somatization mapping
  eval/          Metrics, reports, code mapping
  pipeline/      CLI, runner, sweep
configs/         YAML configuration overlays
prompts/agents/  Bilingual Jinja2 prompt templates
scripts/         Evaluation, finetuning, teacher data generation
tests/           561 unit tests (deterministic, no GPU required)
paper/           Paper drafts, figures, and supplementary materials
```

## Evaluation Output

Each run produces:
- `predictions.jsonl` — per-case diagnosis predictions
- `metrics.json` — accuracy, F1, precision, recall with bootstrap CIs
- `failures.jsonl` — abstention and error records
- `stage_timings.jsonl` — per-stage latency measurements
- `summary.md` — human-readable evaluation report

## Disclaimer

This system is a **research prototype** for academic investigation. All diagnostic outputs are research artifacts — not validated clinical advice. Do not use for actual clinical decision-making.

## Citation

```bibtex
@misc{culturedx2026,
  title={CultureDx: Culture-Adaptive Diagnostic Multi-Agent System with Evidence Grounding for Chinese Psychiatric Differential Diagnosis},
  author={Tsao, Yu-Ning},
  year={2026},
  url={https://github.com/OscarTsao/CultureDx}
}
```

## License

This project is licensed under the Apache License 2.0 — see [LICENSE](LICENSE) for details.
