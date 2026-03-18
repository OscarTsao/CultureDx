# tests/test_json_utils.py
"""Tests for JSON extraction from LLM responses."""
import pytest
from culturedx.llm.json_utils import extract_json_from_response


class TestExtractJson:
    def test_pure_json(self):
        text = '{"diagnosis": "F32", "confidence": 0.9}'
        result = extract_json_from_response(text)
        assert result["diagnosis"] == "F32"

    def test_json_in_markdown_block(self):
        text = 'Here is my analysis:\n```json\n{"diagnosis": "F32"}\n```\nDone.'
        result = extract_json_from_response(text)
        assert result["diagnosis"] == "F32"

    def test_json_embedded_in_text(self):
        text = 'The result is {"diagnosis": "F41.1", "score": 5} as shown.'
        result = extract_json_from_response(text)
        assert result["diagnosis"] == "F41.1"

    def test_no_json_returns_none(self):
        text = "I cannot provide a diagnosis."
        result = extract_json_from_response(text)
        assert result is None

    def test_malformed_json_returns_none(self):
        text = '{"diagnosis": "F32", confidence: 0.9}'
        result = extract_json_from_response(text)
        assert result is None

    def test_json_array(self):
        text = '[{"criterion": "A1", "status": "met"}]'
        result = extract_json_from_response(text)
        assert isinstance(result, list)
        assert result[0]["criterion"] == "A1"
