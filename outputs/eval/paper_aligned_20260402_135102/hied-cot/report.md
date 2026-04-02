# CultureDx Full Evaluation Report

## Config Summary

- Generated at: 2026-04-02T10:42:53.007789+00:00
- Config files: configs/base.yaml, configs/hied.yaml, configs/vllm_awq.yaml, configs/targets/lingxidiag_12class.yaml, outputs/eval/paper_aligned_20260402_135102/hied-cot/eval_config.yaml
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
| global | 1000 | 0.3930 | 0.6770 | 0.0210 | 0.7786 | 0.1545 | 0.0000 |
| hied | 1000 | 0.3930 | 0.6770 | 0.0210 | 0.7786 | 0.1545 | 0.0000 |

## Per-Dataset Comparison

| Mode/Dataset | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate | Elapsed | Cases/Sec |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hied:lingxidiag | 1000 | 0.3930 | 0.6770 | 0.0210 | 0.7786 | 0.1545 | 0.0000 | 12m | 1.360 |

## Per-Disorder Metrics

| Mode | Disorder | Support | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| hied | F20 | 5 | 0.1600 | 0.8000 | 0.2667 |
| hied | F31 | 9 | 0.0000 | 0.0000 | 0.0000 |
| hied | F32 | 370 | 0.4348 | 0.9459 | 0.5957 |
| hied | F39 | 63 | 0.0619 | 0.0952 | 0.0750 |
| hied | F41 | 394 | 0.4459 | 0.7640 | 0.5631 |
| hied | F42 | 36 | 0.1097 | 0.4722 | 0.1780 |
| hied | F43 | 15 | 0.0159 | 0.7333 | 0.0311 |
| hied | F45 | 16 | 0.0000 | 0.0000 | 0.0000 |
| hied | F51 | 43 | 0.0452 | 1.0000 | 0.0864 |
| hied | F98 | 47 | 0.0732 | 0.0638 | 0.0682 |
| hied | Others | 93 | 0.0000 | 0.0000 | 0.0000 |

## Top Error Patterns

| Mode | Dataset | Gold | Predicted | Count | Example Case IDs |
|---|---|---|---|---:|---|
| hied | lingxidiag | F41 | F32 | 217 | 374577341, 329606499, 305328637, 355727279, 397700349 |
| hied | lingxidiag | F39 | F32 | 46 | 327826586, 368679677, 342949614, 398487934, 371401723 |
| hied | lingxidiag | Others | F32 | 40 | 344699340, 371726537, 383925853, 314631661, 391104352 |
| hied | lingxidiag | F41 | F43 | 40 | 341328894, 324224056, 393761475, 329547625, 340563038 |
| hied | lingxidiag | F41 | F42 | 27 | 345082346, 353485011, 387726394, 387949900, 319574587 |
| hied | lingxidiag | F41 | F51 | 26 | 377662897, 380913193, 354219828, 354496307, 308086484 |
| hied | lingxidiag | F51 | F32 | 19 | 348839819, 380136533, 373267151, 387133350, 366260309 |
| hied | lingxidiag | F32 | F43 | 17 | 368042020, 378984052, 307020057, 308845940, 349575167 |
| hied | lingxidiag | F98 | F32 | 17 | 336521777, 321037752, 316834006, 399103589, 379961969 |
| hied | lingxidiag | Others | F20 | 14 | 387302774, 397927451, 317513157, 361989707, 372927830 |
| hied | lingxidiag | Others | F42 | 11 | 347729413, 386951485, 304692970, 331114130, 362317955 |
| hied | lingxidiag | F32 | F41 | 11 | 359213312, 309460138, 379611968, 329640791, 303758025 |
| hied | lingxidiag | F32 | F51 | 10 | 312389408, 321077019, 314915003, 399537463, 364759893 |
| hied | lingxidiag | Others | F41 | 10 | 376197379, 351228828, 341804915, 304404409, 345377956 |
| hied | lingxidiag | Others | F43 | 10 | 305273450, 335538152, 352801207, 330091430, 355975065 |

## Timing Statistics

- Total wall time: 12m
- Total evaluated cases: 1000
- Overall cases/sec: 1.360

| Mode/Dataset | Elapsed | Cases/Sec | Avg Sec/Case | Batch Count |
|---|---:|---:|---:|---:|
| hied:lingxidiag | 12m | 1.360 | 0.735 | 10 |
