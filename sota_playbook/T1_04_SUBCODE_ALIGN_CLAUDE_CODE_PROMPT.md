# T1-SUBCODE：Claude Code 執行 Prompt

```
你在 CultureDx repo，main-v2.4-refactor 分支。目標：建立 diagnostician v2_subcode variant，把官方 LingxiDiagBench 的完整 ICD-10 subcode 描述（F32.0/F32.1/.../F51.0/F51.9 等）整合到 diagnostician prompt，對齊他們所有 LLM baseline 的 prompt 結構。這是為了提升 12c_Top3（目前 0.554, SOTA 0.645, gap -9.1pp）。

完整設計：T1_04_SUBCODE_ALIGN.md。

STEP 1：取得官方 prompt 內容
- 克隆或 wget https://github.com/Lingxi-mental-health/LingxiDiagBench 
- 讀 evaluation/static/prompts/category_12class.txt
- 把完整內容抽出來作為新 prompt 的 candidate description 區塊

STEP 2：建立新 prompt variant
- 新增 prompts/agents/diagnostician_v2_subcode_zh.jinja
- 結構：
  (開頭保留 v2 的結構化臨床推理 7 個 step)
  (把「候選診斷」區塊從原本的 for-loop 換成 inline 完整 subcode 描述)
  (注意：如果你要用繁體，請把官方簡體版本對應轉繁體；或乾脆用簡體但保持一致)

STEP 3：在 src/culturedx/agents/diagnostician.py 加入新 variant
- 加入 elif prompt_variant == "v2_subcode" and input.language == "zh"

STEP 4：Config
- configs/overlays/t1_subcode.yaml
- prompt_variant: v2_subcode
- checker_prompt_variant: v2_improved

STEP 5：Smoke N=50
- 跑完後檢查 predictions.jsonl 裡 diagnostician.ranked_codes
- 確認出現 subcode 層級的預測（e.g., F32.1, F41.0），而不只是 parent code
- 如果全部還是 parent code，debug prompt，確認 prompt 真的被用了（可以 log 第一個 case 的完整 prompt）

STEP 6：Full N=1000
- -o results/validation/t1_subcode
- 印出 12c_Top1, Top3, F1_macro 和 factorial_b 的對比

STEP 7：額外 sanity check
- 統計 top-3 candidates 中出現 subcode 比例（F32.1 vs F32 parent）
- 應該 ≥ 30%，否則 prompt 沒被 LLM 完整 parse

STEP 8：進階分析
- 對 F41 class 做特別觀察：
  - 有多少 F41 gold 被 diagnostician 正確區分為 F41.0 (panic) vs F41.1 (GAD)
  - 提升了多少

驗收：
- 12c_Top3 ≥ 0.58（+3pp from 0.554）
- 12c_Top1 ≥ 0.52（不降超過 1pp）
- subcode 預測比例 ≥ 30%

報告完整 git diff 和實驗結果。
```
