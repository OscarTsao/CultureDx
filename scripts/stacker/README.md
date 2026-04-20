# MAS-Conditioned Stacker

The headline contribution of the v2.5 rebase. Replaces RRF (which ignored
confidence and degraded Top-1) with a learned meta-learner that combines
TF-IDF's calibrated probabilities with DtV's structured reasoning output.

## The setup

Three base systems, all clean train → eval:

| System | Trained on | Evaluated on (for stacker) |
|--------|-----------|---------------------------|
| TF-IDF + LR | `rag_pool` | `dev_hpo` (training) + `test_final` (inference) |
| DtV MAS (Qwen3-32B-AWQ) | — (in-context) | `dev_hpo` (training) + `test_final` (inference) |
| Stacker (LR / LightGBM) | `dev_hpo` features | `test_final` features |

## Features (31 dims, fixed order)

```
tfidf_p__F20, tfidf_p__F31, ..., tfidf_p__Others       (12)  TF-IDF class probs
dtv_rank1_conf, ..., dtv_rank5_conf                    ( 5)  DtV top-5 confidences
dtv_checker_mr__F20, ..., dtv_checker_mr__Others       (12)  DtV criterion met-ratios
tfidf_top1_margin                                      ( 1)  TF-IDF decisiveness
dtv_abstain_flag                                       ( 1)  DtV abstention indicator
```

Feature order is committed in `scripts/stacker/build_features.py::feature_names()`.
Any change requires retraining.

## Protocol

```bash
# 1. TF-IDF on both splits
uv run python scripts/train_tfidf_baseline.py --eval-split dev_hpo
uv run python scripts/train_tfidf_baseline.py --eval-split test_final

# 2. DtV on both splits (requires GPU + vLLM)
uv run culturedx run -c configs/base.yaml -c configs/vllm_awq.yaml \
    -c configs/v2.4_final.yaml -d lingxidiag16k \
    --split dev_hpo --run-name dtv_dev_hpo -n 1000 --seed 42
uv run culturedx run -c configs/base.yaml -c configs/vllm_awq.yaml \
    -c configs/v2.4_final.yaml -d lingxidiag16k \
    --split test_final --run-name dtv_test_final -n 1000 --seed 42

# 3. Build features for both splits
uv run python scripts/stacker/build_features.py \
    --tfidf-pred outputs/tfidf_baseline/dev_hpo/predictions.jsonl \
    --dtv-pred   results/rebase_v2.5/dtv_dev_hpo/predictions.jsonl \
    --eval-split dev_hpo \
    --out        outputs/stacker_features/dev_hpo/features.jsonl

uv run python scripts/stacker/build_features.py \
    --tfidf-pred outputs/tfidf_baseline/test_final/predictions.jsonl \
    --dtv-pred   results/rebase_v2.5/dtv_test_final/predictions.jsonl \
    --eval-split test_final \
    --out        outputs/stacker_features/test_final/features.jsonl

# 4. Train (dev_hpo only — trainer refuses test_final features)
uv run python scripts/stacker/train_stacker.py \
    --features outputs/stacker_features/dev_hpo/features.jsonl \
    --out-dir  outputs/stacker/

# 5. Evaluate on test_final (touches test ONCE per stacker variant)
uv run python scripts/stacker/eval_stacker.py \
    --features   outputs/stacker_features/test_final/features.jsonl \
    --model      outputs/stacker/stacker_lr.pkl \
    --tfidf-pred outputs/tfidf_baseline/test_final/predictions.jsonl \
    --dtv-pred   results/rebase_v2.5/dtv_test_final/predictions.jsonl \
    --out-dir    results/rebase_v2.5/stacker_lr/

# If lightgbm was available during training:
uv run python scripts/stacker/eval_stacker.py \
    --features   outputs/stacker_features/test_final/features.jsonl \
    --model      outputs/stacker/stacker_lgbm.pkl \
    --tfidf-pred outputs/tfidf_baseline/test_final/predictions.jsonl \
    --dtv-pred   results/rebase_v2.5/dtv_test_final/predictions.jsonl \
    --out-dir    results/rebase_v2.5/stacker_lgbm/
```

## Safety guards

Built into the pipeline:

1. `train_stacker.py` **refuses** to load features labeled
   `eval_split="test_final"`. Training is dev_hpo-only.
2. `eval_stacker.py` **refuses** to load features labeled anything other
   than `test_final`.
3. `build_features.py` **refuses** to join TF-IDF and DtV predictions
   from different case-id sets (unless `--allow-missing-dtv` is set,
   which fills missing DtV with synthetic abstain features).

## Expected results

Pre-rebase analysis on val 1000 (main-v2.4-refactor):

```
TF-IDF alone:        Top-1 = 0.610
DtV alone:           Top-1 = 0.505
RRF (k=30, w=[1,0.7]):                 Top-1 = 0.557   [worse than TF-IDF]
Oracle (better-of-two per case):       Top-1 = 0.701

Agreement analysis:
  Both correct:    400 (40.0%)
  TF-IDF only:     210 (21.0%)
  DtV only:         91 ( 9.1%)
  Both wrong:      299 (29.9%)
```

Post-rebase, clean held-out expectation:

```
Stacker LR:    Top-1 ≈ 0.62–0.65  (target)
Stacker LGBM:  Top-1 ≈ 0.63–0.66  (target; usually +1–3pp over LR)
Top-3:         ≈ 0.85+
```

If the stacker does not significantly beat TF-IDF alone (McNemar p ≥ 0.05),
the finding is published as-is: "learned stacking on MAS features does not
improve over the strongest base". That's a valid negative result and worth
the rebase regardless.

## McNemar and bootstrap

`eval_stacker.py` reports 1000-resample bootstrap 95% CIs and two McNemar
tests:

- H0_1: stacker Top-1 == TF-IDF Top-1
- H0_2: stacker Top-1 == DtV Top-1

Both with two-sided exact binomial p.

Result of each goes in the paper's main table with a significance asterisk.
