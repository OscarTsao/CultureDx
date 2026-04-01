# Improvement Queue

Priority-ordered pipeline improvements. Items marked DONE were completed in
the docs-and-production-hardening branch.

## Status Key

| Status | Meaning |
|--------|---------|
| DONE | Merged/committed |
| ACTIVE | In progress or waiting on dependency |
| QUEUED | Ready to start when predecessor completes |

---

## P0: Temporal Evidence Tool Fix (ACTIVE)

**Goal:** Fix eval_loss NaN → select best checkpoint → integrate temporal tool.

**Root cause:** `format_chat_template()` tokenized only `messages[0]` for prompt
boundary; Qwen3-8B template includes `<think>` and system tokens, causing
misalignment. All response tokens masked → NaN loss.

**Fix:** Prepared in `scripts/finetune_checker.py` — collects all pre-assistant
messages for prompt prefix, adds token-level alignment validation.

**Dependency:** Current QLoRA run (PID 320737) must finish first. The fix applies
to the *next* finetune run.

**Estimated effort:** 2–3 days (finetune + eval cycle).

---

## P1: Somatization Ontology Provenance — DONE

Added `source` field to all 150 entries in `somatization_map.json` (v2.0→v2.1)
with ICD-10 criterion references, CCMD-3, or clinical consensus citations.

---

## P2: BGE-reranker-v2-m3 Cross-Encoder (QUEUED)

**Goal:** Replace `ConceptOverlapReranker` (jaccard + retrieval score fusion)
with `bge-reranker-v2-m3` cross-encoder for evidence reranking.

**Position A — highest ROI:** Better evidence quality → better checker accuracy
→ better diagnosis. The current `ConceptOverlapReranker` uses surface-level
jaccard similarity which misses semantic matches, especially for Chinese
somatization expressions.

**Implementation plan:**

1. Add `CrossEncoderReranker` class in `criteria_matcher.py` implementing
   `EvidenceReranker` protocol.
2. Load `BAAI/bge-reranker-v2-m3` via FlagEmbedding `FlagReranker` or
   `sentence-transformers` `CrossEncoder`.
3. Score `(criterion_text, evidence_text)` pairs; preserve negation penalty.
4. Add reranker config fields to `EvidenceConfig` (`reranker_name`,
   `reranker_model_id`).
5. Wire into evidence pipeline assembly (retriever_factory or pipeline.py).
6. Add `FlagEmbedding` to `[project.optional-dependencies].retrieval`.
7. Unit test with `MockRetriever` + `CrossEncoderReranker`.

**Fallback:** Keep `ConceptOverlapReranker` as default when FlagEmbedding is not
installed — same pattern as BGEM3Retriever.

**Estimated effort:** Half day.

---

## P3: BGE-M3 Native Hybrid — DONE

`BGEM3Retriever` already supports native hybrid mode (dense + sparse + ColBERT)
via FlagEmbedding. `HybridRetriever` detects `native_hybrid=True` and skips
external lexical fusion.

---

## P4: Negation Scope — DONE

Evidence metadata propagation (negation + somatization) now flows end-to-end:
`SymptomSpan.expression_type` → `CriterionEvidence.has_negated_spans` →
`_build_evidence_map()` inline tags → checker prompt metadata legend.

---

## P5: Re-sweep N=200 (QUEUED — blocked by P0, P2)

**Goal:** Full ablation sweep with N=200 across all modes to measure cumulative
impact of P1–P4 improvements.

**Blocked by:** P0 (temporal fix integrated) and P2 (cross-encoder active).

**Estimated effort:** 1 day GPU time.

---

## Future Positions (Not Yet Queued)

These were identified in the pipeline scoring gap analysis but have lower ROI
than Position A. They can be revisited after P5 sweep results.

| Position | Location | Current | Upgrade | ROI |
|----------|----------|---------|---------|-----|
| B | Triage confidence | LLM logprobs | Cross-encoder disorder–transcript scoring | Medium |
| C | Calibrator input | Criteria-met counts | Dense similarity features | Low-Medium |
| D | Comorbidity resolver | Rule-based exclusion | Pairwise disorder similarity scoring | Low |
| E | Differential synthesis | LLM free-form | Evidence-weighted differential ranking | Medium |
