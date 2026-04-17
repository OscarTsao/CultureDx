# T12-TOT-HARD-CASES：Tree-of-Thoughts for Low-Confidence Cases

## 動機

你的 factorial_b 對 simple cases（F32/F41 明顯的）通常已經正確（accuracy ~80%）。剩下的 error case 集中在：
- F32↔F41 borderline（shared criteria 都 met）
- F39/F45/F51/F98/Z71 low-freq class
- Multi-comorbid cases

這些困難 cases，typically LLM 的 confidence 也比較低。**Tree-of-Thoughts (ToT, Yao et al., NeurIPS 2023) 或 step-back prompting (Zheng et al., ICLR 2024)** 專門解決這種需要多步推理的困難 cases。

## 核心 Idea

對 factorial_b 輸出的**低信心 cases**（top-1 calibrator score < 0.7）觸發更深層推理：

1. **Identify hard cases** (只 ~20-30% 案例觸發，節省計算)
2. **Tree-of-Thoughts branching**:
   - Branch 1: "Assume F32 is primary, what evidence supports/contradicts?"
   - Branch 2: "Assume F41 is primary, what evidence supports/contradicts?"
   - Branch 3: "Assume they are comorbid, what evidence supports/contradicts?"
3. **Voting / evaluator agent** picks the best branch

## 假設

對 hard cases 應用 ToT：
- Hard cases accuracy 提升 +5-10pp（目前 ~40% → ~50%）
- Easy cases 保持 unchanged
- Overall Top-1 +1.5-2pp（因為 hard cases 只 20-30% 但這部分提升很大）
- **論文 ablation 意義更大**：證明 culture-adaptive reasoning 在 hard cases 上 essential

## 技術設計

### Step 1：Hard Case Detection

```python
def is_hard_case(prediction):
    """Identify cases likely to be wrong, deserving more compute."""
    # Signal 1: Calibrator top-1 score < threshold
    if prediction["calibrator_scores"][prediction["primary"]] < 0.7:
        return True
    # Signal 2: Top-1 and Top-2 very close
    if len(prediction["ranked"]) >= 2:
        gap = prediction["calibrator_scores"][prediction["ranked"][0]] - \
              prediction["calibrator_scores"][prediction["ranked"][1]]
        if gap < 0.1:
            return True
    # Signal 3: Multiple disorders confirmed
    if len(prediction["confirmed_disorders"]) >= 3:
        return True
    return False
```

### Step 2：ToT Branching Prompt

```jinja
{# prompts/agents/tot_branching_zh.jinja #}
你是資深精神科主任醫師。以下是對一個複雜案例的初步評估，system 不確定最佳診斷。

## 案例
{{ transcript }}

## 初步候選
Top-1: {{ candidate_1 }} (calibrator score: {{ score_1 }})
Top-2: {{ candidate_2 }} (calibrator score: {{ score_2 }})
Top-3: {{ candidate_3 }} (calibrator score: {{ score_3 }})

## Criterion-Level 證據
{% for d, crits in criterion_evidence.items() %}
{{ d }}:
{% for c in crits %}
- {{ c.id }}: {{ c.status }} ({{ c.evidence[:80] }})
{% endfor %}
{% endfor %}

## 深度推理任務

請對以下 3 個診斷假設**各自**進行深度分析：

### Branch A：假設 primary diagnosis 是 {{ candidate_1 }}
列舉支持 {{ candidate_1 }} 的 3 個最強證據，及反駁它的 2 個弱點。
給這個假設的合理性打分（0-10）。

### Branch B：假設 primary diagnosis 是 {{ candidate_2 }}
列舉支持 {{ candidate_2 }} 的 3 個最強證據，及反駁它的 2 個弱點。
給這個假設的合理性打分（0-10）。

### Branch C：假設為共病（{{ candidate_1 }} + {{ candidate_2 }}）
列舉兩個障礙是否真的 independently co-occur 的證據。
給共病假設的合理性打分（0-10）。

## 最終結論

基於上述分析，最終建議：
- Primary: {{candidate_1 or 2}}
- Comorbid: [optional]
- Confidence: 0-1
- Key reasoning: 50字內

請嚴格 JSON 輸出。
```

### Step 3：Integration

```python
# In main pipeline, after factorial_b produces predictions:

for case in predictions:
    if is_hard_case(case):
        tot_result = run_tot_branching(case)
        case["final_primary"] = tot_result["primary"]
        case["final_comorbid"] = tot_result.get("comorbid")
        case["final_confidence"] = tot_result["confidence"]
        case["tot_applied"] = True
    else:
        case["final_primary"] = case["primary"]
        case["tot_applied"] = False
```

### Step 4：Self-consistency over ToT

如果 ToT 單次還不夠，疊加 T7 self-consistency：
- ToT 跑 n=3 次 temperature=0.5
- 取 branch score vote

## 成本估算

- 觸發比例 ~25% (假設 threshold 0.7)
- 每個 hard case 多一次 ToT call (~2048 tokens input, ~1024 output)
- N=1000 run 裡多 250 次 ToT call，大約 +30 分鐘 GPU time

## 成功判準

- Hard cases 上 Top-1 accuracy 從 ~40% → ~50%
- Easy cases Top-1 不變（sanity check）
- Overall Top-1 +1.5-2pp
- ToT reasoning 可以 qualitative 驗證（隨機挑 10 個看是否 reasoning 合理）

## 變體

若 ToT 太慢，改用 **Step-Back Prompting**（Zheng et al., 2024）：

```
Original question: "診斷此患者"

Step-back: "一般來說，區分 F32 和 F41.1 應注意哪幾個關鍵點？"
Answer: [LLM 列出 5 個 discriminating rules]

Final: "根據這些 discriminating rules + 案例證據，診斷是..."
```

Step-back 只 2 次 call，比 ToT 輕，效果略弱但還不錯。

## 論文敘事

ToT for hard cases 可以支持：
- **C8**: CultureDx 不只是 accuracy 好，而是在真正難的 cases 上能透過多步推理獲益，這類案例在真實臨床最有價值（clinician 最需要 decision support 的地方）
- Qualitative case study 可以挑 2-3 個 ToT-saved case 放論文

## 輸出

- `results/validation/t12_tot_hard_cases/`
- `analyses/tot_case_studies.md` (論文 case studies)
