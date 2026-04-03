# CultureDx Full Evaluation Report

## Config Summary

- Generated at: 2026-04-03T04:46:03.407422+00:00
- Config files: configs/base.yaml, configs/vllm_32b.yaml, configs/vllm_awq.yaml, configs/hied_dtv.yaml
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
| global | 1000 | 0.3920 | 0.3920 | 0.3490 | 0.6300 | 0.1801 | 0.0000 |
| hied | 1000 | 0.3920 | 0.3920 | 0.3490 | 0.6300 | 0.1801 | 0.0000 |

## Per-Dataset Comparison

| Mode/Dataset | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate | Elapsed | Cases/Sec |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hied:lingxidiag | 1000 | 0.3920 | 0.3920 | 0.3490 | 0.6300 | 0.1801 | 0.0000 | 35m | 0.481 |

## Per-Disorder Metrics

| Mode | Disorder | Support | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| hied | F20 | 5 | 0.0255 | 1.0000 | 0.0498 |
| hied | F31 | 9 | 0.0000 | 0.0000 | 0.0000 |
| hied | F32 | 370 | 0.4922 | 0.6838 | 0.5724 |
| hied | F39 | 63 | 0.0000 | 0.0000 | 0.0000 |
| hied | F41 | 394 | 0.6124 | 0.2766 | 0.3811 |
| hied | F42 | 36 | 0.2703 | 0.2778 | 0.2740 |
| hied | F43 | 15 | 0.2857 | 0.1333 | 0.1818 |
| hied | F45 | 16 | 0.2500 | 0.0625 | 0.1000 |
| hied | F51 | 43 | 0.2000 | 0.2791 | 0.2330 |
| hied | F98 | 47 | 0.0000 | 0.0000 | 0.0000 |
| hied | Others | 93 | 0.0000 | 0.0000 | 0.0000 |

## Top Error Patterns

| Mode | Dataset | Gold | Predicted | Count | Example Case IDs |
|---|---|---|---|---:|---|
| hied | lingxidiag | F41 | F32 | 158 | 341328894, 329606499, 355727279, 397700349, 349524800 |
| hied | lingxidiag | F32 | F20 | 76 | 350352506, 341042297, 312389408, 303895252, 358313639 |
| hied | lingxidiag | F41 | F20 | 47 | 380913193, 335985565, 354219828, 345082346, 354203641 |
| hied | lingxidiag | F39 | F32 | 36 | 327826586, 368679677, 342949614, 398487934, 318024484 |
| hied | lingxidiag | Others | F20 | 33 | 344699340, 387302774, 386951485, 397927451, 376288406 |
| hied | lingxidiag | Others | F32 | 28 | 371726537, 383925853, 351228828, 391104352, 383845546 |
| hied | lingxidiag | F41 | F51 | 26 | 318518739, 354496307, 382615327, 391945652, 371811674 |
| hied | lingxidiag | F32 | F41 | 24 | 372632464, 366918268, 361781918, 349575167, 334446954 |
| hied | lingxidiag | Others | F41 | 16 | 376197379, 383579251, 304692970, 304404409, 335538152 |
| hied | lingxidiag | F98 | F32 | 13 | 309444601, 336521777, 321037752, 316834006, 399103589 |
| hied | lingxidiag | F41 | F42 | 13 | 353485011, 385586556, 310152130, 384544121, 338304783 |
| hied | lingxidiag | F39 | F20 | 12 | 377956208, 371401723, 360136896, 366688675, 383465953 |
| hied | lingxidiag | F51 | F41 | 11 | 380136533, 396857182, 379332969, 313232274, 377593076 |
| hied | lingxidiag | F51 | F32 | 9 | 373267151, 366260309, 379479487, 374496257, 300653771 |
| hied | lingxidiag | F98 | F20 | 9 | 379961969, 374602774, 368417566, 303669869, 306959689 |

## Timing Statistics

- Total wall time: 35m
- Total evaluated cases: 1000
- Overall cases/sec: 0.481

| Mode/Dataset | Elapsed | Cases/Sec | Avg Sec/Case | Batch Count |
|---|---:|---:|---:|---:|
| hied:lingxidiag | 35m | 0.481 | 2.078 | 20 |
