# T4-F1-OPT：Class-Weighted Re-Ranking for F1_macro Optimization

## 動機

F1_macro 是你和 TF-IDF+LR 差距最大的指標（baseline 0.202 vs SOTA 0.295, -9.3pp）。

F1_macro = Σ F1_c / C，意思是 **每個類的 F1 等權重加總**。低頻類（F43/F45/F98/Z71）即使 gold 只有 8-30 cases，每類都貢獻 1/12 的分量。

你目前 5 類 F1=0（F43, F98, Z71, Others, 加上 F39 接近 0），這每一類都讓 F1_macro 掉 0.083。即使 F32/F41 F1 都完美，也只能達 7/12 = 0.583。

## 假設

加一個 **class-weighted re-ranking layer** 放在 calibrator 後面：
- 根據每類的 current recall，動態 boost under-predicted class 的 ranking score
- 用 validation set (或 held-out) 當 calibration data
- 做 post-hoc（不需重跑 LLM）

這類似 [Threshold Optimization for Imbalanced Classification] 的方法，但用在 ranking 而非 threshold。

## 技術設計

### 核心算法

```python
def f1_macro_optimize(predictions, validation_set):
    """Find per-class score adjustments that maximize F1_macro on val."""
    from scipy.optimize import minimize
    
    def neg_f1_macro(adjustments):
        # adjustments: array of per-class boost scores (len = 12)
        adjusted_preds = []
        for p in predictions:
            scores = p["class_scores"].copy()  # dict {class: score}
            for c, boost in zip(TWELVE_CLASS_LABELS, adjustments):
                scores[c] += boost
            new_primary = max(scores, key=scores.get)
            adjusted_preds.append({...})
        
        metrics = compute_f1_macro(adjusted_preds, validation_set)
        return -metrics
    
    # Optimize with random restarts + scipy
    best = -1
    best_adj = None
    for init in random_starts:
        result = minimize(neg_f1_macro, init, method='Nelder-Mead')
        if -result.fun > best:
            best = -result.fun
            best_adj = result.x
    
    return best_adj  # apply at test time
```

### 風險

- 如果 adjustments 是在 val set 上 optimize，**不能用於 final val evaluation**（這是 test contamination）
- 正確做法：用 half val 做 calibration，另 half 評估
- 或用 train set 做 calibration（但 LLM 在 train 上的 output distribution 和 val 可能不完全一樣）

### 替代方案：Grid-based per-class threshold

對每個類，在 train-bootstrap 上找最優 threshold:

```python
for disorder in TWELVE_CLASS_LABELS:
    best_th = None
    best_f1 = 0
    for th in np.arange(0.1, 1.0, 0.05):
        # If pred score for this disorder >= th, predict it
        f1_c = compute_per_class_f1(disorder, threshold=th, ...)
        if f1_c > best_f1:
            best_f1 = f1_c
            best_th = th
    class_thresholds[disorder] = best_th
```

這比 learned calibrator 輕，直接在現有 pipeline 最末端加「per-class threshold 調整」。

## 實際做法建議

先做輕量版：**post-hoc per-class score boost**

```python
# 從 factorial_b 的 output 開始
# 對每個 case，產生 class_scores (ranked list with scores)
# 加上 calibration offset：
#   F43 += +0.3 (很少預測，需要 boost)
#   F98 += +0.3
#   Z71 += +0.2
#   Others += +0.2
#   F39 += +0.2
#   F32 -= 0.1 (過度預測，要壓)
```

這些 offsets 可以 grid-sweep 在 half of val 上 optimize，另 half 評估，避免 test contamination。

## 成功判準

- F1_macro ≥ 0.25（+5pp from 0.202）
- F1_weighted 不降
- Top-1 下降 ≤ 3pp
- 5 個 class F1>0 (從 0 救起)

## 輸出

- `outputs/f1_macro_calibration/offsets.json`
- `results/validation/t4_f1_opt/`

## 和其他 track 的互補

T4-F1-OPT 是**最後的微調**，建議在 T1/T2 都跑完後最後做，用來榨取剩餘的 F1_macro gain。

不要和 T4-CALIB-LEARNED 同時做，兩者目標重疊。選其一。
