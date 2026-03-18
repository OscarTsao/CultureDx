# src/culturedx/data/adapters/base.py
"""Base dataset adapter interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from culturedx.core.models import ClinicalCase


class BaseDatasetAdapter(ABC):
    """Abstract base for all dataset adapters."""

    def __init__(self, data_path: str | Path, **kwargs) -> None:
        self.data_path = Path(data_path)

    @abstractmethod
    def load(self, split: str | None = None) -> list[ClinicalCase]:
        """Load and normalize dataset to ClinicalCase list."""
        ...
