"""Canonical artifact models for experiment runs."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

from culturedx.core.models import ClinicalCase, DiagnosisResult, EvidenceBrief, FailureInfo

ARTIFACT_SCHEMA_VERSION = "v1"


def _normalize(value: Any) -> Any:
    """Convert nested dataclasses into JSON-stable plain values."""
    if is_dataclass(value):
        return {k: _normalize(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    return value


def stable_fingerprint(payload: Any) -> str:
    """Hash JSON-serializable payloads deterministically."""
    normalized = _normalize(payload)
    encoded = json.dumps(normalized, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


@dataclass
class RunManifest:
    """Top-level run metadata."""

    schema_version: str = ARTIFACT_SCHEMA_VERSION
    run_id: str = ""
    created_at: str = ""
    git_hash: str = ""
    mode: str = ""
    dataset: str = ""
    num_cases: int = 0
    model_name: str = ""
    config_fingerprint: str = ""
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class PredictionRecord:
    """Canonical per-case prediction artifact."""

    schema_version: str = ARTIFACT_SCHEMA_VERSION
    run_id: str = ""
    case_id: str = ""
    order_index: int = 0
    dataset: str = ""
    gold_diagnoses: list[str] = field(default_factory=list)
    primary_diagnosis: str | None = None
    comorbid_diagnoses: list[str] = field(default_factory=list)
    confidence: float = 0.0
    decision: str = ""
    mode: str = ""
    model_name: str = ""
    prompt_hash: str = ""
    language_used: str = ""
    routing_mode: str = ""
    scope_policy: str = ""
    candidate_disorders: list[str] = field(default_factory=list)
    decision_trace: dict[str, Any] | None = None
    stage_timings: dict[str, float] = field(default_factory=dict)
    failures: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FailureRecord:
    """Machine-readable failure event emitted during a run."""

    schema_version: str = ARTIFACT_SCHEMA_VERSION
    run_id: str = ""
    case_id: str = ""
    source: str = ""
    code: str = ""
    stage: str = ""
    message: str = ""
    recoverable: bool = False
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class StageTimingRecord:
    """Per-stage timing row."""

    schema_version: str = ARTIFACT_SCHEMA_VERSION
    run_id: str = ""
    case_id: str = ""
    source: str = ""
    stage: str = ""
    duration_sec: float = 0.0


@dataclass
class MetricsSummary:
    """Canonical metrics artifact for a run."""

    schema_version: str = ARTIFACT_SCHEMA_VERSION
    run_id: str = ""
    dataset: str = ""
    num_cases: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)
    slice_metrics: list[dict[str, Any]] = field(default_factory=list)


def build_prediction_record(
    run_id: str,
    order_index: int,
    case: ClinicalCase,
    result: DiagnosisResult,
) -> PredictionRecord:
    """Convert a diagnosis result into the canonical prediction schema."""
    failure_payload = [_normalize(f) for f in result.failures]
    return PredictionRecord(
        run_id=run_id,
        case_id=case.case_id,
        order_index=order_index,
        dataset=case.dataset,
        gold_diagnoses=list(case.diagnoses),
        primary_diagnosis=result.primary_diagnosis,
        comorbid_diagnoses=list(result.comorbid_diagnoses),
        confidence=result.confidence,
        decision=result.decision,
        mode=result.mode,
        model_name=result.model_name,
        prompt_hash=result.prompt_hash,
        language_used=result.language_used,
        routing_mode=result.routing_mode,
        scope_policy=result.scope_policy,
        candidate_disorders=list(result.candidate_disorders),
        decision_trace=_normalize(result.decision_trace),
        stage_timings=dict(result.stage_timings),
        failures=failure_payload,
    )


def build_failure_records(
    run_id: str,
    case_id: str,
    evidence: EvidenceBrief | None,
    result: DiagnosisResult,
) -> list[FailureRecord]:
    """Flatten evidence + diagnosis failures into canonical rows."""
    records: list[FailureRecord] = []
    seen: set[tuple[str, str, str, bool, str]] = set()
    for source, failures in (
        ("evidence", evidence.failures if evidence else []),
        ("diagnosis", result.failures),
    ):
        for failure in failures:
            key = (
                str(failure.code),
                failure.stage,
                failure.message,
                failure.recoverable,
                json.dumps(_normalize(failure.details), ensure_ascii=False, sort_keys=True),
            )
            if key in seen:
                continue
            seen.add(key)
            records.append(
                FailureRecord(
                    run_id=run_id,
                    case_id=case_id,
                    source=source,
                    code=str(failure.code),
                    stage=failure.stage,
                    message=failure.message,
                    recoverable=failure.recoverable,
                    details=_normalize(failure.details),
                )
            )
    return records


def build_stage_timing_records(
    run_id: str,
    case_id: str,
    evidence: EvidenceBrief | None,
    result: DiagnosisResult,
) -> list[StageTimingRecord]:
    """Flatten stage timing dicts into row-oriented records."""
    records: list[StageTimingRecord] = []
    for source, stage_timings in (
        ("evidence", evidence.stage_timings if evidence else {}),
        ("diagnosis", result.stage_timings),
    ):
        for stage, duration in stage_timings.items():
            records.append(
                StageTimingRecord(
                    run_id=run_id,
                    case_id=case_id,
                    source=source,
                    stage=stage,
                    duration_sec=float(duration),
                )
            )
    return records


def serialize_dataclass(instance: Any) -> dict[str, Any]:
    """Serialize a dataclass to a plain JSON-ready dict."""
    return _normalize(instance)
