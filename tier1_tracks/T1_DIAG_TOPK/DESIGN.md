# T1 — Diagnostician Top-K Expansion + Logic Engine All-Outputs

## 攻擊的錯誤

DIAGNOSTICIAN_MISS = 324 (29.7%)，per-class：

| Class | Gold N | DIAG_MISS | Recall |
|---|---|---|---|
| F41 | 394 | 130 | 47.2% |
| F39 | 63 | 25 | 3.2% |
| F98 | 47 | 47 | 0% |
| F51 | 43 | 33 | 14% |
| F42 | 36 | 22 | 36.1% |
| F45 | 16 | 14 | 6.3% |
| F43 | 15 | 15 | 0% |
| F31 | 9 | 8 | 11% |
| Z71 | 8 | 8 | 0% |
| F20 | 5 | 1 | 80% |
| F32 | 370 | 21 | 85.9% |

**目標**：把大部分 long-tail 的 0% recall 拉到 30-50%，同時讓 F41 從 47% 拉到 65%+。

## 核心診斷

經過對 `src/culturedx/modes/hied.py` 和 `prompts/agents/diagnostician_v2_zh.jinja` 的 code 審查，找出兩個 bug-like 問題：

### Bug 1：Diagnostician prompt 強制輸出 top-2

**證據**：`python3 -c "..."` 檢查 predictions.jsonl，998/1000 case 的 ranked_codes 長度為 2。

**根源**：prompt 末尾的 JSON schema：

```
{
  "ranked_diagnoses": [
    {"code": "ICD代码", "reasoning": "简要理由"},
    {"code": "ICD代码", "reasoning": "简要理由"}
  ]
}
```

只給了 2 個 items 作為範例，LLM 忠實地 mimic。

### Bug 2：Logic engine 只看 top-3 checker outputs

**證據**：`src/culturedx/modes/hied.py:1068`

```python
verify_codes = ranked_codes[:3]
# ...跑 top-3 checker...
remaining_codes = [code for code in candidate_codes if code not in verify_codes]
# ...跑 remaining checker...
all_checker_outputs = checker_outputs + remaining_outputs
# ...
logic_output = self.logic_engine.evaluate(checker_outputs)  # ← 只用 top-3!
```

`remaining_outputs` 雖然算了，但 `logic_engine.evaluate` 只餵給 `checker_outputs`（top-3）。
意思是：就算 F98 checker 在 remaining 中通過了，logic engine 根本看不到它，F98 永遠不會進 `confirmed_codes`。

### Bug 3：Primary selection 從 top-3 硬選

**證據**：同 file line 1078-1108：

```python
if top1_code in confirmed_set:
    primary = top1_code
elif top2_code and top2_code in confirmed_set:
    primary = top2_code
elif top3_code and top3_code in confirmed_set:
    primary = top3_code
else:
    primary = top1_code  # fallback
```

即使把 logic engine 改成看 all，primary 仍然只從 diagnostician 的 top-3 選。
必須擴大到所有 confirmed_codes，用 met_ratio 或 diagnostician rank 排序。

## Minimal diff 清單

### Diff 1: `prompts/agents/diagnostician_v2_zh.jinja`

修改兩處：
1. **在第 6 步和第 7 步之間插入「第 7 步：長尾障礙 screening」**，明確提示要考慮低頻 class
2. **修改底部的 JSON schema**，從 2 個 items 改成 5 個 items，並加上輸出要求 "必須輸出 5 個候選，按可能性降冪排列"

### Diff 2: `src/culturedx/modes/hied.py`

三個修改：

**修改 A (line ~998)**：
```python
# 原本
verify_codes = ranked_codes[:3]
# 改為
verify_codes = ranked_codes[:5]  # T1: expand from top-3 to top-5
```

**修改 B (line ~1072)**：
```python
# 原本
logic_output = self.logic_engine.evaluate(checker_outputs)
# 改為
logic_output = self.logic_engine.evaluate(all_checker_outputs)  # T1: consider all candidates
```

**修改 C (line ~1078-1108, primary selection)**：
```python
# 原本：top1/top2/top3 硬選
# 改為：掃描所有 ranked_codes（現在 top-5），第一個 confirmed 即為 primary
# 如果 ranked 裡沒有 confirmed，再掃描 all_confirmed（根據 met_ratio 排序）

confirmed_set = set(logic_output.confirmed_codes)
primary = None
confidence = 0.8
veto_applied = False

# Pass 1: Prefer diagnostician ordering (ranked_codes)
for rc in ranked_codes[:5]:
    if rc in confirmed_set:
        primary = rc
        confidence = 0.9 if rc == ranked_codes[0] else 0.75
        if rc != ranked_codes[0]:
            veto_applied = True
        break

# Pass 2: Fall back to any confirmed code, sorted by met_ratio desc
if primary is None and confirmed_set:
    met_ratios = {
        co.disorder: (co.criteria_met_count / max(co.criteria_required, 1))
        for co in all_checker_outputs
    }
    confirmed_by_ratio = sorted(
        confirmed_set,
        key=lambda c: met_ratios.get(c, 0.0),
        reverse=True,
    )
    primary = confirmed_by_ratio[0]
    confidence = 0.65
    veto_applied = True

# Pass 3: Final fallback - top-1 ranked
if primary is None:
    primary = ranked_codes[0]
    confidence = 0.6

# Build comorbid list from other confirmed (prefer ranked order, max 1)
comorbid = []
for rc in ranked_codes[:5]:
    if rc != primary and rc in confirmed_set:
        comorbid.append(rc)
        break  # max 1 comorbid per paper protocol
```

## 執行成本估計

- 改 prompt + code: 人工 30-45 min
- vLLM cache invalidation: diagnostician prompt 變了，這些 cache miss
- N=1000 重跑 DtV + 新 prompt: 
  - Diagnostician: +50% output token (~15 min 額外)
  - Checker top-5 vs top-3: 5/3 = 1.67x 時間，但 remaining 少了（cache hits），淨 +20% 時間
  - 總估計：原本若 3 小時，現在 3.5-4 小時

## 驗證指標

`validate.sh` 會跑：
1. N=50 pilot 確認 pipeline 跑得起來、ranked_codes 長度現在是 5
2. N=1000 full run
3. 自動重跑 `scripts/error_taxonomy_v24.py` 比較 DIAGNOSTICIAN_MISS 變化

**成功標準**：
- DIAGNOSTICIAN_MISS 從 324 → < 150
- IN_TOP3_NOT_TOP1 可能小幅增加（原 miss 變成 in-top3），這是預期的
- 12c_Top1 從 0.531 → > 0.55
- 12c_F1_macro 從 0.202 → > 0.24
- F98, F43, Z71 的 recall 從 0% → > 10%

## 風險

1. **False positive for long-tail**：diagnostician 如果把 F98 放進 top-5 且 checker 誤判為通過 → primary 被亂選
   - 但 v2.4 checker 精度夠（從 error taxonomy 看 CHECKER_LOW_MET = 0）
2. **F32 primary 被搶走**：某些原本 F32 正確的 case，現在 F41 被 confirm 後 met_ratio 更高，搶走 primary
   - 如果這發生，T3 contrastive 可以修
3. **Token 超限**：5 個 diagnoses 的 reasoning × 5 > max_tokens（目前 1536）
   - Mitigation: 要求 reasoning 限制 30 字以內

## 如果跑完不夠 SOTA

Phase A 的 error taxonomy 重跑會告訴我們下一步。可能的 follow-up：
- 如果 DIAGNOSTICIAN_MISS 還 > 20%：prompt 要更激進（放 criterion 範例）
- 如果 IN_TOP3_NOT_TOP1 > 15%：需要 T3 contrastive
- 如果 F1_w 還 < SOTA：考慮 TF-IDF stacking（原 playbook T3-TFIDF-STACK，現在降級為 safety net）
