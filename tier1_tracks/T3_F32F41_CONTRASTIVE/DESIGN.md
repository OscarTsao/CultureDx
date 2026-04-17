# T3 — F32↔F41 Contrastive Re-ranking

## 攻擊的錯誤

IN_TOP3_NOT_TOP1 = 151 (13.8%)，其中 **F32↔F41 confusion 佔大宗**：

| Gold class | IN_TOP3_NOT_TOP1 count | 含意 |
|---|---|---|
| F41 | 78 | gold 是 F41，system 把它排 top-2/top-3（primary 是別的通常是 F32） |
| F32 | 31 | gold 是 F32，primary 是 F41 |
| F39 | 36 | gold 是 F39 (mood NOS)，primary 通常是 F32 |
| F51 | 4 | gold 是 F51，primary 是 F32 或 F41 |

**T3 targets 78 + 31 = 109 個 F32↔F41 排名錯誤的 case**（F39 屬不同性質，不納入）。

## 核心診斷

因為 F32 (depression) 和 F41 (GAD/anxiety) 的 ICD-10 criteria **共享大量症狀**：
- 失眠 (F32 C5 / F41 B5)
- 注意力不集中 (F32 C6 / F41 B4)
- 疲勞 (F32 C3 / F41 B6)
- 易怒 (F32 C4 / F41 B3)

當 checker 給 F32 和 F41 都 met_ratio ≥ 1.0（符合門檻）時，logic engine 會把兩個都 confirm。
但目前的 primary selection 只看 diagnostician 的 ranked_codes 順序。

Diagnostician 的 prompt 有反錨定提醒：
> 不要因為抑郁常见就默认排第一。如果患者有自主神经症状（心慌/胸闷/出汗），F41应优先于F32。

但實際上 F41 的 78 個 IN_TOP3 case 顯示，diagnostician **仍傾向 F32 priority**，尤其當 F41 的自主神經症狀不典型時。

## T3 做法：專用 contrastive LLM call

觸發條件：**primary 是 F32 (或 F41) 且 comorbid 包含 F41 (或 F32)**，或兩者都在 top-5 ranked_codes 且都 confirmed。

執行：額外 call 一次 LLM，問它「這個 case 是 F32 為主還是 F41 為主」。

不用既有的 `ContrastiveCheckerAgent`（那個需要 shared_pairs data structure，複雜）。寫一個簡化版的專用 prompt。

## 新增檔案

### `prompts/agents/f32_f41_contrastive_zh.jinja`

```jinja
你是精神科鉴别诊断专家。以下 case 同时符合 F32（抑郁障碍）和 F41（焦虑障碍）的诊断标准。
请根据临床证据，判断哪个是**主诊断**（primary）、哪个是共病（comorbid 或不存在）。

## 临床对话

{{ transcript_text }}

## F32（抑郁）checker 结果

符合 criteria: {{ f32_met }} / {{ f32_total }}
主要症状证据（前 3 条）：
{% for ev in f32_evidence %}- {{ ev }}
{% endfor %}

## F41（焦虑）checker 结果

符合 criteria: {{ f41_met }} / {{ f41_total }}
主要症状证据（前 3 条）：
{% for ev in f41_evidence %}- {{ ev }}
{% endfor %}

## 鉴别要点

- **F32 核心**：持续 ≥2 周的情绪低落 + 兴趣丧失 + 精力减退（至少 2 项持续存在）
- **F41 核心**：过度担忧多个领域 ≥6 月 + **自主神经症状**（心慌、胸闷、出汗、口干、头晕）
- **关键鉴别**：
  - 主诉是心情不好、兴趣下降 → 更可能 F32 primary
  - 主诉是担忧、紧张、心慌、胸闷 → 更可能 F41 primary
  - 如两者都明显但焦虑是近期反应性的 → F32 primary, F41 comorbid
  - 如抑郁是焦虑长期后继发的 → F41 primary, F32 comorbid

## 输出

请严格按以下 JSON 格式输出，不要其他文字：

```json
{
  "primary": "F32" 或 "F41",
  "comorbid_present": true 或 false,
  "reasoning": "30 字以内说明"
}
```

若两者都明显但无法分辨哪个主哪个次（真正共病且权重相当），选 primary 为症状证据数更多的那个。
```

### `src/culturedx/modes/hied.py` 新增 method

加在 `_run_contrastive` 相關區域（line ~559 附近）或單獨位置。

```python
def _run_f32_f41_contrastive(
    self,
    transcript_text: str,
    f32_output,  # CheckerOutput
    f41_output,  # CheckerOutput
    lang: str,
) -> tuple[str, bool]:
    """Run F32 vs F41 contrastive. Returns (primary_code, comorbid_present).
    
    Returns ("F32", True) means: primary = F32, F41 also present as comorbid.
    Falls back to the higher-met_ratio disorder if LLM fails.
    """
    import json
    from jinja2 import Environment, FileSystemLoader
    from culturedx.llm.json_utils import extract_json_from_response

    f32_ratio = f32_output.criteria_met_count / max(f32_output.criteria_required, 1)
    f41_ratio = f41_output.criteria_met_count / max(f41_output.criteria_required, 1)
    default = ("F32", True) if f32_ratio >= f41_ratio else ("F41", True)

    try:
        env = Environment(loader=FileSystemLoader(str(self.prompts_dir)))
        template = env.get_template(f"f32_f41_contrastive_{lang}.jinja")
        
        def top_evidence(co, n=3):
            evs = []
            for cr in co.criteria[:n]:
                if cr.status == "met" and cr.evidence:
                    evs.append(f"{cr.criterion_id}: {cr.evidence[:80]}")
            return evs

        prompt = template.render(
            transcript_text=transcript_text[:4000],
            f32_met=f32_output.criteria_met_count,
            f32_total=f32_output.criteria_required,
            f32_evidence=top_evidence(f32_output),
            f41_met=f41_output.criteria_met_count,
            f41_total=f41_output.criteria_required,
            f41_evidence=top_evidence(f41_output),
        )
        
        source, _, _ = env.loader.get_source(env, f"f32_f41_contrastive_{lang}.jinja")
        prompt_hash = self.llm.compute_prompt_hash(source)
        
        raw = self.llm.generate(prompt, prompt_hash=prompt_hash, language=lang)
        parsed = extract_json_from_response(raw)
        
        if not parsed or not isinstance(parsed, dict):
            return default
        
        primary = parsed.get("primary", "").strip().upper()
        comorbid_present = bool(parsed.get("comorbid_present", True))
        
        if primary not in ("F32", "F41"):
            return default
        return (primary, comorbid_present)
    except Exception as e:
        logger.warning(f"F32/F41 contrastive failed, falling back: {e}")
        return default
```

### Integration point in `_run_dtv_pipeline`（hied.py）

在 T1 修改後的 primary selection **之後**（約 line ~1120）加：

```python
# T3: F32↔F41 contrastive disambiguation
# Trigger when both F32 and F41 are in confirmed set (or in top-5 ranked with high met_ratio)
f32_in_confirmed = "F32" in confirmed_set
f41_in_confirmed = any(c.startswith("F41") for c in confirmed_set)

if f32_in_confirmed and f41_in_confirmed and self.f32_f41_contrastive_enabled:
    f32_co = next((co for co in all_checker_outputs if co.disorder == "F32"), None)
    f41_co = next((co for co in all_checker_outputs 
                   if co.disorder.startswith("F41")), None)
    
    if f32_co and f41_co:
        contrastive_start = time.monotonic()
        cont_primary, cont_comorbid = self._run_f32_f41_contrastive(
            transcript_text, f32_co, f41_co, lang,
        )
        stage_timings["f32_f41_contrastive"] = time.monotonic() - contrastive_start
        
        # Apply override
        original_primary = primary
        if cont_primary == "F32" and primary.startswith("F41"):
            primary = "F32"
            comorbid = [f41_co.disorder] if cont_comorbid else []
            logger.info(f"Case {case.case_id}: F32/F41 contrastive overrode F41→F32")
        elif cont_primary == "F41" and primary == "F32":
            primary = f41_co.disorder  # Could be F41.0, F41.1, F41.2
            comorbid = ["F32"] if cont_comorbid else []
            logger.info(f"Case {case.case_id}: F32/F41 contrastive overrode F32→{primary}")
        
        decision_trace["f32_f41_contrastive"] = {
            "original_primary": original_primary,
            "contrastive_primary": cont_primary,
            "applied": cont_primary != original_primary[:3],
        }
```

### 新增 flag in `HiedMode.__init__`

```python
self.f32_f41_contrastive_enabled = config.get("f32_f41_contrastive", True)
```

或在 `configs/v2.4_final.yaml` 加：
```yaml
mode:
  ...
  f32_f41_contrastive: true
```

## 成本估計

- 觸發比例：看現在 factorial_b 有多少 case confirmed 包含 F32 和 F41
- 快速估算：從 error taxonomy, F41 有 394 gold, F32 有 370 gold, 多數共現。估計 200-300 case 會 trigger contrastive
- 每次 contrastive = 1 個 LLM call ≈ 0.5-1 秒
- 總時間：+5-10 min

## 預期效益

基於 F41 的 78 個 IN_TOP3 和 F32 的 31 個：
- LLM contrastive precision 預計 70-80%（task 難度中等）
- 救回 F41: 78 × 0.7 = 55 cases → Top-1 +5.5pp
- F32 可能有少數被 flip（誤判為 F41）：32 × 0.2 = ~6 cases loss
- 淨 Top-1: +5 pp

預期：
- Top-1: T1 的 0.56 → 0.60
- F1_m: T1 的 0.25 → 0.27（F41 recall 提升幫助很大）
- F1_w: T1 的 0.48 → 0.51

## 風險

1. **LLM contrastive 誤判**: 可能把真正的 F32 primary case 翻成 F41
   - Mitigation: `reasoning` 記下來，離線分析 flip 的正確率
   - 若 < 65% accuracy，關掉 T3

2. **Contrastive 不觸發（F32/F41 沒同時 confirmed）**: 
   - 在 T1 之後，logic 看 all_checker_outputs，觸發率應該高
   - 若 < 100 case trigger，效益會有限

3. **F41 subcode 的處理**: F41.0/F41.1/F41.2 要對應正確的 code
   - 使用 `f41_co.disorder` 而不是硬寫 "F41"
