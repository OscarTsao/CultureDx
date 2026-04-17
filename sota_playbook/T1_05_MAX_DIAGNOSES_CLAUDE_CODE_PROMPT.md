# T1-MAXDX：Claude Code 執行 Prompt

```
你在 CultureDx repo，main-v2.4-refactor 分支。目標：加嚴 ComorbidityResolver 的限制，強制最多輸出 1-2 個 diagnosis，並做 comorbid_min_ratio 的 sweep 找最佳值。對齊 LingxiDiag 官方 prompt 的規則「大多只包含一個但不超過 2 個」。

完整設計：T1_05_MAX_DIAGNOSES.md。

STEP 1：加嚴 ComorbidityResolver
- 檔案：src/culturedx/diagnosis/comorbidity.py
- 讀現有實作，找到現在的 resolve() 方法
- 新增 max_diagnoses 參數（預設 2），移除/關掉任何會輸出 3+ 個 diagnosis 的邏輯
- comorbid_min_ratio 作為可配置參數

STEP 2：Config sweep
- 寫 scripts/sweep_comorbid_ratio.py
- 對 ratio ∈ {0.70, 0.80, 0.85, 0.90, 0.95} 用已跑完的 factorial_b predictions.jsonl 做 post-hoc replay（重算 primary/comorbid + 重評 table4）
- 不需要重跑 LLM！只是 replay 下游邏輯
- 輸出表格：ratio, 12c_Acc, Top-1, F1_macro, avg_pred_labels, comorbid_F1

STEP 3：挑最佳 ratio
- 以 12c_F1_macro * 0.5 + 12c_Acc * 0.3 + Top-1 * 0.2 作為綜合分數挑
- 印出最佳 ratio

STEP 4：Full N=1000 run 用最佳 ratio
- configs/overlays/t1_maxdx.yaml，填最佳 ratio
- -o results/validation/t1_maxdx
- 驗證 avg_predicted_labels 確實 ≤ 1.10

STEP 5：Per-class 分析
- 計算 comorbidity detection 是否在 F32+F41 pair 上改善
- LingxiDiag 裡約 10-15% 是 F32+F41 mixed presentation

驗收：
- avg_predicted_labels 1.0-1.1
- comorbidity_detection_f1 ≥ 0.18
- 12c_Acc ≥ 0.44
- Top-1 ≥ 0.52

若 sweep 顯示所有 ratio 都沒幫助，此 track 可以 skip，但請印出 sweep 表格證明 null result。
```
