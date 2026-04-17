# T1-NOS：Claude Code 執行 Prompt

以下 prompt 可以直接貼給你本地的 Claude Code 執行。請在 `main-v2.4-refactor` 分支、乾淨 working tree 下執行。

---

```
你在 CultureDx repo（main-v2.4-refactor 分支）。目標是實作並執行 T1-NOS 實驗：加入 NOS routing rule 讓 diagnostician 在不確定時輸出未特指代碼（F39, F41.9, F45.9, F51.9, F43.9, Z71），用來提升 12c F1_macro。

參考完整設計：/path/to/T1_01_NOS_ROUTING.md（我先前 paste 給你的文件）。

請完成以下六個步驟：

STEP 1：建立新的 prompt variant 檔案
- 複製 `prompts/agents/diagnostician_v2_zh.jinja` → `prompts/agents/diagnostician_v2_nos_zh.jinja`
- 在新檔案的最開頭（第1步之前）插入「第0步：NOS 初篩」section，內容見設計文件
- 其餘保持不變

STEP 2：在 src/culturedx/agents/diagnostician.py 加入新 variant
- grep "prompt_variant" 找到 variant 選擇邏輯
- 加入 elif prompt_variant == "v2_nos" and language == "zh": template_name = "diagnostician_v2_nos_zh.jinja"

STEP 3：擴充 ontology criteria for NOS subcodes
- 找到 src/culturedx/ontology/icd10.py（或 criteria.py）裡 F41.1 的定義
- 新增 F41.9, F43.9, F45.9, F51.9 的 lenient rule（min_met=1, any_of 見設計文件）
- 請 grep "F41.9" 確認目前完全沒定義 → 新增後 pytest 不應 break

STEP 4：建立新 overlay config
- 新增 configs/overlays/t1_nos_routing.yaml，內容見設計文件
- target_disorders 必須擴充為 18 個含 NOS subcodes
- prompt_variant: v2_nos
- checker_prompt_variant: v2_improved （保留 factorial_b 的 winning checker）

STEP 5：先 smoke test
- uv run culturedx run -c configs/base.yaml -c configs/vllm_awq.yaml -c configs/v2.4_final.yaml -c configs/overlays/t1_nos_routing.yaml -d lingxidiag16k --data-path data/raw/lingxidiag16k -n 50 -o outputs/smoke_t1_nos
- 確認前 50 cases 跑完無 crash，預測分佈裡至少出現過 F39 或 F41.9 或 F45.9
- 如果預測分佈全部還是 F32/F41 → prompt 沒生效，debug

STEP 6：完整 N=1000 evaluation
- 改 -n 1000 -o results/validation/t1_nos 重跑
- 跑完後 cat results/validation/t1_nos/summary.md 檢查 table4 的 12class_F1_macro
- 和 factorial_b (0.2018) 比較，並印出 per-class breakdown
- 把 per-class 結果存到 results/validation/t1_nos/per_class.json（至少含 F20/F31/F32/F39/F41/F42/F43/F45/F51/F98/Z71/Others 的 precision/recall/f1）

驗收標準：
- N=1000 run 成功完成
- 12c_F1_macro ≥ 0.25（baseline 0.2018）
- F39 被預測次數 ≥ 10
- Top-1 不低於 0.51

如果 F1_macro 沒達到 0.25，請額外輸出「哪個 class 的 F1 沒提升」的診斷資訊，我再決定下一步。

不要動其他未提及的檔案。不要跑其他實驗。跑完後把所有改動 git diff 印出來。
```
