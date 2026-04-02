# CultureDx Full Evaluation Report

## Config Summary

- Generated at: 2026-04-02T10:30:36.780230+00:00
- Config files: configs/base.yaml, configs/hied.yaml, configs/vllm_awq.yaml, configs/targets/lingxidiag_12class.yaml, outputs/eval/paper_aligned_20260402_135102/hied-baseline/eval_config.yaml
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
| global | 1000 | 0.3910 | 0.6740 | 0.0210 | 0.7780 | 0.1525 | 0.0000 |
| hied | 1000 | 0.3910 | 0.6740 | 0.0210 | 0.7780 | 0.1525 | 0.0000 |

## Per-Dataset Comparison

| Mode/Dataset | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate | Elapsed | Cases/Sec |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hied:lingxidiag | 1000 | 0.3910 | 0.6740 | 0.0210 | 0.7780 | 0.1525 | 0.0000 | 53m | 0.317 |

## Per-Disorder Metrics

| Mode | Disorder | Support | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| hied | F20 | 5 | 0.1538 | 0.8000 | 0.2581 |
| hied | F31 | 9 | 0.0000 | 0.0000 | 0.0000 |
| hied | F32 | 370 | 0.4348 | 0.9459 | 0.5957 |
| hied | F39 | 63 | 0.0789 | 0.1429 | 0.1017 |
| hied | F41 | 394 | 0.4466 | 0.7640 | 0.5637 |
| hied | F42 | 36 | 0.1097 | 0.4722 | 0.1780 |
| hied | F43 | 15 | 0.0159 | 0.7333 | 0.0312 |
| hied | F45 | 16 | 0.0000 | 0.0000 | 0.0000 |
| hied | F51 | 43 | 0.0452 | 1.0000 | 0.0865 |
| hied | F98 | 47 | 0.0732 | 0.0638 | 0.0682 |
| hied | Others | 93 | 0.0000 | 0.0000 | 0.0000 |

## Top Error Patterns

| Mode | Dataset | Gold | Predicted | Count | Example Case IDs |
|---|---|---|---|---:|---|
| hied | lingxidiag | F41 | F32 | 218 | 318518739, 341328894, 329606499, 305328637, 355727279 |
| hied | lingxidiag | F39 | F32 | 48 | 327826586, 368679677, 342949614, 398487934, 371401723 |
| hied | lingxidiag | F41 | F43 | 40 | 324224056, 393761475, 329547625, 340563038, 378819190 |
| hied | lingxidiag | Others | F32 | 37 | 371726537, 351228828, 391104352, 383845546, 376288406 |
| hied | lingxidiag | F41 | F51 | 24 | 377662897, 380913193, 397700349, 354219828, 354496307 |
| hied | lingxidiag | F32 | F43 | 23 | 368042020, 378984052, 366918268, 307020057, 359625875 |
| hied | lingxidiag | F41 | F42 | 23 | 353485011, 387726394, 387949900, 311201618, 310152130 |
| hied | lingxidiag | F51 | F32 | 19 | 348839819, 380136533, 373267151, 366260309, 372953321 |
| hied | lingxidiag | F98 | F32 | 18 | 309444601, 336521777, 321037752, 316834006, 399103589 |
| hied | lingxidiag | Others | F20 | 15 | 383925853, 387302774, 397927451, 317513157, 361989707 |
| hied | lingxidiag | Others | F42 | 13 | 347729413, 386951485, 341804915, 331114130, 362317955 |
| hied | lingxidiag | F32 | F51 | 13 | 312389408, 321077019, 399537463, 364759893, 392292656 |
| hied | lingxidiag | F32 | F41 | 12 | 359213312, 379611968, 362641875, 303758025, 345855766 |
| hied | lingxidiag | Others | F43 | 10 | 344699340, 305273450, 335538152, 352801207, 330091430 |
| hied | lingxidiag | Others | F41 | 10 | 376197379, 314631661, 304692970, 304404409, 344708762 |

## Timing Statistics

- Total wall time: 53m
- Total evaluated cases: 1000
- Overall cases/sec: 0.317

| Mode/Dataset | Elapsed | Cases/Sec | Avg Sec/Case | Batch Count |
|---|---:|---:|---:|---:|
| hied:lingxidiag | 53m | 0.317 | 3.158 | 10 |
