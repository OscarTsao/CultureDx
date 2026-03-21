"""Shared criteria registry for contrastive disambiguation between disorders."""
from __future__ import annotations

from dataclasses import dataclass, replace

from culturedx.core.models import CheckerOutput, CriterionResult


@dataclass(frozen=True)
class SharedCriterionPair:
    """A pair of criteria from two disorders that evaluate the same symptom domain."""

    symptom_domain: str
    disorder_a: str
    criterion_a: str
    disorder_b: str
    criterion_b: str
    disambiguation_hint_en: str
    disambiguation_hint_zh: str


# Registry keyed by frozenset of disorder codes for order-independent lookup.
SHARED_CRITERIA: dict[frozenset[str], list[SharedCriterionPair]] = {
    frozenset({"F32", "F41.1"}): [
        SharedCriterionPair(
            symptom_domain="concentration",
            disorder_a="F32",
            criterion_a="C4",
            disorder_b="F41.1",
            criterion_b="B3",
            disambiguation_hint_en=(
                "Depressive concentration loss: linked to low mood, anhedonia, or "
                "psychomotor retardation. Patient loses interest in tasks. "
                "Anxiety concentration loss: linked to excessive worry, mind racing, "
                "or intrusive thoughts. Patient cannot focus because of worry. "
                "Key: Is poor concentration linked to low mood or to worry?"
            ),
            disambiguation_hint_zh=(
                "抑郁性注意力减退：与情绪低落、兴趣丧失或精神运动迟滞相关。"
                "患者对事物失去兴趣，无法集中注意力。"
                "焦虑性注意力减退：与过度担忧、思维奔逸或侵入性想法相关。"
                "患者因担忧而无法集中注意力。"
                "关键鉴别：注意力下降是因为情绪低落还是因为过度担忧？"
            ),
        ),
        SharedCriterionPair(
            symptom_domain="sleep",
            disorder_a="F32",
            criterion_a="C6",
            disorder_b="F41.1",
            criterion_b="B4",
            disambiguation_hint_en=(
                "Depressive insomnia: early morning awakening, rumination about past "
                "failures/guilt, hypersomnia also possible. "
                "Anxiety insomnia: difficulty falling asleep due to racing worried "
                "thoughts about future events, restless/unsatisfying sleep. "
                "Key: Is sleep disrupted by rumination (past) or worry (future)?"
            ),
            disambiguation_hint_zh=(
                "抑郁性失眠：早醒，反复回忆过去的失败/内疚，也可能出现嗜睡。"
                "焦虑性失眠：因对未来的担忧而入睡困难，睡眠不安宁、不满意。"
                "关键鉴别：睡眠障碍是因为反刍过去还是担忧未来？"
            ),
        ),
        SharedCriterionPair(
            symptom_domain="psychomotor",
            disorder_a="F32",
            criterion_a="C5",
            disorder_b="F41.1",
            criterion_b="B1",
            disambiguation_hint_en=(
                "Depressive psychomotor change: purposeless agitation (hand-wringing, "
                "pacing) OR retardation (slowed speech, reduced movement). "
                "Anxiety motor tension: tension-driven restlessness, fidgeting, "
                "inability to relax, muscle tension, hypervigilant scanning. "
                "Key: Is the agitation purposeless/distressed (depression) or "
                "tension-driven/hypervigilant (anxiety)?"
            ),
            disambiguation_hint_zh=(
                "抑郁性精神运动改变：无目的的激越（搓手、踱步）或迟滞"
                "（言语减少、动作迟缓）。"
                "焦虑性运动紧张：紧张驱动的坐立不安、无法放松、肌肉紧张、"
                "过度警觉。"
                "关键鉴别：激越是无目的的（抑郁）还是紧张驱动的（焦虑）？"
            ),
        ),
        SharedCriterionPair(
            symptom_domain="fatigue",
            disorder_a="F32",
            criterion_a="B3",
            disorder_b="F41.1",
            criterion_b="B1",
            disambiguation_hint_en=(
                "Depressive fatigue: anergic, present even after rest, no motivation, "
                "patient does not want to get out of bed. "
                "Anxiety fatigue: exhausted from sustained tension and worry, "
                "recovers with relaxation, driven by hyperarousal. "
                "Key: Is the patient fatigued even when not worrying?"
            ),
            disambiguation_hint_zh=(
                "抑郁性疲劳：即使休息后也感到疲惫、缺乏动力、什么都不想做。"
                "患者在静止状态下就感到疲倦。"
                "焦虑性疲劳：因长时间紧张和担忧而筋疲力尽，放松后可恢复。"
                "关键鉴别：患者在不担忧的时候是否仍然疲劳？"
            ),
        ),
    ],
}


def get_shared_pairs(disorder_a: str, disorder_b: str) -> list[SharedCriterionPair]:
    """Lookup shared criteria for a disorder pair. Order-independent."""
    return SHARED_CRITERIA.get(frozenset({disorder_a, disorder_b}), [])


def apply_attribution(
    criterion_result: CriterionResult,
    attribution_confidence: float,
    attribution_target: str,
    this_disorder: str,
) -> CriterionResult:
    """Apply contrastive attribution to a criterion result.

    Returns the original object unchanged if this disorder is the primary
    or if the attribution is 'both'. Otherwise, applies a confidence-gated
    downgrade: high (>=0.8) full, medium (0.6-0.8) partial, low (<0.6) minimal.
    """
    if attribution_target == "both" or attribution_target == this_disorder:
        return criterion_result

    if attribution_confidence >= 0.8:
        return replace(
            criterion_result,
            status="insufficient_evidence",
            confidence=criterion_result.confidence * 0.3,
        )
    elif attribution_confidence >= 0.6:
        return replace(
            criterion_result,
            confidence=criterion_result.confidence * 0.5,
        )
    else:
        return replace(
            criterion_result,
            confidence=criterion_result.confidence * 0.8,
        )


def apply_attributions_to_checker_output(
    checker_output: CheckerOutput,
    attribution_map: dict[tuple[str, str], tuple[float, str]],
) -> CheckerOutput:
    """Apply deduped attributions to a single CheckerOutput.

    attribution_map: {(disorder, criterion_id): (attribution_confidence, target_disorder)}
    Only entries matching this checker_output's disorder are applied.
    """
    disorder = checker_output.disorder
    new_criteria = []
    for cr in checker_output.criteria:
        key = (disorder, cr.criterion_id)
        if key in attribution_map:
            conf, target = attribution_map[key]
            new_criteria.append(apply_attribution(cr, conf, target, disorder))
        else:
            new_criteria.append(cr)
    new_met_count = sum(1 for c in new_criteria if c.status == "met")
    return replace(
        checker_output,
        criteria=new_criteria,
        criteria_met_count=new_met_count,
    )
