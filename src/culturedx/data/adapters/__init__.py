"""Dataset adapter registry."""
from __future__ import annotations

from pathlib import Path

from culturedx.data.adapters.base import BaseDatasetAdapter
from culturedx.data.adapters.edaic import EDAICAdapter
from culturedx.data.adapters.lingxidiag16k import LingxiDiag16kAdapter
from culturedx.data.adapters.mdd5k import MDD5kAdapter, MDD5kRawAdapter
from culturedx.data.adapters.pdch import PDCHAdapter

_REGISTRY: dict[str, type[BaseDatasetAdapter]] = {
    "lingxidiag16k": LingxiDiag16kAdapter,
    "mdd5k": MDD5kAdapter,
    "mdd5k_raw": MDD5kRawAdapter,
    "pdch": PDCHAdapter,  # NOT USED: dialogue data unavailable (restricted access)
    "edaic": EDAICAdapter,
}


def get_adapter(name: str, data_path: str | Path, **kwargs) -> BaseDatasetAdapter:
    """Create a dataset adapter by name.

    Args:
        name: Adapter name (e.g., "lingxidiag16k", "mdd5k_raw", "pdch").
        data_path: Path to dataset files.
        **kwargs: Additional adapter-specific arguments.

    Returns:
        Configured adapter instance.

    Raises:
        ValueError: If adapter name is not registered.
    """
    cls = _REGISTRY.get(name)
    if cls is None:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise ValueError(f"Unknown adapter '{name}'. Available: {available}")
    return cls(data_path=data_path, **kwargs)


def list_adapters() -> list[str]:
    """Return list of registered adapter names."""
    return sorted(_REGISTRY.keys())
