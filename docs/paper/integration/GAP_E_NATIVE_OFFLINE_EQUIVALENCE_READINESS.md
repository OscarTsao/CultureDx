# Gap E Native Offline Equivalence Readiness Probe — Round 131a

**Status:** Read-only investigation. NO file write to production code. NO commit. NO push. NO GPU. NO vLLM. Only output: this audit report (staged uncommitted).
**Source HEAD:** `ae413c4` on `feature/gap-e-beta2-implementation`
**Frozen tag:** `paper-integration-v0.1 → c3b0a46`
**Frozen main:** `origin/main-v2.4-refactor → 3d5e014`
**Predecessors:** Round 130 commits A+B at `b1c4474` (BETA-2b feat) + `ae413c4` (BETA-2b smoke audit)
**Authorization:** Round 131a read-only readiness probe per Round 131 verdict, before deciding whether/how to run Round 131b native offline equivalence audit.

---

## 1. Scope and non-execution status

This probe is read-only. It reports whether the BETA-2b production code path can be applied to the 5775 cached canonical records (Round 114) without GPU, vLLM, or new LLM inference. Three feasibility classes are evaluated: A (READY), B (SMALL REFACTOR NEEDED), C (LARGE HARNESS NEEDED), D (NOT POSSIBLE / NOT WORTH IT).

NO production code modified. NO commits. NO pushes. NO GPU. NO vLLM. NO tag movement.

---

## 2. HEAD / workspace status

| Check | Expected | Observed |
|---|---|---|
| Branch | `feature/gap-e-beta2-implementation` | ✓ |
| HEAD | `ae413c4` (after Round 130 commits A+B) | `ae413c4` ✓ |
| Round 130 Commit A in log | `b1c4474 feat(hied): add BETA-2b...` | ✓ present |
| Round 130 Commit B in log | `ae413c4 docs(paper): audit BETA-2b native smoke` | ✓ present |
| Tag `paper-integration-v0.1` | `c3b0a46` (frozen) | `c3b0a46` ✓ |
| `origin/main-v2.4-refactor` | `3d5e014` (frozen) | `3d5e014` ✓ |
| Pre-existing dirty (out of scope) | `configs/vllm_awq.yaml` + `case_retriever.py` | both present, both untouched ✓ |

No unexpected dirty tracked files. Probe proceeds.

---

## 3. Production BETA-2b code path

### Final-output override block

Located at `src/culturedx/modes/hied.py:1474-1479`:

```python
        # BETA-2b feature flag: lock primary to diagnostician_ranked[0] always
        # (Plan v1.3.2 §3 design lock #1; bypasses veto/fallback above)
        if self.final_output_policy == "beta2b_primary_locked" and top_ranked:
            primary = top_ranked[0]
            veto_applied = False
            primary_source = "beta2b_locked"
```

This is an **inline conditional block inside `HiEDMode._diagnose_dtv()` (or equivalent DtV pathway method)**. It is NOT a pure standalone helper.

### Schema-version override

Located at `src/culturedx/pipeline/artifacts.py:140-145`:

```python
    schema_v = ARTIFACT_SCHEMA_VERSION
    dt = result.decision_trace or {}
    if isinstance(dt, dict) and dt.get("final_output_policy") == "beta2b_primary_locked":
        schema_v = "v2b"
```

This IS already a pure utility within `build_prediction_record()` — it can be invoked on any cached `decision_trace` dict to re-derive the schema_version field.

### Decision-trace field stamping

Located at `src/culturedx/modes/hied.py:1587`:

```python
                "audit_comorbid": audit_comorbid,
                "final_output_policy": self.final_output_policy,
```

This is also inline inside the DtV emission's decision_trace dict construction.

### Constructor/storage path

`src/culturedx/modes/hied.py:83` (constructor param), `src/culturedx/modes/hied.py:103` (`self.final_output_policy = final_output_policy`).
`src/culturedx/pipeline/cli.py:168, 392` (CLI plumbing through `cfg.mode.final_output_policy`).
`src/culturedx/core/config.py:58` (ModeConfig field, default `"default"`).

### Can the BETA-2b transform be called on cached records without LLM?

**Direct answer: NO** — the BETA-2b override block at line 1476-1479 is reachable only after a full DtV pass (diagnostician + 14 checkers + logic engine + comorbidity resolver). The current code requires the entire upstream chain to execute before the BETA-2b override fires.

**However**, the BETA-2b transform itself is trivial (4 lines, pure logic over `top_ranked` and `final_output_policy`). It depends only on:
- `top_ranked` (= `decision_trace.diagnostician_ranked`, available in cached records)
- `self.final_output_policy` (= config flag)

So the transform CAN be applied to any cached prediction record IF extracted into a pure helper.

---

## 4. Existing harness / helper inventory

### Cached-checker harness (most relevant)

`scripts/generalization/replay_cached_checkers.py` — designed for "DtV verify phase reusing cached non-top-k checker outputs". Loads `decision_trace.raw_checker_outputs` into per-(case, disorder) cache and injects into `HiEDMode`. **Currently configured for partial caching (only non-top-k), not 100% bypass.**

Per its docstring: "force real checker calls for the DtV verify phase (top-k codes), but reuse cached non-top-k checker outputs". So it's NOT a full LLM-bypass harness; it still requires GPU for top-k checker calls.

### Mock LLM in tests

`tests/test_hied_mode.py:21-37` defines `FakeLLM` class:

```python
class FakeLLM:
    def __init__(self, responses: list[str] | None = None): ...
    def generate(self, prompt: str, **kwargs) -> str: ...
    def compute_prompt_hash(self, template_source: str) -> str: ...
```

Used in unit tests. Could in principle be extended to a record-replayer (read existing decision_trace, return canned responses). However, the LLM-call sequence in `HiEDMode.diagnose()` is non-trivial (1 diagnostician call + 14 checker calls + retrieval) and the order matters for response selection. Building a full record-replayer would be **moderate engineering work**.

### Round 120 CPU projection script

`scripts/sandbox/cross_dataset_replay.py` implements the BETA-2b CPU projection used in Round 120 (`a960616`). This is a **standalone projection script** — it does NOT call the production code path. It manually applies `primary = ranked[0]` etc. transforms to records.

### Other replay scripts

- `scripts/replay_others_fallback.py` — single-purpose Others-class fallback replay
- `scripts/t1_comorbid_cap_replay.py` — comorbid-cap policy replay (different scope)
- `scripts/sandbox/stage_L1_replay.py` — L1 deterministic rule replay (sandbox-internal)

None of these are a full LLM-bypass production-code harness.

### Verdict on harness existence

**No reusable production-native cached-record harness exists.** The closest is `replay_cached_checkers.py` (partial, requires GPU for top-k) and `FakeLLM` in tests (mock for unit-style calls, not record-replayer). Building a full harness is moderate work (~1-2 days).

---

## 5. Feasibility classification

**B. SMALL REFACTOR NEEDED.**

The production BETA-2b override is currently inline at `hied.py:1474-1479` (4 lines) and `hied.py:1587` (1 decision_trace field). To run native offline equivalence on the 5775 cached records WITHOUT mocking the entire HiED inference graph, the cleanest path is:

1. Extract BETA-2b finalization into a pure module-level (or static method) helper:

   ```python
   def apply_beta2b_finalization(
       primary: str | None,
       top_ranked: list[str],
       final_output_policy: str,
   ) -> tuple[str | None, bool, str]:
       """Apply BETA-2b primary-lock if policy active. Returns (primary, veto_applied, primary_source)."""
       if final_output_policy == "beta2b_primary_locked" and top_ranked:
           return top_ranked[0], False, "beta2b_locked"
       return primary, ..., ...   # caller's existing values
   ```

2. Replace the inline block at `hied.py:1474-1479` with `primary, veto_applied, primary_source = apply_beta2b_finalization(primary, top_ranked, self.final_output_policy)`.
3. Round 131b can then call `apply_beta2b_finalization` on each cached canonical record (loading `decision_trace.diagnostician_ranked` as `top_ranked`, `predictions.primary_diagnosis` as `primary`) and produce native-equivalent output for all 5775 records, CPU-only.

Refactor scope: 1 file (`hied.py`), ~10-15 lines moved (no behavior change). This is a Small refactor in the strictest sense — pure extraction with no semantic change.

**Why not class A (READY)**: The override block is currently inline. There is no existing helper that can be invoked on a cached record dict. The CPU projection script in `scripts/sandbox/cross_dataset_replay.py` does NOT call production code.

**Why not class C (LARGE HARNESS NEEDED)**: We do NOT need to mock the full HiED inference graph. BETA-2b finalization is a trivial post-processing step that operates on already-known fields (primary + diagnostician_ranked). No LLM, no checker, no logic-engine state needed at the helper level.

**Why not class D (NOT POSSIBLE / NOT WORTH IT)**: The native offline equivalence audit IS a meaningfully different validation from Round 120 CPU projection: it tests that the **production helper** (when we extract it) produces identical output to the standalone projection script. This catches accidental divergence between the two implementations.

### Assessment of marginal information value

That said: BETA-2b finalization is so trivial (`primary = ranked[0]` plus 2 metadata fields) that the marginal information from native equivalence over CPU projection is small. The Round 128 V1 smoke already demonstrated 120/120 invariants pass on production-native execution. The Round 120 CPU projection demonstrated 5775/5775 invariants pass on the projection.

Native offline equivalence at full N=5775 would close the loop by showing native helper output ≡ projection output, but the residual risk being mitigated is "production helper drifted from projection script logic" — which is bounded since both are reading the same source-of-truth fields.

**Conservative recommendation**: Round 131b is worth doing as a small refactor + 1-shot equivalence verification, but it should be sized as a 30-60 min effort, not a 1-2 day cached-inference harness build.

---

## 6. Stacker dependency re-check

| Field | Read by stacker? | Modified by BETA-2b? |
|---|---|---|
| `primary_diagnosis` | NO (post-emission, used for evaluation only) | YES (set to `ranked[0]`) |
| `comorbid_diagnoses` | NO (post-emission) | YES (forced `[]`) |
| `audit_comorbid` | NO (new field, post-emission) | YES (preserved from BETA-2 patch) |
| `decision_trace.diagnostician_ranked` | YES (5 DtV rank confidences) | NO (preserved) |
| `decision_trace.raw_checker_outputs.met_ratio` | YES (12 checker met_ratios) | NO (preserved) |
| `tfidf_top1_margin` (TF-IDF baseline output) | YES | NO (separate pipeline) |
| `dtv_abstain_flag` | YES | NO (BETA-2b override does NOT set abstain) |

Per Plan v1.3.2 §7 + Round 118 CHECK B + Round 128 V1 smoke verification:

**Stacker retrain verdict: NOT NEEDED.** All 31-feature schema sources upstream of the BETA-2b override block are preserved verbatim. BETA-2b only changes `primary_diagnosis`, `comorbid_diagnoses` (forced empty), `audit_comorbid` (preserved), `schema_version` (bumped to v2b), and `decision_trace.{final_output_policy, audit_comorbid, veto_applied, primary_source}` — none of which are stacker inputs.

Code evidence: `grep -B2 -A6 "beta2b_primary_locked" src/culturedx/modes/hied.py:1476` shows override block touches only `primary`, `veto_applied`, `primary_source`. Lines 1474-1479 do NOT reference `raw_checker_outputs`, `met_ratio`, `diagnostician_ranked` (read-only here), `tfidf`, or `abstain`.

---

## 7. Recommended next trigger

**Round 131b (conditional on user approval): Small refactor + 1-shot native offline equivalence**.

```
Round 131b — BETA-2b native offline equivalence (small refactor + cached run).

Step 1: Extract apply_beta2b_finalization helper from hied.py:1474-1479 into pure module-level
        function (no behavior change). Verify py_compile + V2 default smoke regression test passes.

Step 2: Apply helper to all 5775 cached BETA-2a canonical records (Round 114, results/gap_e_canonical_20260429_225243/).
        Compare output byte-for-byte against Round 120 CPU projection (results/gap_e_beta2b_projection_20260430_164210/).

Step 3: Verdict + audit report.

Estimated effort: 30-60 min.
NO GPU. NO vLLM. NO new LLM inference.
```

**Alternative: Skip Round 131b entirely** and accept that:
- Round 120 CPU projection demonstrates BETA-2b semantics on 5775 records
- Round 128 V1 native smoke demonstrates BETA-2b production-native execution on 120 records (98.3% bit-equivalent to projection, 100% invariant pass)
- Combined evidence is sufficient for Plan v1.3.X amendment to acknowledge BETA-2b as canonical-equivalent

This skips the marginal information from full-N native equivalence in exchange for not touching production code (helper extraction).

**Plan-level decision**: refactor + verify (A) vs accept-as-is (B). Recommend A for narrative cleanliness; B is acceptable if PI prefers no further code touch.

---

## 8. Files not touched in this probe

- `src/culturedx/modes/hied.py` ✓
- `src/culturedx/core/config.py` ✓
- `src/culturedx/pipeline/cli.py` ✓
- `src/culturedx/pipeline/artifacts.py` ✓
- `src/culturedx/diagnosis/calibrator.py` ✓
- `src/culturedx/diagnosis/comorbidity.py` ✓
- `docs/paper/drafts/` ✓
- `docs/paper/repro/REPRODUCTION_README.md` ✓
- `results/analysis/metric_consistency_report.json` ✓
- `docs/paper/integration/Plan_v1.3_GapE.md` ✓
- `docs/paper/integration/Plan_v1.3.2_BETA2b_Patch.md` ✓
- `docs/paper/integration/GAP_E_CANONICAL_RUN_REVIEW.md` ✓
- `docs/paper/integration/GAP_E_BETA2B_PROJECTION_AUDIT.md` ✓
- `docs/paper/integration/GAP_E_BETA2B_NATIVE_SMOKE_AUDIT.md` ✓
- `paper-integration-v0.1` tag (frozen at `c3b0a46`) ✓
- `origin/main-v2.4-refactor` (frozen at `3d5e014`) ✓
- No tag movement, no commit, no push, no GPU, no vLLM load
- Pre-existing dirty `configs/vllm_awq.yaml` + `case_retriever.py` untouched ✓

---

## End of probe

Single output: this report at `docs/paper/integration/GAP_E_NATIVE_OFFLINE_EQUIVALENCE_READINESS.md`. Staged in working tree, UNCOMMITTED for user review.

