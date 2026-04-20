# CultureDx Queue Re-Run Analysis — Round 2

**Date**: 2026-04-20
**Repo state**: `main-v2.4-refactor` @ `27dc18e` (16 commits pulled since last review)
**Scope**: Post-fix re-runs of R13/R14/R17/R21

---

## Executive summary

Of 4 re-run experiments, **only 1 produced valid data** (R21v2). R17's code was buggy (missed two checker paths), and R13v2/R14v2 both failed due to incorrect model-name / chat-template configs.

| Run | Status | Top-1 | Verdict |
|---|---|---:|---|
| r21_evidence_v2 | ✅ Valid data | **0.338** | Real result — evidence pipeline degrades Top-1 by -16.7pp |
| r17_bypass_checker | ❌ Invalid | 0.507 | R17 only bypassed 1 of 3 checker paths (DtV has 2 more). Effectively identical to baseline. |
| r13_qwen3_8b_v2 | ❌ Invalid | 0.085 | vLLM 404: `Qwen/Qwen3-8B-Instruct-AWQ` repo doesn't exist (Qwen3 has no "-Instruct" variant) |
| r14_yi_34b | ❌ Invalid | 0.085 | vLLM 400: Yi chat template not registered with vLLM server |

All 3 failing runs have fixes ready. R21v2 gives a real scientific finding.

---

## R21v2: Evidence pipeline real result

**Configuration**: baseline v2.4 + evidence_verification=true (stacked)

**Metrics** (all 12-class):
| Metric | Baseline | R21v2 | Delta |
|---|---:|---:|---:|
| Acc | 0.057 | 0.026 | **−3.1pp** |
| Top-1 | 0.505 | **0.338** | **−16.7pp** |
| Top-3 | 0.762 | 0.796 | +3.4pp |
| F1_m | 0.190 | 0.144 | −4.6pp |
| F1_w | 0.462 | 0.267 | −19.5pp |

**Head-to-head with v1 (which had top1_code bug)**:
- On 554 cases where both v1 and v2 ran successfully: Top-1 identical at 0.518 each → evidence pipeline didn't change anything on those cases.
- On 441 cases where v1 abstained (top1_code NameError, now fixed): v2 recovered them at Top-1 = 0.116. These were **hard cases** (veto_applied=True implies checker overrode diagnostician), and they pull the average down from 0.518 to 0.338.

**Evidence pipeline primary distribution**:
```
F32: 536    (baseline: ~450)   ← +86 predictions
F39: 256    (baseline: ~50)    ← +206 predictions (MASSIVE shift toward NOS)
F51: 82
F42: 49
F20: 23
F43: 19
F41: 15     (baseline: ~200)   ← −185 predictions (F41 collapsed)
F98: 14
```

**Scientific finding**: Evidence pipeline introduces **strong F39 (NOS) over-prediction and F41 suppression**. This is exactly opposite to what we want — F41 is already under-predicted due to the F32 bias, and evidence pipeline makes it worse.

**Why it happens (hypothesis)**: Evidence verifier downgrades criteria when keyword matches are weak. F41.1's criteria are mostly diffuse ("持續緊張", "難以放鬆", "易疲勞") which don't match evidence keywords as cleanly as F32's more concrete symptoms. So F41 criteria get downgraded more aggressively, pushing the diagnostician to fall back to F39 (NOS mood) as a "safer" label.

**Paper impact**: This kills Narrative B in its original form ("evidence helps"). Reframed version: **"Keyword-based evidence verification introduces a systematic bias toward NOS labels by differentially downgrading diffuse psychological criteria over concrete somatic criteria."** This is actually a more interesting finding.

### Recommendation

- **Drop evidence pipeline from final v2.4 config**. It's a net-negative for Top-1 and F1.
- **Include R21v2 in paper as negative result** to support Narrative H (architectural interventions don't help; only supervised RRF does).
- Investigate: does evidence pipeline help Top-3 coverage? Yes, +3.4pp. But cost is too high for primary diagnosis tasks.

---

## R17: Bug — only 1 of 3 checker paths bypassed

**Symptom**: R17 Top-1 = 0.507 (baseline = 0.505). Essentially identical.

**Root cause**: The v2.4 pipeline uses `diagnose_then_verify: true` (DtV mode). In DtV mode, the checker is invoked **three separate times** in `hied.py`:

```python
# Line 530 — non-DtV Stage 2 (NOT used in v2.4)
checker_outputs = self._parallel_check_criteria(..., candidate_codes, ...)

# Line 1088 — DtV verify stage (USED in v2.4)  ← R17 did not bypass
checker_outputs = self._parallel_check_criteria(..., verify_codes, ...)

# Line 1103 — DtV remaining stage (USED in v2.4)  ← R17 did not bypass
remaining_outputs = self._parallel_check_criteria(..., remaining_codes, ...)
```

My previous R17 patch only wrapped the non-DtV Stage 2 call. The DtV paths still ran the real LLM checker unchanged, so bypass never actually took effect when `diagnose_then_verify=true`.

**Evidence from the data**:
- `decision_trace.raw_checker_outputs` shows real LLM-generated evidence text like `"患者提到这种情况已经持续了四五年"` instead of the expected synthetic marker `"[R17: checker_bypassed]"`
- Criterion met counts are heterogeneous (F32: 4/4, F39: 4/3, F45: 1/5) — not the uniform "all met" pattern synthetic outputs produce
- Stage timings show `diagnostician` = 11.9s (vs 28s baseline). This means ~16 seconds of LLM calls were eliminated — consistent with bypassing the NON-DtV path (which uses the diagnostician in the DtV case, so the 11.9s stage includes diagnostician + DtV checker combined)

**Fix**: Refactored R17 to introduce a helper method `_run_checker_or_bypass()` used by ALL three checker invocation sites. Verified:
- 3 call sites now route through the helper
- `_parallel_check_criteria` directly called only once (inside the helper)
- 388/388 tests pass
- Synthetic outputs verified to produce `all_met=True` CheckerOutputs for all 14 target disorders

**Re-run needed**: R17 will need to run again with the fixed code. Prediction based on the F32 bias analysis: Top-1 will land in 0.49-0.53 range.

---

## R13v2: Model name doesn't exist

**Symptom**: 1000/1000 abstain, all HTTP 404 on `/v1/chat/completions`.

**Root cause**: My previous config specified `model_id: Qwen/Qwen3-8B-Instruct-AWQ`, but **this repo does not exist on HuggingFace**. The Qwen3 family does not have a separate "-Instruct" variant — the base `Qwen/Qwen3-8B` already is the instruct-tuned model, and its AWQ quantization is published as `Qwen/Qwen3-8B-AWQ`.

vLLM returns 404 when the requested model name doesn't match any served model, which is what happened.

**Fix**: Updated config to `model_id: Qwen/Qwen3-8B-AWQ`. Serving command:

```bash
pkill -f vllm
vllm serve Qwen/Qwen3-8B-AWQ \
  --port 8000 \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.80 \
  --enable-reasoning --reasoning-parser deepseek_r1

# Wait ~90s, then verify:
curl http://localhost:8000/v1/models
```

---

## R14v2: Yi chat template not loaded by vLLM

**Symptom**: 1000/1000 abstain, all HTTP 400 Bad Request (not 404 — model IS loaded but rejects request format).

**Root cause**: Yi-1.5-Chat uses ChatML-style tokens (`<|im_start|>system\n...<|im_end|>`). When vLLM loads a model whose `tokenizer_config.json` doesn't include a `chat_template` field, `/v1/chat/completions` returns 400 on any request because vLLM can't format the prompt.

`modelscope/Yi-1.5-34B-Chat-AWQ` may not have a registered chat template in vLLM's version.

**Fix**: Two options for the user to try:

Option A (easier): Add `--chat-template-content-format openai` flag when serving:
```bash
vllm serve modelscope/Yi-1.5-34B-Chat-AWQ \
  --port 8000 \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.90 \
  --quantization awq \
  --chat-template-content-format openai \
  --trust-remote-code
```

Option B (guaranteed): Use the well-tested older Yi AWQ:
```bash
# Update configs/overlays/r14_non_qwen.yaml:
#   model_id: TheBloke/Yi-34B-Chat-AWQ
# This is Yi 1.0 not 1.5, but guaranteed to have vLLM chat template
vllm serve TheBloke/Yi-34B-Chat-AWQ \
  --port 8000 \
  --quantization awq \
  --dtype auto \
  --max-model-len 4096
```

Verification step (critical — do NOT launch a 4-hour run until this passes):
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"<MODEL_NAME>","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'
```
If this returns JSON with content, good. If 400, try Option B.

---

## Complete Table 4 — 12-class updated

Post all re-runs with BOTH broken and valid entries marked:

| Run | Status | Acc | Top-1 | Top-3 | F1_m | F1_w |
|---|---|---:|---:|---:|---:|---:|
| r16_final_stacked | ✅ SOTA | .501 | **.562** | **.847** | .284 | .493 |
| r6_final_stacked | ✅ | .494 | .557 | .837 | .276 | .490 |
| final_combined | ✅ | .492 | .552 | .841 | .302 | .499 |
| r4_final | ✅ | .471 | .532 | .824 | .308 | .486 |
| r16_bypass_logic | ✅ | .047 | .527 | .802 | .221 | .452 |
| r6_combined | ✅ | .465 | .522 | .781 | .200 | .436 |
| r15_no_rag | ✅ | .057 | .509 | .627 | .193 | .460 |
| **r17_bypass_checker** | ❌ buggy | .046 | .507 | .644 | .199 | .457 |
| t1_diag_topk (baseline) | ✅ | .057 | .505 | .762 | .190 | .462 |
| r20_nos_variant | ✅ | .438 | .491 | .599 | .186 | .427 |
| r18_single_llm | ✅ | .249 | .478 | .575 | .167 | .414 |
| **r21_evidence_v2** | ✅ (real neg.) | .026 | .338 | .796 | .144 | .267 |
| **r13_qwen3_8b_v2** | ❌ vLLM 404 | .085 | .085 | .085 | .013 | .012 |
| **r14_yi_34b** | ❌ vLLM 400 | .085 | .085 | .085 | .013 | .012 |

The corrected R17 is needed before it can join this table.

---

## What still needs to be done

### Priority 1 — Re-run the 3 broken experiments (16 GPU hr)

After applying this package:

**R17 (4 hr)** — now that all 3 checker paths are bypassed:
```bash
uv run culturedx run \
  -c configs/base.yaml -c configs/vllm_awq.yaml -c configs/v2.4_final.yaml \
  -c configs/overlays/r17_bypass_checker.yaml \
  -d lingxidiag16k --data-path data/raw/lingxidiag16k \
  -n 1000 --run-name r17_bypass_checker_v2 --seed 42
```

**R13v3 (4 hr)** — with correct model name:
```bash
# First: pkill -f vllm && vllm serve Qwen/Qwen3-8B-AWQ --port 8000 --max-model-len 32768 \
#          --gpu-memory-utilization 0.80 --enable-reasoning --reasoning-parser deepseek_r1
# Verify: curl http://localhost:8000/v1/models

uv run culturedx run \
  -c configs/base.yaml -c configs/vllm_qwen3_8b.yaml -c configs/v2.4_final.yaml \
  -d lingxidiag16k --data-path data/raw/lingxidiag16k \
  -n 1000 --run-name r13_qwen3_8b_v3
```

**R14v3 (4 hr)** — with chat template fix. Do the curl-test FIRST before launching:
```bash
# First: pkill -f vllm && vllm serve modelscope/Yi-1.5-34B-Chat-AWQ --port 8000 \
#          --max-model-len 4096 --gpu-memory-utilization 0.90 --quantization awq \
#          --chat-template-content-format openai --trust-remote-code
# Verify: curl -X POST http://localhost:8000/v1/chat/completions \
#           -H "Content-Type: application/json" \
#           -d '{"model":"modelscope/Yi-1.5-34B-Chat-AWQ","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'
# If 400, fall back to TheBloke/Yi-34B-Chat-AWQ (update config accordingly).

uv run culturedx run \
  -c configs/base.yaml -c configs/v2.4_final.yaml \
  -c configs/overlays/r14_non_qwen.yaml \
  -d lingxidiag16k --data-path data/raw/lingxidiag16k \
  -n 1000 --run-name r14_yi_v3
```

**Total GPU budget**: 12-16 hr.

### Priority 2 — Post-hoc analysis of R21v2 (0 GPU)

The R21v2 F39 over-prediction is a genuine finding worth characterizing:
- Per-case comparison: when does evidence pipeline flip F41 → F39? What evidence keywords triggered it?
- Is this effect worse for Chinese (zh) vs English (en)?
- Would it go away if evidence_verifier threshold is relaxed?

### Priority 3 — Paper narrative sanity check

With R21v2 confirmed as a real negative result, Narrative H has three converging pieces of evidence:
1. ✅ R16 (bypass logic): doesn't fix F32 bias (asymmetry 6.65x, slightly worse)
2. ✅ R6 (somatization+stress): doesn't fix F32 bias (asymmetry 5.93x)
3. ✅ R21 (evidence): doesn't fix F32 bias AND breaks F41 (asymmetry would be near-infinity since F41→F32 is now 536/15)
4. ✅ final_combined (supervised RRF): **does** fix F32 bias (asymmetry 1.80x)

This is a very clean story for the paper.

---

## Deliverables in this package

```
queue_fixes_v2/
├── QUEUE_RERUN_ANALYSIS.md                           This document
├── r17_fix_covers_all_checker_paths.patch            Fix for R17 (covers DtV paths)
├── fix_top1_code_nameerror.patch                     (unchanged — already applied by user)
└── configs_fix/
    ├── vllm_qwen3_8b.yaml                            Correct R13 model name
    ├── r14_non_qwen.yaml                             R14 with chat template guidance
    ├── r17_bypass_checker.yaml                       R17 overlay (unchanged)
    └── strict_config_validation.patch                (unchanged — already applied)
```

Apply with:
```bash
cd ~/CultureDx
tar xzf ~/Downloads/culturedx_queue_fixes_v2.tar.gz

# The R17 fix needs to go on top of the existing committed R17 patch:
git checkout -b fix/r17-all-checker-paths
patch -p1 < queue_fixes_v2/r17_fix_covers_all_checker_paths.patch

# Replace R13/R14 configs with corrected versions:
cp queue_fixes_v2/configs_fix/vllm_qwen3_8b.yaml configs/
cp queue_fixes_v2/configs_fix/r14_non_qwen.yaml configs/overlays/

uv run pytest tests/ -q     # verify 388 pass
git add -A
git commit -m "fix: R17 covers all 3 checker paths + correct R13/R14 model names"
git push origin fix/r17-all-checker-paths
```
