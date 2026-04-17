# T3-LORA-CLF：Claude Code 執行 Prompt

```
你在 CultureDx repo。目標：Fine-tune Qwen3-8B 用 LoRA 在 LingxiDiag-16K 的 14000 cases train split 上，學一個直接 end-to-end 12c classifier，然後作為第 5 個 ensemble member。

完整設計：T3_10_LORA_CLF.md。

先決條件：
- GPU: 需要 1× 80GB GPU（A100 或 H100）
- 環境：transformers + peft + accelerate + bitsandbytes（已有 vLLM 環境，擴充即可）
- 不要用 unsloth（可能和 vLLM 衝突）

STEP 1：準備訓練資料
- 新增 scripts/prepare_lora_training_data.py
- 讀 data/raw/lingxidiag16k/LingxiDiag-16K_train_data.json (14000 cases)
- 對每個 case 產生 chat-formatted training example（system + user + assistant），格式嚴格對齊 LingxiDiagBench 官方 prompt（見設計文件）
- 輸出到 data/processed/lora_training/train.jsonl
- 另外保留 1000 cases 作為 eval（和 val split 分開），輸出 eval.jsonl
- 檢查：訓練集 label 分佈，確認 F32/F41 的 class 不平衡和 paper Table 2 一致

STEP 2：訓練腳本
- 新增 scripts/train_qwen3_lora_classifier.py
- 使用 peft 的 LoraConfig：r=16, alpha=32, target_modules=["q_proj","k_proj","v_proj","o_proj"]
- 載入 Qwen3-8B-Instruct，使用 bf16
- TrainingArguments:
  - per_device_train_batch_size=2
  - gradient_accumulation_steps=8 (effective batch=16)
  - learning_rate=2e-4
  - num_train_epochs=2
  - warmup_ratio=0.05
  - logging_steps=50
  - save_strategy="epoch"
  - evaluation_strategy="epoch"
  - max_seq_length=4096
- 啟用 packing=True for efficiency
- Checkpoints 存 outputs/qwen3_8b_lora_clf/

STEP 3：監控訓練
- 確認 train loss 下降（應該從 ~1.5 降到 ~0.3-0.5）
- 兩個 epoch 就停，不要 overfit

STEP 4：Inference 腳本
- 新增 scripts/infer_qwen3_lora.py
- 載入 base + LoRA weights
- 批次推理 N=1000 validation cases
- 解析 <box>...</box> 輸出，使用 LingxiDiagBench 的 parser（F\d{2}|Z71）
- 輸出 predictions.jsonl 到 outputs/qwen3_8b_lora_clf/predictions.jsonl
- case_id 必須和 factorial_b 對齊（方便 ensemble）

STEP 5：Standalone 評估
- 用 src/culturedx/eval/lingxidiag_paper.py 評估單獨 LoRA baseline
- 與 paper Qwen3-8B zero-shot (F1_macro 0.177, Top-3 0.599) 對比
- 目標：F1_macro > 0.25, Top-3 > 0.65
- 如果沒達到，檢查：
  (a) 訓練 loss 是否收斂
  (b) output 解析是否正確
  (c) 訓練資料格式是否完全對齊官方 prompt

STEP 6：Top-10 candidates for ensemble
- LoRA model 直接 greedy decode 只給 1-2 個 code，沒 ranked list
- 改成：用 vLLM + logit_bias / top_logprobs 抓 top-10 最可能的 code
- 或：用 beam search 或 temperature sampling 多次跑（temperature=0.7, n=5），aggregate 頻率
- 產生 top10_codes 給 ensemble 使用

STEP 7：5-way ensemble
- 擴充 scripts/run_ensemble.py 支援 5 個 systems
- 把 LoRA predictions 加入
- 做 weights sweep，挑最佳組合

STEP 8：Final ablation table
- 1-way: factorial_b (單系統)
- 3-way: DtV only ensemble
- 4-way: DtV + TF-IDF
- 5-way: DtV + TF-IDF + LoRA
- 輸出到 results/validation/t3_5way_ensemble/ablation.md

驗收：
- LoRA standalone F1_macro ≥ 0.25
- 5-way ensemble 在所有 5 個 12c metric 都 ≥ 對應 paper SOTA
- 5-way 至少在 1-2 個 metric 比 4-way 再 +1pp

如果 GPU 有限，考慮用 Qwen3-4B 取代 Qwen3-8B（4B 訓練快 2 倍，效果應該接近 Qwen3-8B zero-shot 的 Top-3 0.637 水準）。

報告所有 ablation 結果。
```
