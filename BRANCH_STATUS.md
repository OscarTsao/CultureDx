# Branch Status — `clean/v2.5-eval-discipline`

**Date**: 2026-04-20
**State**: Rebase in progress. No paper-usable result numbers on this branch yet.

## What this branch is

The consolidation of `main-v2.4-refactor` (where paper conclusions were
drawn) and `pr-stack/docs-and-production-hardening` (where the
infrastructure was actually fixed). Neither branch in isolation is safe
to cite; this branch is where the two are merged under a stricter
evaluation protocol.

## Read first

1. **`REBASE_PLAN.md`** — 16-week plan.
2. **`docs/audit_main_v2.4/RUNS_AUDIT.md`** — silent failures on main.
3. **`docs/audit_main_v2.4/R21V2_ACTUAL_ROOT_CAUSE.md`** — retracts the
   "evidence pipeline causes F41 collapse" finding.
4. **`outputs/_archive_pre_rebase/README.md`** — why every old result
   directory is quarantined.
5. **`HANDOFF_CLAUDE_CODE.md`** — task list for implementation agents
   (Claude Code, Codex, etc.).

## Highest-ROI task

**Replace RRF with a learned stacker.** TF-IDF + LR trained on train
split is already Top-1 0.610 on val — higher than any MAS variant and
higher than GPT-5-Mini / Grok-4.1 / Claude-Haiku-4.5. Oracle over
TF-IDF + DtV is 0.701. RRF captures only 0.557 of that headroom
because it ignores confidence. A learned stacker should reach 0.62–0.65.

See `scripts/stacker/` and `REBASE_PLAN.md §5`.

## What is NOT on this branch (intentionally)

- `results/validation/*` from main-v2.4-refactor
  (R6, R7, R11-R21, t1_diag_topk, final_combined, etc.)
- `outputs/sweeps/*` live results (archived under `outputs/_archive_pre_rebase/sweeps/`)
- Any HPO value fit against `split="validation"` (flagged for re-fit)

## What IS on this branch and trusted

- All source code from pr-stack @ `cda48d5` (silent-fallback removal,
  BGE-M3 hybrid, negation, temporal upgrade, somatization-150, SFT
  checker training pipeline)
- Tests (388, must pass)
- `prompts/agents/criterion_checker_temporal_zh.jinja` (the file whose
  absence broke R21v2 on main)
- TF-IDF baseline and paper-eval module (ported from main)
- New split discipline (dev_hpo / rag_pool / test_final)
- Learned stacker infrastructure

## Active checklist

- [x] Branch created off pr-stack @ cda48d5
- [x] `docs/audit_main_v2.4/*` imported from main
- [x] `outputs/sweeps/*` and `outputs/eval/*` archived
- [x] `REBASE_PLAN.md` and `BRANCH_STATUS.md` written
- [x] `src/culturedx/eval/lingxidiag_paper.py` ported from main
- [x] `scripts/train_tfidf_baseline.py` ported from main
- [x] `scripts/generate_splits.py` written
- [x] `configs/splits/lingxidiag16k_v2_5.yaml` committed (deterministic,
      seed-derived; data dir not required for the file to exist, but
      regeneration requires `data/raw/lingxidiag16k/`)
- [x] Adapter extended for `dev_hpo` / `rag_pool`
- [x] `scripts/stacker/build_features.py` written
- [x] `scripts/stacker/train_stacker.py` written
- [x] `scripts/stacker/eval_stacker.py` written
- [x] `scripts/audit_run.py` written
- [x] Tests for adapter split loading + audit script
- [ ] **For implementation agents**: see `HANDOFF_CLAUDE_CODE.md`

Nothing under `results/rebase_v2.5/` exists yet. It will be created by
the first clean run on a machine with GPU + dataset + vLLM.
