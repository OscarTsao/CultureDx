# T1-F43TRIG：F43 應激事件觸發器

## 問題

Paper Table 2 顯示 F43（Stress-related）佔資料集 12.1%，應該有約 121 cases（N=1000 validation 裡）。但你實際看到 gold=11（1.1%），這代表 **LingxiDiag-16K validation split 的 F43 只有 11 個**（論文的 12.1% 是整個 16000 cases 的比例，validation 抽樣後分佈有差異）。

不過即使是 11 個，你現在預測 **0 個 F43**，全部 11 cases 都是純 FP+FN。這一個 class F1=0 會讓 F1_macro 降低 1/12 = 0.083，是個關鍵瓶頸。

觀察：F43 的核心鑑別是「明確的應激源」。LLM 之所以看不到 F43，是因為 diagnostician ranked list 中 F43 常被 F32/F41 擠到 4-5 名，然後 DtV 的 top-2 verification 就不包含 F43。

## 假設

加一個**輕量級 pre-screening agent**：
1. 先讀 transcript
2. 檢查是否包含明確應激事件關鍵詞（分手、離婚、親人過世、失業、搬家、創傷、事故）
3. 若是，強制把 F43.2（適應障礙）或 F43.1（PTSD）加到 diagnostician candidate list 的 top-3

這不需要 full LLM call，可以用簡單的正則/關鍵詞匹配即可，或用 checker 模型做 binary classification。

預期：
- F43 recall 從 0/11 → 5-7/11
- F43 F1 0.000 → 0.5+
- F1_macro: +2-3pp

## 技術改動

### 檔案 1：`src/culturedx/agents/stress_detector.py`（新檔）

```python
"""Lightweight stress event detector for F43 routing.

Uses keyword matching + optional LLM verification.
"""
from __future__ import annotations
import re
from dataclasses import dataclass

ACUTE_STRESS_KEYWORDS = [
    "分手", "離婚", "離異", "去世", "过世", "死了", "自殺", 
    "車禍", "事故", "性侵", "強暴", "強姦", "被打", "被欺負", 
    "失業", "被裁", "被開除", "破產",
]
CHRONIC_STRESS_KEYWORDS = [
    "搬家", "換工作", "轉學", "出國", "生孩子", "懷孕", "生病", "住院",
    "手術", "考試", "升學", "分居", "婚姻問題",
]
TRAUMA_KEYWORDS = [
    "創傷", "创伤", "PTSD", "戰爭", "自然災害", "地震", "被虐",
    "兒時陰影", "童年陰影", "家暴",
]

TEMPORAL_MARKERS_RECENT = [
    "上個月", "上周", "這個月", "最近", "前几天", "昨天", "今天",
    "一個月前", "兩個月前", "三個月內",
]

@dataclass
class StressSignal:
    has_acute_stressor: bool
    has_chronic_stressor: bool
    has_trauma: bool
    has_recent_marker: bool
    matched_keywords: list[str]
    suggested_code: str  # F43.1 / F43.2 / F43.9 / None

class StressEventDetector:
    """Keyword-based fast detector for F43 routing."""
    
    def detect(self, transcript: str) -> StressSignal:
        matched = []
        has_acute = any(k in transcript for k in ACUTE_STRESS_KEYWORDS)
        has_chronic = any(k in transcript for k in CHRONIC_STRESS_KEYWORDS)
        has_trauma = any(k in transcript for k in TRAUMA_KEYWORDS)
        has_recent = any(k in transcript for k in TEMPORAL_MARKERS_RECENT)
        
        for kw_list in [ACUTE_STRESS_KEYWORDS, CHRONIC_STRESS_KEYWORDS, TRAUMA_KEYWORDS]:
            for k in kw_list:
                if k in transcript:
                    matched.append(k)
        
        # Routing logic
        suggested = None
        if has_trauma:
            suggested = "F43.1"  # PTSD
        elif (has_acute or has_chronic) and has_recent:
            suggested = "F43.2"  # Adjustment disorder
        elif has_acute or has_chronic:
            suggested = "F43.9"  # NOS
        
        return StressSignal(
            has_acute_stressor=has_acute,
            has_chronic_stressor=has_chronic,
            has_trauma=has_trauma,
            has_recent_marker=has_recent,
            matched_keywords=matched,
            suggested_code=suggested,
        )
```

### 檔案 2：`src/culturedx/modes/hied.py`（或等價的主 pipeline 檔）

在 diagnostician 執行前加入 stress pre-routing：

```python
# BEFORE diagnostician call
stress_signal = stress_detector.detect(transcript_text)
if stress_signal.suggested_code and stress_signal.suggested_code in candidate_disorders:
    # Force stress code into top-3 by prepending hint to diagnostician prompt
    extra_context = f"\n\n⚠ 自動偵測：對話包含應激事件關鍵詞（{', '.join(stress_signal.matched_keywords[:3])}）。請將 {stress_signal.suggested_code} 放入前 3 名候選，並在排序理由中說明應激事件的角色。"
    # pass extra_context to diagnostician
```

或者更簡單：直接把 `stress_signal.suggested_code` **強制設為 DtV verification 的其中一個 top-2 checker target**。

### 檔案 3：`configs/overlays/t1_f43_trigger.yaml`

```yaml
mode:
  stress_detection:
    enabled: true
    force_top_verify: true  # 強制加入 DtV top-2
    fallback_to_keyword: true
  checker_prompt_variant: v2_improved
```

## 輸出路徑

`results/validation/t1_f43trig/`

## 成功判準

- F43 預測次數 ≥ 8（gold=11, 目標抓回至少 8 個）
- F43 F1 ≥ 0.4
- F1_macro ≥ 0.22（+2pp from baseline）

## 擴展

若 keyword detector 效果不佳，可以升級為**輕量 LLM binary classifier**：
- 給 Qwen3-8B 一段 transcript，問 "Does this patient describe a clear stressful life event in the past 3 months?"
- 只要 yes/no 輸出，成本低
- 若 yes → force F43.x into top-3

但先試 keyword，如果 F43 recall 已達標就不用加 LLM。
