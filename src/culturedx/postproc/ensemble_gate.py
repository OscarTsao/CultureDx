"""Confidence-gated routing between MAS and TF-IDF predictions."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Literal

PAPER_12_CLASSES: tuple[str, ...] = (
    "F20",
    "F31",
    "F32",
    "F39",
    "F41",
    "F42",
    "F43",
    "F45",
    "F51",
    "F98",
    "Z71",
    "Others",
)
_PAPER_12_CLASS_SET = set(PAPER_12_CLASSES)


def paper_parent(code: str | None) -> str:
    """Collapse a code to the parent label used by the ensemble gate."""
    if not code:
        return "Others"
    return str(code).strip().upper().split(".")[0]


def _paper_label(code: str | None) -> str:
    parent = paper_parent(code)
    return parent if parent in _PAPER_12_CLASS_SET else "Others"


def _extract_ranked_codes(record: dict[str, Any]) -> list[str]:
    for key in ("ranked_codes", "ranked_diagnoses"):
        ranked = record.get(key)
        if isinstance(ranked, list) and ranked:
            if isinstance(ranked[0], str):
                return [str(code) for code in ranked if code]
            if isinstance(ranked[0], dict):
                return [str(item["code"]) for item in ranked if item.get("code")]

    decision_trace = record.get("decision_trace")
    if isinstance(decision_trace, dict):
        diagnostician = decision_trace.get("diagnostician")
        if isinstance(diagnostician, dict):
            ranked = diagnostician.get("ranked_codes")
            if isinstance(ranked, list):
                return [str(code) for code in ranked if code]
        ranked = decision_trace.get("diagnostician_ranked")
        if isinstance(ranked, list):
            return [str(code) for code in ranked if code]

    ordered: list[str] = []
    primary = record.get("primary_diagnosis")
    if primary:
        ordered.append(str(primary))
    for code in record.get("comorbid_diagnoses") or []:
        if code and code not in ordered:
            ordered.append(str(code))
    return ordered


@dataclass
class EnsembleConfig:
    rule: Literal["v1_class_based", "v2_prob_threshold"] = "v1_class_based"
    mas_strong_classes: tuple[str, ...] = ("F32", "F41")
    tfidf_threshold_high: float = 0.4


def apply_ensemble(
    mas_pred: dict[str, Any],
    tfidf_pred: dict[str, Any],
    config: EnsembleConfig,
) -> dict[str, Any]:
    """Route between MAS and TF-IDF predictions under a simple ensemble gate."""
    mas_primary_parent = _paper_label(mas_pred.get("primary_diagnosis"))
    tfidf_primary_parent = _paper_label(tfidf_pred.get("primary_diagnosis"))
    strong_classes = {paper_parent(code) for code in config.mas_strong_classes}

    tfidf_scores = tfidf_pred.get("proba_scores") or []
    tfidf_top_prob = float(tfidf_scores[0]) if tfidf_scores else 0.0

    use_source = "mas" if mas_primary_parent in strong_classes else "tfidf"

    if config.rule == "v2_prob_threshold":
        if (
            tfidf_top_prob >= config.tfidf_threshold_high
            and tfidf_primary_parent not in strong_classes
        ):
            use_source = "tfidf"
    elif config.rule != "v1_class_based":
        raise ValueError(f"Unsupported ensemble rule: {config.rule}")

    selected = mas_pred if use_source == "mas" else tfidf_pred
    result = copy.deepcopy(mas_pred)
    result["primary_diagnosis"] = selected.get("primary_diagnosis")
    result["comorbid_diagnoses"] = list(selected.get("comorbid_diagnoses") or [])
    result["confidence"] = (
        float(selected.get("confidence"))
        if selected.get("confidence") is not None
        else tfidf_top_prob
    )
    result["ranked_codes"] = _extract_ranked_codes(selected)
    if "proba_scores" in tfidf_pred:
        result["proba_scores"] = list(tfidf_pred.get("proba_scores") or [])
    result["ensemble_source"] = use_source
    result["ensemble_rule"] = config.rule
    result["ensemble_mas_primary_parent"] = mas_primary_parent
    result["ensemble_tfidf_primary_parent"] = tfidf_primary_parent
    result["ensemble_tfidf_top_prob"] = tfidf_top_prob
    result["ensemble_mas_strong_classes"] = sorted(strong_classes)
    result["ensemble_rule_description"] = (
        f"{config.rule}: MAS on {sorted(strong_classes)}, "
        f"TF-IDF threshold={config.tfidf_threshold_high:.2f}"
    )
    return result
