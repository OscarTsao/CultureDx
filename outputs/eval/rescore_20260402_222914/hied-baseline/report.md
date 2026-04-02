# CultureDx Full Evaluation Report

## Config Summary

- Generated at: 2026-04-02T14:30:36.233782+00:00
- Config files: configs/base.yaml, configs/hied.yaml, configs/vllm_awq.yaml, configs/targets/lingxidiag_12class.yaml, outputs/eval/rescore_20260402_222914/hied-baseline/eval_config.yaml
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
| global | 753 | 0.3094 | 0.5498 | 0.0319 | 0.7846 | 0.1327 | 0.0000 |
| hied | 753 | 0.3094 | 0.5498 | 0.0319 | 0.7846 | 0.1327 | 0.0000 |

## Per-Dataset Comparison

| Mode/Dataset | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate | Elapsed | Cases/Sec |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hied:lingxidiag | 753 | 0.3094 | 0.5498 | 0.0319 | 0.7846 | 0.1327 | 0.0000 | 1m | 16.133 |

## Per-Disorder Metrics

| Mode | Disorder | Support | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| hied | F20 | 5 | 0.1250 | 0.2000 | 0.1538 |
| hied | F31 | 8 | 0.0000 | 0.0000 | 0.0000 |
| hied | F32 | 289 | 0.4638 | 0.7543 | 0.5744 |
| hied | F39 | 45 | 0.0435 | 0.0444 | 0.0440 |
| hied | F41 | 287 | 0.4477 | 0.5819 | 0.5061 |
| hied | F42 | 27 | 0.1340 | 0.4815 | 0.2097 |
| hied | F43 | 11 | 0.0171 | 0.4545 | 0.0329 |
| hied | F45 | 11 | 0.0000 | 0.0000 | 0.0000 |
| hied | F51 | 31 | 0.0450 | 0.9355 | 0.0858 |
| hied | F98 | 39 | 0.1579 | 0.0769 | 0.1034 |
| hied | Others | 67 | 0.0000 | 0.0000 | 0.0000 |

## Top Error Patterns

| Mode | Dataset | Gold | Predicted | Count | Example Case IDs |
|---|---|---|---|---:|---|
| hied | lingxidiag | F41 | F32 | 105 | 318518739, 344013412, 388730013, 317090766, 334814081 |
| hied | lingxidiag | F41 | F51 | 69 | 377662897, 397700349, 354219828, 329547625, 320669626 |
| hied | lingxidiag | F32 | F51 | 65 | 303364596, 312389408, 346998154, 359213312, 369867441 |
| hied | lingxidiag | F41 | F43 | 25 | 324224056, 393761475, 335985565, 391945652, 363300223 |
| hied | lingxidiag | F39 | F32 | 24 | 342949614, 371401723, 350575983, 357343954, 330014648 |
| hied | lingxidiag | Others | F32 | 16 | 371726537, 391104352, 383845546, 340282544, 321179204 |
| hied | lingxidiag | Others | F51 | 16 | 376197379, 314631661, 351228828, 362317955, 347255679 |
| hied | lingxidiag | F32 | F43 | 16 | 303895252, 307020057, 346313917, 336404489, 379645537 |
| hied | lingxidiag | F41 | F42 | 15 | 353485011, 387726394, 370352292, 319574587, 310152130 |
| hied | lingxidiag | F32 | F41 | 13 | 321077019, 309460138, 333610168, 379611968, 358561077 |
| hied | lingxidiag | F41 | F39 | 13 | 314878848, 314036143, 368315761, 378952793, 326269413 |
| hied | lingxidiag | Others | F41 | 13 | 387302774, 376288406, 317513157, 321679684, 304404409 |
| hied | lingxidiag | F32 | F39 | 12 | 341042297, 338619013, 398106929, 395706701, 354205330 |
| hied | lingxidiag | F98 | F32 | 10 | 309444601, 336521777, 316834006, 399103589, 379961969 |
| hied | lingxidiag | F51 | F32 | 9 | 348839819, 380136533, 373267151, 366260309, 379479487 |

## Timing Statistics

- Total wall time: 1m
- Total evaluated cases: 753
- Overall cases/sec: 12.132

| Mode/Dataset | Elapsed | Cases/Sec | Avg Sec/Case | Batch Count |
|---|---:|---:|---:|---:|
| hied:lingxidiag | 1m | 16.133 | 0.062 | 10 |
