# 4. Experimental Setup

## 4.1 Datasets

| Dataset | Cases | Language | Source | Disorders |
|---------|-------|----------|--------|-----------|
| LingxiDiag-16K | ~14,000 | Chinese | Real clinical transcripts | 15 ICD-10 codes |
| MDD-5k | 925 | Chinese | Simulated clinical interviews | F32, F33, F41.1, F42, F43.1 |

### LingxiDiag-16K
- Real Chinese psychiatric clinical transcripts
- Multi-label: primary + comorbid diagnoses
- Full ICD-10 code coverage (15 disorders)

### MDD-5k
- Simulated clinical interviews for mood and anxiety disorders
- 5 disorder codes: F32, F33, F41.1, F42, F43.1
- Used for focused evaluation on common presentations

## 4.2 Models

| Model | Parameters | Quantization | Role |
|-------|-----------|--------------|------|
| Qwen3-32B-AWQ | 32B | AWQ 4-bit | Teacher / primary evaluator |
| Qwen3-8B (SFT) | 8B | QLoRA 4-bit | Student / finetuned checker |

### Teacher Model: Qwen3-32B-AWQ
- Served via vLLM with AWQ 4-bit quantization
- Greedy decoding: temperature=0.0, top_k=1
- Used for teacher data generation and baseline evaluation

### Student Model: Qwen3-8B (SFT)
- QLoRA fine-tuned on teacher-generated criterion checker data
- Training: 4816 examples, 3 epochs, LoRA r=16, alpha=32
- Served via vLLM with LoRA adapter

## 4.3 Baselines and Ablations

### Mode Comparison
- Single-model baseline (zero-shot)
- HiED (primary pipeline)
- PsyCoT (no triage)
- Specialist-MAS
- Debate-MAS

### Ablation Conditions
1. HiED baseline (greedy, no CoT)
2. HiED + thinking mode (Qwen3 native `<think>` blocks)
3. HiED + CoT prompts (5-step structured reasoning)
4. HiED + thinking + CoT (combined)
5. PsyCoT + thinking + CoT (alternative pipeline)

### Evidence Ablations
- With/without evidence pipeline
- With/without somatization mapping
- With/without negation detection

## 4.4 Evaluation Metrics

- **Accuracy**: Exact match on primary diagnosis
- **F1 (Macro)**: Macro-averaged F1 across disorder classes
- **Precision / Recall**: Per-class and macro-averaged
- **Abstention Rate**: Fraction of cases where system abstains
- **Comorbidity Metrics**: Subset accuracy, Hamming loss for multi-label
- **Bootstrap CIs**: 10,000 resamples for confidence intervals

<!-- TODO: Add specific hyperparameters table, data split details -->
