# CultureDx Full Evaluation Report

## Config Summary

- Generated at: 2026-04-02T17:33:47.747691+00:00
- Config files: configs/base.yaml, configs/vllm_32b.yaml, configs/vllm_awq.yaml
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
| global | 1000 | 0.3640 | 0.6180 | 0.0440 | 0.7865 | 0.1429 | 0.0000 |
| hied | 1000 | 0.3640 | 0.6180 | 0.0440 | 0.7865 | 0.1429 | 0.0000 |

## Per-Dataset Comparison

| Mode/Dataset | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate | Elapsed | Cases/Sec |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hied:lingxidiag | 1000 | 0.3640 | 0.6180 | 0.0440 | 0.7865 | 0.1429 | 0.0000 | 14m | 1.164 |

## Per-Disorder Metrics

| Mode | Disorder | Support | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| hied | F20 | 5 | 0.1333 | 0.4000 | 0.2000 |
| hied | F31 | 9 | 0.0000 | 0.0000 | 0.0000 |
| hied | F32 | 370 | 0.4330 | 0.8216 | 0.5672 |
| hied | F39 | 63 | 0.0577 | 0.0952 | 0.0719 |
| hied | F41 | 394 | 0.4611 | 0.6929 | 0.5538 |
| hied | F42 | 36 | 0.1090 | 0.4722 | 0.1771 |
| hied | F43 | 15 | 0.0183 | 0.7333 | 0.0358 |
| hied | F45 | 16 | 0.0000 | 0.0000 | 0.0000 |
| hied | F51 | 43 | 0.0467 | 0.9767 | 0.0891 |
| hied | F98 | 47 | 0.0488 | 0.0426 | 0.0455 |
| hied | Others | 93 | 0.0000 | 0.0000 | 0.0000 |

## Top Error Patterns

| Mode | Dataset | Gold | Predicted | Count | Example Case IDs |
|---|---|---|---|---:|---|
| hied | lingxidiag | F41 | F32 | 216 | 318518739, 341328894, 329606499, 305328637, 355727279 |
| hied | lingxidiag | F32 | F51 | 53 | 312389408, 358313639, 321077019, 346998154, 327456260 |
| hied | lingxidiag | F41 | F51 | 49 | 377662897, 380913193, 397700349, 354219828, 320669626 |
| hied | lingxidiag | F39 | F32 | 46 | 368679677, 342949614, 398487934, 371401723, 318024484 |
| hied | lingxidiag | Others | F32 | 38 | 344699340, 371726537, 376197379, 351228828, 391104352 |
| hied | lingxidiag | F41 | F43 | 26 | 324224056, 393761475, 329547625, 340563038, 395309894 |
| hied | lingxidiag | F41 | F42 | 21 | 353485011, 387726394, 387949900, 319574587, 310152130 |
| hied | lingxidiag | F98 | F32 | 17 | 309444601, 336521777, 321037752, 316834006, 379961969 |
| hied | lingxidiag | Others | F51 | 16 | 314631661, 383579251, 383845546, 338464039, 383336330 |
| hied | lingxidiag | F51 | F32 | 13 | 348839819, 373267151, 366260309, 379479487, 301219386 |
| hied | lingxidiag | F32 | F43 | 11 | 307020057, 349575167, 379645537, 387294870, 382859942 |
| hied | lingxidiag | F43 | F32 | 10 | 337522433, 395985056, 329984067, 313602441, 378540759 |
| hied | lingxidiag | Others | F42 | 9 | 347729413, 386951485, 331114130, 303683319, 311568500 |
| hied | lingxidiag | F32 | F41 | 9 | 359213312, 379611968, 375048974, 375905284, 378511469 |
| hied | lingxidiag | Others | F20 | 9 | 383925853, 387302774, 397927451, 317513157, 361989707 |

## Timing Statistics

- Total wall time: 14m
- Total evaluated cases: 1000
- Overall cases/sec: 1.164

| Mode/Dataset | Elapsed | Cases/Sec | Avg Sec/Case | Batch Count |
|---|---:|---:|---:|---:|
| hied:lingxidiag | 14m | 1.164 | 0.859 | 20 |
