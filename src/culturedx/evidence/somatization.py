"""Chinese somatization mapper: ontology lookup + normalized fuzzy fallback."""
from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from jinja2 import Environment, FileSystemLoader

from culturedx.core.models import SymptomSpan
from culturedx.evidence.normalization import (
    contains_ambiguity_marker,
    contains_historical_marker,
    contains_negation,
    contains_other_person_marker,
    normalize_text,
)
from culturedx.llm.json_utils import extract_json_from_response
from culturedx.ontology.symptom_map import lookup_symptom

logger = logging.getLogger(__name__)

_COMMON_SYNONYMS: dict[str, str] = {
    # Pain synonyms
    "头痛": "头疼",
    "脑袋疼": "头疼",
    "身上疼": "浑身疼",
    "全身酸痛": "浑身酸痛",
    # Sleep synonyms
    "睡不着觉": "失眠",
    "睡眠不好": "失眠",
    "睡不好觉": "睡不好",
    "夜里醒": "半夜醒",
    "凌晨醒": "早醒",
    # Appetite synonyms
    "胃口不好": "食欲下降",
    "吃不下": "食欲下降",
    "没食欲": "没胃口",
    "吃不进去": "吃不下东西",
    # Cardiovascular synonyms
    "心里发慌": "心慌",
    "心跳很快": "心跳加速",
    "心脏砰砰跳": "心跳加速",
    # Respiratory synonyms
    "胸口发闷": "胸闷",
    "胸口闷": "胸闷",
    "喘不了气": "喘不过气",
    "上气不接下气": "喘不过气",
    # Neurological synonyms
    "脑袋晕": "头晕",
    "天旋地转": "眩晕",
    "头脑发昏": "头昏脑涨",
    "脑子糊涂": "脑子不清楚",
    "记性不好": "记忆力下降",
    # Fatigue synonyms
    "心情很差": "情绪低落",
    "不想做事": "兴趣减退",
    "浑身没力气": "浑身没劲",
    "累得慌": "容易疲劳",
    "整个人没劲": "没有力气",
    # Autonomic synonyms
    "全身发抖": "发抖",
    "手脚发抖": "手抖",
    "一身汗": "冒汗",
    # GI synonyms
    "胃疼": "胃痛",
    "闹肚子": "拉肚子",
    "想吐": "恶心",
}


@dataclass(frozen=True)
class ResolvedSymptomConcept:
    """A resolved symptom concept with provenance."""

    canonical_text: str
    criteria: tuple[str, ...]
    category: str = ""
    match_type: str = "exact"
    score: float = 1.0
    source_text: str = ""


def _canonicalize(text: str) -> str:
    normalized = normalize_text(text)
    return _COMMON_SYNONYMS.get(normalized, normalized)


def _best_fuzzy_key(text: str) -> tuple[str, float] | None:
    normalized = _canonicalize(text)
    candidates = []
    for entry_key in _load_mapping().keys():
        score = SequenceMatcher(
            None,
            normalized,
            _canonicalize(entry_key),
        ).ratio()
        candidates.append((entry_key, score))
    if not candidates:
        return None
    best_key, best_score = max(candidates, key=lambda item: item[1])
    if best_score < 0.82:
        return None
    return best_key, best_score


def _dedupe_criteria(candidates: Iterable[ResolvedSymptomConcept]) -> list[str]:
    criteria: list[str] = []
    seen = set()
    for candidate in candidates:
        for criterion in candidate.criteria:
            if criterion not in seen:
                seen.add(criterion)
                criteria.append(criterion)
    return criteria


def _context_flags(text: str, context: str = "") -> list[str]:
    combined = " ".join(part for part in (text, context) if part).strip()
    flags: list[str] = []
    if contains_negation(combined):
        flags.append("negated")
    if contains_historical_marker(combined):
        flags.append("historical_past")
    if contains_other_person_marker(combined):
        flags.append("family_or_other_person")
    if contains_ambiguity_marker(combined):
        flags.append("ambiguous_context")
    return flags


def _expression_type_from_flags(flags: list[str], mapped: bool) -> str:
    if "negated" in flags:
        return "negated"
    if "historical_past" in flags:
        return "historical_past"
    if "family_or_other_person" in flags:
        return "family_or_other_person"
    if "ambiguous_context" in flags and not mapped:
        return "metaphorical_or_ambiguous"
    if mapped:
        return "somatized_expression"
    return "insufficient_context"


@lru_cache(maxsize=2048)
def _load_mapping() -> dict[str, dict]:
    from culturedx.ontology.symptom_map import load_somatization_map

    return load_somatization_map()


@lru_cache(maxsize=4096)
def resolve_symptom_concept(symptom_text: str) -> ResolvedSymptomConcept | None:
    """Resolve a symptom text to a canonical concept using cached matching."""
    ranked = rank_symptom_concepts(symptom_text, top_k=1)
    return ranked[0] if ranked else None


@lru_cache(maxsize=4096)
def rank_symptom_concepts(
    symptom_text: str,
    top_k: int = 5,
) -> tuple[ResolvedSymptomConcept, ...]:
    """Return ranked candidate concepts for a somatic expression."""
    if not symptom_text:
        return ()

    exact = lookup_symptom(symptom_text)
    if exact is not None:
        return (
            ResolvedSymptomConcept(
                canonical_text=symptom_text,
                criteria=tuple(exact.get("criteria", [])),
                category=exact.get("category", ""),
                match_type="exact",
                score=1.0,
                source_text=symptom_text,
            ),
        )

    canonical = _canonicalize(symptom_text)
    if canonical != symptom_text:
        exact = lookup_symptom(canonical)
        if exact is not None:
            return (
                ResolvedSymptomConcept(
                    canonical_text=canonical,
                    criteria=tuple(exact.get("criteria", [])),
                    category=exact.get("category", ""),
                    match_type="normalized",
                    score=0.95,
                    source_text=symptom_text,
                ),
            )

    normalized = _canonicalize(symptom_text)
    ranked: list[ResolvedSymptomConcept] = []
    seen = set()
    for entry_key, entry in _load_mapping().items():
        candidate_key = _canonicalize(entry_key)
        score = SequenceMatcher(None, normalized, candidate_key).ratio()
        if score < 0.60:
            continue
        match_type = "fuzzy"
        if normalized == candidate_key:
            score = 0.95
            match_type = "normalized"
        resolved = ResolvedSymptomConcept(
            canonical_text=entry_key,
            criteria=tuple(entry.get("criteria", [])),
            category=entry.get("category", ""),
            match_type=match_type,
            score=score,
            source_text=symptom_text,
        )
        if resolved.canonical_text in seen:
            continue
        seen.add(resolved.canonical_text)
        ranked.append(resolved)

    ranked.sort(key=lambda item: (-item.score, item.canonical_text))
    return tuple(ranked[:top_k])


class SomatizationMapper:
    """Map Chinese somatic symptoms to psychiatric criteria."""

    def __init__(
        self,
        llm_client=None,
        llm_fallback: bool = True,
        prompts_dir: str | Path = "prompts/evidence",
    ) -> None:
        self.llm = llm_client
        self.llm_fallback = llm_fallback and (llm_client is not None)
        if self.llm_fallback:
            self._env = Environment(
                loader=FileSystemLoader(str(prompts_dir)),
                keep_trailing_newline=True,
            )
        else:
            self._env = None

    def map_span(
        self, span: SymptomSpan, context: str = ""
    ) -> SymptomSpan:
        """Map a single somatic span to criteria. Returns new SymptomSpan."""
        if not span.is_somatic:
            return span

        payload = self._resolve_mapping_payload(span.text, context)
        if payload is None:
            return span
        return self._apply_mapping_payload(span, payload)

    def map_all(
        self, spans: list[SymptomSpan], context: str = ""
    ) -> list[SymptomSpan]:
        """Map all somatic spans in the list. Returns new list with cached lookups."""
        results: list[SymptomSpan] = []
        cache: dict[str, dict | None] = {}
        for span in spans:
            if not span.is_somatic:
                results.append(span)
                continue
            key = span.text
            if key not in cache:
                cache[key] = self._resolve_mapping_payload(span.text, context)
            payload = cache[key]
            if payload is None:
                results.append(span)
            else:
                results.append(self._apply_mapping_payload(span, payload))
        return results

    def _resolve_mapping_payload(
        self, symptom_text: str, context: str
    ) -> dict | None:
        candidates = list(rank_symptom_concepts(symptom_text, top_k=5))
        resolved = candidates[0] if candidates else None
        flags = _context_flags(symptom_text, context)
        if resolved is not None:
            return {
                "mapped_criterion": ",".join(resolved.criteria),
                "mapping_source": resolved.match_type,
                "mapping_score": resolved.score,
                "normalized_text": normalize_text(symptom_text),
                "canonical_symptom": resolved.canonical_text,
                "concept_category": resolved.category,
                "normalized_concept": resolved.canonical_text,
                "candidate_criteria": _dedupe_criteria(candidates),
                "mapping_confidence": resolved.score,
                "mapping_rationale": (
                    f"{resolved.match_type}_match:{symptom_text}->{resolved.canonical_text}"
                ),
                "ambiguity_flags": flags,
                "cache_metadata": {
                    "resolver_cache": "lru_cache",
                    "cache_key": _canonicalize(symptom_text),
                    "candidate_count": len(candidates),
                },
                "expression_type": _expression_type_from_flags(flags, mapped=True),
            }

        if self.llm_fallback and self._env is not None:
            criteria = self._llm_map(symptom_text, context)
            if criteria:
                return {
                    "mapped_criterion": ",".join(criteria),
                    "mapping_source": "llm",
                    "mapping_score": 0.5,
                    "normalized_text": normalize_text(symptom_text),
                    "canonical_symptom": normalize_text(symptom_text),
                    "concept_category": "",
                    "normalized_concept": normalize_text(symptom_text),
                    "candidate_criteria": list(criteria),
                    "mapping_confidence": 0.5,
                    "mapping_rationale": "llm_fallback",
                    "ambiguity_flags": flags,
                    "cache_metadata": {
                        "resolver_cache": "lru_cache",
                        "cache_key": _canonicalize(symptom_text),
                        "candidate_count": 0,
                    },
                    "expression_type": _expression_type_from_flags(flags, mapped=True),
                }
        return None

    @staticmethod
    def _apply_mapping_payload(span: SymptomSpan, payload: dict) -> SymptomSpan:
        mapped = replace(
            span,
            mapped_criterion=payload["mapped_criterion"],
            expression_type=payload.get("expression_type"),
            normalized_concept=payload.get("normalized_concept"),
            candidate_criteria=list(payload.get("candidate_criteria", [])),
            mapping_confidence=float(payload.get("mapping_confidence", 0.0)),
            mapping_rationale=payload.get("mapping_rationale"),
            mapping_source=payload.get("mapping_source"),
            ambiguity_flags=list(payload.get("ambiguity_flags", [])),
            cache_metadata=dict(payload.get("cache_metadata", {})),
        )
        return mapped

    def _llm_map(self, symptom_text: str, context: str) -> list[str]:
        """Use LLM to map an unknown somatic symptom to criteria."""
        template = self._env.get_template("somatization_fallback_zh.jinja")
        prompt = template.render(
            symptom_text=symptom_text, context=context
        )
        source, _, _ = self._env.loader.get_source(
            self._env, "somatization_fallback_zh.jinja"
        )
        prompt_hash = self.llm.compute_prompt_hash(source)

        raw = self.llm.generate(
            prompt, prompt_hash=prompt_hash, language="zh"
        )
        parsed = extract_json_from_response(raw)

        if parsed is None or not isinstance(parsed, dict):
            logger.warning(
                "LLM fallback failed for symptom: %s", symptom_text
            )
            return []

        return parsed.get("mapped_criteria", [])


def _clear_cache() -> None:
    """Clear module caches (for testing only)."""
    resolve_symptom_concept.cache_clear()
    rank_symptom_concepts.cache_clear()
    _load_mapping.cache_clear()
