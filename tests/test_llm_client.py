# tests/test_llm_client.py
"""Tests for Ollama LLM client."""
import pytest
from unittest.mock import patch, MagicMock
from culturedx.llm.client import OllamaClient


class TestOllamaClient:
    def test_create_client(self):
        client = OllamaClient(
            base_url="http://localhost:11434",
            model="qwen3:14b",
            temperature=0.0,
        )
        assert client.model == "qwen3:14b"

    @patch("culturedx.llm.client.httpx.post")
    def test_generate(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": '{"diagnosis": "F32"}'}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = OllamaClient(
            base_url="http://localhost:11434",
            model="qwen3:14b",
        )
        result = client.generate("Diagnose this patient")
        assert "F32" in result
        mock_post.assert_called_once()

    def test_prompt_hash(self):
        client = OllamaClient(
            base_url="http://localhost:11434",
            model="qwen3:14b",
        )
        h1 = client.compute_prompt_hash("prompt_a")
        h2 = client.compute_prompt_hash("prompt_b")
        h3 = client.compute_prompt_hash("prompt_a")
        assert h1 != h2
        assert h1 == h3
