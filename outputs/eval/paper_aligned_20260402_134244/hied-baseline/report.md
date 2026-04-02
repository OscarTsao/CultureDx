# CultureDx Full Evaluation Report

## Config Summary

- Generated at: 2026-04-02T09:38:17.862172+00:00
- Config files: configs/base.yaml, configs/hied.yaml, configs/vllm_awq.yaml, configs/targets/lingxidiag_12class.yaml, outputs/eval/paper_aligned_20260402_134244/hied-baseline/eval_config.yaml
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
| global | 992 | 0.3982 | 0.6895 | 0.0202 | 0.7755 | 0.1283 | 0.0000 |
| hied | 992 | 0.3982 | 0.6895 | 0.0202 | 0.7755 | 0.1283 | 0.0000 |

## Per-Dataset Comparison

| Mode/Dataset | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate | Elapsed | Cases/Sec |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hied:lingxidiag | 992 | 0.3982 | 0.6895 | 0.0202 | 0.7755 | 0.1283 | 0.0000 | 3h 56m | 0.070 |

## Per-Disorder Metrics

| Mode | Disorder | Support | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| hied | F20 | 5 | 0.1667 | 0.8000 | 0.2759 |
| hied | F22 | 0 | 0.0000 | 0.0000 | 0.0000 |
| hied | F31 | 9 | 0.0000 | 0.0000 | 0.0000 |
| hied | F32 | 370 | 0.4375 | 0.9459 | 0.5983 |
| hied | F33 | 0 | 0.0000 | 0.0000 | 0.0000 |
| hied | F39 | 63 | 0.0000 | 0.0000 | 0.0000 |
| hied | F40 | 0 | 0.0000 | 0.0000 | 0.0000 |
| hied | F41 | 394 | 0.4517 | 0.7716 | 0.5698 |
| hied | F42 | 36 | 0.1111 | 0.4722 | 0.1799 |
| hied | F43 | 15 | 0.0160 | 0.7333 | 0.0313 |
| hied | F45 | 16 | 0.0000 | 0.0000 | 0.0000 |
| hied | F51 | 43 | 0.0456 | 1.0000 | 0.0871 |
| hied | F98 | 47 | 0.0000 | 0.0000 | 0.0000 |
| hied | Others | 85 | 0.0000 | 0.0000 | 0.0000 |

## Top Error Patterns

| Mode | Dataset | Gold | Predicted | Count | Example Case IDs |
|---|---|---|---|---:|---|
| hied | lingxidiag | F41 | F32 | 237 | 374577341, 318518739, 329606499, 355727279, 335985565 |
| hied | lingxidiag | F39 | F32 | 49 | 327826586, 368679677, 342949614, 398487934, 371401723 |
| hied | lingxidiag | F41 | F43 | 27 | 341328894, 324224056, 340563038, 395309894, 324090242 |
| hied | lingxidiag | F41 | F42 | 25 | 353485011, 315846324, 387726394, 370352292, 319574587 |
| hied | lingxidiag | F41 | F51 | 21 | 377662897, 380913193, 397700349, 354219828, 329547625 |
| hied | lingxidiag | F51 | F32 | 20 | 348839819, 380136533, 373267151, 387133350, 366260309 |
| hied | lingxidiag | Others | F32 | 19 | 371726537, 391104352, 387132598, 321179204, 347255679 |
| hied | lingxidiag | F98 | F32 | 19 | 309444601, 336521777, 321037752, 399103589, 379961969 |
| hied | lingxidiag | F32 | F43 | 17 | 378984052, 307020057, 349575167, 309099307, 325425821 |
| hied | lingxidiag | Others | F20 | 14 | 383925853, 397927451, 317513157, 372927830, 351219844 |
| hied | lingxidiag | Others | F51 | 14 | 314631661, 351228828, 383579251, 362317955, 338464039 |
| hied | lingxidiag | Others | F42 | 12 | 347729413, 386951485, 341804915, 331114130, 311568500 |
| hied | lingxidiag | Others | F43 | 12 | 383845546, 340282544, 305273450, 335538152, 346213726 |
| hied | lingxidiag | F32 | F51 | 10 | 312389408, 321077019, 356498183, 375048974, 343215303 |
| hied | lingxidiag | F43 | F32 | 9 | 337522433, 395985056, 329984067, 313602441, 347971142 |

## Timing Statistics

- Total wall time: 3h 56m
- Total evaluated cases: 992
- Overall cases/sec: 0.070

| Mode/Dataset | Elapsed | Cases/Sec | Avg Sec/Case | Batch Count |
|---|---:|---:|---:|---:|
| hied:lingxidiag | 3h 56m | 0.070 | 14.246 | 10 |
