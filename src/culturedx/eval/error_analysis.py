"""Systematic error taxonomy for diagnostic pipeline failures.

Classifies prediction errors by pipeline stage and error type to identify
the primary bottlenecks for accuracy improvement.
"""
from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Taxonomy of diagnostic error types by pipeline stage."""
    # Triage errors
    TRIAGE_MISS = "triage_missed_gold_category"
    TRIAGE_FALSE_ALARM = "triage_included_wrong_category"

    # Criterion checker errors
    CHECKER_FALSE_MET = "criterion_met_but_incorrect"
    CHECKER_MISSED_MET = "criterion_not_met_but_should_be"
    CHECKER_INSUFFICIENT = "criterion_insufficient_evidence"

    # Logic engine errors
    LOGIC_FALSE_CONFIRM = "threshold_met_but_diagnosis_wrong"
    LOGIC_FALSE_REJECT = "threshold_not_met_but_diagnosis_correct"

    # Calibrator / ranking errors
    CALIBRATOR_RANK_SWAP = "correct_disorder_outranked_by_wrong"
    CALIBRATOR_ABSTAIN = "abstained_when_should_diagnose"

    # Ontology errors
    ONTOLOGY_NOT_COVERED = "gold_diagnosis_not_in_icd10_ontology"

    # Comorbidity errors
    COMORBID_MISSED = "comorbidity_not_detected"
    COMORBID_WRONG_PRIMARY = "comorbid_correct_but_primary_wrong"


@dataclass
class CaseError:
    """A single error attribution for one case."""
    case_id: str
    error_type: ErrorType
    predicted: str | None
    gold: str
    stage: str
    detail: str = ""


@dataclass
class ErrorSummary:
    """Aggregated error analysis results."""
    total_cases: int
    total_correct: int
    total_errors: int
    error_counts: dict[str, int] = field(default_factory=dict)
    stage_counts: dict[str, int] = field(default_factory=dict)
    confusion_pairs: dict[str, int] = field(default_factory=dict)
    errors: list[CaseError] = field(default_factory=list)


class ErrorTaxonomyCollector:
    """Collect and categorize prediction errors across an evaluation run.

    Analyzes predictions against gold labels and attributes errors to
    specific pipeline stages using the criteria_results in predictions.
    """

    def __init__(self, ontology_codes: set[str] | None = None):
        self.errors: list[CaseError] = []
        self.ontology_codes = ontology_codes or self._default_ontology_codes()

    @staticmethod
    def _default_ontology_codes() -> set[str]:
        """ICD-10 disorder codes covered by the ontology."""
        return {
            "F20", "F22", "F31", "F32", "F33", "F40",
            "F41", "F41.0", "F41.1", "F42", "F43", "F43.1",
            "F43.2", "F45", "F51",
        }

    def analyze_case(
        self,
        case_id: str,
        predicted: str | None,
        gold: str,
        confidence: float = 0.0,
        criteria_results: list[dict] | None = None,
    ) -> list[CaseError]:
        """Analyze a single case and attribute errors.

        Args:
            case_id: Case identifier.
            predicted: Predicted primary diagnosis (None for abstention).
            gold: Gold-standard diagnosis code.
            confidence: Prediction confidence.
            criteria_results: List of checker output dicts from predictions.json.

        Returns:
            List of CaseError objects for this case (empty if correct).
        """
        case_errors = []

        # Check parent-code matching
        is_correct = self._codes_match(predicted, gold) if predicted else False

        if is_correct:
            return []

        # === Error attribution ===

        # 1. Ontology coverage
        gold_parent = gold.split(".")[0] if "." in gold else gold
        if gold_parent not in self.ontology_codes and gold not in self.ontology_codes:
            case_errors.append(CaseError(
                case_id=case_id,
                error_type=ErrorType.ONTOLOGY_NOT_COVERED,
                predicted=predicted,
                gold=gold,
                stage="ontology",
                detail=f"Gold {gold} not in ontology ({len(self.ontology_codes)} codes)",
            ))
            self.errors.extend(case_errors)
            return case_errors

        # 2. Abstention error
        if predicted is None:
            case_errors.append(CaseError(
                case_id=case_id,
                error_type=ErrorType.CALIBRATOR_ABSTAIN,
                predicted=None,
                gold=gold,
                stage="calibrator",
                detail=f"Abstained (conf={confidence:.3f})",
            ))
            self.errors.extend(case_errors)
            return case_errors

        # 3. Analyze criteria_results if available
        if criteria_results:
            gold_checker = self._find_checker_for_gold(criteria_results, gold)
            pred_checker = self._find_checker_for_gold(criteria_results, predicted)

            if gold_checker is None:
                # Gold disorder wasn't even checked (triage miss)
                case_errors.append(CaseError(
                    case_id=case_id,
                    error_type=ErrorType.TRIAGE_MISS,
                    predicted=predicted,
                    gold=gold,
                    stage="triage",
                    detail=f"Gold {gold} not in checker outputs",
                ))
            else:
                # Gold was checked -- analyze threshold
                gold_met = gold_checker.get("criteria_met_count", 0)
                gold_required = gold_checker.get("criteria_required", 0)

                if gold_met < gold_required:
                    # Gold below threshold (logic engine rejection)
                    # Count insufficient_evidence criteria
                    criteria = gold_checker.get("criteria", [])
                    n_insufficient = sum(
                        1 for c in criteria
                        if isinstance(c, dict) and c.get("status") == "insufficient_evidence"
                    )
                    case_errors.append(CaseError(
                        case_id=case_id,
                        error_type=ErrorType.LOGIC_FALSE_REJECT,
                        predicted=predicted,
                        gold=gold,
                        stage="logic_engine",
                        detail=f"Gold {gold} met={gold_met}/{gold_required}, "
                               f"insufficient_evidence={n_insufficient}",
                    ))
                else:
                    # Gold passed threshold but was outranked
                    case_errors.append(CaseError(
                        case_id=case_id,
                        error_type=ErrorType.CALIBRATOR_RANK_SWAP,
                        predicted=predicted,
                        gold=gold,
                        stage="calibrator",
                        detail=f"Gold {gold} met={gold_met}/{gold_required} confirmed, "
                               f"but {predicted} ranked higher",
                    ))
        else:
            # No criteria_results -- generic misclassification
            case_errors.append(CaseError(
                case_id=case_id,
                error_type=ErrorType.CALIBRATOR_RANK_SWAP,
                predicted=predicted,
                gold=gold,
                stage="calibrator",
                detail=f"Predicted {predicted} instead of {gold} (no criteria data)",
            ))

        self.errors.extend(case_errors)
        return case_errors

    def summarize(self) -> ErrorSummary:
        """Generate aggregated error summary."""
        error_counts = Counter(e.error_type.value for e in self.errors)
        stage_counts = Counter(e.stage for e in self.errors)
        confusion_pairs = Counter(
            f"{e.gold}->{e.predicted or 'abstain'}" for e in self.errors
        )

        total_errors = len(set(e.case_id for e in self.errors))

        return ErrorSummary(
            total_cases=0,  # Set by caller
            total_correct=0,  # Set by caller
            total_errors=total_errors,
            error_counts=dict(error_counts.most_common()),
            stage_counts=dict(stage_counts.most_common()),
            confusion_pairs=dict(confusion_pairs.most_common(20)),
            errors=self.errors,
        )

    def format_summary(self, summary: ErrorSummary) -> str:
        """Format error summary as markdown."""
        lines = [
            f"## Error Taxonomy Summary",
            f"",
            f"Total: {summary.total_cases} cases, "
            f"{summary.total_correct} correct ({summary.total_correct/max(summary.total_cases,1)*100:.1f}%), "
            f"{summary.total_errors} errors",
            "",
            "### By Error Type",
            "| Error Type | Count | % of Errors |",
            "|------------|-------|-------------|",
        ]
        for etype, count in sorted(
            summary.error_counts.items(), key=lambda x: -x[1]
        ):
            pct = count / max(len(self.errors), 1) * 100
            lines.append(f"| {etype} | {count} | {pct:.1f}% |")

        lines.extend([
            "",
            "### By Pipeline Stage",
            "| Stage | Count | % of Errors |",
            "|-------|-------|-------------|",
        ])
        for stage, count in sorted(
            summary.stage_counts.items(), key=lambda x: -x[1]
        ):
            pct = count / max(len(self.errors), 1) * 100
            lines.append(f"| {stage} | {count} | {pct:.1f}% |")

        lines.extend([
            "",
            "### Top Confusion Pairs",
            "| Gold -> Predicted | Count |",
            "|-----------------|-------|",
        ])
        for pair, count in list(summary.confusion_pairs.items())[:10]:
            lines.append(f"| {pair} | {count} |")

        return "\n".join(lines)

    @staticmethod
    def _codes_match(predicted: str | None, gold: str) -> bool:
        """Check if predicted matches gold with parent-code matching."""
        if predicted is None:
            return False
        if predicted == gold:
            return True
        # Parent matching: F41.1 matches F41, F32 matches F32.x
        if predicted.startswith(gold) or gold.startswith(predicted):
            return True
        return False

    @staticmethod
    def _find_checker_for_gold(
        criteria_results: list[dict], gold: str
    ) -> dict | None:
        """Find the checker output matching the gold diagnosis."""
        gold_parent = gold.split(".")[0] if "." in gold else gold
        for cr in criteria_results:
            disorder = cr.get("disorder", "")
            if disorder == gold or disorder.startswith(gold) or gold.startswith(disorder):
                return cr
        return None


def analyze_predictions_file(
    predictions_path: str | Path,
    gold_labels: dict[str, str] | None = None,
) -> ErrorSummary:
    """Run error taxonomy analysis on a predictions.json file.

    Args:
        predictions_path: Path to predictions.json.
        gold_labels: Optional case_id -> gold diagnosis mapping.
            If None, reads gold_diagnosis from prediction entries.

    Returns:
        ErrorSummary with full error breakdown.
    """
    with open(predictions_path, encoding="utf-8") as f:
        predictions = json.load(f)

    collector = ErrorTaxonomyCollector()
    n_correct = 0

    for pred in predictions:
        case_id = pred.get("case_id", "")
        predicted = pred.get("primary_diagnosis")
        confidence = pred.get("confidence", 0.0)
        criteria_results = pred.get("criteria_results", [])

        if gold_labels and case_id in gold_labels:
            gold = gold_labels[case_id]
        elif "gold_diagnosis" in pred:
            gold = pred["gold_diagnosis"]
        else:
            continue

        errors = collector.analyze_case(
            case_id=case_id,
            predicted=predicted,
            gold=gold,
            confidence=confidence,
            criteria_results=criteria_results,
        )
        if not errors:
            n_correct += 1

    summary = collector.summarize()
    summary.total_cases = len(predictions)
    summary.total_correct = n_correct

    return summary
