# T3-LORA-CLF：Qwen3-8B LoRA End-to-End 12c Classifier

## 動機

T3-TFIDF-STACK 雖然便宜，但 TF-IDF 只能看 n-gram features，無法理解「我最近總是胸悶，擔心自己要死」這種跨句語意。如果我們要超越「DtV 3-way + TF-IDF」的效果上限，需要一個**更強的 supervised model**。

最經濟的選擇：**Qwen3-8B LoRA fine-tuning on LingxiDiag-16K train split**。這會同時解決：
1. supervised 的 class frequency 校準（吸收 TF-IDF 的 F1_macro 優勢）
2. 語意理解能力（克服 TF-IDF 的 n-gram 限制）
3. 直接預測 ICD code with reasoning（比 TF-IDF 的 black-box probability 更可解釋）

## 目標定位

不是取代 CultureDx 主 pipeline，而是作為 ensemble 第 5 member：
- DtV 3-way + TF-IDF + LoRA-Qwen3-8B
- 預期比 4-way 再 +1-2pp 在所有 metric

## 技術設計

### Training setup

```python
# scripts/train_qwen3_lora_classifier.py
# Framework: unsloth 或 peft + transformers 或 LLaMA-Factory

BASE_MODEL = "Qwen/Qwen3-8B"  # 或 Qwen3-8B-Instruct
LORA_CONFIG = {
    "r": 16,
    "lora_alpha": 32,
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
    "lora_dropout": 0.05,
    "bias": "none",
    "task_type": "CAUSAL_LM",
}
TRAINING_CONFIG = {
    "per_device_train_batch_size": 2,
    "gradient_accumulation_steps": 8,
    "num_train_epochs": 2,  # LingxiDiag 14000 cases, 2 epochs = 28000 steps with batch 16
    "learning_rate": 2e-4,
    "warmup_ratio": 0.05,
    "max_seq_length": 4096,  # transcript 通常 1500-3000 tokens
}

# Training data format (exactly matching paper's prompt)
def format_training_example(case):
    transcript = case["conversation"]  # full dialog
    gold_code = case["DiagnosisCode"]  # e.g., "F32.2;F41.1"
    
    system = """你是一位经验丰富的精神科医师。请阅读以下精神科初诊对话记录，根据 ICD-10 国际分类标准，仔细分析并输出患者的 ICD-10 诊断代码。

疾病分类（10 大类含子分类）：
... (完整官方 12-class description, 同 T1-SUBCODE 用的) ...

注意：(1) 初诊时症状严重度或细节不明时，推荐未特指 ICD 代码。(2) 诊断可包含 1-2 个 ICD-10 结果，多数单一但不超过 2 个。(3) 不同代码用分号分隔。(4) 严格遵循 ICD-10 标准，避免猜测和无根据诊断。"""
    
    user = f"""[问诊对话开始]
{transcript}
[问诊对话结束]

请用中文 step-by-step 思考，思考过程放在 <think></think>，最后 ICD-10 诊断代码放在 <box></box>，用分号分隔。"""
    
    assistant = f"""<think>
(训练时这里可以留空或用 rationale model 生成的 reasoning trace)
</think>
<box>{gold_code}</box>"""
    
    return {"messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}
```

### 關鍵設計決定

1. **保留官方 prompt 格式 `<think>…</think><box>…</box>`**：與 paper 所有 LLM baseline 一致，evaluation pipeline 可復用
2. **訓練資料不給 reasoning trace**：省訓練時間；<think> 在推理時 LLM 自己生成
3. **Base model Qwen3-8B not Qwen3-32B**：顯存省，速度快，且 paper Table 4 顯示 Qwen3-8B zero-shot 在 12c_Top3 已經 0.599，表示 base model 其實有這個能力，只需要 calibration
4. **2 epochs**：train size 14000 不算大，2 epochs 避免 overfit

### Inference

```python
def predict(model, tokenizer, transcript):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"[问诊对话开始]\n{transcript}\n[问诊对话结束]\n..."},
    ]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    output = model.generate(...)
    
    # Parse <box>...</box>
    import re
    m = re.search(r'<box>(.+?)</box>', output, re.DOTALL)
    if not m:
        return ["Others"]
    
    # Use LingxiDiagBench's 12class parser (from /tmp/LingxiDiagBench/evaluation/static/llm_zeroshot_classifier.py line 267)
    codes = re.findall(r'(F\d{2}|Z71)', m.group(1).upper())
    seen = set()
    result = []
    for c in codes:
        if c not in seen and c in TWELVE_CLASS_LABELS:
            seen.add(c)
            result.append(c)
    return result or ["Others"]
```

## 資源估算

- GPU: 1× A100-80G（Qwen3-8B + LoRA）
- 訓練時間：14000 cases × 2 epochs ÷ (batch 16) = 1750 steps，約 4-6 小時
- Inference on 1000 val: ~30 分鐘

## 成功判準

作為 standalone baseline:
- 12c_Acc ≥ 0.35
- 12c_Top1 ≥ 0.50
- 12c_Top3 ≥ 0.65（應該比 Qwen3-8B zero-shot 的 0.599 顯著高）
- F1_macro ≥ 0.25

作為 5-way ensemble member:
- 讓最終 ensemble metrics 再推 +1-2pp（vs 4-way with TF-IDF）

## 風險

- LoRA 可能 overfit 到 train split 的表達風格，val 上不見得贏太多
- 如果 baseline Qwen3-8B-Instruct 已經在 val 上 F1_macro 0.177，LoRA 要推到 0.25+ 才算成功

## 建議執行時機

**先跑 T3-TFIDF-STACK**，看最終 4-way ensemble 結果。
- 若 4-way 已達全面 SOTA → LoRA 可以 optional，論文主結果用 4-way，LoRA 當 ablation
- 若 4-way 還差 1-2 個指標 → LoRA 必要，用來補最後一哩

## 輸出

- `outputs/qwen3_8b_lora_clf/checkpoints/`: LoRA weights
- `outputs/qwen3_8b_lora_clf/predictions.jsonl`
- `results/validation/t3_lora_clf/` (standalone eval)
- `results/validation/t3_5way_ensemble/` (5-way ensemble)
