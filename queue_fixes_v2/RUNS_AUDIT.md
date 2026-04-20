# CultureDx Runs Audit — Silent Template Failures

**Date**: 2026-04-20
**Scope**: All 16 validation runs on main-v2.4-refactor @ 27dc18e

## Summary: 4 runs affected by silent template bugs

| Run | Stated purpose | Checker coverage | Actual behavior | Paper-usable? |
|---|---|---:|---|---|
| t1_diag_topk | v2.4 baseline | 914/1000 (91%) | Real DtV | ✅ Yes |
| r15_no_rag | No-RAG ablation | 924/1000 (92%) | Real DtV | ✅ Yes |
| r16_bypass_logic | Skip logic engine | 996/1000 (100%) | Real DtV (no logic gating) | ✅ Yes |
| r17_bypass_checker | Skip checker (v2) | 1000/1000 (synthetic) | All-met synthetic | ✅ Yes (new R17) |
| **r6_combined** | DtV + somatization + stress | **0/1000** ✗ | **Effectively diagnostician-only** (checker silently failed) | ⚠️ Reinterpret |
| **r20_nos_variant** | DtV + NOS-aware | **0/1000** ✗ | **Effectively diagnostician-only** | ⚠️ Reinterpret |
| **r21_evidence_v2** | DtV + evidence | F41.1: 0/1000 others: 995/1000 | F41.1 selectively disabled | ⚠️ Re-run |
| r7_triage_top8 | Triage top-8 | variable (legitimate) | Real DtV with dynamic scope | ✅ Yes |
| r18_single_llm | No MAS | N/A (mode=single) | Real | ✅ Yes |

## The three template bug variants

### Variant A: `prompt_variant=v2_somatization` propagates to checker (R6)

Config `r6_combined.yaml` sets `mode.prompt_variant: v2_somatization` to use the somatization
diagnostician prompt. But `_effective_checker_variant` falls back to `self.prompt_variant` when
no explicit checker variant is set (hied.py:171-172), so the checker tries to load
`criterion_checker_v2_somatization_zh.jinja` — which doesn't exist. Falls to else branch →
`criterion_checker_zh.jinja` — which also doesn't exist. Every disorder's checker raises
`TemplateNotFound`, which is caught upstream and turned into "checker failed" warnings.

With all checkers failing, `force_prediction=true` (set in v2.4_final.yaml) kicks in and
primary defaults to diagnostician's top-1. So the run produces predictions, but they reflect
diagnostician-only behavior, not DtV.

**Evidence**: R6 primary == diagnostician top-1 in **999/999** cases.

### Variant B: Same as A but with `v2_nos` (R20)

Identical mechanism. `r20_nos_variant.yaml` uses `prompt_variant: v2_nos`, which has no
corresponding checker template. Also 0/1000 checker coverage, effectively diagnostician-only.

**Evidence**: R20 primary == diagnostician top-1 in **1000/1000** cases.

### Variant C: Hardcoded `temporal_zh.jinja` for F41.1 (R21v2)

Different code path. `criterion_checker.py:113-114`:
```python
if temporal_summary and disorder_code == "F41.1" and input.language == "zh":
    template_name = "criterion_checker_temporal_zh.jinja"
```

`temporal_summary` gets populated when the evidence pipeline runs. The template doesn't exist.
Only F41.1 is affected; other disorders use v2_zh.jinja normally.

**Evidence**: R21v2 has 995/1000 checker coverage for every disorder **except** F41.1, which
has 0/1000.

---

## How this changes the paper story

### R6's actual contribution: diagnostician prompt effect

**Previous claim**: "R6 (somatization + stress detection in DtV pipeline) improves Top-1 by +1.7pp."

**Corrected claim**: "R6 (somatization + stress detection, with DtV checker disabled by template
bug) improves Top-1 by +1.7pp. The improvement comes from the diagnostician prompt and stress
detector alone. DtV's contribution to R6 is untested."

Valid comparison: R6 vs t1_triage_no_meta (also diagnostician-only, Top-1 = 0.530). R6 is
slightly LOWER (0.522 vs 0.530). So the somatization prompt appears roughly neutral, not +1.7pp.

The Top-1 improvement is then actually: R6 (0.522) – baseline with checker (0.505) = **+1.7pp**,
but this is comparing two different architectures (diagnostician-only vs DtV), not testing the
somatization effect alone.

**To cleanly test somatization**: run R6 with the template fallback fix so checker actually executes.

### R20's actual contribution: NOS prompt hurts diagnostician

**Previous claim**: "R20 NOS-aware diagnostician Top-1 = 0.491, -1.4pp vs baseline."

**Corrected claim**: Same number but reinterpret. R20 was effectively diagnostician-only with
NOS prompt. Compared to R6 (diagnostician-only with somatization prompt, Top-1 = 0.522) and
R17 (diagnostician-only with v2 prompt, Top-1 = 0.507):

| Diagnostician prompt variant | Top-1 | Mode |
|---|---:|---|
| v2 (default) | **0.507** | R17 (effectively diag-only via synthetic checker) |
| v2 (default) | 0.478 | r18 (single LLM, no triage) |
| v2_somatization + stress | 0.522 | R6 (diag-only via template bug) |
| v2_nos | **0.491** | R20 (diag-only via template bug) |

So **v2_nos prompt hurts the diagnostician by ~1.6pp** relative to the default v2 prompt
(0.507 → 0.491). This is a real finding about the prompt's effect on diagnostician quality.

### R21v2's actual result: evidence pipeline effect is untested

**Previous claim (twice wrong)**: "Evidence pipeline causes asymmetric criteria downgrading
harming F41."

**Corrected claim**: "R21v2 F41 collapse is entirely explained by F41.1 checker never running
(TemplateNotFound). Evidence pipeline's true effect is untested."

This is the most significant correction. The entire "linguistic artifact" narrative I built
around R21v2's per-disorder retention numbers was **wrong**, because the 0.724 F41 retention
was computed across F41.0, F41.2, F41.9 (F41.1 was absent from the data entirely).

---

## What paper narratives still hold

### Narrative H (LLM priors dominate; only supervised RRF fixes them) — Partially intact ⚠️

**Original claim**: 4 converging ablations all fail to fix F32 bias; only final_combined works.

| Ablation | F41→F32 asymmetry | Status |
|---|---:|---|
| R6 (somatization + stress) | 5.93x | ❌ R6 actually didn't use DtV checker — this wasn't a DtV-level ablation |
| R16 (bypass logic engine) | 6.65x | ✅ Valid |
| R17 (bypass checker — OLD) | ??? | ❌ Only bypassed 1/3 paths — invalid |
| R21 (evidence pipeline) | ∞ | ❌ F41.1 template bug, not evidence effect |
| R4_contrastive_primary | — | ✅ Likely valid (different mechanism) |
| **final_combined (supervised RRF)** | **1.80x** | ✅ Valid |

After audit, only **R16** remains as a valid architectural ablation showing F32 bias is robust
to architecture changes. Narrative H needs:
- R6 re-run with template fix to measure actual somatization+DtV effect
- R17 v2 (the new refactored bypass) to measure checker contribution
- R21 v3 (with temporal template) to measure evidence pipeline

After these, Narrative H could have a clean 4-point comparison. Right now it has 1.

### Narrative A (interpretability via criterion evidence) — Intact ✅

Criterion-level output from baseline/R16/R17 is all intact. This narrative isn't affected.

### Narrative F (MAS adds +2.7pp over single LLM) — Intact ✅

r18_single_llm (0.478) vs t1_diag_topk (0.505) comparison is valid.

### Narrative B (evidence pipeline helps/hurts) — Deferred

Cannot be written until R21 v3 runs.

### SOTA claim: R16 + final_combined stack at Top-1 = 0.562 — Intact ✅

Both components are valid runs. Post-hoc stack doesn't use the broken runs.

---

## Priority-ordered re-run list (after applying template fallback fix)

1. **R21 v3** (4 hr) — Required for Narrative B. Evidence pipeline with F41.1 working.
2. **R6 v2** (4 hr) — Required for Narrative H. Somatization + DtV actually running.
3. **R20 v2** (4 hr) — Required for Narrative H. NOS + DtV actually running.
4. **R17 v2** (4 hr) — Required for Narrative H. Fully refactored bypass actually covering all checker paths.
5. **R13 v3** (4 hr) — Qwen3-8B backbone. Separate investigation.
6. **R14 v3** (4 hr) — Yi-34B backbone. Separate investigation.

Total: **24 GPU hours** to get all narratives onto solid ground.

---

## Minimum viable paper

If GPU budget is tight, the minimum set to re-run is just **R21 v3 + R17 v2** (8 hr).

With those two completing successfully:
- Narrative H has R16 + R17 + R21 as 3 architecture ablations vs supervised RRF — enough
- Narrative B can be written (evidence pipeline effect known)
- SOTA claim still stands (final_combined + R16 = 0.562)
- R6/R20 can stay as "preliminary" results flagged in paper appendix

---

## Audit methodology (reproducible for next time)

For future queue runs, before accepting results:

1. **Check run log for template failures**:
   ```bash
   grep -c "TemplateNotFound\|Criterion checker failed" results/validation/$RUN/run.log
   # Should be 0 (or <20 for rare edge cases)
   ```

2. **Check checker coverage per disorder**:
   ```python
   # 14 disorders × N cases should yield ~14N raw_checker_outputs entries
   # If any disorder has 0 or <80% coverage, something broke
   ```

3. **Check primary agreement with diagnostician top-1**:
   ```python
   # If primary == diagnostician_top_1 in >95% of cases, checker is not influencing selection
   # → either checker failed OR logic engine is overly permissive
   ```

If any of these three checks flag, the run is not DtV — it's diagnostician-only with extra compute.

I should have included these checks in the smoke test I wrote for the first queue. Next queue
package will include them as `scripts/audit_run.py`.
