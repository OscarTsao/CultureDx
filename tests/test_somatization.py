"""Tests for somatization mapper."""
import json
from unittest.mock import MagicMock

import pytest

from culturedx.core.models import SymptomSpan
from culturedx.evidence.normalization import contains_negation
from culturedx.evidence.somatization import (
    SomatizationMapper,
    _clear_cache,
    resolve_symptom_concept,
)


class TestSomatizationMapper:
    def test_ontology_lookup_known(self):
        _clear_cache()
        mapper = SomatizationMapper(llm_client=None, llm_fallback=False)
        span = SymptomSpan(
            text="头疼", turn_id=1, symptom_type="somatic", is_somatic=True
        )
        result = mapper.map_span(span)
        assert result.mapped_criterion is not None
        assert "F32.C6" in result.mapped_criterion
        assert getattr(result, "mapping_source") == "exact"
        # Original not mutated
        assert span.mapped_criterion is None

    def test_ontology_lookup_unknown_no_fallback(self):
        _clear_cache()
        mapper = SomatizationMapper(llm_client=None, llm_fallback=False)
        span = SymptomSpan(
            text="奇怪的躯体感觉xyz",
            turn_id=1,
            symptom_type="somatic",
            is_somatic=True,
        )
        result = mapper.map_span(span)
        assert result.mapped_criterion is None

    def test_non_somatic_skipped(self):
        mapper = SomatizationMapper(llm_client=None, llm_fallback=False)
        span = SymptomSpan(
            text="情绪低落", turn_id=1, symptom_type="emotional", is_somatic=False
        )
        result = mapper.map_span(span)
        assert result.mapped_criterion is None
        assert result is span  # Same object returned (no copy needed)

    def test_normalized_synonym_lookup(self):
        _clear_cache()
        mapper = SomatizationMapper(llm_client=None, llm_fallback=False)
        span = SymptomSpan(
            text="头痛",
            turn_id=1,
            symptom_type="somatic",
            is_somatic=True,
        )
        result = mapper.map_span(span)
        assert result.mapped_criterion is not None
        assert getattr(result, "mapping_source") in {"exact", "normalized"}

    def test_fuzzy_lookup(self):
        _clear_cache()
        mapper = SomatizationMapper(llm_client=None, llm_fallback=False)
        span = SymptomSpan(
            text="睡不着觉",
            turn_id=1,
            symptom_type="somatic",
            is_somatic=True,
        )
        result = mapper.map_span(span)
        assert result.mapped_criterion is not None
        assert getattr(result, "mapping_source") in {"exact", "normalized", "fuzzy"}
        assert result.expression_type == "somatized_expression"
        assert result.normalized_concept == "失眠"
        assert result.candidate_criteria

    def test_llm_fallback(self, tmp_path):
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "somatization_fallback_zh.jinja").write_text(
            "Map: {{ symptom_text }} context: {{ context }}",
            encoding="utf-8",
        )
        mock_llm = MagicMock()
        mock_llm.compute_prompt_hash.return_value = "test_hash"
        mock_llm.generate.return_value = json.dumps({
            "mapped_criteria": ["F32.C6", "F45.C3"],
            "reasoning": "test",
        })

        mapper = SomatizationMapper(
            llm_client=mock_llm,
            llm_fallback=True,
            prompts_dir=str(prompts_dir),
        )
        span = SymptomSpan(
            text="奇怪的躯体感觉xyz",
            turn_id=1,
            symptom_type="somatic",
            is_somatic=True,
        )
        result = mapper.map_span(span, context="测试上下文")
        assert result.mapped_criterion is not None
        assert "F32.C6" in result.mapped_criterion
        mock_llm.generate.assert_called_once()
        assert getattr(result, "mapping_source") == "llm"

    def test_negated_context_emits_structured_flags(self):
        _clear_cache()
        mapper = SomatizationMapper(llm_client=None, llm_fallback=False)
        span = SymptomSpan(
            text="胸口发闷",
            turn_id=1,
            symptom_type="somatic",
            is_somatic=True,
        )
        result = mapper.map_span(span, context="我没有胸口发闷，也不心慌。")
        assert result.expression_type == "negated"
        assert result.normalized_concept == "胸闷"
        assert "negated" in result.ambiguity_flags
        assert result.mapping_confidence > 0.0

    def test_map_all_spans(self):
        _clear_cache()
        mapper = SomatizationMapper(llm_client=None, llm_fallback=False)
        spans = [
            SymptomSpan(
                text="头疼", turn_id=1, symptom_type="somatic", is_somatic=True
            ),
            SymptomSpan(
                text="情绪低落",
                turn_id=2,
                symptom_type="emotional",
                is_somatic=False,
            ),
            SymptomSpan(
                text="失眠", turn_id=3, symptom_type="somatic", is_somatic=True
            ),
        ]
        results = mapper.map_all(spans)
        assert len(results) == 3
        assert results[0].mapped_criterion is not None  # 头疼 mapped
        assert results[1].mapped_criterion is None  # emotional skipped
        assert results[2].mapped_criterion is not None  # 失眠 mapped

    def test_cached_resolution_hits(self):
        _clear_cache()
        resolve_symptom_concept.cache_clear()
        first = resolve_symptom_concept("失眠")
        second = resolve_symptom_concept("失眠")
        assert first is not None
        assert second is not None
        info = resolve_symptom_concept.cache_info()
        assert info.hits >= 1

    def test_contains_negation_handles_symptom_idioms(self):
        assert contains_negation("我没有胸闷") is True
        assert contains_negation("这几天睡不着觉") is False
        assert contains_negation("最近没兴趣做事") is False
