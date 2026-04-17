# T1-OTHERS：Others Fallback in Logic Engine

## 問題

LingxiDiag-16K validation set 中有 85 個 Others cases（8.5% 覆蓋率）。你目前所有系統預測 Others 的次數 = 0。這 85 cases 全部被誤判為 F32 或 F41，每一個都是**純 FP + 純 FN**。

F1_macro 的計算是 12 類平均 F1，Others 永遠 F1=0 會讓 macro F1 有一個硬上限 = 11/12 × max_possible_avg_F1_of_other_11_classes。即使其他 11 類都完美，macro F1 也只能到 11/12 = 0.917。目前你是 0.202，Others 貢獻 0 占很大一部分。

## 假設

在 logic engine 後加一個 final fallback：**若所有 disorder 的 met_ratio 都 < 0.5（即沒有任何 disorder 真的符合），輸出 `["Others"]`**。這直接借鑒 LingxiDiagBench 官方 `llm_zeroshot_classifier.py` 第 294 行的做法：

```python
# 如果没有找到有效代码，返回Others
if not unique_codes:
    return ["Others"]
```

預期：
- Others recall 0% → 40%+（從 85 cases 救回 ~34+）
- F1_macro (Others 類) 從 0 → 0.3+
- 對 F1_macro 貢獻 約 +0.025（單獨一類 F1 從 0 → 0.3，12 類平均影響為 0.3/12 = 0.025）

## 預期風險

- 如果 threshold 設得太 lax（例如 met_ratio < 0.7），會導致正常 F32/F41 cases 被誤判為 Others
- 需要小心 calibrate 這個 threshold

## 技術改動

### 檔案 1：`src/culturedx/diagnosis/logic_engine.py`

在 `DiagnosticLogicEngine.evaluate()` 的 return 前加入 Others fallback 邏輯：

```python
class DiagnosticLogicEngine:
    def __init__(self, others_fallback_threshold: float = 0.5):
        self.others_fallback_threshold = others_fallback_threshold
    
    def evaluate(self, checker_outputs):
        confirmed = []
        rejected = []
        
        for co in checker_outputs:
            result = self._evaluate_disorder(co)
            if result.meets_threshold:
                confirmed.append(result)
            else:
                rejected.append(result)
        
        # ... existing sort ...
        
        # NEW: Others fallback
        if not confirmed:
            # no disorder was confirmed — check whether any disorder's met_ratio > threshold
            max_met_ratio = max(
                (r.met_count / max(r.required_count, 1) for r in rejected),
                default=0.0
            )
            if max_met_ratio < self.others_fallback_threshold:
                # really nothing fits — signal downstream to output Others
                # we encode this as a special "Others" LogicEngineResult
                others_result = LogicEngineResult(
                    disorder_code="Others",
                    meets_threshold=True,
                    met_count=1,
                    required_count=1,
                    rule_explanation="Fallback: no disorder met threshold, max_ratio={:.2f}".format(max_met_ratio),
                    confirmation_type="others_fallback",
                )
                confirmed = [others_result]
        
        return LogicEngineOutput(confirmed=confirmed, rejected=rejected)
```

### 檔案 2：`src/culturedx/diagnosis/comorbidity.py`（或下游）

確保 `ComorbidityResolver` 能接受 `"Others"` 作為 primary_diagnosis 而不 error out。

### 檔案 3：`src/culturedx/eval/lingxidiag_paper.py`

確認 `pred_to_parent_list` 已經支援 "Others" 作為 pass-through：

```python
def pred_to_parent_list(predicted_codes):
    if not predicted_codes:
        return ["Others"]
    # ... existing logic ...
    # 確保 "Others" 不會被 to_paper_parent 轉成別的
```

### 檔案 4：`configs/overlays/t1_others_fallback.yaml`（新檔）

```yaml
# Overlay: T1-OTHERS fallback — output Others when no disorder confirmed
mode:
  others_fallback_threshold: 0.5
  checker_prompt_variant: v2_improved
  prompt_variant: v2
```

## 輸出路徑

`results/validation/t1_others/`

## Threshold Calibration（必做）

在 full N=1000 run 前，用 N=200 做 threshold sweep：
- `others_fallback_threshold ∈ {0.3, 0.4, 0.5, 0.6, 0.7}`
- 選擇讓 F1_macro 最高且 Top-1 不降超過 1pp 的 threshold

## 成功判準

- Others 預測次數 ≥ 30（從 85 gold 救回至少 30）
- Others F1 ≥ 0.25
- F1_macro ≥ 0.22（baseline 0.202，+2pp）
- Top-1 ≥ 0.52（不低於 baseline 的 0.531 太多）

## 注意事項

這是一個 **pure logic change**，不動 LLM prompt。所以不需要重跑 diagnostician/checker LLM call，只要重新跑 logic_engine + calibrator + comorbidity 後處理。如果你把 checker_outputs 存成 jsonl，這個實驗可以在 30 分鐘內完成（只是 re-apply 下游處理）。

這意味著：**可以和 T1-NOS 的 checker_outputs 重用**，或對已跑完的 factorial_b 的 predictions.jsonl 做 post-hoc replay，加速實驗週期。
