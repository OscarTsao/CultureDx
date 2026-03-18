"""Evidence quality metrics: criterion coverage and evidence precision."""
from __future__ import annotations

from culturedx.core.models import EvidenceBrief


def criterion_coverage(
    brief: EvidenceBrief,
    gold_criteria: dict[str, list[str]],
) -> float:
    """Fraction of gold criteria with at least one evidence span.

    Args:
        brief: The assembled evidence brief.
        gold_criteria: Dict mapping disorder_code -> list of criterion_ids
            that are known to be present (ground truth).

    Returns:
        Coverage score between 0.0 and 1.0.
    """
    if not gold_criteria:
        return 0.0

    total_gold = sum(len(v) for v in gold_criteria.values())
    if total_gold == 0:
        return 0.0

    # Build set of criteria with evidence
    covered = set()
    for de in brief.disorder_evidence:
        for ce in de.criteria_evidence:
            if ce.spans:
                covered.add(ce.criterion_id)

    # Count how many gold criteria are covered
    hit = 0
    for disorder_code, crit_ids in gold_criteria.items():
        for cid in crit_ids:
            full_id = f"{disorder_code}.{cid}" if "." not in cid else cid
            if full_id in covered:
                hit += 1

    return hit / total_gold


def evidence_precision(
    brief: EvidenceBrief,
    gold_criteria: dict[str, list[str]],
) -> float:
    """Fraction of extracted evidence criteria that match gold.

    Args:
        brief: The assembled evidence brief.
        gold_criteria: Dict mapping disorder_code -> list of criterion_ids.

    Returns:
        Precision score between 0.0 and 1.0.
    """
    if not gold_criteria:
        return 0.0

    # Build set of gold criterion full IDs
    gold_set = set()
    for disorder_code, crit_ids in gold_criteria.items():
        for cid in crit_ids:
            full_id = f"{disorder_code}.{cid}" if "." not in cid else cid
            gold_set.add(full_id)

    # Count extracted criteria with evidence
    total_extracted = 0
    relevant = 0
    for de in brief.disorder_evidence:
        for ce in de.criteria_evidence:
            if ce.spans:
                total_extracted += 1
                if ce.criterion_id in gold_set:
                    relevant += 1

    if total_extracted == 0:
        return 0.0

    return relevant / total_extracted


def compute_evidence_quality_metrics(
    brief: EvidenceBrief,
    gold_criteria: dict[str, list[str]],
) -> dict[str, float]:
    """Compute both evidence quality metrics.

    Returns:
        Dict with 'criterion_coverage' and 'evidence_precision' keys.
    """
    return {
        "criterion_coverage": criterion_coverage(brief, gold_criteria),
        "evidence_precision": evidence_precision(brief, gold_criteria),
    }
