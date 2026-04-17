# T10-SELF-DISTILLATION：Teacher-Student Distillation

## 動機

T3-LORA-CLF 是 supervised SFT on train split labels，但這些 labels 只有 `[F32.2, F41.1]` 這種 hard label，沒有 reasoning trace。Qwen3-8B student model 學到的只是「memorize case → label」的 mapping，不是 reasoning 能力。

**Self-distillation 解法**：用 Qwen3-32B（你的 teacher model）先跑 14000 train cases，用你 CultureDx 最強的 prompt（v2_improved + subcode descriptions）產生 **teacher reasoning traces + labels**，然後用這些豐富的 data 做 SFT，training signal 從「只有 label」升級為「full reasoning + label」。

研究證據：
- Distilling Reasoning Chains (Zhang et al., EMNLP 2024)
- Orca 2: Teaching Reasoning via Distilled Traces
- MiniCPM distillation showed +5-10pp on reasoning tasks

## 假設

相比 T3-LORA-CLF 的純 SFT：
- Student reasoning quality 顯著提升
- Generalization 更好（學到 "為什麼" 而非 "是什麼"）
- 在 test split 上 transfer 更穩定

預期比 T3-LORA-CLF 在 all 12c metric 再 +1-2pp。

## 技術設計

### Step 1：Generate Teacher Data

用 Qwen3-32B-AWQ + CultureDx 最強配置跑 14000 train cases：

```python
# scripts/generate_teacher_distillation_data.py
"""Generate teacher reasoning traces for SFT distillation."""

def generate_teacher_trace(case, full_cultureDx_pipeline):
    # Run full DtV pipeline including:
    # - Diagnostician ranking with step-by-step reasoning
    # - Criterion Checker with per-criterion evidence
    # - Logic engine explanation
    # - Calibrator confidence scores
    
    # Compose as training example:
    system_prompt = "..."
    user_prompt = format_transcript(case)
    
    # Assistant output: FULL reasoning trace (NOT just label)
    assistant_output = f"""<think>
{diagnostician_reasoning}

## Criterion Evaluation
F32:
- A1: {crit_A1_status} ({crit_A1_evidence})
- A2: ...
F41.1:
- A: ...

## Logic Engine
F32 meets threshold: {f32_met}/{f32_req}
F41.1 meets threshold: {f41_met}/{f41_req}

## Ranking
{calibrator_reasoning}
</think>
<box>{primary};{comorbid if any}</box>"""
    
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_output},
        ]
    }
```

關鍵設計：
- 只保留 `teacher_label == gold_label` 的 cases（quality filter）
- 可能只有 ~60-70% cases 通過 quality filter（i.e. teacher 也答對了那個 case）
- 這樣 student 學的是「高品質 reasoning → 正確 label」而非「random reasoning → noisy label」

### Step 2：SFT on Teacher Data

```python
# 和 T3-LORA-CLF 相同的 LoRA 設定
# 但訓練資料是 teacher traces 而非純 label

trainer = SFTTrainer(
    model=qwen3_8b,
    train_dataset=teacher_traces_train,
    eval_dataset=teacher_traces_val,
    peft_config=lora_config,
    max_seq_length=6144,  # longer because reasoning trace is long
    # ...
)
```

### Step 3：Dual-head Output

Inference 時 student model 輸出：
- Reasoning trace (useful for interpretability)
- Final label in `<box>`

解析和 Qwen3-Base 一致，可以直接 replace factorial_b 的 diagnostician LLM call。

## 相對 T3-LORA-CLF 的優勢

| 維度 | T3-LORA-CLF | T10-SELF-DISTILL |
|---|---|---|
| Training signal | 純 hard label | 完整 reasoning + label |
| 資料過濾 | 無（全 14000 cases）| Quality filter，~60-70% |
| 輸出 | 短（只 box）| 完整 reasoning trace |
| 可解釋性 | 低 | 高（保留 CultureDx interpretability） |
| Generalization | 中 | 高（學到 reasoning pattern）|
| 訓練成本 | 低（短 seq）| 高（長 seq，可能需更大 batch）|

## 成本估算

- Teacher data generation: 14000 cases × Qwen3-32B full pipeline = 30-50 小時 GPU
- Quality filtering: 保留 8000-10000 cases
- SFT: 3 epochs × 10000 cases × seq_len 4096 ≈ 8-12 小時 on A100-80G

## 成功判準

Standalone LoRA-student model:
- 12c_Acc ≥ 0.40
- Top-1 ≥ 0.52
- F1_macro ≥ 0.28
- **比 T3-LORA-CLF 所有 metric 提升 ≥ 1pp**

作為 ensemble member:
- 6-way ensemble (DtV 3-way + TFIDF + LoRA-CLF + LoRA-DISTILL) 在所有 metric 都 ≥ T3-TFIDF-STACK 結果

## 風險

- Teacher data quality filter 太嚴（只留 50% cases）→ student 資料不足
- Teacher data quality filter 太寬（留 90% cases，含錯誤 reasoning）→ student 學偏
- Reasoning trace 過長會 inference 慢（需要 student max_tokens ≥ 2048）

## 論文敘事

Self-distillation 是可以單獨成一個 section 的 contribution：
- **C7**: Culture-adaptive MAS 的 reasoning trace 可以 distill 成 8B 小模型，保留可解釋性同時 inference 加速 4×
- 對 "deploy in resource-constrained clinical settings" 的論點有力

## 輸出

- `data/distillation/teacher_traces.jsonl`
- `outputs/qwen3_8b_lora_distill/`
- `results/validation/t10_lora_distill/`
