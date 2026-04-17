# T2-CONTRAST：Claude Code 執行 Prompt

```
你在 CultureDx repo，main-v2.4-refactor 分支。目標：為 F32 vs F41.1 混淆添加一層專屬 contrastive disambiguation LLM agent。這是 factorial_b 的 F32 recall 86.6%但 precision 52.3% 的關鍵瓶頸（over-prediction F32 by 1.65x）。

完整設計：T2_08_F32_F41_CONTRASTIVE.md。

STEP 1：新增 prompt 模板
- 檔案：prompts/agents/f32_f41_contrastive_zh.jinja
- 接受 f32_criteria, f41_criteria, f32_met_ratio, f41_met_ratio, transcript_summary
- 輸出 JSON {verdict, reasoning, confidence}

STEP 2：新增 contrastive agent
- 檔案：src/culturedx/agents/contrastive_disambiguator.py
- 實作 F32F41ContrastiveDisambiguator
- 處理 LLM JSON parse failure fallback: 若 parse fail，保留原 primary
- 加 pytest 測試 JSON 解析和 edge cases

STEP 3：整合到 HiED pipeline
- grep HiEDMode 找主 pipeline
- 在 logic_engine 確認 confirmed_codes 之後、ranking finalize 之前插入 contrastive step
- 觸發條件：
  (a) F32 和 F41 都 confirmed → 必觸發
  (b) F32 confirmed 且 F41 的 met_ratio ≥ 0.6 → 觸發
  (c) F41 confirmed 且 F32 的 met_ratio ≥ 0.6 → 觸發
  (d) 其他情況不觸發（省 LLM 成本）

STEP 4：處理 transcript_summary
- contrastive 不該塞整個對話（太長），而是給 500 字內的摘要
- 簡單做法：取對話前後各 250 字，或取含關鍵症狀詞的段落
- 或使用 existing 的 triage 或 evidence 輸出作為 summary 來源

STEP 5：Config
- configs/overlays/t2_contrastive.yaml
- enabled: true
- 預設 f41_close_threshold: 0.6

STEP 6：Smoke N=100
- 跑完後印出：
  - 觸發 contrastive 的 case 比例（目標 30-60%）
  - 改變 primary 的 case 比例（目標 10-25%）
  - 被改成 comorbid 的 case 比例
  - LLM JSON parse fail 比例（目標 < 2%）

STEP 7：Full N=1000
- -o results/validation/t2_contrast
- 印 per-class 對比：F32 precision, F41 recall, 和 F1
- 印 Top-1, F1_macro, F1_w 和 factorial_b 對比

STEP 8：Ablation（可選）
- 和 factorial_b 跑同一 seed，對比 contrastive on/off 的 exact 差異
- 特別看：contrastive 把哪些 F32 改成 F41 → 是否都是真 F41?

驗收：
- F41 recall ≥ 0.58（+7pp）
- F32 precision ≥ 0.58（+6pp）
- Top-1 ≥ 0.55
- F1_macro 不降（應略升）
- LLM 額外 call 比例可接受（< 60%）

若 contrastive 並沒有改善 F32/F41 balance，分析失敗原因：
- 是 prompt 沒區分清楚？
- 還是 checker 的 criterion 資料本身就模糊？
- 還是 LLM 有 F32 bias？

報告完整 git diff + 結果。
```
