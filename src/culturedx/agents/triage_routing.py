"""Triage routing, calibration artifact, and evaluation helpers.

This module turns broad category scores into explicit routing decisions that
the rest of the repo can audit: calibrated category scores, selected candidate
disorders, uncertainty, and routing-quality metrics.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
import math
from statistics import mean, median
from typing import Any, Sequence

import numpy as np
from scipy.optimize import minimize_scalar

CATEGORY_DISORDERS: dict[str, list[str]] = {
    "mood": ["F31", "F32", "F33", "F39"],
    "anxiety": ["F40", "F41.0", "F41.1", "F41.2", "F42"],
    "stress": ["F43.1", "F43.2"],
    "somatoform": ["F45"],
    "psychotic": ["F20", "F22"],
    "sleep": ["F51"],
    "behavioral": ["F98"],
    "counseling": ["Z71"],
}

VALID_CATEGORIES = frozenset(CATEGORY_DISORDERS.keys())


def _clamp_probability(value: float) -> float:
    return max(1e-6, min(1.0 - 1e-6, float(value)))


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def _logit(value: float) -> float:
    p = _clamp_probability(value)
    return math.log(p / (1.0 - p))


@dataclass
class TriageCalibrationArtifact:
    """Persisted calibration parameters for triage routing."""

    version: int = 1
    method: str = "temperature_scaling"
    temperature: float = 1.0
    categories: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    validation_metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        return path

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TriageCalibrationArtifact":
        return cls(
            version=int(payload.get("version", 1)),
            method=str(payload.get("method", "temperature_scaling")),
            temperature=float(payload.get("temperature", 1.0)),
            categories=list(payload.get("categories", [])),
            metadata=dict(payload.get("metadata", {})),
            validation_metrics=dict(payload.get("validation_metrics", {})),
        )

    @classmethod
    def load(cls, path: str | Path) -> "TriageCalibrationArtifact":
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            raise ValueError("Calibration artifact must be a JSON object")
        return cls.from_dict(payload)


@dataclass
class TriageCalibrationExample:
    """Generic triage calibration record for fitting and evaluation."""

    example_id: str
    gold_categories: list[str]
    raw_category_scores: dict[str, float]


@dataclass
class TriageCategoryInput:
    """Raw category score extracted from an LLM response."""

    category: str
    raw_score: float


@dataclass
class TriageCategoryScore:
    """Category score with routing metadata."""

    category: str
    raw_score: float
    calibrated_score: float
    selected: bool
    disorder_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TriageRoutingResult:
    """Structured triage routing output."""

    routing_mode: str
    calibration_status: str
    calibration_artifact_path: str | None
    categories: list[TriageCategoryScore]
    raw_category_scores: dict[str, float]
    calibrated_category_scores: dict[str, float]
    selected_categories: list[str]
    candidate_disorder_codes: list[str]
    disorder_codes: list[str]
    uncertainty: float
    open_set_score: float | None = None
    out_of_scope_score: float | None = None
    fallback_reason: str | None = None
    confidence_threshold: float = 0.7
    activation_threshold: float = 0.2
    max_categories: int = 3

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["categories"] = [category.to_dict() for category in self.categories]
        return payload


def normalize_triage_categories(parsed: dict | list | None) -> tuple[list[TriageCategoryInput], str | None]:
    """Extract valid category inputs from a parsed LLM payload."""
    categories: list[TriageCategoryInput] = []
    fallback_reason: str | None = None

    if parsed and isinstance(parsed, dict) and "categories" in parsed:
        best_scores: dict[str, float] = {}
        for item in parsed["categories"]:
            if not isinstance(item, dict):
                continue
            category = str(item.get("category", "")).strip()
            if category not in VALID_CATEGORIES:
                continue
            try:
                raw_score = float(item.get("confidence", 0.0))
            except (TypeError, ValueError):
                raw_score = 0.0
            best_scores[category] = max(
                best_scores.get(category, 0.0),
                max(0.0, min(1.0, raw_score)),
            )
        categories = [
            TriageCategoryInput(category=category, raw_score=score)
            for category, score in best_scores.items()
        ]

    if not categories:
        fallback_reason = "no_valid_categories"

    categories.sort(key=lambda item: item.raw_score, reverse=True)
    return categories, fallback_reason


def load_calibration_artifact(
    artifact_path: str | Path | None,
) -> tuple[TriageCalibrationArtifact | None, str | None]:
    """Load a calibration artifact. Crashes if path is given but file is missing."""
    if artifact_path is None:
        return None, "no_artifact_path"

    path = Path(artifact_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Triage calibration artifact not found at {path}. "
            "Remove calibration_artifact_path from config or provide a valid path."
        )

    return TriageCalibrationArtifact.load(path), None


def apply_temperature_scaling(raw_score: float, temperature: float) -> float:
    """Apply temperature scaling to a probability-like score."""
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    return _sigmoid(_logit(raw_score) / temperature)


def calibrate_scores(
    raw_scores: dict[str, float],
    artifact: TriageCalibrationArtifact | None,
) -> dict[str, float]:
    """Calibrate raw category scores, or pass through unchanged."""
    if artifact is None or artifact.method in {"identity", "none"}:
        return dict(raw_scores)

    if artifact.method != "temperature_scaling":
        raise ValueError(f"Unsupported calibration method: {artifact.method}")

    temperature = artifact.temperature if artifact.temperature > 0 else 1.0
    return {
        category: apply_temperature_scaling(score, temperature)
        for category, score in raw_scores.items()
    }


def route_triage_categories(
    category_inputs: Sequence[TriageCategoryInput],
    *,
    calibration_artifact: TriageCalibrationArtifact | None = None,
    calibration_artifact_path: str | Path | None = None,
    confidence_threshold: float = 0.7,
    activation_threshold: float = 0.2,
    max_categories: int = 3,
) -> TriageRoutingResult:
    """Convert category scores into a structured routing decision.

    The selection rule is intentionally simple and inspectable:

    - if one category is confident enough, keep all activated categories above
      the activation threshold
    - otherwise fall back to the top ``max_categories`` categories

    This keeps open-set routing behavior explicit even without a learned
    calibration artifact.
    """
    raw_scores = {item.category: item.raw_score for item in category_inputs}
    calibrated_scores = calibrate_scores(raw_scores, calibration_artifact)
    score_key = calibrated_scores if calibration_artifact is not None else raw_scores

    ranked = sorted(
        category_inputs,
        key=lambda item: (score_key.get(item.category, 0.0), raw_scores.get(item.category, 0.0), item.category),
        reverse=True,
    )
    top_score = score_key.get(ranked[0].category, 0.0) if ranked else 0.0

    if top_score >= confidence_threshold:
        selected = [
            item for item in ranked
            if score_key.get(item.category, 0.0) >= activation_threshold
        ]
    else:
        selected = list(ranked[:max_categories])

    selected_categories = [item.category for item in selected]
    candidate_disorder_codes = _expand_categories_to_codes(selected_categories)
    category_scores = [
        TriageCategoryScore(
            category=item.category,
            raw_score=raw_scores[item.category],
            calibrated_score=calibrated_scores.get(item.category, raw_scores[item.category]),
            selected=item.category in selected_categories,
            disorder_codes=list(CATEGORY_DISORDERS[item.category]),
        )
        for item in ranked
    ]

    routing_mode = "calibrated" if calibration_artifact is not None else "heuristic_fallback"
    calibration_status = "loaded" if calibration_artifact is not None else "fallback"
    fallback_reason = None if calibration_artifact is not None else "no_calibration_artifact"
    uncertainty = 1.0 - top_score

    return TriageRoutingResult(
        routing_mode=routing_mode,
        calibration_status=calibration_status,
        calibration_artifact_path=str(calibration_artifact_path) if calibration_artifact_path else None,
        categories=category_scores,
        raw_category_scores=raw_scores,
        calibrated_category_scores=calibrated_scores,
        selected_categories=selected_categories,
        candidate_disorder_codes=candidate_disorder_codes,
        disorder_codes=list(candidate_disorder_codes),
        uncertainty=uncertainty,
        open_set_score=uncertainty,
        out_of_scope_score=uncertainty,
        fallback_reason=fallback_reason,
        confidence_threshold=confidence_threshold,
        activation_threshold=activation_threshold,
        max_categories=max_categories,
    )


def _expand_categories_to_codes(categories: Sequence[str]) -> list[str]:
    """Expand ordered triage categories into a deduplicated disorder list."""
    disorder_codes: list[str] = []
    for category in categories:
        for code in CATEGORY_DISORDERS.get(category, []):
            if code not in disorder_codes:
                disorder_codes.append(code)
    return disorder_codes


def fit_temperature_scaling(
    examples: Sequence[TriageCalibrationExample],
    *,
    max_temperature: float = 10.0,
    min_temperature: float = 0.25,
) -> TriageCalibrationArtifact:
    """Fit a global temperature for triage calibration using BCE.

    The artifact is intentionally simple and inspectable so the repo can ship a
    safe fallback path when no private training data or learned artifact is
    available.
    """
    category_set = sorted({category for example in examples for category in example.raw_category_scores})
    if not category_set:
        return TriageCalibrationArtifact(
            method="temperature_scaling",
            temperature=1.0,
            categories=[],
            metadata={"num_examples": len(examples), "fallback": True},
        )

    scores: list[float] = []
    labels: list[int] = []
    for example in examples:
        gold = set(example.gold_categories)
        for category, raw_score in example.raw_category_scores.items():
            if category not in VALID_CATEGORIES:
                continue
            scores.append(float(raw_score))
            labels.append(1 if category in gold else 0)

    if not scores or len(set(labels)) < 2:
        return TriageCalibrationArtifact(
            method="temperature_scaling",
            temperature=1.0,
            categories=category_set,
            metadata={
                "num_examples": len(examples),
                "fallback": True,
                "reason": "insufficient_label_variance",
            },
        )

    scores_arr = np.asarray(scores, dtype=float)
    labels_arr = np.asarray(labels, dtype=float)

    def _loss(temp: float) -> float:
        calibrated = np.asarray(
            [apply_temperature_scaling(score, temp) for score in scores_arr],
            dtype=float,
        )
        calibrated = np.clip(calibrated, 1e-6, 1.0 - 1e-6)
        return float(
            -np.mean(
                labels_arr * np.log(calibrated)
                + (1.0 - labels_arr) * np.log(1.0 - calibrated)
            )
        )

    result = minimize_scalar(_loss, bounds=(min_temperature, max_temperature), method="bounded")
    temperature = float(result.x if result.success else 1.0)
    artifact = TriageCalibrationArtifact(
        method="temperature_scaling",
        temperature=max(min_temperature, temperature),
        categories=category_set,
        metadata={
            "num_examples": len(examples),
            "num_scores": len(scores),
            "optimizer_success": bool(result.success),
            "objective": float(result.fun) if result.success else None,
        },
    )
    artifact.validation_metrics = evaluate_triage_calibration(examples, artifact)
    return artifact


def evaluate_triage_calibration(
    examples: Sequence[TriageCalibrationExample],
    artifact: TriageCalibrationArtifact | None = None,
    *,
    top_k_values: Sequence[int] = (1, 3),
) -> dict[str, Any]:
    """Compute routing metrics for a set of triage calibration examples."""
    if not examples:
        return {
            "recall_at_k": {f"recall@{k}": 0.0 for k in top_k_values},
            "ece": 0.0,
            "brier": 0.0,
            "candidate_set_size": {},
            "risk_coverage": {"coverage": [], "risk": [], "aurc": 0.0},
        }

    flat_probs: list[float] = []
    flat_labels: list[int] = []
    routed: list[TriageRoutingResult] = []

    for example in examples:
        category_inputs = [
            TriageCategoryInput(category=category, raw_score=score)
            for category, score in example.raw_category_scores.items()
            if category in VALID_CATEGORIES
        ]
        if not category_inputs:
            continue
        routing = route_triage_categories(
            category_inputs,
            calibration_artifact=artifact,
            calibration_artifact_path=None,
        )
        routed.append(routing)
        for category, raw_score in routing.raw_category_scores.items():
            flat_probs.append(
                routing.calibrated_category_scores.get(category, raw_score)
                if artifact is not None
                else raw_score
            )
            flat_labels.append(1 if category in set(example.gold_categories) else 0)

    recall_metrics = {}
    for k in top_k_values:
        recall_metrics[f"recall@{k}"] = recall_at_k(examples, k, artifact)

    candidate_sizes = candidate_set_size_stats(routed)
    ece = expected_calibration_error(flat_probs, flat_labels)
    brier = brier_score(flat_probs, flat_labels)
    risk_coverage = compute_risk_coverage(routed, examples)

    return {
        "recall_at_k": recall_metrics,
        "ece": ece,
        "brier": brier,
        "candidate_set_size": candidate_sizes,
        "risk_coverage": risk_coverage,
    }


def recall_at_k(
    examples: Sequence[TriageCalibrationExample],
    k: int,
    artifact: TriageCalibrationArtifact | None = None,
) -> float:
    """Average recall@k over examples."""
    recalls: list[float] = []
    for example in examples:
        category_inputs = [
            TriageCategoryInput(category=category, raw_score=score)
            for category, score in example.raw_category_scores.items()
            if category in VALID_CATEGORIES
        ]
        if not category_inputs or not example.gold_categories:
            continue
        routing = route_triage_categories(category_inputs, calibration_artifact=artifact)
        ranked = sorted(
            routing.categories,
            key=lambda item: item.calibrated_score,
            reverse=True,
        )
        top_k = {item.category for item in ranked[:k]}
        gold = set(example.gold_categories)
        recalls.append(len(top_k & gold) / len(gold))
    return float(mean(recalls)) if recalls else 0.0


def expected_calibration_error(
    probabilities: Sequence[float],
    labels: Sequence[int],
    *,
    n_bins: int = 10,
) -> float:
    """Binary expected calibration error."""
    if not probabilities:
        return 0.0

    probs = np.asarray(probabilities, dtype=float)
    gold = np.asarray(labels, dtype=float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for lower, upper in zip(bins[:-1], bins[1:]):
        mask = (probs >= lower) & (probs <= upper if upper == 1.0 else probs < upper)
        if not np.any(mask):
            continue
        bin_acc = float(np.mean(gold[mask]))
        bin_conf = float(np.mean(probs[mask]))
        ece += (np.sum(mask) / len(probs)) * abs(bin_acc - bin_conf)
    return float(ece)


def brier_score(probabilities: Sequence[float], labels: Sequence[int]) -> float:
    """Binary Brier score."""
    if not probabilities:
        return 0.0
    probs = np.asarray(probabilities, dtype=float)
    gold = np.asarray(labels, dtype=float)
    return float(np.mean((probs - gold) ** 2))


def candidate_set_size_stats(routings: Sequence[TriageRoutingResult]) -> dict[str, float]:
    """Summarize candidate set sizes."""
    sizes = [len(routing.candidate_disorder_codes) for routing in routings]
    if not sizes:
        return {"mean": 0.0, "median": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
    sorted_sizes = sorted(sizes)
    p95_index = min(len(sorted_sizes) - 1, int(round(0.95 * (len(sorted_sizes) - 1))))
    return {
        "mean": float(mean(sorted_sizes)),
        "median": float(median(sorted_sizes)),
        "p95": float(sorted_sizes[p95_index]),
        "min": float(sorted_sizes[0]),
        "max": float(sorted_sizes[-1]),
    }


def compute_risk_coverage(
    routings: Sequence[TriageRoutingResult],
    examples: Sequence[TriageCalibrationExample],
) -> dict[str, Any]:
    """Compute a selective routing risk-coverage curve."""
    scored = []
    for routing, example in zip(routings, examples):
        gold = set(example.gold_categories)
        if not gold:
            continue
        selected = set(routing.selected_categories)
        confidence = max(
            routing.calibrated_category_scores.values(),
            default=0.0,
        )
        correct = 1.0 if selected & gold else 0.0
        scored.append((confidence, correct))

    if not scored:
        return {"coverage": [], "risk": [], "aurc": 0.0}

    scored.sort(key=lambda item: item[0], reverse=True)
    coverage: list[float] = []
    risk: list[float] = []
    correct_so_far = 0.0

    for idx, (_, is_correct) in enumerate(scored, start=1):
        correct_so_far += is_correct
        cov = idx / len(scored)
        acc = correct_so_far / idx
        coverage.append(float(cov))
        risk.append(float(1.0 - acc))

    if len(coverage) >= 2:
        aurc = 0.0
        for i in range(1, len(coverage)):
            width = coverage[i] - coverage[i - 1]
            height = (risk[i] + risk[i - 1]) / 2.0
            aurc += width * height
    else:
        aurc = float(risk[0])
    return {"coverage": coverage, "risk": risk, "aurc": aurc}
