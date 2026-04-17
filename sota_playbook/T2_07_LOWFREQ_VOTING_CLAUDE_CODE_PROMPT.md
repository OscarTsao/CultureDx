# T2-LOWFREQ：Claude Code 執行 Prompt

```
你在 CultureDx repo，已經完成 T2-RRF。現在要在 RRF 輸出之上加一層 asymmetric boost，對 low-freq class (F43/F45/F51/F98/Z71/Others/F39/F20/F31) 做 precision rescue。目標：把 F1_macro 從 0.22 推到 0.25+。

完整設計：T2_07_LOWFREQ_VOTING.md。

重要：此實驗依賴 T2-RRF 先完成，不需要重跑 LLM。

STEP 1：建立 lowfreq_boost module
- 新增 src/culturedx/ensemble/lowfreq_boost.py
- 實作 lowfreq_boost() 函式
- 加 pytest tests/test_lowfreq_boost.py，測試：
  (a) 三系統都 top-1 = F32 → lowfreq_boost 沒影響
  (b) 一個系統 top-1 = F43，另外兩系統 F43 在 top-5 → F43 得到 0.2 boost
  (c) top1=F32 (score 0.5), top2=F43 (score 0.498) → tie swap，F43 變新 top-1

STEP 2：擴充 run_ensemble.py
- 在 RRF 結果之後呼叫 lowfreq_boost
- 同時記錄：
  - 純 RRF 結果
  - RRF + boost 結果
  對兩個版本都跑 compute_table4_metrics，便於比較

STEP 3：Grid search
- low_freq_boost ∈ {0.10, 0.15, 0.20, 0.25, 0.30}
- tie_threshold ∈ {0.005, 0.01, 0.02}
- 共 15 組合，印出每組的 F1_macro / F1_w / Top-1 / per-class F1 表

STEP 4：Pareto 分析
- 畫 F1_macro vs Top-1 scatter plot
- 選一個「Top-1 下降最少但 F1_macro 最大」的 boost 組合
- 這個組合作為最終 T2 ensemble

STEP 5：固定最佳組合，生產 t2_lowfreq 目錄
- results/validation/t2_lowfreq/ 完整輸出
- 包含：predictions.jsonl, metrics.json, per_class.json, summary.md
- summary.md 必須包含：哪些 low-freq class 得到最大幫助、F32 precision drop、最佳 boost 參數

STEP 6：報告
- 和 factorial_b + T2-RRF 兩個 baseline 對比
- 印出 per-class F1 對比表

驗收：
- F43 F1 ≥ 0.30
- F98 F1 ≥ 0.20
- Others F1 ≥ 0.25
- F1_macro ≥ 0.25
- F32 precision drop ≤ 3pp
- Top-1 drop ≤ 2pp vs factorial_b

若 boost 總是 hurt 大類，請輸出 Null Result 分析：也許 boost 不是正確方向，改建議走 T3 supervised track。
```
