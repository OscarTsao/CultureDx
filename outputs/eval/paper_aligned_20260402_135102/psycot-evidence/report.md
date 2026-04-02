# CultureDx Full Evaluation Report

## Config Summary

- Generated at: 2026-04-02T11:17:21.642269+00:00
- Config files: configs/base.yaml, configs/psycot.yaml, configs/vllm_awq.yaml, configs/targets/lingxidiag_12class.yaml, configs/evidence.yaml, outputs/eval/paper_aligned_20260402_135102/psycot-evidence/eval_config.yaml
- Modes: psycot
- Datasets: lingxidiag
- Model: Qwen/Qwen3-32B-AWQ
- Adapter path: not provided
- Evidence: enabled
- Somatization: enabled
- Max cases per dataset: all

## Overall Metrics

| Scope | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| global | 1000 | 0.2230 | 0.5140 | 0.0320 | 0.7617 | 0.1443 | 0.0000 |
| psycot | 1000 | 0.2230 | 0.5140 | 0.0320 | 0.7617 | 0.1443 | 0.0000 |

## Per-Dataset Comparison

| Mode/Dataset | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate | Elapsed | Cases/Sec |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| psycot:lingxidiag | 1000 | 0.2230 | 0.5140 | 0.0320 | 0.7617 | 0.1443 | 0.0000 | 2m | 6.806 |

## Per-Disorder Metrics

| Mode | Disorder | Support | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| psycot | F20 | 5 | 0.2222 | 0.8000 | 0.3478 |
| psycot | F31 | 9 | 0.0000 | 0.0000 | 0.0000 |
| psycot | F32 | 370 | 0.4426 | 0.9162 | 0.5968 |
| psycot | F39 | 63 | 0.0763 | 0.1429 | 0.0994 |
| psycot | F41 | 394 | 0.5345 | 0.3147 | 0.3962 |
| psycot | F42 | 36 | 0.1829 | 0.4167 | 0.2542 |
| psycot | F43 | 15 | 0.0000 | 0.0000 | 0.0000 |
| psycot | F45 | 16 | 0.0000 | 0.0000 | 0.0000 |
| psycot | F51 | 43 | 0.0458 | 0.9767 | 0.0874 |
| psycot | F98 | 47 | 0.0714 | 0.0638 | 0.0674 |
| psycot | Others | 93 | 0.0000 | 0.0000 | 0.0000 |

## Top Error Patterns

| Mode | Dataset | Gold | Predicted | Count | Example Case IDs |
|---|---|---|---|---:|---|
| psycot | lingxidiag | F41 | F51 | 211 | 341328894, 377662897, 324224056, 380913193, 355727279 |
| psycot | lingxidiag | F32 | F51 | 187 | 303364596, 388559461, 312389408, 358313639, 381110368 |
| psycot | lingxidiag | F41 | F32 | 52 | 335985565, 391945652, 363300223, 399980638, 385586556 |
| psycot | lingxidiag | Others | F51 | 48 | 344699340, 376197379, 314631661, 351228828, 383579251 |
| psycot | lingxidiag | F32 | F39 | 32 | 350352506, 341042297, 331016450, 371125111, 362752317 |
| psycot | lingxidiag | F41 | F39 | 28 | 314878848, 322362191, 399312874, 314036143, 368315761 |
| psycot | lingxidiag | F39 | F51 | 22 | 327826586, 368679677, 342949614, 305956530, 367666192 |
| psycot | lingxidiag | F39 | F32 | 15 | 371401723, 360136896, 350575983, 330014648, 366688675 |
| psycot | lingxidiag | Others | F41 | 14 | 383925853, 387302774, 376288406, 304692970, 304404409 |
| psycot | lingxidiag | F41 | F42 | 13 | 353485011, 387726394, 387949900, 310152130, 384544121 |
| psycot | lingxidiag | Others | F32 | 11 | 371726537, 391104352, 321679684, 365074057, 341775516 |
| psycot | lingxidiag | F39 | F41 | 11 | 377956208, 357343954, 318882513, 358853698, 300370328 |
| psycot | lingxidiag | F98 | F51 | 10 | 309444601, 399103589, 303669869, 399753358, 374066930 |
| psycot | lingxidiag | F42 | F51 | 10 | 339178683, 363112097, 397016069, 322387305, 300689279 |
| psycot | lingxidiag | F32 | F98 | 9 | 304891732, 324712168, 375048974, 374053247, 365036675 |

## Timing Statistics

- Total wall time: 2m
- Total evaluated cases: 1000
- Overall cases/sec: 6.695

| Mode/Dataset | Elapsed | Cases/Sec | Avg Sec/Case | Batch Count |
|---|---:|---:|---:|---:|
| psycot:lingxidiag | 2m | 6.806 | 0.147 | 10 |
