# CLAUDE.md — CultureDx × LingxiDiagBench Table 4 Alignment

## Mission

Align CultureDx static diagnosis evaluation with **LingxiDiagBench Table 4** (arXiv:2602.09379) so results are directly comparable. All definitions below come from the official repo: `github.com/Lingxi-mental-health/LingxiDiagBench/evaluation/static/`.

Scope: **Table 4 static diagnosis only.** No dynamic benchmark, no next-question prediction.

---

## Step 0 — Git Setup

```bash
git tag v0.1-pre-alignment -m "Pre-LingxiDiag alignment archive"
git push origin v0.1-pre-alignment
git checkout origin/pr-stack/docs-and-production-hardening -b research/lingxidiag-alignment
```

---

## Step 1 — Ground Truth: The 12-Class Label Set

Source: `LingxiDiagBench/evaluation/static/config.py`

```python
# THIS is the paper's 12-class set. Not F22, not F33, not F40.
VALID_ICD_CODES = [
    "F20",     # 精神分裂症 Schizophrenia
    "F31",     # 双相情感障碍 Bipolar
    "F32",     # 抑郁发作 Depressive episode
    "F39",     # 心境障碍（未特指）Unspecified mood
    "F41",     # 焦虑障碍 Anxiety disorders
    "F42",     # 强迫障碍 OCD
    "F43",     # 应激相关障碍 Stress-related
    "F45",     # 躯体形式障碍 Somatoform
    "F51",     # 睡眠障碍 Sleep
    "F98",     # 儿童青少年行为障碍 Childhood behavioral
    "Z71",     # 咨询 Counseling
    "Others",  # 其他
]
```

**Critical implications for CultureDx:**
- CultureDx's F22, F33, F40 → map to **"Others"** in paper comparison
- CultureDx's F41.0, F41.1 → collapse to **"F41"**
- CultureDx's F43.1, F43.2 → collapse to **"F43"**
- Z71 is NOT in CultureDx's ontology → CultureDx will never predict Z71 → Z71 gold cases will always be wrong (this is expected; paper baselines also struggle with Z71)

---

## Step 2 — Ground Truth: Task Definitions

Source: `LingxiDiagBench/evaluation/static/data_utils.py`

### Task 1: Binary (2-class)

**Labels:** `["Depression", "Anxiety"]`

**Sample filtering (from `classify_2class()`):**
- F41.2 (mixed anxiety-depression) → **excluded** (returns None)
- F32 AND F41 both present → **excluded** (comorbid)
- Only F32, no F41 → "Depression"
- Only F41, no F32 → "Anxiety"
- Everything else → **excluded** (returns None)

**This means binary eval uses a SUBSET of cases.** Only pure-F32 and pure-F41 cases participate. Do NOT evaluate on all 1000 cases for this task.

### Task 2: Four-class (4-class)

**Labels:** `["Depression", "Anxiety", "Mixed", "Others"]`

**Classification (from `classify_4class()`):**
- F41.2 OR (F32 AND F41 both present) → "Mixed"
- Only F32, no F41 → "Depression"
- Only F41, no F32 → "Anxiety"
- Everything else → "Others"

**All cases participate.** No filtering. This is single-label classification.

### Task 3: Twelve-class (12-class) — MULTI-LABEL

**Labels:** The 12 VALID_ICD_CODES above.

**Gold extraction (from `extract_f_codes_from_diagnosis_code()`):**
- Parse `DiagnosisCode` field (e.g. "F32.100;F41.000")
- Extract parent codes: F32, F41
- If none found → ["Others"]

**This is MULTI-LABEL.** A case can have gold = ["F32", "F41"]. Predictions are also multi-label (1-2 codes).

---

## Step 3 — Ground Truth: Metrics

Source: `LingxiDiagBench/evaluation/static/metrics.py`

### 2-class and 4-class: Single-label metrics
Uses `calculate_singlelabel_metrics()`:
- **Accuracy**: `sklearn.metrics.accuracy_score`
- **Macro-F1**: `sklearn.metrics.f1_score(average='macro', labels=present_labels, zero_division=0)`
- **Weighted-F1**: `sklearn.metrics.f1_score(average='weighted', labels=present_labels, zero_division=0)`

Note: `present_labels = [l for l in labels if l in set(y_true) or l in set(y_pred)]` — only labels that actually appear.

### 12-class: Multi-label metrics
Uses `calculate_multilabel_metrics()`:
- **Accuracy** = exact_match (pred set == gold set exactly)
- **Top-1** = first prediction is in gold set
- **Top-3** = any of first 3 predictions is in gold set
- **Macro-F1** = `sklearn.metrics.f1_score` on binarized matrix via `MultiLabelBinarizer`
- **Weighted-F1** = same, `average='weighted'`

### Table 4 Columns (11 metrics)

```
Method | 2c_Acc | 2c_F1m | 2c_F1w | 4c_Acc | 4c_F1m | 4c_F1w | 12c_Acc | 12c_Top1 | 12c_Top3 | 12c_F1m | 12c_F1w
```

Source: `benchmark_runner.py` → `export_summary_excel()` → `_collect_summary_rows()`

**Overall** is NOT computed in code. It is likely the mean of all 11 metric columns (computed externally for the paper table).

---

## Step 4 — Ground Truth: Data Split

Source: `LingxiDiagBench/evaluation/static/config.py`

```python
TEST_DATA_FILE = os.path.join(DATA_DIR, "LingxiDiag-16K_validation_data.json")
```

The file is named "validation" but the paper treats it as the test set for Table 4. LingxiDiag-16K has 16,000 total → 14,000 train / 1,000 validation / 1,000 test. **Table 4 uses the validation split (1,000 cases).**

For CultureDx: if loading from HuggingFace parquet, use `split="validation"`. If loading from JSON, use the file named `validation_data.json`.

---

## Step 5 — CultureDx Changes Required

### 5.1 New file: `src/culturedx/eval/lingxidiag_paper.py`

This is the **single source of truth** for paper-aligned evaluation. All constants and functions come from the official repo.

```python
"""LingxiDiagBench Table 4 paper-aligned evaluation.

All definitions sourced from:
  github.com/Lingxi-mental-health/LingxiDiagBench/evaluation/static/
"""
from __future__ import annotations
import re
from typing import Optional
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.preprocessing import MultiLabelBinarizer
import numpy as np

# === Label Sets (from config.py) ===

PAPER_12_CLASSES: list[str] = [
    "F20", "F31", "F32", "F39", "F41", "F42",
    "F43", "F45", "F51", "F98", "Z71", "Others",
]
_PAPER_PARENT_SET = {c for c in PAPER_12_CLASSES if c != "Others"}

PAPER_2_CLASSES: list[str] = ["Depression", "Anxiety"]
PAPER_4_CLASSES: list[str] = ["Depression", "Anxiety", "Mixed", "Others"]


# === Code Normalization ===

def to_paper_parent(code: str) -> str:
    """Collapse any ICD-10 code to paper's parent level.
    
    F41.1 → F41, F43.2 → F43, F32.900 → F32, Z71.9 → Z71
    Codes not in paper's 12-class set (F22, F33, F40, etc.) → Others
    """
    normalized = code.strip().upper()
    
    # Check Z71
    if "Z71" in normalized:
        return "Z71"
    
    # Extract Fxx parent
    match = re.search(r'F(\d{2})', normalized)
    if match:
        parent = f"F{match.group(1)}"
        return parent if parent in _PAPER_PARENT_SET else "Others"
    
    return "Others"


def gold_to_parent_list(diagnosis_code: str) -> list[str]:
    """Extract parent-level codes from raw DiagnosisCode string.
    
    Mirrors LingxiDiagBench's extract_f_codes_from_diagnosis_code().
    "F32.100;F41.000" → ["F32", "F41"]
    """
    if not diagnosis_code:
        return ["Others"]
    
    code = diagnosis_code.strip().upper()
    parts = re.split(r'[;,]', code)
    
    extracted = []
    for part in parts:
        part = part.strip().rstrip(',')
        if 'Z71' in part:
            if "Z71" not in extracted:
                extracted.append("Z71")
            continue
        match = re.search(r'F(\d{2})', part)
        if match:
            parent = f"F{match.group(1)}"
            if parent in _PAPER_PARENT_SET and parent not in extracted:
                extracted.append(parent)
    
    return extracted if extracted else ["Others"]


def pred_to_parent_list(predicted_codes: list[str]) -> list[str]:
    """Collapse CultureDx predictions to paper parent-level codes.
    
    ["F41.1", "F32"] → ["F41", "F32"]
    ["F22"] → ["Others"]   (F22 not in paper's 12 classes)
    [] → ["Others"]
    """
    if not predicted_codes:
        return ["Others"]
    
    result = []
    seen = set()
    for code in predicted_codes:
        parent = to_paper_parent(code)
        if parent not in seen:
            seen.add(parent)
            result.append(parent)
    
    return result if result else ["Others"]


# === Task Classification (from data_utils.py) ===

def classify_2class(gold_parents: list[str]) -> Optional[str]:
    """Binary: pure Depression(F32) vs pure Anxiety(F41).
    
    Returns None if case should be excluded from binary eval.
    Mirrors LingxiDiagBench's classify_2class().
    """
    has_f32 = "F32" in gold_parents
    has_f41 = "F41" in gold_parents
    # Note: F41.2 check needs raw DiagnosisCode, not parent-level.
    # We handle this via a separate function that takes raw code.
    
    if has_f32 and has_f41:
        return None  # comorbid → exclude
    if has_f32 and not has_f41:
        return "Depression"
    if has_f41 and not has_f32:
        return "Anxiety"
    return None  # not F32 or F41 → exclude


def classify_2class_from_raw(diagnosis_code: str) -> Optional[str]:
    """Binary classification using raw DiagnosisCode (handles F41.2).
    
    Exact mirror of LingxiDiagBench's logic:
    - F41.2 → exclude
    - F32 AND F41 → exclude (comorbid)
    - Only F32 → Depression
    - Only F41 → Anxiety
    - Otherwise → exclude
    """
    if not diagnosis_code:
        return None
    code = diagnosis_code.strip().upper()
    
    has_f32 = bool(re.search(r'F32', code))
    has_f41 = bool(re.search(r'F41', code))
    has_f41_2 = bool(re.search(r'F41\.2', code))
    
    if has_f41_2 or (has_f32 and has_f41):
        return None
    if has_f32 and not has_f41:
        return "Depression"
    if has_f41 and not has_f32:
        return "Anxiety"
    return None


def classify_4class_from_raw(diagnosis_code: str) -> str:
    """4-class using raw DiagnosisCode.
    
    Exact mirror of LingxiDiagBench's classify_4class().
    """
    if not diagnosis_code:
        return "Others"
    code = diagnosis_code.strip().upper()
    
    has_f32 = bool(re.search(r'F32', code))
    has_f41 = bool(re.search(r'F41', code))
    has_f41_2 = bool(re.search(r'F41\.2', code))
    
    if has_f41_2 or (has_f32 and has_f41):
        return "Mixed"
    if has_f32 and not has_f41:
        return "Depression"
    if has_f41 and not has_f32:
        return "Anxiety"
    return "Others"


# === Metrics (from metrics.py) ===

def compute_singlelabel_metrics(
    y_true: list[str], y_pred: list[str], labels: list[str]
) -> dict:
    """Single-label metrics. Used for 2-class and 4-class tasks.
    
    Mirrors LingxiDiagBench's calculate_singlelabel_metrics().
    """
    present_labels = [l for l in labels if l in set(y_true) or l in set(y_pred)]
    
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=present_labels,
                                    average='macro', zero_division=0)),
        "weighted_f1": float(f1_score(y_true, y_pred, labels=present_labels,
                                       average='weighted', zero_division=0)),
        "n": len(y_true),
    }


def compute_multilabel_metrics(
    y_true: list[list[str]], y_pred: list[list[str]], labels: list[str]
) -> dict:
    """Multi-label metrics. Used for 12-class task.
    
    Mirrors LingxiDiagBench's calculate_multilabel_metrics().
    """
    n = len(y_true)
    
    mlb = MultiLabelBinarizer(classes=labels)
    y_true_bin = mlb.fit_transform(y_true)
    y_pred_bin = mlb.transform(y_pred)
    
    # Exact match
    exact_match = sum(1 for t, p in zip(y_true, y_pred) if set(t) == set(p)) / n
    
    # Top-1: first prediction in gold set
    top1 = sum(1 for t, p in zip(y_true, y_pred) if p and p[0] in set(t)) / n
    
    # Top-3: any of first 3 predictions in gold set
    top3 = sum(1 for t, p in zip(y_true, y_pred)
               if len(set(p[:3]) & set(t)) > 0) / n
    
    return {
        "accuracy": float(exact_match),      # exact_match = "Acc" in Table 4
        "top1_accuracy": float(top1),         # "Top1" in Table 4
        "top3_accuracy": float(top3),         # "Top3" in Table 4
        "macro_f1": float(f1_score(y_true_bin, y_pred_bin,
                                    average='macro', zero_division=0)),
        "weighted_f1": float(f1_score(y_true_bin, y_pred_bin,
                                       average='weighted', zero_division=0)),
        "n": n,
    }


def compute_table4_metrics(
    cases: list[dict],
    get_prediction: callable,
) -> dict:
    """Compute all Table 4 metrics for a list of cases.
    
    Args:
        cases: List of dicts with at least 'DiagnosisCode' and 'cleaned_text'.
        get_prediction: Function(case) → list[str] of predicted parent-level codes.
                        e.g. ["F32"] or ["F41", "F32"]
    
    Returns:
        Dict with all 11 Table 4 metrics + Overall.
    """
    # Collect predictions and gold labels
    gold_12_all = []
    pred_12_all = []
    
    gold_2_all = []
    pred_2_all = []
    
    gold_4_all = []
    pred_4_all = []
    
    for case in cases:
        raw_code = case.get("DiagnosisCode", "")
        gold_parents = gold_to_parent_list(raw_code)
        pred_parents = get_prediction(case)
        
        # 12-class (all cases, multi-label)
        gold_12_all.append(gold_parents)
        pred_12_all.append(pred_parents)
        
        # 4-class (all cases, single-label)
        gold_4 = classify_4class_from_raw(raw_code)
        # For prediction: map primary to 4-class
        pred_primary = pred_parents[0] if pred_parents else "Others"
        if pred_primary == "F32":
            pred_4 = "Depression"
        elif pred_primary == "F41":
            pred_4 = "Anxiety"
        else:
            pred_4 = "Others"
        # Check if prediction has both F32 and F41
        pred_parent_set = set(pred_parents)
        if "F32" in pred_parent_set and "F41" in pred_parent_set:
            pred_4 = "Mixed"
        
        gold_4_all.append(gold_4)
        pred_4_all.append(pred_4)
        
        # 2-class (only non-comorbid F32 or F41 cases)
        gold_2 = classify_2class_from_raw(raw_code)
        if gold_2 is not None:
            pred_2 = "Depression" if pred_primary == "F32" else \
                     "Anxiety" if pred_primary == "F41" else "Other"
            gold_2_all.append(gold_2)
            pred_2_all.append(pred_2)
    
    # Compute metrics per task
    m2 = compute_singlelabel_metrics(gold_2_all, pred_2_all, PAPER_2_CLASSES) if gold_2_all else {}
    m4 = compute_singlelabel_metrics(gold_4_all, pred_4_all, PAPER_4_CLASSES)
    m12 = compute_multilabel_metrics(gold_12_all, pred_12_all, PAPER_12_CLASSES)
    
    # Assemble Table 4 row
    table4 = {
        "2class_Acc": m2.get("accuracy"),
        "2class_F1_macro": m2.get("macro_f1"),
        "2class_F1_weighted": m2.get("weighted_f1"),
        "4class_Acc": m4.get("accuracy"),
        "4class_F1_macro": m4.get("macro_f1"),
        "4class_F1_weighted": m4.get("weighted_f1"),
        "12class_Acc": m12.get("accuracy"),
        "12class_Top1": m12.get("top1_accuracy"),
        "12class_Top3": m12.get("top3_accuracy"),
        "12class_F1_macro": m12.get("macro_f1"),
        "12class_F1_weighted": m12.get("weighted_f1"),
        "2class_n": m2.get("n", 0),
        "4class_n": m4.get("n", 0),
        "12class_n": m12.get("n", 0),
    }
    
    # Overall = mean of all 11 metric columns (if all present)
    metric_values = [v for k, v in table4.items()
                     if not k.endswith("_n") and v is not None]
    table4["Overall"] = float(np.mean(metric_values)) if metric_values else None
    
    return table4
```

### 5.2 Modify: `src/culturedx/eval/code_mapping.py`

Add these to EXACT_MAP (they exist in CultureDx ontology AND paper's 12-class):
```python
EXACT_MAP["F39"] = "F39"   # Already present, but verify
EXACT_MAP["F98"] = "F98"   # Already present, but verify
```

**Do NOT add F22, F33, F40 to EXACT_MAP for paper evaluation.** Those map to "Others".

**Remove "Others" from EXCLUDED_CODES:**
```python
EXCLUDED_CODES = {"Z71"}  
# Wait — Z71 IS in the paper's 12 classes. 
# But CultureDx can't predict Z71, so we should NOT exclude it from gold labels.
# Change to:
EXCLUDED_CODES: set[str] = set()  # Don't exclude anything for paper-aligned eval
```

### 5.3 Modify: `scripts/run_full_eval.py`

**Change default split for LingxiDiag:**
```python
"split": "validation",  # Paper's Table 4 uses validation split (1000 cases)
```

**Wire paper metrics:** After computing existing metrics, also compute Table 4 metrics:
```python
from culturedx.eval.lingxidiag_paper import compute_table4_metrics, pred_to_parent_list
# ... inside metric computation:
table4 = compute_table4_metrics(cases, lambda case: pred_to_parent_list(predicted_codes))
result["table4_paper_metrics"] = table4
```

### 5.4 Modify: `configs/targets/lingxidiag_12class.yaml` (NEW)

```yaml
# Target disorders that cover all 11 ICD parent codes in paper's 12-class set.
# F39 and F98 use parent-level (no subcodes in CultureDx ontology).
# Z71 is NOT covered by CultureDx — those cases will default to "Others".
# "Others" is a fallback, not a target disorder.
target_disorders:
  - F20      # → paper F20
  - F31      # → paper F31
  - F32      # → paper F32
  - F39      # → paper F39
  - F41.0    # → paper F41 (collapsed)
  - F41.1    # → paper F41 (collapsed)
  - F42      # → paper F42
  - F43.1    # → paper F43 (collapsed)
  - F43.2    # → paper F43 (collapsed)
  - F45      # → paper F45
  - F51      # → paper F51
  - F98      # → paper F98
```

### 5.5 Modify: `src/culturedx/diagnosis/calibrator.py`

Add `force_prediction: bool` config option. When True:
- Never abstain
- Always pick highest-confidence candidate
- If all fail, output "Others"

Paper baselines always produce a prediction. Abstention makes accuracy non-comparable.

### 5.6 Modify: `src/culturedx/data/adapters/lingxidiag16k.py`

Ensure the adapter preserves the raw `DiagnosisCode` string in `case.metadata["diagnosis_code_full"]`. The paper's 2-class and 4-class tasks need the raw string (to detect F41.2).

---

## Step 6 — Verification Script

Create `scripts/verify_paper_alignment.py`:

```python
"""Verify CultureDx evaluation aligns with LingxiDiagBench Table 4."""
import sys
sys.path.insert(0, "src")
from culturedx.eval.lingxidiag_paper import (
    PAPER_12_CLASSES, to_paper_parent, gold_to_parent_list,
    classify_2class_from_raw, classify_4class_from_raw,
)

def main():
    errors = []
    
    # 1. Parent code mapping
    checks = [
        ("F41.1", "F41"), ("F41.0", "F41"), ("F43.2", "F43"), ("F43.1", "F43"),
        ("F32.900", "F32"), ("F39", "F39"), ("F98", "F98"), ("Z71.9", "Z71"),
        ("F22", "Others"), ("F33", "Others"), ("F40", "Others"),
        ("F20.0", "F20"), ("garbage", "Others"),
    ]
    for code, expected in checks:
        result = to_paper_parent(code)
        if result != expected:
            errors.append(f"to_paper_parent('{code}') = '{result}', expected '{expected}'")
    
    # 2. Gold extraction
    assert gold_to_parent_list("F32.100;F41.000") == ["F32", "F41"]
    assert gold_to_parent_list("Z71") == ["Z71"]
    assert gold_to_parent_list("") == ["Others"]
    assert gold_to_parent_list("F99.999") == ["Others"]
    
    # 3. Binary classification
    assert classify_2class_from_raw("F32.100") == "Depression"
    assert classify_2class_from_raw("F41.000") == "Anxiety"
    assert classify_2class_from_raw("F32.100;F41.000") is None  # comorbid
    assert classify_2class_from_raw("F41.200") is None           # F41.2 excluded
    assert classify_2class_from_raw("F20.000") is None           # not F32/F41
    
    # 4. 4-class classification
    assert classify_4class_from_raw("F32.100") == "Depression"
    assert classify_4class_from_raw("F41.000") == "Anxiety"
    assert classify_4class_from_raw("F32.100;F41.000") == "Mixed"
    assert classify_4class_from_raw("F41.200") == "Mixed"
    assert classify_4class_from_raw("F20.000") == "Others"
    
    if errors:
        print(f"FAILED — {len(errors)} errors:")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)
    else:
        print("✅ All paper-alignment checks passed")

if __name__ == "__main__":
    main()
```

---

## Step 7 — Reference Baselines (LingxiDiag-16K ONLY)

From paper Table 4, **LingxiDiag-16K validation split**:

| Method | 2c_Acc | 2c_F1m | 2c_F1w | 4c_Acc | 4c_F1m | 4c_F1w | 12c_Acc | 12c_Top1 | 12c_Top3 | 12c_F1m | 12c_F1w | Overall |
|--------|--------|--------|--------|--------|--------|--------|---------|----------|----------|---------|---------|---------|
| TF-IDF+LR | .853 | .852 | .853 | .475 | .327 | .444 | .145 | .485 | .614 | .295 | .469 | .533 |
| GPT-5-Mini | .846 | .846 | .846 | .468 | .326 | .431 | .166 | .409 | .645 | .225 | .343 | .505 |

*Fill in exact numbers from paper after verifying. The above are approximate from paper text.*

**DO NOT use LingxiDiag-Clinical numbers. Those are a different dataset (Table 7, not Table 4).**

---

## Checklist

- [ ] Branch is `research/lingxidiag-alignment`
- [ ] `to_paper_parent("F41.1")` returns `"F41"`
- [ ] `to_paper_parent("F22")` returns `"Others"`
- [ ] `to_paper_parent("Z71.9")` returns `"Z71"`
- [ ] `classify_2class_from_raw("F32.100;F41.000")` returns `None`
- [ ] `classify_4class_from_raw("F41.200")` returns `"Mixed"`
- [ ] `gold_to_parent_list("F32.100;F41.000")` returns `["F32", "F41"]`
- [ ] `verify_paper_alignment.py` passes all assertions
- [ ] LingxiDiag adapter uses `split="validation"` (1000 cases)
- [ ] `EXCLUDED_CODES` is empty (no silently dropped gold labels)
- [ ] Target disorders config covers F20,F31,F32,F39,F41.0,F41.1,F42,F43.1,F43.2,F45,F51,F98
- [ ] 12-class evaluation uses `MultiLabelBinarizer`, not single-label
- [ ] Force-prediction mode available (no abstention)
- [ ] Table 4 output has exactly 11 metric columns + Overall
- [ ] outputs/ is NOT in .gitignore

---

## Files Summary

| File | Action |
|------|--------|
| `src/culturedx/eval/lingxidiag_paper.py` | **NEW** — All paper-aligned constants, code mapping, task classification, metrics |
| `src/culturedx/eval/code_mapping.py` | Clear EXCLUDED_CODES, verify F39/F98 in EXACT_MAP |
| `scripts/run_full_eval.py` | Default split="validation", wire Table 4 metrics |
| `configs/targets/lingxidiag_12class.yaml` | **NEW** — 12 target disorders for paper alignment |
| `src/culturedx/core/target_disorders.py` | Update default to lingxidiag_12class |
| `src/culturedx/diagnosis/calibrator.py` | Add force_prediction mode |
| `src/culturedx/data/adapters/lingxidiag16k.py` | Ensure raw DiagnosisCode preserved |
| `scripts/verify_paper_alignment.py` | **NEW** — Alignment verification |
| `.gitignore` | Remove outputs/ exclusion |
