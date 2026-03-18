# src/culturedx/core/models.py
"""Core data models for CultureDx."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Turn:
    """A single dialogue turn in a clinical transcript."""

    speaker: str
    text: str
    turn_id: int

    @property
    def is_patient(self) -> bool:
        return self.speaker.lower() in ("patient", "participant", "p")


@dataclass
class ClinicalCase:
    """A normalized clinical case from any dataset."""

    case_id: str
    transcript: list[Turn]
    language: str  # "zh" | "en"
    dataset: str
    transcript_format: str = "dialogue"
    coding_system: str = "icd10"

    # Ground truth (evaluation only)
    diagnoses: list[str] = field(default_factory=list)
    severity: dict | None = None
    comorbid: bool = False
    suicide_risk: int | None = None
    metadata: dict | None = None

    def patient_turns(self) -> list[Turn]:
        """Return only patient/participant turns."""
        return [t for t in self.transcript if t.is_patient]


@dataclass
class SymptomSpan:
    """An extracted symptom mention from the transcript."""

    text: str
    turn_id: int
    symptom_type: str
    mapped_criterion: str | None = None


@dataclass
class CriterionEvidence:
    """Evidence collected for a single diagnostic criterion."""

    criterion_id: str
    spans: list[SymptomSpan] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class EvidenceBrief:
    """Assembled evidence brief for a case, per criterion per disorder."""

    case_id: str
    language: str
    criteria_evidence: list[CriterionEvidence] = field(default_factory=list)


@dataclass
class CriterionResult:
    """Result of checking a single criterion."""

    criterion_id: str
    status: Literal["met", "not_met", "insufficient_evidence"]
    evidence: str | None = None
    confidence: float = 0.0


@dataclass
class CheckerOutput:
    """Output from a criterion checker agent for one disorder."""

    disorder: str
    criteria: list[CriterionResult] = field(default_factory=list)
    criteria_met_count: int = 0
    criteria_required: int = 0


@dataclass
class DiagnosisResult:
    """Final diagnosis output from any MAS mode."""

    case_id: str
    primary_diagnosis: str | None
    comorbid_diagnoses: list[str] = field(default_factory=list)
    confidence: float = 0.0
    decision: Literal["diagnosis", "abstain"] = "diagnosis"
    criteria_results: list[CheckerOutput] = field(default_factory=list)
    mode: str = ""
    model_name: str = ""
    prompt_hash: str = ""
    language_used: str = ""  # "zh" or "en"
