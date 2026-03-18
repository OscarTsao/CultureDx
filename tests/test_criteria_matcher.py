"""Tests for criteria matcher."""
import pytest
from culturedx.evidence.criteria_matcher import CriteriaMatcher
from culturedx.evidence.retriever import MockRetriever


class TestCriteriaMatcher:
    def test_match_single_criterion(self):
        retriever = MockRetriever()
        matcher = CriteriaMatcher(retriever=retriever, top_k=5, min_score=0.0)
        evidence = matcher.match_criterion(
            criterion_text="depressed mood",
            sentences=["I feel very sad", "I can't sleep", "My head hurts"],
            turn_ids=[1, 2, 3],
            criterion_id="F32.B1",
        )
        assert evidence.criterion_id == "F32.B1"
        assert len(evidence.spans) > 0
        assert evidence.confidence > 0.0

    def test_match_for_disorder(self):
        retriever = MockRetriever()
        matcher = CriteriaMatcher(retriever=retriever, top_k=5, min_score=0.0)
        results = matcher.match_for_disorder(
            disorder_code="F32",
            sentences=[
                "我情绪很低落",
                "对什么都没兴趣",
                "晚上失眠",
                "感觉很疲劳",
            ],
            turn_ids=[1, 2, 3, 4],
            language="zh",
        )
        assert len(results) > 0
        # F32 has 11 criteria (A, B1-B3, C1-C7)
        assert all(e.criterion_id.startswith("F32.") for e in results)

    def test_somatization_boost(self):
        retriever = MockRetriever()
        matcher = CriteriaMatcher(retriever=retriever, top_k=5, min_score=0.0)

        sentences = ["头疼得厉害", "心情不好"]
        turn_ids = [1, 2]

        # Without boost
        evidence_no_boost = matcher.match_criterion(
            criterion_text="Sleep disturbance",
            sentences=sentences,
            turn_ids=turn_ids,
            criterion_id="F32.C6",
        )

        # With somatization boost for sentence 0
        somat_map = {"头疼得厉害": ["F32.C6"]}
        evidence_with_boost = matcher.match_criterion(
            criterion_text="Sleep disturbance",
            sentences=sentences,
            turn_ids=turn_ids,
            criterion_id="F32.C6",
            somatization_map=somat_map,
        )

        # The boosted version should have higher or equal confidence
        assert evidence_with_boost.confidence >= evidence_no_boost.confidence

    def test_empty_sentences(self):
        retriever = MockRetriever()
        matcher = CriteriaMatcher(retriever=retriever, top_k=5, min_score=0.0)
        evidence = matcher.match_criterion(
            criterion_text="depressed mood",
            sentences=[],
            criterion_id="F32.B1",
        )
        assert evidence.criterion_id == "F32.B1"
        assert len(evidence.spans) == 0
        assert evidence.confidence == 0.0
