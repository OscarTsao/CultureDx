"""LLM client module."""
from __future__ import annotations

from pathlib import Path

from culturedx.llm.base import BaseLLMClient
from culturedx.llm.cache import LLMCache
from culturedx.llm.client import OllamaClient


def create_llm_client(
    provider: str = "ollama",
    base_url: str = "http://localhost:11434",
    model: str = "qwen3:14b",
    temperature: float = 0.0,
    top_k: int = 1,
    timeout: int = 300,
    cache_path: Path | str | None = None,
    disable_thinking: bool = True,
    max_concurrent: int = 4,
) -> BaseLLMClient:
    """Create an LLM client based on provider config."""
    if provider == "vllm":
        from culturedx.llm.vllm_client import VLLMClient
        return VLLMClient(
            base_url=base_url,
            model=model,
            temperature=temperature,
            top_k=top_k,
            timeout=timeout,
            cache_path=cache_path,
            provider=provider,
            max_concurrent=max_concurrent,
            disable_thinking=disable_thinking,
        )
    return OllamaClient(
        base_url=base_url,
        model=model,
        temperature=temperature,
        top_k=top_k,
        timeout=timeout,
        cache_path=cache_path,
        provider=provider,
        disable_thinking=disable_thinking,
    )


__all__ = [
    "BaseLLMClient",
    "LLMCache",
    "OllamaClient",
    "create_llm_client",
]
