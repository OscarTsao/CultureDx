"""Ollama LLM client with caching, pooling, and prompt hashing."""
from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Any

from culturedx.llm.cache import LLMCache
from culturedx.llm.runtime import LLMRequestStats, SharedLLMHTTPRuntime

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for Ollama API with response caching."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen3:14b",
        temperature: float = 0.0,
        top_k: int = 1,
        timeout: int = 300,
        cache_path: str | Path | None = None,
        provider: str = "ollama",
        disable_thinking: bool = True,
        max_retries: int = 3,
        max_concurrent: int = 4,
        transport=None,
        observability_hook=None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.provider = provider
        self.temperature = temperature
        self.top_k = top_k
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_concurrent = max(1, max_concurrent)
        self.disable_thinking = disable_thinking
        self._cache = LLMCache(cache_path) if cache_path else None
        self._runtime = SharedLLMHTTPRuntime(
            base_url=self.base_url,
            timeout=self.timeout,
            max_concurrent=self.max_concurrent,
            max_retries=self.max_retries,
            transport=transport,
            headers={"Content-Type": "application/json"},
            observability_hook=observability_hook,
        )
        self.last_request_stats: LLMRequestStats | None = None

    def close(self) -> None:
        """Close the runtime and cache connections."""
        self._runtime.close()
        if self._cache:
            self._cache.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @staticmethod
    def compute_prompt_hash(prompt_text: str) -> str:
        """SHA-256 hash of a prompt template for cache keying."""
        return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:16]

    def _build_prompt(self, prompt: str, prompt_prefix: str | None = None) -> str:
        if not prompt_prefix:
            return prompt
        return f"{prompt_prefix}\n\n{prompt}"

    def _build_request_body(
        self,
        prompt: str,
        prompt_prefix: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "prompt": self._build_prompt(prompt, prompt_prefix=prompt_prefix),
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "top_k": self.top_k,
            },
        }
        if self.disable_thinking:
            body["think"] = False
        return body

    def generate(
        self,
        prompt: str,
        prompt_hash: str = "",
        language: str = "zh",
        json_schema: dict | None = None,
        *,
        prompt_prefix: str | None = None,
    ) -> str:
        """Send prompt to Ollama and return response text."""
        if not prompt_hash:
            prompt_hash = self.compute_prompt_hash(prompt)

        if json_schema is not None:
            logger.warning("OllamaClient does not support json_schema; parameter ignored")

        cache_input = self._build_prompt(prompt, prompt_prefix=prompt_prefix)
        if self._cache:
            cached = self._cache.get(
                self.provider, self.model, prompt_hash, language, cache_input
            )
            if cached is not None:
                self.last_request_stats = LLMRequestStats(
                    provider=self.provider,
                    model=self.model,
                    endpoint="/api/generate",
                    prompt_hash=prompt_hash,
                    language=language,
                    cache_hit=True,
                )
                return cached

        stats = LLMRequestStats(
            provider=self.provider,
            model=self.model,
            endpoint="/api/generate",
            prompt_hash=prompt_hash,
            language=language,
            structured_output_mode=None,
        )
        response = self._runtime.post_json(
            "/api/generate",
            self._build_request_body(prompt, prompt_prefix=prompt_prefix),
            stats,
        )
        data = self._runtime.parse_json_response(response)
        text = data["response"]

        if self._cache:
            self._cache.put(
                self.provider, self.model, prompt_hash, language, cache_input, text
            )
        self.last_request_stats = stats
        return text

    async def async_generate(
        self,
        prompt: str,
        prompt_hash: str = "",
        language: str = "zh",
        json_schema: dict | None = None,
        *,
        prompt_prefix: str | None = None,
    ) -> str:
        """Async variant for callers that want to manage their own event loop."""
        if not prompt_hash:
            prompt_hash = self.compute_prompt_hash(prompt)

        cache_input = self._build_prompt(prompt, prompt_prefix=prompt_prefix)
        if self._cache:
            cached = self._cache.get(
                self.provider, self.model, prompt_hash, language, cache_input
            )
            if cached is not None:
                self.last_request_stats = LLMRequestStats(
                    provider=self.provider,
                    model=self.model,
                    endpoint="/api/generate",
                    prompt_hash=prompt_hash,
                    language=language,
                    cache_hit=True,
                )
                return cached

        stats = LLMRequestStats(
            provider=self.provider,
            model=self.model,
            endpoint="/api/generate",
            prompt_hash=prompt_hash,
            language=language,
            structured_output_mode=None,
        )
        response = await self._runtime.apost_json(
            "/api/generate",
            self._build_request_body(prompt, prompt_prefix=prompt_prefix),
            stats,
        )
        data = self._runtime.parse_json_response(response)
        text = data["response"]

        if self._cache:
            self._cache.put(
                self.provider, self.model, prompt_hash, language, cache_input, text
            )
        self.last_request_stats = stats
        return text

    def batch_generate(
        self,
        prompts: list[str],
        prompt_hashes: list[str] | None = None,
        language: str = "zh",
        *,
        prompt_prefix: str | None = None,
    ) -> list[str]:
        """Generate responses for multiple prompts using the async runtime."""
        return asyncio.run(
            self.async_batch_generate(
                prompts,
                prompt_hashes=prompt_hashes,
                language=language,
                prompt_prefix=prompt_prefix,
            )
        )

    async def async_batch_generate(
        self,
        prompts: list[str],
        prompt_hashes: list[str] | None = None,
        language: str = "zh",
        *,
        prompt_prefix: str | None = None,
    ) -> list[str]:
        """Async batch generation with bounded concurrency and stable ordering."""
        if prompt_hashes is None:
            prompt_hashes = [""] * len(prompts)
        if len(prompt_hashes) != len(prompts):
            raise ValueError("prompt_hashes must match prompts length")

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def _generate_one(idx: int) -> tuple[int, str]:
            async with semaphore:
                text = await self.async_generate(
                    prompts[idx],
                    prompt_hashes[idx],
                    language,
                    prompt_prefix=prompt_prefix,
                )
                return idx, text

        results = await asyncio.gather(*(_generate_one(i) for i in range(len(prompts))))
        ordered = ["" for _ in prompts]
        for idx, text in results:
            ordered[idx] = text
        return ordered
