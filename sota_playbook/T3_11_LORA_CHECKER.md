# T3-LORA-CHECKER：Criterion Checker LoRA Fine-tuning

## 動機

你在 master 分支已有 `outputs/finetune/criterion_checker_lora/` 的實驗成果：
- Base Qwen2.5-7B criterion accuracy = 58.1%
- LoRA fine-tuned criterion accuracy = **78.1%**（+20pp）

這個 20pp 的 criterion-level 提升如果能傳導到 end-to-end，應該很驚人。但 master 分支的這個工作沒被整合進 v2.4-refactor pipeline，也沒在 LingxiDiag-16K 上做 end-to-end eval。

這個 track 的目的是**把 LoRA checker 接到 v2.4 pipeline 並 eval**，看 criterion +20pp 能傳導到多少 end-to-end metric。

## 和 T3-LORA-CLF 的關係

兩個 LoRA 方向：
- T3-LORA-CLF：**end-to-end 分類器**，完全繞過 DtV 架構，作為 ensemble member
- T3-LORA-CHECKER：**強化既有 DtV 的 checker 層**，保持整個 MAS 架構，讓 criterion-level 準確度升，整條 pipeline 也跟著升

兩者可以同時做，互不衝突。但論文敘事上，T3-LORA-CHECKER 更能支持「culture-adaptive MAS」的 narrative，因為保留了 criterion-level 可解釋性。

## 技術改動

### 檔案 1：從 master 分支 cherry-pick LoRA checker 代碼

```bash
# 看 master 分支有什麼
git log master -- outputs/finetune/criterion_checker_lora/ 
git log master -- scripts/train_checker_lora*
git log master -- src/culturedx/agents/criterion_checker.py

# Cherry-pick 必要的部分
# 或手動 copy：scripts, configs, model loading 邏輯
```

### 檔案 2：接入 v2.4 CriterionChecker

找到 `src/culturedx/agents/criterion_checker.py`，加入 LoRA 支援：

```python
class CriterionChecker:
    def __init__(
        self,
        llm_client,
        prompt_variant: str = "v2_improved",
        use_lora: bool = False,
        lora_path: str = None,
    ):
        self.llm = llm_client
        self.prompt_variant = prompt_variant
        self.use_lora = use_lora
        if use_lora:
            assert lora_path, "lora_path required when use_lora=True"
            self._load_lora(lora_path)
    
    def _load_lora(self, lora_path):
        from peft import PeftModel
        # Load LoRA adapter on top of base Qwen2.5-7B
        self.lora_model = PeftModel.from_pretrained(
            self.llm.base_model,
            lora_path,
        )
```

### 檔案 3：新 overlay

```yaml
# configs/overlays/t3_lora_checker.yaml
mode:
  checker:
    backend: lora
    base_model: "Qwen/Qwen2.5-7B-Instruct"
    lora_path: "outputs/finetune/criterion_checker_lora/checkpoint-final"
    prompt_variant: v2_improved  # LoRA 訓練時用的 prompt，必須一致
```

## 關鍵校驗

1. **LoRA 訓練用的 prompt_variant 和目前 v2.4 checker 要一致**
   - 看 `outputs/finetune/criterion_checker_lora/` 裡的 train config
   - 如果 LoRA 是用 v1 prompt 訓練的，但你現在用 v2_improved prompt → LoRA 不會生效甚至會降效
   - 若不一致，需要重新訓練 LoRA using v2_improved prompt

2. **輸出 schema 對齊**
   - LoRA 應該輸出和 base CriterionChecker 一樣的 JSON schema
   - 確保 pipeline 下游（logic engine）能解析

## 成功判準

作為 primary system replacement:
- 12c_Acc 從 0.432 → ≥ 0.45
- 12c_Top1 從 0.531 → ≥ 0.55
- F1_macro 從 0.202 → ≥ 0.25

注意：criterion +20pp 通常不會**線性**傳導到 end-to-end +20pp，因為 diagnostician 和 calibrator 才是 ranking 的主導。預期 end-to-end +3-5pp 算成功。

## 輸出

- `results/validation/t3_lora_checker/`

## 實際執行建議

1. 先跑 N=200 smoke test 看 criterion accuracy 是否真的 +20pp（在 v2.4 pipeline context 下）
2. 如果 smoke 沒升，表示 prompt 不對齊或 loading 有問題，先修
3. 升了才跑 N=1000 full
