# CultureDx Full Evaluation Report

## Config Summary

- Generated at: 2026-04-02T18:39:20.055964+00:00
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
| global | 1000 | 0.4430 | 0.4430 | 0.3930 | 0.5825 | 0.1710 | 0.0000 |
| hied | 1000 | 0.4430 | 0.4430 | 0.3930 | 0.5825 | 0.1710 | 0.0000 |

## Per-Dataset Comparison

| Mode/Dataset | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate | Elapsed | Cases/Sec |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hied:lingxidiag | 1000 | 0.4430 | 0.4430 | 0.3930 | 0.5825 | 0.1710 | 0.0000 | 41m | 0.407 |

## Per-Disorder Metrics

| Mode | Disorder | Support | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| hied | F20 | 5 | 0.0500 | 0.8000 | 0.0941 |
| hied | F31 | 9 | 0.0000 | 0.0000 | 0.0000 |
| hied | F32 | 370 | 0.5125 | 0.8324 | 0.6344 |
| hied | F39 | 63 | 0.0000 | 0.0000 | 0.0000 |
| hied | F41 | 394 | 0.6310 | 0.2690 | 0.3772 |
| hied | F42 | 36 | 0.2459 | 0.4167 | 0.3093 |
| hied | F43 | 15 | 0.0909 | 0.0667 | 0.0769 |
| hied | F45 | 16 | 0.2500 | 0.0625 | 0.1000 |
| hied | F51 | 43 | 0.1127 | 0.1860 | 0.1404 |
| hied | F98 | 47 | 0.0000 | 0.0000 | 0.0000 |
| hied | Others | 93 | 0.0000 | 0.0000 | 0.0000 |

## Top Error Patterns

| Mode | Dataset | Gold | Predicted | Count | Example Case IDs |
|---|---|---|---|---:|---|
| hied | lingxidiag | F41 | F32 | 166 | 341328894, 329606499, 355727279, 397700349, 335985565 |
| hied | lingxidiag | F39 | F32 | 40 | 327826586, 368679677, 342949614, 398487934, 371401723 |
| hied | lingxidiag | F41 | F51 | 39 | 318518739, 377662897, 354219828, 382615327, 319673363 |
| hied | lingxidiag | Others | F32 | 34 | 344699340, 371726537, 376197379, 351228828, 391104352 |
| hied | lingxidiag | Others | F20 | 26 | 383925853, 387302774, 397927451, 376288406, 317513157 |
| hied | lingxidiag | F41 | F20 | 23 | 354203641, 316244279, 303319935, 366264963, 385620603 |
| hied | lingxidiag | F32 | F41 | 21 | 321077019, 372632464, 368042020, 366918268, 349575167 |
| hied | lingxidiag | F98 | F32 | 20 | 309444601, 336521777, 321037752, 316834006, 399103589 |
| hied | lingxidiag | F41 | F42 | 17 | 353485011, 387726394, 375065461, 310152130, 361559752 |
| hied | lingxidiag | Others | F41 | 15 | 383579251, 304692970, 341804915, 387132598, 347255679 |
| hied | lingxidiag | F32 | F20 | 15 | 370136374, 365096401, 353953724, 396605235, 329824525 |
| hied | lingxidiag | F51 | F32 | 14 | 373267151, 387133350, 366260309, 379479487, 326222823 |
| hied | lingxidiag | F32 | F51 | 11 | 312389408, 359213312, 378576998, 333030816, 303758025 |
| hied | lingxidiag | F51 | F41 | 11 | 348839819, 380136533, 396857182, 379332969, 313232274 |
| hied | lingxidiag | F32 | F42 | 9 | 369825193, 322845072, 336404489, 319509963, 345655884 |

## Timing Statistics

- Total wall time: 41m
- Total evaluated cases: 1000
- Overall cases/sec: 0.407

| Mode/Dataset | Elapsed | Cases/Sec | Avg Sec/Case | Batch Count |
|---|---:|---:|---:|---:|
| hied:lingxidiag | 41m | 0.407 | 2.457 | 20 |
