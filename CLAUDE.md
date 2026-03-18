# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

**CultureDx:** Culture-Adaptive Diagnostic MAS with Evidence Grounding for Chinese psychiatric differential diagnosis and comorbidity detection.

**Core thesis:** Evidence-grounded MAS outperforms single LLMs for Chinese psychiatric diagnosis because LLMs have weak parametric knowledge of Chinese clinical presentations, somatization requires explicit culture-aware mapping, and differential/comorbid diagnosis requires genuine agent asymmetry.

## Commands

```bash
# Setup
uv sync

# Run tests
uv run pytest -q
uv run pytest tests/test_models.py -v
uv run pytest -m "not integration"

# CLI
uv run culturedx --help
uv run culturedx smoke
uv run culturedx run --config configs/base.yaml --dataset mdd5k
uv run culturedx run --config configs/base.yaml --dataset mdd5k --with-evidence

# Install with retrieval (BGE-M3)
uv pip install -e ".[retrieval]"
```

## Package Architecture (src/culturedx/)

| Module | Purpose |
|--------|---------|
| core/config.py | Pydantic config models (all YAML fields) |
| core/models.py | Data structures (ClinicalCase, EvidenceBrief, DiagnosisResult) |
| data/adapters/ | Dataset adapters (MDD-5k, PDCH, E-DAIC) → ClinicalCase |
| llm/client.py | OllamaClient (temperature=0, top_k=1 = greedy) |
| llm/cache.py | SQLite-backed LLM response cache |
| llm/json_utils.py | JSON extraction from LLM responses |
| agents/base.py | BaseAgent ABC |
| agents/criterion_checker.py | CriterionCheckerAgent: per-disorder ICD-10 criteria evaluation |
| agents/differential.py | DifferentialDiagnosisAgent: cross-disorder differential synthesis |
| modes/base.py | BaseModeOrchestrator ABC |
| modes/single.py | Single-model baseline (zero-shot/few-shot) |
| modes/mas.py | MASMode orchestrator: checker + differential pipeline |
| eval/metrics.py | Diagnosis and severity metrics |
| pipeline/runner.py | ExperimentRunner |
| pipeline/cli.py | Click CLI entry point |
| evidence/extractor.py | LLM-based symptom span extraction |
| evidence/somatization.py | Chinese somatization mapper (ontology + LLM fallback) |
| evidence/retriever.py | BaseRetriever ABC, MockRetriever, BGEM3Retriever |
| evidence/criteria_matcher.py | Per-criterion evidence retrieval with somatization boost |
| evidence/brief.py | Evidence Brief assembly per-disorder per-criterion |
| evidence/pipeline.py | End-to-end evidence extraction orchestrator |
| ontology/icd10.py | ICD-10 criterion definitions (13 disorders) |
| ontology/symptom_map.py | Chinese somatic symptom → criterion mapping (38 entries) |
| prompts/agents/ | Bilingual Jinja2 prompts for MAS agents |
| eval/evidence_metrics.py | Criterion coverage, evidence precision |

## Key Invariants

1. All LLM calls via OllamaClient with temperature=0.0, top_k=1 (greedy)
2. LLM cache key: {provider}:{model}:{prompt_hash}:{language}:{input_hash}
3. All datasets normalize to ClinicalCase dataclass
4. DiagnosisResult.decision is "diagnosis" or "abstain"
5. No gold features at inference
6. Somatization mapper: ontology lookup first, LLM fallback for unknown somatic symptoms
7. EvidenceBrief uses DisorderEvidence (per-disorder) as primary structure
8. Retriever optional dep: sentence-transformers only needed for BGEM3Retriever
9. Evidence pipeline: extract → somatize (Chinese only) → match → assemble
10. MAS mode: criterion checker per disorder → differential diagnosis synthesis

## Code Conventions

- PEP 8, max line length 100
- All file I/O: explicit encoding="utf-8"
- Type hints everywhere
- Tests: deterministic (fixed seeds), no GPU required, no private data
