# CultureDx Dual-Standard Architecture Design

**Version**: v3.0 (dual-standard)
**Target deadline**: August 2026
**Goal**: Support DSM-5 and/or ICD-10 reasoning with aligned dual output,
enabling deployment in dual-standard jurisdictions (Taiwan, US).

---

## Clarification of the "6 combinations"

Your description was technically "6 combinations" but it collapses to:

**3 reasoning configurations × 2 output requirements** = but output is
always BOTH (ICD-10 + DSM-5 are emitted together).

So the real experiment matrix is **3 reasoning configs**, each of which
produces dual output:

| Config name | Criteria/prompts | Output |
|---|---|---|
| **mode_icd10** | ICD-10 only | Both (ICD-10 primary, DSM-5 via translator) |
| **mode_dsm5** | DSM-5 only | Both (DSM-5 primary, ICD-10 via reverse translator) |
| **mode_both** | Both run in parallel + ensemble | Both (from ensemble) |

All three produce a prediction record containing:
```json
{
  "primary_diagnosis_icd10": "F32.1",
  "primary_diagnosis_dsm5": "296.22",
  "evidence_trace_icd10": {...},   // criteria checker outputs, ICD-10 ids
  "evidence_trace_dsm5": {...},    // criteria checker outputs, DSM-5 ids
  "reasoning_mode": "both|icd10|dsm5",
  ...
}
```

This lets 長庚 clinicians read evidence in their preferred standard while
accuracy evaluation uses ICD-10 against gold labels.

---

## What stays the same

You do NOT need to rebuild:

1. **Triage agent** — still outputs disorder codes; only the *candidate list*
   will be expressed in different coding systems in different modes
2. **Logic engine** — it's purely rule-based over checker outputs; only the
   input `disorder_code` key changes from "F32" to "296.22" style
3. **Calibrator / comorbidity resolver** — same structure, different code strings
4. **Stacker features** — still extract TF-IDF + checker ratios, but now get
   two sets of checker ratios (ICD + DSM when in `mode_both`)
5. **Dataset adapters** — gold labels unchanged (always ICD-10 in benchmarks)

## What needs to change

### Tier 1: Data (this is where the real work is)

| Artifact | Current | Target | Effort |
|---|---|---|---|
| `icd10_criteria.json` | 26 disorders, 128 criteria | keep as-is | 0 |
| **NEW: `dsm5_criteria.json`** | doesn't exist | 26 disorders, ~140 criteria (DSM-5 is often more granular) | 3 days Claude + 2 weeks 長庚 review |
| **NEW: `dsm5_to_icd10_reverse.json`** | extend existing forward mapping | add reverse lookup (DSM-5 code → ICD-10 paper parent) | 0.5 day |
| Lossy case policy doc | implicit | explicit per-code fallback rules (F41.2 etc.) | 0.5 day + clinical input |

### Tier 2: Code module (thin abstraction layer)

Add **one new module** `src/culturedx/ontology/standards.py`:

```python
"""Unified coding-standard abstraction.

Replaces direct `from culturedx.ontology.icd10 import ...` throughout.
Callers now pass a `standard` parameter.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
import copy
import json
from functools import lru_cache

class DiagnosticStandard(str, Enum):
    ICD10 = "icd10"
    DSM5 = "dsm5"

@lru_cache(maxsize=2)
def _load(standard: DiagnosticStandard) -> dict:
    path = Path(__file__).parent / "data" / f"{standard.value}_criteria.json"
    return json.loads(path.read_text(encoding="utf-8"))

def load_criteria(standard: DiagnosticStandard) -> dict:
    return copy.deepcopy(_load(standard)["disorders"])

def list_disorders(standard: DiagnosticStandard) -> list[str]:
    return list(_load(standard)["disorders"].keys())

def get_disorder_criteria(code: str, standard: DiagnosticStandard) -> dict | None:
    return _load(standard)["disorders"].get(code)

def get_disorder_name(code: str, standard: DiagnosticStandard, lang: str = "zh") -> str:
    d = _load(standard)["disorders"].get(code, {})
    return d.get(f"name_{lang}", d.get("name", code))

def get_disorder_threshold(code: str, standard: DiagnosticStandard) -> dict:
    d = _load(standard)["disorders"].get(code, {})
    return d.get("threshold", {})

def paper_parent_icd10(code: str) -> str:
    """Extract paper 12-class parent, e.g. 'F32.1' -> 'F32'."""
    return code.split(".")[0] if code else ""

def dsm5_to_icd10(dsm5_code: str) -> tuple[str, bool]:
    """Reverse translate DSM-5 → ICD-10 parent. Returns (icd10_code, is_lossy)."""
    mapping = _load_dsm5_reverse()
    entry = mapping.get(dsm5_code)
    if not entry:
        return ("", True)
    return (entry["icd10_parent"], entry.get("is_lossy", False))

def icd10_to_dsm5(icd10_code: str) -> tuple[str | None, bool]:
    """Forward translate (existing translator). Returns (dsm5_code, is_lossy)."""
    # reuse existing translators.dsm5_translator logic
    ...
```

Keep `culturedx.ontology.icd10` as a backwards-compatible shim that calls
the new `standards` module with `ICD10` default — no callsite changes break.

### Tier 3: Config overlay (runtime switch)

Add three new overlay configs:

`configs/overlays/standard_icd10.yaml` (current default, make explicit):
```yaml
reasoning:
  standard: icd10
  criteria_file: icd10_criteria.json
  prompt_suffix: _zh      # diagnostician_v2_zh.jinja etc.
output:
  emit_icd10: true
  emit_dsm5: true         # via post-hoc translator
```

`configs/overlays/standard_dsm5.yaml`:
```yaml
reasoning:
  standard: dsm5
  criteria_file: dsm5_criteria.json
  prompt_suffix: _dsm5_zh
output:
  emit_icd10: true        # via dsm5 → icd10 reverse translator
  emit_dsm5: true
```

`configs/overlays/standard_both.yaml`:
```yaml
reasoning:
  standard: both
  # pipeline runs both ICD-10 and DSM-5 paths in parallel
  ensemble_policy: vote_then_translate
output:
  emit_icd10: true
  emit_dsm5: true
```

### Tier 4: Prompt templates

Create DSM-5 variants (naming convention: `*_dsm5_zh.jinja`):

| File | Source |
|---|---|
| `diagnostician_v2_dsm5_zh.jinja` | translate existing v2 prompt, swap criteria language |
| `criterion_checker_v2_dsm5_zh.jinja` | same, swap criterion references |
| `triage_v2_cot_dsm5_zh.jinja` | list DSM-5 categories in place of ICD-10 families |

Keep existing `*_zh.jinja` (ICD-10 versions) unchanged. Template resolution
driven by `config.reasoning.prompt_suffix`.

### Tier 5: Orchestration changes

**File**: `src/culturedx/modes/hied.py`

Key modifications (pseudocode):

```python
class HiEDOrchestrator:
    def __init__(self, config, ...):
        self.standards = self._resolve_standards(config)  # [ICD10] or [DSM5] or [ICD10, DSM5]
        # ... existing init ...

    def diagnose(self, case):
        results = {}
        for std in self.standards:
            results[std] = self._diagnose_single_standard(case, std)
        
        if len(self.standards) == 2:
            final = self._ensemble_dual_standard(results, case)
        else:
            final = self._promote_single_with_translation(results, self.standards[0])
        
        return final
```

The pipeline's stage order stays identical. Only the criteria-loading and
prompt-resolution are parameterized by `standard`.

### Tier 6: Ensemble policy for `mode_both`

This is the only genuinely new logic. Decisions to make:

**Policy option A: "Vote then translate"**
- Both ICD-10 and DSM-5 pipelines produce top-3 ranked codes
- Translate both into a common ICD-10 space
- Vote: if both agree → confident; if disagree → flag for review
- Primary output = majority, with confidence lowered on disagreement

**Policy option B: "Criteria union"**
- Merge criterion-met evidence from both pipelines
- Disorder is "confirmed" if either standard confirms it
- Output primary from the pipeline with higher total criterion confidence

**Policy option C: "Pass-through with disagreement flagging"**
- Report both predictions; don't reconcile
- Flag cases where ICD-10 primary ≠ DSM-5 primary (after translation)
- Downstream user (clinician) sees both and decides

**I strongly recommend C** for your 長庚 deployment goal:
- Matches the "dual-standard audit" clinical reality
- Easier to evaluate (you can compute metrics three ways: ICD view, DSM view, agreement subset)
- Most defensible in paper ("we don't hide disagreement; we surface it")

### Tier 7: Output schema

Every prediction record from now on emits:

```json
{
  "case_id": "12345",
  "reasoning_mode": "both",
  
  "primary_diagnosis": {
    "icd10": "F32.1",
    "icd10_name_zh": "中度抑郁發作",
    "dsm5": "296.22",
    "dsm5_name_zh": "重度憂鬱症，單次發作，中度",
    "standards_agree": true,
    "lossy_translation": false
  },
  
  "comorbid_diagnoses": [...],
  "ranked_codes": {
    "icd10": ["F32", "F41", ...],
    "dsm5": ["296.22", "300.02", ...]
  },
  
  "evidence_trace": {
    "icd10": {
      "criteria_met": {"F32": [{"id": "A1", "status": "met", ...}]},
      "logic_engine_confirmed": ["F32"]
    },
    "dsm5": {
      "criteria_met": {"296.22": [{"id": "A", "status": "met", ...}]},
      "logic_engine_confirmed": ["296.22"]
    }
  },
  
  "clinical_audit_summary_zh": "根據DSM-5判斷為重度憂鬱症（單次發作，中度），對應ICD-10為F32.1。兩標準一致。",
  
  "metadata": { ...existing fields... }
}
```

This is what 長庚 醫生 actually read during review.

---

## Execution plan (6 weeks, staged)

### Week 1: Foundation
- [ ] Write `dsm5_criteria.json` v0 (Claude drafts all 26 disorders from DSM-5 textbook)
- [ ] Extend existing mapping with reverse DSM-5 → ICD-10 direction
- [ ] Document lossy cases + fallback policy
- [ ] Send `dsm5_criteria.json` to 長庚 for review (kick off clinical review clock)
- [ ] Write `ontology/standards.py` unified abstraction

### Week 2: Prompts & orchestration
- [ ] Create `diagnostician_v2_dsm5_zh.jinja`
- [ ] Create `criterion_checker_v2_dsm5_zh.jinja`
- [ ] Create `triage_v2_cot_dsm5_zh.jinja`
- [ ] Modify `hied.py` to accept `standard` parameter
- [ ] Add the three new config overlays
- [ ] Unit tests for each standard independently

### Week 3: Pilot (F32 + F41 only)
- [ ] Run `mode_icd10` on N=100 (sanity baseline)
- [ ] Run `mode_dsm5` on N=100 (DSM-5 only)
- [ ] Run `mode_both` on N=100 (both + ensemble)
- [ ] Compare Top-1, F1_macro across three modes
- [ ] Audit disagreement cases manually

### Week 4: Integrate 長庚 review feedback
- [ ] Receive DSM-5 criteria revisions from 長庚
- [ ] Update `dsm5_criteria.json` to v1
- [ ] Re-run pilot and verify improvement

### Week 5: Full scale
- [ ] Run all three modes on LingxiDiag-16K test_final (N=1000)
- [ ] Run all three modes on MDD-5k (N=925)
- [ ] Produce full comparison table
- [ ] Stacker re-fit with dual-standard features

### Week 6: Analysis & paper
- [ ] Disagreement analysis: where do ICD-10 and DSM-5 reasoning diverge?
- [ ] Lossy case deep-dive (F41.2 specifically)
- [ ] Paper Section: "Dual-standard deployment"

---

## Decision gates

### G1 (end of Week 1): DSM-5 criteria feasibility
- Can you fit all 26 disorders under the existing threshold schema? Some DSM-5 disorders have more complex specifier structures than ICD-10. If any disorder exceeds threshold schema, consider extending the schema or flagging those as "pipeline-incompatible" and using translator fallback.

### G2 (end of Week 3): Pilot Top-1 spread
- If `mode_dsm5` Top-1 is within 3pp of `mode_icd10` → ensemble has room to help
- If `mode_dsm5` Top-1 is >5pp worse → lossy cases dominate; focus paper on "why DSM-5 reasoning is harder on LingxiDiag" (distribution mismatch, not model failure)
- If `mode_dsm5` Top-1 is better → especially interesting finding

### G3 (end of Week 4): 長庚 acceptance
- If ≥80% of sample DSM-5 criteria acceptable → proceed to full
- If 60-80% → do one more revision round
- If <60% → major rethink, may need to scope down to 5-10 disorders

---

## Specific engineering tasks for Codex

Here is the concrete sequence you'll hand to Codex after clinician review:

### Codex Task 1: Create unified standards module (4 hours)
- Create `src/culturedx/ontology/standards.py`
- Keep `culturedx/ontology/icd10.py` as backwards-compatible shim
- Add unit tests covering both standards
- Ensure no callsites break (full test suite must pass)

### Codex Task 2: Translate criteria JSON (6 hours, DO NOT commit until 長庚 reviews)
- Use existing 26 ICD-10 disorders as base
- For each disorder, write DSM-5 criteria following DSM-5 text (Claude references DSM-5-TR text)
- Mark criteria with ICD-10 ↔ DSM-5 alignment notes in metadata
- Handle F41.2 as special case: DSM-5 equivalent = "MDD with anxious distress specifier", with explicit lossy flag
- Sanity checks: disorder count equals 26, criteria schema matches ICD-10 format

### Codex Task 3: Create DSM-5 prompt variants (8 hours)
- Copy each `*_zh.jinja` to `*_dsm5_zh.jinja`
- Swap criterion naming and category references
- Update `disorder_descriptions` references to pull from DSM-5 criteria
- Preserve all non-standard-specific prompt logic (F32 prior, somatization hints, etc.)

### Codex Task 4: Modify orchestrator for standard parameter (1 day)
- Modify `modes/hied.py` `diagnose()` to accept `standard` parameter
- Dispatch pipeline stages through `standards.py` abstraction
- Support parallel execution for `mode_both`
- Add ensemble policy (recommend option C, pass-through with flagging)

### Codex Task 5: Output schema migration (6 hours)
- Extend `DiagnosisResult` dataclass to include dual-standard fields
- Update JSONL writers to emit new schema
- Update existing eval scripts to parse new schema
- Write migration notes for old-format results (backwards-compatibility flag)

### Codex Task 6: Config overlays (3 hours)
- Create 3 new overlay YAMLs
- Update existing overlays to be explicit about standard (currently implicit ICD-10)

### Codex Task 7: Pilot runner script (4 hours)
- Create `scripts/dual_standard/run_pilot.py`
- Runs all three modes on N=100 subset
- Produces comparison JSON + case-by-case disagreement report

### Codex Task 8: Full benchmark runner (3 hours)
- Create `scripts/dual_standard/run_full_benchmark.py`
- Runs all three modes on LingxiDiag + MDD-5k
- Produces results/dual_standard/{mode}/predictions.jsonl

### Codex Task 9: Evaluation harness update (1 day)
- Evaluate both standards independently (metric for each view)
- Compute disagreement rate between pipelines
- Produce paper Table 6 draft

### Codex Task 10: Clinician review package generator (4 hours)
- Randomly sample 30 predictions (stratified by disorder class)
- Format as Word doc with DSM-5 evidence + ICD-10 code + clinical question prompts
- Ready to send to 長庚

**Total: ~10 days of engineering work, distributable across multiple Codex sessions.**

---

## Risks and mitigations

| Risk | Probability | Mitigation |
|---|---|---|
| DSM-5 criteria take longer than estimated to write well | HIGH | Start with 6 most common disorders first (F32, F41, F31, F39, F42, F43); extend if time permits |
| 長庚 review latency blocks pipeline | MEDIUM | Submit criteria in waves; they review wave 1 while you do wave 2 |
| F41.2 lossy case policy is clinically contentious | HIGH | Let 長庚 define policy, not you; offer 2-3 reasonable options (dual-code, MDD+anxious distress, or explicit "no DSM-5 equivalent" marker) |
| `mode_dsm5` accuracy is much worse than `mode_icd10` due to translation cost | MEDIUM | Frame as feature: "We surface the clinical translation cost quantitatively" |
| Ensemble policy choice biases results | LOW-MEDIUM | Evaluate all three policies (A, B, C), report in paper appendix |
| Stacker features need refitting for dual standard | MEDIUM | Extend feature vector, re-train stacker; straightforward |
| Pipeline latency doubles in `mode_both` | LOW | Expected; document it; not a research problem |

---

## What to ship to 長庚 this week (before Codex work starts)

Before kicking off the 10-day engineering sprint, send 長庚 this package:

1. **Cover letter** explaining the goal: DSM-5 reasoning + ICD-10 output
2. **Sample criteria doc**: show 3 disorders in both ICD-10 (current) and DSM-5 (your draft) side by side
3. **Lossy case policy questions**:
   - How should we handle F41.2 (混合焦慮憂鬱) in DSM-5 mode?
   - Should F43.2 require specifier selection or default to "Unspecified"?
   - Is F98 → DSM-5 dispersion acceptable or do you prefer a single fallback?
4. **Review burden estimate**: ~2 hours per wave, 3 waves expected
5. **Timeline**: their wave-1 feedback by W2, wave-2 by W3, wave-3 by W4

Getting this out **this week** is higher priority than starting the code,
because their turnaround is your critical path.

---

## Paper positioning

Headline claim (revised for dual-standard):

> "CultureDx is the first Chinese psychiatric MAS to support dual-standard
> reasoning (DSM-5, ICD-10, or both) with aligned ICD-10 output for
> regulatory billing compatibility. Evaluated on LingxiDiag-16K (N=1000)
> and MDD-5k (N=925), our pipeline achieves Top-1 = 0.6XX in ICD-10 mode,
> 0.5XX in DSM-5 mode, and 0.6XX in both-standard ensemble mode, with
> disagreement rates of X% between standards. We characterize 8 diagnostic
> categories where DSM-5 and ICD-10 materially disagree, and provide
> clinician-reviewed DSM-5 criteria translations. External validation on
> 長庚 Memorial Hospital cases (N=XX) confirms clinical utility of the
> dual-standard audit trail."

This positions you as a **deployment-validated clinical system paper**,
not an accuracy benchmark paper. Much stronger for your 長庚 collaboration
and for any clinical-NLP venue (JAMIA, npj Digital Medicine, JMIR AI).

---

## Summary: what happens when

| Who | What | When |
|---|---|---|
| You | Send 長庚 criteria review package | This week |
| Claude (via Codex) | Task 1-2 (standards module + DSM-5 JSON draft) | Week 1 |
| 長庚 | Wave 1 review | Week 2-3 |
| Claude | Task 3-6 (prompts + orchestrator + configs) | Week 2 |
| You | Pilot N=100 across 3 modes | Week 3 |
| 長庚 | Wave 2 review | Week 3-4 |
| Claude | Task 7-9 (eval harness + full benchmark) | Week 4-5 |
| You | Full N=1000 + N=925 runs | Week 5 |
| You + Claude | Paper draft integrating dual-standard results | Week 6 |
| 長庚 | External validation on their clinical data | Week 7-10 |
| You | Revisions + submission | Week 11-14 |

This is executable. Tight but doable.
