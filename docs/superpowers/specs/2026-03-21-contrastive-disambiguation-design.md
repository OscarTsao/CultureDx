# Contrastive Criterion Disambiguation — Design Spec

**Date:** 2026-03-21
**Status:** Approved (rev 2 — addresses spec review)
**Scope:** HiED Stage 2.5 — criterion-level disambiguation for overlapping disorders

## Problem

V10 HiED achieves 41.5% Top-1 accuracy on LingxiDiag (N=200), exceeding GPT-5-Mini SOTA (40.9%). However, ranking error analysis reveals 21 ranking-only errors, of which 9 are F32↔F41.1 contests caused by 4 shared ICD-10 criteria receiving `met` status in both disorders simultaneously. The calibrator cannot break these ties reliably because F32 has 11 criteria (large margin signal) while F41.1 has 5 (zero margin at threshold), creating structural asymmetry in the ranking signal.

**Root cause:** The criterion checkers evaluate each disorder independently. Shared symptoms (concentration, sleep, psychomotor, fatigue) get marked `met` for both F32 and F41.1 without considering which disorder the symptom primarily belongs to.

## Solution: Stage 2.5 Contrastive Disambiguation

Insert a new LLM-based stage between Stage 2 (criterion checkers) and Stage 3 (logic engine) that re-evaluates shared criteria when 2+ disorders both have them marked `met`. The contrastive agent examines the transcript in context of both disorders and attributes each shared symptom to its primary disorder.

## Architecture

```
Stage 2: Criterion Checkers (parallel, per-disorder)
    │
    ▼
Stage 2.5: Contrastive Disambiguation (NEW)
    │  - Fires only when shared criteria are both-met across 2+ disorders
    │  - Re-evaluates shared criteria with cross-disorder context
    │  - Applies confidence-gated downgrade to non-primary disorder
    │
    ▼
Stage 3: Logic Engine (deterministic thresholds)
```

## Shared Criteria Registry

### Data Structure

```python
@dataclass(frozen=True)
class SharedCriterionPair:
    symptom_domain: str          # e.g., "concentration", "sleep"
    disorder_a: str              # e.g., "F32"
    criterion_a: str             # e.g., "C4"
    disorder_b: str              # e.g., "F41.1"
    criterion_b: str             # e.g., "B3"
    disambiguation_hint_en: str  # English clinical hint for LLM
    disambiguation_hint_zh: str  # Chinese clinical hint for LLM

# Registry: keyed by frozenset of disorder codes
SHARED_CRITERIA: dict[frozenset[str], list[SharedCriterionPair]]

def get_shared_pairs(disorder_a: str, disorder_b: str) -> list[SharedCriterionPair]:
    """Lookup shared criteria for a disorder pair. Order-independent."""
    return SHARED_CRITERIA.get(frozenset({disorder_a, disorder_b}), [])
```

### F32 ↔ F41.1 Mapping (4 pairs)

| # | Symptom Domain | F32 Criterion | F41.1 Criterion | Disambiguation Key |
|---|---------------|--------------|-----------------|-------------------|
| 1 | concentration | C4 (diminished thinking/concentration) | B3 (difficulty concentrating due to worry) | Is poor concentration linked to low mood/anhedonia or to excessive worry? |
| 2 | sleep | C6 (sleep disturbance of any type) | B4 (difficulty falling/staying asleep, restless sleep) | Is insomnia driven by rumination/early waking (depression) or by racing worried thoughts (anxiety)? |
| 3 | psychomotor/motor | C5 (psychomotor agitation or retardation) | B1 (motor tension, fidgeting, inability to relax) | Is the agitation depressive (purposeless, distressed) or anxious (tension-driven, hypervigilant)? |
| 4 | fatigue | B3 (decreased energy/increased fatigability) | B1 (motor tension — tension exhaustion component) | Depressive fatigue: anergic, present even at rest, no motivation. Anxiety fatigue: exhausted from sustained tension/worry, recovers with relaxation. Key: Is patient fatigued even when not worrying? |

Note: F41.1.B1 appears in pairs #3 and #4 because B1 (motor tension) is a multi-faceted criterion covering both psychomotor restlessness and tension-related exhaustion. This is clinically correct — each pair targets a different symptom domain within B1.

### Future Extensions

F42/F43 pairs are deferred. Pattern C errors (12/21 ranking errors) are distributed across multiple disorder pairs with lower per-pair ROI. The registry design supports adding new pairs without code changes — only data entries.

## Contrastive Agent

### Pattern

Follows `BaseAgent` ABC (same as `CriterionCheckerAgent` and `DifferentialDiagnosisAgent`):

```python
class ContrastiveCheckerAgent(BaseAgent):
    def run(self, input: AgentInput) -> AgentOutput
```

### Input (via AgentInput.extra)

The `checker_evidence` dict uses composite keys in the format `"{disorder}_{criterion_id}"` (underscore-separated). This key is constructed by `_run_contrastive` by iterating `CheckerOutput.criteria` and joining `CheckerOutput.disorder` with `CriterionResult.criterion_id`:

```python
# Key construction in _run_contrastive:
for co in checker_outputs:
    for cr in co.criteria:
        key = f"{co.disorder}_{cr.criterion_id}"  # e.g., "F32_C4"

extra = {
    "shared_pairs": list[SharedCriterionPair],  # pairs where both sides are met
    "checker_evidence": {
        # Composite key: "{disorder}_{criterion_id}"
        "F32_C4": {"status": "met", "evidence": "...", "confidence": 0.85},
        "F41.1_B3": {"status": "met", "evidence": "...", "confidence": 0.78},
        ...
    },
    "disorder_names": {
        "F32": "抑郁发作",
        "F41.1": "广泛性焦虑障碍",
    }
}
```

### Output JSON Schema

```json
{
  "attributions": [
    {
      "symptom_domain": "concentration",
      "primary_attribution": "F41.1",
      "attribution_confidence": 0.82,
      "reasoning": "Patient explicitly links concentration difficulty to worry cycles, not to low mood"
    }
  ]
}
```

Fields:
- `symptom_domain`: matches the pair's `symptom_domain` (unique within a single contrastive call)
- `primary_attribution`: one of the two disorder codes, or `"both"` for true comorbidity
- `attribution_confidence`: 0.0-1.0, how confident the agent is in the attribution
- `reasoning`: brief clinical reasoning (for debugging/paper analysis, not used downstream)

### Error Handling

If `ContrastiveCheckerAgent.run()` returns `parsed=None` or an empty/malformed `attributions` list, `_run_contrastive` returns the original `checker_outputs` unchanged. No exception raised — contrastive is a best-effort optimization that gracefully degrades to V10 behavior on failure.

### Prompt Design

Bilingual Jinja2 templates:
- `prompts/agents/contrastive_checker_zh.jinja`
- `prompts/agents/contrastive_checker_en.jinja`

Template selection follows existing pattern: `f"contrastive_checker_{input.language}.jinja"` where `input.language` is the `AgentInput.language` field.

Prompt structure:
1. Role: "You are a clinical differential diagnosis specialist"
2. Context: transcript text
3. For each shared criterion pair:
   - The symptom domain
   - Disorder A's criterion text + original checker evidence
   - Disorder B's criterion text + original checker evidence
   - Disambiguation hint (from registry)
4. Task: "For each shared symptom, determine which disorder it primarily belongs to"
5. Output: JSON schema above

## Confidence-Gated Downgrade

The downgrade applied to non-primary disorder criteria is proportional to the contrastive agent's attribution confidence. This prevents low-confidence attributions from destroying information.

### Three Tiers

| Attribution Confidence | Action on Non-Primary Criterion | Rationale |
|----------------------|-------------------------------|-----------|
| >= 0.8 (high) | status -> `insufficient_evidence`, confidence x 0.3 | Strong attribution — full downgrade |
| 0.6-0.8 (medium) | status stays `met`, confidence x 0.5 | Probable attribution — reduce ranking signal but preserve for logic engine |
| < 0.6 (low) | status stays `met`, confidence x 0.8 | Contrastive is unsure — minimal adjustment |

### Implementation

```python
from dataclasses import replace

def apply_attribution(
    criterion_result: CriterionResult,
    attribution_confidence: float,
    attribution_target: str,   # disorder code or "both"
    this_disorder: str,
) -> CriterionResult:
    if attribution_target == "both" or attribution_target == this_disorder:
        return criterion_result  # no change

    # Non-primary: confidence-gated downgrade
    if attribution_confidence >= 0.8:
        return replace(criterion_result,
                       status="insufficient_evidence",
                       confidence=criterion_result.confidence * 0.3)
    elif attribution_confidence >= 0.6:
        return replace(criterion_result,
                       confidence=criterion_result.confidence * 0.5)
    else:
        return replace(criterion_result,
                       confidence=criterion_result.confidence * 0.8)
```

### Per-Criterion-ID Deduplication

F41.1.B1 appears in two pairs (psychomotor and fatigue). To prevent compounding confidence multipliers on the same `CriterionResult`, `_run_contrastive` enforces **at most one downgrade per (disorder, criterion_id)**. When two attributions target the same criterion_id, the attribution with the **higher confidence** takes precedence:

```python
# In _run_contrastive: collect attributions, deduplicate per criterion_id
attribution_map: dict[tuple[str, str], tuple[float, str]] = {}
# key = (disorder, criterion_id), value = (attribution_confidence, target)

for attr in attributions:
    pair = find_pair_by_domain(attr["symptom_domain"])
    for disorder, criterion_id in [(pair.disorder_a, pair.criterion_a),
                                    (pair.disorder_b, pair.criterion_b)]:
        key = (disorder, criterion_id)
        new_conf = attr["attribution_confidence"]
        if key not in attribution_map or new_conf > attribution_map[key][0]:
            attribution_map[key] = (new_conf, attr["primary_attribution"])
```

### Interaction with Logic Engine Soft Confirmation

F41.1 has 5 criteria with `min_symptoms: 4`. If contrastive downgrades one F41.1 criterion from `met` to `insufficient_evidence`, F41.1 drops to 3 met — which triggers the logic engine's **soft confirmation path** (met == min-1, insufficient > 0, not_met <= 1), confirming F41.1 as `confirmation_type="soft"` rather than rejecting it.

This is **acceptable and intended behavior**:
1. Soft-confirmed F41.1 still enters the calibrator, but its `threshold_ratio` drops from 1.0 (4/4) to 0.75 (3/4), reducing its calibrated score
2. The downgraded criterion's reduced confidence flows into `avg_confidence`, further reducing F41.1's ranking signal
3. Combined effect: F32 and F41.1 scores diverge enough for the calibrator to rank correctly
4. In cases where contrastive attribution confidence is medium (0.6-0.8), status stays `met` but confidence is halved — the logic engine is unaffected, but the calibrator sees a weaker signal

The contrastive stage does NOT attempt to force rejection of any disorder. It provides a nuanced ranking signal that the calibrator uses to break ties.

### Why Not a Flat Multiplier

V11 attempted a flat calibrator-level adjustment and dropped accuracy from 41.5% to 37.0%. Root cause: margin score structural bias (F32 always gets higher excess-criteria ratio). The confidence-gated approach avoids this by:
1. Operating at criterion level (before calibrator), not score level
2. Preserving information when the contrastive agent is uncertain
3. Only fully downgrading when attribution confidence is high

## Trigger Condition

Stage 2.5 fires when ALL of:
1. `contrastive_enabled == True` in config
2. >= 2 candidate disorders have checker outputs
3. A disorder pair exists in `SHARED_CRITERIA` registry
4. At least 1 shared criterion is marked `met` in **both** disorders' checker outputs

If no trigger, Stage 2.5 is skipped entirely (zero LLM cost for non-overlapping cases).

## Pipeline Integration

### hied.py Changes

```python
# In __init__:
self.contrastive_enabled = contrastive_enabled  # from config, default False
if self.contrastive_enabled:
    from culturedx.agents.contrastive_checker import ContrastiveCheckerAgent
    self.contrastive = ContrastiveCheckerAgent(llm_client, prompts_dir)

# In diagnose(), between Stage 2 and Stage 3:
# === Stage 2.5: Contrastive Disambiguation ===
if self.contrastive_enabled:
    checker_outputs = self._run_contrastive(
        checker_outputs, transcript_text, lang,
    )
```

New method `_run_contrastive(checker_outputs, transcript_text, lang) -> list[CheckerOutput]`:
1. Build disorder->CheckerOutput index from checker_outputs
2. For each pair of disorders, call `get_shared_pairs(d1, d2)`
3. For each pair, check if both criteria are `met` in their respective CheckerOutputs
4. If any shared criteria are both-met: build AgentInput with composite keys, call ContrastiveCheckerAgent
5. If agent returns None/empty: return original checker_outputs (graceful fallback)
6. Deduplicate attributions per (disorder, criterion_id) — highest confidence wins
7. Apply confidence-gated downgrade via `apply_attribution()`
8. Recompute `criteria_met_count` for modified CheckerOutputs
9. Return modified list

Requires `from dataclasses import replace` added to `hied.py` imports.

### CheckerOutput Mutation Strategy

`CheckerOutput` and `CriterionResult` are dataclasses. Stage 2.5 creates new instances via `dataclasses.replace()` rather than mutating in-place. The modified list replaces the original `checker_outputs` variable before passing to Stage 3. No new fields are added to `CheckerOutput` or `CriterionResult` — the contrastive stage only modifies existing `status` and `confidence` values.

After replacing criteria, `criteria_met_count` must be recomputed:
```python
new_met_count = sum(1 for c in new_criteria if c.status == "met")
new_checker_output = replace(checker_output, criteria=new_criteria, criteria_met_count=new_met_count)
```

### Config Changes

```python
class ModeConfig(BaseModel):
    name: str = "single"
    type: str = "single"
    variants: list[str] | None = None
    target_disorders: list[str] | None = None
    contrastive_enabled: bool = False  # NEW — default False for safe rollout
```

Default is `False` to prevent implicit behavior changes on existing sweeps and CI jobs. Enable explicitly via YAML or CLI flag for ablation runs.

YAML override:
```yaml
mode:
  contrastive_enabled: true  # enable for contrastive ablation
```

### CLI/Sweep Integration

The `contrastive_enabled` config field must be forwarded to `HiEDMode.__init__()` at all construction sites:

1. `src/culturedx/pipeline/cli.py` — main `run` command: pass `contrastive_enabled=cfg.mode.contrastive_enabled`
2. `src/culturedx/pipeline/sweep.py` — sweep runner: same forwarding per condition
3. Any factory function that constructs HiEDMode

## Ablation Design (2x2)

| Condition | contrastive_enabled | evidence |
|-----------|-------------------|----------|
| V10 baseline | false | none |
| V10 + contrastive | true | none |
| V10 + evidence | false | with-evidence |
| V10 + both | true | with-evidence |

This produces a 2x2 factorial table for the paper, isolating the contribution of each component.

## Expected Impact

### LingxiDiag (N=200)
- 9/21 ranking errors are F32-F41.1 contests -> addressable
- Contrastive does NOT force rejection of F41.1 — instead shifts ranking signal via confidence reduction and soft-confirmation downgrade
- If contrastive fixes 6-7 ranking errors: +3-3.5pp Top-1 accuracy (41.5% -> 44.5-45%)
- Pattern C errors (12/21, F42/F43) not addressed -> future extension

### MDD-5k
- Already has high B1/B2 detection (84%, 97%) -> less room for criterion-level gains
- Contrastive may help with F32-F33 ranking (recurrence disambiguation)

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `src/culturedx/ontology/shared_criteria.py` | NEW | Shared criteria registry with F32-F41.1 mapping |
| `src/culturedx/agents/contrastive_checker.py` | NEW | ContrastiveCheckerAgent (BaseAgent subclass) |
| `prompts/agents/contrastive_checker_zh.jinja` | NEW | Chinese contrastive prompt |
| `prompts/agents/contrastive_checker_en.jinja` | NEW | English contrastive prompt |
| `src/culturedx/modes/hied.py` | EDIT | Add Stage 2.5 integration, `_run_contrastive()`, `from dataclasses import replace` |
| `src/culturedx/core/config.py` | EDIT | Add `contrastive_enabled: bool = False` to ModeConfig |
| `src/culturedx/pipeline/cli.py` | EDIT | Forward `contrastive_enabled` to HiEDMode construction |
| `src/culturedx/pipeline/sweep.py` | EDIT | Forward `contrastive_enabled` to HiEDMode construction |
| `tests/test_contrastive.py` | NEW | Unit tests for registry + agent + downgrade logic |
| `tests/test_hied_e2e.py` | EDIT | Add contrastive E2E golden cases |

## Test Strategy

### Unit Tests (`tests/test_contrastive.py`)
1. **Registry lookup**: verify `get_shared_pairs("F32", "F41.1")` returns 4 pairs
2. **Registry symmetry**: `get_shared_pairs("F41.1", "F32")` returns same pairs
3. **No overlap**: `get_shared_pairs("F32", "F20")` returns empty
4. **Confidence-gated downgrade**: test all 3 tiers with boundary values (0.59, 0.6, 0.79, 0.8)
5. **"both" attribution**: verify no change applied
6. **Agent output parsing**: mock LLM response -> verify parsed attributions
7. **B1 deduplication**: two attributions targeting F41.1.B1 -> only highest-confidence applied
8. **Parse failure fallback**: agent returns None -> original checker_outputs unchanged

### E2E Tests (`tests/test_hied_e2e.py`)
1. **Contrastive fires**: F32+F41.1 both confirmed, shared criteria both met -> contrastive called -> non-primary criteria downgraded -> weaker disorder gets soft-confirmed with lower score
2. **Contrastive skipped**: only 1 disorder confirmed -> contrastive not called
3. **True comorbid**: contrastive returns "both" for all pairs -> no changes -> both disorders confirmed
4. **Config disabled**: `contrastive_enabled=False` -> stage skipped entirely

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Contrastive LLM hallucination attributes wrong disorder | Confidence-gated downgrade limits damage; low-confidence attributions barely change outputs |
| Extra latency (~5s per case) | Only fires when trigger condition met; most cases have 0-1 confirmed disorder |
| Contrastive prompt picks up Jinja2 auto_reload changes during sweep | Same risk as V11 incident; use `auto_reload=False` in production sweeps (separate fix) |
| F41.1.B1 appears in 2 pairs — could get double-downgraded | Per-criterion-id dedup: max one downgrade per (disorder, criterion_id), highest confidence wins |
| criteria_met_count stale after downgrade | Recompute after applying all attributions (see CheckerOutput Mutation Strategy) |
| Soft-confirmation path preserves downgraded F41.1 | Intended: contrastive shifts ranking signal, does not force rejection. threshold_ratio drops from 1.0 to 0.75 |
| Default True changes production behavior silently | Default is False; must be explicitly enabled via config |

## Non-Goals

- F42/F43 shared criteria (deferred to future iteration)
- Modifying the calibrator scoring formula
- Changing the logic engine threshold rules
- Cross-lingual prompt differences beyond translation (zh and en prompts are structurally identical)
