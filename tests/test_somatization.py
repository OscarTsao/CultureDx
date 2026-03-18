"""Tests for somatization mapper."""
import json
from unittest.mock import MagicMock

import pytest

from culturedx.core.models import SymptomSpan
from culturedx.evidence.somatization import SomatizationMapper


class TestSomatizationMapper:
    def test_ontology_lookup_known(self):
        mapper = SomatizationMapper(llm_client=None, llm_fallback=False)
        span = SymptomSpan(
            text="头疼", turn_id=1, symptom_type="somatic", is_somatic=True
        )
        result = mapper.map_span(span)
        assert result.mapped_criterion is not None
        assert "F32.C6" in result.mapped_criterion
        # Original not mutated
        assert span.mapped_criterion is None

    def test_ontology_lookup_unknown_no_fallback(self):
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

    def test_map_all_spans(self):
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
