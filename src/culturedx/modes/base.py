# src/culturedx/modes/base.py
"""Base mode orchestrator interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from culturedx.core.models import ClinicalCase, DiagnosisResult, EvidenceBrief


class BaseModeOrchestrator(ABC):
    """Abstract base for all MAS mode orchestrators."""

    @abstractmethod
    def diagnose(
        self, case: ClinicalCase, evidence: EvidenceBrief | None = None
    ) -> DiagnosisResult:
        ...
