# Rebase Plan — `clean/v2.5-eval-discipline`

**Created**: 2026-04-20
**Target submission**: August 2026 (~16 weeks out)
**Base branch**: `pr-stack/docs-and-production-hardening` @ `cda48d5`

---

## 0. Why this rebase exists

Two branches have drifted:

- `main-v2.4-refactor` has the paper's conclusions (Top-1 0.505 DtV,
  0.552/0.841 final_combined) but buggy Jinja templates that silently
  broke four ablations (R6, R17, R20, R21v2).
- `pr-stack/docs-and-production-hardening` has the fixed code
  (silent-fallback removal, BGE-M3 hybrid, temporal upgrade,
  somatization ontology expansion, SFT checker training pipeline) but
  never ran the paper's evaluation end-to-end.

Neither branch in isolation is safe to cite. This branch consolidates
the infrastructure of pr-stack with the audit discipline of main under
a stricter evaluation protocol.

---

## 1. The finding that reframes the paper

**TF-IDF + LogReg trained on train (14k), evaluated on val (1k),
achieves Top-1 0.610** — higher than any LLM system:

| System | Top-1 | Top-3 | F1-macro |
|--------|------:|------:|---------:|
| DtV V2 + RAG (Qwen3-32B MAS) | 0.505 | 0.762 | 0.190 |
| **TF-IDF + LR (char_wb, sklearn)** | **0.610** | **0.829** | **0.352** |
| RRF stack (DtV + TF-IDF, k=30) | 0.557 | 0.846 | 0.255 |
| Final combined (stack + F1-opt)* | 0.552 | 0.841 | 0.302 |

*val-on-val calibration; see `outputs/_archive_pre_rebase/README.md §2`

Agreement analysis on val 1000:
- Both correct: 400 (40.0%)
- TF-IDF only correct: 210 (21.0%)
- DtV only correct: 91 (9.1%)
- Both wrong: 299 (29.9%)

**Oracle ceiling over TF-IDF + DtV: 0.701 Top-1.** Current RRF stack
at 0.557 captures only 35% of that headroom. The gap is because RRF
only uses rank; confidence signals are thrown away. A learned stacker
that sees both TF-IDF calibrated probabilities and DtV structured
checker outputs should reach **Top-1 0.62–0.65 on clean held-out test**.

### Paper reframe

From: "MAS beats Single LLM" (weak, borderline)
To: "TF-IDF is already a strong baseline. We design a
MAS-conditioned stacker that defers to TF-IDF when it is confident
and invokes LLM-based reasoning when TF-IDF is uncertain, achieving
both higher Top-1/Top-3 accuracy and criterion-level explainability."

This frame is honest, concrete, and answers "what is MAS *for*?"

---

## 2. Contamination ledger (what to throw out)

| Artifact | Status | Reason |
|----------|--------|--------|
| main: R6, R20, R21v2, old R17 | not imported | silent template failure, checker 0/1000 |
| main: `final_combined` Top-1 0.552 | not imported | val-on-val offset fitting |
| main: `t2_rrf` / `t3_tfidf_stack` | not imported | RRF k and weights grid-searched on val |
| main: `configs/v2.4_final.yaml` `abs_threshold=0.50`, `comorbid_min_ratio` | flagged for re-fit | val-selected thresholds |
| pr-stack: `outputs/sweeps/*` | archived under `outputs/_archive_pre_rebase/sweeps/` | N=200 under-powered |
| pr-stack: `outputs/eval/*` | archived under `outputs/_archive_pre_rebase/eval/` | superseded |

## 3. What this rebase keeps

| Artifact | Reason |
|----------|--------|
| All pr-stack source code | Latest infrastructure |
| `prompts/agents/criterion_checker_temporal_zh.jinja` | Already present on pr-stack; bug from main does not reproduce |
| pr-stack's 388-test suite | Must continue to pass |
| Canonical artifact schema | Reproducibility |
| TF-IDF baseline (`scripts/train_tfidf_baseline.py`) | Imported from main; training is clean (train → val) |
| Paper-aligned eval (`src/culturedx/eval/lingxidiag_paper.py`) | Imported from main; Table-4 metrics are the citation target |
| `docs/audit_main_v2.4/*` | History + self-retractions |

---

## 4. The new eval discipline

### 4.1 Three-way split

LingxiDiag-16K ships with train (~15 000) and validation (1 000). No
vendor test set. We carve one out of train, once, with a fixed seed,
and commit case-id lists.

| Split | Size | Purpose | Source |
|-------|------|---------|--------|
| `rag_pool` | train \ dev_hpo (~14 000) | TF-IDF training, FAISS index, SFT checker training | complement of `dev_hpo` within train |
| `dev_hpo` | 1 000 | HPO, offset fitting, stacker training, prompt iteration | stratified-by-ICD-10-parent from train, seed=20260420 |
| `test_final` | 1 000 | Paper numbers. **Touched once** at submission time. | the LingxiDiag-16K `validation-*.parquet` (unchanged) |

**Implementation**:
- `scripts/generate_splits.py` — deterministic generator
- `configs/splits/lingxidiag16k_v2_5.yaml` — committed case-id list
- `src/culturedx/data/adapters/lingxidiag16k.py` — honors
  `split="dev_hpo"` and `split="rag_pool"`

### 4.2 Rules of engagement

1. **Every HPO knob is fit on `dev_hpo` only.** This includes:
   `abs_threshold`, `comorbid_min_ratio`, RRF weights and k, stacker
   parameters, F1-opt offsets, retrieval `top_k`, triage confidence
   threshold, prompt temperature.
2. **Every ablation metric is reported on `test_final`** with
   bootstrap CI (1 000 resamples, seed=20260420) and McNemar vs. the
   clean DtV baseline B0.
3. **`test_final` is touched exactly once per ablation.** No iterative
   looking. If an ablation fails, the failure is reported as-is.
4. **The TF-IDF model, FAISS index, and SFT checker are trained on
   `rag_pool` only.** No test-case leakage into retrieval or fit.
5. **Pipeline fails fast on missing templates or misconfigured
   variants.** No `force_prediction=true` silently hiding checker
   failures — failures are logged to `failures.jsonl` and reflected in
   `metrics_summary.json` as a coverage number.
6. **Every run emits a `run_manifest.json`** containing git SHA,
   config hash, split SHA256, model name, and a `checker_coverage`
   field per disorder. Runs with <95% coverage for any disorder are
   rejected by `scripts/audit_run.py`.

### 4.3 Pre-run coverage gate

Before any run's metrics are accepted:
```bash
uv run python scripts/audit_run.py <run_dir>
# Checks:
#  (1) run.log has 0 TemplateNotFound warnings
#  (2) per-disorder checker coverage >= 95%
#  (3) primary differs from diagnostician_top1 in >=5% of cases
#  (4) run_manifest.json git SHA is ancestor of HEAD
# Exit 0 => clean. Exit non-zero => quarantine.
```

---

## 5. Experiment plan

GPU budget: **~50 GPU-hours total on RTX 5090 32 GB**
(Qwen3-32B-AWQ ≈ 13 s/case on DtV → N=1000 ≈ 3.6 hr per config)

### Tier 0 — Baselines (16 GPU-hr, must come first)

| Run | Config | GPU hr | Purpose |
|-----|--------|-------:|---------|
| T0 | TF-IDF + LR trained on `rag_pool`, evaluated on `test_final` | 0 (CPU) | Paper's strongest single baseline. Replaces main's `tfidf_baseline`. |
| B0 | DtV V2 + RAG on `test_final` | 4 | New canonical MAS baseline. Replaces main's `t1_diag_topk`. |
| B1 | Single-LLM baseline on `test_final` | 2 | Replaces r18. MAS delta measured clean. |
| B2 | DtV V2 + RAG on `dev_hpo` | 4 | Used to HPO-refit thresholds and to train the stacker. Predictions NEVER reported as result. |
| B3 | TF-IDF + LR evaluated on `dev_hpo` | 0 (CPU) | Stacker training features. |
| B4 | Single-LLM on `dev_hpo` | 2 | Optional stacker feature. |
| B5 | DtV V2 + RAG on `rag_pool` 2k sample | 4 | Optional, only if stacker needs more training examples. |

### Tier 1 — The stacker (2 CPU hours, zero GPU) ⭐ **highest ROI**

| Run | Purpose |
|-----|---------|
| S1 | Build stacker features on `dev_hpo`: per-case 30-dim vector (TF-IDF probs + DtV top-5 scores + checker met_ratios + TF-IDF margin + abstain flag) |
| S2 | Train stacker (LR and LightGBM variants) on `dev_hpo` |
| S3 | Apply stacker to `test_final` (touches test exactly once). Report Top-1, Top-3, F1-macro with 1000-bootstrap CI. Expected: Top-1 **0.62–0.65** |
| S4 | McNemar vs T0 (TF-IDF alone) and vs B0 (DtV alone) |

**Acceptance criterion for stacker**: Top-1 on `test_final` must
significantly exceed both T0 and B0 (McNemar p < 0.05, two-sided).

### Tier 2 — Headline ablations (16 GPU-hr)

| Run | Config | GPU hr | Question |
|-----|--------|-------:|---------|
| A1 | DtV with logic engine bypassed | 4 | Does deterministic ICD-10 gating contribute? (replaces R16) |
| A2 | DtV with criterion checker fully bypassed | 4 | Marginal contribution of the checker (replaces R17v2 from main) |
| A3 | DtV with RAG disabled | 4 | What does retrieval buy? (replaces R15) |
| A4 | DtV with evidence pipeline enabled (temporal template present on pr-stack) | 4 | **Directly refutes main-v2.4's claim that evidence hurts** |

### Tier 3 — One infrastructure claim (4 GPU-hr, pick one)

| Option | Claim | Why it matters |
|--------|-------|----------------|
| **I2 (recommended)** | SFT checker (LoRA Qwen2.5-7B, existing checkpoint on pr-stack) | Standalone "supervised gating closes structural gaps" story |
| I1 | BGE-M3 hybrid vs dense retrieval | Answers memory's open question |
| I3 | Temporal extraction upgrade end-to-end | Tests whether 18→64% F41 recall traverses to Top-1 |

### Tier 4 — Error analysis (0 GPU)

| Task | Purpose |
|------|---------|
| E1 | 200-case error taxonomy on B0 (out-of-canonical, ranking, calibrator). Predicted split: ~43% / ~32% / ~24% |
| E2 | Stacker gating analysis: when does the stacker pick TF-IDF vs DtV? Plot TF-IDF margin vs stacker weight |
| E3 | Bootstrap CI + McNemar for every Tier-2 and Tier-1 result |
| E4 | Per-disorder F1 breakdown for baseline vs stacker |

### Total budget

Tier 0 + Tier 1 + Tier 2 + Tier 3 = 4 + 2 + 4 + 4 + 0 + 2 + 4 + 4 + 4 + 4 + 4 = **36 GPU-hours** + ~8 CPU-hours.
Leaves 14 GPU-hours headroom for re-runs.

---

## 6. What each sub-system must do

### 6.1 Data adapter
`src/culturedx/data/adapters/lingxidiag16k.py`:
- Accept `split="dev_hpo"` and `split="rag_pool"` by loading case-id
  allowlist from `configs/splits/lingxidiag16k_v2_5.yaml`
- Ensure `split="validation"` unchanged (= `test_final`)
- Emit hash of loaded case-id list into log (for `run_manifest.json`)

### 6.2 Split generator
`scripts/generate_splits.py`:
- Deterministic, seed=20260420
- Stratified by 12-class parent label
- Output `configs/splits/lingxidiag16k_v2_5.yaml`
- Committed in this branch

### 6.3 TF-IDF baseline
`scripts/train_tfidf_baseline.py` (ported from main):
- CHANGE: train on `split="rag_pool"` (not `split="train"`)
- Evaluate on both `dev_hpo` (for stacker features) and `test_final`
- Save model artifacts to `outputs/tfidf_baseline/`

### 6.4 Stacker
`scripts/stacker/build_features.py`:
- Join TF-IDF predictions + DtV predictions (+ optional Single LLM)
- Produce `features_{split}.parquet` with 30-dim feature vector per case

`scripts/stacker/train_stacker.py`:
- LR and LightGBM trainers
- Train on features from `dev_hpo` only
- Frozen, saved to `outputs/stacker/`

`scripts/stacker/eval_stacker.py`:
- Apply frozen stacker to features from `test_final`
- Compute Table-4 metrics, bootstrap CI, McNemar
- Output to `results/rebase_v2.5/stacker/`

### 6.5 Audit
`scripts/audit_run.py`:
- Parses run.log for `TemplateNotFound`
- Parses `predictions.jsonl` for checker coverage and primary vs
  diagnostician_top1 divergence
- Verifies `run_manifest.json` git SHA ancestry
- Exit code non-zero on any failure

### 6.6 Reporting
`scripts/build_results_table.py`:
- Loads all runs from `results/rebase_v2.5/*` whose audit passed
- Emits a single Markdown table with bootstrap CIs and McNemar p-values

---

## 7. Week-by-week

| Week | Work |
|------|------|
| 1 (Apr 20–26) | **THIS REBASE + Tier 0 + Tier 1 (stacker)**. By end of week: clean T0, B0, stacker on `test_final` with bootstrap CI. First headline number in the paper. |
| 2 (Apr 27–May 3) | HPO re-fit on `dev_hpo`. Freeze `configs/v2.5_final.yaml`. Run A1–A3. |
| 3 (May 4–10) | Run A4 (evidence). Error analysis E1. First draft of ablation table. |
| 4 (May 11–17) | SFT checker integration (I2). Clean run I2 on `test_final`. |
| 5 (May 18–24) | Bootstrap CIs and McNemar (E3). Redraft paper Section 4 (Results). |
| 6–7 (May 25–Jun 7) | Paper writing: architecture, related work, error analysis. 長庚合作在此時介入. |
| 8 (Jun 8–14) | Optional: MDD-5K cross-dataset transfer. Finalize paper Section 5. |
| 9–10 (Jun 15–28) | Full paper draft + supervisor review. |
| 11–12 (Jun 29–Jul 12) | Revision cycle 1. Any targeted re-runs. |
| 13–14 (Jul 13–26) | Revision cycle 2. Final `test_final` runs (each touched once). |
| 15 (Jul 27–Aug 2) | Camera-ready. |
| 16 (Aug 3–9) | Submission buffer. |

---

## 8. Non-goals (explicit)

- Re-running R11/R12 seed variance (already stable)
- New datasets beyond LingxiDiag-16K + MDD-5K
- DSM-5 support (future work)
- Multi-agent debate variants (optimization paradox already concluded)
- Real-time inference optimization

---

## 9. Branch hygiene

- Do not delete `main-v2.4-refactor`,
  `pr-stack/docs-and-production-hardening`, or
  `research/lingxidiag-alignment`. They are the audit trail.
- Protect `clean/v2.5-eval-discipline` on GitHub:
  - require PR before merge
  - disallow force-push
  - require the audit check CI job (added once `audit_run.py` lands
    in CI)
- After submission, branch-protect the old branches read-only.
