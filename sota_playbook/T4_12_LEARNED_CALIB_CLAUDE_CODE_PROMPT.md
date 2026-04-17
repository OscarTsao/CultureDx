# T4-CALIB-LEARNED：Claude Code 執行 Prompt

```
你在 CultureDx repo，main-v2.4-refactor 分支。目標：用 LightGBM LambdaRank 訓練一個 learned calibrator 取代目前的 heuristic-v2，讓 ranking 直接從 14000 train cases 學 pairwise preference。這是為了提升 12c_Top1 (目前 0.531) 和 12c_Top3 (目前 0.554)。

完整設計：T4_12_LEARNED_CALIB.md。

這是個 high-effort track，預計 12-16h 工時（含 bootstrap + feature eng + train + eval）。

STEP 1：Bootstrap training features from factorial_b on train split
- 目標：在 14000 train cases 上跑完整 factorial_b pipeline（diagnostician + checker + logic_engine），存 checker outputs 和 logic engine outputs
- 這會花 8-10 小時 GPU 時間
- 建議用現有 factorial_b config 但不要跑 calibrator/comorbidity（後面要替換這部分）
- 指令大概：
  uv run culturedx run -c configs/base.yaml -c configs/vllm_awq.yaml -c configs/v2.4_final.yaml -c configs/overlays/checker_v2_improved.yaml -d lingxidiag16k --split train -n 14000 -o outputs/factorial_b_train_bootstrap
- 確保 predictions.jsonl 裡面每個 case 有 decision_trace.raw_checker_outputs 和 logic_engine_output

STEP 2：Feature extraction
- 新增 scripts/extract_calibrator_features.py
- 讀 bootstrap 的 predictions.jsonl
- 對每個 case × 每個 confirmed/rejected disorder 產生 feature vector（設計文件有 feature list）
- 重要 features:
  - met_count, total_count, met_ratio
  - n_insufficient_evidence
  - avg_criterion_confidence
  - meets_threshold, confirmation_type_soft
  - disorder_freq_in_train (hardcoded from paper Table 2)
  - is_low_freq
  - somatic_keywords_matched
  - diagnostician_rank (from the ranked_codes list)
  - transcript_length, n_turns
- Label: 1 if disorder_parent in gold, else 0
- Group: each case = one group (all candidates belong same group)
- 輸出 numpy .npz 包含 X, y, group

STEP 3：Train LightGBM LambdaRank
- 新增 scripts/train_learned_calibrator.py
- 用 lightgbm, objective="lambdarank", metric="ndcg", eval_at=[1,3]
- train_test_split 90/10 內部驗證
- num_boost_round=500, early_stopping=50
- 儲存 model 到 outputs/learned_calibrator/lgbm_lambdarank.txt
- 輸出 feature importance，確認哪些 features 最重要

STEP 4：Integrate to pipeline
- src/culturedx/diagnosis/calibrator.py 新增 LearnedCalibrator class
- 接受 model_path 參數，載入 LGBM booster
- rank(case, confirmed, rejected) 方法：
  - 對所有候選抽 features（用同一個 extract_calibrator_features）
  - predict scores
  - 按 score 排序

STEP 5：Config
- configs/overlays/t4_learned_calib.yaml
- mode.calibrator_mode: learned
- mode.calibrator_model_path: outputs/learned_calibrator/lgbm_lambdarank.txt

STEP 6：Evaluation
- Smoke N=200 比 factorial_b
- Full N=1000 比 factorial_b
- 比較 12c_Top1, Top-3, F1_macro, F1_w
- 特別看 Top-3 是否 +3pp 以上

STEP 7：Analysis
- Print feature importance top-20
- 分析哪些 features 是 Top-1 ranking 的主力
- 對 F41 under-prediction 是否改善（看 F41 recall 是否升）

驗收：
- 12c_Top1 ≥ 0.55（+2pp from 0.531）
- 12c_Top3 ≥ 0.60（+5pp from 0.554）
- F1_macro 不降

如果 Step 1 bootstrap 太貴，可以改成：
- 只用 validation set (1000 cases) 做 10-fold CV train/eval
- 結果會差（overfitting 大），但省 8 小時 GPU 時間
- 論文中當作「proof of concept」，主 result 還是用 full bootstrap

或跳過此 track 完全，用 T2-RRF + T3-TFIDF-STACK 已足夠贏 SOTA。
```
