# T1-OTHERS：Claude Code 執行 Prompt

```
你在 CultureDx repo（main-v2.4-refactor 分支）。目標是加入 Others fallback 到 logic engine：當沒有任何 disorder 符合 threshold、且最高 met_ratio < 0.5 時，輸出 primary_diagnosis = "Others"。這會救回 LingxiDiag-16K 的 85 個 Others cases（目前預測 = 0）。

完整設計：見 T1_02_OTHERS_FALLBACK.md。

STEP 1：修改 DiagnosticLogicEngine
- 檔案：src/culturedx/diagnosis/logic_engine.py
- 在 __init__ 加入 others_fallback_threshold: float = 0.5 參數
- 在 evaluate() 的 return 前，若 confirmed 為空且 max(rejected 的 met_ratio) < threshold，就 append 一個 LogicEngineResult(disorder_code="Others", meets_threshold=True, confirmation_type="others_fallback")
- 跑 pytest tests/ 確認沒 break

STEP 2：確保 comorbidity resolver 不會拒絕 "Others"
- grep "Others" src/culturedx/diagnosis/comorbidity.py
- 如果 Others 被當作 invalid disorder，改成允許它通過（但不能有 comorbid diagnoses）

STEP 3：確保評估 pipeline 能處理 "Others" primary diagnosis
- grep "Others" src/culturedx/eval/lingxidiag_paper.py
- to_paper_parent("Others") 應回傳 "Others"（pass-through），不應被正則匹配成其他

STEP 4：建立 overlay config
- 新增 configs/overlays/t1_others_fallback.yaml，內容見設計文件

STEP 5：Threshold sweep on N=200
- 跑 5 個 threshold 版本：0.3, 0.4, 0.5, 0.6, 0.7
- 每個 threshold 用 -n 200 跑，output 存 outputs/t1_others_sweep/th_{THRESHOLD}
- 比較 12c_F1_macro 和 Others F1，挑最佳 threshold

STEP 6：最終 N=1000 run 用最佳 threshold
- 改 threshold 到 configs/overlays/t1_others_fallback.yaml
- 跑 uv run culturedx run -c configs/base.yaml -c configs/vllm_awq.yaml -c configs/v2.4_final.yaml -c configs/overlays/checker_v2_improved.yaml -c configs/overlays/t1_others_fallback.yaml -d lingxidiag16k -n 1000 -o results/validation/t1_others
- 印出 12c_F1_macro、Others class F1、Top-1、和 factorial_b 的 diff

STEP 7：輸出 per-class analysis
- 存 results/validation/t1_others/per_class.json
- 特別檢查 Others class 的 recall 是否 ≥ 0.35

驗收：
- Others predictions count ≥ 30 (from 0)
- Others class F1 ≥ 0.25
- 12c_F1_macro ≥ 0.22
- Top-1 ≥ 0.52

附加：此實驗其實可以不重跑 LLM，直接 post-hoc replay factorial_b 的 raw_checker_outputs。如果你發現 factorial_b 有完整的 checker outputs 存在 predictions.jsonl 的 decision_trace.raw_checker_outputs 裡，請寫一個 scripts/replay_with_others_fallback.py 來快速 post-hoc evaluate 而不用重跑 LLM，這樣 5 個 threshold sweep 可以 10 分鐘跑完。

完成後印出 git diff 並報告結果。
```
