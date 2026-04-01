"""Dataset schema and I/O helpers for the somatization benchmark."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from culturedx.core.models import ClinicalCase, SymptomSpan

SomatizationExpressionType = Literal[
    "direct_symptom",
    "somatized_expression",
    "metaphorical_or_ambiguous",
    "negated",
    "historical_past",
    "family_or_other_person",
    "insufficient_context",
]
SomatizationDatasetSplit = Literal[
    "train",
    "val",
    "test",
    "annotation_pool",
    "review_pool",
    "gold",
]


def build_somatization_example_id(
    text: str,
    span_text: str | None = None,
    source_dataset: str = "",
    source_id: str = "",
    span_start: int | None = None,
    span_end: int | None = None,
) -> str:
    """Build a deterministic ID from stable example attributes."""
    parts = [
        source_dataset.strip(),
        source_id.strip(),
        str(span_start) if span_start is not None else "",
        str(span_end) if span_end is not None else "",
        span_text or "",
        text,
    ]
    digest = hashlib.sha1("||".join(parts).encode("utf-8")).hexdigest()[:12]
    prefix = source_dataset or "somat"
    return f"{prefix}-{digest}"


class SomatizationBenchmarkExample(BaseModel):
    """Canonical annotation/example schema for the somatization benchmark."""

    model_config = ConfigDict(extra="forbid")

    example_id: str = ""
    split: SomatizationDatasetSplit = "annotation_pool"
    text: str
    span_text: str | None = None
    span_start: int | None = None
    span_end: int | None = None
    normalized_concept: str | None = None
    candidate_criterion_ids: list[str] = Field(default_factory=list)
    disorder_relevance: list[str] = Field(default_factory=list)
    expression_type: SomatizationExpressionType
    annotation_confidence: float | None = None
    annotator_notes: str | None = None
    source_dataset: str = ""
    source_id: str = ""
    source_turn_id: int | None = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    language: str = "zh"
    locale: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must be non-empty")
        return value

    @field_validator("annotation_confidence")
    @classmethod
    def _validate_confidence(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if not 0.0 <= value <= 1.0:
            raise ValueError("annotation_confidence must be between 0 and 1")
        return float(value)

    @field_validator("candidate_criterion_ids", "disorder_relevance")
    @classmethod
    def _dedupe_lists(cls, value: list[str]) -> list[str]:
        deduped: list[str] = []
        seen = set()
        for item in value:
            cleaned = item.strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            deduped.append(cleaned)
        return deduped

    @model_validator(mode="after")
    def _validate_offsets_and_ids(self) -> "SomatizationBenchmarkExample":
        if (self.span_start is None) != (self.span_end is None):
            raise ValueError("span_start and span_end must both be set or both be null")
        if self.span_start is not None and self.span_end is not None:
            if self.span_start < 0 or self.span_end <= self.span_start:
                raise ValueError("invalid span offsets")
            if self.span_end > len(self.text):
                raise ValueError("span_end exceeds text length")
            if self.span_text is None:
                object.__setattr__(self, "span_text", self.text[self.span_start : self.span_end])
        if self.span_text is not None and not self.span_text.strip():
            raise ValueError("span_text must be non-empty when provided")
        if not self.example_id:
            object.__setattr__(
                self,
                "example_id",
                build_somatization_example_id(
                    text=self.text,
                    span_text=self.span_text,
                    source_dataset=self.source_dataset,
                    source_id=self.source_id,
                    span_start=self.span_start,
                    span_end=self.span_end,
                ),
            )
        return self


class SomatizationDataset(BaseModel):
    """Container for validated somatization benchmark examples."""

    model_config = ConfigDict(extra="forbid")

    examples: list[SomatizationBenchmarkExample] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_example_ids(self) -> "SomatizationDataset":
        seen: set[str] = set()
        duplicates: list[str] = []
        for example in self.examples:
            if example.example_id in seen:
                duplicates.append(example.example_id)
                continue
            seen.add(example.example_id)
        if duplicates:
            raise ValueError(
                "duplicate somatization example_id values: "
                + ", ".join(sorted(set(duplicates)))
            )
        return self

    def by_split(
        self,
        split: SomatizationDatasetSplit | str | None = None,
    ) -> list[SomatizationBenchmarkExample]:
        if split is None:
            return list(self.examples)
        return [example for example in self.examples if example.split == split]


def load_somatization_dataset(
    path: str | Path,
    split: SomatizationDatasetSplit | str | None = None,
) -> SomatizationDataset:
    """Load a JSONL somatization dataset with schema validation."""
    examples: list[SomatizationBenchmarkExample] = []
    with open(path, encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = SomatizationBenchmarkExample.model_validate_json(line)
            except Exception as exc:  # pragma: no cover - error path exercised in tests
                raise ValueError(f"Invalid somatization dataset row {line_no}: {exc}") from exc
            examples.append(record)
    dataset = SomatizationDataset(examples=examples)
    if split is None:
        return dataset
    return SomatizationDataset(examples=dataset.by_split(split))


def save_somatization_dataset(
    dataset: SomatizationDataset | list[SomatizationBenchmarkExample],
    path: str | Path,
) -> None:
    """Write benchmark examples to canonical JSONL."""
    examples = dataset.examples if isinstance(dataset, SomatizationDataset) else list(dataset)
    with open(path, "w", encoding="utf-8") as f:
        for example in examples:
            payload = (
                example.model_dump(mode="json")
                if isinstance(example, SomatizationBenchmarkExample)
                else SomatizationBenchmarkExample.model_validate(example).model_dump(mode="json")
            )
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def export_somatization_dataset_csv(
    dataset: SomatizationDataset | list[SomatizationBenchmarkExample],
    path: str | Path,
) -> None:
    """Export dataset to a flat CSV for annotation/review workflows."""
    examples = dataset.examples if isinstance(dataset, SomatizationDataset) else list(dataset)
    fieldnames = [
        "example_id",
        "split",
        "text",
        "span_text",
        "span_start",
        "span_end",
        "normalized_concept",
        "candidate_criterion_ids",
        "disorder_relevance",
        "expression_type",
        "annotation_confidence",
        "annotator_notes",
        "source_dataset",
        "source_id",
        "source_turn_id",
        "language",
        "locale",
        "source_metadata",
        "metadata",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for example in examples:
            row = example.model_dump(mode="json")
            row["candidate_criterion_ids"] = "|".join(example.candidate_criterion_ids)
            row["disorder_relevance"] = "|".join(example.disorder_relevance)
            row["source_metadata"] = json.dumps(example.source_metadata, ensure_ascii=False)
            row["metadata"] = json.dumps(example.metadata, ensure_ascii=False)
            writer.writerow(row)


def import_somatization_dataset_csv(path: str | Path) -> SomatizationDataset:
    """Import a CSV export back into the validated dataset schema."""
    examples: list[SomatizationBenchmarkExample] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            payload = dict(row)
            payload["candidate_criterion_ids"] = [
                item for item in payload.get("candidate_criterion_ids", "").split("|") if item
            ]
            payload["disorder_relevance"] = [
                item for item in payload.get("disorder_relevance", "").split("|") if item
            ]
            payload["source_metadata"] = json.loads(payload.get("source_metadata") or "{}")
            payload["metadata"] = json.loads(payload.get("metadata") or "{}")
            for key in ("span_start", "span_end", "source_turn_id"):
                if payload.get(key) in ("", None):
                    payload[key] = None
                else:
                    payload[key] = int(payload[key])
            if payload.get("annotation_confidence") in ("", None):
                payload["annotation_confidence"] = None
            else:
                payload["annotation_confidence"] = float(payload["annotation_confidence"])
            examples.append(SomatizationBenchmarkExample.model_validate(payload))
    return SomatizationDataset(examples=examples)


def build_annotation_examples_from_spans(
    case: ClinicalCase,
    spans: list[SymptomSpan],
    split: SomatizationDatasetSplit = "annotation_pool",
) -> SomatizationDataset:
    """Create annotation-pool examples from extracted symptom spans."""
    turn_index = {turn.turn_id: turn for turn in case.transcript}
    examples: list[SomatizationBenchmarkExample] = []
    for span in spans:
        turn = turn_index.get(span.turn_id)
        context_text = turn.text if turn is not None else span.text
        span_start = context_text.find(span.text) if span.text else -1
        span_end = span_start + len(span.text) if span_start >= 0 else None
        examples.append(
            SomatizationBenchmarkExample(
                split=split,
                text=context_text,
                span_text=span.text,
                span_start=span_start if span_start >= 0 else None,
                span_end=span_end,
                normalized_concept=span.normalized_concept,
                candidate_criterion_ids=list(span.candidate_criteria),
                disorder_relevance=[],
                expression_type=(
                    span.expression_type
                    or ("somatized_expression" if span.is_somatic else "direct_symptom")
                ),
                source_dataset=case.dataset,
                source_id=case.case_id,
                source_turn_id=span.turn_id,
                language=case.language,
                metadata={
                    "annotation_status": "pending",
                    "symptom_type": span.symptom_type,
                },
            )
        )
    return SomatizationDataset(examples=examples)
