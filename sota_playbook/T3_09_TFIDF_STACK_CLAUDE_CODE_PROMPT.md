# T3-TFIDF-STACK：Claude Code 執行 Prompt

```
你在 CultureDx repo，main-v2.4-refactor 分支。目標：把 TF-IDF+LR 訓練成一個 supervised baseline（對齊論文 Table 4 的 TFIDF_CONFIG），然後作為第 4 個 ensemble member 和現有三個系統做 RRF 融合。這是最便宜的 SOTA 推進路徑（預期在所有 12c metric 贏過 paper baseline）。

完整設計：T3_09_TFIDF_STACK.md。

先決條件檢查：
- 確認 data/raw/lingxidiag16k/ 下有 train / validation json
- 確認 src/culturedx/eval/lingxidiag_paper.py 的 to_paper_parent_list() 和 compute_table4_metrics() 已經正確實作（這是你以前做 factorial_b 評估用的）

STEP 1：訓練 TF-IDF + LR
- 新增 scripts/train_tfidf_baseline.py（完整內容見設計文件）
- 使用 paper config: max_features=10000, ngram(1,2), min_df=2, max_df=0.95
- 用 OneVsRestClassifier(LogisticRegression(max_iter=2000, C=1.0))
- 儲存 vectorizer.pkl, classifier.pkl, mlb.pkl 到 outputs/tfidf_baseline/

STEP 2：Case ID alignment — 關鍵步驟
- TF-IDF 產生的 case_id 必須和 DtV 系統的 case_id 一致才能做 ensemble
- 打開 results/validation/factorial_b_improved_noevidence/predictions.jsonl 看 case_id 格式
- 在 train_tfidf_baseline.py 裡面，讀 validation JSON 時用**相同的 case identification 邏輯**
  （通常是檔案裡的 "id" 或 "case_id" field，或用 index）
- 確保兩邊的 case_id list 完全重合

STEP 3：產生 predictions.jsonl
- TF-IDF predict_proba 輸出 (N, 12) 機率
- 對每個 case 產生：
  - primary_diagnosis: 最高 proba 的 class
  - comorbid_diagnoses: proba >= 0.3 的次選（最多 1 個）
  - top10_codes: proba 排序的 top-10
  - proba_scores: 所有 12 類的分數
- 輸出到 outputs/tfidf_baseline/predictions.jsonl

STEP 4：單獨評估 TF-IDF baseline
- 用 src/culturedx/eval/lingxidiag_paper.py 評估 outputs/tfidf_baseline/predictions.jsonl
- 目標：12c_F1_macro ≈ 0.29, Top-3 ≈ 0.64, Overall ≈ 0.53 (對齊論文)
- 如果你複現不出來，printing 每類的 per-class metrics 找差異

STEP 5：4-way RRF ensemble
- 修改 scripts/run_ensemble.py
- 加入 TF-IDF 作為第 4 個 system
- 對 weights_grid 做 sweep（設計文件有 5 組建議 weights）
- 對 k ∈ {30, 60, 100} sweep
- 印出每組的 12c metrics

STEP 6：挑最佳組合
- 綜合分數 = F1_macro*0.3 + F1_w*0.25 + Top-3*0.2 + Top-1*0.15 + Acc*0.1
- 輸出 results/validation/t3_tfidf_stack/
  - predictions.jsonl
  - metrics.json
  - summary.md
  - ablation.md（對比單 system, 3-way, 4-way）

STEP 7：論文敘事資料
- 產出兩個結果：
  (A) 純 DtV 3-way ensemble（不含 TF-IDF）— 作為 LLM-only 系統的最佳
  (B) 4-way w/ TF-IDF — 作為最終 SOTA
- 分開存兩個 results dir

驗收：
- 複現 TF-IDF baseline 的 F1_macro 在論文 0.295 ± 0.02 之內
- 4-way ensemble 在**所有 5 個 12c metric 超越所有 paper baselines**
- 特別：F1_macro ≥ 0.30, F1_w ≥ 0.52, Top-3 ≥ 0.66, Top-1 ≥ 0.53, Acc ≥ 0.44

注意：如果 TF-IDF baseline 跑出來 < 0.28 F1_macro，表示 case alignment 或 label processing 有問題，debug 那邊再繼續。

跑完後報告：
1. TF-IDF baseline 單獨 metrics vs 論文
2. 4-way ensemble 最佳 weights 和 metrics
3. 每個 12c metric 對比 paper SOTA 的 gap
```
