# CultureDx Full Evaluation Report

## Config Summary

- Generated at: 2026-04-02T11:01:03.240908+00:00
- Config files: configs/base.yaml, configs/hied.yaml, configs/vllm_awq.yaml, configs/targets/lingxidiag_12class.yaml, configs/evidence.yaml, outputs/eval/paper_aligned_20260402_135102/hied-evidence/eval_config.yaml
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
| global | 1000 | 0.3770 | 0.6620 | 0.0240 | 0.7799 | 0.1544 | 0.0000 |
| hied | 1000 | 0.3770 | 0.6620 | 0.0240 | 0.7799 | 0.1544 | 0.0000 |

## Per-Dataset Comparison

| Mode/Dataset | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate | Elapsed | Cases/Sec |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hied:lingxidiag | 1000 | 0.3770 | 0.6620 | 0.0240 | 0.7799 | 0.1544 | 0.0000 | 18m | 0.920 |

## Per-Disorder Metrics

| Mode | Disorder | Support | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| hied | F20 | 5 | 0.1600 | 0.8000 | 0.2667 |
| hied | F31 | 9 | 0.0000 | 0.0000 | 0.0000 |
| hied | F32 | 370 | 0.4350 | 0.9405 | 0.5949 |
| hied | F39 | 63 | 0.0865 | 0.1429 | 0.1078 |
| hied | F41 | 394 | 0.4275 | 0.7563 | 0.5463 |
| hied | F42 | 36 | 0.1149 | 0.4722 | 0.1848 |
| hied | F43 | 15 | 0.0164 | 0.7333 | 0.0322 |
| hied | F45 | 16 | 0.0000 | 0.0000 | 0.0000 |
| hied | F51 | 43 | 0.0454 | 1.0000 | 0.0869 |
| hied | F98 | 47 | 0.0682 | 0.0638 | 0.0659 |
| hied | Others | 93 | 0.0000 | 0.0000 | 0.0000 |

## Top Error Patterns

| Mode | Dataset | Gold | Predicted | Count | Example Case IDs |
|---|---|---|---|---:|---|
| hied | lingxidiag | F41 | F32 | 206 | 318518739, 341328894, 329606499, 305328637, 355727279 |
| hied | lingxidiag | F39 | F32 | 45 | 368679677, 342949614, 398487934, 371401723, 318024484 |
| hied | lingxidiag | Others | F32 | 40 | 344699340, 371726537, 376197379, 314631661, 351228828 |
| hied | lingxidiag | F41 | F51 | 35 | 377662897, 380913193, 397700349, 354219828, 329547625 |
| hied | lingxidiag | F41 | F43 | 34 | 393761475, 340563038, 300484187, 324090242, 342584665 |
| hied | lingxidiag | F32 | F43 | 25 | 378984052, 366918268, 315705131, 307020057, 308845940 |
| hied | lingxidiag | F41 | F42 | 25 | 353485011, 315846324, 387726394, 387949900, 319574587 |
| hied | lingxidiag | F32 | F51 | 23 | 303364596, 312389408, 321077019, 346998154, 356498183 |
| hied | lingxidiag | F98 | F32 | 18 | 336521777, 321037752, 399103589, 379961969, 368417566 |
| hied | lingxidiag | F51 | F32 | 17 | 348839819, 380136533, 373267151, 387133350, 366260309 |
| hied | lingxidiag | F32 | F41 | 16 | 359213312, 361781918, 333030816, 303758025, 334446954 |
| hied | lingxidiag | Others | F20 | 14 | 387302774, 397927451, 317513157, 361989707, 372927830 |
| hied | lingxidiag | Others | F43 | 12 | 340282544, 305273450, 335538152, 347255679, 352801207 |
| hied | lingxidiag | Others | F42 | 10 | 347729413, 386951485, 376288406, 331114130, 303683319 |
| hied | lingxidiag | F43 | F32 | 9 | 337522433, 395985056, 313602441, 378540759, 347971142 |

## Timing Statistics

- Total wall time: 18m
- Total evaluated cases: 1000
- Overall cases/sec: 0.918

| Mode/Dataset | Elapsed | Cases/Sec | Avg Sec/Case | Batch Count |
|---|---:|---:|---:|---:|
| hied:lingxidiag | 18m | 0.920 | 1.087 | 10 |
