# Pre-Rebase Archive — DO NOT USE FOR PAPER CLAIMS

**Date archived**: 2026-04-20
**Archive reason**: Contamination and protocol drift; superseded by
`clean/v2.5-eval-discipline` branch.

This directory contains every eval artifact that existed on
`pr-stack/docs-and-production-hardening` at commit `cda48d5`. It also
supersedes (by exclusion) the `results/validation/*` tree on
`main-v2.4-refactor` — those directories are intentionally not imported
into this branch. See `docs/audit_main_v2.4/` for the audit of main's
runs.

## Why these artifacts are quarantined

### 1. Four silent template-failure runs on `main-v2.4-refactor`
Documented in `docs/audit_main_v2.4/RUNS_AUDIT.md`. R6 (somatization +
stress), R20 (NOS variant), R21v2 (evidence), and the original R17
(bypass checker) never actually executed the DtV criterion checker —
they fell through to diagnostician-only due to missing Jinja templates.
The self-retraction is in
`docs/audit_main_v2.4/R21V2_ACTUAL_ROOT_CAUSE.md`.

### 2. Val-on-val calibration in main's `final_combined`
`scripts/f1_macro_offset_sweep.py` (on main) partitions validation
N=1000 into 500-calib / 500-held-out, fits per-class offsets on the
calib half, then reports numbers on the full N=1000. Top-1 0.552 /
Top-3 0.841 from main's `results/validation/final_combined` are
therefore not clean held-out numbers.

### 3. RRF hyperparameters on main were grid-searched on val
`scripts/run_ensemble.py` sweeps `k ∈ {30, 60, 100}` ×
`weights ∈ {...}` on validation and picks the combo with best Overall.
Small but real val-on-val.

### 4. No true test split
All experiments on both branches evaluated on `split="validation"` with
no separately held test set. Hyperparameters selected under this regime
(`abs_threshold=0.50`, `comorbid_min_ratio`, target-disorder list,
retrieval `top_k=5`) are val-selected and must be re-fit under the new
eval discipline before any number enters the paper.

### 5. Branch drift between reasoning and code
`main-v2.4-refactor` contains the R6/R20/R21v2 conclusions but lacks
the silent-fallback removal (pr-stack `b9ec26b`), temporal template,
and infrastructure upgrades. The two branches were never jointly
evaluated.

### 6. N=200 sweeps are under-powered for final claims
Most sweeps preserved under `sweeps/*` are N=200 dev runs. Bootstrap
CIs on N=200 are ±5pp at 95%, too loose to discriminate claimed
effects.

## What to do with these files

- Read them as history, not as evidence.
- Do not cite any number from these directories in the thesis or
  conference submission.
- The `sweep_report.json` files are useful for sanity-checking that
  the pipeline ran end-to-end in development, and for comparing run
  times.
- Individual `predictions.jsonl` files may be useful for post-hoc
  inspection but any aggregate metric must be recomputed clean.

## When these can be deleted

After the first clean N=1000 eval is committed under
`results/rebase_v2.5/` and the paper's canonical number table is
cross-referenced against the new results, this directory can be
removed via `git rm -rf`. Until then, keep for audit purposes.
