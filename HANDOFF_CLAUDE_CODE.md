# Handoff — Implementation Tasks for Claude Code / Codex

**Branch**: `clean/v2.5-eval-discipline`
**Base**: `pr-stack/docs-and-production-hardening` @ `cda48d5`
**Context docs**: `REBASE_PLAN.md`, `BRANCH_STATUS.md`,
`docs/audit_main_v2.4/*`, `scripts/stacker/README.md`

This file enumerates the concrete tasks an implementation agent needs to
complete to get from "rebase infrastructure landed" to "first paper number
on `test_final`".

The rebase commits already landed provide the skeleton. What follows is
the work that must happen *on a machine with GPU + vLLM + LingxiDiag-16K
parquet*.

---

## Task 0 — Environment setup (one-time, ~10 min)

### 0.1 Clone the branch
```bash
git clone https://github.com/OscarTsao/CultureDx.git
cd CultureDx
git fetch origin
git checkout clean/v2.5-eval-discipline
```

### 0.2 Install deps
```bash
uv sync                            # base install
uv pip install -e ".[retrieval]"   # BGE-M3 etc.
uv pip install lightgbm            # optional; stacker gracefully falls back without it
uv pip install scikit-learn pandas pyarrow pyyaml
```

### 0.3 Fetch LingxiDiag-16K
Place `train-*.parquet` and `validation-*.parquet` at
`data/raw/lingxidiag16k/` (or `data/raw/lingxidiag16k/data/`).

### 0.4 Verify tests pass
```bash
uv run pytest tests/ -q
# Expect: 390+ passing (pr-stack's 388 + rebase's new ones)
```

---

## Task 1 — Populate the split manifest (5 min, CPU only)

```bash
uv run python scripts/generate_splits.py --force
# Writes configs/splits/lingxidiag16k_v2_5.yaml
# Expected output:
#   rag_pool:   ~14000 cases, sha256=...
#   dev_hpo:     1000 cases, sha256=...
#   test_final:  1000 cases, sha256=...

# Commit the populated manifest:
git add configs/splits/lingxidiag16k_v2_5.yaml
git commit -m "data: populate v2.5 split manifest from generate_splits.py"
```

After this commit, every subsequent clone will have the identical split.
The placeholder is now superseded.

---

## Task 2 — TF-IDF baseline on both splits (30 min, CPU only)

```bash
# Train on rag_pool, predict on dev_hpo (stacker training features)
uv run python scripts/train_tfidf_baseline.py --eval-split dev_hpo
# Writes outputs/tfidf_baseline/dev_hpo/{predictions.jsonl,metrics.json,model/}

# Train on rag_pool (same run, but this script retrains; that's intentional
# for audit reproducibility), predict on test_final
uv run python scripts/train_tfidf_baseline.py --eval-split test_final
# Writes outputs/tfidf_baseline/test_final/

# Sanity check the numbers:
python3 -c "
import json
for split in ['dev_hpo', 'test_final']:
    m = json.load(open(f'outputs/tfidf_baseline/{split}/metrics.json'))
    t = m['table4']
    print(f'{split}: Top-1={t[\"12class_Top1\"]:.3f}  Top-3={t[\"12class_Top3\"]:.3f}  F1m={t[\"12class_F1_macro\"]:.3f}')
"
# Expected (based on main's val):
#   dev_hpo:    Top-1 ~0.55-0.62, Top-3 ~0.80-0.85, F1m ~0.30-0.36
#   test_final: Top-1  0.610,     Top-3  0.829,     F1m  0.352
```

Commit the outputs (they're small):
```bash
git add outputs/tfidf_baseline/
git commit -m "results(T0): TF-IDF baseline on dev_hpo + test_final"
```

---

## Task 3 — DtV on both splits (~8 GPU-hours on RTX 5090)

### 3.1 Start vLLM
```bash
vllm serve Qwen/Qwen3-32B-AWQ --port 8000 --max-model-len 8192 &
# Wait for ready (tail logs until you see 'Application startup complete')
```

### 3.2 Run DtV on dev_hpo (for stacker training)
```bash
uv run culturedx run \
    -c configs/base.yaml \
    -c configs/vllm_awq.yaml \
    -c configs/v2.4_final.yaml \
    -d lingxidiag16k \
    --data-path data/raw/lingxidiag16k \
    --split dev_hpo \
    --run-name dtv_dev_hpo \
    -n 1000 \
    --seed 42
# Writes results/rebase_v2.5/dtv_dev_hpo/
```

> IMPORTANT — check that `culturedx run` accepts `--split dev_hpo`. The
> CLI may pass this through to the adapter; if it doesn't, add a
> `--split` flag to `src/culturedx/pipeline/cli.py`. The adapter change
> in commit rebase(3/5) already accepts the logical split names.

### 3.3 Audit the run
```bash
uv run python scripts/audit_run.py results/rebase_v2.5/dtv_dev_hpo/
# Must exit 0. If any check fails, fix before proceeding.
# Specifically: checker_coverage >= 95% and checker_influence >= 5%.
```

### 3.4 Run DtV on test_final
```bash
uv run culturedx run \
    -c configs/base.yaml \
    -c configs/vllm_awq.yaml \
    -c configs/v2.4_final.yaml \
    -d lingxidiag16k \
    --data-path data/raw/lingxidiag16k \
    --split test_final \
    --run-name dtv_test_final \
    -n 1000 \
    --seed 42

uv run python scripts/audit_run.py results/rebase_v2.5/dtv_test_final/
# Must exit 0.
```

### 3.5 Commit
```bash
git add results/rebase_v2.5/dtv_dev_hpo/ results/rebase_v2.5/dtv_test_final/
git commit -m "results(B0,B2): clean DtV on dev_hpo and test_final

Both runs audited via scripts/audit_run.py — checker_coverage >=95%
across all target disorders, checker_influence >=5%, no
TemplateNotFound warnings in run.log."
```

---

## Task 4 — Build stacker features (5 min, CPU only)

```bash
# dev_hpo features (for training)
uv run python scripts/stacker/build_features.py \
    --tfidf-pred outputs/tfidf_baseline/dev_hpo/predictions.jsonl \
    --dtv-pred   results/rebase_v2.5/dtv_dev_hpo/predictions.jsonl \
    --eval-split dev_hpo \
    --out        outputs/stacker_features/dev_hpo/features.jsonl

# test_final features (for evaluation)
uv run python scripts/stacker/build_features.py \
    --tfidf-pred outputs/tfidf_baseline/test_final/predictions.jsonl \
    --dtv-pred   results/rebase_v2.5/dtv_test_final/predictions.jsonl \
    --eval-split test_final \
    --out        outputs/stacker_features/test_final/features.jsonl

git add outputs/stacker_features/
git commit -m "results(S1): stacker features for dev_hpo + test_final"
```

---

## Task 5 — Train the stacker (2 min, CPU only)

```bash
uv run python scripts/stacker/train_stacker.py \
    --features outputs/stacker_features/dev_hpo/features.jsonl \
    --out-dir  outputs/stacker/
# Writes outputs/stacker/{stacker_lr.pkl, stacker_lgbm.pkl*, feature_names.json, train_manifest.json}
# (* only if lightgbm installed)

git add outputs/stacker/
git commit -m "results(S2): trained LR + LightGBM stackers on dev_hpo"
```

---

## Task 6 — The headline evaluation (5 min, CPU only, touches test_final ONCE)

### 6.1 LR stacker
```bash
uv run python scripts/stacker/eval_stacker.py \
    --features   outputs/stacker_features/test_final/features.jsonl \
    --model      outputs/stacker/stacker_lr.pkl \
    --tfidf-pred outputs/tfidf_baseline/test_final/predictions.jsonl \
    --dtv-pred   results/rebase_v2.5/dtv_test_final/predictions.jsonl \
    --out-dir    results/rebase_v2.5/stacker_lr/
```

### 6.2 LightGBM stacker (if available)
```bash
uv run python scripts/stacker/eval_stacker.py \
    --features   outputs/stacker_features/test_final/features.jsonl \
    --model      outputs/stacker/stacker_lgbm.pkl \
    --tfidf-pred outputs/tfidf_baseline/test_final/predictions.jsonl \
    --dtv-pred   results/rebase_v2.5/dtv_test_final/predictions.jsonl \
    --out-dir    results/rebase_v2.5/stacker_lgbm/
```

### 6.3 Commit
```bash
git add results/rebase_v2.5/stacker_lr/ results/rebase_v2.5/stacker_lgbm/
git commit -m "results(S3): stacker evaluation on test_final

First clean held-out number for the paper. Bootstrap 95% CI and McNemar
p-values vs TF-IDF-alone and DtV-alone baselines included."
```

### 6.4 Read the numbers

`results/rebase_v2.5/stacker_lr/metrics.json` will contain:
```json
{
  "top1_stacker":          {"mean": 0.XXX, "ci95": [..., ...]},
  "top1_tfidf_baseline":   {"mean": 0.XXX, "ci95": [..., ...]},
  "top1_dtv_baseline":     {"mean": 0.XXX, "ci95": [..., ...]},
  "mcnemar_stacker_vs_tfidf_p": 0.XXX,
  "mcnemar_stacker_vs_dtv_p":   0.XXX,
  ...
}
```

**Decision tree**:
- If `top1_stacker > top1_tfidf_baseline` AND `mcnemar_vs_tfidf_p < 0.05`:
  paper headline number achieved. Go to Task 7.
- If `top1_stacker ≈ top1_tfidf_baseline` (not significant): the stacker
  did not improve over TF-IDF alone. This is a valid negative result —
  document it honestly. Reframe paper around "DtV contributes Top-3
  coverage and interpretability, not Top-1". Go to Task 7 with adjusted
  expectations.
- If `top1_stacker < top1_tfidf_baseline`: something is wrong with the
  features. Common causes: (a) DtV features have wrong sign/scale, (b)
  the LR L2 penalty is too weak and overfits dev_hpo. Re-examine the
  `feature_importance` section of `metrics.json`, and consider adding
  `C=0.1` to the LR and retraining. Do NOT re-evaluate on test_final —
  fix, commit, run ONCE more at most. More than one re-evaluation is
  val-on-val by the back door.

---

## Task 7 — Report table (1 hr, no GPU)

Create `paper/tables/main_results_v2_5.md` with the canonical numbers.
Template:

```markdown
# Main Results (test_final, N=1000)

| System | Top-1 (95% CI) | Top-3 (95% CI) | F1-macro | McNemar vs TF-IDF |
|--------|----------------|----------------|----------|-------------------|
| TF-IDF + LR (rag_pool train) | X.XXX [X.XX, X.XX] | ... | ... | — |
| DtV V2 + RAG (Qwen3-32B-AWQ) | X.XXX [X.XX, X.XX] | ... | ... | p = X.XXX |
| Stacker (LR) | **X.XXX** [X.XX, X.XX] | **X.XXX** | X.XXX | p = X.XXX |
| Stacker (LightGBM) | X.XXX [X.XX, X.XX] | X.XXX | X.XXX | p = X.XXX |

All numbers are clean held-out on test_final (LingxiDiag-16K validation
split). Hyperparameters and stacker weights fit only on dev_hpo. See
`REBASE_PLAN.md §4` for the protocol.
```

---

## Task 8 — Tier 2 ablations (16 GPU-hours, spread across week 2)

Once the headline is in, run each ablation via the same recipe as Task 3
but with a different config overlay:

| Run | Config | Question |
|-----|--------|---------|
| A1 | `configs/overlays/r16_bypass_logic_engine.yaml` | Does logic engine contribute? |
| A2 | `configs/overlays/r17_bypass_checker.yaml` | Marginal contribution of checker |
| A3 | `configs/overlays/r15_no_rag.yaml` | What does RAG buy? |
| A4 | `configs/overlays/evidence_on.yaml` + the fixed temporal template | Does evidence help when F41.1 template actually exists? |

For each: run on `--split test_final`, audit, commit to `results/rebase_v2.5/AX_<name>/`.

Build the ablation table with McNemar vs. B0 (clean DtV baseline).

---

## Task 9 — SFT checker integration (4 GPU-hours, week 4)

pr-stack has LoRA checkpoints under `outputs/` for a Qwen2.5-7B
criterion checker fine-tuned on criterion-matching data (memory records
58.1% → 78.1% criterion accuracy).

Integrate as follows:

1. Check if `src/culturedx/agents/criterion_checker.py` supports a
   backend switch (`prompt_variant` or `backend` parameter).
2. Add a `checker_backend: "sft_lora_7b"` path that loads the LoRA
   adapter and calls it via a local vLLM instance on port 8001.
3. Run DtV with this checker on `test_final`:
   ```bash
   vllm serve Qwen2.5-7B-Instruct \
       --enable-lora \
       --lora-modules culturedx_checker=outputs/lora_checker/checkpoint-300/ \
       --port 8001 &
   uv run culturedx run \
       -c configs/base.yaml \
       -c configs/vllm_awq.yaml \
       -c configs/v2.4_final.yaml \
       -c configs/overlays/sft_checker.yaml \
       -d lingxidiag16k \
       --split test_final \
       --run-name dtv_sft_checker \
       -n 1000
   ```
4. Audit, commit, compare vs B0.

This is Tier 3 Option I2 from `REBASE_PLAN.md`. If it improves B0's
Top-1 by ≥2pp, the stacker Top-1 will also improve (since DtV features
get better signal).

---

## Task 10 — Bootstrap + McNemar for every Tier-2 ablation

The `eval_stacker.py` script already computes bootstrap CI and McNemar
for the stacker. For DtV-only ablations, write a thin wrapper
`scripts/bootstrap_dtv.py` that:

1. Loads `predictions.jsonl` from two run directories (A vs B0).
2. Aligns on case_id.
3. Computes Top-1 correctness vector for each.
4. Calls `scripts.stacker.eval_stacker.bootstrap_ci` and `mcnemar_p`.
5. Emits a single JSON with `{a_mean, a_ci95, b_mean, b_ci95, mcnemar_p}`.

This unblocks the ablation table for the paper.

---

## Quick-check commands

```bash
# Run all tests
uv run pytest tests/ -q

# Audit every committed run
for d in results/rebase_v2.5/*/; do
    echo "=== $d ==="
    uv run python scripts/audit_run.py "$d" || echo "FAILED"
done

# Quick smoke on a fresh machine
uv run python scripts/stacker/build_features.py --help
uv run python scripts/stacker/train_stacker.py --help
uv run python scripts/stacker/eval_stacker.py --help
uv run python scripts/audit_run.py --help
uv run python scripts/generate_splits.py --help
uv run python scripts/train_tfidf_baseline.py --help
```

---

## What NOT to do (tripwires)

1. **Do not evaluate on test_final more than once per ablation.** If
   you discover a bug in the stacker after eval, fix it, then
   re-evaluate **once** — not iteratively.
2. **Do not train TF-IDF on `train`.** Always `--eval-split dev_hpo` or
   `--eval-split test_final`; training is always on `rag_pool`.
3. **Do not run DtV on `train` or `validation`** directly. Use logical
   splits (`dev_hpo` / `test_final`).
4. **Do not re-fit HPO on val.** HPO is on `dev_hpo` only. `abs_threshold`,
   `comorbid_min_ratio`, RRF weights, stacker features, thresholds —
   all `dev_hpo`.
5. **Do not edit `outputs/_archive_pre_rebase/`.** It's a reference
   trail. If you need to compare old results, copy out but don't modify
   in place.
6. **Do not merge this branch into pr-stack or main.** They're the
   audit trail. `clean/v2.5-eval-discipline` is the forward branch; it
   stays separate until submission.

---

## Handoff summary

At the end of Task 6 you'll have:

1. `configs/splits/lingxidiag16k_v2_5.yaml` populated with real ids
2. `outputs/tfidf_baseline/{dev_hpo,test_final}/metrics.json`
3. `results/rebase_v2.5/dtv_dev_hpo/` and `dtv_test_final/` — audited clean
4. `outputs/stacker_features/` — 31-dim per-case features
5. `outputs/stacker/` — trained LR (and LightGBM) model
6. `results/rebase_v2.5/stacker_lr/metrics.json` — **the first paper number**

Estimated wall-clock on RTX 5090:
- Task 0 + 1 + 2 + 4 + 5 + 6: **~45 min CPU**
- Task 3 (DtV on both splits): **~8 hr GPU**

Total: **one working day** to go from the rebase commits to the
headline paper number.

Everything after that (Tasks 7–10) is ablation and error-analysis work
that should fit in weeks 2–5 per `REBASE_PLAN.md §7`.
