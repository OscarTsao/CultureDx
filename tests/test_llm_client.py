"""Tests for LLM clients and shared HTTP runtime."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from culturedx.llm.client import OllamaClient
from culturedx.llm.vllm_client import VLLMClient


def _response_json(content: dict, request: httpx.Request, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code=status_code, json=content, request=request)


class TestOllamaClient:
    def test_create_client(self):
        client = OllamaClient(
            base_url="http://localhost:11434",
            model="qwen3:14b",
            temperature=0.0,
        )
        assert client.model == "qwen3:14b"
        client.close()

    def test_generate_builds_expected_request_body(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["url"] = str(request.url)
            seen["body"] = json.loads(request.content.decode())
            return _response_json({"response": '{"diagnosis": "F32"}'}, request)

        client = OllamaClient(
            base_url="http://localhost:11434",
            model="qwen3:14b",
            transport=httpx.MockTransport(handler),
        )
        result = client.generate("Diagnose this patient", prompt_hash="abc123", language="zh")
        assert "F32" in result
        assert seen["method"] == "POST"
        assert seen["url"].endswith("/api/generate")
        assert seen["body"]["model"] == "qwen3:14b"
        assert seen["body"]["prompt"] == "Diagnose this patient"
        assert seen["body"]["think"] is False
        assert client.last_request_stats is not None
        assert client.last_request_stats.cache_hit is False
        client.close()

    def test_cache_hit_skips_transport(self, tmp_path):
        cache_path = tmp_path / "cache.db"
        calls = {"count": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["count"] += 1
            return _response_json({"response": "cached response"}, request)

        client = OllamaClient(
            base_url="http://localhost:11434",
            model="qwen3:14b",
            cache_path=cache_path,
            transport=httpx.MockTransport(handler),
        )
        first = client.generate("prompt")
        second = client.generate("prompt")
        assert first == second == "cached response"
        assert calls["count"] == 1
        assert client.last_request_stats is not None
        assert client.last_request_stats.cache_hit is True
        client.close()

    def test_retry_on_timeout(self):
        calls = {"count": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["count"] += 1
            if calls["count"] == 1:
                raise httpx.ReadTimeout("timeout", request=request)
            return _response_json({"response": "ok"}, request)

        client = OllamaClient(
            base_url="http://localhost:11434",
            model="qwen3:14b",
            max_retries=2,
            transport=httpx.MockTransport(handler),
        )
        result = client.generate("prompt")
        assert result == "ok"
        assert calls["count"] == 2
        assert client.last_request_stats is not None
        assert client.last_request_stats.retries == 1
        client.close()


class TestVLLMClient:
    def test_structured_outputs_use_response_format_then_fallback(self):
        calls = {"count": 0}
        seen_bodies: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls["count"] += 1
            body = json.loads(request.content.decode())
            seen_bodies.append(body)
            if calls["count"] == 1:
                return httpx.Response(
                    400,
                    json={"error": "response_format unsupported"},
                    request=request,
                )
            assert "guided_json" in body
            return _response_json(
                {
                    "choices": [
                        {"message": {"content": '{"diagnosis": "F32"}'}}
                    ]
                },
                request,
            )

        client = VLLMClient(
            base_url="http://localhost:8000",
            model="qwen3-32b",
            transport=httpx.MockTransport(handler),
        )
        text = client.generate("Prompt", json_schema={"type": "object"})
        assert "F32" in text
        assert calls["count"] == 2
        assert "response_format" in seen_bodies[0]
        assert "guided_json" in seen_bodies[1]
        assert client.last_request_stats is not None
        assert client.last_request_stats.structured_output_mode == "guided_json"
        client.close()

    def test_batch_generate_preserves_input_order(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode())
            prompt = body["messages"][-1]["content"]
            if "slow" in prompt:
                await asyncio.sleep(0.05)
            else:
                await asyncio.sleep(0.01)
            return _response_json(
                {
                    "choices": [
                        {"message": {"content": f"response:{prompt}"}}
                    ]
                },
                request,
            )

        client = VLLMClient(
            base_url="http://localhost:8000",
            model="qwen3-32b",
            max_concurrent=2,
            transport=httpx.MockTransport(handler),
        )
        results = client.batch_generate(["slow prompt", "fast prompt"])
        assert results == ["response:slow prompt", "response:fast prompt"]
        client.close()

    def test_retry_on_timeout(self):
        calls = {"count": 0}

        async def handler(request: httpx.Request) -> httpx.Response:
            calls["count"] += 1
            if calls["count"] == 1:
                raise httpx.ReadTimeout("timeout", request=request)
            return _response_json(
                {
                    "choices": [
                        {"message": {"content": "ok"}}
                    ]
                },
                request,
            )

        client = VLLMClient(
            base_url="http://localhost:8000",
            model="qwen3-32b",
            max_retries=2,
            transport=httpx.MockTransport(handler),
        )
        result = client.generate("prompt")
        assert result == "ok"
        assert calls["count"] == 2
        assert client.last_request_stats is not None
        assert client.last_request_stats.retries == 1
        client.close()
