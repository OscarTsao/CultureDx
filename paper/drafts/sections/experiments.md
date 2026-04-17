# 4. Experimental Setup

## 4.1 Datasets

All headline numbers in this draft come from the committed LingxiDiag-16K validation split (`results/validation`, N=1000). The repository contains adapters for additional datasets, including MDD-5k, but matching paper-aligned result artifacts are not checked in for this branch. To keep the paper claims auditable, we therefore restrict the quantitative discussion to LingxiDiag-16K validation and treat other adapters as implementation support rather than reported experiments.

The benchmark follows the LingxiDiagBench-style 2-class, 4-class, and 12-class evaluation protocol. Runtime scope is explicit: the paper configuration sets `scope_policy: manual`, `execution_mode: benchmark_manual_scope`, and `force_prediction: true`. This means the benchmark does not use triage to silently narrow the candidate set, and it does not abstain during the paper-aligned run. Instead, the system predicts within a declared manual target set consisting of `F20`, `F31`, `F32`, `F39`, `F41.0`, `F41.1`, `F41.2`, `F42`, `F43.1`, `F43.2`, `F45`, `F51`, `F98`, and `Z71`.

## 4.2 Models and Runtime

The main evaluation model is `Qwen/Qwen3-32B-AWQ`, served through vLLM with AWQ quantization. The paper-aligned configs set greedy decoding (`temperature=0.0`, `top_k=1`) and `max_tokens=1536`. Retrieval uses top-5 balanced similar cases when enabled, and the final V2 configuration uses label-only retrieval with the diagnose-then-verify stack.

We also include a partial multi-backbone validation slice in `results/validation/multi_backbone`. Those runs test whether the same structure transfers to smaller or cheaper backbones, including Qwen3-8B BF16, Qwen3-8B-AWQ, and Qwen3-14B-AWQ. These auxiliary results are presented as robustness evidence rather than as the primary benchmark table.

## 4.3 Compared Configurations

The six committed validation runs correspond to the rows in `paper/tables/ablation_results.md`:

| Row | Config | Description |
|-----|--------|-------------|
| 01 | Single | Zero-shot baseline without the multi-stage pipeline |
| 02 | Single + RAG | Single-call generation with similar-case retrieval |
| 03 | DtV V1 | Diagnose-then-verify without retrieval |
| 04 | DtV V1 + RAG | V1 pipeline with retrieval |
| 05 | DtV V2 + RAG | Final paper configuration |
| 06 | DtV V2 + RAG + Gate | Final configuration plus forbidden-pair comorbidity gate |

## 4.4 Evaluation Metrics

The primary ranking metric is `Overall`, defined in the committed validation README as the mean of 11 paper metrics: three 2-class metrics, three 4-class metrics, and five 12-class metrics. We additionally inspect diagnosis accuracy, top-1 and top-3 accuracy, macro/weighted F1, and multi-label comorbidity metrics such as subset accuracy, hamming accuracy, label precision, and label coverage. These secondary metrics are not used to rank systems in the paper table, but they are useful for understanding why a configuration improves or regresses.
