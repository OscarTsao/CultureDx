"""Tests for temporal reasoning module."""
from __future__ import annotations

import pytest

import culturedx.evidence.temporal as temporal
from culturedx.core.models import Turn
from culturedx.evidence.temporal import (
    TemporalFeatures,
    TemporalMatch,
    _check_short_duration,
    _extract_from_text,
    _infer_duration,
    _zh_num_to_int,
    extract_temporal_features,
)


# ---------------------------------------------------------------------------
# Chinese number conversion tests
# ---------------------------------------------------------------------------


class TestZhNumToInt:
    """Tests for _zh_num_to_int."""

    def test_arabic_numerals(self):
        assert _zh_num_to_int("6") == 6
        assert _zh_num_to_int("12") == 12
        assert _zh_num_to_int("100") == 100

    def test_single_chinese_digits(self):
        assert _zh_num_to_int("一") == 1
        assert _zh_num_to_int("二") == 2
        assert _zh_num_to_int("两") == 2
        assert _zh_num_to_int("三") == 3
        assert _zh_num_to_int("九") == 9

    def test_teens(self):
        assert _zh_num_to_int("十") == 10
        assert _zh_num_to_int("十一") == 11
        assert _zh_num_to_int("十二") == 12

    def test_tens(self):
        assert _zh_num_to_int("二十") == 20
        assert _zh_num_to_int("三十六") == 36

    def test_empty_and_invalid(self):
        assert _zh_num_to_int("") is None
        assert _zh_num_to_int("  ") is None
        assert _zh_num_to_int("半") is None
        assert _zh_num_to_int("abc") is None


# ---------------------------------------------------------------------------
# Explicit duration pattern tests
# ---------------------------------------------------------------------------


class TestExplicitDuration:
    """Tests for explicit duration patterns."""

    def test_months_chinese(self):
        """Test X个月 pattern with Chinese numerals."""
        matches = _extract_from_text("症状持续了六个月", 0)
        duration_matches = [m for m in matches if m.category == "explicit_duration"]
        assert len(duration_matches) >= 1
        assert any(m.estimated_months == 6.0 for m in duration_matches)

    def test_months_arabic(self):
        """Test X个月 with Arabic numeral."""
        matches = _extract_from_text("大概有8个月了", 0)
        duration_matches = [m for m in matches if m.category == "explicit_duration"]
        assert len(duration_matches) >= 1
        assert any(m.estimated_months == 8.0 for m in duration_matches)

    def test_years_chinese(self):
        """Test X年 pattern."""
        matches = _extract_from_text("已经两年了", 0)
        duration_matches = [m for m in matches if m.category == "explicit_duration"]
        assert len(duration_matches) >= 1
        assert any(m.estimated_months == 24.0 for m in duration_matches)

    def test_half_year(self):
        """Test 半年 pattern."""
        matches = _extract_from_text("差不多半年了吧", 0)
        duration_matches = [m for m in matches if m.category == "explicit_duration"]
        assert len(duration_matches) >= 1
        assert any(m.estimated_months == 6.0 for m in duration_matches)

    def test_several_months(self):
        """Test 几个月/好几个月 pattern."""
        matches = _extract_from_text("有好几个月了", 0)
        duration_matches = [m for m in matches if m.category == "explicit_duration"]
        assert len(duration_matches) >= 1
        assert any(m.estimated_months == 4.0 for m in duration_matches)

    def test_several_years(self):
        """Test 几年/好几年 pattern."""
        matches = _extract_from_text("这种情况好几年了", 0)
        duration_matches = [m for m in matches if m.category == "explicit_duration"]
        assert len(duration_matches) >= 1
        assert any(m.estimated_months == 36.0 for m in duration_matches)

    def test_many_years(self):
        """Test 多年 pattern."""
        matches = _extract_from_text("我失眠多年了", 0)
        duration_matches = [m for m in matches if m.category == "explicit_duration"]
        assert len(duration_matches) >= 1
        assert any(m.estimated_months == 60.0 for m in duration_matches)

    def test_weeks(self):
        """Test X周/X个星期 pattern."""
        matches = _extract_from_text("大概两周了", 0)
        duration_matches = [m for m in matches if m.category == "explicit_duration"]
        assert len(duration_matches) >= 1
        assert any(m.estimated_months == 0.5 for m in duration_matches)

    def test_days(self):
        """Test X天 pattern."""
        matches = _extract_from_text("已经三天了", 0)
        duration_matches = [m for m in matches if m.category == "explicit_duration"]
        assert len(duration_matches) >= 1
        assert any(m.estimated_months == pytest.approx(0.1) for m in duration_matches)

    def test_many_years_with_hen(self):
        """Test 很多年 pattern."""
        matches = _extract_from_text("这种担心很多年了", 0)
        duration_matches = [m for m in matches if m.category == "explicit_duration"]
        assert len(duration_matches) >= 1
        assert any(m.estimated_months == 60.0 for m in duration_matches)

    def test_long_time_explicit(self):
        """Test 好长时间/很长时间 pattern."""
        matches = _extract_from_text("已经很长时间了", 0)
        duration_matches = [m for m in matches if m.category == "explicit_duration"]
        assert len(duration_matches) >= 1
        assert any(m.estimated_months == 12.0 for m in duration_matches)

    def test_long_time_phrase_counts_as_explicit_duration(self):
        """很久了/好久了 should count as explicit long duration."""
        matches = _extract_from_text("这种情况很久了", 0)
        duration_matches = [m for m in matches if m.category == "explicit_duration"]
        assert len(duration_matches) >= 1
        assert any(m.estimated_months == 12.0 for m in duration_matches)


# ---------------------------------------------------------------------------
# Relative time pattern tests
# ---------------------------------------------------------------------------


class TestRelativeTime:
    """Tests for relative time patterns."""

    def test_last_year(self):
        """Test 去年 pattern."""
        matches = _extract_from_text("去年就开始这样了", 0)
        relative_matches = [m for m in matches if m.category == "relative_time"]
        assert any(m.estimated_months == 12.0 for m in relative_matches)

    def test_last_year_boundary(self):
        """Test 去年年底/去年年初 pattern."""
        matches = _extract_from_text("去年年底就开始这样了", 0)
        relative_matches = [m for m in matches if m.category == "relative_time"]
        assert any(m.estimated_months == 12.0 for m in relative_matches)

    def test_year_before_last(self):
        """Test 前年 pattern."""
        matches = _extract_from_text("前年就有这个问题", 0)
        relative_matches = [m for m in matches if m.category == "relative_time"]
        assert any(m.estimated_months == 24.0 for m in relative_matches)

    def test_last_month(self):
        """Test 上个月 pattern."""
        matches = _extract_from_text("上个月开始加重", 0)
        relative_matches = [m for m in matches if m.category == "relative_time"]
        assert any(m.estimated_months == 1.0 for m in relative_matches)

    def test_few_months_ago(self):
        """Test 前几个月 pattern."""
        matches = _extract_from_text("前几个月就有点不对劲", 0)
        relative_matches = [m for m in matches if m.category == "relative_time"]
        assert any(m.estimated_months == 3.0 for m in relative_matches)

    def test_since_event(self):
        """Test 从...开始 pattern."""
        matches = _extract_from_text("从失业那天开始就焦虑", 0)
        relative_matches = [m for m in matches if m.category == "relative_time"]
        assert len(relative_matches) >= 1
        assert any("从失业那天开始" in m.text for m in relative_matches)

    def test_already_duration(self):
        """Test 已经...了 pattern."""
        matches = _extract_from_text("已经很长时间了", 0)
        relative_matches = [m for m in matches if m.category == "relative_time"]
        assert len(relative_matches) >= 1

    def test_already_long_time(self):
        """已经持续很久了 should estimate a long relative duration."""
        matches = _extract_from_text("已经持续很久了", 0)
        relative_matches = [m for m in matches if m.category == "relative_time"]
        assert len(relative_matches) >= 1
        assert any(m.estimated_months == 12.0 for m in relative_matches)

    def test_life_event(self):
        """Test life event pattern (毕业以后, 离婚以来, etc.)."""
        matches = _extract_from_text("离婚以后一直这样", 0)
        relative_matches = [m for m in matches if m.category == "relative_time"]
        assert len(relative_matches) >= 1
        assert any("离婚以后" in m.text or "离婚后" in m.text
                    for m in relative_matches)

    def test_last_season(self):
        """Test season-based reference."""
        matches = _extract_from_text("去年冬天就开始了", 0)
        relative_matches = [m for m in matches if m.category == "relative_time"]
        assert len(relative_matches) >= 1


# ---------------------------------------------------------------------------
# Onset marker pattern tests
# ---------------------------------------------------------------------------


class TestOnsetMarkers:
    """Tests for onset marker patterns."""

    def test_onset(self):
        matches = _extract_from_text("发病的时候很突然", 0)
        onset_matches = [m for m in matches if m.category == "onset_marker"]
        assert len(onset_matches) >= 1

    def test_first_appeared(self):
        matches = _extract_from_text("开始出现失眠症状", 0)
        onset_matches = [m for m in matches if m.category == "onset_marker"]
        assert len(onset_matches) >= 1

    def test_first_time(self):
        matches = _extract_from_text("首次发作是在去年", 0)
        onset_matches = [m for m in matches if m.category == "onset_marker"]
        assert len(onset_matches) >= 1

    def test_initially(self):
        matches = _extract_from_text("起初只是睡不好", 0)
        onset_matches = [m for m in matches if m.category == "onset_marker"]
        assert len(onset_matches) >= 1

    def test_at_beginning(self):
        matches = _extract_from_text("一开始只是有点紧张", 0)
        onset_matches = [m for m in matches if m.category == "onset_marker"]
        assert len(onset_matches) >= 1


# ---------------------------------------------------------------------------
# Frequency pattern tests
# ---------------------------------------------------------------------------


class TestFrequencyPatterns:
    """Tests for frequency/persistence patterns."""

    def test_daily(self):
        matches = _extract_from_text("每天都睡不好", 0)
        freq_matches = [m for m in matches if m.category == "frequency"]
        assert len(freq_matches) >= 1

    def test_always(self):
        matches = _extract_from_text("一直都有这个问题", 0)
        freq_matches = [m for m in matches if m.category == "frequency"]
        assert len(freq_matches) >= 1

    def test_frequently(self):
        matches = _extract_from_text("经常感到胸闷心慌", 0)
        freq_matches = [m for m in matches if m.category == "frequency"]
        assert len(freq_matches) >= 1

    def test_recurring(self):
        matches = _extract_from_text("反复出现焦虑症状", 0)
        freq_matches = [m for m in matches if m.category == "frequency"]
        assert len(freq_matches) >= 1

    def test_long_time(self):
        matches = _extract_from_text("这种情况很久了", 0)
        freq_matches = [m for m in matches if m.category == "frequency"]
        assert len(freq_matches) >= 1

    def test_fluctuating(self):
        matches = _extract_from_text("时好时坏的", 0)
        freq_matches = [m for m in matches if m.category == "frequency"]
        assert len(freq_matches) >= 1

    def test_continuous(self):
        matches = _extract_from_text("持续失眠", 0)
        freq_matches = [m for m in matches if m.category == "frequency"]
        assert len(freq_matches) >= 1


# ---------------------------------------------------------------------------
# Course indicator pattern tests
# ---------------------------------------------------------------------------


class TestCourseIndicators:
    """Tests for course indicator patterns."""

    def test_worsening(self):
        matches = _extract_from_text("最近症状加重了", 0)
        course_matches = [m for m in matches if m.category == "course_indicator"]
        assert len(course_matches) >= 1

    def test_progressive(self):
        matches = _extract_from_text("焦虑越来越严重", 0)
        course_matches = [m for m in matches if m.category == "course_indicator"]
        assert len(course_matches) >= 1

    def test_relapse(self):
        matches = _extract_from_text("上个月复发了", 0)
        course_matches = [m for m in matches if m.category == "course_indicator"]
        assert len(course_matches) >= 1

    def test_chronic(self):
        matches = _extract_from_text("已经是慢性焦虑了", 0)
        course_matches = [m for m in matches if m.category == "course_indicator"]
        assert len(course_matches) >= 1

    def test_prior_episodes(self):
        matches = _extract_from_text("以前也有过这种情况", 0)
        course_matches = [m for m in matches if m.category == "course_indicator"]
        assert len(course_matches) >= 1

    def test_recurrent_events(self):
        matches = _extract_from_text("反复发作好几次了", 0)
        course_matches = [m for m in matches if m.category == "course_indicator"]
        assert len(course_matches) >= 1

    def test_prolonged_treatment(self):
        matches = _extract_from_text("吃了好几个月的药", 0)
        course_matches = [m for m in matches if m.category == "course_indicator"]
        assert len(course_matches) >= 1


# ---------------------------------------------------------------------------
# Short duration detection
# ---------------------------------------------------------------------------


class TestShortDuration:
    """Tests for short duration marker detection."""

    def test_recent_onset(self):
        assert _check_short_duration("最近才开始焦虑") is True

    def test_these_few_days(self):
        assert _check_short_duration("就这几天睡不好") is True

    def test_just_started(self):
        assert _check_short_duration("刚刚开始有症状") is True

    def test_no_short_markers(self):
        assert _check_short_duration("一直都有这个问题") is False


# ---------------------------------------------------------------------------
# Duration inference logic tests
# ---------------------------------------------------------------------------


class TestDurationInference:
    """Tests for the duration inference logic."""

    def test_explicit_gte_6_months_high_confidence(self):
        """Explicit duration >= 6 months should yield confidence 0.9."""
        matches = [
            TemporalMatch(
                category="explicit_duration",
                text="八个月",
                turn_id=0,
                estimated_months=8.0,
            )
        ]
        result = _infer_duration(matches, has_short_markers=False)
        assert result.duration_confidence == 0.9
        assert result.meets_6month_criterion is True
        assert result.estimated_months == 8.0

    def test_explicit_3_to_6_months_medium_confidence(self):
        """Explicit 3-6 month duration should yield confidence 0.6."""
        matches = [
            TemporalMatch(
                category="explicit_duration",
                text="四个月",
                turn_id=0,
                estimated_months=4.0,
            )
        ]
        result = _infer_duration(matches, has_short_markers=False)
        assert result.duration_confidence == 0.6
        assert result.meets_6month_criterion is False  # < 6 months

    def test_onset_plus_course_medium_confidence(self):
        """Onset + course markers without explicit duration -> 0.5 confidence."""
        matches = [
            TemporalMatch(category="onset_marker", text="发病", turn_id=0),
            TemporalMatch(category="course_indicator", text="加重", turn_id=1),
        ]
        result = _infer_duration(matches, has_short_markers=False)
        assert result.duration_confidence >= 0.5
        assert result.meets_6month_criterion is True

    def test_frequency_only_low_confidence(self):
        """Only frequency markers -> 0.3 confidence."""
        matches = [
            TemporalMatch(category="frequency", text="每天", turn_id=0),
            TemporalMatch(category="frequency", text="经常", turn_id=1),
        ]
        result = _infer_duration(matches, has_short_markers=False)
        assert result.duration_confidence == 0.3
        assert result.meets_6month_criterion is False

    def test_no_matches_zero_confidence(self):
        """No matches -> 0.0 confidence."""
        result = _infer_duration([], has_short_markers=False)
        assert result.duration_confidence == 0.0
        assert result.meets_6month_criterion is False

    def test_short_markers_do_not_override_explicit_long_duration(self):
        """Short markers should only mildly reduce confidence when long duration is explicit."""
        matches = [
            TemporalMatch(
                category="explicit_duration",
                text="八个月",
                turn_id=0,
                estimated_months=8.0,
            )
        ]
        result = _infer_duration(matches, has_short_markers=True)
        assert result.duration_confidence == 0.8  # 0.9 - 0.1
        assert result.meets_6month_criterion is True

    def test_relative_time_last_year(self):
        """Relative time 'last year' should give ~12 months estimate."""
        matches = [
            TemporalMatch(
                category="relative_time",
                text="去年",
                turn_id=0,
                estimated_months=12.0,
            )
        ]
        result = _infer_duration(matches, has_short_markers=False)
        assert result.duration_confidence == 0.85
        assert result.estimated_months == 12.0
        assert result.meets_6month_criterion is True

    def test_frequency_plus_course_boost(self):
        """Frequency + course markers together should get a confidence boost."""
        matches = [
            TemporalMatch(category="frequency", text="一直", turn_id=0),
            TemporalMatch(category="course_indicator", text="加重", turn_id=1),
        ]
        result = _infer_duration(matches, has_short_markers=False)
        # onset_count=0, course_count=1: not enough for rule 3 alone
        # but frequency + course boost applies: 0.0 + 0.1 = 0.1 (then boost)
        assert result.duration_confidence >= 0.1

    def test_three_frequency_markers_raise_confidence(self):
        """Three frequency markers should raise confidence above the default 0.3."""
        matches = [
            TemporalMatch(category="frequency", text="每天", turn_id=0),
            TemporalMatch(category="frequency", text="经常", turn_id=0),
            TemporalMatch(category="frequency", text="持续", turn_id=0),
        ]
        result = _infer_duration(matches, has_short_markers=False)
        assert result.duration_confidence == 0.45
        assert result.meets_6month_criterion is False

    def test_three_frequency_markers_with_course_reach_threshold(self):
        """Three frequency markers plus course evidence should reach 0.55 confidence."""
        matches = [
            TemporalMatch(category="frequency", text="每天", turn_id=0),
            TemporalMatch(category="frequency", text="经常", turn_id=0),
            TemporalMatch(category="frequency", text="持续", turn_id=0),
            TemporalMatch(category="course_indicator", text="加重", turn_id=1),
        ]
        result = _infer_duration(matches, has_short_markers=False)
        assert result.duration_confidence == 0.55
        assert result.meets_6month_criterion is True

    def test_chronic_course_heuristic_overrides_short_recent_episode(self):
        """Dense persistence markers should recover chronic course from a short episode mention."""
        matches = [
            TemporalMatch(
                category="explicit_duration",
                text="两个月",
                turn_id=0,
                estimated_months=2.0,
            ),
            TemporalMatch(category="frequency", text="总是", turn_id=0),
            TemporalMatch(category="frequency", text="每天", turn_id=0),
            TemporalMatch(category="frequency", text="天天", turn_id=0),
            TemporalMatch(category="frequency", text="经常", turn_id=0),
            TemporalMatch(category="course_indicator", text="越来越重", turn_id=1),
            TemporalMatch(category="onset_marker", text="一开始", turn_id=1),
        ]
        result = _infer_duration(matches, has_short_markers=False)
        assert result.duration_confidence == 0.55
        assert result.estimated_months == 8.0
        assert result.meets_6month_criterion is True

    def test_recurrence_markers_imply_long_history(self):
        """Recurrence markers should infer a long course even with a short recent episode."""
        matches = [
            TemporalMatch(
                category="explicit_duration",
                text="一个月",
                turn_id=0,
                estimated_months=1.0,
            ),
            TemporalMatch(category="frequency", text="一直", turn_id=0),
            TemporalMatch(category="frequency", text="每天", turn_id=0),
            TemporalMatch(category="course_indicator", text="以前也有过", turn_id=1),
        ]
        result = _infer_duration(matches, has_short_markers=False)
        assert result.duration_confidence == 0.55
        assert result.estimated_months == 12.0
        assert result.meets_6month_criterion is True


# ---------------------------------------------------------------------------
# Integration: extract_temporal_features
# ---------------------------------------------------------------------------


class TestExtractTemporalFeatures:
    """Integration tests using full transcript Turn objects."""

    @staticmethod
    def _make_transcript(patient_texts: list[str]) -> list[Turn]:
        """Build a simple transcript with patient turns."""
        turns = []
        for i, text in enumerate(patient_texts):
            turns.append(Turn(speaker="doctor", text="请描述一下您的情况。", turn_id=i * 2))
            turns.append(Turn(speaker="patient", text=text, turn_id=i * 2 + 1))
        return turns

    def test_chronic_anxiety_with_explicit_duration(self):
        """Classic case: patient says '八个月' explicitly."""
        transcript = self._make_transcript([
            "我焦虑大概有八个月了",
            "每天都担心各种事情",
        ])
        features = extract_temporal_features(transcript)
        assert features.duration_confidence >= 0.9
        assert features.estimated_months == 8.0
        assert features.meets_6month_criterion is True

    def test_implicit_duration_last_year(self):
        """Patient references 'last year' as onset."""
        transcript = self._make_transcript([
            "去年冬天开始就一直这样",
            "心慌、胸闷、睡不着",
        ])
        features = extract_temporal_features(transcript)
        assert features.duration_confidence >= 0.8
        assert features.meets_6month_criterion is True

    def test_life_event_reference(self):
        """Duration inferred from life event reference."""
        transcript = self._make_transcript([
            "从离婚以来一直焦虑不安",
            "反反复复的，越来越严重",
        ])
        features = extract_temporal_features(transcript)
        assert features.duration_confidence >= 0.5
        assert len(features.matches) >= 2

    def test_no_temporal_info(self):
        """No temporal markers -> zero confidence."""
        transcript = self._make_transcript([
            "我感觉很紧张",
            "心慌、出汗",
        ])
        features = extract_temporal_features(transcript)
        assert features.duration_confidence == 0.0
        assert features.meets_6month_criterion is False

    def test_recent_onset_reduces_confidence(self):
        """Short-duration markers should prevent meeting 6-month criterion."""
        transcript = self._make_transcript([
            "最近才开始焦虑，大概两周了",
        ])
        features = extract_temporal_features(transcript)
        assert features.meets_6month_criterion is False

    def test_explicit_long_duration_survives_recent_onset_marker(self):
        """Explicit long duration should still satisfy the 6-month criterion."""
        transcript = self._make_transcript([
            "我这样已经一年了",
            "最近才开始这样",
        ])
        features = extract_temporal_features(transcript)
        assert features.estimated_months == 12.0
        assert features.duration_confidence == 0.8
        assert features.meets_6month_criterion is True

    def test_doctor_turns_ignored(self):
        """Only patient turns should be analyzed."""
        turns = [
            Turn(speaker="doctor", text="您这个症状持续多年了？", turn_id=0),
            Turn(speaker="patient", text="对", turn_id=1),
        ]
        features = extract_temporal_features(turns)
        # Doctor's "多年" should not be counted
        doctor_text_matches = [
            m for m in features.matches if m.turn_id == 0
        ]
        assert len(doctor_text_matches) == 0

    def test_multiple_temporal_cues(self):
        """Rich temporal narrative should yield high confidence."""
        transcript = self._make_transcript([
            "这个问题好几年了",
            "一开始只是有点紧张",
            "后来越来越严重",
            "反复发作，看了好几次医生",
            "吃了好久的药也不见好转",
        ])
        features = extract_temporal_features(transcript)
        assert features.duration_confidence >= 0.5
        assert len(features.matches) >= 3

    def test_summary_zh_output(self):
        """Test that summary_zh returns a non-empty string."""
        transcript = self._make_transcript(["症状持续了一年多"])
        features = extract_temporal_features(transcript)
        summary = features.summary_zh()
        assert len(summary) > 0
        assert "时间证据置信度" in summary

    def test_summary_zh_no_matches(self):
        """Test summary_zh with no temporal matches."""
        features = TemporalFeatures()
        summary = features.summary_zh()
        assert "未发现" in summary

    def test_half_year_matches_criterion(self):
        """半年 should match exactly 6.0 months and meet criterion."""
        transcript = self._make_transcript(["这种担忧持续了半年了"])
        features = extract_temporal_features(transcript)
        assert features.estimated_months == 6.0
        assert features.meets_6month_criterion is True

    def test_ctnlp_extract_months_from_timedelta(self, monkeypatch: pytest.MonkeyPatch):
        """ChineseTimeNLP helper should normalize timedelta output to months."""

        class FakeTimeNormalizer:
            def parse(self, target: str):
                return {
                    "type": "timedelta",
                    "timedelta": {"year": 1, "month": 2, "day": 15},
                }

        monkeypatch.setattr(temporal, "_get_chinese_time_nlp", lambda: FakeTimeNormalizer())
        assert temporal._ctnlp_extract_months("一年两个月半") == pytest.approx(14.5)

    def test_stanza_extract_temporal_builds_relative_time_match(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """stanza DATE entities should become relative-time evidence when estimable."""

        class FakeEntity:
            def __init__(self, text: str, entity_type: str):
                self.text = text
                self.type = entity_type

        class FakeSentence:
            def __init__(self, entities):
                self.entities = entities

        class FakeDoc:
            def __init__(self, entities):
                self.sentences = [FakeSentence(entities)]

        monkeypatch.setattr(temporal, "_get_chinese_time_nlp", lambda: None)
        monkeypatch.setattr(
            temporal,
            "_get_stanza_nlp",
            lambda: (lambda text: FakeDoc([FakeEntity("去年", "DATE")])),
        )

        matches = temporal._stanza_extract_temporal("去年开始这样", turn_id=1)
        assert len(matches) == 1
        assert matches[0].category == "relative_time"
        assert matches[0].estimated_months == 12.0

    def test_ctnlp_boosts_longer_duration_than_regex(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """ChineseTimeNLP should be able to lift a borderline regex estimate."""

        class FakeTimeNormalizer:
            def parse(self, target: str):
                return {"type": "timedelta", "timedelta": {"month": 8}}

        monkeypatch.setattr(temporal, "_get_chinese_time_nlp", lambda: FakeTimeNormalizer())
        monkeypatch.setattr(temporal, "_get_stanza_nlp", lambda: None)

        transcript = self._make_transcript(["我焦虑大概有五个月了"])
        features = extract_temporal_features(transcript)

        assert features.estimated_months == 8.0
        assert features.duration_confidence == 0.7
        assert features.meets_6month_criterion is True
        assert "ChineseTimeNLP" in features.reasoning

    def test_stanza_fallback_adds_temporal_match_when_regex_is_sparse(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """stanza fallback should add useful temporal evidence on regex-light cases."""

        class FakeEntity:
            def __init__(self, text: str, entity_type: str):
                self.text = text
                self.type = entity_type

        class FakeSentence:
            def __init__(self, entities):
                self.entities = entities

        class FakeDoc:
            def __init__(self, entities):
                self.sentences = [FakeSentence(entities)]

        monkeypatch.setattr(temporal, "_get_chinese_time_nlp", lambda: None)
        monkeypatch.setattr(
            temporal,
            "_get_stanza_nlp",
            lambda: (
                lambda text: FakeDoc([FakeEntity("大三", "DATE")])
                if "大三" in text
                else FakeDoc([])
            ),
        )

        transcript = self._make_transcript([
            "从高中开始就这样",
            "到现在大三还是一直紧张",
        ])
        features = extract_temporal_features(transcript)

        assert any(match.text == "大三" for match in features.matches)
        assert features.estimated_months == 60.0
        assert features.meets_6month_criterion is True

    def test_stanza_skipped_when_regex_finds_two_explicit_durations(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """stanza should not run on already-easy cases with multiple explicit durations."""
        stanza_calls = {"count": 0}

        def _fake_get_stanza():
            stanza_calls["count"] += 1
            return None

        monkeypatch.setattr(temporal, "_get_chinese_time_nlp", lambda: None)
        monkeypatch.setattr(temporal, "_get_stanza_nlp", _fake_get_stanza)

        transcript = self._make_transcript([
            "我这样已经八个月了",
            "之前也有一年多了",
        ])
        features = extract_temporal_features(transcript)

        assert stanza_calls["count"] == 0
        assert len([m for m in features.matches if m.category == "explicit_duration"]) >= 2
