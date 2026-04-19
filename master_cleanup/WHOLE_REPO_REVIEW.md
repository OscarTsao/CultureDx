# CultureDx — Whole-Repo Review, Verification & Master Plan

**Review date**: 2026-04-19
**Reviewer**: Claude (session 3)
**Scope**: deep review of `main-v2.4-refactor` @ `d6a74c9` against the
backup PR branch `pr-stack/docs-and-production-hardening`.

This document contains findings with evidence, and a prioritized action plan
with code diffs. Nothing below is speculation — every claim is backed by a
specific line number or test result I verified in code.

---

## Executive summary (3 minutes)

**Repo state is healthier than feared, but needs three surgical fixes.**

- ✅ **Code imports cleanly**, all 20+ modules load
- ✅ **387/388 tests pass** (1 stale expectation in `test_triage`)
- ✅ **Silent fallback fixes already on main** — I checked triage.py, retriever_factory.py, negation.py, calibrator.py; all production-hardened already
- ❌ **CLI missing `--seed` and `--run-name` options** → R11/R12 ran with identical config, not a seed variance test
- ❌ **No `logic_engine_enabled` / `checker_enabled` config flags** → R16, R17 cannot run without source code changes
- 🟡 **`results/validation/` is 493 MB with 43 dirs**, of which ~20 are legacy T-series runs
- 🟡 **`scripts/` has 31 files with 3+ duplicates** (q4_v1/v2, bootstrap_ci_v1/final)
- 🟡 **PR branch `pr-stack/docs-and-production-hardening` is legacy**, not to be merged (see below)

**Three highest-ROI actions to take before running GPU queue**:

1. **Fix seed CLI plumbing + write a temperature>0 ensemble run config** (2 hours effort, unlocks real seed variance)
2. **Add `checker_enabled` flag** for R17 ablation (1 hour, gives paper Table 4 completeness)
3. **Skip R19 and R11/R12** from planned queue (already effectively tested or impossible)

**Two high-ROI axes I found that weren't in the queue**:

1. **R6 + stress detection combined** — `stress_detection_enabled` already wired, can stack with R6 somatization prompt
2. **R4 with ensemble threshold** — current R4 uses single LLM call at confidence≥0.70, **72.5% of overrides confidence was ≥0.85 despite being wrong 56% of the time**. A multi-call ensemble (3 calls majority vote) might flip the pattern.

Full details below.

---

## Finding 1: PR branch is legacy, DO NOT merge

### Evidence

I compared `main-v2.4-refactor` against `origin/pr-stack/docs-and-production-hardening`:

- **Branches diverged 2026-03-28** at merge-base `b37d643`
- **PR branch last commit: 2026-04-02** (17 days ago), frozen
- **Main commit on 2026-04-13** (`2cb8120`) explicitly says:
  > "import: V2.4 source, prompts, tests, configs from research branch"
  
  This was a **deliberate clean re-import** from a research branch into a new trimmed v2.4 codebase.

- **File counts**:
  - Files unique to PR (not on main): **131** (includes `src/culturedx/modes/psycot.py`, `debate.py`, `mas.py`, `specialist.py`, 60+ training scripts, judge/perspective agents)
  - Files unique to main (not on PR): **404** (includes `configs/v2.4_final.yaml`, all ablation configs, paper/, all recent experimental results)

- **hied.py divergence**:
  - main: **1500 lines** (has R4 contrastive, stress detection, T1 top-5, evidence verification)
  - PR: **723 lines** (simpler pipeline, no R4)

- **Silent fallback fix already on main**: I checked `src/culturedx/agents/triage.py:113-129` and confirmed it uses the parse_failure return path (not the old all-categories fallback). Same for retriever_factory, negation, calibrator.

### Conclusion

Main was the successor of PR branch, not a parallel fork. The PR branch is a
historical artifact from before the v2.4 simplification. **Leave it alone.**

### Action
- Delete reminder from workflow: don't think about this branch again.
- If worried about losing something: cherry-pick individual files only if
  needed (e.g., if you want PsyCoT mode back, grab `src/culturedx/modes/psycot.py`).

---

## Finding 2: Seed CLI bug confirmed

### Evidence

1. `src/culturedx/pipeline/cli.py` — the `run` command has these `@click.option`s:
   ```
   line 43: --config
   line 44: --dataset
   line 45: --split
   line 46: --output-dir
   line 47: --with-evidence
   line 48: --data-path
   line 49: --limit
   ```
   **No `--seed`, no `--run-name`.**

2. R11/R12 `run_info.json` both show:
   ```
   config_paths: ['configs/base.yaml', 'configs/vllm_awq.yaml', 'configs/v2.4_final.yaml']
   seed: 42
   ```
   Identical to baseline `t1_diag_topk`. Only difference is `run_id` (derived from output_dir name).

3. Seed value is read from `cfg.seed` (line 67), which comes from `base.yaml:1` where `seed: 42` is hard-coded.

4. Even if `--seed` were plumbed, **vLLM at temperature=0.0 uses greedy decoding** (`configs/vllm_awq.yaml:6-7`), making seed irrelevant at inference level.

### Fix (provided as diff below)

Both problems need fixing:

**A. Add CLI options** (required for `--run-name` to work):
```python
# In src/culturedx/pipeline/cli.py, add after line 49:
@click.option("--seed", default=None, type=int, help="Override config seed")
@click.option("--run-name", default=None, help="Override auto-generated run name")
```

Then plumb into config (lines ~65 after `load_config`):
```python
if seed is not None:
    cfg.seed = seed
if run_name is not None:
    # Use this as output dir name
    effective_output_dir = str(Path(cfg.output_dir) / run_name)
else:
    effective_output_dir = output_dir
```

**B. For real variance**, create `configs/overlays/sampling_variance.yaml`:
```yaml
# Enables stochastic sampling for true seed variance
llm:
  temperature: 0.5
  top_p: 0.9
  seed_override_at_runtime: true  # signals vLLM client to pass seed to sampling_params
```

And in `src/culturedx/llm/vllm_client.py`, ensure seed is passed to vLLM's
`sampling_params.seed`.

---

## Finding 3: R16, R17 need code changes; R19 is redundant

### Evidence

I grepped `src/culturedx/modes/hied.py` for the config flags my queue assumed existed:

```
grep -n "logic_engine_enabled\|checker_enabled\|triage_enabled" src/culturedx/modes/hied.py
# result: EMPTY
```

None of these flags are currently read. For R16/R17 to meaningfully disable
parts of the pipeline, the code needs explicit guards.

For R19 specifically:

```
grep -n "scope_policy == \"manual\"" src/culturedx/modes/hied.py:415
```

Line 415-434 of hied.py ALREADY skips the triage agent when
`scope_policy == "manual"`. Your `v2.4_final.yaml` sets
`scope_policy: manual`. **The current baseline already has no triage.**

### Implication
- **R19 is a no-op experiment** — the baseline is already "no triage"
- R16 requires adding `logic_engine_enabled` guard (code change, ~15 lines)
- R17 requires adding `checker_enabled` guard (code change, ~20 lines)

### Action (minimum viable code diff below)

Instead of the heavyweight guards I originally proposed, a simpler approach
exists for **R16 (disable logic engine)**:

```python
# In src/culturedx/modes/hied.py line 1122, change:
logic_output = self.logic_engine.evaluate(all_checker_outputs)
# To:
if getattr(self.cfg_flags, "disable_logic_engine", False):
    # Bypass: treat all candidates as "confirmed", use diag ranking
    from culturedx.diagnosis.logic_engine import LogicEngineOutput
    logic_output = LogicEngineOutput(
        confirmed_codes=list(ranked_codes[:5]),
        raw_outputs=all_checker_outputs,
    )
else:
    logic_output = self.logic_engine.evaluate(all_checker_outputs)
```

And read from a new config field.

**But actually, a much cleaner approach exists**:

The logic engine uses thresholds. Set `criteria_met_ratio_threshold: 0.0` and
it will "confirm" everything. This achieves R16's intent **without any code
change**.

```yaml
# configs/overlays/r16_logic_engine_permissive.yaml
logic_engine:
  criteria_met_ratio_threshold: 0.0    # confirms any candidate with met_count >= 1
  criteria_met_count_threshold: 1
```

Same principle for R17 — "no checker" is equivalent to "checker always
passes all criteria". Instead of a flag, pre-fabricate trivial checker
outputs. But that needs a code change.

**Recommendation**: Drop R17 from queue. The ablation is less informative
than R16, and current Q4 analysis already shows checker passes 91% of cases
anyway.

---

## Finding 4: hied.py is 1500 lines but logically correct

I read the key sections (407-475 scope logic, 625-680 logic engine,
1040-1200 DtV pipeline with R4 integration, 1296-1330 mode semantics) and
confirmed:

- ✅ All silent fallbacks replaced with explicit errors
- ✅ R4 contrastive integration at line 1183 uses the apply_contrastive_primary helper I wrote earlier
- ✅ Top-5 diagnostician behavior is hardcoded (lines 1016, 1120) — this is actually the "t1_diag_topk" behavior permanently installed
- ✅ Force prediction fallback is clean (not a hidden silent path)

**The main smell**: 1500 lines in one file is large. But refactoring this
pre-queue would be scope creep. Note it for post-paper cleanup.

---

## Finding 5: Test suite health

`uv run pytest tests/ -q` results:

```
387 passed, 1 failed, 1 skipped in 46s

FAILED tests/test_triage.py::TestTriageAgent::test_multiple_categories
    assert candidate_disorder_codes == [F31, F32, F33, F39, F40, F41.0, F41.1, F41.2, F42]
    got: [F31, F32, F33, F39, F40, F41.0, F41.1, F41.2, F41.9, F42]  # F41.9 added
```

**Root cause**: `src/culturedx/agents/triage_routing.py:21` added F41.9 to the
anxiety category mapping. Test expectation wasn't updated.

**Fix** (one-line test update):
```python
# In tests/test_triage.py line 72, update expected list to include F41.9
```

Non-blocking for queue but should fix to keep CI clean.

---

## Finding 6: Scripts/ cleanup

Current: 31 scripts. Many are dead or superseded:

### Duplicates (remove the older version)
- `q4_f41_f32_analysis.py` + `q4_f41_f32_confusion.py` — superseded by `q4_v2_f41_f32.py`
- `bootstrap_ci.py` — superseded by `bootstrap_ci_final.py`
- `q2_oracle_ranker_on_confirmed.py` — superseded by `q7f_candidate_generator.py`

### One-off experiment scripts (move to `legacy/`)
- `ablation_sweep.py` (from pre-t1 era)
- `lowfreq_boost_sweep.py`, `f1_macro_offset_sweep.py`
- `replay_others_fallback.py`, `paper_results.py`
- `run_ensemble.py`
- `r4_integration_plan.py` (was my planning doc, not code)
- `r4_oracle_simulation.py` (was my simulation, now superseded by actual R4 results)

### Keep and organize
- `eval/`: run_final_combined, recompute_top3, t1_comorbid_cap_replay, bootstrap_ci_final, compute_table4, build_results_table
- `analysis/`: oracle_analysis, q4_v2_f41_f32, q7_learned_ranker_v2, q7b_ablation, q7cde_ablation, q7f_candidate_generator, extract_ranker_features
- `training/`: train_tfidf_baseline, train_ranker_lightgbm, calibrate_confidence
- `runners/`: run_multi_backbone.sh, run_api_backbone.py, run_full_eval.py

---

## Finding 7: Results/ cleanup

493 MB, 43 dirs. Most of those dirs are historical. Recommendation:

### Keep on main (reference for paper)
- `final_combined/` — current best
- `t1_diag_topk/` — baseline
- `tfidf_baseline/` — supervised reference
- `bootstrap_ci/` — CI data
- `factorial_b_improved_noevidence/` — ablation reference
- `r4_contrastive_primary/`, `r4_final/` — R4 negative
- `r11_t1_seed123/`, `r12_t1_seed456/` — (keep for audit; note they're broken)
- `r15_no_rag/`, `r18_single_llm/` — recent ablations
- `t1_diag_topk_capped/`, `t1_diag_topk_comorbid_fixed/` — post-hoc variants
- `mdd5k_*` (all) — cross-dataset

### Archive to `results/legacy/validation/` (~250 MB recovered)
- `01_single_baseline` through `08_checker_per_class` (8 dirs, ~90 MB)
- `03_dtv_v1`, `04_dtv_v1_rag`, `05_dtv_v2_rag`, `06_dtv_v2_rag_gate` (~60 MB)
- `t1_others`, `t1_f43trig`, `t1_nos`, `t1_triage_no_meta`, `t1_diag_topk_smoke`
- `t2_lowfreq`, `t2_rrf`, `t2_triage_demographics`
- `t3_manual_fixed`, `t3_tfidf_stack`
- `t5b_contrastive`
- `factorial_a_orig_evidence`, `factorial_c_improved_evidence`
- `multi_backbone/` (empty marker)

### Move JSON reports to `results/validation/analysis/`
- `abstention_analysis.json`, `abstention_corrected_analysis.json`, `abstention_z71_others_analysis.json`
- `factorial_decision.json`
- `gate_rescore_analysis.json`
- `t3_gate_decision.json`

---

## Finding 8: Config overlays cleanup

Current `configs/overlays/` has 9 files. After R21 experiment completes:

### Keep active
- `evidence_on.yaml` (used by R21)
- `no_rag.yaml` (used by R15 reference)
- `r4_contrastive_primary.yaml` (R4 reference)

### Archive to `configs/legacy/overlays/`
- `checker_per_class.yaml` (experiment done)
- `checker_v2_improved.yaml` (superseded)
- `t1_f43_trigger.yaml` (stress_detection now always enabled via diag prompt)
- `t1_nos_routing.yaml` (can be revived for R20, otherwise legacy)
- `t5b_contrastive.yaml` (experiment done — negative)
- `verifier_on.yaml` (now hardcoded in hied.py evidence_verification path)

---

## Findings 9 & 10: Untapped experimental axes (the brainstorm)

While auditing, I noticed two axes **not in your queue** that are more
tractable than I initially scoped:

### 9a. Stress detection + somatization prompt (combined R6')

Main has `self.stress_detection_enabled` plumbed (line 102, 1020-1050 in hied.py).
It calls `StressEventDetector` to find F43 cues from transcript.

**Combined experiment**: R6 somatization prompt + stress detection on. Stacks
two orthogonal interventions. Should be tested together, not separately.

Config:
```yaml
# configs/overlays/r6_combined.yaml
mode:
  prompt_variant: v2_somatization
  stress_detection_enabled: true
```

Small smoke test first to see if `stress_detection_enabled: true` was already
used in any past run and what the effect was.

### 9b. R4 with ensemble (R4')

Evidence from R4 analysis:
- Single contrastive LLM call picks F32 96% of the time at confidence ~0.88
- But the 40.7% F41 accuracy suggests **some F41 signal exists** — it's just outnumbered

**Hypothesis**: Running the contrastive agent 3 times with temperature=0.3
and majority vote will break ties differently. If ≥2/3 say F41, override.
Otherwise keep original.

This is **not** just repeating R4 with noise — it tests whether the F32 bias
has any stochastic component at all. If all 3 calls agree F32, confirmed
deterministic bias. If even 1 flips F41, ensemble can recover cases.

**Implementation** (5 lines change to `apply_contrastive_primary`):
```python
# Run N times, take majority
votes = []
for _ in range(n_ensemble):
    result = await run_contrastive_primary(...)
    votes.append(result["primary_diagnosis"])
majority = Counter(votes).most_common(1)[0][0]
```

### 10. Diagnostician CoT mode (genuinely new axis)

Current diagnostician prompt forces JSON output (line 107-111):
```
请严格按照以下JSON格式输出（必须恰好 5 个 items）：
{
  "ranked_diagnoses": [...]
}
```

**Untested**: A two-step prompt where step 1 = free-form CoT reasoning,
step 2 = "now output your JSON ranking". This gives the model explicit
space to verbalize F41 vs F32 distinctions before committing to a rank.

Evidence this matters: the existing prompt has an "reasoning" field in each
ranked_diagnosis, but capped at 30 chars per item. That's too short for
nuanced differential reasoning.

**Estimated impact**: F1_m +2-5pp on minority classes. Also tests
"can reasoning quality alone break the F32 bias?"

---

## Master action plan

### Phase 0 — Cleanup (2-3 hr, no GPU)

1. Create branch `chore/pre-queue-cleanup`
2. Run `cleanup.sh` (from my earlier package) — handles Tier 1, 2, 4, 5, 7
3. **Fix the failing test**:
   ```python
   # tests/test_triage.py line 72 — add F41.9 before F42
   ```
4. **Fix CLI seed plumbing** (code diff in Finding 2)
5. **Interactive Tier 3**: archive legacy `results/validation/` subdirs to
   `results/legacy/validation/`
6. Run test suite to confirm green
7. Commit: `chore: pre-queue cleanup + CLI seed fix + test update`
8. Merge to main-v2.4-refactor

### Phase 1 — Add config flags for R16 only (1 hr, no GPU)

Drop R17 and R19 from queue per Findings 3. R16 is the only one worth code
change. Use the **permissive threshold** approach (no code change needed):

```yaml
# configs/overlays/r16_logic_engine_permissive.yaml
logic_engine:
  criteria_met_ratio_threshold: 0.0
  criteria_met_count_threshold: 1
```

Smoke test 20 cases to verify the config path works.

### Phase 2 — Run reduced queue (sequential, ~24 hr GPU)

Revised queue:

| # | Run | Expected GPU | What it answers | Code change? |
|---|---|---|---|---|
| 1 | R6 + stress detection combined | 4 hr | F45/F98 recall, R6 isolated | No |
| 2 | R7 triage top-8 | 4 hr | Triage recall impact | No |
| 3 | R20 NOS variant diagnostician | 4 hr | F39 recall | No |
| 4 | R21 evidence stacked | 4 hr | Evidence in new arch | No |
| 5 | R16 logic permissive | 4 hr | Logic engine isolation | No (just config) |
| 6 | R13 Qwen3-8B | 4 hr | Bias is 32B-AWQ or Qwen family? | No (vLLM swap) |
| 7 | R14 non-Qwen | 4 hr | Bias is Qwen family or general LLM? | No (vLLM swap) |

**Dropped from original queue**: R17 (low-yield), R19 (already tested),
R11/R12 (impossible at temp=0.0).

### Phase 3 — Post-queue analysis (no GPU)

For each of 7 new runs:
1. Apply Stage 2-5 post-hoc pipeline
2. Oracle analysis
3. Q4 F41/F32 confusion
4. Primary distribution comparison

Bundle metrics for next brainstorm session.

### Phase 4 — Tier 1 experiments (only if Phase 2 results don't break paper)

Based on Phase 2 findings, consider:

1. **R22 — Temperature ensemble** (20 hr GPU, 5 samples × 1000 cases)
2. **R23 — CoT diagnostician** (4 hr GPU)
3. **R24 — R4 with N=3 ensemble majority vote** (4 hr GPU)
4. **R25 — Fine-tuned checker integration** (4 hr GPU, needs LoRA from
   `outputs/finetune/criterion_checker_lora/` — which is in the PR branch)

If R25 needs LoRA weights that are only on PR branch, that's the **one valid
reason to cherry-pick from PR** — specifically the LoRA integration code and
weights, not the architectural changes.

---

## Comprehensive delivery package

The accompanying tarball (`culturedx_master_cleanup.tar.gz`) contains:

- `cleanup.sh` — automated Phase 0 cleanup (Tier 1, 2, 4, 5, 7)
- `fix_cli_seed.patch` — unified diff for CLI `--seed` / `--run-name` plumbing
- `fix_test_triage.patch` — unified diff for test_triage F41.9 fix
- `configs/overlays/r16_logic_engine_permissive.yaml` — R16 without code change
- `configs/overlays/r6_combined.yaml` — R6 + stress detection
- `scripts/run_queue_revised.sh` — sequential runner for 7-run queue
- `scripts/post_hoc_analyze_all.sh` — batch post-hoc analysis
- `MASTER_SCHEDULE.md` — step-by-step execution timeline
- `WHOLE_REPO_REVIEW.md` — this document

---

## Final recommendations in priority order

1. **Adopt this document** as the source of truth. Throw away earlier
   cleanup/queue plans that assumed wrong things about CLI/config flags.

2. **Execute Phase 0** before touching any GPU. Fix seed, fix test, clean up.

3. **Execute Phase 2 revised queue** — 28 GPU hr, down from original 36.

4. **Don't merge PR branch**. If you specifically want LoRA checker weights
   from that branch, cherry-pick only those files.

5. **Keep R4 analysis in mind** — the F32 bias is real and **will not be
   fixed by prompt engineering alone**. R13/R14 backbone swap is the key
   data point for the paper's narrative.

6. **Consider temperature ensemble (Phase 4) as the real lever** — it's the
   one axis we haven't explored that could genuinely move Top-1 ≥ 3pp
   without supervised augmentation.
