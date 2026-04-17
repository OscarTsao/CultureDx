# T10-SELF-DISTILLATION：Claude Code 執行 Prompt

```
你在 CultureDx repo。目標：用 Qwen3-32B 當 teacher 跑 14000 train cases 產生完整 reasoning traces + labels，然後 SFT distill 到 Qwen3-8B student，作為比 T3-LORA-CLF 更強的 ensemble member。

完整設計：T10_19_SELF_DISTILLATION.md。

需求：1× A100-80G for ~60h total (30h teacher data gen + 10h training)

STEP 1：Teacher data generation setup
- 新增 scripts/generate_teacher_distillation_data.py
- 對每個 train case 跑完整 CultureDx factorial_b pipeline
- 把 diagnostician reasoning + checker outputs + logic engine explanation + final label 組合成 single assistant response
- 儲存格式：JSONL with {"messages": [system, user, assistant]}
- 重要：在 assistant response 加入 <think>...</think> 結構化 reasoning，<box>...</box> 包 label

STEP 2：Quality filter
- 對每個 teacher trace，檢查 teacher label == gold label
- 只保留 match 的 cases 作為訓練資料（預期 60-70% 保留率）
- 紀錄 filter 統計：per-class 保留比例（看是否對 F32/F41 有 bias）

STEP 3：SFT training
- 新增 scripts/train_qwen3_distill.py（基於 T3-LORA-CLF 改）
- LoRA config: r=16, alpha=32, target_modules=q,k,v,o_proj
- Training: batch 1, grad_acc 16, lr 1e-4, epochs 3, max_seq 6144
- 更長的 max_seq 是因為 reasoning trace 佔用空間
- Save adapter 到 outputs/qwen3_8b_lora_distill/

STEP 4：Standalone inference
- 新增 scripts/infer_qwen3_distill.py
- 批次推論 N=1000 val cases
- 輸出 predictions.jsonl with full reasoning + label
- Case_id 對齊 factorial_b

STEP 5：Standalone evaluation
- 12c metrics vs T3-LORA-CLF 對比
- 預期 all metrics +1pp 以上
- 如果不贏，debug：
  - Teacher data 是否太少 (<5000)
  - Trace 是否太長導致 truncation
  - LoRA rank 是否太低

STEP 6：Ensemble integration
- 擴充 scripts/run_ensemble.py 支援第 6 個 member
- 6-way ensemble: factorial_b + qwen3_8b_dtv + 05_dtv_v2_rag + TF-IDF + LoRA-CLF + LoRA-DISTILL
- Weights sweep

STEP 7：Ablation study
- T3-LORA-CLF vs T10-LORA-DISTILL standalone
- T3-LORA-CLF vs T10-LORA-DISTILL inside ensemble
- Paper table: distillation quality -> student capability

驗收：
- Teacher data quality filter retention rate ≥ 50%
- Student 12c_Acc ≥ 0.40（比 T3-LORA-CLF 預期的 0.35+ 更高）
- Student F1_macro ≥ 0.28
- 6-way ensemble all metrics ≥ 5-way ensemble + 1pp OR no regression

如果 teacher data generation 太貴（>40h GPU），可以：
- 縮小到 train split 的 subset 5000 cases
- 或用更快的 teacher model 如 Qwen3-14B-AWQ
- 但效果會稍降，預期學生 metric 只超越 T3-LORA-CLF +0.5-1pp

報告：teacher data 統計、student metrics、ensemble 改善。
```
