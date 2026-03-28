# Triage Routing

The triage agent now produces a structured routing payload instead of only a flat category list. The output is still backward-compatible with existing consumers because `categories` and `disorder_codes` remain present.

## Output Schema

Each triage response includes:

- `raw_category_scores`: raw LLM confidence per category
- `calibrated_category_scores`: calibrated scores if an artifact is loaded
- `categories`: per-category routing records with raw score, calibrated score, selection flag, and disorder codes
- `selected_categories`: categories selected for downstream checking
- `candidate_disorder_codes` / `disorder_codes`: flattened ICD-10 codes for selected categories
- `uncertainty`, `open_set_score`, `out_of_scope_score`
- `routing_mode`: `calibrated` or `heuristic_fallback`
- `calibration_status`: `loaded` or `fallback`
- `fallback_reason`: why fallback behavior was used

## Calibration Artifact

Artifacts are JSON files with the following core fields:

- `method`: currently `temperature_scaling`
- `temperature`: positive scalar applied to raw scores
- `categories`: optional category inventory captured during fitting
- `metadata`: fitting provenance
- `validation_metrics`: optional evaluation summary

If the artifact is missing or invalid, the agent falls back to identity calibration and keeps routing functional.

## Dataset Format For Fitting

`scripts/train_triage_calibration.py` consumes JSONL records with this minimal shape:

```json
{
  "example_id": "case-001",
  "gold_categories": ["mood", "anxiety"],
  "raw_category_scores": {
    "mood": 0.91,
    "anxiety": 0.33,
    "sleep": 0.12
  }
}
```

The loader also accepts `scores` or `categories` lists with `confidence` values.

## Recommended Workflow

1. Export triage training examples into JSONL.
2. Fit a calibration artifact with `scripts/train_triage_calibration.py`.
3. Pass the saved artifact path to `TriageAgent`.
4. Evaluate recall@k, ECE, Brier score, candidate-set size, and risk-coverage before using the artifact in production-style routing.

The artifact should be treated as a routing aid, not evidence of model quality by itself. Report metrics only from reproducible data and committed artifacts.
