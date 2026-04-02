# CultureDx Full Evaluation Report

## Config Summary

- Generated at: 2026-04-02T14:40:40.230171+00:00
- Config files: configs/base.yaml, configs/hied.yaml, configs/vllm_awq.yaml, configs/targets/lingxidiag_12class.yaml, configs/evidence.yaml, outputs/eval/rescore_gate_only_20260402_223720/hied-evidence/eval_config.yaml
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
| global | 665 | 0.3609 | 0.5308 | 0.0677 | 0.7833 | 0.1765 | 0.0000 |
| hied | 665 | 0.3609 | 0.5308 | 0.0677 | 0.7833 | 0.1765 | 0.0000 |

## Per-Dataset Comparison

| Mode/Dataset | Cases | Top-1 | Top-3 | Exact Match | Hamming Loss | Macro F1 | Abstain Rate | Elapsed | Cases/Sec |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hied:lingxidiag | 665 | 0.3609 | 0.5308 | 0.0677 | 0.7833 | 0.1765 | 0.0000 | 2m | 9.479 |

## Per-Disorder Metrics

| Mode | Disorder | Support | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| hied | F20 | 5 | 0.4286 | 0.6000 | 0.5000 |
| hied | F31 | 4 | 0.0000 | 0.0000 | 0.0000 |
| hied | F32 | 249 | 0.4648 | 0.7430 | 0.5719 |
| hied | F39 | 38 | 0.0667 | 0.0789 | 0.0723 |
| hied | F41 | 251 | 0.4388 | 0.5139 | 0.4734 |
| hied | F42 | 27 | 0.2241 | 0.4815 | 0.3059 |
| hied | F43 | 9 | 0.0211 | 0.6667 | 0.0410 |
| hied | F45 | 10 | 0.0000 | 0.0000 | 0.0000 |
| hied | F51 | 35 | 0.0616 | 1.0000 | 0.1161 |
| hied | F98 | 37 | 0.0667 | 0.0270 | 0.0385 |
| hied | Others | 63 | 0.0000 | 0.0000 | 0.0000 |

## Top Error Patterns

| Mode | Dataset | Gold | Predicted | Count | Example Case IDs |
|---|---|---|---|---:|---|
| hied | lingxidiag | F41 | F32 | 98 | 318518739, 355727279, 335985565, 365148198, 382615327 |
| hied | lingxidiag | F41 | F51 | 67 | 377662897, 380913193, 397700349, 354219828, 320669626 |
| hied | lingxidiag | F32 | F51 | 61 | 312389408, 358313639, 321077019, 346998154, 327456260 |
| hied | lingxidiag | F39 | F32 | 26 | 342949614, 371401723, 357343954, 330014648, 366688675 |
| hied | lingxidiag | Others | F51 | 20 | 314631661, 351228828, 383579251, 326740623, 338464039 |
| hied | lingxidiag | Others | F32 | 19 | 344699340, 371726537, 391104352, 387132598, 321679684 |
| hied | lingxidiag | F98 | F32 | 14 | 336521777, 321037752, 379961969, 368417566, 303669869 |
| hied | lingxidiag | F51 | F32 | 11 | 348839819, 373267151, 366260309, 379479487, 301219386 |
| hied | lingxidiag | F41 | F42 | 11 | 315846324, 387949900, 310152130, 366264963, 301884572 |
| hied | lingxidiag | Others | F42 | 7 | 347729413, 386951485, 331114130, 362317955, 303683319 |
| hied | lingxidiag | F41 | F43 | 7 | 340563038, 357675887, 393386510, 356942364, 323525666 |
| hied | lingxidiag | Others | F43 | 7 | 305273450, 335538152, 330091430, 308267561, 399676049 |
| hied | lingxidiag | F43 | F32 | 6 | 337522433, 395985056, 329984067, 313602441, 395760227 |
| hied | lingxidiag | F32 | F43 | 6 | 379645537, 387294870, 314451639, 326684645, 399300958 |
| hied | lingxidiag | F39 | F51 | 5 | 327826586, 377956208, 318024484, 389224279, 375870610 |

## Timing Statistics

- Total wall time: 2m
- Total evaluated cases: 665
- Overall cases/sec: 6.160

| Mode/Dataset | Elapsed | Cases/Sec | Avg Sec/Case | Batch Count |
|---|---:|---:|---:|---:|
| hied:lingxidiag | 2m | 9.479 | 0.106 | 10 |
