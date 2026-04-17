# T2-CONTRAST：F32 ↔ F41 Contrastive Re-ranking

## 問題

F32 (365 gold) 和 F41 (358 gold) 合佔 72.3% 的案例，是最大的混淆對。從你 factorial_b 的 per-class 分析：

| Class | Gold | Pred | Precision | Recall | F1 |
|---|---|---|---|---|---|
| F32 | 365 | 604 | 0.523 | **0.866** | 0.652 |
| F41 | 358 | 297 | 0.616 | **0.511** | 0.559 |

**F32 over-prediction by 1.65×**，F41 under-prediction by 0.83×。這代表很多真正 F41 的案例被 diagnostician 判成 F32。

歷史 narrative（from `docs/paper_narrative_v2.md` C6/C10/C11/C12）已經確認：
- F41→F32 是 cross-dataset 最主要 error（29.7%）
- Somatization mapping（胸悶→F41.1 B2）能救，但 precision ceiling 還是 52%
- Calibrator-level adjustments 是 zero-sum（給 F41 就要拿走 F32）

## 假設

在 diagnostician + checker 全部跑完後，對**被判為 F32 或 F41 的所有 cases 加一個 contrastive disambiguation step**：

1. Input: 該 case 的 F32 checker output + F41 checker output（包含所有 criterion level 證據）
2. Prompt LLM 做一個 **N-way pairwise comparison**：
   - "以下是兩個 disorder 的 criterion-level 評估。根據證據強度，哪個才是 primary？"
3. LLM 輸出：F32 > F41, F41 > F32, 或 both (comorbid)

這是 Stage 2.5（contrastive disambiguation）的升級版，你在 paper_narrative_v2.md 裡有類似概念但沒完整實作到 v2.4。

## 為什麼會贏

- LLM 在看到**兩個 disorder 的完整 criterion 證據並排比較**時，更容易看出「哪個核心症狀群更主導」
- 相比之下，原本的 diagnostician 是看整段 transcript 做排序，沒有這層 concentrated 比較
- 對 F41.1 的 B1/B2（somatic）特別有幫助：LLM 可以直接看到「F41.1 B1 met=True, B2 met=True, 但 F32 B1 only True」這種對比訊號

## 技術改動

### 檔案 1：`prompts/agents/f32_f41_contrastive_zh.jinja`（新檔）

```jinja
你是資深精神科醫師。以下是對同一患者的 F32（抑鬱）和 F41.1（GAD）的 criterion-level 評估結果。請根據證據強度判斷主要診斷。

## F32 標準評估結果
{% for c in f32_criteria %}
- {{ c.criterion_id }}: {{ c.status }} (conf={{ c.confidence }})
  evidence: {{ c.evidence | default("無") }}
{% endfor %}
met_ratio: {{ f32_met_ratio }}

## F41.1 標準評估結果
{% for c in f41_criteria %}
- {{ c.criterion_id }}: {{ c.status }} (conf={{ c.confidence }})
  evidence: {{ c.evidence | default("無") }}
{% endfor %}
met_ratio: {{ f41_met_ratio }}

## 臨床對話摘要
{{ transcript_summary }}

## 鑑別原則
1. 若 F41.1 的 B1 (motor tension) 或 B2 (autonomic arousal) 有 ≥1 個 met，且 transcript 包含「心慌/胸悶/出汗/手抖/呼吸急促/坐立不安」這類自主神經或運動緊張症狀 → 傾向 F41
2. 若 F32 的 B1+B2+B3 核心症狀都 met 且患者主訴是「心情低落/沒興趣/疲憊」 → 傾向 F32
3. 若兩者都符合且 patient 同時表現明顯抑鬱 + 明顯焦慮 → 輸出 comorbid

## 輸出要求
嚴格 JSON：
{
  "verdict": "F32" | "F41" | "comorbid",
  "reasoning": "100字內說明關鍵鑑別依據",
  "confidence": 0.0-1.0
}
```

### 檔案 2：`src/culturedx/agents/contrastive_disambiguator.py`（新檔）

```python
"""F32 vs F41 contrastive disambiguation agent."""
from dataclasses import dataclass

@dataclass
class ContrastiveVerdict:
    verdict: str  # "F32", "F41", "comorbid"
    reasoning: str
    confidence: float

class F32F41ContrastiveDisambiguator:
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def disambiguate(
        self,
        f32_checker_output,
        f41_checker_output,
        transcript_summary,
    ) -> ContrastiveVerdict:
        """Run contrastive comparison for F32 vs F41."""
        prompt = self._render_prompt(f32_checker_output, f41_checker_output, transcript_summary)
        response = self.llm.generate(prompt, response_format="json")
        # parse and return
        ...
```

### 檔案 3：在 HiED pipeline 加入觸發條件

```python
# AFTER checker + logic engine, BEFORE final ranking
if "F32" in confirmed_codes and ("F41" in confirmed_codes or "F41.1" in confirmed_codes):
    # Both confirmed — contrastive is needed
    verdict = contrastive.disambiguate(...)
    if verdict.verdict == "F32":
        # re-rank: F32 first, remove F41
    elif verdict.verdict == "F41":
        # re-rank: F41 first, remove F32
    # comorbid: keep both

elif "F32" in confirmed_codes and f41_met_ratio > 0.6:
    # F32 confirmed but F41 came close — contrastive might flip
    verdict = contrastive.disambiguate(...)
    # Apply
```

### Config

```yaml
# configs/overlays/t2_contrastive.yaml
mode:
  contrastive_disambiguation:
    enabled: true
    trigger_condition: "f32_f41_both_confirmed_or_close"
    f41_close_threshold: 0.6
    checker_prompt_variant: v2_improved
```

## 成功判準

- F41 recall ≥ 0.58（baseline 0.511, +7pp）
- F32 precision ≥ 0.58（baseline 0.523, +6pp）
- F32/F41 combined F1 ≥ 0.62（兩個類的平均）
- Top-1 ≥ 0.55（因為 F32/F41 合計佔 72.3%，若兩類都改善，Top-1 會同步升）
- 額外 LLM call cost: 每個符合觸發條件的 case +1 次呼叫（估約 50% cases 會觸發）

## 輸出路徑

`results/validation/t2_contrast/`
