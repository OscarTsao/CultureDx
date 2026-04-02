# CultureDx Full Evaluation Report

## Config Summary

- Generated at: 2026-04-02T05:58:05.702974+00:00
- Config files: configs/base.yaml, configs/vllm_awq.yaml, configs/targets/lingxidiag_12class.yaml, outputs/eval/paper_aligned_20260402_135102/single-baseline/eval_config.yaml
- Modes: single
- Datasets: lingxidiag
- Model: Qwen/Qwen3-32B-AWQ
- Adapter path: not provided
- Evidence: disabled
- Somatization: disabled
- Max cases per dataset: all

## Overall Metrics

| Scope | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| global | 992 | 0.4637 | 0.6069 | 0.0151 | 0.7129 | 0.1754 | 0.0000 |
| single | 992 | 0.4637 | 0.6069 | 0.0151 | 0.7129 | 0.1754 | 0.0000 |

## Per-Dataset Comparison

| Mode/Dataset | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate | Elapsed | Cases/Sec |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| single:lingxidiag | 992 | 0.4637 | 0.6069 | 0.0151 | 0.7129 | 0.1754 | 0.0000 | 7m | 2.350 |

## Per-Disorder Metrics

| Mode | Disorder | Support | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| single | F20 | 5 | 0.1290 | 0.8000 | 0.2222 |
| single | F31 | 9 | 0.1250 | 0.2222 | 0.1600 |
| single | F32 | 370 | 0.4523 | 0.8973 | 0.6014 |
| single | F33 | 0 | 0.0000 | 0.0000 | 0.0000 |
| single | F39 | 63 | 0.0000 | 0.0000 | 0.0000 |
| single | F40 | 0 | 0.0000 | 0.0000 | 0.0000 |
| single | F41 | 394 | 0.4751 | 0.5812 | 0.5228 |
| single | F42 | 36 | 0.2321 | 0.3611 | 0.2826 |
| single | F43 | 15 | 0.0000 | 0.0000 | 0.0000 |
| single | F45 | 16 | 0.0400 | 0.0625 | 0.0488 |
| single | F51 | 43 | 0.0682 | 0.0698 | 0.0690 |
| single | F98 | 47 | 0.0000 | 0.0000 | 0.0000 |
| single | Others | 85 | 0.0947 | 0.4000 | 0.1532 |

## Top Error Patterns

| Mode | Dataset | Gold | Predicted | Count | Example Case IDs |
|---|---|---|---|---:|---|
| single | lingxidiag | F41 | F32 | 166 | 318518739, 341328894, 377662897, 329606499, 355727279 |
| single | lingxidiag | F41 | F40 | 45 | 374577341, 300493869, 380913193, 393761475, 388730013 |
| single | lingxidiag | F39 | F32 | 39 | 327826586, 368679677, 342949614, 305956530, 398487934 |
| single | lingxidiag | Others | F32 | 28 | 371726537, 351228828, 391104352, 383845546, 340282544 |
| single | lingxidiag | F98 | F32 | 21 | 309444601, 336521777, 321037752, 316834006, 399103589 |
| single | lingxidiag | Others | F20 | 20 | 383925853, 387302774, 397927451, 376288406, 317513157 |
| single | lingxidiag | F41 | F33 | 20 | 334085925, 391945652, 380733404, 342584665, 332020997 |
| single | lingxidiag | F51 | F32 | 19 | 348839819, 380136533, 387133350, 366260309, 372953321 |
| single | lingxidiag | F32 | F33 | 17 | 303895252, 333610168, 329640791, 361781918, 362641875 |
| single | lingxidiag | F32 | F41 | 15 | 338463663, 366918268, 308925436, 345855766, 385432303 |
| single | lingxidiag | Others | F41 | 12 | 314631661, 383579251, 304692970, 341804915, 362317955 |
| single | lingxidiag | F51 | F41 | 11 | 396857182, 313232274, 377593076, 395495143, 356998799 |
| single | lingxidiag | F41 | F42 | 11 | 353485011, 385586556, 310152130, 384544121, 378742214 |
| single | lingxidiag | F42 | F41 | 9 | 339178683, 397016069, 322387305, 300689279, 357531958 |
| single | lingxidiag | F43 | F32 | 8 | 395985056, 329984067, 313602441, 347971142, 364202902 |

## Timing Statistics

- Total wall time: 7m
- Total evaluated cases: 992
- Overall cases/sec: 2.349

| Mode/Dataset | Elapsed | Cases/Sec | Avg Sec/Case | Batch Count |
|---|---:|---:|---:|---:|
| single:lingxidiag | 7m | 2.350 | 0.426 | 10 |
