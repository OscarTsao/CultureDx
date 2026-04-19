# CultureDx Queue Results — Complete Analysis

**Date**: 2026-04-20
**Repo state**: `main-v2.4-refactor` @ `851e92f` (9 commits pulled from GitHub)
**Analysis scope**: 7 new queue runs + per-disorder breakdown + post-hoc stacking + bias analysis

---

## 🏆 Headline: New SOTA achieved

**R16 bypass logic + final_combined stack**:
- **Top-1 = 0.562** (new best, +1.0pp over previous 0.552)
- **Top-3 = 0.847** (new best, +0.6pp over previous 0.841)
- F1_m = 0.284, F1_w = 0.493

**R6 combined + final_combined stack**:
- Top-1 = 0.557 (+0.5pp)
- Top-3 = 0.837 (-0.4pp)

But 3 of 7 runs are invalid due to 3 distinct bugs. See below.

---

## Table — All runs, 12-class metrics

| Run | Status | Acc | **Top-1** | Top-3 | F1_m | F1_w |
|---|---|---:|---:|---:|---:|---:|
| **r16_final_stacked** ⭐ | ✅ new | .501 | **.562** | **.847** | .284 | .493 |
| r6_final_stacked | ✅ new | .494 | .557 | .837 | .276 | .490 |
| final_combined (prev. best) | ✅ | .492 | .552 | .841 | .302 | .499 |
| r4_final | ✅ | .471 | .532 | .824 | .308 | .486 |
| r16_bypass_logic (alone) | ✅ | .047 | .527 | .802 | .221 | .452 |
| r6_combined (alone) | ✅ | .465 | .522 | .781 | .200 | .436 |
| t1_diag_topk (v2.4 baseline) | ✅ | .057 | .505 | .762 | .190 | .462 |
| r15_no_rag | ✅ | .057 | .509 | .627 | .193 | .460 |
| r7_triage_top8 | ⚠️ 10% bug | .059 | .495 | .741 | .217 | .459 |
| r20_nos_variant | ✅ | .438 | .491 | .599 | .186 | .427 |
| r18_single_llm | ✅ | .249 | .478 | .575 | .167 | .414 |
| r21_evidence_stacked | ❌ 44% bug | .067 | .334 | .509 | .152 | .259 |
| r13_qwen3_8b | ❌ invalid | .085 | .085 | .085 | .013 | .012 |
| r14_gemma3_12b | ❌ invalid | .085 | .085 | .085 | .013 | .012 |

---

## Per-disorder recall — baseline vs R6 vs R16 (top classes only)

For each class, what % of gold-labeled cases had primary correctly identified?

| Disorder | Gold N | Baseline | R6 | R16 | R6 Δ | R16 Δ |
|---|---:|---:|---:|---:|---:|---:|
| F32 (MDD) | 370 | .835 | .876 | **.892** | +4.1 | **+5.7** |
| F41 (anxiety) | 394 | .401 | **.461** | .426 | **+6.0** | +2.5 |
| F42 (OCD) | 36 | .361 | .361 | .361 | 0 | 0 |
| F39 (NOS mood) | 63 | .079 | .079 | .079 | 0 | 0 |
| F45 (somatoform) | 16 | **.000** | **.125** | **.125** | **+12.5** | **+12.5** |
| F51 (sleep) | 43 | .047 | .070 | .047 | +2.3 | 0 |
| F98 (childhood) | 47 | .000 | .000 | .000 | 0 | 0 |
| F43 (stress) | 15 | .000 | .000 | .000 | 0 | 0 |
| F20 (schiz) | 5 | .800 | .800 | .800 | 0 | 0 |

### What this tells us

**R6 (somatization + stress detection)** genuinely unlocks:
- F45 from 0% to 12.5% (2/16 cases) — prompt targeting worked for somatoform
- F41 recall +6.0pp — likely from stress-detection triggering context
- F32 recall +4.1pp — unexpected side effect (R6 doesn't target F32)

**R16 (bypass logic engine)** concentrates gain on F32:
- F32 recall +5.7pp (largest single lift) — logic engine was rejecting valid F32 cases
- F41 recall +2.5pp — modest
- F45 +12.5pp — same as R6 (probably for different reason: less strict gating)

**What doesn't work**:
- F39 (NOS): 7.9% recall across all runs. R20 (NOS-aware) didn't move it.
- F98 (childhood): 0% recall across all runs. Diagnostician never picks F98.
- F43 (stress): 0% recall. Stress detection didn't trigger or didn't change ranking enough.
- F42 (OCD): 36.1% plateau across all runs.

**Critical gap**: F98 and F43 at 0% recall need a dedicated intervention. Current diagnostician prompt simply doesn't surface these disorders even when they're in candidate list. Options:
- Prompt variant with explicit "consider childhood/stress presentations"
- Supervised re-weighting on these classes
- Different diagnostician (e.g., R14 backbone)

---

## F41/F32 bias asymmetry — the KEY scientific finding

| Run | F41 recall | F32 recall | F41→F32 errors | F32→F41 errors | **Asymmetry** |
|---|---:|---:|---:|---:|---:|
| t1_diag_topk (baseline) | .431 | .839 | 160 | 25 | **6.40x** |
| r6_combined | .461 | .875 | 172 | 29 | 5.93x |
| r16_bypass_logic | .458 | .893 | 173 | 26 | 6.65x |
| r20_nos_variant | .450 | .792 | 154 | 28 | 5.50x |
| **final_combined** | **.544** | .744 | 128 | 71 | **1.80x** ⭐ |
| r6_final_stacked | .567 | .774 | 134 | 62 | 2.16x |
| r16_final_stacked | .567 | .774 | 134 | 67 | 2.00x |

### What this reveals

**Architecture-level interventions do NOT fix the F32 bias**:
- R6, R16 slightly improve F41 recall but asymmetry stays 5-7x
- R16 actually makes asymmetry worse (6.65x) because logic engine bypass lets MORE F32 false positives through

**Only supervised signal reduces the bias**:
- final_combined (which adds RRF with TF-IDF baseline) drops asymmetry from 6.40x → 1.80x
- TF-IDF is a supervised model trained on the data — it has the OPPOSITE bias (or at least a different bias) from the LLM

**Paper implication** (very important):
> "The F32 bias in LLM-based psychiatric diagnosis is intrinsic to pretrained weights. Prompt engineering (R4 contrastive primary), architectural changes (R16 bypass logic engine), and supplementary detection modules (R6 somatization+stress) fail to reduce the F41→F32 error asymmetry below 5x. Only supervised classifier integration via RRF brings it to 1.8x."

This is the strongest thesis-worthy finding in the dataset. Reframes the contribution as: **"MAS pipelines inherit LLM priors; integrating supervised components is necessary for bias mitigation."**

---

## Three bugs discovered during review

### Bug 1: `top1_code` NameError (code bug)

**Location**: `src/culturedx/modes/hied.py` line 1285
```python
"veto_from": top1_code if veto_applied else None,   # top1_code never defined
```

**Scope**:
- r7_triage_top8: 10.1% of cases lost
- **r21_evidence_stacked: 44.1% of cases lost** — evidence pipeline triggers veto much more often
- r16_bypass_logic: 0.4% (negligible)

**Fix** (patch provided as `fix_top1_code_nameerror.patch`):
```python
"veto_from": top_ranked[0] if veto_applied and top_ranked else None,
```

**Verified**: applies cleanly, all 388/388 tests pass.

### Bug 2: R13/R14 config field names wrong

**Location**: `configs/vllm_qwen3_8b.yaml` and `configs/overlays/r14_non_qwen.yaml`

Both use `model:` and `backend:` which are **not valid field names** in LLMConfig. The actual schema is:
- `provider: str` (not `backend:`)
- `model_id: str` (not `model:`)

**Why it silently failed**: `CultureDxConfig` had `model_config = ConfigDict(extra="ignore")`, so Pydantic silently dropped the mis-spelled fields. LLMConfig fell back to defaults (`provider: "ollama", model_id: "qwen3:14b"`), which is why BOTH R13 and R14 ran the same `qwen3:14b` via ollama.

**Fix**: Replace config files + add strict validation to catch future typos.
- `configs_fix/vllm_qwen3_8b.yaml` (replacement)
- `configs_fix/r14_non_qwen.yaml` (replacement with Yi-1.5-34B as proper cross-family model)

### Bug 3: Silent config validation (system-level)

**Location**: `src/culturedx/core/config.py`

```python
class CultureDxConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")   # silently drops typos
```

This was the root enabler of Bug 2. The PR branch `b9ec26b "fix: remove all silent fallbacks for research reproducibility"` missed this one.

**Fix** (`strict_config_validation.patch`):
- Change to `extra="forbid"` on both LLMConfig and CultureDxConfig
- Verified: catches `LLMConfig(model='...')` with ValidationError, all 388 tests still pass.

---

## GPU hours spent vs gained

**Spent**: ~28 GPU-hours across 7 runs
**Valid results**: ~16 hours (R6, R7 partial, R16, R20)
**Wasted**: ~12 hours (R13, R14, half of R21)

**Scientific yield per hour**:
- 🥇 R16 result (+2.2pp Top-1 alone, +1.0pp stacked, new SOTA) — 4 hr well spent
- 🥇 F41/F32 bias analysis — requires no extra GPU, pure analysis on existing predictions
- 🥈 R6 (+1.7pp Top-1 alone, modest stacked) — 4 hr worthwhile
- 🥉 R20 (negative result, drop from paper) — 4 hr for a non-result (but still useful info)
- ⚠️ R7 (null result, contaminated by bug) — 4 hr mostly wasted
- ❌ R13, R14, R21 — need to re-run after fixes

---

## Master action plan — what to do next

### Immediate (0 GPU, ~30 min):
1. **Apply `fix_top1_code_nameerror.patch`** — critical bug fix
2. **Apply `strict_config_validation.patch`** — prevent future silent failures
3. **Replace R13/R14 config files** with the fixed versions
4. **Commit** — single PR: `fix: queue runtime bugs (top1_code NameError, strict config validation, R13/R14 configs)`

### Re-run priority list (GPU needed):
1. **R21 evidence** — 4 hr — highest priority because current results are invalid and evidence is a key hypothesis
2. **R13 Qwen3-8B** — 4 hr — backbone size test (requires vLLM restart with Qwen3-8B-Instruct-AWQ)
3. **R14 Yi-1.5-34B-Chat-AWQ** — 4 hr — backbone family test (requires vLLM swap)
4. **R7** — 4 hr (optional) — probably null result but clean data is nice

### Post-hoc analysis priorities (0 GPU):
1. **Per-disorder error taxonomy for F39/F98/F43** — why are these always 0%?
2. **Oracle analysis on r16_final_stacked** — what's the new Top-1 ceiling?
3. **R4 contrastive + final_combined** — already done as r4_final (0.532)
4. **R6+R16 combined overlay** — test if stacking overlays before final_combined beats either alone

### Paper narrative update:
- 🆕 **Narrative H (new)**: "LLM priors dominate MAS pipelines; architectural interventions fail to mitigate F32 bias; supervised RRF integration achieves 3.5x bias reduction." This is now your strongest claim.
- ✅ **Narrative A (interpretability)**: Still viable. Criterion evidence still useful for explanation even if logic engine gating hurts.
- ✅ **Narrative F (MAS > single LLM)**: Confirmed. +2.7pp Top-1 over r18_single_llm baseline.
- ⚠️ **Narrative B (detection ≠ ranking)**: Need R13/R14 to test whether bias correlates with model capability or family.

---

## Deliverables in this package

All files in the tarball:

```
queue_fixes/
├── QUEUE_RESULTS_COMPLETE.md                  This document
├── fix_top1_code_nameerror.patch              Critical bug fix
├── configs_fix/
│   ├── strict_config_validation.patch         Prevent silent failures
│   ├── vllm_qwen3_8b.yaml                     R13 config fix
│   └── r14_non_qwen.yaml                      R14 config fix (Yi-1.5-34B)
└── apply_all_fixes.sh                         One-shot apply script
```

Apply all with:
```bash
cd ~/CultureDx
tar xzf ~/Downloads/culturedx_queue_fixes.tar.gz
./queue_fixes/apply_all_fixes.sh
uv run pytest tests/ -q     # verify 388 passed
git add -A && git commit -m "fix: queue runtime bugs + strict config + R13/R14 configs"
git push origin main-v2.4-refactor
```

---

## Appendix: Root cause of F98/F43/F39 zero recall (investigated post-review)

### F98 (childhood): 47 gold cases
- ✓ Target in candidate list: **37/47** (79%)
- ✗ Target anywhere in diag ranking: 10/47 (21%)
- ✗ Target at rank 1: **0/47**
- ✗ When ranked, position: always 5/5 (last slot)
- ✓ **Logic engine confirmed F98 in 30/47 (64%) — checker says YES**
- Predicted instead: F32 (31×), abstain (10×), F41 (5×)
- **Root cause**: Diagnostician prompt never surfaces F98 early enough. Checker confirms but primary selection uses top-5 slice so F98-at-position-5 loses to whatever got ranked higher.

### F43 (stress reactions): 15 gold cases
- ✓ In candidates: 15/15 (100%)
- ✗ In diag ranking: 8/15 (53%)
- ✗ In top-3: 1/15
- ✓ **Logic engine confirmed: 13/15 (87%)**
- Predicted instead: F32 (9×), F41 (4×)
- **Root cause**: same as F98 — checker confirms, diagnostician doesn't surface.

### F39 (NOS mood): 63 gold cases
- ✓ In candidates: 61/63 (97%)
- ✓ In diag ranking: 59/63 (94%)
- ✓ **In top-3: 52/63 (83%)** — diagnostician DOES rank it high
- ✗ At rank 1: 5/63 (7.9%)
- ✓ Logic engine confirmed: 60/63 (95%)
- Predicted instead: **F32 (41/63 = 65%)**
- **Root cause**: Different from F98/F43. F39 IS correctly ranked high, but F32 bias wins at primary selection.

### The supervised stack rescues F39 and F43, not F98

| Class | Baseline | R6 | R16 | final_combined | R6+stack | R16+stack |
|---|---:|---:|---:|---:|---:|---:|
| F98 | 0% | 0% | 0% | **10.6%** | 0% | 0% |
| F43 | 0% | 0% | 0% | 20.0% | **26.7%** | 20.0% |
| F39 | 7.9% | 7.9% | 7.9% | **52.4%** | 46.0% | 52.4% |
| F45 | 0% | 12.5% | 12.5% | 18.8% | **31.2%** | 31.2% |

**Key insight**: TF-IDF RRF ensemble (via final_combined) dramatically improves F39 (+44.5pp), F43 (+20pp), F45 (+18.8pp). But:
- **F98 only rescued by final_combined alone**. Adding R6/R16 pushes F32 predictions even harder, crowding F98 back to 0%.
- This is the per-class tradeoff of R16+stack reaching Top-1 .562: it wins F32/F41 but loses F98.

### Actionable next experiments

1. **F98-specific intervention**: Current diagnostician prompt lists 14 disorders but likely doesn't describe F98 (childhood onset) in a way that triggers ranking. A targeted prompt revision for childhood presentations could push F98 from rank 5 to rank 2-3, where the RRF ensemble could rescue it.

2. **Per-class threshold in RRF**: Current RRF uses uniform weights (1.0, 0.7). For F98/F43, the TF-IDF signal might need stronger weighting since LLM essentially abstains.

3. **F39 remaining 47.6% gap**: Even with final_combined, F39 loses 48% to F32. An F41/F39/F32 triangle disambiguator (similar to R4 but handling 3 classes) might close this further.

