# CultureDx Validation Results

All results on LingxiDiag-16K **validation split** (N=1000).
Backbone: Qwen3-32B-AWQ (unless noted).
scope_policy: manual (all target disorders checked, no triage filtering).

## Ablation Table

| Dir | Config | Overall |
|-----|--------|---------|
| 01 | Single baseline (paper 12c prompt) | .482 |
| 02 | Single + RAG label-only | .469 |
| 03 | DtV V1 (V1 prompts, no RAG) | .475 |
| 04 | DtV V1 + RAG label-only | .480 |
| 05 | DtV V2 + RAG (best system) | .527 |
| 06 | DtV V2 + RAG + comorbidity gate | .526 |

Best system: **05_dtv_v2_rag** (Overall = 0.527)

Row 05 vs 06: gate effect is +1/1000 cases (forbidden pair F32+F20).
The comorbidity gate is a safety net, not a performance driver.

## Multi-backbone (in progress)

| Dir | Model | Config | Overall |
|-----|-------|--------|---------|
| qwen3_8b_single | Qwen3-8B (BF16) | Single | .318 |
| qwen3_8b_dtv | Qwen3-8B (BF16) | DtV V2+RAG | .508 |

## Gate Analysis
- Isolated effect: +1/1000 cases (F32+F20 forbidden pair correctly removed)
- Row 06 vs 05: near-identical (within LLM non-determinism)
- See `gate_rescore_analysis.json`

## Abstention Analysis
- Oracle ceiling: +0.037 Overall if Z71/Others perfectly detected
- Practical: no threshold-based strategy beats baseline
- Checker over-confirms criteria even for Z71 cases (mean met_ratio=0.72)
- See `abstention_corrected_analysis.json`

## File structure per experiment
- `metrics.json` — Full metrics (diagnosis, comorbidity, four_class, table4)
- `predictions.jsonl` — Per-case predictions
- `run_info.json` — Config, git hash, timestamp

## Evaluation protocol
- 2c/4c: Paper official prompts (independent LLM calls)
- 12c: From DtV pipeline (or single prompt for baselines)
- Overall = mean of 11 metrics (2c x 3 + 4c x 3 + 12c x 5)
- No EMR metadata used at runtime (scope_policy=manual bypasses triage)
