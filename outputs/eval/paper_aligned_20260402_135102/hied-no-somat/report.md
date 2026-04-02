# CultureDx Full Evaluation Report

## Config Summary

- Generated at: 2026-04-02T11:14:51.005702+00:00
- Config files: configs/base.yaml, configs/hied.yaml, configs/vllm_awq.yaml, configs/targets/lingxidiag_12class.yaml, configs/evidence.yaml, outputs/eval/paper_aligned_20260402_135102/hied-no-somat/eval_config.yaml
- Modes: hied
- Datasets: lingxidiag
- Model: Qwen/Qwen3-32B-AWQ
- Adapter path: not provided
- Evidence: enabled
- Somatization: disabled
- Max cases per dataset: all

## Overall Metrics

| Scope | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| global | 1000 | 0.3960 | 0.6670 | 0.0240 | 0.7799 | 0.1520 | 0.0000 |
| hied | 1000 | 0.3960 | 0.6670 | 0.0240 | 0.7799 | 0.1520 | 0.0000 |

## Per-Dataset Comparison

| Mode/Dataset | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate | Elapsed | Cases/Sec |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hied:lingxidiag | 1000 | 0.3960 | 0.6670 | 0.0240 | 0.7799 | 0.1520 | 0.0000 | 14m | 1.214 |

## Per-Disorder Metrics

| Mode | Disorder | Support | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| hied | F20 | 5 | 0.1667 | 0.8000 | 0.2759 |
| hied | F31 | 9 | 0.0000 | 0.0000 | 0.0000 |
| hied | F32 | 370 | 0.4355 | 0.9405 | 0.5954 |
| hied | F39 | 63 | 0.0625 | 0.0952 | 0.0755 |
| hied | F41 | 394 | 0.4278 | 0.7589 | 0.5471 |
| hied | F42 | 36 | 0.1156 | 0.4722 | 0.1858 |
| hied | F43 | 15 | 0.0165 | 0.7333 | 0.0322 |
| hied | F45 | 16 | 0.0000 | 0.0000 | 0.0000 |
| hied | F51 | 43 | 0.0456 | 1.0000 | 0.0871 |
| hied | F98 | 47 | 0.0682 | 0.0638 | 0.0659 |
| hied | Others | 93 | 0.0000 | 0.0000 | 0.0000 |

## Top Error Patterns

| Mode | Dataset | Gold | Predicted | Count | Example Case IDs |
|---|---|---|---|---:|---|
| hied | lingxidiag | F41 | F32 | 204 | 341328894, 329606499, 305328637, 355727279, 335985565 |
| hied | lingxidiag | F39 | F32 | 45 | 327826586, 368679677, 342949614, 398487934, 371401723 |
| hied | lingxidiag | F41 | F51 | 38 | 377662897, 380913193, 354219828, 329547625, 344013412 |
| hied | lingxidiag | Others | F32 | 37 | 344699340, 371726537, 351228828, 391104352, 383845546 |
| hied | lingxidiag | F41 | F43 | 25 | 393761475, 397700349, 388730013, 340563038, 324090242 |
| hied | lingxidiag | F41 | F42 | 24 | 353485011, 315846324, 387726394, 387949900, 319574587 |
| hied | lingxidiag | F32 | F51 | 21 | 303364596, 312389408, 321077019, 346998154, 356498183 |
| hied | lingxidiag | F51 | F32 | 19 | 373267151, 387133350, 366260309, 372953321, 379479487 |
| hied | lingxidiag | F32 | F43 | 18 | 359213312, 378984052, 366918268, 346313917, 372137789 |
| hied | lingxidiag | F98 | F32 | 17 | 336521777, 321037752, 316834006, 399103589, 379961969 |
| hied | lingxidiag | Others | F20 | 15 | 383925853, 387302774, 397927451, 317513157, 361989707 |
| hied | lingxidiag | Others | F42 | 12 | 347729413, 386951485, 304692970, 331114130, 303683319 |
| hied | lingxidiag | Others | F43 | 12 | 376197379, 340282544, 305273450, 335538152, 352801207 |
| hied | lingxidiag | F32 | F41 | 12 | 311456028, 361781918, 362641875, 333030816, 334446954 |
| hied | lingxidiag | F43 | F32 | 10 | 337522433, 395985056, 329984067, 313602441, 378540759 |

## Timing Statistics

- Total wall time: 14m
- Total evaluated cases: 1000
- Overall cases/sec: 1.210

| Mode/Dataset | Elapsed | Cases/Sec | Avg Sec/Case | Batch Count |
|---|---:|---:|---:|---:|
| hied:lingxidiag | 14m | 1.214 | 0.824 | 10 |
