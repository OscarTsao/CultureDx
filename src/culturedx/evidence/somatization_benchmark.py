"""Benchmark, evaluation, and review tooling for somatization normalization."""
from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from culturedx.core.models import FailureInfo, SymptomSpan
from culturedx.eval.calibration import compute_brier_score, compute_calibration
from culturedx.evidence.normalization import (
    contains_ambiguity_marker,
    contains_bodily_marker,
    contains_direct_symptom_marker,
    contains_historical_marker,
    contains_negation,
    contains_other_person_marker,
)
from culturedx.evidence.somatization import (
    SomatizationMapper,
    rank_symptom_concepts,
    resolve_symptom_concept,
)
from culturedx.evidence.somatization_dataset import (
    SomatizationBenchmarkExample,
    SomatizationDataset,
)
from culturedx.ontology.symptom_map import lookup_symptom

EXPRESSION_TYPE_LABELS = (
    "direct_symptom",
    "somatized_expression",
    "metaphorical_or_ambiguous",
    "negated",
    "historical_past",
    "family_or_other_person",
    "insufficient_context",
)


@dataclass
class SomatizationPrediction:
    """Prediction record for benchmark evaluation."""

    example_id: str
    method_name: str
    predicted_expression_type: str
    predicted_concept: str | None = None
    candidate_concepts: list[str] = field(default_factory=list)
    candidate_criterion_ids: list[str] = field(default_factory=list)
    confidence: float | None = None
    rationale: str = ""
    ambiguity_flags: list[str] = field(default_factory=list)
    predicted_span_text: str | None = None
    predicted_span_start: int | None = None
    predicted_span_end: int | None = None
    cache_metadata: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewQueueItem:
    """Human-review queue record."""

    example_id: str
    priority_score: float
    review_reasons: list[str] = field(default_factory=list)
    text: str = ""
    span_text: str | None = None
    source_dataset: str = ""
    source_id: str = ""
    predicted_expression_types: dict[str, str] = field(default_factory=dict)
    predicted_concepts: dict[str, str | None] = field(default_factory=dict)
    gold_expression_type: str | None = None
    gold_concept: str | None = None
    production_signals: list[str] = field(default_factory=list)


@dataclass
class AdjudicationRecord:
    """Reviewer-friendly comparison record."""

    example_id: str
    text: str
    span_text: str | None
    source_dataset: str
    source_id: str
    model_prediction: str | None
    model_expression_type: str
    gold_label: str | None
    gold_expression_type: str
    candidate_criterion_ids: list[str] = field(default_factory=list)
    gold_criterion_ids: list[str] = field(default_factory=list)
    confidence: float | None = None
    disagreement_reason: str = ""
    free_text_notes: str = ""


def _prediction_index(
    predictions: Iterable[SomatizationPrediction],
) -> dict[str, SomatizationPrediction]:
    return {prediction.example_id: prediction for prediction in predictions}


def _is_ambiguous_expression(expression_type: str) -> bool:
    return expression_type in {
        "metaphorical_or_ambiguous",
        "insufficient_context",
        "negated",
        "historical_past",
        "family_or_other_person",
    }


def _clip_confidence(confidence: float | None) -> float | None:
    if confidence is None:
        return None
    return max(0.0, min(1.0, float(confidence)))


def infer_expression_type(text: str, has_concept: bool = False) -> tuple[str, list[str]]:
    """Infer a lightweight expression type for baseline methods."""
    flags: list[str] = []
    if contains_negation(text):
        flags.append("negated")
        return "negated", flags
    if contains_historical_marker(text):
        flags.append("historical_past")
        return "historical_past", flags
    if contains_other_person_marker(text):
        flags.append("family_or_other_person")
        return "family_or_other_person", flags
    if contains_direct_symptom_marker(text) and not contains_bodily_marker(text):
        return "direct_symptom", flags
    if has_concept and contains_bodily_marker(text):
        return "somatized_expression", flags
    if contains_ambiguity_marker(text):
        flags.append("ambiguous_context")
        return "metaphorical_or_ambiguous", flags
    return "insufficient_context", flags


class ExactOntologySomatizationBaseline:
    """Exact ontology lookup baseline."""

    method_name = "ontology_exact"

    def predict(self, example: SomatizationBenchmarkExample) -> SomatizationPrediction:
        query = example.span_text or example.text
        entry = lookup_symptom(query)
        expression_type, flags = infer_expression_type(query, has_concept=entry is not None)
        predicted_concept = query if entry is not None else None
        return SomatizationPrediction(
            example_id=example.example_id,
            method_name=self.method_name,
            predicted_expression_type=expression_type,
            predicted_concept=predicted_concept,
            candidate_concepts=[predicted_concept] if predicted_concept else [],
            candidate_criterion_ids=list(entry.get("criteria", [])) if entry else [],
            confidence=1.0 if entry else 0.0,
            rationale="exact_ontology_lookup",
            ambiguity_flags=flags,
            predicted_span_text=example.span_text,
            predicted_span_start=example.span_start,
            predicted_span_end=example.span_end,
        )

    def predict_all(
        self,
        examples: Iterable[SomatizationBenchmarkExample],
    ) -> list[SomatizationPrediction]:
        return [self.predict(example) for example in examples]


class FuzzyOntologySomatizationBaseline:
    """Ontology + synonym/fuzzy baseline."""

    method_name = "ontology_fuzzy"

    def __init__(self, top_k: int = 5) -> None:
        self.top_k = top_k

    def predict(self, example: SomatizationBenchmarkExample) -> SomatizationPrediction:
        query = example.span_text or example.text
        ranked = list(rank_symptom_concepts(query, top_k=self.top_k))
        resolved = ranked[0] if ranked else resolve_symptom_concept(query)
        expression_type, flags = infer_expression_type(query, has_concept=resolved is not None)
        candidate_concepts = [candidate.canonical_text for candidate in ranked]
        candidate_criteria = []
        seen = set()
        for candidate in ranked:
            for criterion in candidate.criteria:
                if criterion not in seen:
                    seen.add(criterion)
                    candidate_criteria.append(criterion)
        return SomatizationPrediction(
            example_id=example.example_id,
            method_name=self.method_name,
            predicted_expression_type=expression_type,
            predicted_concept=resolved.canonical_text if resolved else None,
            candidate_concepts=candidate_concepts,
            candidate_criterion_ids=candidate_criteria,
            confidence=resolved.score if resolved else 0.0,
            rationale=resolved.match_type if resolved else "no_match",
            ambiguity_flags=flags,
            predicted_span_text=example.span_text,
            predicted_span_start=example.span_start,
            predicted_span_end=example.span_end,
        )

    def predict_all(
        self,
        examples: Iterable[SomatizationBenchmarkExample],
    ) -> list[SomatizationPrediction]:
        return [self.predict(example) for example in examples]


class CurrentSomatizationModuleBaseline:
    """Current repo somatization module baseline."""

    method_name = "current_mapper"

    def __init__(self, mapper: SomatizationMapper | None = None) -> None:
        self.mapper = mapper or SomatizationMapper(llm_client=None, llm_fallback=False)

    def predict(self, example: SomatizationBenchmarkExample) -> SomatizationPrediction:
        query = example.span_text or example.text
        span = SymptomSpan(
            text=query,
            turn_id=example.source_turn_id or 0,
            symptom_type="somatic",
            is_somatic=True,
        )
        mapped = self.mapper.map_span(span, context=example.text)
        expression_type = getattr(mapped, "expression_type", None) or infer_expression_type(
            example.text,
            has_concept=bool(mapped.normalized_concept),
        )[0]
        return SomatizationPrediction(
            example_id=example.example_id,
            method_name=self.method_name,
            predicted_expression_type=expression_type,
            predicted_concept=mapped.normalized_concept,
            candidate_concepts=[mapped.normalized_concept] if mapped.normalized_concept else [],
            candidate_criterion_ids=list(mapped.candidate_criteria),
            confidence=mapped.mapping_confidence,
            rationale=mapped.mapping_rationale or "",
            ambiguity_flags=list(mapped.ambiguity_flags),
            predicted_span_text=query,
            predicted_span_start=example.span_start,
            predicted_span_end=example.span_end,
            cache_metadata=dict(mapped.cache_metadata),
        )

    def predict_all(
        self,
        examples: Iterable[SomatizationBenchmarkExample],
    ) -> list[SomatizationPrediction]:
        return [self.predict(example) for example in examples]


class EmbeddingAssistedSomatizationBaseline:
    """Optional embedding-assisted candidate generator behind a feature gate."""

    method_name = "embedding_assisted"

    def __init__(
        self,
        enabled: bool = False,
        model_id: str = "BAAI/bge-m3",
        top_k: int = 5,
    ) -> None:
        self.enabled = enabled
        self.model_id = model_id
        self.top_k = top_k
        self._encoder = None
        self._concepts: list[str] | None = None
        self._concept_embeddings = None

        if not enabled:
            self.disabled_reason = "feature_disabled"
            return

        try:  # pragma: no cover - optional dependency path
            from sentence_transformers import SentenceTransformer
        except Exception:
            self.disabled_reason = "sentence_transformers_unavailable"
            return

        from culturedx.ontology.symptom_map import load_somatization_map

        self._encoder = SentenceTransformer(model_id)
        self._concepts = sorted(load_somatization_map().keys())
        self._concept_embeddings = self._encoder.encode(
            self._concepts,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        self.disabled_reason = ""

    def predict(self, example: SomatizationBenchmarkExample) -> SomatizationPrediction:
        if self._encoder is None or self._concepts is None or self._concept_embeddings is None:
            return SomatizationPrediction(
                example_id=example.example_id,
                method_name=self.method_name,
                predicted_expression_type="insufficient_context",
                confidence=0.0,
                rationale=self.disabled_reason,
            )

        query = example.span_text or example.text
        query_embedding = self._encoder.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )[0]
        scores = np.dot(self._concept_embeddings, query_embedding)
        top_indices = np.argsort(scores)[::-1][: self.top_k]
        concepts = [self._concepts[idx] for idx in top_indices]
        best = concepts[0] if concepts else None
        entry = lookup_symptom(best) if best else None
        expression_type, flags = infer_expression_type(example.text, has_concept=best is not None)
        return SomatizationPrediction(
            example_id=example.example_id,
            method_name=self.method_name,
            predicted_expression_type=expression_type,
            predicted_concept=best,
            candidate_concepts=concepts,
            candidate_criterion_ids=list(entry.get("criteria", [])) if entry else [],
            confidence=float(scores[top_indices[0]]) if len(top_indices) else 0.0,
            rationale=f"embedding:{self.model_id}",
            ambiguity_flags=flags,
            predicted_span_text=query,
            predicted_span_start=example.span_start,
            predicted_span_end=example.span_end,
        )

    def predict_all(
        self,
        examples: Iterable[SomatizationBenchmarkExample],
    ) -> list[SomatizationPrediction]:
        return [self.predict(example) for example in examples]


def evaluate_somatization_predictions(
    dataset: SomatizationDataset | list[SomatizationBenchmarkExample],
    predictions: Iterable[SomatizationPrediction],
    top_k: int = 3,
) -> dict[str, Any]:
    """Evaluate benchmark predictions and return machine-readable metrics."""
    examples = dataset.examples if isinstance(dataset, SomatizationDataset) else list(dataset)
    pred_index = _prediction_index(predictions)

    concept_total = 0
    concept_exact_hits = 0
    concept_topk_hits = 0
    criterion_total = 0
    criterion_recall_sum = 0.0
    expr_correct = 0
    span_tp = span_fp = span_fn = 0
    label_stats: dict[str, dict[str, float]] = {}
    confusion: dict[str, dict[str, int]] = {}
    correct_flags: list[bool] = []
    confidence_values: list[float] = []
    per_concept: dict[str, dict[str, float]] = {}
    per_disorder: dict[str, dict[str, float]] = {}

    for label in EXPRESSION_TYPE_LABELS:
        label_stats[label] = {"tp": 0.0, "fp": 0.0, "fn": 0.0, "support": 0.0}

    for example in examples:
        pred = pred_index.get(example.example_id)
        predicted_expression = pred.predicted_expression_type if pred else "insufficient_context"
        predicted_concept = pred.predicted_concept if pred else None
        predicted_candidates = pred.candidate_concepts if pred else []
        predicted_criteria = pred.candidate_criterion_ids if pred else []

        expr_correct += int(predicted_expression == example.expression_type)
        confusion.setdefault(example.expression_type, {})
        confusion[example.expression_type][predicted_expression] = (
            confusion[example.expression_type].get(predicted_expression, 0) + 1
        )
        label_stats[example.expression_type]["support"] += 1
        for label in EXPRESSION_TYPE_LABELS:
            if predicted_expression == label and example.expression_type == label:
                label_stats[label]["tp"] += 1
            elif predicted_expression == label and example.expression_type != label:
                label_stats[label]["fp"] += 1
            elif predicted_expression != label and example.expression_type == label:
                label_stats[label]["fn"] += 1

        if example.normalized_concept:
            concept_total += 1
            concept_exact = predicted_concept == example.normalized_concept
            concept_exact_hits += int(concept_exact)
            concept_topk_hits += int(example.normalized_concept in predicted_candidates[:top_k])
            clipped_confidence = _clip_confidence(pred.confidence if pred else None)
            if pred and clipped_confidence is not None:
                confidence_values.append(clipped_confidence)
                correct_flags.append(concept_exact)

            concept_stats = per_concept.setdefault(
                example.normalized_concept,
                {"support": 0.0, "exact_hits": 0.0},
            )
            concept_stats["support"] += 1
            concept_stats["exact_hits"] += int(concept_exact)

        if example.candidate_criterion_ids:
            criterion_total += 1
            overlap = set(example.candidate_criterion_ids) & set(predicted_criteria)
            criterion_recall_sum += len(overlap) / len(example.candidate_criterion_ids)

        if example.disorder_relevance:
            for disorder in example.disorder_relevance:
                stats = per_disorder.setdefault(disorder, {"support": 0.0, "exact_hits": 0.0})
                stats["support"] += 1
                stats["exact_hits"] += int(predicted_concept == example.normalized_concept)

        if (
            example.span_start is not None
            and example.span_end is not None
            and pred
            and pred.predicted_span_start is not None
            and pred.predicted_span_end is not None
        ):
            gold = set(range(example.span_start, example.span_end))
            pred_span = set(range(pred.predicted_span_start, pred.predicted_span_end))
            span_tp += len(gold & pred_span)
            span_fp += len(pred_span - gold)
            span_fn += len(gold - pred_span)

    label_metrics: dict[str, dict[str, float]] = {}
    for label in EXPRESSION_TYPE_LABELS:
        counts = label_stats[label]
        precision = counts["tp"] / (counts["tp"] + counts["fp"]) if counts["tp"] + counts["fp"] else 0.0
        recall = counts["tp"] / (counts["tp"] + counts["fn"]) if counts["tp"] + counts["fn"] else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        label_metrics[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": counts["support"],
        }

    span_precision = span_tp / (span_tp + span_fp) if span_tp + span_fp else 0.0
    span_recall = span_tp / (span_tp + span_fn) if span_tp + span_fn else 0.0
    span_f1 = (
        2 * span_precision * span_recall / (span_precision + span_recall)
        if span_precision + span_recall
        else 0.0
    )

    reduced_confusion: dict[str, dict[str, int]] = {
        "somatized_expression": {"somatized_expression": 0, "direct_symptom": 0, "ambiguous_or_contextual": 0},
        "direct_symptom": {"somatized_expression": 0, "direct_symptom": 0, "ambiguous_or_contextual": 0},
        "ambiguous_or_contextual": {"somatized_expression": 0, "direct_symptom": 0, "ambiguous_or_contextual": 0},
    }
    for gold_label, preds in confusion.items():
        gold_bucket = (
            gold_label if gold_label in {"somatized_expression", "direct_symptom"} else "ambiguous_or_contextual"
        )
        for pred_label, count in preds.items():
            pred_bucket = (
                pred_label if pred_label in {"somatized_expression", "direct_symptom"} else "ambiguous_or_contextual"
            )
            reduced_confusion[gold_bucket][pred_bucket] += count

    confidence_metrics = {}
    if confidence_values:
        calibration = compute_calibration(confidence_values, correct_flags, n_bins=5, mode="somatization")
        confidence_metrics = {
            "brier_score": compute_brier_score(confidence_values, correct_flags),
            "ece": calibration.ece,
            "avg_confidence": calibration.avg_confidence,
            "overall_accuracy": calibration.overall_accuracy,
        }

    return {
        "num_examples": len(examples),
        "exact_concept_accuracy": concept_exact_hits / concept_total if concept_total else 0.0,
        "top_k_concept_recall": concept_topk_hits / concept_total if concept_total else 0.0,
        "top_k": top_k,
        "criterion_candidate_recall": criterion_recall_sum / criterion_total if criterion_total else 0.0,
        "expression_type_accuracy": expr_correct / len(examples) if examples else 0.0,
        "span_metrics": {
            "precision": span_precision,
            "recall": span_recall,
            "f1": span_f1,
        },
        "label_metrics": label_metrics,
        "confusion_breakdown": reduced_confusion,
        "confidence_diagnostics": confidence_metrics,
        "per_concept": {
            concept: {
                "support": stats["support"],
                "exact_accuracy": stats["exact_hits"] / stats["support"] if stats["support"] else 0.0,
            }
            for concept, stats in sorted(per_concept.items())
        },
        "per_disorder": {
            disorder: {
                "support": stats["support"],
                "exact_accuracy": stats["exact_hits"] / stats["support"] if stats["support"] else 0.0,
            }
            for disorder, stats in sorted(per_disorder.items())
        },
        "error_records": build_error_analysis_records(examples, pred_index.values()),
    }


def format_somatization_metrics_markdown(metrics: dict[str, Any], title: str = "Somatization Benchmark") -> str:
    """Create a reviewer-friendly markdown summary."""
    lines = [
        f"# {title}",
        "",
        f"- Examples: {metrics['num_examples']}",
        f"- Exact concept accuracy: {metrics['exact_concept_accuracy']:.4f}",
        f"- Top-{metrics['top_k']} concept recall: {metrics['top_k_concept_recall']:.4f}",
        f"- Criterion candidate recall: {metrics['criterion_candidate_recall']:.4f}",
        f"- Expression type accuracy: {metrics['expression_type_accuracy']:.4f}",
        "",
        "## Span Metrics",
        "",
        f"- Precision: {metrics['span_metrics']['precision']:.4f}",
        f"- Recall: {metrics['span_metrics']['recall']:.4f}",
        f"- F1: {metrics['span_metrics']['f1']:.4f}",
        "",
        "## Label Metrics",
        "",
        "| label | precision | recall | f1 | support |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, values in metrics["label_metrics"].items():
        lines.append(
            f"| {label} | {values['precision']:.4f} | {values['recall']:.4f} | "
            f"{values['f1']:.4f} | {int(values['support'])} |"
        )
    lines.append("")

    if metrics["confidence_diagnostics"]:
        lines.append("## Confidence Diagnostics")
        lines.append("")
        for key, value in metrics["confidence_diagnostics"].items():
            lines.append(f"- {key}: {value:.4f}")
        lines.append("")

    lines.append("## Confusion Breakdown")
    lines.append("")
    lines.append("| gold \\ pred | somatized_expression | direct_symptom | ambiguous_or_contextual |")
    lines.append("|---|---:|---:|---:|")
    for gold, values in metrics["confusion_breakdown"].items():
        lines.append(
            f"| {gold} | {values['somatized_expression']} | {values['direct_symptom']} "
            f"| {values['ambiguous_or_contextual']} |"
        )
    lines.append("")
    return "\n".join(lines)


def save_somatization_metrics(
    metrics: dict[str, Any],
    json_path: str | Path,
    markdown_path: str | Path | None = None,
) -> None:
    """Persist benchmark metrics in machine-readable and markdown forms."""
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    if markdown_path is not None:
        Path(markdown_path).write_text(
            format_somatization_metrics_markdown(metrics),
            encoding="utf-8",
        )


def build_error_analysis_records(
    dataset: SomatizationDataset | list[SomatizationBenchmarkExample],
    predictions: Iterable[SomatizationPrediction],
) -> list[dict[str, Any]]:
    """Create error buckets for review and analysis."""
    examples = dataset.examples if isinstance(dataset, SomatizationDataset) else list(dataset)
    pred_index = _prediction_index(predictions)
    records: list[dict[str, Any]] = []
    for example in examples:
        pred = pred_index.get(example.example_id)
        if pred is None:
            continue
        buckets: list[str] = []
        if pred.predicted_expression_type == "direct_symptom" and example.expression_type == "somatized_expression":
            buckets.append("false_direct_expression_prediction")
        if example.expression_type == "somatized_expression" and pred.predicted_expression_type != "somatized_expression":
            buckets.append("missed_somatized_expression")
        if example.normalized_concept and pred.predicted_concept != example.normalized_concept:
            buckets.append("wrong_normalized_concept")
        if example.candidate_criterion_ids and not (
            set(example.candidate_criterion_ids) & set(pred.candidate_criterion_ids)
        ):
            buckets.append("wrong_criterion_grounding")
        if _is_ambiguous_expression(example.expression_type) or pred.ambiguity_flags:
            buckets.append("ambiguity_heavy_example")
        if example.expression_type in {"negated", "historical_past"} and pred.predicted_expression_type != example.expression_type:
            buckets.append("negation_or_temporality_failure")
        if not buckets:
            continue
        records.append(
            {
                "example_id": example.example_id,
                "text": example.text,
                "span_text": example.span_text,
                "gold_expression_type": example.expression_type,
                "gold_concept": example.normalized_concept,
                "predicted_expression_type": pred.predicted_expression_type,
                "predicted_concept": pred.predicted_concept,
                "confidence": pred.confidence,
                "buckets": buckets,
            }
        )
    return records


def build_adjudication_records(
    dataset: SomatizationDataset | list[SomatizationBenchmarkExample],
    predictions: Iterable[SomatizationPrediction],
) -> list[AdjudicationRecord]:
    """Create adjudication-ready comparison rows."""
    examples = dataset.examples if isinstance(dataset, SomatizationDataset) else list(dataset)
    pred_index = _prediction_index(predictions)
    records: list[AdjudicationRecord] = []
    for example in examples:
        pred = pred_index.get(example.example_id)
        if pred is None:
            continue
        reasons = []
        if pred.predicted_expression_type != example.expression_type:
            reasons.append("expression_type_disagreement")
        if pred.predicted_concept != example.normalized_concept:
            reasons.append("concept_disagreement")
        if example.candidate_criterion_ids and not (
            set(example.candidate_criterion_ids) & set(pred.candidate_criterion_ids)
        ):
            reasons.append("criterion_disagreement")
        records.append(
            AdjudicationRecord(
                example_id=example.example_id,
                text=example.text,
                span_text=example.span_text,
                source_dataset=example.source_dataset,
                source_id=example.source_id,
                model_prediction=pred.predicted_concept,
                model_expression_type=pred.predicted_expression_type,
                gold_label=example.normalized_concept,
                gold_expression_type=example.expression_type,
                candidate_criterion_ids=list(pred.candidate_criterion_ids),
                gold_criterion_ids=list(example.candidate_criterion_ids),
                confidence=pred.confidence,
                disagreement_reason=",".join(reasons) if reasons else "match",
            )
        )
    return records


def export_adjudication_records(
    records: Iterable[AdjudicationRecord],
    path: str | Path,
) -> None:
    """Export adjudication records to JSONL or CSV."""
    path = Path(path)
    items = [asdict(record) for record in records]
    if path.suffix.lower() == ".csv":
        with open(path, "w", encoding="utf-8", newline="") as f:
            fieldnames = list(items[0].keys()) if items else [
                "example_id",
                "text",
                "span_text",
                "source_dataset",
                "source_id",
                "model_prediction",
                "model_expression_type",
                "gold_label",
                "gold_expression_type",
                "candidate_criterion_ids",
                "gold_criterion_ids",
                "confidence",
                "disagreement_reason",
                "free_text_notes",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in items:
                item["candidate_criterion_ids"] = "|".join(item["candidate_criterion_ids"])
                item["gold_criterion_ids"] = "|".join(item["gold_criterion_ids"])
                writer.writerow(item)
        return

    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def generate_review_queue(
    dataset: SomatizationDataset | list[SomatizationBenchmarkExample],
    prediction_sets: dict[str, Iterable[SomatizationPrediction]],
    production_failures: dict[str, list[FailureInfo | str]] | None = None,
    max_items: int | None = None,
) -> list[ReviewQueueItem]:
    """Prioritize examples for human review using disagreement and uncertainty."""
    examples = dataset.examples if isinstance(dataset, SomatizationDataset) else list(dataset)
    indexed_predictions = {
        name: _prediction_index(predictions)
        for name, predictions in prediction_sets.items()
    }
    concept_counts: dict[str, int] = {}
    for example in examples:
        if example.normalized_concept:
            concept_counts[example.normalized_concept] = concept_counts.get(example.normalized_concept, 0) + 1

    queue: list[ReviewQueueItem] = []
    for example in examples:
        method_predictions = {
            name: preds.get(example.example_id)
            for name, preds in indexed_predictions.items()
            if preds.get(example.example_id) is not None
        }
        if not method_predictions:
            continue

        predicted_concepts = {name: pred.predicted_concept for name, pred in method_predictions.items()}
        predicted_expression_types = {
            name: pred.predicted_expression_type for name, pred in method_predictions.items()
        }
        unique_concepts = {value for value in predicted_concepts.values() if value}
        unique_exprs = set(predicted_expression_types.values())
        confidences = [
            pred.confidence for pred in method_predictions.values()
            if pred.confidence is not None
        ]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        low_confidence_score = 1.0 - avg_conf
        disagreement_score = max(0.0, (len(unique_concepts) - 1) * 0.35 + (len(unique_exprs) - 1) * 0.25)
        ambiguity_score = 0.25 if (
            example.expression_type == "metaphorical_or_ambiguous"
            or any(pred.ambiguity_flags for pred in method_predictions.values())
        ) else 0.0
        underrepresented_score = 0.0
        if example.normalized_concept:
            support = concept_counts.get(example.normalized_concept, 1)
            underrepresented_score = 1.0 / math.sqrt(support)
        ontology_mismatch_score = 0.35 if len(unique_concepts) > 1 else 0.0

        production_signals: list[str] = []
        if production_failures and example.example_id in production_failures:
            raw_signals = production_failures[example.example_id]
            for item in raw_signals:
                if isinstance(item, FailureInfo):
                    production_signals.append(f"{item.code}:{item.stage}")
                else:
                    production_signals.append(str(item))
        production_score = 0.20 * len(production_signals)

        priority = (
            low_confidence_score
            + disagreement_score
            + ambiguity_score
            + underrepresented_score
            + ontology_mismatch_score
            + production_score
        )

        reasons: list[str] = []
        if low_confidence_score > 0.35:
            reasons.append("low_confidence")
        if disagreement_score > 0.0:
            reasons.append("high_method_disagreement")
        if ambiguity_score > 0.0:
            reasons.append("ambiguity")
        if underrepresented_score > 0.5:
            reasons.append("underrepresented_concept")
        if ontology_mismatch_score > 0.0:
            reasons.append("ontology_vs_fuzzy_or_mapper_mismatch")
        reasons.extend(production_signals)

        queue.append(
            ReviewQueueItem(
                example_id=example.example_id,
                priority_score=priority,
                review_reasons=reasons,
                text=example.text,
                span_text=example.span_text,
                source_dataset=example.source_dataset,
                source_id=example.source_id,
                predicted_expression_types=predicted_expression_types,
                predicted_concepts=predicted_concepts,
                gold_expression_type=example.expression_type,
                gold_concept=example.normalized_concept,
                production_signals=production_signals,
            )
        )

    queue.sort(key=lambda item: (-item.priority_score, item.example_id))
    if max_items is not None:
        return queue[:max_items]
    return queue


def save_review_queue(
    queue: Iterable[ReviewQueueItem],
    path: str | Path,
) -> None:
    """Persist review queue items as JSONL or CSV."""
    path = Path(path)
    items = [asdict(item) for item in queue]
    if path.suffix.lower() == ".csv":
        with open(path, "w", encoding="utf-8", newline="") as f:
            fieldnames = list(items[0].keys()) if items else [
                "example_id",
                "priority_score",
                "review_reasons",
                "text",
                "span_text",
                "source_dataset",
                "source_id",
                "predicted_expression_types",
                "predicted_concepts",
                "gold_expression_type",
                "gold_concept",
                "production_signals",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in items:
                item["review_reasons"] = "|".join(item["review_reasons"])
                item["predicted_expression_types"] = json.dumps(
                    item["predicted_expression_types"],
                    ensure_ascii=False,
                    sort_keys=True,
                )
                item["predicted_concepts"] = json.dumps(
                    item["predicted_concepts"],
                    ensure_ascii=False,
                    sort_keys=True,
                )
                item["production_signals"] = "|".join(item["production_signals"])
                writer.writerow(item)
        return

    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
