# CultureDx Full Evaluation Report

## Config Summary

- Generated at: 2026-04-02T09:37:57.485230+00:00
- Config files: configs/base.yaml, configs/hied.yaml, configs/vllm_awq.yaml, configs/targets/lingxidiag_12class.yaml, configs/evidence.yaml, configs/reasoning.yaml, outputs/eval/paper_aligned_20260402_135102/hied-full-pipeline/eval_config.yaml
- Modes: hied
- Datasets: lingxidiag
- Model: Qwen/Qwen3-32B-AWQ
- Adapter path: not provided
- Evidence: enabled
- Somatization: enabled
- Max cases per dataset: all

## Overall Metrics

| Scope | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| global | 991 | 0.3744 | 0.6690 | 0.0222 | 0.7691 | 0.1215 | 0.0000 |
| hied | 991 | 0.3744 | 0.6690 | 0.0222 | 0.7691 | 0.1215 | 0.0000 |

## Per-Dataset Comparison

| Mode/Dataset | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate | Elapsed | Cases/Sec |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hied:lingxidiag | 991 | 0.3744 | 0.6690 | 0.0222 | 0.7691 | 0.1215 | 0.0000 | 3h 40m | 0.075 |

## Per-Disorder Metrics

| Mode | Disorder | Support | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| hied | F20 | 5 | 0.1667 | 0.8000 | 0.2759 |
| hied | F22 | 0 | 0.0000 | 0.0000 | 0.0000 |
| hied | F31 | 9 | 0.0000 | 0.0000 | 0.0000 |
| hied | F32 | 370 | 0.4433 | 0.9297 | 0.6003 |
| hied | F33 | 0 | 0.0000 | 0.0000 | 0.0000 |
| hied | F39 | 63 | 0.0000 | 0.0000 | 0.0000 |
| hied | F40 | 0 | 0.0000 | 0.0000 | 0.0000 |
| hied | F41 | 393 | 0.4443 | 0.7405 | 0.5553 |
| hied | F42 | 36 | 0.1339 | 0.4722 | 0.2086 |
| hied | F43 | 15 | 0.0169 | 0.6667 | 0.0331 |
| hied | F45 | 16 | 0.0000 | 0.0000 | 0.0000 |
| hied | F51 | 43 | 0.0471 | 1.0000 | 0.0901 |
| hied | F98 | 47 | 0.0000 | 0.0000 | 0.0000 |
| hied | Others | 85 | 0.0000 | 0.0000 | 0.0000 |

## Top Error Patterns

| Mode | Dataset | Gold | Predicted | Count | Example Case IDs |
|---|---|---|---|---:|---|
| hied | lingxidiag | F41 | F32 | 133 | 318518739, 305328637, 335985565, 320669626, 314878848 |
| hied | lingxidiag | F41 | F51 | 91 | 377662897, 380913193, 329606499, 397700349, 365148198 |
| hied | lingxidiag | F32 | F51 | 64 | 303364596, 312389408, 321077019, 346998154, 369867441 |
| hied | lingxidiag | F39 | F32 | 37 | 327826586, 368679677, 342949614, 398487934, 371401723 |
| hied | lingxidiag | F41 | F43 | 24 | 341328894, 379652943, 340563038, 354203641, 393930509 |
| hied | lingxidiag | F32 | F41 | 22 | 359213312, 361781918, 362641875, 349630064, 349575167 |
| hied | lingxidiag | F41 | F42 | 21 | 353485011, 315846324, 319574587, 310152130, 384544121 |
| hied | lingxidiag | Others | F32 | 20 | 371726537, 376197379, 351228828, 391104352, 383845546 |
| hied | lingxidiag | F32 | F43 | 17 | 349034373, 338463663, 366918268, 346313917, 372137789 |
| hied | lingxidiag | Others | F42 | 15 | 347729413, 386951485, 304692970, 341804915, 331114130 |
| hied | lingxidiag | Others | F20 | 15 | 383925853, 397927451, 317513157, 361989707, 372927830 |
| hied | lingxidiag | Others | F51 | 15 | 314631661, 383579251, 340282544, 305273450, 338464039 |
| hied | lingxidiag | F98 | F32 | 14 | 321037752, 316834006, 399103589, 379961969, 368417566 |
| hied | lingxidiag | F41 | F40 | 9 | 300493869, 393761475, 308086484, 387949900, 323525666 |
| hied | lingxidiag | F51 | F32 | 9 | 348839819, 380136533, 387133350, 366260309, 379479487 |

## Timing Statistics

- Total wall time: 3h 40m
- Total evaluated cases: 991
- Overall cases/sec: 0.075

| Mode/Dataset | Elapsed | Cases/Sec | Avg Sec/Case | Batch Count |
|---|---:|---:|---:|---:|
| hied:lingxidiag | 3h 40m | 0.075 | 13.295 | 10 |
