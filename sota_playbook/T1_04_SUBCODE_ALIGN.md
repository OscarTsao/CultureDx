# T1-SUBCODE：Diagnostician Prompt 對齊官方 Subcode 描述

## 問題

LingxiDiag 官方 12c prompt（paper p.17 Appendix C.3.3）在 system prompt 裡**列出所有 F32.0~F32.9、F41.0~F41.9、F51.0~F51.9 等 subcodes 的一句話描述**。這是他們所有 LLM baseline（Qwen3-32B, GPT-5-Mini, DeepSeek-V3.2, Claude-Haiku-4.5）拿到 12c_Top1 0.46-0.50 的 prompt 基礎。

你的 `diagnostician_v2_zh.jinja` 目前只列 parent-level code 的描述，沒有 subcode 層級細節。這使得 LLM 對 subcode 粒度的判別弱於官方 baseline。

論文 Table 4 的 LLM baselines 在 12c_Top1 上都有 0.44-0.50，顯著高於你某些 run 的表現。雖然你 factorial_b 已達 0.531（超越 Top-1 SOTA），但 Top-3 和 m_F1 還有 gap，而 subcode 精度可能間接影響這些。

## 假設

把官方 prompt 的完整 subcode 描述（來自我前面抓的 LingxiDiagBench/evaluation/static/prompts/category_12class.txt）整合到你的 diagnostician prompt 中，預期：

- 12c_Top1 略升（可能 +1-2pp）
- 12c_Top3 更重要的升級，因為 top-3 要求有 diverse 的候選，subcode 描述能幫助區分 F32.1/F32.2（中度/重度）
- subcode 層級的 F41.0（panic）vs F41.1（GAD）區分提升

這可能是讓 12c_Top3 從 0.554 推到 0.62+ 的關鍵 prompt improvement。

## 技術改動

### 檔案 1：`prompts/agents/diagnostician_v2_subcode_zh.jinja`（新 variant）

將 candidate_disorders 的 for-loop 部分改成 inline 完整 subcode 描述，直接套用官方 prompt 格式：

```jinja
## 候選診斷（完整 ICD-10 子類別描述）

- **F32 抑郁发作**：情緒持續低落、興趣/愉快感下降、精力不足；伴睡眠/食慾改變、自責/無價值感等；可輕/中/重度（重度可伴精神病性症狀）；無既往躁狂/輕躁狂。
  - F32.0 輕度抑鬱發作：症狀輕，社會功能影響有限。
  - F32.1 中度抑鬱發作：症狀更明顯，日常活動受限。
  - F32.2 重度抑鬱發作，無精神病性症狀：症狀顯著，喪失功能，但無妄想/幻覺。
  - F32.3 重度抑鬱發作，有精神病性症狀：伴有抑鬱性妄想、幻覺或木僵。
  - F32.8 其他抑鬱發作；F32.9 抑鬱發作，未特指。

- **F41 其他焦慮障礙**：...
  - F41.0 惊恐障礙：突發的強烈恐慌發作，常伴濒死感。
  - F41.1 廣泛性焦慮障礙：長期持續的過度擔憂和緊張不安。
  - F41.2 混合性焦慮與抑鬱障礙：焦慮與抑鬱並存但均不足以單獨診斷。
  - F41.3 其他混合性焦慮障礙
  - F41.9 焦慮障礙，未特指

- **F39.x00 未特指的心境（情感）障礙**：存在心境障礙證據，但資料不足以明確歸入抑鬱或雙相等具體亞型時選用。

- **F51 非器質性睡眠障礙**：...
  - F51.0 非器質性失眠：入睡困難、易醒或睡眠不恢復精力。
  - F51.1 非器質性嗜睡
  - F51.2 非器質性睡眠-覺醒節律障礙
  - F51.3 夢魘障礙
  - F51.4 睡眠驚恐
  - F51.5 夢遊症
  - F51.9 非器質性睡眠障礙，未特指

（以下省略，完整內容直接複製官方 category_12class.txt）
```

具體 content 直接從 `/tmp/LingxiDiagBench/evaluation/static/prompts/category_12class.txt` 複製 + 繁體化。

### 檔案 2：在 diagnostician.py 加新 variant

```python
elif prompt_variant == "v2_subcode" and input.language == "zh":
    template_name = "diagnostician_v2_subcode_zh.jinja"
```

### 檔案 3：Config

```yaml
# configs/overlays/t1_subcode.yaml
mode:
  prompt_variant: v2_subcode
  checker_prompt_variant: v2_improved
```

## 輸出路徑

`results/validation/t1_subcode/`

## 成功判準

- 12c_Top1 ≥ 0.535（baseline 0.531, 至少不降）
- **12c_Top3 ≥ 0.58（baseline 0.554, +3pp）** ← 這是主目標
- F1_macro 不降
- subcode 層級的 F41.0（panic）/F41.1（GAD）區分應該更準

## 額外測試

跑完後做一個 sanity check：
- 統計 diagnostician ranked_codes 中出現 subcode 的比例（F32.1, F32.2 等）
- 應該顯著高於 v2 baseline，確認 prompt 有生效
