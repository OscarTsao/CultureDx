"""StressEventDetector — rule-based stress event detection for Chinese transcripts.

Scans transcripts for stress-related keywords and determines whether F43.x
(Reaction to severe stress / adjustment disorders) should be force-injected
into the DtV verification candidate set.

Part of T1-F43TRIG.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class StressSignal:
    """Result of stress event detection on a transcript."""

    detected: bool
    event_type: str  # "trauma", "loss", "breakup", "work_stress", "other", "none"
    suggested_code: str  # "F43.1", "F43.2", "F43.9", or ""
    keywords_found: list[str] = field(default_factory=list)
    confidence: float = 0.0


class StressEventDetector:
    """Rule-based detector for stress events in Chinese clinical transcripts.

    Scans for keyword categories, determines the most appropriate F43.x subcode,
    and returns a StressSignal indicating whether F43 should be force-added to
    the DtV verification set.
    """

    # --- Keyword banks (simplified + traditional Chinese variants) ---

    TRAUMA_KEYWORDS: list[str] = [
        # Accidents / disasters
        "车祸", "車禍", "地震", "火灾", "火災", "洪水", "海啸", "海嘯",
        "爆炸", "意外事故", "交通事故",
        # Violence / abuse
        "性侵", "强奸", "強姦", "暴力", "虐待", "家暴", "殴打", "毆打",
        "施暴", "性骚扰", "性騷擾", "性暴力", "猥亵", "猥褻",
        # War / conflict
        "战争", "戰爭", "战乱", "戰亂", "恐怖袭击", "恐怖襲擊",
        # Severe threat
        "绑架", "綁架", "抢劫", "搶劫", "威胁生命", "威脅生命",
        "差点死", "差點死", "濒死", "瀕死", "重伤", "重傷",
        # PTSD-related re-experiencing
        "噩梦", "噩夢", "闪回", "閃回", "创伤后", "創傷後",
    ]

    LOSS_KEYWORDS: list[str] = [
        "过世", "過世", "去世", "死亡", "丧亲", "喪親", "丧失", "喪失",
        "死掉", "走了", "不在了", "离世", "離世", "亡故",
        "丧偶", "喪偶", "丧子", "喪子", "丧父", "喪父", "丧母", "喪母",
        "病逝", "猝死", "自杀身亡", "自殺身亡",
    ]

    BREAKUP_KEYWORDS: list[str] = [
        "分手", "离婚", "離婚", "出轨", "出軌", "外遇",
        "被抛弃", "被拋棄", "被甩", "感情破裂", "婚变", "婚變",
        "背叛", "劈腿",
    ]

    WORK_STRESS_KEYWORDS: list[str] = [
        "失业", "失業", "裁员", "裁員", "被开除", "被開除",
        "辞职", "辭職", "降薪", "破产", "破產", "倒闭", "倒閉",
        "失去工作", "下岗", "下崗", "被解雇", "被解僱",
        "欠债", "欠債", "债务", "債務", "经济困难", "經濟困難",
    ]

    RECENT_MARKERS: list[str] = [
        "最近", "上个月", "上個月", "前几天", "前幾天", "去年",
        "几个月前", "幾個月前", "上周", "上週", "这几天", "這幾天",
        "刚刚", "剛剛", "不久前", "前阵子", "前陣子",
        "这段时间", "這段時間", "近来", "近來", "这一年", "這一年",
        "半年前", "三个月前", "三個月前", "两个月前", "兩個月前",
    ]

    # Priority order: trauma > loss > breakup > work_stress
    _CATEGORY_MAP: list[tuple[str, str, str]] = [
        ("trauma", "TRAUMA_KEYWORDS", "F43.1"),
        ("loss", "LOSS_KEYWORDS", "F43.2"),
        ("breakup", "BREAKUP_KEYWORDS", "F43.2"),
        ("work_stress", "WORK_STRESS_KEYWORDS", "F43.2"),
    ]

    def __init__(self) -> None:
        # Pre-compile a single regex per category for performance
        self._patterns: dict[str, re.Pattern] = {}
        for event_type, attr_name, _ in self._CATEGORY_MAP:
            keywords = getattr(self, attr_name)
            if keywords:
                escaped = [re.escape(kw) for kw in keywords]
                self._patterns[event_type] = re.compile("|".join(escaped))
        # Recent-marker pattern
        escaped_recent = [re.escape(m) for m in self.RECENT_MARKERS]
        self._recent_pattern = re.compile("|".join(escaped_recent))

    def detect(self, transcript: str) -> StressSignal:
        """Scan *transcript* for stress-event keywords.

        Returns a ``StressSignal`` with the highest-priority match.

        Decision rules:
        - Trauma keywords → F43.1 (PTSD / acute stress reaction)
        - Loss / breakup / work stress keywords → F43.2 (adjustment disorder)
        - If keywords found but no recent-time marker → F43.9 (unspecified)
        - If nothing found → not detected
        """
        if not transcript:
            return StressSignal(
                detected=False,
                event_type="none",
                suggested_code="",
            )

        # Scan each category in priority order
        best_event_type: str = "none"
        best_code: str = ""
        all_keywords: list[str] = []

        for event_type, _, default_code in self._CATEGORY_MAP:
            pattern = self._patterns.get(event_type)
            if pattern is None:
                continue
            matches = pattern.findall(transcript)
            if matches:
                all_keywords.extend(matches)
                if best_event_type == "none":
                    best_event_type = event_type
                    best_code = default_code

        if not all_keywords:
            return StressSignal(
                detected=False,
                event_type="none",
                suggested_code="",
            )

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_keywords: list[str] = []
        for kw in all_keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        # Check for recent time markers — absence downgrades to F43.9
        has_recent = bool(self._recent_pattern.search(transcript))
        if not has_recent and best_code != "F43.1":
            best_code = "F43.9"

        # Confidence heuristic: more keywords and recent markers → higher
        base_conf = min(0.5 + 0.1 * len(unique_keywords), 0.9)
        if has_recent:
            base_conf = min(base_conf + 0.1, 0.95)

        return StressSignal(
            detected=True,
            event_type=best_event_type,
            suggested_code=best_code,
            keywords_found=unique_keywords,
            confidence=round(base_conf, 2),
        )
