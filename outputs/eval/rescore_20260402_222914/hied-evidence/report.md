# CultureDx Full Evaluation Report

## Config Summary

- Generated at: 2026-04-02T14:32:45.924696+00:00
- Config files: configs/base.yaml, configs/hied.yaml, configs/vllm_awq.yaml, configs/targets/lingxidiag_12class.yaml, configs/evidence.yaml, outputs/eval/rescore_20260402_222914/hied-evidence/eval_config.yaml
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
| global | 715 | 0.3203 | 0.5021 | 0.0406 | 0.7891 | 0.1712 | 0.0000 |
| hied | 715 | 0.3203 | 0.5021 | 0.0406 | 0.7891 | 0.1712 | 0.0000 |

## Per-Dataset Comparison

| Mode/Dataset | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate | Elapsed | Cases/Sec |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hied:lingxidiag | 715 | 0.3203 | 0.5021 | 0.0406 | 0.7891 | 0.1712 | 0.0000 | 2m | 7.923 |

## Per-Disorder Metrics

| Mode | Disorder | Support | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| hied | F20 | 5 | 0.4000 | 0.4000 | 0.4000 |
| hied | F31 | 5 | 0.0000 | 0.0000 | 0.0000 |
| hied | F32 | 275 | 0.4822 | 0.7382 | 0.5833 |
| hied | F39 | 44 | 0.0625 | 0.0682 | 0.0652 |
| hied | F41 | 273 | 0.4556 | 0.4505 | 0.4530 |
| hied | F42 | 22 | 0.1923 | 0.4545 | 0.2703 |
| hied | F43 | 9 | 0.0211 | 0.5556 | 0.0407 |
| hied | F45 | 8 | 0.0000 | 0.0000 | 0.0000 |
| hied | F51 | 32 | 0.0500 | 0.9375 | 0.0949 |
| hied | F98 | 43 | 0.1500 | 0.0698 | 0.0952 |
| hied | Others | 67 | 0.0000 | 0.0000 | 0.0000 |

## Top Error Patterns

| Mode | Dataset | Gold | Predicted | Count | Example Case IDs |
|---|---|---|---|---:|---|
| hied | lingxidiag | F41 | F32 | 83 | 318518739, 355727279, 381931431, 334814081, 382615327 |
| hied | lingxidiag | F41 | F51 | 77 | 377662897, 397700349, 354219828, 329547625, 320669626 |
| hied | lingxidiag | F32 | F51 | 68 | 303364596, 312389408, 346998154, 369867441, 356498183 |
| hied | lingxidiag | F39 | F32 | 22 | 342949614, 371401723, 350575983, 357343954, 330014648 |
| hied | lingxidiag | Others | F51 | 18 | 376197379, 314631661, 351228828, 362317955, 347255679 |
| hied | lingxidiag | F32 | F43 | 16 | 303895252, 346313917, 336404489, 379645537, 369686188 |
| hied | lingxidiag | F41 | F43 | 15 | 393761475, 335985565, 391945652, 363300223, 387949900 |
| hied | lingxidiag | F32 | F41 | 15 | 321077019, 309460138, 358561077, 361781918, 377099392 |
| hied | lingxidiag | Others | F32 | 13 | 344699340, 371726537, 391104352, 321179204, 341775516 |
| hied | lingxidiag | F32 | F39 | 13 | 341042297, 371125111, 379611968, 398106929, 395706701 |
| hied | lingxidiag | F41 | F39 | 13 | 314878848, 314036143, 368315761, 378952793, 326269413 |
| hied | lingxidiag | Others | F41 | 11 | 376288406, 317513157, 321679684, 304404409, 338464039 |
| hied | lingxidiag | Others | F43 | 11 | 305273450, 335538152, 352801207, 330091430, 315071239 |
| hied | lingxidiag | F98 | F32 | 10 | 336521777, 316834006, 399103589, 379961969, 368417566 |
| hied | lingxidiag | F41 | F42 | 10 | 353485011, 310152130, 307032548, 399081176, 352879530 |

## Timing Statistics

- Total wall time: 2m
- Total evaluated cases: 715
- Overall cases/sec: 5.552

| Mode/Dataset | Elapsed | Cases/Sec | Avg Sec/Case | Batch Count |
|---|---:|---:|---:|---:|
| hied:lingxidiag | 2m | 7.923 | 0.126 | 10 |
