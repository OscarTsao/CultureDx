# T8-TEST-SPLIT-EVAL：Claude Code 執行 Prompt

**重要**：這個 track 是所有 T1-T7 跑完、最終架構 frozen 後才執行的 paper-ready final evaluation。**跑完 test split 後禁止修改任何 hyperparameter**（學術誠信）。

完整設計：T8_17_TEST_SPLIT_EVAL.md。

```
你在 CultureDx repo。目標：對最終 frozen 的 CultureDx 架構在 LingxiDiag-16K test split (N=1000) 跑一次 holdout evaluation，產生 paper-ready final metrics。

**鐵律**：跑完 test split 後，任何 hyperparameter 修改都會使這次 test 結果失效。若需重跑，只能是 bug fix 且無關 metric 變化。

STEP 1：確認 test split file 存在
- ls data/raw/lingxidiag16k/ | grep -i test
- 期望檔名類似 LingxiDiag-16K_test_data.json
- 若不存在：
  (a) 從 LingxiDiagBench 官方 repo 下載: git clone https://github.com/Lingxi-mental-health/LingxiDiagBench /tmp/LXB && cp /tmp/LXB/data/*test* data/raw/lingxidiag16k/
  (b) 或從 HuggingFace dataset repo 下載

STEP 2：確認 dataset adapter 支援 --split test
- 讀 src/culturedx/data/adapters/lingxidiag16k.py
- grep "split" 看是否有 split 參數
- 若沒有，加入：
  def load(self, path, split="validation"):
      file_map = {"train": "...train...", "validation": "...validation...", "test": "...test..."}
      return self._load_file(file_map[split])
- 確認 CLI 可以 --split test 透傳

STEP 3：列出 final 架構的所有組件
- 根據 validation 上跑過的所有 T1-T7 實驗，列出哪些被選為 final:
  - T1: 哪些 overlay 啟用？(NOS, OTHERS, F43TRIG, SUBCODE, MAXDX)
  - T2: ensemble 是否使用？weights?
  - T3: TFIDF-STACK 是否用？LoRA-CLF/CHECKER 是否用？
  - T5/T6/T7: revived/RAG/self-consistency 是否啟用？
- 你先問我要 final 組合，我告訴你後再繼續

STEP 4：Freeze final config
- 建立 configs/final/culturedx_v3_final.yaml
- header 標記 FROZEN DATE
- 整合 STEP 3 所有 overlay
- 所有 hyperparameter (threshold, weight, etc.) 寫死成 val-tuned 的值

STEP 5：每個 ensemble member 在 test split 跑
- 依序：
  (a) factorial_b: uv run culturedx run -c ... --split test -n 1000 -o results/test/factorial_b --seed 42
  (b) qwen3_8b_dtv: 同上但 backbone 換
  (c) 05_dtv_v2_rag: 同上但 overlay 換
  (d) TF-IDF: python scripts/infer_tfidf.py --split test (TF-IDF 不重新訓練，只 inference)
  (e) 其他 member (T5/T6/T7): 各自跑
- 每個存 results/test/{system}/predictions.jsonl

STEP 6：跑 final ensemble
- python scripts/run_ensemble.py --split test --config configs/final/culturedx_v3_final.yaml --out results/test/culturedx_final/
- Weights 必須是 val 上 locked 的（不能根據 test 再調）

STEP 7：評估每個系統
- 用 src/culturedx/eval/lingxidiag_paper.py
- 產出 metrics.json per system
- 合併成 results/test/all_systems_metrics.json

STEP 8：Val vs Test gap 分析
- 對每個 system + final ensemble，計算 val - test 的 diff per metric
- 合理範圍 ≤ 2pp
- 若 > 3pp：flag，可能 overfitting
- 特別注意 F1_macro（因為 T4-F1-OPT 直接在 val tune offset）

STEP 9：Bootstrap CI on test
- python scripts/bootstrap_ci.py --predictions results/test/culturedx_final/predictions.jsonl --out results/test/culturedx_final/bootstrap_ci.json
- Report 95% CI for 所有 12c metrics

STEP 10：Paper-ready tables
- 產出 paper/tables/final_test_results.md，內含：
  Table 1：Main results (paper baselines 的 val 分數 + CultureDx 的 val + test 分數)
  Table 2：Val-test gap per metric
  Table 3：Per-class F1 on test (all 12 classes)
  Table 4：Bootstrap CI for test metrics

STEP 11：final sanity check
- 列出最佳 12c_Acc / Top-1 / Top-3 / F1_m / F1_w / Overall 分數
- 對照 paper baselines 最佳分數
- 標出哪些 metric 是 new SOTA (超越 paper 對應指標)

驗收：
- test split 上，至少 5 個 12c metric 中有 4 個嚴格超越 paper baseline SOTA
- val-test gap 在 F1_macro 上 ≤ 3pp（F1_macro 最脆弱）
- Bootstrap 95% CI 下限仍然超越 paper SOTA point estimate（強 claim）

若以上不滿足，誠實報告 gap，paper 需加 Limitations 章節討論。

報告：
1. Final frozen architecture 確認清單
2. 每個 member system val vs test 分數表
3. Final ensemble val vs test 分數
4. Bootstrap CI
5. 和 paper SOTA 的逐 metric 比較表
6. 任何發現的 overfitting signal
```
