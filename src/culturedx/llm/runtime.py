"""Shared HTTP runtime helpers for CultureDx LLM clients."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
import logging
import threading
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})


@dataclass
class LLMRequestStats:
    """Lightweight observability record for a single request."""

    provider: str
    model: str
    endpoint: str
    prompt_hash: str
    language: str
    attempts: int = 0
    retries: int = 0
    duration_sec: float = 0.0
    cache_hit: bool = False
    status_code: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    structured_output_mode: str | None = None
    batch_index: int | None = None
    request_tags: dict[str, str] = field(default_factory=dict)


@dataclass
class _AsyncClientState:
    """Per-loop async client state for thread-safe async HTTP access."""

    loop: asyncio.AbstractEventLoop
    client: httpx.AsyncClient


class SharedLLMHTTPRuntime:
    """Pooled sync/async HTTP runtime shared by Ollama and vLLM clients."""

    def __init__(
        self,
        base_url: str,
        timeout: int,
        max_concurrent: int,
        max_retries: int = 3,
        transport: httpx.BaseTransport | httpx.AsyncBaseTransport | None = None,
        limits: httpx.Limits | None = None,
        headers: dict[str, str] | None = None,
        observability_hook: Callable[[LLMRequestStats], None] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_concurrent = max(1, max_concurrent)
        self.max_retries = max(1, max_retries)
        self.transport = transport
        self.limits = limits or httpx.Limits(
            max_connections=max(2, self.max_concurrent * 2),
            max_keepalive_connections=max(1, self.max_concurrent),
        )
        self.headers = headers or {}
        self.observability_hook = observability_hook
        self._sync_client: httpx.Client | None = None
        self._async_local = threading.local()
        self._async_client_lock = threading.Lock()
        self._async_client_states: dict[tuple[int, int], _AsyncClientState] = {}

    def _sync(self) -> httpx.Client:
        if self._sync_client is None:
            self._sync_client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
                limits=self.limits,
                headers=self.headers,
            )
        return self._sync_client

    async def _async(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        state = getattr(self._async_local, "state", None)
        if (
            state is None
            or state.loop is not loop
            or state.loop.is_closed()
        ):
            client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
                limits=self.limits,
                headers=self.headers,
            )
            state = _AsyncClientState(loop=loop, client=client)
            self._async_local.state = state
            with self._async_client_lock:
                self._async_client_states[(threading.get_ident(), id(loop))] = state
        return state.client

    @staticmethod
    def _close_async_client_sync(client: httpx.AsyncClient) -> None:
        errors: list[BaseException] = []

        def _runner() -> None:
            try:
                asyncio.run(client.aclose())
            except BaseException as exc:  # pragma: no cover - best-effort cleanup
                errors.append(exc)

        closer = threading.Thread(
            target=_runner,
            name="culturedx-async-client-close",
            daemon=True,
        )
        closer.start()
        closer.join()
        if errors:
            raise errors[0]

    def close(self) -> None:
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None

        with self._async_client_lock:
            states = list(self._async_client_states.values())
            self._async_client_states.clear()

        seen_clients: set[int] = set()
        for state in states:
            client_id = id(state.client)
            if client_id in seen_clients:
                continue
            seen_clients.add(client_id)
            self._close_async_client_sync(state.client)

        self._async_local.state = None

    async def aclose(self) -> None:
        with self._async_client_lock:
            states = list(self._async_client_states.values())
            self._async_client_states.clear()

        seen_clients: set[int] = set()
        for state in states:
            client_id = id(state.client)
            if client_id in seen_clients:
                continue
            seen_clients.add(client_id)
            await state.client.aclose()

        self._async_local.state = None
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None

    def _emit(self, stats: LLMRequestStats) -> None:
        if self.observability_hook is not None:
            try:
                self.observability_hook(stats)
            except Exception:
                logger.debug("LLM observability hook failed", exc_info=True)

    @staticmethod
    def _should_retry_status(status_code: int) -> bool:
        return status_code in RETRYABLE_STATUS_CODES

    @staticmethod
    def _error_name(exc: Exception) -> str:
        return exc.__class__.__name__

    def _sync_post_json(
        self,
        endpoint: str,
        payload: dict[str, Any],
        stats: LLMRequestStats,
    ) -> httpx.Response:
        client = self._sync()
        start = time.monotonic()
        for attempt in range(1, self.max_retries + 1):
            stats.attempts = attempt
            try:
                response = client.post(endpoint, json=payload)
                stats.status_code = response.status_code
                if self._should_retry_status(response.status_code):
                    raise httpx.HTTPStatusError(
                        f"Retryable status {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                stats.duration_sec = time.monotonic() - start
                self._emit(stats)
                return response
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                stats.error_type = self._error_name(exc)
                stats.error_message = str(exc)
                if isinstance(exc, httpx.HTTPStatusError):
                    status_code = exc.response.status_code
                    stats.status_code = status_code
                    retryable = self._should_retry_status(status_code)
                else:
                    retryable = True
                if retryable and attempt < self.max_retries:
                    stats.retries += 1
                    wait = 2 ** (attempt - 1)
                    logger.warning(
                        "LLM request failed (%s attempt %d/%d): %s. Retrying in %ds...",
                        stats.endpoint,
                        attempt,
                        self.max_retries,
                        exc,
                        wait,
                    )
                    time.sleep(wait)
                    continue
                stats.duration_sec = time.monotonic() - start
                self._emit(stats)
                raise

    async def _async_post_json(
        self,
        endpoint: str,
        payload: dict[str, Any],
        stats: LLMRequestStats,
    ) -> httpx.Response:
        client = await self._async()
        start = time.monotonic()
        for attempt in range(1, self.max_retries + 1):
            stats.attempts = attempt
            try:
                response = await client.post(endpoint, json=payload)
                stats.status_code = response.status_code
                if self._should_retry_status(response.status_code):
                    raise httpx.HTTPStatusError(
                        f"Retryable status {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                stats.duration_sec = time.monotonic() - start
                self._emit(stats)
                return response
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                stats.error_type = self._error_name(exc)
                stats.error_message = str(exc)
                if isinstance(exc, httpx.HTTPStatusError):
                    status_code = exc.response.status_code
                    stats.status_code = status_code
                    retryable = self._should_retry_status(status_code)
                else:
                    retryable = True
                if retryable and attempt < self.max_retries:
                    stats.retries += 1
                    wait = 2 ** (attempt - 1)
                    logger.warning(
                        "LLM request failed (%s attempt %d/%d): %s. Retrying in %ds...",
                        stats.endpoint,
                        attempt,
                        self.max_retries,
                        exc,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                stats.duration_sec = time.monotonic() - start
                self._emit(stats)
                raise

    def post_json(
        self,
        endpoint: str,
        payload: dict[str, Any],
        stats: LLMRequestStats,
    ) -> httpx.Response:
        return self._sync_post_json(endpoint, payload, stats)

    async def apost_json(
        self,
        endpoint: str,
        payload: dict[str, Any],
        stats: LLMRequestStats,
    ) -> httpx.Response:
        return await self._async_post_json(endpoint, payload, stats)

    @staticmethod
    def parse_json_response(response: httpx.Response) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:
            raise ValueError("LLM response body was not valid JSON") from exc
