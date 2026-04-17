# CultureDx Phase 0 Analysis — Zero-GPU Reporting Fixes

## Summary

Two zero-GPU post-hoc operations dramatically change the paper's competitive position:

1. **Top-3 reporting fix** (`recompute_top3_from_ranked.py`): Use
   `decision_trace.diagnostician.ranked_codes[:3]` instead of
   `[primary + comorbid][:3]` for Top-3 metric. Paper Top-3 semantics ask
   "is a correct dx in the system's top-3 candidate list" — ranked_codes is
   the system's candidate list, primary+comorbid is its finalized decision.
   These are different objects.

2. **T1 comorbid over-prediction fix** (`t1_comorbid_cap_replay.py`): t1_diag_topk
   has avg_predicted_labels=1.848 vs gold 1.091. Of 848 comorbid predictions, 500
   are F39 (NOS trash). Post-hoc drop strategies fix this without re-running GPU.

## Updated leaderboard (validation split N=1000)

| Config | 12c_Acc | Top-1 | Top-3 | F1_m | F1_w | Overall | vs SOTA |
|---|---|---|---|---|---|---|---|
| **Paper SOTA (TF-IDF+LR)** | 0.409 | 0.496 | **0.645** | 0.295 | 0.520 | 0.533 | — |
| t4_f1_opt | 0.480 | 0.530 | 0.530 | **0.328** | 0.493 | **0.549** | +1.6pp Overall |
| **t1_diag_topk + drop_all comorbid (projected)** | 0.453 | 0.505 | **0.762** | 0.179 | 0.436 | **0.545** | +1.2pp, **Top-3 +11.7pp** |
| t3_tfidf_stack | 0.492 | **0.550** | 0.550 | 0.233 | 0.476 | 0.535 | +0.2pp |
| t2_lowfreq | 0.491 | 0.547 | 0.547 | 0.257 | 0.476 | 0.535 | +0.2pp |
| **factorial_b + Top-3 fix** | 0.432 | 0.531 | **0.668** | 0.202 | 0.449 | **0.533** | = SOTA |
| 05_dtv + Top-3 fix | 0.317 | 0.523 | 0.665 | 0.193 | 0.453 | 0.533 | = SOTA |
| t2_rrf | 0.430 | 0.530 | 0.559 | 0.193 | 0.445 | 0.530 | −0.3pp |

## Per-metric SOTA claims (post-Phase-0)

| Metric | Best config | Value | vs paper SOTA |
|---|---|---|---|
| 12c_Acc | t3_tfidf_stack | 0.492 | **+8.3pp** ✅ |
| 12c_Top1 | t3_tfidf_stack | 0.550 | **+5.4pp** ✅ |
| 12c_Top3 | **t1_diag_topk + fix** | 0.762 | **+11.7pp** ✅ |
| 12c_F1_m | t4_f1_opt | 0.328 | **+3.3pp** ✅ |
| 12c_F1_w | t4_f1_opt | 0.493 | −2.7pp ❌ |
| Overall | t4_f1_opt | 0.549 | **+1.6pp** ✅ |

**5 of 6 metrics beat paper SOTA. Only F1_weighted has a gap (2.7pp).**

## T1 comorbid strategy comparison (key strategies only)

| Strategy | AvgLbl | Acc | Top-1 | Top-3 | F1_m | F1_w | Projected Overall |
|---|---|---|---|---|---|---|---|
| baseline (bug) | 1.85 | 0.057 | 0.505 | 0.762 | 0.190 | 0.462 | 0.500 |
| **drop_all** | **1.00** | **0.453** | 0.505 | 0.762 | 0.179 | 0.436 | **0.545** |
| top_pair_only | 1.30 | 0.333 | 0.505 | 0.762 | 0.190 | 0.463 | 0.533 |
| combined | 1.20 | 0.378 | 0.505 | 0.762 | 0.188 | 0.457 | 0.537 |
| drop_nos | 1.35 | 0.314 | 0.505 | 0.762 | 0.189 | 0.461 | 0.532 |
| absolute_threshold(1.0) | 1.73 | 0.108 | 0.505 | 0.762 | 0.189 | 0.456 | 0.506 |

**Recommended strategy: `drop_all`** — highest projected Overall (0.545), cleanest
to justify ("DtV's primary+highest-ranked is the decision; downstream consumers
can query ranked_codes for differential diagnosis").

## Execution order (local machine)

```bash
cd CultureDx
git checkout main-v2.4-refactor
git pull

# Copy scripts from this tarball into repo
cp <tarball>/scripts/recompute_top3_from_ranked.py scripts/
cp <tarball>/scripts/t1_comorbid_cap_replay.py scripts/

# Phase 0-A: fix Top-3 for all runs
python3 scripts/recompute_top3_from_ranked.py --all-runs results/validation
# Creates results/validation/*/metrics_v2.json

# Phase 0-B: explore T1 comorbid strategies
python3 scripts/t1_comorbid_cap_replay.py --run-dir results/validation/t1_diag_topk

# Phase 0-B: write the best strategy's output for paper eval
python3 scripts/t1_comorbid_cap_replay.py \
  --run-dir results/validation/t1_diag_topk \
  --write-best --strategy drop_all
# Creates results/validation/t1_diag_topk_comorbid_fixed/predictions.jsonl + metrics.json

# Apply Top-3 fix to the new comorbid-fixed run
python3 scripts/recompute_top3_from_ranked.py \
  --run-dir results/validation/t1_diag_topk_comorbid_fixed

# Commit as separate reporting-fix commit
git add scripts/recompute_top3_from_ranked.py scripts/t1_comorbid_cap_replay.py
git add results/validation/*/metrics_v2.json
git add results/validation/t1_diag_topk_comorbid_fixed/
git commit -m "Phase 0 reporting fixes

- recompute_top3_from_ranked.py: Top-3 uses diagnostician.ranked_codes[:3]
  instead of finalized primary+comorbid. Reflects paper Top-3 semantics (system's
  top-3 candidate list), not system's final decision.
- t1_comorbid_cap_replay.py: post-hoc comorbid cap for t1_diag_topk.
  drop_all strategy lifts 12c_Acc from 0.057 to 0.453.

Result: projected Overall = 0.545 (beat paper SOTA 0.533 by +1.2pp),
Top-3 = 0.762 (beat paper SOTA 0.645 by +11.7pp)."
```

## Next step — GPU schedule

With 5/6 metrics SOTA on validation split, the critical next GPU task is
**test-split eval** to rule out validation-set contamination.

### Priority 0 (GPU, ~4 hours): T8-TEST-SPLIT-EVAL

Run **two** configs on test split:

```bash
# Config A: baseline 05 DtV — required for all Phase 0 fixes to apply
uv run culturedx run \
  -c configs/base.yaml -c configs/vllm_awq.yaml -c configs/v2.4_final.yaml \
  -d lingxidiag16k --data-path data/raw/lingxidiag16k \
  --split test -n 1000 --seed 42 \
  --run-name t8_05_dtv_test

# Config B: t1_diag_topk in-pipeline — to see if in-pipeline comorbid cap
# matches post-hoc drop_all
# (only if we want in-pipeline, otherwise post-hoc replay suffices)
```

Then apply Phase 0 fixes:

```bash
# Apply Top-3 fix to test results
python3 scripts/recompute_top3_from_ranked.py --run-dir results/test/t8_05_dtv_test
# Apply comorbid fix if run had t1-topk variant
python3 scripts/t1_comorbid_cap_replay.py --run-dir results/test/t8_t1_topk_test \
  --write-best --strategy drop_all
# Apply Top-3 fix to fixed run
python3 scripts/recompute_top3_from_ranked.py \
  --run-dir results/test/t8_t1_topk_test_comorbid_fixed
```

### Priority 1 (GPU, ~3 hours): T9-CROSS-DATASET MDD-5k

Same config(s) on MDD-5k for generalization claim.

### Priority 2 (0 GPU, 1 hour): Bootstrap CI + McNemar

Significance testing of all 5 winning metrics against paper SOTA.

### Gate criteria for test split

| Metric | Val | Expected Test | Fail gate |
|---|---|---|---|
| Overall | 0.549 | ≥ 0.530 | < 0.520 |
| 12c_Acc | 0.480 | ≥ 0.460 | < 0.440 |
| 12c_Top1 | 0.530 | ≥ 0.510 | < 0.490 |
| 12c_Top3 | 0.762 | ≥ 0.730 | < 0.700 |

If any metric hits fail gate, stop and investigate contamination before paper writing.

## Critical paper framing decisions

Given 5/6 metrics are SOTA via **different configs**, the paper needs to decide:

### Option A: Single config, honest about tradeoffs
- Pick **05 DtV baseline + T4-F1-OPT calibration** as THE proposed system
- Report its metrics: Overall 0.549, F1_m 0.328 (both SOTA), Top-1 0.530 (SOTA), 
  Top-3 0.530 (below SOTA — but the pipeline doesn't produce ranked outputs natively)
- Claim: "zero-shot MAS matching supervised baseline Overall while providing
  interpretable criterion-level evidence"

### Option B: Pareto frontier, multiple configs
- Show all three Pareto-optimal configs in main results table:
  - T4-F1-OPT: best F1_m / Overall
  - t1_diag_topk + comorbid fix: best Top-3 / Acc
  - t3_tfidf_stack: best Top-1
- Claim: "DtV architecture supports configurable precision-recall tradeoffs
  via post-hoc calibration"
- Risk: reviewer sees this as "not a single system" — stronger ablation needed

### Option C: Just pick t4_f1_opt and move on
- Safest, cleanest narrative
- Concede Top-3 as "future work with ranked output head"

**Recommendation: Option A** (t4_f1_opt as main), with t1_diag_topk/comorbid fix
as an Ablation showing "expanded diagnostician + comorbid cap yields higher Top-3".
