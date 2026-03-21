# Comorbidity Evaluation Wiring — Design Spec

## Problem

`compute_comorbidity_metrics` (7 metrics) exists in `eval/metrics.py` but is never called.
All predictions.json files include `comorbid_diagnoses` but no analysis evaluates them.
The LingxiDiag 4-class task (depression/anxiety/mix/other, baseline 43.0%) has never been run.

## Scope (Option C)

1. Wire `compute_comorbidity_metrics` into `ExperimentRunner.evaluate()` for all future runs
2. Create `scripts/analyze_comorbidity.py` for retrospective evaluation of existing predictions
3. Add LingxiDiag 4-class task evaluation against `four_class_label` gold

## Design

### Component 1: ExperimentRunner wiring

In `src/culturedx/pipeline/runner.py`, `evaluate()` method, after existing diagnosis metrics:

```python
from culturedx.eval.metrics import compute_comorbidity_metrics

# ... existing code builds preds, golds ...

# New: comorbidity metrics
comorbid_metrics = compute_comorbidity_metrics(preds, golds)
metrics["comorbidity"] = comorbid_metrics
```

**Impact:** Zero — adds an output key, no behavioral change. All future sweeps automatically produce comorbidity metrics.

### Component 2: `scripts/analyze_comorbidity.py`

Single retrospective analysis script. Inputs: sweep directory path(s). For each condition:

1. Load `predictions.json` → extract `{primary_diagnosis, comorbid_diagnoses}` per case
2. Load gold labels from dataset (auto-detect dataset from case_id patterns or prediction metadata)
3. Build `preds = [[primary] + comorbid]` and `golds = [case.diagnoses]` per case
4. Call `compute_comorbidity_metrics(preds, golds, normalize="parent")` → 7 metrics
5. For LingxiDiag: also compute 4-class accuracy (see Component 3)
6. Print summary table, save `comorbidity_metrics.json` next to predictions

**CLI interface:**
```bash
uv run python scripts/analyze_comorbidity.py \
    --sweep-dirs outputs/sweeps/v10_lingxidiag_* outputs/sweeps/contrastive_*_lingxidiag_* \
    --dataset lingxidiag16k
```

### Component 3: LingxiDiag 4-class mapping

**Mapping rules (validated against raw data):**

| 4-class label | Our prediction pattern | Gold ICD codes |
|---------------|----------------------|----------------|
| Depression | F32.x or F33.x only | F32.x |
| Anxiety | F40.x or F41.x only | F41.0, F41.1, F41.9 |
| Mixed | Both depression (F32/F33) AND anxiety (F40/F41) | F41.2 |
| Other | Everything else (F42, F43, F39, F51, etc.) | F39, F42, F43, F45, F51, F98, ... |

**Critical:** F42 (OCD) and F43 (PTSD) map to "Other", NOT "Anxiety". The Anxiety class in LingxiDiag is exclusively F40/F41.

```python
def predict_four_class(primary: str | None, comorbid: list[str]) -> str:
    all_codes = [c for c in [primary] + (comorbid or []) if c]
    has_dep = any(c.startswith("F32") or c.startswith("F33") for c in all_codes)
    has_anx = any(c.startswith("F40") or c.startswith("F41") for c in all_codes)
    if has_dep and has_anx:
        return "Mixed"
    if has_dep:
        return "Depression"
    if has_anx:
        return "Anxiety"
    return "Other"
```

**4-class evaluation metrics:** accuracy, per-class precision/recall/F1, confusion matrix.

**Baseline to beat:** LingxiDiagBench reports 43.0% on this task.

### Files Changed

| File | Change |
|------|--------|
| `src/culturedx/pipeline/runner.py` | Add 3 lines: import + comorbidity metrics call |
| `scripts/analyze_comorbidity.py` | New: ~120 lines retrospective analysis |

### Testing

- Unit test for `predict_four_class` mapping (all 4 classes + edge cases)
- Run on V10 LingxiDiag predictions to validate output format
- Compare 4-class accuracy against LingxiDiagBench 43.0% baseline
