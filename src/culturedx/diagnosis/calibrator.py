"""Confidence calibrator for diagnosis ranking, abstention, and audit traces.

The calibrator is intentionally non-LLM and split into two paths:

- learned artifact path when a persisted linear calibrator is available
- heuristic fallback path when no artifact exists or loading fails

Both paths produce interpretable feature summaries and machine-readable
decision traces so downstream reviewers can see why a disorder became primary,
comorbid, abstained, or rejected.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from culturedx.core.models import CheckerOutput, EvidenceBrief, ScaleScore

CALIBRATOR_ARTIFACT_SCHEMA_VERSION = 1
DEFAULT_CALIBRATOR_FEATURE_NAMES = (
    "avg_confidence",
    "threshold_ratio",
    "evidence_coverage",
    "core_score",
    "uniqueness_score",
    "margin_score",
    "variance_penalty",
    "info_content_score",
    "scale_score_signal",
    "criteria_met_count",
    "criteria_total_count",
    "met_fraction",
    "met_minus_required",
)

# Common Chinese stop characters that inflate character-set overlap
_ZH_STOP_CHARS = frozenset("的了是我有在不会很也都你他她它这那个人们要和就")


def _evidence_overlaps(a: str, b: str) -> bool:
    """Check if two evidence strings share substantial word-level overlap."""
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    # Character-level set overlap for Chinese text, filtering stop chars
    set_a = set(a) - _ZH_STOP_CHARS
    set_b = set(b) - _ZH_STOP_CHARS
    if not set_a or not set_b:
        return False
    overlap = len(set_a & set_b) / len(set_a | set_b)
    return overlap > 0.5


@dataclass
class CalibratedDiagnosis:
    """A diagnosis with calibrated confidence and decision."""
    disorder_code: str
    confidence: float
    decision: str  # "diagnosis", "abstain", or "rejected"
    placement: str = ""  # "primary", "comorbid", "abstained", "rejected"
    decision_reason: str = ""
    calibration_path: str = ""
    feature_vector: dict[str, float] = field(default_factory=dict)
    decision_trace: dict[str, object] = field(default_factory=dict)
    evidence_coverage: float = 0.0
    avg_criterion_confidence: float = 0.0
    threshold_ratio: float = 0.0
    criteria_met_count: int = 0
    criteria_total_count: int = 0
    # V2 signal fields
    core_score: float = 0.0
    uniqueness_score: float = 0.0
    margin_score: float = 0.0
    variance_penalty: float = 0.0
    info_content_score: float = 0.0
    scale_score_signal: float = 0.0


@dataclass
class CalibrationOutput:
    """Complete calibrator output."""
    primary: CalibratedDiagnosis | None = None
    comorbid: list[CalibratedDiagnosis] = field(default_factory=list)
    abstained: list[CalibratedDiagnosis] = field(default_factory=list)
    rejected: list[CalibratedDiagnosis] = field(default_factory=list)


@dataclass
class CalibratorArtifact:
    """Stable JSON schema for learned diagnosis-calibrator parameters."""

    schema_version: int = CALIBRATOR_ARTIFACT_SCHEMA_VERSION
    artifact_type: str = "diagnosis_calibrator_linear"
    model_type: str = "logistic_regression"
    feature_names: list[str] = field(default_factory=lambda: list(DEFAULT_CALIBRATOR_FEATURE_NAMES))
    weights: dict[str, float] = field(default_factory=dict)
    bias: float = 0.0
    abstain_threshold: float = 0.3
    comorbid_threshold: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_type": self.artifact_type,
            "model_type": self.model_type,
            "feature_names": list(self.feature_names),
            "weights": {k: float(v) for k, v in self.weights.items()},
            "bias": float(self.bias),
            "abstain_threshold": float(self.abstain_threshold),
            "comorbid_threshold": float(self.comorbid_threshold),
            "metadata": dict(self.metadata),
        }

    def save(self, path: str | Path) -> None:
        """Persist the artifact as stable JSON."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalibratorArtifact":
        return cls(
            schema_version=int(data.get("schema_version", CALIBRATOR_ARTIFACT_SCHEMA_VERSION)),
            artifact_type=str(data.get("artifact_type", "diagnosis_calibrator_linear")),
            model_type=str(data.get("model_type", "logistic_regression")),
            feature_names=list(data.get("feature_names", list(DEFAULT_CALIBRATOR_FEATURE_NAMES))),
            weights={str(k): float(v) for k, v in dict(data.get("weights", {})).items()},
            bias=float(data.get("bias", 0.0)),
            abstain_threshold=float(data.get("abstain_threshold", 0.3)),
            comorbid_threshold=float(data.get("comorbid_threshold", 0.5)),
            metadata=dict(data.get("metadata", {})),
        )

    @classmethod
    def load(cls, path: str | Path) -> "CalibratorArtifact":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


class ConfidenceCalibrator:
    """Statistical confidence calibrator for diagnostic decisions.

    No LLM is involved here. The class combines checker outputs, evidence
    coverage, rule-threshold satisfaction, and optional learned parameters into
    a calibrated split between primary, comorbid, abstained, and rejected
    diagnoses.
    """

    def __init__(
        self,
        abstain_threshold: float = 0.3,
        comorbid_threshold: float = 0.5,
        version: int = 2,
        mode: str = "heuristic-v2",
        artifact_path: str | Path | None = None,
        artifact: CalibratorArtifact | dict[str, Any] | None = None,
        force_prediction: bool = False,
        # Comorbidity gate thresholds
        comorbid_ratio_threshold: float = 0.6,
        comorbid_gap_threshold: float = 0.20,
        # V1 weights (backward compat)
        evidence_weight: float = 0.3,
        criterion_weight: float = 0.4,
        threshold_weight: float = 0.3,
    ) -> None:
        if mode not in ("heuristic-v2", "learned"):
            raise ValueError(
                f"Invalid calibrator mode {mode!r}; expected 'heuristic-v2' or 'learned'"
            )

        self.abstain_threshold = abstain_threshold
        self.comorbid_threshold = comorbid_threshold
        self.version = version
        self.mode = mode
        self.force_prediction = force_prediction
        self.comorbid_ratio_threshold = comorbid_ratio_threshold
        self.comorbid_gap_threshold = comorbid_gap_threshold
        self.evidence_weight = evidence_weight
        self.criterion_weight = criterion_weight
        self.threshold_weight = threshold_weight
        self.artifact: CalibratorArtifact | None = None
        self.artifact_path = Path(artifact_path) if artifact_path is not None else None
        if artifact is not None:
            self.artifact = (
                artifact if isinstance(artifact, CalibratorArtifact)
                else CalibratorArtifact.from_dict(artifact)
            )
            self.abstain_threshold = self.artifact.abstain_threshold
            self.comorbid_threshold = self.artifact.comorbid_threshold
        elif mode == "learned":
            if self.artifact_path is None:
                raise ValueError(
                    "Calibrator mode 'learned' requires artifact_path"
                )
            if not self.artifact_path.exists():
                raise FileNotFoundError(
                    f"Calibrator artifact not found at {self.artifact_path}. "
                    "Use mode='heuristic-v2' or provide a valid artifact_path."
                )
            self.artifact = CalibratorArtifact.load(self.artifact_path)
            self.abstain_threshold = self.artifact.abstain_threshold
            self.comorbid_threshold = self.artifact.comorbid_threshold
        # V2 weights — tuned via LOO cross-validation (scripts/tune_calibrator_weights.py)
        # Changes from initial weights:
        #   core_score 0.30->0.05: was inflating short-checklist disorders (F41.1=5
        #     criteria) because type-weighted average favors checklists where every
        #     met criterion is "core" type. Caused F41.1 to outrank F32 (11 criteria).
        #   threshold_ratio 0.207->0.35: strongest single predictor of correct ranking.
        #   variance 0.00->0.10: penalizes disorders with inconsistent criterion
        #     confidence (e.g., one criterion at 0.9, rest at 0.3).
        #   info_content 0.00->0.05: mild tiebreaker; slightly biased toward longer
        #     checklists but useful when threshold_ratio is tied.
        #   uniqueness=0: character-set overlap unreliable for Chinese paraphrased
        #     evidence; kept zeroed until semantic similarity replaces char overlap.
        self.v2_weights = {
            "core_score": 0.05,
            "avg_confidence": 0.207,
            "threshold_ratio": 0.35,
            "evidence_coverage": 0.207,
            "uniqueness": 0.00,
            "margin": 0.08,
            "variance": 0.10,
            "info_content": 0.05,
            "scale_score": 0.05,
        }

    def calibrate(
        self,
        confirmed_disorders: list[str],
        checker_outputs: list[CheckerOutput],
        evidence: EvidenceBrief | None = None,
        confirmation_types: dict[str, str] | None = None,
        scale_scores: list[ScaleScore] | None = None,
    ) -> CalibrationOutput:
        """Calibrate confidence for logic-confirmed disorders.

        ``confirmed_disorders`` comes from the deterministic logic engine.
        This method then scores each confirmed disorder, ranks them, and makes
        the final primary/comorbid/abstain/rejected split while preserving the
        feature-level reasoning used for that decision.
        """
        checker_map = {co.disorder: co for co in checker_outputs}

        # Get confirmed checker outputs for cross-disorder comparison
        confirmed_outputs = [
            checker_map[code] for code in confirmed_disorders
            if code in checker_map
        ]

        scored = []
        for code in confirmed_disorders:
            co = checker_map.get(code)
            if co is None:
                continue
            cal = self._score_disorder(
                code,
                co,
                confirmed_outputs,
                evidence,
                scale_scores,
            )
            scored.append(cal)

        # Apply soft confirmation penalty
        if confirmation_types:
            for cal in scored:
                ctype = confirmation_types.get(cal.disorder_code)
                if ctype:
                    cal.decision_trace["confirmation_type"] = ctype
                if ctype == "soft":
                    cal.confidence *= 0.85

        # Sort by confidence descending
        scored.sort(key=lambda c: c.confidence, reverse=True)

        # Split into primary, comorbid, abstained (unchanged)
        primary = None
        comorbid = []
        abstained = []
        rejected = []

        for rank, cal in enumerate(scored, start=1):
            cal.decision_trace.update({
                "rank": rank,
                "abstain_threshold": self.abstain_threshold,
                "comorbid_threshold": self.comorbid_threshold,
                "confidence": cal.confidence,
                "threshold_ratio": cal.threshold_ratio,
                "evidence_coverage": cal.evidence_coverage,
                "criteria_met_count": cal.criteria_met_count,
                "criteria_total_count": cal.criteria_total_count,
                "calibration_path": cal.calibration_path,
                "force_prediction": self.force_prediction,
            })
            if primary is None and self.force_prediction:
                cal.decision = "diagnosis"
                cal.placement = "primary"
                cal.decision_reason = "forced_highest_confidence"
                primary = cal
            elif cal.confidence < self.abstain_threshold:
                cal.decision = "abstain"
                cal.placement = "abstained"
                cal.decision_reason = "below_abstain_threshold"
                abstained.append(cal)
            elif primary is None:
                cal.decision = "diagnosis"
                cal.placement = "primary"
                cal.decision_reason = "highest_confidence_above_abstain_threshold"
                primary = cal
            elif cal.confidence >= self.comorbid_threshold:
                # Comorbidity gate: met_ratio + confidence gap
                met_ratio = (
                    cal.criteria_met_count / cal.criteria_total_count
                    if cal.criteria_total_count > 0 else 0.0
                )
                gap = primary.confidence - cal.confidence if primary else 0.0
                passes_ratio = met_ratio >= self.comorbid_ratio_threshold
                passes_gap = gap <= self.comorbid_gap_threshold
                cal.decision_trace["comorbid_met_ratio"] = met_ratio
                cal.decision_trace["comorbid_gap"] = gap
                cal.decision_trace["comorbid_ratio_threshold"] = self.comorbid_ratio_threshold
                cal.decision_trace["comorbid_gap_threshold"] = self.comorbid_gap_threshold
                if passes_ratio and passes_gap:
                    cal.decision = "diagnosis"
                    cal.placement = "comorbid"
                    cal.decision_reason = "meets_comorbid_gate"
                    comorbid.append(cal)
                else:
                    cal.decision = "rejected"
                    cal.placement = "rejected"
                    reasons = []
                    if not passes_ratio:
                        reasons.append(f"met_ratio={met_ratio:.3f}<{self.comorbid_ratio_threshold}")
                    if not passes_gap:
                        reasons.append(f"gap={gap:.3f}>{self.comorbid_gap_threshold}")
                    cal.decision_reason = "comorbid_gate_failed:" + ";".join(reasons)
                    rejected.append(cal)
            else:
                cal.decision = "rejected"
                cal.placement = "rejected"
                cal.decision_reason = self._classify_rejection_reason(cal)
                rejected.append(cal)

        return CalibrationOutput(
            primary=primary,
            comorbid=comorbid,
            abstained=abstained,
            rejected=rejected,
        )

    def _classify_rejection_reason(self, diagnosis: CalibratedDiagnosis) -> str:
        """Provide an interpretable reason for non-primary rejection."""
        if diagnosis.threshold_ratio < 1.0:
            return "insufficient_threshold_support"
        if diagnosis.evidence_coverage < 0.25:
            return "insufficient_evidence_coverage"
        return "below_comorbid_threshold"

    def _score_disorder(
        self,
        disorder_code: str,
        checker_output: CheckerOutput,
        all_confirmed_outputs: list[CheckerOutput],
        evidence: EvidenceBrief | None,
        scale_scores: list[ScaleScore] | None,
    ) -> CalibratedDiagnosis:
        """Score one confirmed disorder with either artifact or heuristic path."""
        if self.artifact is not None:
            return self._compute_calibrated_artifact(
                disorder_code,
                checker_output,
                all_confirmed_outputs,
                evidence,
                scale_scores,
            )
        if self.version >= 2:
            return self._compute_calibrated_v2(
                disorder_code,
                checker_output,
                all_confirmed_outputs,
                evidence,
                scale_scores,
            )
        return self._compute_calibrated(disorder_code, checker_output, evidence)

    def _compute_calibrated_artifact(
        self,
        disorder_code: str,
        checker_output: CheckerOutput,
        all_confirmed_outputs: list[CheckerOutput],
        evidence: EvidenceBrief | None,
        scale_scores: list[ScaleScore] | None = None,
    ) -> CalibratedDiagnosis:
        """Score a disorder using a learned linear calibration artifact."""
        feature_map = self._extract_feature_map(
            disorder_code=disorder_code,
            checker_output=checker_output,
            all_confirmed_outputs=all_confirmed_outputs,
            evidence=evidence,
            scale_scores=scale_scores,
        )
        score = self._linear_score(feature_map, self.artifact)
        confidence = self._sigmoid(score)

        decision_trace = {
            "calibration_path": "artifact",
            "artifact_type": self.artifact.artifact_type,
            "schema_version": self.artifact.schema_version,
            "linear_score": score,
            "feature_names": list(self.artifact.feature_names),
            "feature_vector": {name: feature_map.get(name, 0.0) for name in self.artifact.feature_names},
            "metadata": dict(self.artifact.metadata),
        }

        met_criteria = [cr for cr in checker_output.criteria if cr.status == "met"]
        met_count = len(met_criteria)
        total_count = len(checker_output.criteria)
        return CalibratedDiagnosis(
            disorder_code=disorder_code,
            confidence=confidence,
            decision="",
            calibration_path="artifact",
            feature_vector=decision_trace["feature_vector"],
            decision_trace=decision_trace,
            evidence_coverage=feature_map["evidence_coverage"],
            avg_criterion_confidence=feature_map["avg_confidence"],
            threshold_ratio=feature_map["threshold_ratio"],
            criteria_met_count=met_count,
            criteria_total_count=total_count,
            core_score=feature_map["core_score"],
            uniqueness_score=feature_map["uniqueness_score"],
            margin_score=feature_map["margin_score"],
            variance_penalty=feature_map["variance_penalty"],
            info_content_score=feature_map["info_content_score"],
            scale_score_signal=feature_map["scale_score_signal"],
        )

    @staticmethod
    def _sigmoid(value: float) -> float:
        if value >= 0:
            z = math.exp(-value)
            return 1.0 / (1.0 + z)
        z = math.exp(value)
        return z / (1.0 + z)

    @staticmethod
    def _linear_score(feature_map: dict[str, float], artifact: CalibratorArtifact) -> float:
        score = artifact.bias
        for name in artifact.feature_names:
            score += artifact.weights.get(name, 0.0) * feature_map.get(name, 0.0)
        return score

    def _extract_feature_map(
        self,
        disorder_code: str,
        checker_output: CheckerOutput,
        all_confirmed_outputs: list[CheckerOutput],
        evidence: EvidenceBrief | None,
        scale_scores: list[ScaleScore] | None = None,
    ) -> dict[str, float]:
        """Build a stable feature map for both heuristic and learned calibration."""
        met_criteria = [cr for cr in checker_output.criteria if cr.status == "met"]
        avg_conf = (
            sum(cr.confidence for cr in met_criteria) / len(met_criteria)
            if met_criteria
            else 0.0
        )

        from culturedx.ontology.icd10 import get_disorder_threshold
        threshold = get_disorder_threshold(disorder_code)
        required = self._compute_required_from_threshold(
            threshold, checker_output, disorder_code
        )
        threshold_ratio = (
            min(1.0, checker_output.criteria_met_count / required)
            if required > 0
            else (1.0 if checker_output.criteria_met_count > 0 else 0.0)
        )

        evidence_coverage = self._compute_evidence_coverage(
            disorder_code, checker_output, evidence
        )
        core_score = self._compute_core_score(checker_output, disorder_code)
        uniqueness = self._compute_evidence_uniqueness(
            disorder_code, checker_output, all_confirmed_outputs
        )
        margin = self._compute_margin_score(checker_output, disorder_code, required)
        variance = self._compute_variance_penalty(checker_output)
        info_content = self._compute_info_content(checker_output)
        scale_score_sig = self._compute_scale_score_signal(disorder_code, scale_scores)
        met_count = len(met_criteria)
        total_count = len(checker_output.criteria)
        met_fraction = met_count / total_count if total_count > 0 else 0.0
        met_minus_required = float(met_count - required)

        feature_map = {
            "avg_confidence": avg_conf,
            "threshold_ratio": threshold_ratio,
            "evidence_coverage": evidence_coverage,
            "core_score": core_score,
            "uniqueness_score": uniqueness,
            "margin_score": margin,
            "variance_penalty": variance,
            "info_content_score": info_content,
            "scale_score_signal": scale_score_sig,
            "criteria_met_count": float(met_count),
            "criteria_total_count": float(total_count),
            "met_fraction": met_fraction,
            "met_minus_required": met_minus_required,
        }
        return feature_map

    @classmethod
    def fit_linear_artifact(
        cls,
        examples: Sequence[dict[str, float]],
        labels: Sequence[int | bool],
        feature_names: Sequence[str] | None = None,
        abstain_threshold: float = 0.3,
        comorbid_threshold: float = 0.5,
        metadata: dict[str, Any] | None = None,
        c: float = 1.0,
        max_iter: int = 1000,
    ) -> CalibratorArtifact:
        """Fit a simple logistic-regression artifact from feature rows."""
        if len(examples) != len(labels):
            raise ValueError(
                f"examples/labels length mismatch: {len(examples)} vs {len(labels)}"
            )
        if not examples:
            raise ValueError("cannot fit calibrator artifact from empty data")

        names = list(feature_names) if feature_names is not None else cls._infer_feature_names(examples)
        if len(set(int(bool(v)) for v in labels)) < 2:
            raise ValueError("need both positive and negative labels to fit artifact")

        try:
            from sklearn.linear_model import LogisticRegression
        except Exception as exc:  # pragma: no cover - dependency should exist in repo
            raise RuntimeError("scikit-learn is required to fit a calibrator artifact") from exc

        X = [[float(example.get(name, 0.0)) for name in names] for example in examples]
        y = [int(bool(label)) for label in labels]

        model = LogisticRegression(C=c, max_iter=max_iter, random_state=42)
        model.fit(X, y)

        weights = {name: float(weight) for name, weight in zip(names, model.coef_[0])}
        return CalibratorArtifact(
            feature_names=names,
            weights=weights,
            bias=float(model.intercept_[0]),
            abstain_threshold=abstain_threshold,
            comorbid_threshold=comorbid_threshold,
            metadata={
                **(metadata or {}),
                "n_examples": len(examples),
                "positive_rate": float(sum(y) / len(y)),
            },
        )

    @staticmethod
    def _infer_feature_names(examples: Sequence[dict[str, float]]) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for example in examples:
            for name in example.keys():
                if name not in seen:
                    seen.add(name)
                    names.append(name)
        return names

    def extract_calibration_features(
        self,
        disorder_code: str,
        checker_output: CheckerOutput,
        all_confirmed_outputs: list[CheckerOutput],
        evidence: EvidenceBrief | None = None,
        scale_scores: list[ScaleScore] | None = None,
    ) -> dict[str, float]:
        """Public wrapper for building the calibrator feature map.

        This is the safest entry point for training/evaluation scripts that
        need the same feature construction logic as runtime calibration.
        """
        return self._extract_feature_map(
            disorder_code=disorder_code,
            checker_output=checker_output,
            all_confirmed_outputs=all_confirmed_outputs,
            evidence=evidence,
            scale_scores=scale_scores,
        )

    @classmethod
    def load_artifact(cls, path: str | Path) -> CalibratorArtifact:
        """Load a learned calibrator artifact from disk."""
        return CalibratorArtifact.load(path)

    def _compute_calibrated(
        self,
        disorder_code: str,
        checker_output: CheckerOutput,
        evidence: EvidenceBrief | None,
    ) -> CalibratedDiagnosis:
        """Compute calibrated confidence for a single disorder."""
        # 1. Average criterion confidence (for met criteria)
        met_criteria = [
            cr for cr in checker_output.criteria if cr.status == "met"
        ]
        avg_conf = (
            sum(cr.confidence for cr in met_criteria) / len(met_criteria)
            if met_criteria
            else 0.0
        )

        # 2. Threshold satisfaction ratio (use ICD-10 ontology required count)
        from culturedx.ontology.icd10 import get_disorder_threshold
        threshold = get_disorder_threshold(disorder_code)
        required = self._compute_required_from_threshold(
            threshold, checker_output, disorder_code
        )

        if required > 0:
            threshold_ratio = min(1.0, checker_output.criteria_met_count / required)
        else:
            threshold_ratio = 1.0 if checker_output.criteria_met_count > 0 else 0.0

        # 3. Evidence coverage (what fraction of criteria have evidence spans)
        evidence_coverage = self._compute_evidence_coverage(
            disorder_code, checker_output, evidence
        )

        # Weighted combination
        confidence = (
            self.criterion_weight * avg_conf
            + self.threshold_weight * threshold_ratio
            + self.evidence_weight * evidence_coverage
        )
        confidence = max(0.0, min(1.0, confidence))

        met_count = len(met_criteria)
        total_count = len(checker_output.criteria)

        return CalibratedDiagnosis(
            disorder_code=disorder_code,
            confidence=confidence,
            decision="",  # Set by calibrate()
            calibration_path=f"heuristic_v{self.version}",
            feature_vector={
                "avg_confidence": avg_conf,
                "threshold_ratio": threshold_ratio,
                "evidence_coverage": evidence_coverage,
            },
            decision_trace={
                "calibration_path": f"heuristic_v{self.version}",
                "avg_criterion_confidence": avg_conf,
                "threshold_ratio": threshold_ratio,
                "evidence_coverage": evidence_coverage,
            },
            evidence_coverage=evidence_coverage,
            avg_criterion_confidence=avg_conf,
            threshold_ratio=threshold_ratio,
            criteria_met_count=met_count,
            criteria_total_count=total_count,
        )

    def _compute_calibrated_v2(
        self,
        disorder_code: str,
        checker_output: CheckerOutput,
        all_confirmed_outputs: list[CheckerOutput],
        evidence: EvidenceBrief | None,
        scale_scores: list[ScaleScore] | None = None,
    ) -> CalibratedDiagnosis:
        """V2 calibration with weighted signals for disorder differentiation."""
        # Existing signals
        met_criteria = [cr for cr in checker_output.criteria if cr.status == "met"]
        avg_conf = (
            sum(cr.confidence for cr in met_criteria) / len(met_criteria)
            if met_criteria else 0.0
        )

        from culturedx.ontology.icd10 import get_disorder_threshold
        threshold = get_disorder_threshold(disorder_code)
        required = self._compute_required_from_threshold(
            threshold, checker_output, disorder_code
        )
        threshold_ratio = (
            min(1.0, checker_output.criteria_met_count / required)
            if required > 0
            else (1.0 if checker_output.criteria_met_count > 0 else 0.0)
        )

        evidence_coverage = self._compute_evidence_coverage(
            disorder_code, checker_output, evidence
        )

        # NEW V2 signals
        core_score = self._compute_core_score(checker_output, disorder_code)
        uniqueness = self._compute_evidence_uniqueness(
            disorder_code, checker_output, all_confirmed_outputs
        )
        margin = self._compute_margin_score(checker_output, disorder_code, required)
        variance = self._compute_variance_penalty(checker_output)
        info_content = self._compute_info_content(checker_output)
        scale_score_sig = self._compute_scale_score_signal(disorder_code, scale_scores)

        # Weighted combination
        w = self.v2_weights
        confidence = (
            w["core_score"] * core_score
            + w["avg_confidence"] * avg_conf
            + w["threshold_ratio"] * threshold_ratio
            + w["evidence_coverage"] * evidence_coverage
            + w.get("uniqueness", 0) * uniqueness
            + w["margin"] * margin
            + w["variance"] * variance
            + w.get("info_content", 0) * info_content
            + w.get("scale_score", 0) * scale_score_sig
        )
        confidence = max(0.0, min(1.0, confidence))

        met_count = len(met_criteria)
        total_count = len(checker_output.criteria)

        return CalibratedDiagnosis(
            disorder_code=disorder_code,
            confidence=confidence,
            decision="",
            calibration_path="heuristic_v2",
            feature_vector={
                "avg_confidence": avg_conf,
                "threshold_ratio": threshold_ratio,
                "evidence_coverage": evidence_coverage,
                "core_score": core_score,
                "uniqueness_score": uniqueness,
                "margin_score": margin,
                "variance_penalty": variance,
                "info_content_score": info_content,
                "scale_score_signal": scale_score_sig,
            },
            decision_trace={
                "calibration_path": "heuristic_v2",
                "avg_criterion_confidence": avg_conf,
                "threshold_ratio": threshold_ratio,
                "evidence_coverage": evidence_coverage,
                "core_score": core_score,
                "uniqueness_score": uniqueness,
                "margin_score": margin,
                "variance_penalty": variance,
                "info_content_score": info_content,
                "scale_score_signal": scale_score_sig,
            },
            evidence_coverage=evidence_coverage,
            avg_criterion_confidence=avg_conf,
            threshold_ratio=threshold_ratio,
            criteria_met_count=met_count,
            criteria_total_count=total_count,
            core_score=core_score,
            uniqueness_score=uniqueness,
            margin_score=margin,
            variance_penalty=variance,
            info_content_score=info_content,
            scale_score_signal=scale_score_sig,
        )

    @staticmethod
    def _compute_scale_score_signal(
        disorder_code: str,
        scale_scores: list[ScaleScore] | None,
    ) -> float:
        """Map scale scores to a confidence signal [0, 1] for the given disorder.

        Returns 0.5 (neutral) if no matching scale is available, so the signal
        neither helps nor hurts when scale data is absent.

        Thresholds follow standard clinical cut-offs:
        - PHQ-8/9 for F32/F33: <10->0.0, 10-14->0.3, 15-19->0.6, >=20->1.0
        - HAMD-17 for F32/F33: <8->0.0, 8-16->0.4, 17-24->0.7, >=25->1.0
        - GAD-7 for F41/F41.1: <10->0.0, 10-14->0.3, 15-21->0.7
        """
        if not scale_scores:
            return 0.5

        # Build name -> total lookup
        scores = {s.name.lower(): s.total for s in scale_scores}

        # Depression disorders: F32.x, F33.x
        if disorder_code.startswith(("F32", "F33")):
            # Check PHQ-8/9 first, then HAMD-17
            for name in ("phq8", "phq9"):
                if name in scores:
                    total = scores[name]
                    if total < 10:
                        return 0.0
                    if total < 15:
                        return 0.3
                    if total < 20:
                        return 0.6
                    return 1.0
            if "hamd17" in scores:
                total = scores["hamd17"]
                if total < 8:
                    return 0.0
                if total < 17:
                    return 0.4
                if total < 25:
                    return 0.7
                return 1.0

        # Anxiety disorders: F41, F41.1
        if disorder_code.startswith("F41"):
            if "gad7" in scores:
                total = scores["gad7"]
                if total < 10:
                    return 0.0
                if total < 15:
                    return 0.3
                return 0.7

        return 0.5

    @staticmethod
    def _compute_core_score(checker_output: CheckerOutput, disorder_code: str) -> float:
        """Weighted criterion score: core criteria count 1.5x, duration 1.3x, others 1.0x."""
        from culturedx.ontology.icd10 import get_disorder_criteria
        criteria_def = get_disorder_criteria(disorder_code) or {}

        TYPE_WEIGHTS = {
            "core": 1.5,
            "duration": 1.3,
            "first_rank": 1.5,
            "exclusion": 1.2,
        }

        weighted_sum = 0.0
        max_possible = 0.0
        for cr in checker_output.criteria:
            cdef = criteria_def.get(cr.criterion_id, {})
            ctype = cdef.get("type", "")
            w = TYPE_WEIGHTS.get(ctype, 1.0)
            max_possible += w
            if cr.status == "met":
                weighted_sum += w * cr.confidence

        return weighted_sum / max_possible if max_possible > 0 else 0.0

    @staticmethod
    def _compute_evidence_uniqueness(
        disorder_code: str,
        checker_output: CheckerOutput,
        all_confirmed_outputs: list[CheckerOutput],
    ) -> float:
        """Fraction of met criteria whose evidence is unique to this disorder."""
        met_criteria = [cr for cr in checker_output.criteria if cr.status == "met"]
        if not met_criteria:
            return 0.0

        # Collect evidence texts from other confirmed disorders
        other_evidence: set[str] = set()
        for co in all_confirmed_outputs:
            if co.disorder == disorder_code:
                continue
            for cr in co.criteria:
                if cr.status == "met" and cr.evidence and cr.evidence.strip():
                    other_evidence.add(cr.evidence.strip().lower())

        if not other_evidence:
            return 1.0  # No other disorders — all evidence unique

        unique = 0
        total_with_evidence = 0
        for cr in met_criteria:
            if cr.evidence and cr.evidence.strip():
                total_with_evidence += 1
                normalized = cr.evidence.strip().lower()
                # Check for word-level overlap with any other disorder's evidence
                is_shared = any(
                    _evidence_overlaps(normalized, other_ev)
                    for other_ev in other_evidence
                )
                if not is_shared:
                    unique += 1

        return unique / total_with_evidence if total_with_evidence > 0 else 0.5

    @staticmethod
    def _compute_margin_score(
        checker_output: CheckerOutput, disorder_code: str, required: int,
    ) -> float:
        """Score for how far criteria met exceeds the minimum threshold.

        Normalized by max possible excess for the disorder so that
        F41.1 (5 criteria, threshold 4, max excess 1) and F32 (11
        criteria, threshold 4, max excess 7) are on equal footing when
        all criteria are met.
        """
        import math

        met_count = sum(1 for cr in checker_output.criteria if cr.status == "met")
        total_criteria = len(checker_output.criteria)

        if required <= 0:
            return 0.5

        excess = met_count - required
        if excess <= 0:
            return 0.0

        max_excess = max(total_criteria - required, 1)
        excess_ratio = excess / max_excess  # [0, 1] regardless of checklist length
        return min(1.0, math.log1p(excess_ratio * 7) / math.log(8))

    @staticmethod
    def _compute_variance_penalty(checker_output: CheckerOutput) -> float:
        """Penalty for high variance in criterion confidence. Returns [0, 1]."""
        met_criteria = [cr for cr in checker_output.criteria if cr.status == "met"]
        if len(met_criteria) <= 1:
            return 1.0

        confs = [cr.confidence for cr in met_criteria]
        mean = sum(confs) / len(confs)
        variance = sum((c - mean) ** 2 for c in confs) / len(confs)
        normalized_var = min(1.0, variance / 0.25)
        return 1.0 - normalized_var

    @staticmethod
    def _compute_info_content(checker_output: CheckerOutput) -> float:
        """Information content: rewards more met criteria in absolute terms.
        
        A diagnosis supported by 8 met criteria has more diagnostic evidence
        than one supported by 4 criteria, regardless of total criteria count.
        Saturates at 8 met criteria.
        """
        import math
        met_count = sum(1 for cr in checker_output.criteria if cr.status == "met")
        # Sigmoid-like scaling: 1→0.12, 3→0.35, 5→0.58, 7→0.80, 8→0.88, 10→1.0
        return min(1.0, math.log1p(met_count) / math.log1p(10))

    @staticmethod
    def _compute_evidence_coverage(
        disorder_code: str,
        checker_output: CheckerOutput,
        evidence: EvidenceBrief | None,
    ) -> float:
        """Compute what fraction of met criteria have supporting evidence.

        Normalized by met criteria count (not total) to avoid penalizing
        disorders with more criteria, where unmet criteria naturally lack evidence.
        """
        if not evidence:
            met_criteria = [
                cr for cr in checker_output.criteria if cr.status == "met"
            ]
            total_met = len(met_criteria)
            if total_met == 0:
                return 0.0
            has_evidence = sum(
                1 for cr in met_criteria
                if cr.evidence is not None and cr.evidence.strip()
            )
            return has_evidence / total_met

        # With evidence brief, check disorder-specific evidence
        # Weight by uniqueness: unique evidence contributes full credit,
        # shared evidence contributes partial credit (min 0.3)
        for de in evidence.disorder_evidence:
            if de.disorder_code == disorder_code:
                met_criteria_ids = {
                    cr.criterion_id for cr in checker_output.criteria
                    if cr.status == "met"
                }
                total_met = len(met_criteria_ids)
                if total_met == 0:
                    return 0.0
                weighted_coverage = 0.0
                for ce in de.criteria_evidence:
                    if ce.spans and ce.criterion_id in met_criteria_ids:
                        # Scale by uniqueness: 1.0 for unique, 0.3 min for shared
                        weight = max(0.3, getattr(ce, "uniqueness_score", 1.0))
                        weighted_coverage += weight
                return min(1.0, weighted_coverage / total_met)

        return 0.0

    @staticmethod
    def _compute_required_from_threshold(
        threshold: dict, checker_output: CheckerOutput, disorder_code: str
    ) -> int:
        """Compute the effective required criterion count from ICD-10 threshold.

        Handles all threshold schemas to ensure fair confidence comparison
        across disorders with different threshold types.
        """
        if not threshold:
            return max(checker_output.criteria_required, 1)

        # Schema: min_core + min_total (F32, F33)
        if "min_total" in threshold:
            return max(threshold["min_total"], threshold.get("min_core", 0))

        # Schema: min_symptoms (F41.1 GAD)
        if "min_symptoms" in threshold:
            return threshold["min_symptoms"]

        # Schema: all_required (F22)
        if threshold.get("all_required"):
            from culturedx.ontology.icd10 import get_disorder_criteria
            criteria = get_disorder_criteria(disorder_code)
            return len(criteria) if criteria else checker_output.criteria_required

        # Schema: min_first_rank + min_other (F20)
        if "min_first_rank" in threshold and "min_other" in threshold:
            # Easier path: 1 first-rank symptom
            return threshold["min_first_rank"]

        # Schema: core_required + min_additional (F40)
        if "min_additional" in threshold:
            from culturedx.ontology.icd10 import get_disorder_criteria
            criteria = get_disorder_criteria(disorder_code) or {}
            core_count = sum(
                1 for v in criteria.values() if v.get("type") == "core"
            )
            return core_count + threshold["min_additional"]

        # Schema: attacks_per_month + min_symptoms_per_attack (F41.0)
        if "min_symptoms_per_attack" in threshold:
            from culturedx.ontology.icd10 import get_disorder_criteria
            criteria = get_disorder_criteria(disorder_code) or {}
            core_count = sum(
                1 for v in criteria.values() if v.get("type") == "core"
            )
            return core_count + threshold["min_symptoms_per_attack"]

        # Schema: min_episodes + at_least_one_manic (F31)
        if "min_episodes" in threshold:
            return 2  # core + manic

        # Schema: duration_weeks + distress_required (F42 OCD)
        if "distress_required" in threshold:
            return 3  # core + distress + obs/comp

        # Schema: frequency_per_week (F51)
        if "frequency_per_week" in threshold:
            return 2  # core + at least 1 symptom, as logic engine requires

        # Schema: trauma_required (F43.1 PTSD)
        if "trauma_required" in threshold:
            from culturedx.ontology.icd10 import get_disorder_criteria
            criteria = get_disorder_criteria(disorder_code) or {}
            return len(criteria) if criteria else 3

        # Schema: min_somatic_groups (F45)
        if "min_somatic_groups" in threshold:
            return threshold["min_somatic_groups"] + 1  # groups + core

        # Schema: onset_within_month (F43.2 adjustment)
        if "onset_within_month" in threshold:
            from culturedx.ontology.icd10 import get_disorder_criteria
            criteria = get_disorder_criteria(disorder_code) or {}
            return len(criteria) if criteria else 2

        # Fallback
        return max(checker_output.criteria_required, 1)
