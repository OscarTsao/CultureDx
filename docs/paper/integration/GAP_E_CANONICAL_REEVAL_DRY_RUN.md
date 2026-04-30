# Gap E Canonical Re-Evaluation — Dry-Run Readiness Report

**Status:** Read-mostly dry-run. Single new uncommitted file. Plan v1.3 §8 Gate 8.3 preflight only.
**Source HEAD:** `3d5e014` (`docs(paper): plan logic-engine final-output redesign`)
**Frozen tag:** `paper-integration-v0.1 → c3b0a46` (NOT moved)
**Author context:** CultureDx round 110, Plan v1.3 Gap E preflight gate
**Authorization:** Plan v1.3 §6 production-code gate and §7 manuscript-impact gate are NOT cleared. This dry-run does NOT modify production code, does NOT commit, does NOT push, does NOT load the LLM, and does NOT start vLLM server.

---

## 1. Scope and non-execution status

This dry-run is a Plan v1.3 §8 Gate 8.3 preflight inspection. It does the following:

- Reads Plan v1.3 (`docs/paper/integration/Plan_v1.3_GapE.md`, 313 lines, 10 sections) and `LOGIC_ENGINE_FINAL_OUTPUT_SANDBOX_REPORT.md` (455 lines, 13 sections) in full
- Inspects (read-only) `src/culturedx/modes/hied.py`, `src/culturedx/diagnosis/{calibrator,comorbidity,logic_engine}.py`, `src/culturedx/eval/lingxidiag_paper.py`, `scripts/stacker/eval_stacker.py`
- Samples first-record schema of all 6 canonical prediction files
- Lightweight GPU readiness check (`nvidia-smi`, `torch.cuda.is_available()`, `vllm` import — no model load)
- Surfaces R3-β implementation ambiguity between sandbox-as-implemented and Plan v1.3 §3 design lock

It does NOT:

- Modify any production code
- Commit, push, or move the `paper-integration-v0.1` tag
- Run any LLM inference
- Train or retrain the stacker
- Load Qwen3-32B-AWQ or start a vLLM server
- Use `git add .` or `git add -A`

The single file produced is this report at `docs/paper/integration/GAP_E_CANONICAL_REEVAL_DRY_RUN.md`. It is left uncommitted for user review.

---

## 2. HEAD / workspace preflight

| Check | Expected | Observed |
|---|---|---|
| HEAD | ≥ `3d5e014` | `3d5e014` ✓ |
| Branch | `main-v2.4-refactor` | `main-v2.4-refactor` ✓ |
| Tag `paper-integration-v0.1` commit | `c3b0a46` (frozen) | `c3b0a46` ✓ |
| Tracked-file dirty (allowed only the 2 pre-existing) | `configs/vllm_awq.yaml` + `src/culturedx/retrieval/case_retriever.py` | both present, no others ✓ |
| Untracked tracked under `src/`, `docs/paper/drafts/`, `results/analysis/` | none | none ✓ |

Pre-existing dirty files are out of scope and will NOT be staged by any Gap E commit. No tracked code under `src/culturedx/modes/` or `src/culturedx/diagnosis/` is dirty.

---

## 3. Planning-artifact alignment

### Plan v1.3 §3 design lock — verbatim 6 clauses

```
1. Diagnostician rank-1 = benchmark primary.
2. Diagnostician original ranking = Top-k differential.
3. Checker = audit trace, evidence explanation, uncertainty signal.
4. Checker does not freely rerank or override primary.
5. Comorbidity annotations live in a separate field, not in the benchmark prediction set.
6. Benchmark prediction set is primary-only (single-label).
```

### Plan v1.3 stop-decisions (binding immediately)

- ⛔ checker free primary override (current pipeline behavior; net −17 Top-1)
- ⛔ checker rank 2-5 reranking by met_ratio / decisive / composite
- ⛔ checker conservative veto under any tested margin / decisive threshold
- ⛔ DtV-rerank-by-checker (Top-1 collapse to 0.3110)
- ⛔ forced single-label EM via current-primary keep (Rule H; Pareto-dominated by Rule K)

### Sandbox §7 recommended design lock (verbatim)

```
1. Benchmark primary prediction = Diagnostician rank-1 (locked, no override)
2. Top-k differential = Diagnostician original ranking (no checker rerank)
3. Checker = audit trace + per-criterion evidence + uncertainty signal
            (NOT a ranking authority)
4. Comorbidity = SEPARATE annotation field, NOT in benchmark prediction set
5. Benchmark EM uses primary-only single-label prediction
6. Audit output preserves checker traces and conservative annotations
```

The Plan v1.3 §3 design lock and the sandbox §7 design lock are mutually consistent. Both lock benchmark = primary-only, single-label.

---

## 4. Current final-output code path

Read-only inspection results:

| Stage | File | Line range | Function / role |
|---|---|---|---|
| Diagnostician rank-1 selection (DtV path) | `src/culturedx/modes/hied.py` | ~1330-1372 | primary derivation from confirmed_set / top_ranked / fallback chain |
| Logic engine evaluate | `src/culturedx/modes/hied.py` | 1318-1322 | `self.logic_engine.evaluate(...)` → `confirmed_set = set(logic_output.confirmed_codes)` |
| Comorbidity gate | `src/culturedx/modes/hied.py` | 1423, 1440, 1447 | `comorbid = comorbidity_result.comorbid` → `comorbid_diagnoses=comorbid` |
| ComorbidityResolver | `src/culturedx/diagnosis/comorbidity.py` | class `ComorbidityResolver`, method `resolve` | confirmed-set → primary + up-to-3 comorbids; uses ICD-10 forbidden-pair logic |
| Comorbid threshold | `src/culturedx/modes/hied.py` | 70, 192 | `comorbid_threshold: float = 0.5` (HiED constructor parameter) |
| DiagnosisResult final emission | `src/culturedx/modes/hied.py` | 1444-1461 | `DiagnosisResult(primary_diagnosis=primary, comorbid_diagnoses=comorbid, ...)` + decision_trace serialization |
| Diagnostician_ranked serialization | `src/culturedx/modes/hied.py` | 1461 | `"diagnostician_ranked": ranked_codes` written into decision_trace |
| Both-mode merge | `src/culturedx/modes/hied.py` | 253 (`_merge_dual_standard_results`) | attaches DSM-5 result as sidecar on ICD-10 primary |

The single chokepoint where BETA-1 vs BETA-2 differs is at **line 1447** — what gets passed to `comorbid_diagnoses` field of the DiagnosisResult.

---

## 5. Current prediction schema

All 6 canonical prediction files share `schema_version: "v1"` with identical top-level field set:

```
schema_version, run_id, case_id, order_index, dataset, gold_diagnoses,
primary_diagnosis, reasoning_standard, dsm5_criteria_version,
primary_diagnosis_icd10, primary_diagnosis_dsm5, dual_standard_meta,
comorbid_diagnoses, confidence, decision, mode, model_name, prompt_hash,
language_used, routing_mode, scope_policy, candidate_disorders,
decision_trace, stage_timings, failures
```

`decision_trace` (audit-only, NOT consumed by v4 eval contract) contains:

```
candidate_disorders, diagnostician, diagnostician_ranked,
diagnostician_reasoning, dtv_mode, [dual_standard for both-mode],
evidence_failures, logic_engine_confirmed_codes, raw_checker_outputs,
routing_mode, scope_policy, triage, verify_codes,
veto_applied, veto_from, veto_to
```

| Channel | Field | Currently consumed by v4 eval contract? |
|---|---|---|
| Benchmark primary | `primary_diagnosis` | YES — Top-1, Top-3 (with ranked), 2c, 4c |
| Benchmark multilabel | `comorbid_diagnoses` | YES — multilabel predicted set for EM, F1_macro, F1_weighted |
| Audit | `decision_trace.*` | NO — audit-only |

**No existing field separates "benchmark comorbid" from "audit comorbid"**. They are co-located in `comorbid_diagnoses`. BETA-2 implementation requires introducing a NEW field (e.g., `comorbid_annotations` or `audit_comorbid`) and a corresponding `schema_version` bump (`"v1"` → `"v2"`).

---

## 6. R3-β implementation ambiguity and recommendation (BETA-1 vs BETA-2)

### 6.1 Two non-equivalent interpretations

| Aspect | BETA-1 (benchmark-output) | BETA-2 (audit-annotation) |
|---|---|---|
| `comorbid_diagnoses` field semantics | strict-gated comorbid (decisive ≥ 0.85, dominance, criterion A, in-confirmed) | **always `[]`** in benchmark |
| New audit-only field | none | NEW `comorbid_annotations` carries strict-gated candidates |
| Benchmark Top-1 | = R3-α | = R3-α (identical) |
| Benchmark Top-3 | = R3-α | = R3-α (identical) |
| Benchmark EM | distinct from R3-α (sandbox: 0.288 vs 0.469 LingxiDiag ICD-10) | = R3-α (0.469) |
| Benchmark mF1 / wF1 | distinct from R3-α | = R3-α |
| Schema compatibility | `schema_version: "v1"` (no field added) | `schema_version` bump to `"v2"` (new field) |
| Stacker feature semantics | unchanged (features upstream) | unchanged (features upstream) |
| Plan v1.3 §3 design lock #6 alignment | **Conflicts** — design lock says benchmark = primary-only single-label | **Consistent** — design lock satisfied verbatim |

### 6.2 Sandbox-as-implemented evidence (BETA-1)

Sandbox `LOGIC_ENGINE_FINAL_OUTPUT_SANDBOX_REPORT.md §8.3` reports for R3-β:

| Mode | Top-1 | EM | mF1 | multi_emit |
|---|---:|---:|---:|---:|
| LingxiDiag-16K × ICD-10 | 0.5240 | 0.2880 | 0.1863 | 0.4170 |
| LingxiDiag-16K × DSM-5 | 0.5300 | 0.3990 | 0.2124 | 0.2300 |
| MDD-5k × ICD-10 | 0.6043 | 0.2411 | 0.2229 | 0.5914 |
| MDD-5k × DSM-5 | 0.5881 | 0.1373 | 0.2499 | 0.7546 |

`multi_emit` columns are non-zero (0.23-0.75), proving sandbox R3-β emits comorbid into the benchmark prediction set. **Sandbox R3-β = BETA-1.** The R3-β EM column (0.14-0.40) is distinct from R3-α EM column (0.47-0.56), confirming benchmark-level distinction.

### 6.3 Plan-v1.3-as-locked evidence (BETA-2)

Plan v1.3 §3 design lock clause #6 verbatim (line 97 of `Plan_v1.3_GapE.md`):

> "Benchmark prediction set is primary-only (single-label)."

Sandbox §7 recommended design lock clauses 4 and 5 (lines 186-187 of sandbox report):

> "4. Comorbidity = SEPARATE annotation field, NOT in benchmark prediction set"
> "5. Benchmark EM uses primary-only single-label prediction"

Both Plan v1.3 and the sandbox's own §7 recommendation lock BETA-2.

### 6.4 The critical contradiction

The §4 candidate policies table in Plan v1.3 (line 126) cites R3-β as having `EM = 0.2880, mF1 = 0.1863` on LingxiDiag ICD-10. **These numbers are sandbox BETA-1 numbers**. Under BETA-2 (which the design lock mandates), R3-β collapses to R3-α at the benchmark level (EM = 0.4690, mF1 = 0.1814). The mF1 advantage R3-β shows over R3-α in §8.6 / §8.7 of the sandbox ("R3-β preserves or improves mF1 in 3 of 4 modes") is **BETA-1-only** — it does not exist under BETA-2.

In other words: under the design lock as written, R3-β is functionally identical to R3-α at the benchmark level. The sandbox's "R3-β is the more defensible policy" verdict (sandbox §8.7 bottom line) is conditional on BETA-1.

### 6.5 Recommendation

**AMBIGUOUS — requires Plan v1.3.1 amendment before any code change.**

The contradiction is not resolvable by code-level inspection alone. Two coherent paths exist:

- **Path AMBIGUOUS-A (Plan v1.3.1 relaxes design lock #6 → adopt BETA-1)**:
  - Amend §3 clause #6 to: "Benchmark prediction set may include strict-gated comorbid annotations under R3-β." 
  - Amend §4 to clarify that R3-β is BETA-1 (multi_emit > 0 in benchmark)
  - The §5.4 manuscript narrative becomes: "single-label benchmark for R3-α; strict multi-label benchmark for R3-β; PI selects one"
  - Sandbox §8 numbers carry through as canonical predictions

- **Path AMBIGUOUS-B (Plan v1.3 §3 stays; canonical R3-β = BETA-2)**:
  - R3-β is implemented as benchmark-primary-only + new `comorbid_annotations` audit field
  - Benchmark metrics for R3-β ≡ R3-α
  - The "R3-β > R3-α on mF1" claim is REMOVED from candidate policy comparison
  - Sandbox §4 / §8.6-8.7 rationale for R3-β vs R3-α (cross-mode mF1 stability) collapses; the actual policy choice becomes R3-α-or-not (single binary), with R3-β surviving only as an audit-richness preference
  - Schema bumps to `"v2"` with new field

Either path is internally coherent. Picking between them is a Plan-level decision, not an engineering-level decision. Plan v1.3.1 must specify which.

---

## 7. Stacker retrain audit

### Source-field mapping for 18 MAS-derived stacker features

| Feature group | Count | Source field in `predictions.jsonl` | Affected by BETA-1? | Affected by BETA-2? |
|---|---:|---|:---:|:---:|
| Per-disorder met_ratios | 12-14 (per active scope) | `decision_trace.raw_checker_outputs[i].met_ratio` | NO | NO |
| DtV diagnostician ranked codes | up to 5 | `decision_trace.diagnostician_ranked` | NO | NO |
| DtV reasoning | 1 | `decision_trace.diagnostician.reasoning` | NO | NO |
| Abstain flag | 1 | `decision == "abstain"` or stage-gate trace | NO | NO |

All 18 MAS-derived feature sources are computed UPSTREAM of the comorbid emission stage (line 1447 in `hied.py`). BETA-1 and BETA-2 both modify only what gets serialized to `comorbid_diagnoses` — they do NOT change `decision_trace.raw_checker_outputs`, `diagnostician_ranked`, or the abstain flag.

### Verdict

**stacker retrain NOT needed** under either BETA option (purely from a feature-source-changed perspective).

**However, two upstream blockers remain regardless of this verdict:**

1. **Stage 0 §4 finding (commit `0007d22`)**: stacker training infrastructure is missing in this clone (`scripts/stacker/train_stacker.py` absent, `outputs/stacker/stacker_lgbm.pkl` absent, `outputs/stacker_features/test_final/features.jsonl` absent, hyperparameter config and frozen seed undocumented). Even if retrain were needed for some reason, it is blocked at Stage 0.
2. **Stacker LR / LGBM canonical numbers** in `metric_consistency_report.json` would technically be unchanged after Gap E because their predictions don't move. But §5.4 Table 4 needs to be regenerated for HiED rows (which DO change), and the stacker rows can be left at the existing canonical values without recompute.

---

## 8. GPU readiness

| Check | Result |
|---|---|
| `nvidia-smi` | OK — `NVIDIA GeForce RTX 5090`, 31.3 GB VRAM, driver 580.126.09, CUDA 13.0 |
| `torch.cuda.is_available()` | `True` |
| Device | `NVIDIA GeForce RTX 5090` |
| VRAM | 31.3 GB (Qwen3-32B-AWQ ~20 GB; budget OK with KV cache) |
| `vllm.__version__` | `0.17.1` |
| Existing GPU consumers (idle) | Xorg + gnome-shell ≈ 250 MiB; baseline ~664 MiB available headroom |

GPU is ready. NO model loaded. NO vLLM server started. NO inference performed.

---

## 9. Proposed smoke-test plan (NOT executed)

Smoke-test phase per Plan v1.3 §8 Gate 8.3 + sandbox §11.

### 9.1 Pre-execution gates (must clear in order)

- Gate 8.1: PI / advisor verdict on Gap E scope — **NOT cleared**
- Plan v1.3.1 amendment to disambiguate BETA-1 vs BETA-2 — **NOT drafted** (this dry-run identifies the requirement)
- Gate 8.2: Policy preregistration — **NOT done**

### 9.2 hied.py modification scope (per ONE recommended option, deferred until Plan v1.3.1)

If BETA-1 (after Plan v1.3.1-A):
- Modify line 1447 region: insert strict-gate filter on `comorbid` before assignment
- Gate parameters: `decisive ≥ 0.85`, ICD-10 dominance, criterion A in `met_status`, code in `confirmed_set`
- File scope: `src/culturedx/modes/hied.py` only

If BETA-2 (after Plan v1.3.1-B):
- Modify line 1447: assign `comorbid_diagnoses=[]` for benchmark
- Add new audit field: `comorbid_annotations=<strict-gated list>`
- Bump `schema_version` to `"v2"` in DiagnosisResult and prediction-record writer
- Update v4 eval contract to consume `comorbid_diagnoses` only (already does this; no change to eval needed)

Branch hygiene: feature branch off `3d5e014` (now `df05637+1`), not direct to `main-v2.4-refactor`.

Rollback plan: revert single commit; canonical state restores.

### 9.3 Smoke-test phase (only after Gate 8.2)

- N=20 cases per dataset/mode (e.g., first 20 by case_id within each `case_selection.json`)
- 6 runs total = 6 × 20 = 120 LLM-case completions
- Estimated runtime: ~30 min on RTX 5090 with Qwen3-32B-AWQ
- Output directory: `results/sandbox/gap_e_smoke_test_YYYYMMDD_HHMMSS/`

Fail-loud criteria for smoke:

- Top-1 deviates > 5pp from sandbox prediction for the chosen option (Top-1 LingxiDiag ICD-10 expected ≈ 0.524 under both options)
- EM directional change inconsistent with the chosen option:
  - BETA-1 R3-β: expect EM ≈ 0.288 (LingxiDiag ICD-10) — within ±5pp
  - BETA-2 R3-β: expect EM ≈ 0.469 — within ±5pp (matches R3-α)
- Multi_emit rate inconsistent with the chosen option:
  - BETA-1: expect multi_emit ≈ 0.42 (LingxiDiag ICD-10)
  - BETA-2: expect multi_emit ≈ 0.0
- Schema validation fails (record missing expected fields per chosen `schema_version`)

---

## 10. Proposed full-run plan (NOT executed)

Full-run phase per Plan v1.3 §8 Gate 8.3 — only after smoke passes.

### 10.1 Run matrix

- LingxiDiag-16K × {ICD-10, DSM-5, Both} on N=1000 (canonical)
- MDD-5k × {ICD-10, DSM-5, Both} on N=925 (canonical)
- Total: 6 runs
- Estimated runtime: 1-2 hr on RTX 5090 + Qwen3-32B-AWQ
- Output directory: `results/gap_e_canonical_reval_YYYYMMDD_HHMMSS/`

### 10.2 Metrics to compute

- Top-1, Top-3, exact match (12c set-equality), macro-F1, weighted-F1, Overall
- F32→F41, F41→F32, F41→F32 / F32→F41 ratio (cascade asymmetry)
- F42 recall
- 2-class / 4-class accuracy from raw `DiagnosisCode` (re-derived per v4 contract)
- Comorbidity emission rate (multi_emit)
- Mode_both vs mode_icd10 sidecar pass-through verification (per sandbox §8.2)

### 10.3 Comparison to canonical baseline

- Compare against `results/sandbox/cross_dataset_replay_20260429_121100.json` (current pipeline column + sandbox-predicted columns for chosen option)
- Document convergence / divergence per cell
- Any cell with |Δ Top-1| > 5pp from sandbox prediction triggers a STOP-and-investigate

### 10.4 Fail-loud criteria for full run

- Any prediction file with malformed JSONL (jsonl-decode failure on any line)
- Any case missing `decision_trace`
- Schema diff from chosen option's expected schema (e.g., BETA-2 missing `comorbid_annotations`, or `schema_version` mismatch)
- Top-1 collapse (> 10pp drop on any mode relative to current canonical)

### 10.5 Stacker re-evaluation (only if §7 verdict says NEEDED or UNCERTAIN — not the case here)

NOT NEEDED per §7. If feature semantics had changed, the path would be: locate stacker training infra (currently blocked at Stage 0 §4), retrain on post-Gap-E predictions, regenerate stacker rows in `metric_consistency_report.json`. None of this is required under either BETA option.

---

## 11. Files that would be touched if implementation is approved

Conditional on Plan v1.3.1 + Gate 8.1 + Gate 8.2:

| Path | Touched | Reason |
|---|:---:|---|
| `src/culturedx/modes/hied.py` | YES | comorbid emission gate at line 1447 region |
| `src/culturedx/diagnosis/comorbidity.py` | possibly | only if BETA-1 strict-gate is implemented inside ComorbidityResolver instead of in hied.py |
| Schema-version constants (in `hied.py` or `base.py`) | YES (BETA-2 only) | bump `schema_version` "v1" → "v2" |
| `results/dual_standard_full/.../predictions.jsonl` (×6) | YES | regenerated by canonical re-evaluation |
| `results/dual_standard_full/.../metrics.json` (×6) | YES | regenerated |
| `results/dual_standard_full/.../metrics_summary.json` (×6) | YES | regenerated |
| `results/analysis/metric_consistency_report.json` | YES (manuscript-impact gate) | regenerated; HiED rows change, stacker rows unchanged |
| `docs/paper/drafts/SECTION_5_4*.md` | YES (manuscript-impact gate) | Table 4 numbers + narrative |
| `docs/paper/drafts/SECTION_4*.md` | YES | Methods description of benchmark-vs-audit channel separation |
| `docs/paper/drafts/SECTION_7*.md` | YES | Limitations: design correction framing |
| `docs/paper/repro/REPRODUCTION_README.md` | YES | reference new tag, updated final-output policy |
| `docs/paper/integration/Plan_v1.3.1_GapE_amendment.md` | YES | new file; locks BETA choice |
| `docs/paper/integration/Plan_v1.3_GapE_preregistration.md` | YES | new file; per Plan v1.3 §8 Gate 8.2 |
| New annotated tag `paper-integration-v0.2` | YES | Plan v1.3 §8 Gate 8.6 |

---

## 12. Files that must NOT be touched in dry run

This dry-run respects all Plan v1.3 §6 + §7 prohibitions:

- ✓ `src/culturedx/modes/hied.py` — NOT modified
- ✓ `src/culturedx/diagnosis/calibrator.py` — NOT modified
- ✓ `src/culturedx/diagnosis/comorbidity.py` — NOT modified
- ✓ `src/culturedx/diagnosis/logic_engine.py` — NOT modified
- ✓ `src/culturedx/eval/lingxidiag_paper.py` — NOT modified
- ✓ `docs/paper/repro/REPRODUCTION_README.md` — NOT modified
- ✓ `docs/paper/drafts/*` — NOT modified
- ✓ `results/analysis/metric_consistency_report.json` — NOT modified
- ✓ `docs/paper/integration/Plan_v1.3_GapE.md` — NOT modified (frozen until v1.3.1)
- ✓ `docs/paper/integration/LOGIC_ENGINE_FINAL_OUTPUT_SANDBOX_REPORT.md` — NOT modified
- ✓ `paper-integration-v0.1` tag — NOT moved
- ✓ No git commit, no git push, no GPU full inference, no stacker retrain, no vLLM server start, no model load
- ✓ No sweeping `git add` (this report file is left UNCOMMITTED for user review)

---

## 13. Go / no-go recommendation

**NO-GO at Plan v1.3 §8 Gate 8.3 currently.** The blocking issue is the BETA-1 vs BETA-2 ambiguity identified in §6 of this report.

Specifically:

- **Blocker 1 (Plan-level):** Plan v1.3 §3 design lock clause #6 mandates BETA-2, but Plan v1.3 §4 candidate policy table cites sandbox R3-β numbers that are BETA-1-implementation-specific. The two are mutually inconsistent. Plan v1.3.1 amendment is required to disambiguate.
- **Blocker 2 (Gate-level):** Gate 8.1 (PI sign-off) is not cleared. Gate 8.2 (preregistration) is not started.
- **Non-blocker:** GPU readiness ✓, stacker retrain not needed ✓, code-path scope clear ✓, schema-bump implications clear ✓.

### Recommended next-trigger options

| Trigger | Action | Round 111 candidate |
|---|---|:---:|
| `Go draft Plan v1.3.1-A — relax design lock #6, adopt BETA-1` | Draft amendment file; prerequisite for canonical R3-β-BETA-1 | candidate |
| `Go draft Plan v1.3.1-B — keep design lock #6, adopt BETA-2` | Draft amendment + new schema field spec; prerequisite for canonical R3-β-BETA-2 (= R3-α at benchmark) | candidate |
| `Go draft PI-facing summary of dry-run + ambiguity` | Generate `Plan_v1.3_GapE_PI_summary.md` for PI review (per Plan §9 trigger taxonomy) | candidate |
| `Hold Gap E pending PI verdict on ambiguity` | No-op | candidate |
| `Drop R3-β; preregister R3-α only` | Avoids the ambiguity entirely; R3-α is well-defined under both interpretations | candidate |

### Preferred path (engineering-level recommendation, not a decision)

Path AMBIGUOUS-A (BETA-1) preserves the cross-mode mF1 stability finding that the sandbox §8.7 verdict relies on. But it requires explicitly relaxing Plan v1.3 §3 design lock #6, which means the manuscript narrative around "channel separation" no longer applies cleanly.

Path AMBIGUOUS-B (BETA-2) preserves the design-lock narrative but reduces R3-β to R3-α at benchmark level. The "R3-β better mF1" claim is removed from candidate consideration; R3-β survives only as an audit-richness option (which has no benchmark metric to defend it).

Path "Drop R3-β; preregister R3-α only" sidesteps the ambiguity entirely. Sandbox §11.2 already notes R3-α as the correct choice "if paper priority is EM + Top-1." If PI deprioritizes the cross-mode mF1 stability angle, this path collapses Plan v1.3 to a single-policy preregistration with no BETA confusion.

**No code change is recommended until Plan v1.3.1 (or its functional equivalent) is committed.** This dry-run is the preflight evidence that justifies the amendment requirement.

---

## End of dry-run report

This report is left **UNCOMMITTED** at `docs/paper/integration/GAP_E_CANONICAL_REEVAL_DRY_RUN.md` for user review. To commit:

```bash
git add docs/paper/integration/GAP_E_CANONICAL_REEVAL_DRY_RUN.md
git commit -m "docs(paper): Gap E canonical re-eval dry-run readiness report"
git push origin main-v2.4-refactor
```

(Above `git` block is for user reference; this dry-run does NOT execute it.)

