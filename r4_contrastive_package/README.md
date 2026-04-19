# R4: Primary-level Contrastive Disambiguation

## What this does

Runs an LLM "second opinion" specifically for the F41/F32 decision, AFTER the
logic engine has confirmed both. Attacks the 160 F41→F32 ranking errors found
in Q4 analysis.

## Expected impact (from oracle simulation)

| Scenario | Top-1 | F1_m | F1_w |
|---|---|---|---|
| t1_diag_topk baseline | 0.505 | 0.190 | 0.462 |
| R4 Oracle (perfect) | 0.688 | 0.216 | 0.570 |
| R4 Realistic (70% F41 acc) | 0.595 | 0.202 | 0.510 |
| R4 Pessimistic (30% F41 acc) | ~0.530 | ~0.195 | ~0.475 |

**Realistic expectation**: +5 to +9pp Top-1 improvement. If LLM has same F32
bias as diagnostician, gain could be <3pp. R4 run also tests this hypothesis.

## Integration steps

### Step 1: Copy files into repo

```bash
cd ~/CultureDx

# Prompts
cp /path/to/r4_contrastive_package/prompts/agents/contrastive_primary_zh.jinja \
   prompts/agents/

# Config
cp /path/to/r4_contrastive_package/configs/overlays/r4_contrastive_primary.yaml \
   configs/overlays/

# Agent module
cp /path/to/r4_contrastive_package/src/culturedx/agents/contrastive_primary.py \
   src/culturedx/agents/
```

### Step 2: Modify `src/culturedx/modes/hied.py`

Find the location where `logic_engine_confirmed_codes` is determined (after
logic_engine.evaluate() call) and BEFORE the final primary selection.

Add these imports at the top:

```python
from culturedx.agents.contrastive_primary import (
    apply_contrastive_primary, load_prompt_template,
)
from culturedx.eval.lingxidiag_paper import to_paper_parent
```

In the `__init__` method, cache the prompt template:

```python
if getattr(self.cfg.mode, "contrastive_primary_enabled", False):
    prompt_name = self.cfg.mode.get("contrastive_primary_prompt", "contrastive_primary_zh")
    self._contrastive_primary_template = load_prompt_template(
        prompt_name, Path(self.cfg.paths.prompts_dir)
    )
```

In the main pipeline method, after getting `logic_engine_confirmed_codes` and
computing initial `primary_diagnosis` + `ranked_codes`, insert:

```python
# --- R4: Primary-level Contrastive Disambiguation ---
if getattr(self.cfg.mode, "contrastive_primary_enabled", False):
    trigger_pairs = self.cfg.mode.get(
        "contrastive_primary_trigger_pairs", [["F32", "F41"]]
    )
    threshold = self.cfg.mode.get(
        "contrastive_primary_confidence_threshold", 0.70
    )
    llm_config = self.cfg.mode.get("contrastive_primary_llm", {})

    primary_diagnosis, ranked_codes, contrastive_trace = await apply_contrastive_primary(
        logic_confirmed_codes=logic_engine_confirmed_codes,
        ranked_codes=ranked_codes,
        raw_checker_outputs=all_checker_outputs,
        transcript_text=transcript_text,
        current_primary=primary_diagnosis,
        trigger_pairs=[tuple(p) for p in trigger_pairs],
        confidence_threshold=threshold,
        llm_runtime=self.llm_runtime,
        prompt_template=self._contrastive_primary_template,
        llm_config=llm_config,
        to_paper_parent_fn=to_paper_parent,
    )

    # Save trace for post-hoc analysis
    decision_trace["contrastive_primary"] = contrastive_trace
```

### Step 3: Run R4 GPU experiment

```bash
uv run culturedx run \
  -c configs/base.yaml \
  -c configs/vllm_awq.yaml \
  -c configs/v2.4_final.yaml \
  -c configs/overlays/r4_contrastive_primary.yaml \
  -d lingxidiag16k --data-path data/raw/lingxidiag16k \
  -n 1000 --seed 42 --run-name r4_contrastive_primary \
  2>&1 | tee outputs/r4_contrastive.log
```

Expected runtime: **~4.5 hr** (baseline 4 hr + 25% overhead for contrastive calls on 689 cases).

### Step 4: Post-hoc analysis

```bash
# Apply Stage 2-5 (comorbid cap, RRF, F1-OPT, Top-3 fix)
python3 scripts/run_final_combined.py \
  --dtv-run results/validation/r4_contrastive_primary \
  --tfidf-run results/validation/tfidf_baseline \
  --output-dir results/validation/r4_final \
  --fit-offsets

# Oracle analysis on R4 output
python3 scripts/oracle_analysis.py --run-dir results/validation/r4_contrastive_primary

# Q4 pattern analysis: is F41→F32 bucket smaller now?
python3 scripts/q4_v2_f41_f32.py  # (edit script to point to r4 run)

# Compare contrastive_trace distribution
python3 -c "
import json
from pathlib import Path
records = [json.loads(line) for line in open('results/validation/r4_contrastive_primary/predictions.jsonl')]
triggered = sum(1 for r in records if r.get('decision_trace', {}).get('contrastive_primary', {}).get('triggered'))
overridden = sum(1 for r in records if r.get('decision_trace', {}).get('contrastive_primary', {}).get('overridden'))
print(f'Triggered: {triggered}/1000 ({triggered/10}%)')
print(f'Overridden: {overridden}/1000 ({overridden/10}%)')
print(f'Override rate when triggered: {overridden/triggered*100:.1f}%')

# Check if contrastive agent has F32 bias
override_to_f32 = sum(1 for r in records if r.get('decision_trace', {}).get('contrastive_primary', {}).get('chosen_parent') == 'F32' and r.get('decision_trace', {}).get('contrastive_primary', {}).get('overridden'))
override_to_f41 = sum(1 for r in records if r.get('decision_trace', {}).get('contrastive_primary', {}).get('chosen_parent') == 'F41' and r.get('decision_trace', {}).get('contrastive_primary', {}).get('overridden'))
print(f'Overrides to F32: {override_to_f32}')
print(f'Overrides to F41: {override_to_f41}')
"
```

## Understanding metrics to track

**Primary metric**: Top-1 improvement over t1_diag_topk baseline.

**Diagnostic metrics** (critical for understanding whether R4 works):
- `contrastive_primary.triggered` rate: expect ~689/1000 (68.9%)
- `contrastive_primary.overridden` rate: depends on F32 bias of LLM
  - High (>30%): LLM doesn't have F32 bias, overrides often → expect big Top-1 gain
  - Low (<10%): LLM has F32 bias, rarely overrides → minimal gain
- Override direction ratio (F41:F32): if ~1:1, bias is balanced; if heavily F41-only, oracle-like

**Post-override per-class F1**:
- F41 F1 should INCREASE significantly (current 0.58 baseline)
- F32 F1 should slightly DECREASE (some correct F32 flipped to F41)
- Net F1_m: small positive (+1-3pp)

## Key falsifiable hypotheses

1. **H1**: LLM contrastive agent does NOT have same F32 bias as diagnostician
   - Tested by: override rate and direction
2. **H2**: F41/F32 ranking errors can be reduced by >50%
   - Tested by: re-running Q4 analysis on R4 output
3. **H3**: R4 gain stacks with F1-OPT
   - Tested by: running Stage 2-5 on R4 output and comparing to final_combined

## Files in this package

- `prompts/agents/contrastive_primary_zh.jinja` — the LLM prompt
- `configs/overlays/r4_contrastive_primary.yaml` — config overlay
- `src/culturedx/agents/contrastive_primary.py` — agent implementation
- `scripts/r4_integration_plan.py` — integration pseudocode (reference)
- `scripts/r4_oracle_simulation.py` — zero-GPU simulation (already run)
