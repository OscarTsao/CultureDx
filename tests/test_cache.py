# tests/test_cache.py
"""Tests for SQLite LLM response cache."""
import pytest
from culturedx.llm.cache import LLMCache


@pytest.fixture
def cache(tmp_path):
    with LLMCache(tmp_path / "test_cache.db") as c:
        yield c


class TestLLMCache:
    def test_get_miss(self, cache):
        result = cache.get("ollama", "model", "prompt_hash", "zh", "input")
        assert result is None

    def test_put_and_get(self, cache):
        cache.put("ollama", "model", "prompt_hash", "zh", "input", "output_text")
        result = cache.get("ollama", "model", "prompt_hash", "zh", "input")
        assert result == "output_text"

    def test_different_prompt_hash_miss(self, cache):
        cache.put("ollama", "model", "hash_a", "zh", "input", "output_a")
        result = cache.get("ollama", "model", "hash_b", "zh", "input")
        assert result is None

    def test_different_model_miss(self, cache):
        cache.put("ollama", "model_a", "hash", "zh", "input", "output_a")
        result = cache.get("ollama", "model_b", "hash", "zh", "input")
        assert result is None

    def test_different_language_miss(self, cache):
        cache.put("ollama", "model", "hash", "zh", "input", "output_zh")
        result = cache.get("ollama", "model", "hash", "en", "input")
        assert result is None

    def test_overwrite(self, cache):
        cache.put("ollama", "model", "hash", "zh", "input", "old")
        cache.put("ollama", "model", "hash", "zh", "input", "new")
        result = cache.get("ollama", "model", "hash", "zh", "input")
        assert result == "new"
