# R21v2 Evidence Pipeline — ACTUAL Root Cause Found

**Date**: 2026-04-20
**Status**: Critical bug discovered during mechanism analysis

---

## TL;DR reversal

My previous analysis claimed evidence pipeline's F41 collapse was caused by "asymmetric
keyword-based downgrading of diffuse psychological criteria." **That analysis was wrong.**

The real cause is **much simpler and more embarrassing**: a missing Jinja template crashes the
F41.1 checker on every case when evidence pipeline is enabled. F41.1 never gets checked, so
it's never confirmed, so primary falls through to F39.

---

## Evidence

1. R21v2 `raw_checker_outputs` contains **0 F41.1 entries out of 1000 cases**.
2. R21v2 run log has exactly **1000 warnings**: `"Criterion checker failed for F41.1 ...
   criterion_checker_temporal_zh.jinja not found in search path"`.
3. The template file **does not exist** anywhere in the repo:
   ```
   $ find prompts -name "criterion_checker*"
   prompts/agents/criterion_checker_v2_improved_zh.jinja
   prompts/agents/criterion_checker_v2_zh.jinja
   prompts/agents/criterion_checker_v2_zh.jinja.backup
   # no criterion_checker_temporal_zh.jinja
   ```
4. The code that tries to load it (`src/culturedx/agents/criterion_checker.py:113-115`):
   ```python
   if temporal_summary and disorder_code == "F41.1" and input.language == "zh":
       template_name = "criterion_checker_temporal_zh.jinja"
   ```
5. `temporal_summary` is populated by the evidence pipeline (extracts temporal cues about
   symptom duration), so the code path only activates when `evidence_verification=true`.

---

## Why my previous mechanism analysis was wrong

I computed met_ratio averages by disorder and saw:
- F41 retention: 82%
- F32 retention: 90%
- F39 retention: 108%

I interpreted this as "evidence verifier asymmetrically downgrades F41." But that's backwards:
- F41.1 was **entirely absent** from R21v2 checker output (not 82% retained — 0% present).
- The `0.724` ratio I computed came from F41.0, F41.2, and F41.9 only (which don't use the
  temporal template and ran normally).
- The "82% retention" was a between-subset comparison, not a within-class downgrade.

The F39 over-prediction is real. The cause is simpler than I claimed: F41.1 is gone, so the
diagnostician's fallback (F39 = NOS mood) wins.

---

## Corrected paper narrative

### What evidence pipeline actually does (from this data)

**Unknown.** Because the template is missing, R21v2 is not measuring the evidence pipeline's
effect on diagnosis — it's measuring what happens when F41.1 checking is silently disabled.
To know what evidence pipeline does, the template bug needs to be fixed and R21v3 needs to run.

### What paper Narrative B can currently say

Honestly, very little:
1. "We tested an evidence pipeline. A template file bug prevented fair evaluation."
2. "After fixing the bug, re-running is pending."

This is a **paper-reproducibility risk**. If we ran R21v2 and wrote "evidence pipeline doesn't
help" based on Top-1 = 0.338, a reviewer who pulls the code will find the template bug and
reject our conclusion.

### What paper Narrative H can still say

The F32 bias analysis is unaffected:
- Architecture-only ablations (R6, R16): 5.9–6.7x asymmetry, no improvement
- Supervised RRF (final_combined): 1.80x asymmetry, 3.5x improvement

The R21v2 "evidence is net-negative" data point **cannot** be included in this narrative
until R21v3 (post-fix) is run.

---

## The fix

### Part 1: Template file

Create `prompts/agents/criterion_checker_temporal_zh.jinja` with F41.1 temporal evaluation
logic. The file is provided in this package.

### Part 2: Graceful fallback in checker code

Modify `src/culturedx/agents/criterion_checker.py` to fall back to `v2_zh` when the requested
template isn't found, instead of raising `TemplateNotFound` and losing the disorder entirely:

```python
try:
    template = self._env.get_template(template_name)
except Exception as e:
    logger.warning("Template %s not found for %s: falling back to v2_zh",
                   template_name, disorder_code)
    template_name = "criterion_checker_v2_zh.jinja" if input.language == "zh" else f"criterion_checker_{input.language}.jinja"
    template = self._env.get_template(template_name)
```

This ensures **future template bugs don't silently collapse a disorder class**. The fallback
logs a warning that will be visible in stdout/log, making the issue easy to catch next time.

Both parts of the fix are in the package, verified by 388/388 tests passing.

---

## Post-hoc F39-swap experiment result (still valuable)

Independent of the template bug, I ran one post-hoc analysis worth keeping:

**Rule**: If R21v2 primary = F39, swap to diagnostician's top-1 non-F39 disorder from its ranked list.

**Result**: Top-1 recovers from 0.338 to **0.427** (+8.9pp). F41 recall recovers from 2.5%
to 17.3%.

But this still misses baseline (0.505) and only partially recovers F41 (baseline had 40.1%).
The remaining gap is explained by the F41.1 template bug: even with F39 swapped out, F41.1
still isn't in the confirmed set, so F41 can only get recovered when F41.0 or F41.2 are
confirmed — which happens less often than F41.1 would.

---

## What the user needs to do

### Priority 1: Apply template fix + re-run R21 (4 hr GPU)

```bash
cd ~/CultureDx
tar xzf ~/Downloads/culturedx_queue_fixes_v2.tar.gz

# Copy template
cp queue_fixes_v2/criterion_checker_temporal_zh.jinja prompts/agents/

# Apply fallback patch
patch -p1 < queue_fixes_v2/fix_checker_template_fallback.patch

# Verify
uv run pytest tests/ -q    # should pass 388

git add -A
git commit -m "fix: missing F41.1 temporal checker template + graceful fallback"

# Re-run R21 (the template bug affected it — priority 1)
uv run culturedx run \
  -c configs/base.yaml -c configs/vllm_awq.yaml -c configs/v2.4_final.yaml \
  -c configs/overlays/r21_evidence_stacked.yaml \
  --with-evidence \
  -d lingxidiag16k --data-path data/raw/lingxidiag16k \
  -n 1000 --run-name r21_evidence_v3 --seed 42
```

### Priority 2: Investigate if baseline had a similar issue

The baseline (t1_diag_topk) doesn't use evidence pipeline, so `temporal_summary` shouldn't
be populated. But it's worth confirming the baseline F41.1 checker ran on all cases:

```bash
python3 -c "
import json
count = sum(1 for l in open('results/validation/t1_diag_topk/predictions.jsonl')
            if any(co.get('disorder_code')=='F41.1'
                   for co in (json.loads(l).get('decision_trace',{}).get('raw_checker_outputs') or [])))
print(f'Baseline cases with F41.1 in checker output: {count}/1000')
"
```

If baseline shows 1000/1000, no issue. If less, there's another instance of this bug elsewhere.

---

## Meta-lesson

I made two mistakes in the previous analysis:

1. **I didn't look at the run log**. The log showed "Criterion checker failed for F41.1" 1000 times.
   If I'd grepped the log first, I would have found this in 30 seconds.

2. **I constructed a sophisticated mechanism when a simple bug was the cause**. The "asymmetric
   keyword downgrading" story was coherent and believable but wrong. I should have checked the
   raw data (is F41.1 actually present in the output?) before theorizing about how it was downgraded.

**The correction**: always verify the null hypothesis ("did the code actually run?") before
building interpretations of its output.

Also: a 30% drop from a single architectural change should trigger more suspicion than it did.
The "evidence pipeline hurts" result is plausible, but a -16.7pp drop to near-chance F41 recall
(2.5%) should have immediately flagged "something is architecturally broken" rather than
"evidence verifier has subtle differential effects."
