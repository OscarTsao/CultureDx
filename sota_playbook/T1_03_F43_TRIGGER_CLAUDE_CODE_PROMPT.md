# T1-F43TRIG：Claude Code 執行 Prompt

```
你在 CultureDx repo，main-v2.4-refactor 分支。目標：建立一個 StressEventDetector 去偵測 transcript 中的應激事件（分手、失業、親人過世、車禍等），當偵測到時強制 F43.1/F43.2/F43.9 進入 DtV 的 verification top-2 candidate set。這會救回目前完全抓不到的 F43 類別（gold=11, pred=0）。

完整設計：T1_03_F43_TRIGGER.md。

STEP 1：新增 StressEventDetector
- 檔案：src/culturedx/agents/stress_detector.py
- 實作設計文件中的 StressSignal dataclass 和 StressEventDetector 類別
- 關鍵字列表用繁簡對照版本（"離婚/离婚", "過世/过世", ...）
- 加入 pytest 測試在 tests/test_stress_detector.py
  測試案例：
  (a) 包含「上個月跟男朋友分手」→ suggested_code == "F43.2"
  (b) 包含「小時候被虐待」→ suggested_code == "F43.1"
  (c) 純粹「最近心情不好」→ suggested_code == None

STEP 2：整合到 HiED pipeline
- grep HiEDMode 找到主 pipeline 檔
- 在 diagnostician 被呼叫之前插入 stress detection
- 如果 stress_signal.suggested_code 存在且在 candidate_disorders 中，把它強制加到 DtV verify_codes 的 top-2 (即使 diagnostician 沒把它排前 2)
- 不要修改 diagnostician 本身的 ranking，只改 DtV 的 verify set

STEP 3：新增 overlay config
- configs/overlays/t1_f43_trigger.yaml
- 啟用 stress_detection.enabled = true
- 保留 checker_v2_improved

STEP 4：Smoke test
- uv run culturedx run -c ... -c configs/overlays/t1_f43_trigger.yaml -n 50
- 印出 smoke_t1_f43 的 predictions.jsonl 裡面 primary_diagnosis 是 F43.x 的 cases（應該 ≥ 1）
- 如果沒有任何 F43.x 預測出現，debug stress detector

STEP 5：Full N=1000 run
- -n 1000 -o results/validation/t1_f43trig
- 印出 per-class F1 的改動：
  F43 gold=?, pred=?, F1=?
  其他類別 F1 是否有顯著下降

STEP 6：整合測試（可選）
- 檢查 stress_detector 對 F32 cases 的誤觸率：
  python scripts/analyze_stress_trigger.py results/validation/t1_f43trig/predictions.jsonl
  應該報告：stress_signal 觸發比例 vs gold F43 比例
  如果觸發比例 >> gold 比例（過度觸發），表示關鍵詞太寬

驗收：
- F43 class F1 ≥ 0.4
- 12c_F1_macro ≥ 0.22
- F32/F41 recall 下降 ≤ 3pp（不能把所有 F32 也被誤判成 F43.2）
- Top-1 ≥ 0.51

如果 stress_detector 對 F32 誤觸率過高（>20%），請降低關鍵字 trigger 條件，改成「應激關鍵字 + 最近時間標記」同時出現才觸發，否則只升級 F43 到 top-5 而非 top-2。

報告完成後的 git diff。
```
