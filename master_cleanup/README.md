# CultureDx Master Cleanup & Queue Package

This package is the authoritative result of a deep whole-repo review on 2026-04-19.
It supersedes earlier cleanup/queue attempts from previous sessions.

## What's inside

```
master_cleanup/
├── README.md                            This file
├── WHOLE_REPO_REVIEW.md                 Complete review with 10 findings
├── cleanup.sh                           Automated Phase 0 cleanup
├── fix_cli_seed.patch                   Add --seed and --run-name to CLI
├── fix_test_triage.patch                Fix failing test (F41.9 addition)
├── r16_bypass_logic_engine.patch        Optional: enable R16 ablation
├── configs/overlays/
│   ├── r16_bypass_logic_engine.yaml    R16 overlay (needs patch)
│   └── r6_combined.yaml                R6 + stress detection
└── scripts/
    ├── run_queue_revised.sh             7-run sequential queue (28 GPU hr)
    └── post_hoc_analyze_all.sh          Batch Stage 2-5 + oracle + Q4 analysis
```

Also assumes the earlier `culturedx_full_queue.tar.gz` is applied first for:
- `configs/overlays/r6_somatization_cues.yaml` (superseded by `r6_combined.yaml`)
- `configs/overlays/r7_triage_top8.yaml`
- `configs/overlays/r13_qwen3_8b.yaml`
- `configs/overlays/r14_non_qwen.yaml`
- `configs/overlays/r20_nos_variant.yaml`
- `configs/overlays/r21_evidence_stacked.yaml`
- `configs/vllm_qwen3_8b.yaml`
- `prompts/agents/diagnostician_v2_somatization_zh.jinja`

## TLDR execution sequence

```bash
# 1. Setup
cd ~/CultureDx
git checkout main-v2.4-refactor
git pull
tar xzf ~/Downloads/culturedx_full_queue.tar.gz   # from earlier session
tar xzf ~/Downloads/culturedx_master_cleanup.tar.gz
cp -r culturedx_full_queue/prompts/agents/* prompts/agents/
cp -r culturedx_full_queue/configs/overlays/* configs/overlays/
cp culturedx_full_queue/configs/vllm_qwen3_8b.yaml configs/

# Add master_cleanup configs
cp master_cleanup/configs/overlays/r6_combined.yaml configs/overlays/
cp master_cleanup/configs/overlays/r16_bypass_logic_engine.yaml configs/overlays/

# 2. Run Phase 0 cleanup
./master_cleanup/cleanup.sh

# 3. Apply patches
patch -p1 < master_cleanup/fix_cli_seed.patch
patch -p1 < master_cleanup/fix_test_triage.patch
# Optional — only if you want to run R16:
# patch -p1 < master_cleanup/r16_bypass_logic_engine.patch

# 4. Verify
uv run pytest tests/ -q

# 5. Commit
git add -A
git commit -m "chore: pre-queue cleanup + CLI --seed fix + R16 patch"
git checkout main-v2.4-refactor
git merge chore/pre-queue-cleanup --ff-only

# 6. Run the revised queue (28 hr GPU, sequential)
chmod +x master_cleanup/scripts/*.sh
./master_cleanup/scripts/run_queue_revised.sh

# 7. Post-hoc analysis (no GPU)
./master_cleanup/scripts/post_hoc_analyze_all.sh

# 8. Bundle results for next analysis session
tar czf ~/queue_results.tar.gz \
    results/validation/r*/metrics.json \
    results/validation/r*/run_info.json \
    results/validation/r*/summary.md \
    results/validation/*_final/metrics_combined.json
```

## Queue contents (7 runs, 28 GPU hr)

| # | Run | GPU | Hypothesis |
|---|---|---|---|
| 1 | R6_combined (somatization + stress detection) | 4 hr | +5-10pp F45/F98 recall |
| 2 | R7_triage_top8 | 4 hr | +1-2pp Top-3 coverage |
| 3 | R20_nos_variant | 4 hr | +F39 recall, possibly minor Top-1 loss |
| 4 | R21_evidence_stacked | 4 hr | Unknown (evidence was neutral in old arch) |
| 5 | R16_bypass_logic | 4 hr | Minimal Top-1 change, quantifies logic engine value |
| 6 | R13_Qwen3_8B | 4 hr | Tests if F32 bias is 32B-AWQ specific |
| 7 | R14_non_qwen | 4 hr | Tests if F32 bias is Qwen family specific |

**Dropped from original 9-run queue**:
- R17 (no checker): low yield + needs code change
- R19 (no triage): current baseline already has no triage
- R11/R12 (seed variance): impossible at temperature=0.0

## Key findings from the review

1. **PR branch is legacy, DO NOT merge** — main was a deliberate clean re-import
2. **Silent fallback fixes already on main** — the PR branch was superseded
3. **Seed CLI bug confirmed** — `--seed` option missing from cli.py
4. **R19 redundant** — baseline already uses scope_policy=manual (no triage)
5. **R16 solvable with small patch** — logic engine bypass needs 15-line change
6. **Test health: 387/388 passing** — one stale test expectation

## What's NOT in this package

### Tier 3 (archive old results) — interactive script provided
Run `master_cleanup/scripts/archive_legacy_results.sh` after cleanup.sh.
It asks category-by-category whether to move ~20 legacy dirs (~250 MB)
to `results/legacy/validation/`. You can accept some categories and
skip others.

Safe to skip entirely if you want to keep everything for now —
queue will run fine either way.

### Tier 1 experiments (Phase 4) — defer until queue results arrive
- Temperature ensemble (20 hr GPU) — untested new axis
- CoT diagnostician (4 hr GPU) — prompt redesign
- R4 with N=3 ensemble (4 hr GPU) — improves R4 negative
- Fine-tuned checker integration (4 hr GPU) — needs LoRA weights

These should be decided based on Phase 2 queue results.

## Safety notes

1. `cleanup.sh` creates a new branch `chore/pre-queue-cleanup` before making
   changes. If anything breaks, `git checkout main-v2.4-refactor` restores.

2. CLI patch is backward compatible — existing scripts without `--seed`
   still work.

3. R16 patch adds one attribute (`_bypass_logic_engine`) that defaults to
   False. No existing behavior changes.

4. Smoke tests (20 cases each) run before every full 1000-case experiment.
   If config override doesn't apply, smoke output will reveal it before
   wasting 4 hours.

## When queue completes

Share back a summary of:
- Which runs succeeded (0-7 out of 7)
- Any unexpected failures or config override issues
- Bundle `~/queue_results.tar.gz`

Then in the next session we'll analyze patterns across all runs and decide
Tier 1 experiments based on what the data shows.
