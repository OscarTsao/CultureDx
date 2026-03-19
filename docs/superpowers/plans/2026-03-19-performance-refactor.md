# Performance & Productivity Refactor Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox syntax for tracking.

**Goal:** 5-10x experiment throughput via vLLM dual-backend, parallel criterion checking, and Qwen3 thinking-mode control.

**Architecture:** Unified LLM client protocol supporting both Ollama (dev) and vLLM (experiments) with batch_generate() for parallel agent execution. Hardware: RTX 5090 32GB, Intel Ultra 7 265K 20-core, 128GB RAM, NVMe.

**Tech Stack:** Python 3.11+, httpx (async+sync), concurrent.futures, vLLM OpenAI-compat API, SQLite WAL

---

## Hardware Budget (RTX 5090 32GB GDDR7)

| Model | VRAM (Q4) | Throughput (Ollama) | Throughput (vLLM est.) |
|-------|-----------|--------------------|-----------------------|
| qwen3:32b | 18.8GB | ~25 tok/s | ~120 tok/s (batched) |
| qwen3:14b | ~9GB | ~45 tok/s | ~200 tok/s (batched) |
| deepseek-r1:14b | 8.4GB | ~40 tok/s | ~180 tok/s |
| BGE-M3 (570M) | 1.5GB | N/A (encoder) | N/A |
| Qwen3-Embedding-8B | 4.4-7.5GB | N/A (encoder) | N/A |

**Key insight:** With vLLM continuous batching, 6 parallel criterion checker requests use the SAME GPU memory as 1 sequential request — the model stays loaded, only KV-cache grows. With 32GB VRAM and qwen3:32b (18.8GB), ~13GB remains for KV-cache, supporting ~6 concurrent sequences at 4K context.

---

## Phase 0: Quick Wins (P0 - Do First)

### Task 0.1: DRY Refactor — Hoist shared mode utilities

**Files:**
- Modify: `src/culturedx/modes/base.py`
- Modify: `src/culturedx/modes/hied.py`, `psycot.py`, `mas.py`, `specialist.py`, `debate.py`
- Create: `tests/test_base_mode.py`

- [ ] Write tests for shared methods on BaseModeOrchestrator
- [ ] Move `_build_transcript_text`, `_build_evidence_map`, `_build_global_evidence_summary` to base
- [ ] Refactor `_abstain` to accept `mode_name` parameter, move to base
- [ ] Delete duplicate methods from all 5 mode files (-115 lines)
- [ ] Run tests: `uv run pytest -q`

### Task 0.2: Inject `/no_think` for Qwen3

**Files:**
- Modify: `src/culturedx/core/config.py` — add `disable_thinking: bool = True`
- Modify: `src/culturedx/llm/client.py` — prepend `/no_think\n` when enabled
- Modify: `configs/base.yaml` — add field

- [ ] Write test: client prepends `/no_think\n` when `disable_thinking=True`
- [ ] Write test: cache key uses original prompt (without `/no_think`)
- [ ] Implement in client.py
- [ ] Update config model and base.yaml
- [ ] Run tests

**Impact:** 10-30% token savings = 10-30% faster generation

---

## Phase 1: Unified LLM Backend (P1)

### Task 1.1: BaseLLMClient Protocol

**Files:**
- Create: `src/culturedx/llm/base.py`

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class BaseLLMClient(Protocol):
    model: str
    def generate(self, prompt: str, prompt_hash: str = "", language: str = "zh") -> str: ...
    def batch_generate(self, prompts: list[str], prompt_hashes: list[str] | None = None, language: str = "zh") -> list[str]: ...
    def compute_prompt_hash(self, template_source: str) -> str: ...
```

- [ ] Write test: OllamaClient satisfies protocol
- [ ] Create base.py
- [ ] Add `batch_generate()` to OllamaClient (ThreadPoolExecutor fallback)

### Task 1.2: VLLMClient Implementation

**Files:**
- Create: `src/culturedx/llm/vllm_client.py`
- Create: `tests/test_vllm_client.py`

- [ ] Write tests (mocked httpx)
- [ ] Implement VLLMClient using `/v1/chat/completions`
- [ ] Support `guided_json` for structured output
- [ ] Support `batch_generate()` with concurrent requests
- [ ] Share LLMCache with OllamaClient

### Task 1.3: Client Factory + Config

**Files:**
- Modify: `src/culturedx/llm/__init__.py`
- Modify: `src/culturedx/core/config.py` — add `max_concurrent: int = 4`
- Modify: `src/culturedx/pipeline/cli.py` — use factory

- [ ] Create `create_llm_client(cfg, cache_path)` factory
- [ ] Update CLI to use factory
- [ ] Test with `provider: "ollama"` (default) and `provider: "vllm"`

---

## Phase 2: Parallel Criterion Checking (P1 - Biggest Speedup)

### Task 2.1: batch_generate() on OllamaClient

- [ ] Implement using ThreadPoolExecutor
- [ ] Cache-first: check all prompts in cache, only send uncached
- [ ] Preserve result order

### Task 2.2: Parallel checker loops in modes

**Files:**
- Modify: `src/culturedx/modes/base.py` — add `_run_checkers_parallel()`
- Modify: All 5 mode files

- [ ] Add `_run_checkers_parallel()` to BaseModeOrchestrator
- [ ] Refactor HiED Stage 2 to use it
- [ ] Refactor PsyCoT, MAS, Specialist, Debate
- [ ] Configurable `max_concurrent_checkers` in mode config

**Expected impact:**
- Ollama: ~1.3x (I/O overlap only, GPU still sequential)
- vLLM: ~5-6x (true parallel via continuous batching)

---

## Phase 3: Sweep Runner Fix (P1)

### Task 3.1: Implement run_fn for sweep CLI

- [ ] Create `_make_run_fn()` factory in cli.py
- [ ] Wire into sweep command
- [ ] Add progress tracking (progress.json)
- [ ] Add resume capability (skip completed conditions)

---

## Phase 4: Evidence Retriever Optimization (P2)

### Task 4.1: Cache sentence embeddings per case
### Task 4.2: Lazy-load BGE-M3 model

---

## Phase 5: Structured Output — vLLM Guided Decoding (P2)

### Task 5.1: JSON schemas per agent type
### Task 5.2: Wire guided_json into VLLMClient

---

## Projected Impact (925-case MDD-5k)

| Config | Per-Case | Full Dataset | Full Ablation (5 modes) |
|--------|----------|-------------|------------------------|
| Current (Ollama sequential) | 2.5 min | 38 hrs | 190 hrs |
| + /no_think (Phase 0) | 2.0 min | 31 hrs | 155 hrs |
| + vLLM parallel (Phase 1+2) | 0.4 min | 6.2 hrs | 31 hrs |
| + All optimizations | 0.3 min | 4.6 hrs | 23 hrs |
