# CLAUDE.md — CultureDx LingxiDiag Alignment Sprint

## Mission

You are working on CultureDx, a multi-agent system for Chinese psychiatric differential diagnosis. The immediate goal is to **strictly align the evaluation pipeline with the LingxiDiagBench paper (arXiv:2602.09379)** so that results are directly comparable.

This is a **research repo**. Do not apply production hardening. Prioritize reproducibility, clarity, and paper-alignment over public-release concerns.

---

## Step 0 — Git Setup (DO THIS FIRST)

```bash
# Archive current master state
git tag v0.1-pre-alignment -m "Pre-LingxiDiag alignment archive"
git push origin v0.1-pre-alignment

# Create new research branch from the existing research branch
git checkout origin/pr-stack/docs-and-production-hardening -b research/lingxidiag-alignment

# Verify you're on the right branch
git log --oneline -3
```

Do NOT touch master. All work happens on `research/lingxidiag-alignment`.

---

## Step 1 — Undo Production Hardening

This is a research repo. Restore research-friendly state:

1. **Keep CLAUDE.md** — it's useful for agent workflows
2. **Keep outputs/ tracked** — research artifacts belong in the repo
3. **Keep docs/superpowers/ if present** — internal planning docs are useful
4. **Remove .gitignore entries that block outputs/** — we want to commit results
5. **Revert the README** to research-facing (not paper-facing landing page)

Check `.gitignore` and remove any lines that exclude `outputs/`.

---

## Step 2 — Fix Label Scheme (CRITICAL)

### The Problem

LingxiDiagBench defines **12 parent-level ICD-10 categories**:

```
F20  — Schizophrenia
F22  — Persistent delusional disorder  ← CURRENTLY DROPPED
F31  — Bipolar affective disorder
F32  — Depressive episode
F33  — Recurrent depressive disorder   ← CURRENTLY DROPPED
F40  — Phobic anxiety disorders         ← CURRENTLY DROPPED
F41  — Other anxiety disorders (GAD + Panic)
F42  — Obsessive-compulsive disorder
F43  — Reaction to severe stress (PTSD + Adjustment)
F45  — Somatoform disorders
F51  — Nonorganic sleep disorders
Others — All other codes                ← CURRENTLY EXCLUDED
```

### Fix: `src/culturedx/eval/code_mapping.py`

**Add F22, F33, F40 to EXACT_MAP:**

```python
EXACT_MAP: dict[str, str] = {
    "F20": "F20",
    "F22": "F22",    # ← ADD
    "F31": "F31",
    "F32": "F32",
    "F33": "F33",    # ← ADD
    "F40": "F40",    # ← ADD
    "F42": "F42",
    "F45": "F45",
    "F51": "F51",
    "F39": "F39",
    "F98": "F98",
}
```

**Remove "Others" from EXCLUDED_CODES** (it's a valid LingxiDiag class):

```python
EXCLUDED_CODES = {"Z71"}  # Only Z71 is truly excluded; "Others" is a valid class
```

**Add parent-level normalization functions:**

```python
def to_parent_code(code: str) -> str:
    """F41.1 → F41, F43.2 → F43, F32 → F32."""
    return code.split(".")[0]

LINGXIDIAG_12_CLASSES = [
    "F20", "F22", "F31", "F32", "F33", "F40",
    "F41", "F42", "F43", "F45", "F51", "Others",
]
_LINGXIDIAG_PARENT_SET = {c for c in LINGXIDIAG_12_CLASSES if c != "Others"}

def to_lingxidiag_label(code: str) -> str:
    """Map any ICD-10 code to LingxiDiag 12-class label.
    Returns parent code if recognized, else 'Others'."""
    parent = to_parent_code(code)
    return parent if parent in _LINGXIDIAG_PARENT_SET else "Others"
```

### Verify after fixing:

```python
# ALL of these must return non-empty lists:
assert map_dataset_code("F22") != []   # was [] before fix
assert map_dataset_code("F33") != []   # was [] before fix
assert map_dataset_code("F40") != []   # was [] before fix
```

---

## Step 3 — Fix Evaluation Split (CRITICAL)

### The Problem

CultureDx evaluates on `split="train"` (or `"validation"` on research branch).
LingxiDiagBench paper reports all numbers on **test split (1,000 cases)**.

### Fix: `scripts/run_full_eval.py`

Find the `resolve_dataset_spec` function. Change the LingxiDiag split:

```python
if output_name == "lingxidiag":
    return {
        "requested_name": dataset_name,
        "output_name": "lingxidiag",
        "adapter_name": "lingxidiag16k",
        "data_path": data_path,
        "split": args.split if hasattr(args, 'split') and args.split else "test",
        #                                                                  ^^^^
        # Paper uses test split. Allow CLI override for dev iteration.
    }
```

Also ensure the `--split` CLI argument exists and is wired through.

---

## Step 4 — Fix Target Disorders

### The Problem

`configs/targets/final_target_disorders.yaml` only has 5 disorders:
```yaml
target_disorders: [F32, F33, F41.1, F42, F43.1]
```
This means HiED only checks 5 disorders and can never predict the other 7 classes.

### Fix: Create `configs/targets/lingxidiag_12class.yaml`

```yaml
# LingxiDiag-aligned: all system-level disorders that map to the 12 parent classes
target_disorders:
  - F20      # Schizophrenia
  - F22      # Persistent delusional disorder
  - F31      # Bipolar affective disorder
  - F32      # Depressive episode
  - F33      # Recurrent depressive disorder
  - F40      # Phobic anxiety disorders
  - F41.0    # Panic disorder
  - F41.1    # Generalized anxiety disorder
  - F42      # OCD
  - F43.1    # PTSD
  - F43.2    # Adjustment disorders
  - F45      # Somatoform disorders
  - F51      # Nonorganic sleep disorders
```

Update `src/culturedx/core/target_disorders.py` to point to this as the default:

```python
FINAL_TARGET_DISORDERS = [
    "F20", "F22", "F31", "F32", "F33", "F40",
    "F41.0", "F41.1", "F42", "F43.1", "F43.2", "F45", "F51",
]
```

---

## Step 5 — Add Paper-Aligned Metrics

### The Problem

LingxiDiagBench reports 3 tasks with specific metrics:
- **Task 1 (Binary)**: Depression vs Anxiety accuracy
- **Task 2 (4-class)**: Depression / Anxiety / Mixed / Others accuracy
- **Task 3 (12-class)**: Accuracy, Macro-F1, Top-3 Accuracy
- **Overall**: Average of 3 task accuracies

CultureDx metrics don't match these definitions.

### Fix: Create `src/culturedx/eval/lingxidiag_metrics.py`

```python
"""Paper-aligned metrics for direct comparison with LingxiDiagBench (arXiv:2602.09379)."""
from __future__ import annotations
from sklearn.metrics import f1_score, accuracy_score
from culturedx.eval.code_mapping import to_parent_code, to_lingxidiag_label, LINGXIDIAG_12_CLASSES

DEPRESSION_CODES = {"F32", "F33"}
ANXIETY_CODES = {"F40", "F41", "F42"}


def compute_binary_task(pred_parents: list[str], gold_parents: list[str]) -> dict:
    """Task 1: Depression (F32|F33) vs Anxiety (F40|F41|F42).
    Only evaluates cases whose primary gold label is in depression or anxiety."""
    valid_codes = DEPRESSION_CODES | ANXIETY_CODES
    filtered = [(p, g) for p, g in zip(pred_parents, gold_parents) if g in valid_codes]
    if not filtered:
        return {"binary_accuracy": float("nan"), "binary_n": 0}
    preds, golds = zip(*filtered)
    pred_binary = ["Depression" if p in DEPRESSION_CODES else "Anxiety" if p in ANXIETY_CODES else "Other" for p in preds]
    gold_binary = ["Depression" if g in DEPRESSION_CODES else "Anxiety" for g in golds]
    return {
        "binary_accuracy": accuracy_score(gold_binary, pred_binary),
        "binary_n": len(filtered),
    }


def compute_4class_task(pred_parents: list[str], gold_label_lists: list[list[str]]) -> dict:
    """Task 2: Depression / Anxiety / Mixed / Others.
    Mixed = has both depression and anxiety labels."""
    def to_4class(labels: list[str]) -> str:
        parents = {to_parent_code(l) for l in labels}
        has_dep = bool(parents & DEPRESSION_CODES)
        has_anx = bool(parents & ANXIETY_CODES)
        if has_dep and has_anx:
            return "Mixed"
        if has_dep:
            return "Depression"
        if has_anx:
            return "Anxiety"
        return "Others"

    gold_4class = [to_4class(g) for g in gold_label_lists]
    # For predictions, use primary prediction's parent code
    pred_4class = []
    for p in pred_parents:
        if p in DEPRESSION_CODES:
            pred_4class.append("Depression")
        elif p in ANXIETY_CODES:
            pred_4class.append("Anxiety")
        else:
            pred_4class.append("Others")

    return {
        "four_class_accuracy": accuracy_score(gold_4class, pred_4class),
        "four_class_n": len(gold_4class),
    }


def compute_12class_task(
    pred_lists: list[list[str]],
    gold_lists: list[list[str]],
) -> dict:
    """Task 3: 12-class ICD-10 multi-label prediction.
    All codes normalized to parent level. Unmapped → 'Others'."""
    pred_primary = [to_lingxidiag_label(p[0]) if p else "Others" for p in pred_lists]
    gold_primary = [to_lingxidiag_label(g[0]) if g else "Others" for g in gold_lists]

    accuracy = accuracy_score(gold_primary, pred_primary)
    macro_f1 = f1_score(gold_primary, pred_primary, average="macro",
                        labels=LINGXIDIAG_12_CLASSES, zero_division=0)

    # Top-3 accuracy
    top3_correct = 0
    for preds, golds in zip(pred_lists, gold_lists):
        pred_top3 = {to_lingxidiag_label(p) for p in preds[:3]}
        gold_set = {to_lingxidiag_label(g) for g in golds}
        if pred_top3 & gold_set:
            top3_correct += 1
    top3_acc = top3_correct / len(gold_lists) if gold_lists else 0.0

    return {
        "twelve_class_accuracy": accuracy,
        "twelve_class_macro_f1": macro_f1,
        "twelve_class_top3_accuracy": top3_acc,
        "twelve_class_n": len(gold_lists),
    }


def compute_overall_score(binary_acc: float, four_class_acc: float, twelve_class_acc: float) -> float:
    """Overall = average of 3 task accuracies (LingxiDiagBench definition)."""
    return (binary_acc + four_class_acc + twelve_class_acc) / 3.0


def compute_all_lingxidiag_metrics(
    pred_lists: list[list[str]],
    gold_lists: list[list[str]],
) -> dict:
    """Compute all LingxiDiagBench-aligned metrics in one call."""
    pred_parents = [to_lingxidiag_label(p[0]) if p else "Others" for p in pred_lists]
    gold_parents = [to_lingxidiag_label(g[0]) if g else "Others" for g in gold_lists]

    binary = compute_binary_task(pred_parents, gold_parents)
    four_class = compute_4class_task(pred_parents, gold_lists)
    twelve_class = compute_12class_task(pred_lists, gold_lists)

    overall = compute_overall_score(
        binary.get("binary_accuracy", 0.0),
        four_class.get("four_class_accuracy", 0.0),
        twelve_class.get("twelve_class_accuracy", 0.0),
    )

    return {
        **binary,
        **four_class,
        **twelve_class,
        "overall_score": overall,
    }
```

### Wire into `run_full_eval.py`

In `compute_group_metrics()`, add:

```python
from culturedx.eval.lingxidiag_metrics import compute_all_lingxidiag_metrics

# After existing metric computation, add:
lingxidiag_metrics = compute_all_lingxidiag_metrics(preds, golds)
result["lingxidiag_paper_metrics"] = lingxidiag_metrics
```

---

## Step 6 — Add Forced Prediction Mode (No Abstention)

### The Problem

LingxiDiagBench baselines always produce a prediction. CultureDx's calibrator abstains on low-confidence cases, making accuracy non-comparable.

### Fix: `src/culturedx/diagnosis/calibrator.py`

Add a `force_prediction: bool = False` parameter. When True:
- Never return "abstain" decision
- Always pick the highest-confidence candidate as primary diagnosis
- If all checkers fail, fall back to triage result
- If triage also fails, fall back to "Others"

This should be toggleable via config or CLI flag `--force-prediction`.

---

## Step 7 — Verification Script

Create `scripts/verify_lingxidiag_alignment.py`:

```python
"""Verify CultureDx evaluation is aligned with LingxiDiagBench paper protocol."""
import sys
sys.path.insert(0, "src")
from collections import Counter
from culturedx.data.adapters.lingxidiag16k import LingxiDiag16kAdapter
from culturedx.eval.code_mapping import (
    map_dataset_code, to_parent_code, to_lingxidiag_label,
    LINGXIDIAG_12_CLASSES,
)

def main():
    errors = []

    # 1. Code mapping: no class should be dropped
    print("Checking code_mapping covers all 12 classes...")
    for cls in LINGXIDIAG_12_CLASSES:
        if cls == "Others":
            continue
        mapped = map_dataset_code(cls)
        if not mapped:
            errors.append(f"FAIL: map_dataset_code('{cls}') returns [] — class silently dropped!")
        else:
            print(f"  ✓ {cls} → {mapped}")

    # 2. Load test split
    print("\nChecking test split loads correctly...")
    try:
        adapter = LingxiDiag16kAdapter(data_path="data/raw/lingxidiag16k")
        cases = adapter.load(split="test")
        print(f"  ✓ Loaded {len(cases)} test cases")
        if len(cases) != 1000:
            errors.append(f"WARN: Expected 1000 test cases, got {len(cases)}")
    except Exception as e:
        errors.append(f"FAIL: Could not load test split: {e}")
        cases = []

    # 3. Check label distribution
    if cases:
        print("\nLabel distribution (parent-level):")
        label_dist = Counter()
        dropped = 0
        for case in cases:
            for label in case.diagnoses:
                parent = to_lingxidiag_label(label)
                label_dist[parent] += 1

        for cls in LINGXIDIAG_12_CLASSES:
            count = label_dist.get(cls, 0)
            status = "✓" if count > 0 else "✗ MISSING"
            print(f"  {status} {cls}: {count}")

        total_mapped = sum(label_dist.values())
        print(f"\n  Total labels: {total_mapped}")

    # 4. Check no cases are filtered out
    if cases:
        print("\nChecking zero-drop policy...")
        from culturedx.eval.code_mapping import map_code_list
        dropped_cases = []
        for case in cases:
            mapped = map_code_list(case.diagnoses)
            if not mapped:
                dropped_cases.append((case.case_id, case.diagnoses))

        if dropped_cases:
            errors.append(f"FAIL: {len(dropped_cases)} cases would be dropped from evaluation!")
            for cid, diags in dropped_cases[:5]:
                print(f"  DROPPED: case_id={cid}, diagnoses={diags}")
        else:
            print(f"  ✓ All {len(cases)} cases have valid mapped codes")

    # Summary
    print("\n" + "=" * 50)
    if errors:
        print(f"ALIGNMENT CHECK FAILED — {len(errors)} issue(s):")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)
    else:
        print("✅ ALL ALIGNMENT CHECKS PASSED")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

---

## Step 8 — Update Paper Tables

After running evaluation, populate `paper/tables/main_results.md` with this format to enable direct comparison:

```markdown
## LingxiDiagBench-Aligned Results (test split, n=1000)

### Baselines from Paper (Table 4)
| Method | Binary Acc | 4-Class Acc | 12-Class Acc | Macro-F1 | Top-3 | Overall |
|--------|-----------|-------------|-------------|----------|-------|---------|
| TF-IDF + LR | — | — | — | — | — | 0.533 |
| GPT-5-Mini | — | — | 0.409 | — | — | — |
| Qwen3-32B | — | — | — | 0.278 | — | — |
| Qwen3-4B | — | — | — | — | 0.698 | — |

### CultureDx (Ours)
| Method | Binary Acc | 4-Class Acc | 12-Class Acc | Macro-F1 | Top-3 | Overall |
|--------|-----------|-------------|-------------|----------|-------|---------|
| CultureDx Single (no evidence) | — | — | — | — | — | — |
| CultureDx HiED (no evidence) | — | — | — | — | — | — |
| CultureDx HiED + evidence | — | — | — | — | — | — |
| CultureDx HiED + evidence + somatization | — | — | — | — | — | — |
```

---

## Reference: LingxiDiagBench Paper Key Numbers

From arXiv:2602.09379 Table 4, LingxiDiag-16K **test split**:

- Best 12-class accuracy: **0.409** (GPT-5-Mini)
- Best macro-F1: **0.278** (Qwen3-32B)
- Best Top-3 accuracy: **0.698** (Qwen3-4B)
- Best Overall score: **0.533** (TF-IDF + LR)
- Binary (depression vs anxiety): up to **0.854** (Gemini-3-Flash)
- 4-class: **0.479** (TF-IDF + RF)

These are **our target baselines to beat**.

---

## Checklist (verify all before any eval run)

- [ ] `git branch` shows `research/lingxidiag-alignment`
- [ ] `map_dataset_code("F22")` returns non-empty
- [ ] `map_dataset_code("F33")` returns non-empty
- [ ] `map_dataset_code("F40")` returns non-empty
- [ ] `to_lingxidiag_label("F41.1")` returns `"F41"`
- [ ] `to_lingxidiag_label("F99")` returns `"Others"`
- [ ] Test split loads 1000 cases
- [ ] Zero cases dropped from evaluation
- [ ] `--force-prediction` flag exists and works
- [ ] `lingxidiag_paper_metrics` appears in output metrics.json
- [ ] `verify_lingxidiag_alignment.py` passes all checks
- [ ] `target_disorders` config covers all 13 system-level codes
- [ ] `outputs/` is NOT in `.gitignore`

---

## Files to Modify (Summary)

| File | Action |
|------|--------|
| `src/culturedx/eval/code_mapping.py` | Add F22/F33/F40, remove Others exclusion, add parent-level functions |
| `src/culturedx/eval/lingxidiag_metrics.py` | **NEW** — Paper-aligned 3-task metrics |
| `src/culturedx/core/target_disorders.py` | Expand to 13 system-level disorders |
| `configs/targets/lingxidiag_12class.yaml` | **NEW** — 12-class config |
| `scripts/run_full_eval.py` | Default split=test, wire lingxidiag_metrics, --force-prediction |
| `src/culturedx/diagnosis/calibrator.py` | Add force_prediction mode |
| `scripts/verify_lingxidiag_alignment.py` | **NEW** — Alignment sanity check |
| `paper/tables/main_results.md` | Update with paper-aligned table format |
| `.gitignore` | Remove outputs/ exclusion |
| `tests/test_code_mapping.py` | Add tests for F22, F33, F40, parent normalization |
