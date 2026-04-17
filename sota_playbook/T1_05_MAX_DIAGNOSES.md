# T1-MAXDX：強制輸出 1-2 個診斷（對齊官方 prompt）

## 問題

LingxiDiag 官方 12c prompt 明確規定：
> (2) 診斷結果可能包含 1 至 2 個 icd-10 診斷結果，**大多只包含一個但不超過 2 個**。
> (3) 用分號分隔不同的代碼。

官方 LLM baseline 在平均預測 label 數約為 1.0-1.1。

你目前系統（factorial_b）的 `avg_predicted_labels: 1.1100`（from summary.md），看起來接近，但實際上：
- 12c exact_match_accuracy = 0.432，而 Top-1 = 0.531
- 這個 10pp gap 的主因是**共病預測不足或過度**

特別是：
- `comorbidity_detection_f1: 0.1429`（很低）
- 有些 F32 gold 案例應該同時有 F41 共病（約 23% 論文顯示），你抓不到這些共病

## 假設

在 ComorbidityResolver 之後加一個 **MaxDx guardrail**：
1. 優先輸出 1 個 primary diagnosis
2. 只有當第二名候選的 met_ratio > 0.85 且與 primary 非互斥時，才加入 comorbid
3. 絕不輸出超過 2 個 diagnosis

這可能提升 exact_match (12c_Acc)，尤其是減少 over-prediction 帶來的 FP。

## 技術改動

### 檔案：`src/culturedx/diagnosis/comorbidity.py`

```python
@dataclass
class ComorbidityConfig:
    max_diagnoses: int = 2
    comorbid_min_ratio: float = 0.85  # stricter than before
    require_non_exclusive: bool = True

class ComorbidityResolver:
    def resolve(self, ranked_results):
        if not ranked_results:
            return [], []
        
        primary = ranked_results[0]
        comorbid = []
        
        # Try to add at most 1 comorbid
        for candidate in ranked_results[1:]:
            if len(comorbid) >= self.config.max_diagnoses - 1:
                break
            
            ratio = candidate.met_count / max(candidate.required_count, 1)
            if ratio < self.config.comorbid_min_ratio:
                continue
            
            if self.config.require_non_exclusive:
                if self._is_exclusive_with(primary.disorder_code, candidate.disorder_code):
                    continue
            
            comorbid.append(candidate)
        
        return primary, comorbid
```

### Config

```yaml
# configs/overlays/t1_maxdx.yaml
mode:
  comorbidity:
    max_diagnoses: 2
    comorbid_min_ratio: 0.85
```

## 成功判準

- `avg_predicted_labels` 降到 1.00-1.10 之間（不超過）
- `comorbidity_detection_f1` ≥ 0.2
- 12c_Acc (exact match) ≥ 0.44
- Top-1 不降

## 延伸

也可以做一個 ratio sweep：試 0.7 / 0.8 / 0.85 / 0.9 / 0.95 看哪個最優。
