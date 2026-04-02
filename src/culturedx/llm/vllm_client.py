"""vLLM client using the OpenAI-compatible API."""
from __future__ import annotations

import asyncio
import hashlib
import threading
from pathlib import Path
from typing import Any

import httpx

from culturedx.llm.cache import LLMCache
from culturedx.llm.runtime import LLMRequestStats, SharedLLMHTTPRuntime
import logging

logger = logging.getLogger(__name__)


class VLLMClient:
    """LLM client for vLLM's OpenAI-compatible API.

    Supports:
    - Single and batch generation
    - Structured outputs via response_format with guided_json fallback
    - SQLite response caching
    - Concurrent batch requests with bounded concurrency
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        model: str = "Qwen/Qwen3-32B-AWQ",
        temperature: float = 0.0,
        top_k: int = 1,
        top_p: float = 1.0,
        timeout: int = 300,
        max_tokens: int = 2048,
        cache_path: Path | str | None = None,
        provider: str = "vllm",
        max_concurrent: int = 4,
        disable_thinking: bool = True,
        max_retries: int = 3,
        seed: int | None = None,
        transport: httpx.BaseTransport | httpx.AsyncBaseTransport | None = None,
        observability_hook=None,
        structured_output_mode: str = "auto",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.top_k = top_k
        self.top_p = top_p
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.provider = provider
        self.max_concurrent = max(1, max_concurrent)
        self.disable_thinking = disable_thinking
        self.max_retries = max_retries
        self.seed = seed
        self.structured_output_mode = structured_output_mode
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
        self._event_loop_local = threading.local()
        self._event_loops_lock = threading.Lock()
        self._event_loops: dict[int, asyncio.AbstractEventLoop] = {}

    def _cache_key_input(self, prompt: str, prompt_prefix: str | None = None) -> str:
        if not prompt_prefix:
            key_input = prompt
        else:
            key_input = f"{prompt_prefix}\n\n{prompt}"
        if self.seed is None:
            return key_input
        return f"{key_input}\n\n[seed:{self.seed}]"

    @staticmethod
    def compute_prompt_hash(template_source: str) -> str:
        """Compute SHA-256 hash of prompt template source."""
        return hashlib.sha256(template_source.encode()).hexdigest()[:16]

    def close(self) -> None:
        """Close cache connections and underlying HTTP clients."""
        self._runtime.close()
        self._close_event_loops()
        if self._cache:
            self._cache.close()

    def _get_or_create_event_loop(self) -> asyncio.AbstractEventLoop:
        """Return a persistent event loop for the current thread."""
        loop = getattr(self._event_loop_local, "loop", None)
        if loop is None or loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._event_loop_local.loop = loop
            with self._event_loops_lock:
                self._event_loops[threading.get_ident()] = loop
        return loop

    def _close_event_loops(self) -> None:
        """Close thread-local event loops created for sync access."""
        with self._event_loops_lock:
            loops = list(self._event_loops.values())
            self._event_loops.clear()

        seen_loops: set[int] = set()
        for loop in loops:
            loop_id = id(loop)
            if loop_id in seen_loops or loop.is_closed():
                continue
            seen_loops.add(loop_id)
            try:
                loop.close()
            except RuntimeError:
                logger.debug("Failed to close vLLM event loop cleanly", exc_info=True)

        self._event_loop_local.loop = None

    def _run_sync(self, coro: Any) -> Any:
        """Run a coroutine from sync code using a per-thread event loop."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "VLLMClient sync methods cannot be called from a running event loop; "
                "use async_generate/async_batch_generate instead."
            )

        loop = self._get_or_create_event_loop()
        return loop.run_until_complete(coro)

    def _build_messages(
        self,
        prompt: str,
        prompt_prefix: str | None = None,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if prompt_prefix:
            messages.append({"role": "system", "content": prompt_prefix})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _build_base_body(
        self,
        prompt: str,
        prompt_prefix: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": self._build_messages(prompt, prompt_prefix=prompt_prefix),
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
        }
        if self.seed is not None:
            body["seed"] = self.seed
        if self.disable_thinking:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        return body

    def _build_structured_body(
        self,
        prompt: str,
        json_schema: dict[str, Any],
        prompt_prefix: str | None = None,
        *,
        mode: str,
    ) -> dict[str, Any]:
        body = self._build_base_body(prompt, prompt_prefix=prompt_prefix)
        if mode == "guided_json":
            body["guided_json"] = json_schema
            return body
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "culturedx_output",
                "schema": json_schema,
                "strict": True,
            },
        }
        return body

    def _parse_chat_content(self, response: httpx.Response) -> str:
        data = self._runtime.parse_json_response(response)
        return data["choices"][0]["message"]["content"]

    def _cache_get(
        self,
        prompt_hash: str,
        language: str,
        prompt: str,
        prompt_prefix: str | None,
    ) -> str | None:
        if not self._cache:
            return None
        return self._cache.get(
            self.provider,
            self.model,
            prompt_hash,
            language,
            self._cache_key_input(prompt, prompt_prefix=prompt_prefix),
        )

    def _cache_put(
        self,
        prompt_hash: str,
        language: str,
        prompt: str,
        prompt_prefix: str | None,
        text: str,
    ) -> None:
        if not self._cache:
            return
        self._cache.put(
            self.provider,
            self.model,
            prompt_hash,
            language,
            self._cache_key_input(prompt, prompt_prefix=prompt_prefix),
            text,
        )

    def generate(
        self,
        prompt: str,
        prompt_hash: str = "",
        language: str = "zh",
        json_schema: dict | None = None,
        *,
        prompt_prefix: str | None = None,
    ) -> str:
        if not prompt_hash:
            prompt_hash = self.compute_prompt_hash(prompt)

        cached = self._cache_get(prompt_hash, language, prompt, prompt_prefix)
        if cached is not None:
            self.last_request_stats = LLMRequestStats(
                provider=self.provider,
                model=self.model,
                endpoint="/v1/chat/completions",
                prompt_hash=prompt_hash,
                language=language,
                cache_hit=True,
            )
            return cached

        # Use sync HTTP to avoid asyncio event-loop conflicts under ThreadPoolExecutor.
        base_stats = LLMRequestStats(
            provider=self.provider,
            model=self.model,
            endpoint="/v1/chat/completions",
            prompt_hash=prompt_hash,
            language=language,
        )

        if json_schema is None:
            response = self._runtime.post_json(
                "/v1/chat/completions",
                self._build_base_body(prompt, prompt_prefix=prompt_prefix),
                base_stats,
            )
            text = self._parse_chat_content(response)
            self._cache_put(prompt_hash, language, prompt, prompt_prefix, text)
            self.last_request_stats = base_stats
            return text

        # Structured output with fallback
        structured_mode = self.structured_output_mode
        preferred_modes = ["response_format", "guided_json"]
        if structured_mode == "guided_json":
            preferred_modes = ["guided_json"]
        elif structured_mode == "response_format":
            preferred_modes = ["response_format"]

        last_exc: Exception | None = None
        for mode in preferred_modes:
            try:
                stats = LLMRequestStats(
                    provider=self.provider,
                    model=self.model,
                    endpoint="/v1/chat/completions",
                    prompt_hash=prompt_hash,
                    language=language,
                    structured_output_mode=mode,
                )
                response = self._runtime.post_json(
                    "/v1/chat/completions",
                    self._build_structured_body(
                        prompt,
                        json_schema,
                        prompt_prefix=prompt_prefix,
                        mode=mode,
                    ),
                    stats,
                )
                text = self._parse_chat_content(response)
                self._cache_put(prompt_hash, language, prompt, prompt_prefix, text)
                self.last_request_stats = stats
                return text
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if mode == "response_format" and structured_mode == "auto":
                    status_code = exc.response.status_code
                    body_text = exc.response.text.lower()
                    if status_code in {400, 404, 422} or "response_format" in body_text:
                        logger.info(
                            "Structured output mode=%s rejected (status=%d), "
                            "falling back to guided_json for model=%s",
                            mode, status_code, self.model,
                        )
                        continue
                raise

        assert last_exc is not None
        raise last_exc

    async def async_generate(
        self,
        prompt: str,
        prompt_hash: str = "",
        language: str = "zh",
        json_schema: dict | None = None,
        *,
        prompt_prefix: str | None = None,
    ) -> tuple[str, LLMRequestStats]:
        if not prompt_hash:
            prompt_hash = self.compute_prompt_hash(prompt)

        cached = self._cache_get(prompt_hash, language, prompt, prompt_prefix)
        if cached is not None:
            stats = LLMRequestStats(
                provider=self.provider,
                model=self.model,
                endpoint="/v1/chat/completions",
                prompt_hash=prompt_hash,
                language=language,
                cache_hit=True,
            )
            return cached, stats

        base_stats = LLMRequestStats(
            provider=self.provider,
            model=self.model,
            endpoint="/v1/chat/completions",
            prompt_hash=prompt_hash,
            language=language,
        )

        if json_schema is None:
            response = await self._runtime.apost_json(
                "/v1/chat/completions",
                self._build_base_body(prompt, prompt_prefix=prompt_prefix),
                base_stats,
            )
            text = self._parse_chat_content(response)
            self._cache_put(prompt_hash, language, prompt, prompt_prefix, text)
            return text, base_stats

        # Structured output compatibility shim:
        # Prefer the currently recommended structured_outputs/response_format path
        # and fall back to legacy guided_json if the server rejects it.
        structured_mode = self.structured_output_mode
        preferred_modes = ["response_format", "guided_json"]
        if structured_mode == "guided_json":
            preferred_modes = ["guided_json"]
        elif structured_mode == "response_format":
            preferred_modes = ["response_format"]

        last_exc: Exception | None = None
        for mode in preferred_modes:
            try:
                logger.debug(
                    "Attempting structured output mode=%s for model=%s",
                    mode, self.model,
                )
                stats = LLMRequestStats(
                    provider=self.provider,
                    model=self.model,
                    endpoint="/v1/chat/completions",
                    prompt_hash=prompt_hash,
                    language=language,
                    structured_output_mode=mode,
                )
                response = await self._runtime.apost_json(
                    "/v1/chat/completions",
                    self._build_structured_body(
                        prompt,
                        json_schema,
                        prompt_prefix=prompt_prefix,
                        mode=mode,
                    ),
                    stats,
                )
                text = self._parse_chat_content(response)
                logger.debug(
                    "Structured output succeeded with mode=%s for model=%s",
                    mode, self.model,
                )
                self._cache_put(prompt_hash, language, prompt, prompt_prefix, text)
                return text, stats
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if mode == "response_format" and structured_mode == "auto":
                    status_code = exc.response.status_code
                    body_text = exc.response.text.lower()
                    if status_code in {400, 404, 422} or "response_format" in body_text:
                        logger.info(
                            "Structured output mode=%s rejected (status=%d), "
                            "falling back to guided_json for model=%s",
                            mode, status_code, self.model,
                        )
                        continue
                raise

        assert last_exc is not None
        raise last_exc

    def batch_generate(
        self,
        prompts: list[str],
        prompt_hashes: list[str] | None = None,
        language: str = "zh",
        json_schema: dict | None = None,
        *,
        prompt_prefix: str | None = None,
    ) -> list[str]:
        return self._run_sync(
            self.async_batch_generate(
                prompts,
                prompt_hashes=prompt_hashes,
                language=language,
                json_schema=json_schema,
                prompt_prefix=prompt_prefix,
            )
        )

    async def async_batch_generate(
        self,
        prompts: list[str],
        prompt_hashes: list[str] | None = None,
        language: str = "zh",
        json_schema: dict | None = None,
        *,
        prompt_prefix: str | None = None,
    ) -> list[str]:
        if prompt_hashes is None:
            prompt_hashes = [""] * len(prompts)
        if len(prompt_hashes) != len(prompts):
            raise ValueError("prompt_hashes must match prompts length")

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def _generate_one(idx: int) -> tuple[int, str]:
            async with semaphore:
                text, stats = await self.async_generate(
                    prompts[idx],
                    prompt_hashes[idx],
                    language,
                    json_schema=json_schema,
                    prompt_prefix=prompt_prefix,
                )
                self.last_request_stats = stats
                return idx, text

        results = await asyncio.gather(*(_generate_one(i) for i in range(len(prompts))))
        ordered = ["" for _ in prompts]
        for idx, text in results:
            ordered[idx] = text
        return ordered
