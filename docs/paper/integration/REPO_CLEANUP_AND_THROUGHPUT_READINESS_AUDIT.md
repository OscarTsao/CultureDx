# Repo Cleanup + Throughput Readiness Audit (Round 147)

**Date:** 2026-04-30
**Branch:** feature/gap-e-beta2-implementation @ 2c82f42
**Mode:** READ-ONLY audit. No production code changes. No commits. No pushes. No GPU.
**Scope:** Inventory dirty + untracked state, classify subdirs, analyze throughput levers, recommend branching strategy.

---

## 0 — Workspace baseline

| Item | Value |
|---|---|
| HEAD | `2c82f42` (PI summary commit) |
| Active branch | `feature/gap-e-beta2-implementation` |
| Frozen tag `paper-integration-v0.1` | `c3b0a46` (untouched) |
| `origin/main-v2.4-refactor` | `3d5e014` (untouched) |
| `origin/master` | `3d3c079` (default, 182 commits behind main-v2.4-refactor) |
| Other branches | clean/v2.5-eval-discipline, pr-stack/docs-and-production-hardening, research/lingxidiag-alignment |
| In sync with origin | yes |

---

## 1 — Dirty tracked files inspection

### 1.1 `configs/vllm_awq.yaml`

```diff
@@ -3,6 +3,7 @@ llm:
   provider: vllm
   model_id: "Qwen/Qwen3-32B-AWQ"
   base_url: http://localhost:8000
+  context_window: 8192
   temperature: 0.0
```

| Question | Answer |
|---|---|
| What changed | One added line: `context_window: 8192` |
| Throughput-related? | No — it's a context-window declaration matching the running vLLM `--max-model-len 8192`. Does not alter `max_concurrent`, `enforce_eager`, `max_num_seqs`, `dtype` |
| BETA-2b-related? | No |
| Orphan dirty? | Effectively yes — adds documentation/redundancy; vLLM already enforces 8192 via `--max-model-len` |
| Used in any past canonical run? | No round (114/120/128/132) depended on this config field — they used the running vLLM at `localhost:8000` directly. The added field is client-side metadata only |

**Verdict:** orphan dirty; harmless redundancy. Safe to commit (as `chore: declare context_window in vllm config`) or revert. Either way, **NOT** load-bearing.

**Recommended action:** revert (`git checkout configs/vllm_awq.yaml`) — keeps configs minimal — OR commit standalone if you prefer documenting the running-server contract. Your call.

### 1.2 `src/culturedx/retrieval/case_retriever.py`

```diff
+    _shared_encoder: Any | None = None
+    _encoder_lock = threading.Lock()
...
     def _get_encoder(self) -> Any:
         if self._encoder is None:
-            _check_sentence_transformers()
-            from sentence_transformers import SentenceTransformer
-            logger.info("Loading BGE-M3 encoder (first call)...")
-            self._encoder = SentenceTransformer("BAAI/bge-m3", device="cpu")
-            logger.info("BGE-M3 encoder loaded.")
+            with self._encoder_lock:
+                if self._shared_encoder is None:
+                    _check_sentence_transformers()
+                    from sentence_transformers import SentenceTransformer
+                    logger.info("Loading BGE-M3 encoder (first call)...")
+                    self._shared_encoder = SentenceTransformer("BAAI/bge-m3", device="cpu")
+                    logger.info("BGE-M3 encoder loaded.")
+                self._encoder = self._shared_encoder
         return self._encoder
```

| Question | Answer |
|---|---|
| What changed | Class-level singleton with thread-safe lock around BGE-M3 encoder construction. Multiple `CaseRetriever` instances now share one encoder. |
| RAG-related? | Yes — affects BGE-M3 sentence-encoder for RAG case retrieval |
| Used in current Full HiED pipeline? | Yes — `case_retriever` is consumed by `pipeline/cli.py` (HiED path) |
| Throughput-related? | **Yes (indirectly)** — eliminates redundant encoder loads when multiple retriever instances are constructed (e.g. parallel modes) |
| Orphan / abandoned? | No — this is a sensible memory + startup optimization (~ 2GB BGE-M3 weights × N retrievers → 1× shared) |
| Used in any committed prediction artifact? | Cannot verify by code alone; behavior is identical to HEAD when only one retriever is constructed (single-process eval). The shared-encoder code path only kicks in if multiple retrievers exist concurrently. Recent canonical runs (Round 114/120/128/132) used single-process so the change is **behavior-equivalent** for those runs |

**Verdict:** legitimate throughput/memory optimization, behavior-equivalent for prior runs (single retriever), beneficial for future parallel orchestration (Lever A). NOT BETA-2b-related. Branch-isolated to be promoted as a clean commit.

**Recommended action:** commit standalone as `perf(retrieval): share BGE-M3 encoder across retriever instances` after verifying with smoke (run `tests/test_retrieval*` if available, or single-mode HiED smoke). Do NOT bundle with BETA-2b adoption work — different scope.

---

## 2 — Untracked artifact inventory

### 2.1 Tarballs at repo root (workspace pollution)

61 `culturedx_*.tar.gz` files at repo root, total ~900 KB. Span Round 18 (2026-04-22) → Round 136 (2026-04-30). All are **scratch sandbox snapshots** created during plan/sandbox iteration cycles. None referenced by any committed code or doc.

| Action | Recommendation |
|---|---|
| Move to gitignored archive | `mkdir -p .archive/scratch_tarballs/ && mv culturedx_*.tar.gz .archive/` then add `.archive/` to `.gitignore` |
| Hard delete | acceptable — durable record exists in git history (sandbox docs already committed) |
| Keep at root | NOT recommended — pollutes `git status`, makes branch-switching noisy |

### 2.2 ZIP files at repo root

- `files.zip` (21K), `files0426.zip` (21K), `files2.zip` (127K) — 3 unidentified zips. Cannot tell content without extracting. Same recommendation: archive or delete.

### 2.3 Scratch markdown at repo root

| File | Lines | Recommendation |
|---|---|---|
| `ABSTRACT.md` | 22 | Stale draft — duplicate of `docs/paper/drafts/ABSTRACT.md`. Delete. |
| `WORKSTREAM_C_CODEX_generalization.md` | 475 | Codex-CLI handoff doc for generalization workstream. Move to `docs/handoffs/` if still needed; else delete. |
| `WS_D_Task1_Task2_codex.md` | 707 | Codex-CLI handoff doc for workstream D. Same — move or delete. |

### 2.4 `v2.5_rebase/` directory (412K)

Contains `BRANCH_STATUS.md`, `culturedx_sota_push.tar.gz`, `HANDOFF_CLAUDE_CODE.md`, `REBASE_PLAN.md`, `rebase_v2.5.patch`, `STACKER_README.md`. Rebase artifacts from a v2.5 branch sync. Status: superseded by current `feature/gap-e-beta2-implementation` work.

**Recommended action:** archive to `.archive/v2.5_rebase/` or delete entirely.

### 2.5 Untracked code/scripts

- `scripts/generalization/replay_cached_checkers.py` — appears to be Workstream C (Codex generalization) implementation. Currently not committed. **Decide:** is this still active workstream? If yes, commit on a separate `feature/generalization-replay` branch (NOT mixed into Gap E branch).
- `results/generalization/_novel_replay_smoke{,2}/`, `_novel_smoke/`, `_r6_replay_smoke/` — total ~570K of smoke artifacts from generalization replay. Same provenance as the script above. Belong on the generalization branch (or in `outputs/` since this is gitignored).

### 2.6 Top 3 most-important untracked items

| # | Item | Why important |
|---|---|---|
| 1 | `scripts/generalization/replay_cached_checkers.py` | Active uncommitted code — risk of loss |
| 2 | `WS_D_Task1_Task2_codex.md` (707 lines) | Workstream-D plan/handoff — content not elsewhere |
| 3 | `WORKSTREAM_C_CODEX_generalization.md` (475 lines) | Workstream-C plan/handoff — content not elsewhere |

**Recommended action:** triage 1+2+3 first (preserve content); bulk-archive 2.1/2.2/2.4 second.

---

## 3 — Legacy `paper/` directory audit

### 3.1 Structure

```
paper/
  drafts/main.md, main.tex, references.bib  (no sections/ subdir)
  figures/
  preprints/
  supplementary/
  tables/main_results.md, ablation_results.md
  README.md
```

### 3.2 vs. canonical `docs/paper/`

The `paper-integration-v0.1` tag (commit `c3b0a46`) modifies `docs/paper/drafts/SECTION_5_2.md` and `docs/paper/drafts/SECTION_5_6.md` — confirming **`docs/paper/` is the canonical, frozen-by-tag manuscript directory.** `paper/` is **legacy**.

### 3.3 Content drift

`paper/drafts/main.md` Abstract claims Overall = 0.527 LingxiDiag-only with single-dataset framing. Current `docs/paper/drafts/ABSTRACT.md` is reframed for parity-plus-audit narrative across LingxiDiag + MDD-5K with Overall = 0.527 / 0.499 etc. — i.e., the legacy `paper/main.md` is **stale** by ~Round 77 (Abstract reframe).

`paper/tables/main_results.md` is the OLD Table format (single-dataset, 6 LLM rows) — superseded by `docs/paper/integration/TABLE_NUMBERING_PLAN.md` and Section 5.X tables.

`paper/drafts/main.tex` exists — **may be the only LaTeX scaffolding**. Verify before deletion: is there a current `.tex` build under `docs/paper/` for conference submission? (Spot-check: `docs/paper/` has only `.md` files in the inspected ls output. The legacy `.tex` may be the sole LaTeX artifact — preserve it during cleanup or migrate.)

### 3.4 Recommended action

| Path | Action | Reason |
|---|---|---|
| `paper/README.md` | Update with banner: "DEPRECATED — see `docs/paper/`" OR delete | Currently misleading |
| `paper/drafts/main.md`, `main.tex`, `references.bib` | Move `main.tex` + `references.bib` to `docs/paper/drafts/legacy/` (preserve LaTeX scaffolding); delete `main.md` (superseded) | Stale prose; LaTeX may still be needed |
| `paper/tables/*.md` | Archive to `docs/paper/integration/legacy_tables/` or delete | Stale numbers |
| `paper/figures/`, `paper/supplementary/`, `paper/preprints/` | Inspect contents (not done in this audit); move active figures to `docs/paper/figures/` if not yet present | Out of scope to inspect each file |

**This is a multi-step move that should happen on a dedicated cleanup branch (see §6).** NOT to be mixed with Gap E.

---

## 4 — USAGE_AUDIT classification (high-level)

| Subdir | Class | Example consumer |
|---|---|---|
| `agents/` | USED | `modes/base.py`, `tests/test_triage.py`, `tests/test_contrastive.py` |
| `core/` | USED | `agents/criterion_checker.py`, `evidence/criteria_matcher.py`, `modes/single.py` (config layer) |
| `data/` | USED | `pipeline/cli.py`, `tests/test_lingxidiag16k.py` |
| `diagnosis/` | USED | `modes/hied.py`, `tests/test_calibrator.py` |
| `ensemble/` | SANDBOX | `scripts/lowfreq_boost_sweep.py`, `scripts/run_ensemble.py` (no production HiED dependency) |
| `eval/` | USED | `pipeline/runner.py`, `tests/test_lingxidiag_paper.py` |
| `evidence/` | USED | `pipeline/cli.py`, `pipeline/runner.py` |
| `llm/` | USED | `agents/criterion_checker.py`, `modes/single.py` |
| `modes/` | USED | `pipeline/cli.py`, `pipeline/runner.py`, `tests/test_hied_e2e.py` |
| `ontology/` | USED | `agents/diagnostician.py`, `agents/criterion_checker.py` |
| `pipeline/` | USED | `tests/test_sweep.py`, `tests/test_runner_artifacts.py` |
| `postproc/` | SANDBOX | `scripts/ensemble/tune_on_dev.py`, `tests/test_ensemble_gate.py` (post-prediction calibration sandbox) |
| `retrieval/` | USED | `pipeline/cli.py`, `scripts/generalization/replay_cached_checkers.py` |
| `translators/` | USED | `tests/test_dsm5_translator.py`, `scripts/dsm5/generate_review_sample.py` |

### 4.1 Notes

- **All 14 subdirs have at least one consumer** — none are dead.
- `ensemble/` and `postproc/` are SANDBOX in the sense that consumers are scripts (`scripts/`) and tests, not the production `pipeline/cli.py` HiED path. They are kept for ablation table reproduction (`scripts/ablation_sweep.py`, `scripts/run_ensemble.py`). **Do not cut.**

**Recommended action:** No cuts. This is a healthy module graph. Future deeper audit (per-file, not per-subdir) may reveal unused symbols, but that's out of scope for Round 147.

---

## 5 — Throughput levers A/B/C analysis

### Lever A — Parallel orchestration (3-mode parallel)

| Aspect | Detail |
|---|---|
| Current state | Single-mode sequential runs via `scripts/run_full_eval.py` per mode (lingxi_icd10/dsm5/both, mdd_icd10/dsm5/both = 6 modes total) |
| Proposed change | Orchestration script that launches 3 modes concurrently (e.g. lingxi triplet vs mdd triplet, sharing one vLLM server). NO production code change. |
| Expected speedup | 1.8–2.3× on the canonical 6-mode run (NOT 3× — vLLM is the bottleneck, batching across modes still saturates the same GPU) |
| Risk | LOW — vLLM handles concurrent requests via its own scheduler; client-side `max_concurrent=16` already exercises this path. Risk is logging/race conditions in scratch dirs (use per-mode `RUN_DIR`) |
| Implementation cost | ~50–100 lines of new shell or Python orchestrator script, + parallel-safe RUN_DIR pattern |
| Smoke required | Run 2 modes in parallel, byte-compare predictions vs sequential baseline (must be invariant) |

### Lever B — vLLM startup config tweaks

Current vLLM startup (from running process):
```
--model Qwen/Qwen3-32B-AWQ --quantization awq_marlin --port 8000
--max-model-len 8192 --gpu-memory-utilization 0.85 --dtype float16 --enforce-eager
```

Two changes proposed:

#### B1 — Drop `--enforce-eager`
| Aspect | Detail |
|---|---|
| Current | `--enforce-eager` forces eager mode (no CUDA graph capture); deterministic-ish but slower |
| Proposed | Remove flag → vLLM uses CUDA graphs by default (~1.3–1.5× speedup) |
| Risk | **Reproducibility regression.** Round 128 native smoke showed 2/120 cases divergent (1.7%) under `--enforce-eager` — without it, divergence may grow. Affects bit-identical claims for paper-canonical reruns |
| Implementation cost | 1 line in startup script |
| Smoke required | Run V1 BETA-2b smoke (N=20 × 6 modes) without `--enforce-eager`, compare against Round 128 native smoke. Accept if divergence ≤ 5% AND invariants pass on all cases |

#### B2 — Raise `--max-num-seqs` (currently default = 256)
| Aspect | Detail |
|---|---|
| Current | Default `--max-num-seqs 256` — caps concurrent sequences in vLLM scheduler |
| Proposed | Set `--max-num-seqs 512` (or scan 256/384/512 in smoke) |
| Expected speedup | Marginal — `max_concurrent=16` client-side already gates submission far below 256 ceiling |
| Risk | **Probably no benefit** unless client `max_concurrent` is also raised |
| Implementation cost | 1 line in startup script |
| Smoke required | Only worth testing IF Lever A or C raises client concurrency above ~64 |

### Lever C — Client-side `max_concurrent` 16 → 32 / 64

| Aspect | Detail |
|---|---|
| Current | `max_concurrent: 16` in `configs/vllm_awq.yaml` |
| Proposed | Raise to 32 or 64; semaphore in `llm/client.py:244` |
| Expected speedup | ~1.5–2× IF GPU is currently underutilized (likely, given Round 114 reports CPU-bound at low GPU usage) |
| Risk | LOW — vLLM scheduler will queue if oversubscribed; only risk is memory pressure on prefill |
| Implementation cost | 1 line in config |
| Smoke required | Smoke at 32, then 64. Watch nvidia-smi for memory spikes. Compare prediction parity vs 16. |

### Summary table

| Lever | Speedup | Risk | Cost | Recommended order |
|---|---|---|---|---|
| C (client `max_concurrent` 16→32/64) | 1.5–2× | LOW | trivial | **First** — biggest win for least risk |
| A (3-mode parallel orchestrator) | 1.8–2.3× on 6-mode | LOW | medium | **Second** — combines well with C |
| B1 (drop `--enforce-eager`) | 1.3–1.5× | MEDIUM (reproducibility) | trivial | **Third** — only if reproducibility tolerance allows |
| B2 (raise `--max-num-seqs`) | marginal | LOW | trivial | **Skip** unless C/A push bottleneck to vLLM scheduler |

**Recommended action:** Adopt C first (smoke + 1-line config commit). Re-evaluate A/B1 after C measurements.

---

## 6 — Safe-now vs wait-later classification

### Safe NOW (branch-isolated, no adoption decision needed)

| Item | Why safe now |
|---|---|
| Archive 61 tarballs to `.archive/scratch_tarballs/` (or delete) | Workspace hygiene, no code/doc references |
| Archive 3 root-level zips | Same |
| Delete `ABSTRACT.md` at repo root (duplicate of canonical) | Stale duplicate |
| Move `WORKSTREAM_C_CODEX_generalization.md` + `WS_D_Task1_Task2_codex.md` to `docs/handoffs/` (or delete if obsolete) | Out of repo root |
| Archive `v2.5_rebase/` | Superseded |
| Commit `case_retriever.py` perf optimization standalone (after smoke) | Behavior-equivalent for single-retriever path; safe |
| Adopt Lever C (`max_concurrent` 32 or 64) after smoke | Branch-isolated; reproducibility-preserving |
| Add `.archive/`, `*.tar.gz`, `*.zip` to `.gitignore` | Hygiene |

### Wait LATER (depends on Q1/Q2/Q3 verdict)

| Item | Why wait |
|---|---|
| Lever A (parallel orchestrator) | Most useful AFTER BETA-2b adoption decision: if V3 GPU canonical is requested, parallel orchestrator cuts the run from 5–7hr to ~2.5–3.5hr. If CPE sufficient, less urgent |
| Lever B1 (drop `--enforce-eager`) | If Q2 = V3 GPU canonical, KEEP `--enforce-eager` for the canonical run (max determinism), tweak only afterwards. If Q2 = CPE sufficient, B1 can proceed independently |
| Legacy `paper/` directory cleanup | Touches paper materials — wait for Q1 verdict to avoid race with Plan v1.3.4 manuscript-impact PR |
| Workstream C/D code commits (`replay_cached_checkers.py` + smoke artifacts) | Different workstream; should land on `feature/generalization-*` branch after BETA-2b dust settles |
| `configs/vllm_awq.yaml` `context_window` declaration | Trivial; can be either committed or reverted any time. Defer to avoid noise |

### Counts

- **SAFE NOW:** 8 items (workspace hygiene + 1 perf commit + 1 throughput config commit)
- **WAIT LATER:** 5 items (parallel orchestrator, eager-mode tweak, paper/ migration, generalization workstream, vllm config redundancy)

**Recommended action:** Execute SAFE NOW items in 2 mini-PRs on a new `chore/repo-cleanup-and-throughput` branch (described in §7). Hold WAIT LATER items until BETA-2b verdict and/or generalization workstream resumes.

---

## 7 — Recommended branch strategy

### 7.1 Current branch state

| Branch | HEAD | Purpose | Status |
|---|---|---|---|
| `master` (origin default) | `3d3c079` | Production / public default | 182 commits behind `main-v2.4-refactor` (stale) |
| `main-v2.4-refactor` | `3d5e014` | Mainline development trunk | Frozen during paper-integration; **canonical PI summary ancestor for HiED** |
| `feature/gap-e-beta2-implementation` | `2c82f42` | Current Gap E + BETA-2b work | Active; awaiting PI verdict |
| `clean/v2.5-eval-discipline` | `914381b` | Older eval-discipline rework (pre-BETA-2) | Stale unless v2.5 work resumes |
| `pr-stack/docs-and-production-hardening` | `cda48d5` | Older PR stack | Stale |
| `research/lingxidiag-alignment` | `7eb6ba9` | LingxiDiag preprocessing research | Stale |
| Tag `paper-integration-v0.1` | `c3b0a46` | Manuscript freeze | **DO NOT MOVE** |

### 7.2 Where should cleanup work happen?

**Recommended:** new branch `chore/repo-cleanup-and-throughput` forked from `feature/gap-e-beta2-implementation` HEAD (`2c82f42`).

Reason:
- Cleanup needs the same baseline as Gap E (we're inspecting the same dirty files).
- Forking from `2c82f42` (not from `main-v2.4-refactor`) inherits the BETA-2b implementation context — useful if cleanup touches anything BETA-2b-adjacent.
- Cleanup is BETA-2b-orthogonal: no plan-version bump, no manuscript impact.

### 7.3 Where should throughput config changes happen?

**Same branch** (`chore/repo-cleanup-and-throughput`). Lever C is a 1-line config change with smoke. Lever A is a separate orchestrator script (additive, NOT modifying production code) — also fits.

If Lever B1 (drop `--enforce-eager`) is adopted, it goes on this branch too.

### 7.4 Final delivery

**Recommended:** treat `chore/repo-cleanup-and-throughput` as a **review-only branch** until Gap E verdict closes:

1. PI gives Q1/Q2/Q3 verdict.
2. If `Q1 = Yes` → adopt BETA-2b + create `release/paper-integration-v0.2` branch from `feature/gap-e-beta2-implementation`. Cherry-pick cleanup commits onto `release/paper-integration-v0.2`. Tag `paper-integration-v0.2`.
3. Then cleanup branch + paper-integration-v0.2 fast-forward into `main-v2.4-refactor` (or the agreed mainline).
4. Eventually `main-v2.4-refactor` → `master` reconciliation (separate concern).

If `Q1 = No / Defer` → cleanup branch can still merge into `main-v2.4-refactor` independently (it's BETA-2b-orthogonal). PI can decide timing.

### 7.5 Tag strategy

- `paper-integration-v0.1` stays at `c3b0a46` (DO NOT MOVE).
- `paper-integration-v0.2` created **only after Q1=Yes verdict + Plan v1.3.4 + manuscript-impact PR + reviewer pass**.
- Cleanup work does NOT need its own tag.

### 7.6 Recommended action (branch strategy summary)

1. Create `chore/repo-cleanup-and-throughput` from `2c82f42`.
2. Land 8 SAFE NOW items in 2 mini-PRs (hygiene PR + perf+throughput PR).
3. Hold merge until Gap E verdict.
4. Merge after, into the agreed mainline (`main-v2.4-refactor` first, then onward).

---

## Appendix — Summary table (≤30 lines)

| Item | Verdict | Action |
|---|---|---|
| `configs/vllm_awq.yaml` | orphan dirty (1-line `context_window`) | revert or commit standalone |
| `src/culturedx/retrieval/case_retriever.py` | legitimate perf opt (BGE-M3 singleton) | smoke + commit standalone |
| Untracked tarballs | 61 files, ~900 KB | archive or delete |
| Untracked zips | 3 files | archive or delete |
| Scratch root .md | 3 files (1 dup, 2 handoffs) | delete dup, move handoffs |
| `v2.5_rebase/` | 412K, superseded | archive or delete |
| `scripts/generalization/replay_cached_checkers.py` | active uncommitted code | commit on generalization branch |
| Legacy `paper/` | stale, `docs/paper/` is canonical | migrate `.tex` + `.bib`, delete prose, archive tables |
| USAGE_AUDIT subdirs | all 14 USED or SANDBOX-with-consumers | no cuts |
| Lever A (3-mode parallel) | 1.8–2.3× speedup | wait — adopt after Gap E verdict |
| Lever B1 (drop `--enforce-eager`) | 1.3–1.5× speedup, reproducibility risk | wait — adopt after V3 decision |
| Lever B2 (`--max-num-seqs`) | marginal | skip unless C/A bottlenecks shift |
| Lever C (`max_concurrent` 16→32/64) | 1.5–2× speedup, low risk | **do first** |
| SAFE NOW count | 8 items | 2 mini-PRs on new chore branch |
| WAIT LATER count | 5 items | hold until verdict / workstream resumption |
| Branch strategy | `chore/repo-cleanup-and-throughput` from `2c82f42` | review-only until Gap E closes |

---

## Hard-constraint compliance verification

- ✅ Did NOT modify any file other than this audit doc
- ✅ Did NOT commit or push
- ✅ Did NOT modify `configs/vllm_awq.yaml`
- ✅ Did NOT modify `src/culturedx/retrieval/case_retriever.py`
- ✅ Did NOT modify any frozen plan / sandbox / audit / simulation / PI summary
- ✅ Did NOT modify manuscript drafts (§1–§7, Abstract, Table 4)
- ✅ Did NOT touch `hied.py` / `calibrator.py` / `comorbidity.py` / production code
- ✅ Did NOT move `paper-integration-v0.1` tag
- ✅ Did NOT merge any branch
- ✅ Did NOT create any new branch
- ✅ Did NOT run GPU
- ✅ Did NOT regenerate predictions or metrics
- ✅ Did NOT decide adoption questions Q1/Q2/Q3 (user's call)

**Audit ends. Hand back to user for review.**
