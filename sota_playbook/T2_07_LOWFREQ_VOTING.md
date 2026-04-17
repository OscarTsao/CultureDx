# T2-LOWFREQ：Low-frequency Class Rescue Voting

## 問題

即使做了 T2-RRF，low-frequency classes（F43, F45, F51, F98, Z71, Others）依然可能被 majority 系統壓倒。RRF 本質是「加權 rank 合併」，當三個系統**都沒把** F98 放進 top-5 時，RRF 輸出一樣沒 F98。

資料集分佈（gold N=1000）：
- F32: 365 (36.5%) — 佔大宗
- F41: 358 (35.8%) — 佔大宗
- F43: 11 (1.1%)
- F42: 25 (2.5%)
- F45: 8 (0.8%)
- F51: 36 (3.6%)
- F98: 30 (3.0%)
- F39: 60 (6.0%)
- Z71: 8 (0.8%)
- Others: 85 (8.5%)
- F20: 5 (0.5%)
- F31: 9 (0.9%)

low-freq class 合計 ~267 cases (26.7%)，F1_macro 的 7/12 權重被它們佔。**不解決長尾就永遠拿不到 F1_macro SOTA**。

## 假設

設計一個 **class-aware precision-boost voting**：

1. 先 RRF 產生 top-3
2. 對 low-freq class (F43/F45/F51/F98/Z71/Others/F39/F20/F31)，若任何一個系統在 top-1 輸出該 low-freq class → 給它額外 +0.2 RRF score boost
3. 對 F32/F41（over-predicted classes），若最高分比第二名 RRF score 只多 < 0.01 → 把 top-1 換成第二名
4. 保留 primary/comorbid 輸出

這是一種「**對長尾有利的 asymmetric fusion**」。

## 風險

- 如果 low-freq class 其實不該預測（gold=F32 卻因為 boost 變 F43），會 hurt F32 precision
- 所以 boost 強度要 tune

## 技術改動

### 檔案 1：`src/culturedx/ensemble/lowfreq_boost.py`

```python
"""Low-frequency class rescue voting on top of RRF."""

LOW_FREQ_CLASSES = {"F20", "F31", "F39", "F42", "F43", "F45", "F51", "F98", "Z71", "Others"}
HIGH_FREQ_CLASSES = {"F32", "F41"}

def lowfreq_boost(
    rrf_scores: list[tuple[str, float]],
    top1_per_system: list[str],
    low_freq_boost: float = 0.2,
    tie_threshold: float = 0.01,
) -> list[tuple[str, float]]:
    """Apply class-aware boost to RRF output.
    
    Args:
        rrf_scores: list of (code, score) from RRF, sorted descending
        top1_per_system: top-1 prediction from each source system
        low_freq_boost: score boost for low-freq class if any system picked it as top-1
        tie_threshold: if top-1 beats top-2 by < threshold and top-1 is high-freq,
                       swap them
    
    Returns:
        adjusted (code, score) list, re-sorted
    """
    from collections import defaultdict
    scores = dict(rrf_scores)
    
    # Boost low-freq if any system voted top-1 for it
    for code in set(top1_per_system):
        parent = _to_parent(code)
        if parent in LOW_FREQ_CLASSES and parent in scores:
            scores[parent] += low_freq_boost
    
    adjusted = sorted(scores.items(), key=lambda x: -x[1])
    
    # Tie-break: if top-1 is high-freq and top-2 is low-freq within tie_threshold, swap
    if len(adjusted) >= 2:
        top1_code, top1_s = adjusted[0]
        top2_code, top2_s = adjusted[1]
        if _to_parent(top1_code) in HIGH_FREQ_CLASSES and \
           _to_parent(top2_code) in LOW_FREQ_CLASSES and \
           (top1_s - top2_s) < tie_threshold:
            adjusted[0], adjusted[1] = adjusted[1], adjusted[0]
    
    return adjusted

def _to_parent(code):
    import re
    m = re.match(r'([FZ]\d{2})', code)
    return m.group(1) if m else code
```

### 檔案 2：修改 `scripts/run_ensemble.py`

在 RRF 後加入 lowfreq_boost 呼叫，同時輸出兩個版本比較（純 RRF vs RRF+boost）。

### Config sweep

`low_freq_boost ∈ {0.1, 0.15, 0.2, 0.25, 0.3}`
`tie_threshold ∈ {0.005, 0.01, 0.02}`

## 成功判準

- F43 F1 ≥ 0.3（baseline 0 → target 0.3+）
- F98 F1 ≥ 0.2
- Others F1 ≥ 0.25
- F1_macro ≥ 0.25
- F32 precision 下降 ≤ 3pp（不能傷大類太多）
- Top-1 不降超過 2pp

## 輸出路徑

`results/validation/t2_lowfreq/`

## 後續

這個 track 完成後，可以和 T2-RRF 合併成 `t2_rrf_lowfreq` 作為最終 ensemble baseline，讓 T3 stage 在此之上做 supervised stacking。
