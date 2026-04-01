"""Tests for retriever abstraction."""
import pytest
from culturedx.evidence.retriever import (
    HybridRetriever,
    LexicalRetriever,
    RetrievalResult,
    MockRetriever,
)


class TestRetrievalResult:
    def test_create_result(self):
        r = RetrievalResult(text="I feel sad", turn_id=1, score=0.85)
        assert r.text == "I feel sad"
        assert r.turn_id == 1
        assert r.score == 0.85
        assert r.source == "dense"

    def test_sort_by_score(self):
        results = [
            RetrievalResult(text="a", turn_id=0, score=0.3),
            RetrievalResult(text="b", turn_id=1, score=0.9),
            RetrievalResult(text="c", turn_id=2, score=0.6),
        ]
        sorted_r = sorted(results, key=lambda r: r.score, reverse=True)
        assert sorted_r[0].score == 0.9
        assert sorted_r[-1].score == 0.3


class TestMockRetriever:
    def test_returns_results(self):
        retriever = MockRetriever()
        results = retriever.retrieve(
            query="depressed mood",
            sentences=["I feel sad", "I have a headache", "I can't sleep"],
            top_k=3,
        )
        assert len(results) == 3
        assert all(isinstance(r, RetrievalResult) for r in results)

    def test_top_k_limits(self):
        retriever = MockRetriever()
        results = retriever.retrieve(
            query="depressed mood",
            sentences=["a", "b", "c", "d", "e"],
            top_k=2,
        )
        assert len(results) == 2

    def test_empty_sentences(self):
        retriever = MockRetriever()
        results = retriever.retrieve(query="test", sentences=[])
        assert results == []

    def test_turn_ids_preserved(self):
        retriever = MockRetriever()
        results = retriever.retrieve(
            query="test",
            sentences=["a", "b", "c"],
            turn_ids=[10, 20, 30],
        )
        for r in results:
            assert r.turn_id in [10, 20, 30]

    def test_deterministic(self):
        retriever = MockRetriever()
        r1 = retriever.retrieve(query="q", sentences=["s1", "s2"])
        r2 = retriever.retrieve(query="q", sentences=["s1", "s2"])
        assert [r.score for r in r1] == [r.score for r in r2]

    def test_scores_between_0_and_1(self):
        retriever = MockRetriever()
        results = retriever.retrieve(
            query="test",
            sentences=["a", "b", "c", "d", "e"],
        )
        for r in results:
            assert 0.0 <= r.score <= 1.0


class TestLexicalRetriever:
    def test_prefers_token_overlap(self):
        retriever = LexicalRetriever()
        results = retriever.retrieve(
            query="睡不着 失眠",
            sentences=["我最近睡不着", "今天头疼", "天气不错"],
            top_k=3,
        )
        assert results[0].text == "我最近睡不着"
        assert results[0].source == "lexical"
        assert results[0].score >= results[-1].score

    def test_batch_order_matches_queries(self):
        retriever = LexicalRetriever()
        batches = retriever.retrieve_batch(
            queries=["失眠", "头疼"],
            sentences=["我睡不着", "我头疼", "没事"],
            top_k=2,
        )
        assert len(batches) == 2
        assert all(len(batch) <= 2 for batch in batches)


class TestHybridRetriever:
    def test_combines_dense_and_lexical_results(self):
        dense = MockRetriever()
        lexical = LexicalRetriever()
        retriever = HybridRetriever(dense_retriever=dense, lexical_retriever=lexical)
        results = retriever.retrieve(
            query="失眠",
            sentences=["我睡不着", "我头疼", "我很焦虑"],
            top_k=3,
        )
        assert len(results) == 3
        assert all(r.source in {"hybrid", "dense", "lexical"} for r in results)
        assert results[0].score >= results[-1].score

    def test_batch_preserves_query_order(self):
        retriever = HybridRetriever(
            dense_retriever=MockRetriever(),
            lexical_retriever=LexicalRetriever(),
        )
        batches = retriever.retrieve_batch(
            queries=["失眠", "焦虑"],
            sentences=["我睡不着", "我心慌", "没事"],
            top_k=2,
        )
        assert len(batches) == 2
        assert all(len(batch) <= 2 for batch in batches)
