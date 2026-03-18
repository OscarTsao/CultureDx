# src/culturedx/llm/client.py
"""Ollama LLM client with caching and prompt hashing."""
from __future__ import annotations

import hashlib
from pathlib import Path

import httpx

from culturedx.llm.cache import LLMCache


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
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.provider = provider
        self.temperature = temperature
        self.top_k = top_k
        self.timeout = timeout
        self._cache = LLMCache(cache_path) if cache_path else None

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
    ) -> str:
        """Send prompt to Ollama and return response text."""
        if not prompt_hash:
            prompt_hash = self.compute_prompt_hash(prompt)

        # Check cache
        if self._cache:
            cached = self._cache.get(self.provider, self.model, prompt_hash, language, prompt)
            if cached is not None:
                return cached

        # Call Ollama
        response = httpx.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "top_k": self.top_k,
                },
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        text = response.json()["response"]

        # Store in cache
        if self._cache:
            self._cache.put(self.provider, self.model, prompt_hash, language, prompt, text)

        return text
