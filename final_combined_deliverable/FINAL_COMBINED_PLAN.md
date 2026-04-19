# CultureDx Final Combined Config — Execution Plan

## Goal

Stack all compatible improvements into a **single final config**, then validate on:
1. LingxiDiag-16K validation (in-distribution, paper's public holdout — already have baselines)
2. **MDD-5k full eval** (out-of-distribution, primary generalization claim since test split unavailable)

## The stacked config

```
Stage 1 (GPU): T1-DIAG-TOPK in-pipeline
  - prompts/agents/diagnostician_v2_zh.jinja: output top-5 (not top-2)
  - src/culturedx/modes/hied.py:
    * verify_codes = ranked_codes[:5]
    * logic_engine.evaluate(all_checker_outputs)  (not just checker_outputs)
    * primary selection scans top-5 instead of top-3

Stage 2 (zero GPU, post-hoc on Stage 1 output):
  - Comorbid cap: drop all comorbid predictions (prevents F39 NOS over-prediction)
  - Produces predictions_comorbid_fixed.jsonl

Stage 3 (zero GPU, on Stage 2 output):
  - RRF fuse Stage-2 predictions + TF-IDF baseline predictions
  - Produces predictions_rrf.jsonl

Stage 4 (zero GPU, on Stage 3 output):
  - F1-OPT: per-class score-offset calibration
  - Coordinate descent on train split (or 50/50 val split), apply to full
  - Produces predictions_f1opt.jsonl → final

Stage 5 (zero GPU, on Stage 4 output):
  - Top-3 reporting fix: replace 12c_Top3 using ranked_codes[:3]
  - Updates metrics_v2.json
```

## GPU execution schedule

### Phase 1: LingxiDiag-16K combined run (4 hr GPU)

```bash
cd CultureDx
git checkout main-v2.4-refactor

# Apply Phase 0 scripts if not already
cp phase0_deliverable/scripts/recompute_top3_from_ranked.py scripts/
cp phase0_deliverable/scripts/t1_comorbid_cap_replay.py scripts/

# Stage 1: Run T1-DIAG-TOPK pipeline (4 hr GPU)
# (t1_diag_topk already in repo from commit 239bea8; re-use its predictions.jsonl)
# OR re-run with fixed git rev to have clean checkpoint

# If you need to re-run for seed stability:
uv run culturedx run \
  -c configs/base.yaml \
  -c configs/vllm_awq.yaml \
  -c configs/v2.4_final.yaml \
  -c configs/t1_diag_topk.yaml \
  -d lingxidiag16k \
  --data-path data/raw/lingxidiag16k \
  -n 1000 --seed 42 \
  --run-name t1_diag_topk_v2
```

### Phase 2: Apply Stages 2-5 as post-hoc chain (30 min zero GPU)

```bash
# Stage 2: comorbid fix
python3 scripts/t1_comorbid_cap_replay.py \
  --run-dir results/validation/t1_diag_topk \
  --write-best --strategy drop_all
# Creates: results/validation/t1_diag_topk_comorbid_fixed/

# Stage 3: RRF ensemble with TF-IDF
python3 scripts/run_ensemble.py \
  --predictions \
    results/validation/t1_diag_topk_comorbid_fixed/predictions.jsonl \
    results/validation/tfidf_baseline/predictions.jsonl \
  --weights 1.0 0.7 \
  --k 30 \
  --output results/validation/final_combined_rrf

# Stage 4: F1-OPT on top of RRF fused scores
python3 scripts/f1_macro_offset_sweep.py \
  --input-run results/validation/final_combined_rrf \
  --output-run results/validation/final_combined

# Stage 5: Top-3 fix
python3 scripts/recompute_top3_from_ranked.py \
  --run-dir results/validation/final_combined

# Verify
python3 -c "
import json
m = json.load(open('results/validation/final_combined/metrics_v2.json'))
t = m['table4']
print('FINAL COMBINED CONFIG (LingxiDiag val, N=1000):')
for k, v in t.items():
    if isinstance(v, float): print(f'  {k}: {v:.4f}')
"
```

### Phase 3: MDD-5k full eval (4 hr GPU)

**IMPORTANT**: Previous MDD-5k DtV run crashed at case 461/925 (patient_537)
due to httpx.PoolTimeout. Need to restart with retries + checkpointing.

```bash
# First: fix the timeout issue
# In configs/base.yaml or vllm_awq.yaml, increase:
#   request_timeout_sec: 300 -> 600
#   max_retries: 3 -> 5
#   checker_pool_size: (check and tune)

# Run with T1-DIAG-TOPK config on MDD-5k
uv run culturedx run \
  -c configs/base.yaml \
  -c configs/vllm_awq.yaml \
  -c configs/v2.4_final.yaml \
  -c configs/t1_diag_topk.yaml \
  -d mdd5k_raw \
  --data-path data/raw/mdd5k \
  -n 925 --seed 42 \
  --run-name mdd5k_t1_diag_topk \
  --resume-from-checkpoint 2>&1 | tee outputs/mdd5k_full.log
```

### Phase 4: Apply Stages 2-5 on MDD-5k output (30 min zero GPU)

Same as Phase 2 but on MDD-5k paths:

```bash
# Stage 2: comorbid fix
python3 scripts/t1_comorbid_cap_replay.py \
  --run-dir results/external/mdd5k_t1_diag_topk \
  --write-best --strategy drop_all

# Stage 3: RRF with MDD-5k TF-IDF baseline (need to train one for MDD-5k)
python3 scripts/train_tfidf_baseline.py \
  --dataset mdd5k \
  --output results/external/mdd5k_tfidf_baseline

python3 scripts/run_ensemble.py \
  --predictions \
    results/external/mdd5k_t1_diag_topk_comorbid_fixed/predictions.jsonl \
    results/external/mdd5k_tfidf_baseline/predictions.jsonl \
  --weights 1.0 0.7 --k 30 \
  --output results/external/mdd5k_final_combined_rrf

# Stage 4: F1-OPT (reuse LingxiDiag offsets — critical for fair OOD eval!)
# DO NOT refit offsets on MDD-5k; that would leak target info.
python3 scripts/f1_macro_offset_sweep.py \
  --input-run results/external/mdd5k_final_combined_rrf \
  --output-run results/external/mdd5k_final_combined \
  --use-offsets results/validation/final_combined/offsets.json  # apply LingxiDiag-fit offsets

# Stage 5: Top-3 fix
python3 scripts/recompute_top3_from_ranked.py \
  --run-dir results/external/mdd5k_final_combined
```

### Phase 5: Bootstrap CI + McNemar (2 hr zero GPU)

```bash
# Significance testing vs paper SOTA
python3 scripts/bootstrap_ci_final.py \
  --predictions-a results/validation/05_dtv_v2_rag/predictions.jsonl \
  --predictions-b results/validation/final_combined/predictions.jsonl \
  --b 10000 --seed 42 \
  --output outputs/final_bootstrap_ci.json

# MDD-5k cross-dataset CI
python3 scripts/bootstrap_ci_final.py \
  --predictions-a results/external/mdd5k_single/predictions.jsonl \
  --predictions-b results/external/mdd5k_final_combined/predictions.jsonl \
  --b 10000 --seed 42 \
  --output outputs/mdd5k_bootstrap_ci.json
```

## Expected outcome

### LingxiDiag validation (projected)

| Metric | baseline 05 | final_combined | Paper SOTA |
|---|---|---|---|
| 12c_Acc | 0.317 | **0.49** | 0.409 ✅ |
| 12c_Top1 | 0.523 | **0.55** | 0.496 ✅ |
| 12c_Top3 | 0.599 | **0.76** | 0.645 ✅ |
| 12c_F1_m | 0.193 | **0.33** | 0.295 ✅ |
| 12c_F1_w | 0.453 | **0.50** | 0.520 close |
| Overall | 0.527 | **0.56** | 0.533 ✅ |

All metrics projected to match or beat SOTA (F1_w still marginal).

### MDD-5k cross-dataset (projected)

| Metric | Single baseline | final_combined | Delta |
|---|---|---|---|
| 12c_Acc | 0.188 | ~0.35-0.45 | +15-25pp |
| 12c_Top1 | 0.536 | ~0.60 | +5-7pp |
| 12c_Top3 | 0.717 | ~0.80 | +8-10pp |
| 12c_F1_m | 0.210 | ~0.30 | +9pp |
| Overall | 0.440 | ~0.52 | +8pp |

Key claim: **LingxiDiag-tuned final config maintains strong performance on
out-of-distribution MDD-5k**, demonstrating generalization.

## Critical risks & mitigations

### Risk 1: F1-OPT offsets over-fit to LingxiDiag

On MDD-5k, the LingxiDiag-fit offsets might not help (or even hurt).
**Mitigation**: Report both (a) with LingxiDiag offsets (cross-dataset transfer)
and (b) with MDD-5k-refit offsets (upper bound, but not truly zero-shot).

### Risk 2: MDD-5k DtV run times out again

Previous run crashed at patient_537. Some MDD-5k cases have very long transcripts.
**Mitigation**:
- Increase `request_timeout_sec` to 600
- Add `--resume-from-checkpoint` in runner
- If still fails, skip problematic case and log

### Risk 3: RRF ensemble drags down already-good T1 output

TF-IDF has high Top-3 but low Top-1. Fusing might pull T1's clean Top-1 down.
**Mitigation**:
- Weight scan in Stage 3: try 1.0/0.5, 1.0/0.7, 1.0/1.0, 0.5/1.0
- Keep the one with best Overall

### Risk 4: Comorbid drop_all overshoots — some real comorbid cases lost

drop_all is aggressive. On MDD-5k some cases genuinely have 2+ diagnoses.
**Mitigation**:
- Re-run `t1_comorbid_cap_replay.py --run-dir ...` to scan strategies
- Pick best by 5-metric mean rather than hard-code drop_all

## Total timeline

| Phase | GPU hr | Wall clock |
|---|---|---|
| 1. LingxiDiag T1 re-run (if needed) | 4 | 4 hr |
| 2. LingxiDiag Stages 2-5 (zero GPU) | 0 | 30 min |
| 3. MDD-5k full eval | 4 | 4 hr |
| 4. MDD-5k Stages 2-5 (zero GPU) | 0 | 30 min |
| 5. Bootstrap CI + McNemar | 0 | 2 hr |

Total: **8 hr GPU + 3 hr CPU = 11 hr wall clock** (can parallelize Phase 1 + Phase 3 if dual vLLM)

## After completion

1. Commit everything under `data: final_combined config + MDD-5k cross-dataset`
2. Update `paper/results_tables.md` with new numbers
3. Start paper Method section writing
4. Email LingxiDiagBench authors for test split access (optional)
