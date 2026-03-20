# src/culturedx/llm/client.py
"""Ollama LLM client with caching and prompt hashing."""
from __future__ import annotations

import logging
import time
import hashlib
from pathlib import Path

import httpx

from culturedx.llm.cache import LLMCache

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
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.provider = provider
        self.temperature = temperature
        self.top_k = top_k
        self.timeout = timeout
        self._cache = LLMCache(cache_path) if cache_path else None
        self.disable_thinking = disable_thinking

    def close(self) -> None:
        """Close the cache connection."""
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

    def generate(
        self,
        prompt: str,
        prompt_hash: str = "",
        language: str = "zh",
        json_schema: dict | None = None,
    ) -> str:
        """Send prompt to Ollama and return response text."""
        if not prompt_hash:
            prompt_hash = self.compute_prompt_hash(prompt)

        # Check cache
        if self._cache:
            cached = self._cache.get(self.provider, self.model, prompt_hash, language, prompt)
            if cached is not None:
                return cached

        request_body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "top_k": self.top_k,
            },
        }
        if self.disable_thinking:
            request_body["think"] = False

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = httpx.post(
                    f"{self.base_url}/api/generate",
                    json=request_body,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                text = response.json()["response"]
                break  # success
            except (httpx.TimeoutException, httpx.HTTPStatusError, ConnectionError) as e:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        "LLM call failed (attempt %d/%d): %s. Retrying in %ds...",
                        attempt + 1, max_retries, str(e), wait,
                    )
                    time.sleep(wait)
                else:
                    logger.error("LLM call failed after %d attempts: %s", max_retries, str(e))
                    raise

        # Store in cache
        if self._cache:
            self._cache.put(self.provider, self.model, prompt_hash, language, prompt, text)

        return text

    def batch_generate(
        self,
        prompts: list[str],
        prompt_hashes: list[str] | None = None,
        language: str = "zh",
    ) -> list[str]:
        """Generate responses for multiple prompts using ThreadPoolExecutor."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if prompt_hashes is None:
            prompt_hashes = [""] * len(prompts)

        results = [None] * len(prompts)

        def _gen(idx: int) -> tuple[int, str]:
            return idx, self.generate(prompts[idx], prompt_hashes[idx], language)

        max_workers = min(len(prompts), 4)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_gen, i): i for i in range(len(prompts))}
            for future in as_completed(futures):
                idx, response = future.result()
                results[idx] = response

        return results
