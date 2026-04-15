# CultureDx: Diagnose-then-Verify for Chinese Psychiatric Diagnosis

CultureDx is a multi-agent system (MAS) for Chinese psychiatric
differential diagnosis, benchmarked on LingxiDiag-16K.

## Key Results

- **Overall 0.527** on LingxiDiag-16K validation (N=1000)
- Beats all 15 LLM baselines (GPT-5-Mini, Grok-4.1, Claude-Haiku-4.5, etc.)
- Within 0.006 of TF-IDF+LR (0.533)
- DtV > Single across all tested backbones (Qwen3 8B–32B)

## Architecture: Diagnose-then-Verify (DtV)

```
Transcript ──→ [Triage] ──→ [RAG Retrieval] ──→ [Diagnostician]
                                                      │
                                            ranked candidates
                                                      │
                                              [Criterion Checker] ×2
                                                      │
                                              [Logic Engine]
                                                      │
                                              [Comorbidity Gate]
                                                      │
                                              Final Diagnosis
```

1. **Triage**: Routes to relevant ICD-10 categories
2. **RAG Retrieval**: Retrieves similar cases from train split (FAISS + BGE-M3)
3. **Diagnostician**: Ranks candidate disorders with clinical reasoning
4. **Criterion Checker**: Verifies top-2 candidates against ICD-10 criteria
5. **Logic Engine**: Applies structured ICD-10 threshold rules
6. **Comorbidity Gate**: Enforces ICD-10 forbidden pairs

## Supported Disorders

| Category | Disorders |
|----------|-----------|
| Mood | F31 (Bipolar), F32 (Depression), F33 (Recurrent), F39 (Unspecified) |
| Anxiety | F40 (Phobic), F41.0 (Panic), F41.1 (GAD), F41.2 (Mixed), F42 (OCD) |
| Stress | F43.1 (PTSD), F43.2 (Adjustment) |
| Psychotic | F20 (Schizophrenia), F22 (Delusional) |
| Other | F45 (Somatoform), F51 (Sleep), F98 (Behavioral), Z71 (Counseling) |

## Quick Start

```bash
git clone https://github.com/OscarTsao/CultureDx.git
cd CultureDx
pip install -e .

# Start vLLM
vllm serve Qwen/Qwen3-32B-AWQ --port 8000 --max-model-len 8192

# Run DtV pipeline (validation split, N=1000)
uv run culturedx run \
  -c configs/base.yaml -c configs/vllm_awq.yaml -c configs/v2.4_final.yaml \
  -d lingxidiag16k --data-path data/raw/lingxidiag16k -n 1000

# Run single baseline
uv run culturedx run \
  -c configs/base.yaml -c configs/vllm_awq.yaml -c configs/single_baseline.yaml \
  -d lingxidiag16k --data-path data/raw/lingxidiag16k -n 1000
```

## Project Structure

```
CultureDx/
├── src/culturedx/
│   ├── agents/          # Triage, Diagnostician, Criterion Checker
│   ├── diagnosis/       # Logic engine, Comorbidity, Calibrator
│   ├── modes/           # DtV (hied.py) and Single baseline
│   ├── ontology/        # ICD-10 criteria and disorder definitions
│   ├── eval/            # Metrics aligned with LingxiDiagBench Table 4
│   └── data/adapters/   # Dataset adapters (LingxiDiag-16K, MDD-5K)
├── configs/             # YAML configs for all experiments
├── prompts/             # Jinja templates for all agents
├── results/validation/  # Official validation split results
└── scripts/             # Evaluation and analysis utilities
```

## Benchmark

Evaluated on [LingxiDiag-16K](https://huggingface.co/datasets/XuShihao6715/LingxiDiag-16K)
validation split using the [LingxiDiagBench](https://github.com/Lingxi-mental-health/LingxiDiagBench)
evaluation protocol (Table 4: 2c/4c/12c classification).

## License

See LICENSE file.
