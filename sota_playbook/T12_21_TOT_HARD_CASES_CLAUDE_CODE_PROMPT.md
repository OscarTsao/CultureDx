# T12-TOT-HARD-CASES：Claude Code 執行 Prompt

```
你在 CultureDx repo。目標：對 factorial_b 輸出的「低信心 hard cases」觸發 Tree-of-Thoughts 深度推理，提升這部分案例的 accuracy，predict overall Top-1 +1.5-2pp。

完整設計：T12_21_TOT_HARD_CASES.md。

STEP 1：建立 hard case detector
- 新增 src/culturedx/agents/hard_case_detector.py
- 實作 is_hard_case() 函數，返回 True 對以下條件：
  (a) calibrator top-1 score < 0.7
  (b) top-1 vs top-2 score gap < 0.1
  (c) 3+ disorders confirmed
- 統計在 factorial_b 的 predictions.jsonl 上有多少 case 是 hard case（預期 20-30%）

STEP 2：建立 ToT branching agent
- 新增 prompts/agents/tot_branching_zh.jinja（設計文件有完整 prompt）
- 新增 src/culturedx/agents/tot_agent.py
- 接受 top-3 candidates + criterion evidence
- 輸出結構化 JSON: branch A/B/C scores + final primary + confidence + reasoning

STEP 3：整合到 pipeline
- 修改 src/culturedx/modes/hied.py 或主 pipeline:
  - 在 calibrator/comorbidity 之後，最終輸出之前
  - 加 hard case detection
  - 如果是 hard case，呼叫 ToT agent
  - ToT 輸出覆蓋 primary/comorbid

STEP 4：Post-hoc replay（先低成本驗證）
- 新增 scripts/tot_replay_on_factorial_b.py
- 讀 factorial_b predictions.jsonl
- 識別 hard cases
- 只對 hard cases 呼叫 ToT agent
- 輸出 replay_predictions.jsonl
- 評估整體 metrics，對比原 factorial_b

STEP 5：Analysis
- 分 2 組 case：
  - Easy case (non-hard): factorial_b vs ToT 應該差不多
  - Hard case (hard): ToT 應該顯著改善
- 如果 easy case 也被 ToT 改壞，debug 觸發條件

STEP 6：Qualitative case studies
- 隨機挑 10 個 ToT 改變最終答案的 case（gold label 已知）
- 手動檢查：ToT reasoning 是否合理
- 挑 3 個 "ToT-saved"（ToT 對, factorial_b 錯）case 作為論文 qualitative evidence

STEP 7：整合進最終 ensemble（可選）
- 如果 ToT 在 hard cases 上顯著改善，把 ToT-enhanced factorial_b 當新 system 加入 ensemble
- 或者：直接用 ToT-enhanced 取代原 factorial_b 作為 ensemble 第 1 member

驗收：
- Hard cases (~25% of N=1000) 上 Top-1 accuracy 從 ~40% → ≥ 48%
- Easy cases Top-1 不變（sanity check）
- Overall Top-1 ≥ 0.55（baseline 0.531, +2pp）
- ToT reasoning qualitative 驗證：合理案例 ≥ 80%

成本：每個 hard case +1 次 LLM call，N=1000 total 多 ~250 calls，約 +30 分鐘。

如果 ToT 改善不夠（< +1pp overall），試 step-back prompting 變體（設計文件最後有）。

報告：hard case 比例、ToT 對 hard/easy 的邊際效益、qualitative case studies。
```
