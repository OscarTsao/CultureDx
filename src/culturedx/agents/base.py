# src/culturedx/agents/base.py
"""Base agent interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentInput:
    """Input to any agent."""

    transcript_text: str
    evidence: dict | None = None
    language: str = "zh"
    extra: dict = field(default_factory=dict)


@dataclass
class AgentOutput:
    """Output from any agent."""

    raw_response: str = ""
    parsed: dict | None = None
    model_name: str = ""
    prompt_hash: str = ""


class BaseAgent(ABC):
    """Abstract base for all agents."""

    @abstractmethod
    def run(self, input: AgentInput) -> AgentOutput:
        ...
