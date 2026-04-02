# CultureDx Full Evaluation Report

## Config Summary

- Generated at: 2026-04-02T14:38:51.378646+00:00
- Config files: configs/base.yaml, configs/hied.yaml, configs/vllm_awq.yaml, configs/targets/lingxidiag_12class.yaml, outputs/eval/rescore_gate_only_20260402_223720/hied-baseline/eval_config.yaml
- Modes: hied
- Datasets: lingxidiag
- Model: Qwen/Qwen3-32B-AWQ
- Adapter path: not provided
- Evidence: disabled
- Somatization: disabled
- Max cases per dataset: all

## Overall Metrics

| Scope | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| global | 702 | 0.3490 | 0.5698 | 0.0613 | 0.7770 | 0.1447 | 0.0000 |
| hied | 702 | 0.3490 | 0.5698 | 0.0613 | 0.7770 | 0.1447 | 0.0000 |

## Per-Dataset Comparison

| Mode/Dataset | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate | Elapsed | Cases/Sec |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hied:lingxidiag | 702 | 0.3490 | 0.5698 | 0.0613 | 0.7770 | 0.1447 | 0.0000 | 1m | 14.202 |

## Per-Disorder Metrics

| Mode | Disorder | Support | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| hied | F20 | 5 | 0.2000 | 0.4000 | 0.2667 |
| hied | F31 | 7 | 0.0000 | 0.0000 | 0.0000 |
| hied | F32 | 264 | 0.4554 | 0.7727 | 0.5730 |
| hied | F39 | 36 | 0.0000 | 0.0000 | 0.0000 |
| hied | F41 | 275 | 0.5076 | 0.6036 | 0.5515 |
| hied | F42 | 19 | 0.1081 | 0.4211 | 0.1720 |
| hied | F43 | 9 | 0.0141 | 0.5556 | 0.0275 |
| hied | F45 | 9 | 0.0000 | 0.0000 | 0.0000 |
| hied | F51 | 35 | 0.0562 | 0.9714 | 0.1063 |
| hied | F98 | 37 | 0.0667 | 0.0270 | 0.0385 |
| hied | Others | 66 | 0.0000 | 0.0000 | 0.0000 |

## Top Error Patterns

| Mode | Dataset | Gold | Predicted | Count | Example Case IDs |
|---|---|---|---|---:|---|
| hied | lingxidiag | F41 | F32 | 137 | 318518739, 305328637, 355727279, 335985565, 365148198 |
| hied | lingxidiag | F32 | F51 | 53 | 312389408, 358313639, 321077019, 346998154, 327456260 |
| hied | lingxidiag | F41 | F51 | 47 | 377662897, 380913193, 397700349, 354219828, 320669626 |
| hied | lingxidiag | F39 | F32 | 24 | 371401723, 318024484, 360136896, 357343954, 330014648 |
| hied | lingxidiag | Others | F32 | 22 | 344699340, 351228828, 391104352, 340282544, 321679684 |
| hied | lingxidiag | F41 | F43 | 19 | 324224056, 393761475, 329547625, 395309894, 324090242 |
| hied | lingxidiag | F41 | F42 | 17 | 345082346, 353485011, 387949900, 319574587, 310152130 |
| hied | lingxidiag | Others | F51 | 16 | 314631661, 383579251, 383845546, 338464039, 383336330 |
| hied | lingxidiag | F98 | F32 | 14 | 321037752, 316834006, 379961969, 368417566, 303669869 |
| hied | lingxidiag | F51 | F32 | 8 | 348839819, 373267151, 366260309, 379479487, 356160815 |
| hied | lingxidiag | F32 | F43 | 8 | 307020057, 379645537, 387294870, 314451639, 303657806 |
| hied | lingxidiag | Others | F43 | 8 | 305273450, 335538152, 330091430, 355975065, 308267561 |
| hied | lingxidiag | Others | F41 | 7 | 341804915, 304404409, 344708762, 392824698, 383339189 |
| hied | lingxidiag | Others | F42 | 6 | 347729413, 386951485, 303683319, 374554660, 373615731 |
| hied | lingxidiag | F31 | F32 | 6 | 368998951, 372751711, 386493731, 375436808, 371239097 |

## Timing Statistics

- Total wall time: 1m
- Total evaluated cases: 702
- Overall cases/sec: 9.960

| Mode/Dataset | Elapsed | Cases/Sec | Avg Sec/Case | Batch Count |
|---|---:|---:|---:|---:|
| hied:lingxidiag | 1m | 14.202 | 0.070 | 10 |
