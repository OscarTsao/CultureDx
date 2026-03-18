"""Retriever factory: create retrievers from config."""
from __future__ import annotations

from culturedx.core.config import RetrieverConfig
from culturedx.evidence.retriever import BaseRetriever, MockRetriever


def create_retriever(config: RetrieverConfig) -> BaseRetriever:
    """Create a retriever instance from config.

    Args:
        config: RetrieverConfig with name and parameters.

    Returns:
        Configured retriever instance.

    Raises:
        ValueError: If retriever name is unknown.
    """
    if config.name == "mock":
        return MockRetriever()
    if config.name == "bge-m3":
        from culturedx.evidence.retriever import BGEM3Retriever

        return BGEM3Retriever(
            model_id=config.model_id or "BAAI/bge-m3",
            device=config.device,
            cache_dir=config.cache_dir or None,
        )
    raise ValueError(
        f"Unknown retriever '{config.name}'. Available: mock, bge-m3"
    )
