# T7-SELF-CONSISTENCY：Claude Code 執行 Prompt

```
你在 CultureDx repo，main-v2.4-refactor 分支。目標：對 Diagnostician 和 Criterion Checker 加入 self-consistency sampling（temperature > 0, n samples, majority vote），換取 +2pp Top-1 / Top-3。

完整設計：T7_16_SELF_CONSISTENCY.md。

這個 track 穩賺但貴（時間 3-4x）。建議先 N=200 smoke 看效益，再決定是否全做。

STEP 1：實作 SelfConsistencyWrapper
- 新增 src/culturedx/agents/self_consistency.py
- 實作設計文件中的 SelfConsistencyWrapper class
- 需要支援：
  (a) override LLM temperature 和 seed per-call
  (b) 聚合方法：majority vote (for single label)、RRF (for ranked list)、average probability (for checker met/not_met)

STEP 2：擴充 LLM client 支援 n_samples
- 讀 src/culturedx/llm/vllm_client.py
- 確認 vLLM 支援 n > 1 sampling（vLLM 原生支援 SamplingParams(n=5, temperature=0.5)）
- 如果沒暴露這個介面，加入 generate_n(prompt, n, temperature) 方法

STEP 3：Diagnostician SC 整合
- 修改 src/culturedx/agents/diagnostician.py
- 新增 sc_config 參數 (SCConfig object)
- 如啟用 SC：
  - 以 temperature=0.5 跑 n=5 次
  - 對 5 個 ranked_codes list 做 RRF fusion
  - 輸出 aggregated ranked_codes

STEP 4：Checker SC 整合
- 修改 src/culturedx/agents/criterion_checker.py
- 對每個 criterion check call 用 n=3 temp=0.3
- 3 次的結果：count "met" 次數，≥2 次判 met，否則 not_met
- 更新 CheckerOutput 加一個 sc_agreement 欄位（0-1 range，3/3=1.0, 2/3=0.67, ...）

STEP 5：Config
- configs/overlays/t7_sc_diag.yaml（僅 diagnostician SC）
- configs/overlays/t7_sc_full.yaml（diag + checker 都 SC）
- 同時保留 checker_v2_improved

STEP 6：Smoke N=200，三 configs 對比
- baseline: factorial_b (n=1, temp=0)
- t7_sc_diag: diag n=5, checker n=1
- t7_sc_full: diag n=5, checker n=3
- 印 metrics 對比 table
- 如果 t7_sc_diag 沒 +1pp Top-1，停下來 debug（檢查 temperature 是否生效、seed 是否差異）

STEP 7：Full N=1000 (若 smoke 有效)
- 決策：
  - 若 t7_sc_diag 改善 ≥ 1pp, 時間允許 → 跑 full
  - 若 t7_sc_full 比 t7_sc_diag 再改善 ≥ 0.5pp → 跑 full t7_sc_full
  - 否則 skip, 用 t7_sc_diag 的 full 結果

STEP 8：和其他 track 組合
- t7_sc_diag 的 predictions 作為第 6 個 ensemble member 疊到 T3-TFIDF-STACK
- 看是否再 push +1pp

STEP 9：Agreement analysis
- 分析 SC agreement (5 個 sample 中幾個投同一個 top-1) 和 accuracy 的相關
- 應該：高 agreement → 高 accuracy
- 這支持「low agreement cases 可以 flag 為 abstention / human review」
- 論文 ablation 可用

STEP 10：Cost 分析
- 記錄 wall-clock time for smoke (baseline vs sc_diag vs sc_full)
- 估算 full N=1000 需要多久
- 在 summary.md 寫 "cost vs benefit" 章節

驗收：
- t7_sc_diag 全跑 in N=1000:
  - Top-1 ≥ 0.545 (baseline 0.531, +1.5pp)
  - Top-3 ≥ 0.57
- t7_sc_full 全跑：額外 +0.5pp

如果 vLLM 的 SamplingParams(n=5) 不產生真的 diverse outputs（有時 vLLM 若 temperature 太低或 seed 一致會輸出相同結果），強制加 seed 參數：每個 sample 用不同的 seed (e.g., seed=i for i in range(n))。

報告：
1. SC smoke N=200 三配置 metrics 對比
2. SC agreement vs accuracy 散布圖（概念描述）
3. 成本 (hours) vs Top-1 改善 (pp)
4. 是否建議納入最終 pipeline
```
