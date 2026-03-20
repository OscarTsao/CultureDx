"""vLLM client using OpenAI-compatible API."""
from __future__ import annotations

import hashlib
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

from culturedx.llm.cache import LLMCache

logger = logging.getLogger(__name__)


class VLLMClient:
    """LLM client for vLLM's OpenAI-compatible API.

    Supports:
    - Single and batch generation
    - Guided JSON decoding (structured output)
    - SQLite response caching
    - Concurrent batch requests
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        model: str = "Qwen/Qwen3-32B-AWQ",
        temperature: float = 0.0,
        top_k: int = 1,
        top_p: float = 1.0,
        timeout: int = 300,
        max_tokens: int = 1024,
        cache_path: Path | str | None = None,
        provider: str = "vllm",
        max_concurrent: int = 4,
        disable_thinking: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.top_k = top_k
        self.top_p = top_p
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.provider = provider
        self.max_concurrent = max_concurrent
        self.disable_thinking = disable_thinking
        self._cache = LLMCache(cache_path) if cache_path else None

    def generate(
        self,
        prompt: str,
        prompt_hash: str = "",
        language: str = "zh",
        json_schema: dict | None = None,
    ) -> str:
        """Generate a single response via vLLM OpenAI-compatible API."""
        # Check cache
        input_hash = hashlib.sha256(prompt.encode()).hexdigest()
        if self._cache:
            cached = self._cache.get(
                self.provider, self.model, prompt_hash, language, input_hash
            )
            if cached is not None:
                return cached

        # Build request
        messages = [{"role": "user", "content": prompt}]
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
        }
        if self.disable_thinking:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        if json_schema:
            body["guided_json"] = json_schema

        # Call with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = httpx.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=body,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()
                text = data["choices"][0]["message"]["content"]

                # Cache result
                if self._cache:
                    self._cache.put(
                        self.provider, self.model, prompt_hash,
                        language, input_hash, text,
                    )
                return text

            except (httpx.TimeoutException, httpx.HTTPStatusError, ConnectionError) as e:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        "vLLM call failed (attempt %d/%d): %s. Retrying in %ds...",
                        attempt + 1, max_retries, str(e), wait,
                    )
                    time.sleep(wait)
                else:
                    logger.error("vLLM call failed after %d attempts: %s", max_retries, str(e))
                    raise

    def batch_generate(
        self,
        prompts: list[str],
        prompt_hashes: list[str] | None = None,
        language: str = "zh",
        json_schema: dict | None = None,
    ) -> list[str]:
        """Generate responses for multiple prompts concurrently."""
        if prompt_hashes is None:
            prompt_hashes = [""] * len(prompts)

        results = [None] * len(prompts)

        def _gen(idx: int) -> tuple[int, str]:
            return idx, self.generate(
                prompts[idx], prompt_hashes[idx], language, json_schema
            )

        max_workers = min(len(prompts), self.max_concurrent)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_gen, i): i for i in range(len(prompts))}
            for future in as_completed(futures):
                idx, response = future.result()
                results[idx] = response

        return results

    def compute_prompt_hash(self, template_source: str) -> str:
        """Compute SHA-256 hash of prompt template source."""
        return hashlib.sha256(template_source.encode()).hexdigest()[:16]

    def close(self) -> None:
        """Close cache connection."""
        if self._cache:
            self._cache.close()
