"""Base LLM client protocol."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class BaseLLMClient(Protocol):
    """Protocol for LLM clients. Supports both Ollama and vLLM backends."""

    model: str

    def generate(
        self,
        prompt: str,
        prompt_hash: str = "",
        language: str = "zh",
        json_schema: dict | None = None,
        *,
        prompt_prefix: str | None = None,
    ) -> str:
        """Generate a single response."""
        ...

    def batch_generate(
        self,
        prompts: list[str],
        prompt_hashes: list[str] | None = None,
        language: str = "zh",
        json_schema: dict | None = None,
        *,
        prompt_prefix: str | None = None,
    ) -> list[str]:
        """Generate responses for multiple prompts (may be parallel)."""
        ...

    def compute_prompt_hash(self, template_source: str) -> str:
        """Compute hash of a prompt template."""
        ...
