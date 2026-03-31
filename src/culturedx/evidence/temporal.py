"""Temporal reasoning for Chinese clinical text.

Infers symptom duration from indirect evidence in Chinese clinical narratives,
where explicit temporal markers (e.g., "担忧超过六个月") are rare.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from culturedx.core.models import Turn

logger = logging.getLogger(__name__)

_CHINESE_TIME_NLP = None
_STANZA_NLP = None


def _get_chinese_time_nlp() -> Any | None:
    """Lazily initialize ChineseTimeNLP if it is available."""
    global _CHINESE_TIME_NLP

    if _CHINESE_TIME_NLP is None:
        try:
            from ChineseTimeNLP import TimeNormalizer

            _CHINESE_TIME_NLP = TimeNormalizer()
        except ImportError:
            _CHINESE_TIME_NLP = False
        except Exception:
            logger.debug("ChineseTimeNLP initialization failed.", exc_info=True)
            _CHINESE_TIME_NLP = False

    return _CHINESE_TIME_NLP if _CHINESE_TIME_NLP is not False else None


def _get_stanza_nlp() -> Any | None:
    """Lazily initialize the stanza zh tokenize+ner pipeline if available."""
    global _STANZA_NLP

    if _STANZA_NLP is None:
        try:
            import stanza

            _STANZA_NLP = stanza.Pipeline(
                "zh",
                processors="tokenize,ner",
                download_method=stanza.DownloadMethod.REUSE_RESOURCES,
                logging_level="ERROR",
            )
        except ImportError:
            _STANZA_NLP = False
        except Exception:
            logger.debug("stanza temporal pipeline initialization failed.", exc_info=True)
            _STANZA_NLP = False

    return _STANZA_NLP if _STANZA_NLP is not False else None


# ---------------------------------------------------------------------------
# Chinese number utilities
# ---------------------------------------------------------------------------

_ZH_DIGIT = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "百": 100, "千": 1000,
}


def _zh_num_to_int(text: str) -> int | None:
    """Convert a simple Chinese number string to int.

    Handles: 一, 二, 十二, 二十, 三百, etc.  Returns None on failure.
    """
    text = text.strip()
    if not text:
        return None

    # Try Arabic numeral first
    try:
        return int(text)
    except ValueError:
        pass

    # Handle single-character numbers
    if len(text) == 1 and text in _ZH_DIGIT:
        return _ZH_DIGIT[text]

    # Handle 十X (10-19)
    if text.startswith("十"):
        rest = text[1:]
        if not rest:
            return 10
        d = _ZH_DIGIT.get(rest)
        return 10 + d if d is not None else None

    # Handle X十Y (20-99)
    if "十" in text:
        parts = text.split("十", 1)
        tens = _ZH_DIGIT.get(parts[0])
        if tens is None:
            return None
        ones = _ZH_DIGIT.get(parts[1]) if parts[1] else 0
        if ones is None:
            return None
        return tens * 10 + ones

    # Handle 半 (half)
    if text == "半":
        return None  # caller should handle "半年" specially

    return None


# ---------------------------------------------------------------------------
# Pattern categories
# ---------------------------------------------------------------------------

@dataclass
class TemporalMatch:
    """A single temporal expression extracted from text."""

    category: str  # "explicit_duration", "relative_time", "onset_marker",
                   # "frequency", "course_indicator"
    text: str      # matched substring
    turn_id: int
    estimated_months: float | None = None  # inferred duration in months


@dataclass
class TemporalFeatures:
    """Aggregated temporal evidence for a clinical case."""

    matches: list[TemporalMatch] = field(default_factory=list)
    duration_confidence: float = 0.0  # 0.0 to 1.0
    estimated_months: float | None = None  # best estimate of symptom duration
    meets_6month_criterion: bool = False
    reasoning: str = ""

    def summary_zh(self) -> str:
        """Return a Chinese-language summary suitable for prompt injection."""
        if not self.matches:
            return "未发现时间线相关信息。"
        parts = []
        parts.append(f"时间证据置信度: {self.duration_confidence:.1f}")
        if self.estimated_months is not None:
            parts.append(f"估计持续时间: 约{self.estimated_months:.0f}个月")
        met_label = "是" if self.meets_6month_criterion else "否"
        parts.append(f"满足6个月标准: {met_label}")
        if self.reasoning:
            parts.append(f"推理依据: {self.reasoning}")
        cats: dict[str, list[str]] = {}
        for m in self.matches:
            cats.setdefault(m.category, []).append(m.text)
        for cat, texts in cats.items():
            label = {
                "explicit_duration": "明确时间表述",
                "relative_time": "相对时间参照",
                "onset_marker": "起病标志",
                "frequency": "频率/持续性表述",
                "course_indicator": "病程变化描述",
            }.get(cat, cat)
            joined = ", ".join(texts)
            parts.append(f"  {label}: {joined}")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Regex pattern definitions
# ---------------------------------------------------------------------------

# 1. Explicit duration: "X个月", "X年", "半年", "几个月"
_EXPLICIT_DURATION_PATTERNS = [
    # X个月 / X个多月
    (re.compile(r"([一二两三四五六七八九十百千\d]+)\s*个多?月"), "month"),
    # X年 / X年多
    (re.compile(r"([一二两三四五六七八九十百千\d]+)\s*年多?"), "year"),
    # 半年 / 大半年
    (re.compile(r"大?半年"), "half_year"),
    # 几个月 / 好几个月
    (re.compile(r"好?几个月"), "several_months"),
    # X周 / X个星期
    (re.compile(r"([一二两三四五六七八九十\d]+)\s*(?:周|个?星期)"), "week"),
    # X天
    (re.compile(r"([一二两三四五六七八九十百千\d]+)\s*天"), "day"),
    # 几年
    (re.compile(r"好?几年"), "several_years"),
    # 多年 / 好多年 / 很多年
    (re.compile(r"(?:好|很)?多年"), "many_years"),
    # 很久了 / 好久了
    (re.compile(r"(?:好|很)久(?:了)?"), "long_time"),
    # 好长时间 / 很长时间
    (re.compile(r"[好很]长时间"), "long_time"),
]

# 2. Relative time: "去年", "前年", "从...开始", "已经...了"
_RELATIVE_TIME_PATTERNS = [
    (re.compile(r"去年(?:年底|年初)"), "last_year"),
    (re.compile(r"去年"), "last_year"),
    (re.compile(r"前年"), "year_before_last"),
    (re.compile(r"大前年"), "three_years_ago"),
    (re.compile(r"上个月"), "last_month"),
    (re.compile(r"前几个月"), "few_months_ago"),
    (re.compile(r"从.{1,20}(?:开始|以来|起)"), "since_event"),
    (re.compile(r"已经(?:持续)?(?:很|好)?(?:久|长时间)(?:了)?"), "already_long_time"),
    (re.compile(r"已经.{1,15}了"), "already_duration"),
    (re.compile(r"(?:上|去)个?学期"), "last_semester"),
    (re.compile(r"这学期"), "this_semester"),
    (re.compile(r"(?:从|自从).{0,6}(?:年|月)"), "since_time"),
    (re.compile(r"过年前"), "before_new_year"),
    (re.compile(r"(?:去年|前年)(?:冬天|夏天|春天|秋天)"), "last_season"),
    (re.compile(r"(?:毕业|退休|离婚|失业|下岗|搬家|手术)(?:以?后|之后|以来)"), "life_event"),
]

# 3. Onset markers: "发病", "开始出现", "首次", "起初"
_ONSET_MARKER_PATTERNS = [
    (re.compile(r"发病"), "onset"),
    (re.compile(r"开始(?:出现|有|感觉)"), "first_appeared"),
    (re.compile(r"首次"), "first_time"),
    (re.compile(r"起初"), "initially"),
    (re.compile(r"(?:最)?初[的是]?时候"), "at_first"),
    (re.compile(r"一开始"), "at_beginning"),
    (re.compile(r"(?:第一|首)次(?:发作|就诊|看病)"), "first_episode_visit"),
]

# 4. Frequency: "每天", "经常", "反复", "持续"
_FREQUENCY_PATTERNS = [
    (re.compile(r"每天"), "daily"),
    (re.compile(r"天天"), "every_day"),
    (re.compile(r"经常"), "frequently"),
    (re.compile(r"频繁"), "frequent"),
    (re.compile(r"反复"), "recurring"),
    (re.compile(r"反反复复"), "recurring_emphasis"),
    (re.compile(r"持续"), "continuous"),
    (re.compile(r"一直(?:都?(?:是|在|有))?"), "always"),
    (re.compile(r"老是"), "always_colloquial"),
    (re.compile(r"总是"), "always_formal"),
    (re.compile(r"很久了"), "long_time"),
    (re.compile(r"好久了"), "long_time_colloquial"),
    (re.compile(r"长时间"), "long_duration"),
    (re.compile(r"时好时坏"), "fluctuating"),
    (re.compile(r"断断续续"), "intermittent"),
]

# 5. Course indicators: "加重", "缓解", "复发", "慢性"
_COURSE_INDICATOR_PATTERNS = [
    (re.compile(r"加重"), "worsening"),
    (re.compile(r"恶化"), "deteriorating"),
    (re.compile(r"缓解"), "remission"),
    (re.compile(r"复发"), "relapse"),
    (re.compile(r"慢性"), "chronic"),
    (re.compile(r"(?:越来越|逐渐|日渐)(?:严重|重|厉害|差)"), "progressive"),
    (re.compile(r"(?:以前|之前|过去)也.{0,6}(?:有过|出现过|发作过)"), "prior_episodes"),
    (re.compile(r"(?:反复|多次)(?:发作|就诊|住院|看病)"), "recurrent_events"),
    (re.compile(r"(?:看了|吃了|治了)(?:好|很)(?:几|多|长)"), "prolonged_treatment"),
]

# Short-duration markers (evidence AGAINST >=6 months)
_SHORT_DURATION_PATTERNS = [
    (re.compile(r"最近(?:才|刚|刚刚)?(?:开始|出现|有)"), "recent_onset"),
    (re.compile(r"(?:就)?这几天"), "these_few_days"),
    (re.compile(r"刚(?:刚)?开始"), "just_started"),
    (re.compile(r"(?:这|上)(?:个|一)?(?:星期|周)"), "this_week"),
]


# ---------------------------------------------------------------------------
# Duration estimation helpers
# ---------------------------------------------------------------------------

def _estimate_months_from_match(
    text: str, kind: str, pattern_type: str
) -> float | None:
    """Estimate months from a matched temporal expression."""
    if pattern_type == "month":
        n = _zh_num_to_int(text)
        return float(n) if n is not None else None
    if pattern_type == "year":
        n = _zh_num_to_int(text)
        return float(n * 12) if n is not None else None
    if pattern_type == "week":
        n = _zh_num_to_int(text)
        return float(n * 0.25) if n is not None else None
    if pattern_type == "day":
        n = _zh_num_to_int(text)
        return float(n / 30.0) if n is not None else None
    if pattern_type == "half_year":
        return 6.0
    if pattern_type == "several_months":
        return 4.0  # conservative estimate for "几个月"
    if pattern_type == "several_years":
        return 36.0  # conservative: "几年" → ~3 years
    if pattern_type == "many_years":
        return 60.0  # "多年" → ~5 years
    if pattern_type == "long_time":
        return 12.0
    if pattern_type == "last_year":
        return 12.0
    if pattern_type == "year_before_last":
        return 24.0
    if pattern_type == "three_years_ago":
        return 36.0
    if pattern_type == "last_month":
        return 1.0
    if pattern_type == "few_months_ago":
        return 3.0
    if pattern_type == "last_semester":
        return 5.0
    if pattern_type == "this_semester":
        return 3.0
    if pattern_type == "already_long_time":
        return 12.0
    return None


def _months_from_timedelta(delta: dict[str, Any] | None) -> float | None:
    """Convert a timedelta-like dict to a month estimate."""
    if not isinstance(delta, dict):
        return None

    years = float(delta.get("year", 0) or 0)
    months = float(delta.get("month", 0) or 0)
    days = float(delta.get("day", 0) or 0)
    total_months = years * 12 + months + days / 30.0
    return round(total_months, 2) if total_months > 0 else None


def _parse_datetime(value: Any) -> datetime | None:
    """Parse a datetime-ish value returned by external temporal tools."""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None

    stripped = value.strip()
    if not stripped:
        return None

    try:
        return datetime.fromisoformat(stripped.replace("Z", "+00:00"))
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(stripped, fmt)
        except ValueError:
            continue
    return None


def _months_since(dt: datetime | None, now: datetime | None = None) -> float | None:
    """Estimate months elapsed since a parsed timestamp."""
    if dt is None:
        return None

    reference = now or datetime.now()
    delta_days = (reference - dt).total_seconds() / 86400.0
    if delta_days < 0:
        return None
    return round(delta_days / 30.0, 2)


def _estimate_zh_years(text: str) -> float | None:
    """Estimate month duration from year-based Chinese expressions."""
    if "半年" in text:
        return 6.0
    if "几年" in text:
        return 36.0
    if "多年" in text:
        return 60.0

    match = re.search(r"([一二两三四五六七八九十百千\d]+)\s*年", text)
    if match is None:
        return None

    value = _zh_num_to_int(match.group(1))
    return float(value * 12) if value is not None else None


def _estimate_zh_months(text: str) -> float | None:
    """Estimate month duration from month-based Chinese expressions."""
    if "大半年" in text or "半年" in text:
        return 6.0
    if "几个月" in text:
        return 4.0

    match = re.search(r"([一二两三四五六七八九十百千\d]+)\s*个?多?月", text)
    if match is None:
        return None

    value = _zh_num_to_int(match.group(1))
    return float(value) if value is not None else None


def _estimate_zh_weeks(text: str) -> float | None:
    """Estimate month duration from week-based Chinese expressions."""
    if any(marker in text for marker in ("上周", "这周", "这个星期", "这星期")):
        return 0.25

    match = re.search(r"([一二两三四五六七八九十百千\d]+)\s*(?:周|个?星期)", text)
    if match is None:
        return None

    value = _zh_num_to_int(match.group(1))
    return round(value * 0.25, 2) if value is not None else None


def _estimate_zh_days(text: str) -> float | None:
    """Estimate month duration from day-based Chinese expressions."""
    if any(marker in text for marker in ("这几天", "三四天", "几天")):
        return 0.1

    match = re.search(r"([一二两三四五六七八九十百千\d]+)\s*天", text)
    if match is None:
        return None

    value = _zh_num_to_int(match.group(1))
    return round(value / 30.0, 2) if value is not None else None


def _estimate_months_from_temporal_text(text: str) -> float | None:
    """Estimate months from a temporal fragment or sentence."""
    stripped = text.strip()
    if not stripped:
        return None

    school_stage_months = {
        "大一": 36.0,
        "大二": 48.0,
        "大三": 60.0,
        "大四": 72.0,
    }
    for marker, months in school_stage_months.items():
        if marker in stripped:
            return months

    for regex, kind in _EXPLICIT_DURATION_PATTERNS:
        match = regex.search(stripped)
        if match is None:
            continue
        group1 = match.group(1) if match.lastindex and match.lastindex >= 1 else ""
        estimated = _estimate_months_from_match(group1, kind, kind)
        if estimated is not None:
            return estimated

    for regex, kind in _RELATIVE_TIME_PATTERNS:
        if regex.search(stripped):
            estimated = _estimate_months_from_match("", kind, kind)
            if estimated is not None:
                return estimated

    for estimator in (
        _estimate_zh_years,
        _estimate_zh_months,
        _estimate_zh_weeks,
        _estimate_zh_days,
    ):
        estimated = estimator(stripped)
        if estimated is not None:
            return estimated

    if "最近" in stripped:
        return 0.1
    return None


def _ctnlp_extract_months(text: str) -> float | None:
    """Extract a month estimate using ChineseTimeNLP when available."""
    tn = _get_chinese_time_nlp()
    if tn is None:
        return None

    try:
        result = tn.parse(target=text)
    except Exception:
        logger.debug("ChineseTimeNLP parse failed.", exc_info=True)
        return None

    months: float | None = None
    if isinstance(result, dict):
        result_type = result.get("type")
        if result_type == "timedelta":
            months = _months_from_timedelta(result.get("timedelta"))
        elif result_type == "timestamp":
            months = _months_since(_parse_datetime(result.get("timestamp")))
        elif result_type == "timespan":
            timespan = result.get("timespan")
            if isinstance(timespan, list) and timespan:
                months = _months_since(_parse_datetime(timespan[0]))

    if months is not None and months > 0.05:
        return months

    fallback = _estimate_months_from_temporal_text(text)
    if fallback is not None:
        return fallback
    return months if months is not None and months > 0 else None


def _stanza_extract_temporal(text: str, turn_id: int) -> list[TemporalMatch]:
    """Extract temporal matches from stanza NER entities when available."""
    nlp = _get_stanza_nlp()
    if nlp is None:
        return []

    try:
        doc = nlp(text)
    except Exception:
        logger.debug("stanza temporal NER parse failed.", exc_info=True)
        return []

    results: list[TemporalMatch] = []
    seen_texts: set[str] = set()
    for sent in getattr(doc, "sentences", []):
        for ent in getattr(sent, "entities", []):
            ent_type = getattr(ent, "type", None)
            ent_text = getattr(ent, "text", "").strip()
            if ent_type not in ("DATE", "TIME", "DURATION") or not ent_text:
                continue
            if ent_text in seen_texts:
                continue

            estimated = _ctnlp_extract_months(ent_text)
            if estimated is None:
                estimated = _estimate_months_from_temporal_text(ent_text)

            if ent_type == "DURATION":
                category = "explicit_duration"
            elif estimated is not None:
                category = "relative_time"
            else:
                category = "onset_marker"

            results.append(
                TemporalMatch(
                    category=category,
                    text=ent_text,
                    turn_id=turn_id,
                    estimated_months=estimated,
                )
            )
            seen_texts.add(ent_text)

    return results


# ---------------------------------------------------------------------------
# Core extraction function
# ---------------------------------------------------------------------------

def _extract_from_text(
    text: str, turn_id: int
) -> list[TemporalMatch]:
    """Extract all temporal matches from a single text string."""
    results: list[TemporalMatch] = []

    for regex, kind in _EXPLICIT_DURATION_PATTERNS:
        for m in regex.finditer(text):
            group1 = m.group(1) if m.lastindex and m.lastindex >= 1 else ""
            est = _estimate_months_from_match(group1, kind, kind)
            results.append(TemporalMatch(
                category="explicit_duration",
                text=m.group(0),
                turn_id=turn_id,
                estimated_months=est,
            ))

    for regex, kind in _RELATIVE_TIME_PATTERNS:
        for m in regex.finditer(text):
            est = _estimate_months_from_match("", kind, kind)
            results.append(TemporalMatch(
                category="relative_time",
                text=m.group(0),
                turn_id=turn_id,
                estimated_months=est,
            ))

    for regex, kind in _ONSET_MARKER_PATTERNS:
        for m in regex.finditer(text):
            results.append(TemporalMatch(
                category="onset_marker",
                text=m.group(0),
                turn_id=turn_id,
            ))

    for regex, kind in _FREQUENCY_PATTERNS:
        for m in regex.finditer(text):
            results.append(TemporalMatch(
                category="frequency",
                text=m.group(0),
                turn_id=turn_id,
            ))

    for regex, kind in _COURSE_INDICATOR_PATTERNS:
        for m in regex.finditer(text):
            results.append(TemporalMatch(
                category="course_indicator",
                text=m.group(0),
                turn_id=turn_id,
            ))

    return results


def _check_short_duration(text: str) -> bool:
    """Check if text contains markers suggesting short/recent onset."""
    for regex, _ in _SHORT_DURATION_PATTERNS:
        if regex.search(text):
            return True
    return False


# ---------------------------------------------------------------------------
# Duration inference logic
# ---------------------------------------------------------------------------

def _infer_duration(matches: list[TemporalMatch], has_short_markers: bool) -> TemporalFeatures:
    """Apply duration inference rules to aggregated matches.

    Rules:
    - If explicit duration >= 6 months -> high confidence (0.9)
    - If explicit duration 3-6 months -> medium (0.6)
    - If multiple onset/course markers without explicit duration -> medium (0.5)
    - If only frequency markers -> low (0.3)
    - If dense persistence/course evidence suggests chronic psychiatric course
      -> threshold confidence with inferred long duration
    - No temporal info -> neutral (0.0)
    - Short-duration markers reduce confidence
    """
    if not matches:
        return TemporalFeatures(
            matches=[],
            duration_confidence=0.0,
            reasoning="对话中未发现任何时间线信息。",
        )

    # Gather explicit duration estimates
    explicit_months: list[float] = []
    for m in matches:
        if m.category == "explicit_duration" and m.estimated_months is not None:
            explicit_months.append(m.estimated_months)

    # Gather relative time estimates
    relative_months: list[float] = []
    for m in matches:
        if m.category == "relative_time" and m.estimated_months is not None:
            relative_months.append(m.estimated_months)

    # Count categories
    cats: dict[str, int] = {}
    for m in matches:
        cats[m.category] = cats.get(m.category, 0) + 1

    onset_count = cats.get("onset_marker", 0)
    course_count = cats.get("course_indicator", 0)
    frequency_count = cats.get("frequency", 0)
    relative_count = cats.get("relative_time", 0)
    # Relative-time matches without month estimates (e.g. life events) act like onset markers
    relative_no_est = sum(
        1 for m in matches
        if m.category == "relative_time" and m.estimated_months is None
    )

    best_months: float | None = None
    confidence = 0.0
    reasoning_parts: list[str] = []

    # Rule 1: Explicit duration
    if explicit_months:
        best_months = max(explicit_months)
        if best_months >= 6.0:
            confidence = 0.9
            reasoning_parts.append(
                f"明确时间表述提示持续约{best_months:.0f}个月（≥6个月）。"
            )
        elif best_months >= 3.0:
            confidence = 0.6
            reasoning_parts.append(
                f"明确时间表述提示持续约{best_months:.0f}个月（3-6个月）。"
            )
        else:
            confidence = 0.3
            reasoning_parts.append(
                f"明确时间表述提示持续约{best_months:.0f}个月（<3个月）。"
            )

    # Rule 2: Relative time references (can supplement or stand alone)
    if relative_months:
        rel_best = max(relative_months)
        if best_months is None or rel_best > best_months:
            best_months = rel_best
        if rel_best >= 6.0:
            new_conf = 0.85
            if new_conf > confidence:
                confidence = new_conf
                reasoning_parts.append(
                    f"相对时间参照提示持续约{rel_best:.0f}个月。"
                )

    # Rule 2b: Relative time without month estimates (life events, etc.)
    # Treat these like strong onset markers since they imply extended duration
    if not explicit_months and not relative_months and relative_no_est > 0:
        if course_count >= 1 or frequency_count >= 1:
            confidence = max(confidence, 0.6)
            reasoning_parts.append(
                f"发现{relative_no_est}个生活事件时间参照和病程/持续性描述，"
                "提示较长病程。"
            )
        else:
            confidence = max(confidence, 0.4)
            reasoning_parts.append(
                f"发现{relative_no_est}个生活事件时间参照，提示一定持续时间。"
            )

    # Rule 3: Onset + course markers (no explicit duration)
    effective_onset = onset_count + relative_no_est
    if not explicit_months and not relative_months:
        if effective_onset >= 1 and course_count >= 1:
            confidence = max(confidence, 0.5)
            reasoning_parts.append(
                f"发现{effective_onset}个起病标志和{course_count}个病程变化描述，"
                "虽无明确时间但提示较长病程。"
            )
        elif effective_onset + course_count >= 2:
            confidence = max(confidence, 0.5)
            total_oc = effective_onset + course_count
            reasoning_parts.append(
                f"发现{total_oc}个起病/病程标志，提示较长病程。"
            )

    # Rule 4: Frequency markers only
    if (not explicit_months and not relative_months
            and onset_count == 0 and course_count == 0
            and frequency_count > 0):
        confidence = max(confidence, 0.3)
        reasoning_parts.append(
            f"发现{frequency_count}个频率/持续性表述，提示症状持续但时间不明确。"
        )

    multi_frequency_boost_applied = False
    if not explicit_months and not relative_months and frequency_count >= 3:
        if onset_count > 0 or course_count > 0:
            confidence = max(confidence, 0.55)
            reasoning_parts.append(
                "发现多个频率/持续性表述并伴随起病或病程标志，提示症状长期存在。"
            )
        else:
            confidence = max(confidence, 0.45)
            reasoning_parts.append(
                "发现多个频率/持续性表述，提示症状可能持续较久。"
            )
        multi_frequency_boost_applied = True

    # Boost: frequency + course/onset together
    if (
        frequency_count > 0
        and (onset_count > 0 or course_count > 0)
        and not multi_frequency_boost_applied
    ):
        confidence = min(confidence + 0.1, 0.95)
        reasoning_parts.append("频率表述与病程标志并存，置信度上调。")

    # Rule 5: Chronic course heuristic for psychiatric dialogue.
    # A short explicit duration may describe recent worsening rather than total
    # illness course, so allow dense persistence/course markers to lift the
    # inferred duration above the local episode length.
    persistence_count = frequency_count + course_count
    recurrence_markers = sum(
        1
        for m in matches
        if m.category == "course_indicator"
        and any(keyword in m.text for keyword in ("反复", "复发", "以前也"))
    )
    if persistence_count >= 4 and not has_short_markers:
        confidence = max(confidence, 0.55)
        best_months = max(best_months or 0.0, 8.0)
        reasoning_parts.append(
            f"发现{persistence_count}个持续性/病程标志，提示慢性精神科病程。"
        )

    if recurrence_markers >= 1 and persistence_count >= 2:
        confidence = max(confidence, 0.55)
        best_months = max(best_months or 0.0, 12.0)
        reasoning_parts.append(
            "发现复发/既往史标志，提示病程超过6个月。"
        )

    # Penalty: short duration markers
    has_long_duration_evidence = best_months is not None and best_months >= 6.0
    if has_short_markers:
        if has_long_duration_evidence:
            confidence = max(confidence - 0.1, 0.0)
            reasoning_parts.append(
                "虽有近期起病表述，但存在明确长病程证据，置信度轻度下调。"
            )
        else:
            confidence = max(confidence - 0.3, 0.0)
            reasoning_parts.append("发现近期起病表述，置信度下调。")

    meets_criterion = (
        confidence >= 0.5
        and (best_months is None or best_months >= 6.0)
        and not (has_short_markers and (best_months is None or best_months < 6.0))
    )

    return TemporalFeatures(
        matches=matches,
        duration_confidence=round(confidence, 2),
        estimated_months=best_months,
        meets_6month_criterion=meets_criterion,
        reasoning=" ".join(reasoning_parts),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_temporal_features(transcript: list[Turn]) -> TemporalFeatures:
    """Extract temporal features from a clinical transcript.

    Uses a 3-layer hybrid pipeline:
    1. Regex patterns for clinical-context temporal cues.
    2. ChineseTimeNLP for supplementary duration normalization.
    3. stanza NER as a fallback when regex finds few explicit durations.

    Args:
        transcript: List of Turn objects from a clinical case.

    Returns:
        TemporalFeatures with matches, confidence, and duration estimate.
    """
    patient_turns = [turn for turn in transcript if turn.is_patient]
    all_matches: list[TemporalMatch] = []
    has_short = False

    # Layer 1: regex extraction remains the primary source of temporal evidence.
    for turn in patient_turns:
        matches = _extract_from_text(turn.text, turn.turn_id)
        all_matches.extend(matches)
        if _check_short_duration(turn.text):
            has_short = True

    # Layer 2: ChineseTimeNLP runs on every patient turn when available.
    ctnlp_max_months: float | None = None
    for turn in patient_turns:
        months = _ctnlp_extract_months(turn.text)
        if months is None:
            continue
        if ctnlp_max_months is None or months > ctnlp_max_months:
            ctnlp_max_months = months

    # Layer 3: stanza NER is only used when regex found limited explicit data.
    explicit_count = sum(1 for m in all_matches if m.category == "explicit_duration")
    if explicit_count < 2:
        existing_texts = {match.text for match in all_matches}
        for turn in patient_turns:
            for stanza_match in _stanza_extract_temporal(turn.text, turn.turn_id):
                if stanza_match.text in existing_texts:
                    continue
                all_matches.append(stanza_match)
                existing_texts.add(stanza_match.text)

    features = _infer_duration(all_matches, has_short)
    if ctnlp_max_months is not None:
        if (
            features.estimated_months is None
            or ctnlp_max_months > features.estimated_months
        ):
            features.estimated_months = ctnlp_max_months

        if ctnlp_max_months >= 6.0 and features.duration_confidence < 0.7:
            features.duration_confidence = round(
                max(features.duration_confidence, 0.7), 2
            )
            extra_reasoning = "ChineseTimeNLP检测到≥6个月的时间表述。"
            features.reasoning = (
                f"{features.reasoning} {extra_reasoning}".strip()
                if features.reasoning
                else extra_reasoning
            )

        features.meets_6month_criterion = (
            features.duration_confidence >= 0.5
            and (
                features.estimated_months is None
                or features.estimated_months >= 6.0
            )
            and not (
                has_short
                and (
                    features.estimated_months is None
                    or features.estimated_months < 6.0
                )
            )
        )

    logger.debug(
        "Temporal extraction: %d matches, confidence=%.2f, months=%s, ctnlp=%s",
        len(all_matches),
        features.duration_confidence,
        features.estimated_months,
        ctnlp_max_months,
    )
    return features
