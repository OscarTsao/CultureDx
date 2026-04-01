# 5. Results

## 5.1 Main Results

<!-- See paper/tables/main_results.md for the results table template -->

### HiED vs Single-Model Baseline

| Model | Mode | Dataset | Acc. | F1 (Macro) | Prec. | Recall |
|-------|------|---------|------|------------|-------|--------|
| Qwen3-32B-AWQ | Single | LingxiDiag | — | — | — | — |
| Qwen3-32B-AWQ | HiED | LingxiDiag | — | — | — | — |
| Qwen3-8B (SFT) | HiED | LingxiDiag | — | — | — | — |
| Qwen3-32B-AWQ | Single | MDD-5k | — | — | — | — |
| Qwen3-32B-AWQ | HiED | MDD-5k | — | — | — | — |
| Qwen3-8B (SFT) | HiED | MDD-5k | — | — | — | — |

*To be populated after full evaluation completes.*

## 5.2 Mode Comparison (5 MAS Architectures)

| Mode | LingxiDiag Acc. | LingxiDiag F1 | MDD-5k Acc. | MDD-5k F1 |
|------|----------------|---------------|-------------|-----------|
| Single | — | — | — | — |
| HiED | — | — | — | — |
| PsyCoT | — | — | — | — |
| Specialist | — | — | — | — |
| Debate | — | — | — | — |

## 5.3 Ablation Study

<!-- See paper/tables/ablation_results.md for the ablation table template -->

### Reasoning/CoT Ablation

| Condition | Dataset | Acc. | F1 | Delta |
|-----------|---------|------|-----|-------|
| HiED baseline | LingxiDiag | — | — | — |
| + Thinking mode | LingxiDiag | — | — | — |
| + CoT prompts | LingxiDiag | — | — | — |
| + Thinking + CoT | LingxiDiag | — | — | — |
| PsyCoT + Thinking + CoT | LingxiDiag | — | — | — |

### Evidence Pipeline Ablation

| Condition | Dataset | Acc. | F1 | Delta |
|-----------|---------|------|-----|-------|
| HiED (no evidence) | — | — | — | — |
| + Evidence pipeline | — | — | — | — |
| + Somatization mapping | — | — | — | — |
| + Negation detection | — | — | — | — |

## 5.4 Cross-Dataset Generalization

<!-- Compare performance between LingxiDiag (real) and MDD-5k (simulated) -->

## 5.5 Comorbidity Detection

<!-- Multi-label metrics: subset accuracy, Hamming loss -->

<!-- TODO: Populate all tables with actual experiment results -->
