# T2-RRF：Claude Code 執行 Prompt

```
你在 CultureDx repo。目標：建立 Reciprocal Rank Fusion ensemble，把 factorial_b、qwen3_8b_dtv、05_dtv_v2_rag 三個已跑完的系統的 ranked list 合併，取得一個在所有 12c metric 都接近/超越最佳單系統的 fused prediction。

完整設計：T2_06_RRF_ENSEMBLE.md。

重要：此實驗不需要重跑 LLM，完全 post-hoc on existing predictions.jsonl。

STEP 1：建立 RRF module
- 新增 src/culturedx/ensemble/__init__.py（空）
- 新增 src/culturedx/ensemble/rrf.py
- 實作設計文件中的 rrf_fuse() 和 ensemble_predictions()
- 加 pytest：tests/test_rrf.py
  測試案例：
  (a) 三個 ranked lists 都把 "F32" 排 top → RRF 後 F32 排第一
  (b) 一個 list top=F43，其他 list F43 根本沒出現 → F43 score 依然有，但排名在 top-3 左右
  (c) weights 生效（給 factorial_b 1.5 倍時，factorial_b 的 top-1 應壓過其他）

STEP 2：driver script
- 新增 scripts/run_ensemble.py
- 讀三個 predictions.jsonl
- 對 case_id 做 intersection（三個系統都預測過的 cases）
- 跑一個 weights + k grid:
  k ∈ {30, 60, 100}
  weights ∈ {[1,1,1], [1.5,1,1], [1,1.5,1], [1,1,1.5], [1.2,1.2,0.8]}
- 每個組合印出 table4 metrics

STEP 3：挑最佳組合
- 綜合分數 = F1_macro * 0.4 + Top-1 * 0.25 + Top-3 * 0.2 + F1_w * 0.15
- 或根據你想優先哪個指標調整

STEP 4：把最佳組合的完整預測寫入 results/validation/t2_rrf/
- predictions.jsonl
- metrics.json (table4)
- summary.md
- per_class.json

STEP 5：Per-class analysis
- 分析哪些 class 因為 RRF 得到 recall 提升
- 特別看 F43/F45/F51/F39 是否因為 qwen3_8b_dtv 提供的多樣性抓回來

STEP 6：報告
- 和 factorial_b 單系統對比表格
- 印出 improvement summary

驗收：
- 至少 3 個 12c metric 嚴格優於 factorial_b
- 12c_Top3 ≥ 0.63
- 12c_F1_macro ≥ 0.22

若 RRF 沒法改善所有 metric，至少要給「沒改善的 metric 是因為什麼原因」的分析，例如某個 class 在所有三個系統都錯。
```
