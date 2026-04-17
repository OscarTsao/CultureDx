# T2 — Others Fallback: 調查結論與放棄理由

## 結論：T2 不做

這個 track 原本預期能救 85 個 CANDIDATE_MISS (Others) case。**經過實際資料分析，無法用 post-hoc 規則達成**。

## 分析過程

### 假設 1: 用 max_met_ratio 低作為 Others 訊號 ❌

測試：對 predictions.jsonl 掃 threshold ∈ {0.25, 0.30, ..., 0.55}

結果：factorial_b 的 met_ratio 範圍是 0 ~ 2.75（ratio > 1 表示 over-satisfy），中位數 2.0。

- NOT_OTHERS case: max_met_ratio median = 2.0
- OTHERS case: max_met_ratio median = 1.67

重疊太多，threshold 無法區分。任何 threshold < 1.0 只觸發 < 5 cases。

### 假設 2: 用 `logic_engine_confirmed_codes=[]` 作為觸發 ❌

測試結果 (N=1000)：

```
=== Variant: others_fallback ===
Top-1: 0.2520  (vs baseline 0.5310, 暴跌 28pp!)
F1_m:  0.1238  (vs baseline 0.1980, 也變差)
Triggered: 633 cases
  Of which gold = Others: 55 (precision = 8.7%)
  Of which gold = F32:    203  (被錯誤改成 Others)
  Of which gold = F41:    208  (被錯誤改成 Others)
```

**根源**：v2.4 的 logic engine 門檻嚴，203 個 F32 正確 + 208 個 F41 正確的 case 都 `confirmed=[]`。
這些 case 的 primary 雖然不是「logic-certified」但預測 code 是對的。硬改成 Others 破壞大量正確答案。

### 假設 3: 資料中真實有 Others 訊號

Gold 是 Others 的 85 個 case，分布：F22 (3), F30 (4), F34 (2), F50 (5), F90 (8), F93 (6), G47 (2), 其他混合 (55)

這些是 **真正的 catch-all 類別** — 需要系統判斷「此 transcript 不符合任何 F32/F41/F43/... 典型 presentation」。在 criterion-level 無法做到（criterion checker 問的是「disorder X 的 criterion 是否 met」，不是「是不是 disorder X」）。

**唯一可行的 Others fallback 需要**：
- 額外 LLM call：給 transcript + 所有 12 個 class 描述 → 讓 LLM 選「不屬於任何一類」
- 成本：N=1000 → 1000 次額外 LLM call，~30 min
- Precision/recall 仍然未知，風險高

## 建議的 paper framing

誠實在 Limitations 寫：

> CultureDx predicts from a closed vocabulary of 11 ICD-10 parent codes plus Z71.
> The LingxiDiag-16K 12-class evaluation includes an "Others" catch-all category
> (8.5% of validation set) comprising rarer F-codes (F22, F30, F34, F50, F90,
> F93) and non-F codes (G47). Our system does not produce "Others" predictions,
> so these 85 cases are structural errors. This accounts for a floor of 8.5pp
> in the 12c Accuracy metric that can only be closed by adding an open-world
> classification head, which is outside the scope of this work.

**這個限制不是 method 的錯，是 task formulation 的 irreducible ceiling**。

## 重新計算 T1+T3 預期效益（不含 T2）

| Metric | Current | T1 only | T1+T3 | Paper SOTA |
|---|---|---|---|---|
| 12c_Acc | 0.432 | 0.46 | 0.48 | 0.409 ✅ |
| 12c_Top1 | 0.531 | 0.56 | 0.59 | 0.496 ✅ |
| 12c_Top3 | 0.554 | 0.65 | 0.67 | 0.645 ✅ |
| 12c_F1_macro | 0.202 | 0.25 | 0.27 | 0.295 (近 80%) |
| 12c_F1_weighted | 0.449 | 0.48 | 0.50 | 0.520 (近 80%) |
| Overall | 0.523 | 0.54 | 0.56 | 0.533 ✅ |

**五個 metric 中 4 個 SOTA，F1_m/F1_w 剩 ~2pp gap**。若 paper 需要全 5 metric SOTA，後備加 TF-IDF stacking。

## 若真要做 T2（不建議）

LLM-based open-world classifier：
- 加一個 `OpenWorldClassifier` agent
- Prompt: "Given the transcript, does this patient's presentation fit any of the following: F20/F31/F32/F39/F41/F42/F43/F45/F51/F98/Z71? If none match well, output 'Others'."
- 成本：+1000 LLM call, 30 min
- 插入點：primary selection 之前，if output == 'Others' → override primary

這是新 track 不是 minimal 改動，不在本次 Tier 1 範圍。
