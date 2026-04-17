# 3. Method

## 3.1 System Architecture

CultureDx implements a diagnose-then-verify variant of the HiED pipeline. The core design principle is to separate open-ended reasoning from thresholded diagnostic decisions so that each stage can be inspected independently.

```
Clinical Transcript
        │
        ▼
┌───────────────────┐
│ Evidence Pipeline │  extract → somatize → retrieve → match
└────────┬────────┘
         ▼
┌─────────────────┐
│ Diagnostician    │  LLM: rank candidate disorders
│ Criterion Check  │  LLM: verify top-ranked disorders
│ Logic Engine     │  Deterministic ICD-10 dispatch
│ Calibrator       │  Statistical confidence scoring
│ Comorbidity Gate │  Rule-based ICD-10 exclusions
└────────┬────────┘
         ▼
   DiagnosisResult
```

For the benchmark reported in this draft, `scope_policy: manual` and `execution_mode: benchmark_manual_scope` are explicit. This matters: the evaluation does not rely on triage to narrow the search space. Instead, the benchmark uses a fixed manual target set and measures how well the downstream reasoning stack ranks, verifies, and filters diagnoses within that declared scope. The same orchestrator also supports open-set production semantics, but those results are not claimed here.

Within the benchmark path, the diagnostician receives the full transcript, the candidate disorder list, and optional retrieved similar cases, then returns a ranked list of candidate diagnoses with free-text reasoning. The top-ranked candidates are passed to the criterion checker, which produces structured per-criterion outputs including status, confidence, and extracted evidence. These checker outputs are the only inputs consumed by the deterministic logic engine, which applies disorder-specific ICD-10 thresholds rather than asking the LLM to make the final threshold decision directly.

The post-checker stages are intentionally simple and auditable. The confidence calibrator converts checker features into a calibrated primary prediction and optional comorbid candidates, while the comorbidity resolver enforces directional exclusions and forbidden pairs such as F31 superseding F32/F33 and Z71 excluding specific disorders. Each run preserves decision traces, failures, and stage timings so that final predictions remain machine-joinable with the rest of the evaluation artifacts.

## 3.2 Evidence Pipeline

The evidence pipeline turns a raw dialogue into an `EvidenceBrief` that can be reused by downstream agents. It proceeds in four steps: symptom span extraction from patient turns, Chinese somatization mapping, criterion-level retrieval/matching, and brief assembly. This decomposition is important because the benchmark transcripts often contain diagnostically useful symptoms in forms that do not directly resemble ICD-10 phrasing.

Somatization handling is implemented through a checked-in ontology of 150 mappings from Chinese expressions to criterion-level hints. Examples include `胸闷` for anxiety-related somatic symptoms, `浑身没劲` for fatigue or loss of energy, and `睡不着` for insomnia-related criteria. The ontology is used before LLM fallback, which keeps common cultural expressions deterministic and reviewable. Temporal extraction is handled separately so that duration-dependent disorders, such as depressive episodes and generalized anxiety disorder, can incorporate normalized time-course signals rather than raw string matches alone.

Negation handling is scope-aware rather than keyword-only. This is necessary in Chinese because surface negation markers can appear inside positive clinical idioms; for example, `睡不着` should count as insomnia evidence, not as negated sleep difficulty. Retrieval and matching then connect extracted symptoms to disorder criteria using BGE-M3-based dense retrieval, lexical overlap, and native hybrid fusion where available. The final `EvidenceBrief` contains disorder-specific evidence snippets, temporal summaries, failures, and stage timings, allowing later components to degrade gracefully instead of failing opaquely.

## 3.3 Evaluated Variants

The current branch includes six paper-aligned validation variants, each backed by committed artifacts:

| Row | Variant | Purpose |
|-----|---------|---------|
| 01 | Single | Zero-shot single-model baseline |
| 02 | Single + RAG | Tests whether similar-case retrieval helps without verification |
| 03 | DtV V1 | Early diagnose-then-verify pipeline without retrieval |
| 04 | DtV V1 + RAG | Adds label-only retrieval to the V1 pipeline |
| 05 | DtV V2 + RAG | Final paper configuration |
| 06 | DtV V2 + RAG + Gate | Adds explicit forbidden-pair filtering |

These variants isolate a practical question rather than a purely architectural one: does adding retrieval help only when the model is also forced to verify candidate disorders against explicit criteria? The validation results in Section 5 show that the answer is yes.
