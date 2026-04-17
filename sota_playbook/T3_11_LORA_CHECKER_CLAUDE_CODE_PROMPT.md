# T3-LORA-CHECKER：Claude Code 執行 Prompt

```
你在 CultureDx repo，main-v2.4-refactor 分支。目標：把 master 分支訓練好的 Criterion Checker LoRA（master 分支 outputs/finetune/criterion_checker_lora/ 下有 criterion_accuracy 78.1% vs base 58.1% 的 adapter）整合到 v2.4 pipeline 的 CriterionChecker，然後在 LingxiDiag-16K 上做 end-to-end eval，看 criterion +20pp 能傳導多少 end-to-end improvement。

完整設計：T3_11_LORA_CHECKER.md。

STEP 1：檢查 master 分支的 LoRA artifacts
- git log master -- outputs/finetune/criterion_checker_lora/
- git log master -- scripts/
- 找出：
  (a) LoRA 訓練用的 base model (Qwen2.5-7B-Instruct?)
  (b) LoRA 訓練用的 prompt template (是 v1, v2, 還是 v2_improved?)
  (c) LoRA 訓練用的 data format
- 印出訓練 config，讓我確認

STEP 2：評估 prompt 對齊風險
- 如果 LoRA 是用 v1 或 v2 prompt 訓練的，**但 factorial_b 用的是 v2_improved**：
  - v2_improved 是 216 行的升級版，加了 somatization mapping hints
  - LoRA 模型沒看過這個新 prompt，效果會不穩定
- 決策樹：
  - 如果 prompt 一致 → 直接接入
  - 如果 prompt 不一致 → 三選一：
    (a) 用 v2_improved prompt 重訓 LoRA (需要 GPU 4-6h)
    (b) 把 LoRA 搭 v2 prompt 跑，和 factorial_b (v2_improved) 做公平比較
    (c) Skip 此 track，優先跑 T3-09 和 T3-10

STEP 3：Cherry-pick 或 port 必要 code
- 從 master 分支 copy 以下到 v2.4-refactor:
  - outputs/finetune/criterion_checker_lora/ (整個 dir, 含 adapter_model.safetensors 和 config)
  - scripts/ 中相關的 infer script
- 如果 master 分支已刪除這些 file，從 git history revive: git show master~N:path

STEP 4：擴充 CriterionChecker
- 讀 src/culturedx/agents/criterion_checker.py
- 新增 use_lora, lora_path 參數
- 如果 use_lora=True，改用 peft 載入 LoRA adapter on top of base model
- 推理時使用 LoRA 增強的 model.generate()

STEP 5：新 overlay config
- configs/overlays/t3_lora_checker.yaml
- 如 T3_11_LORA_CHECKER.md 描述
- 同時保留 diagnostician 和 calibrator 與 factorial_b 一致，只換 checker

STEP 6：Smoke N=200
- 跑 N=200 validation
- 對比 factorial_b 同樣 200 cases:
  - criterion-level: 每個 disorder 的 B1/B2/B3/B4/... 平均 met rate 變化
  - 特別看 F41.1 B2 (autonomic)
  - 如果 criterion accuracy 沒 +15pp 以上，表示 loading 有問題，debug

STEP 7：Full N=1000
- -o results/validation/t3_lora_checker
- 對比 factorial_b:
  - 12c_Acc, Top-1, Top-3, F1_macro, F1_weighted
  - Per-class F1 全表

STEP 8：分析傳導效應
- 寫 scripts/analyze_criterion_to_endgame_transfer.py:
  - 按 case 計算 criterion_accuracy (LoRA) - criterion_accuracy (base)
  - 相關這個 Δcriterion 和 end-to-end accuracy 變化
  - 找出：criterion improve 但 end-to-end 沒 improve 的 cases, root cause 在哪（通常是 calibrator ranking）

驗收：
- criterion accuracy 在 v2.4 pipeline context 下 > 70% (接近 master 分支的 78.1%)
- 12c_Acc 升級 ≥ +2pp (0.432 → 0.45)
- F1_macro 升級 ≥ +2pp

如果 checker LoRA 和 v2.4 pipeline 不對齊導致效果劣化，優先級降低，等後面有空再重訓。
```
