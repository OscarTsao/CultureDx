"""Tests for evidence pipeline orchestrator."""
import json
from unittest.mock import MagicMock

import pytest

from culturedx.core.models import ClinicalCase, Turn
from culturedx.evidence.pipeline import EvidencePipeline
from culturedx.evidence.retriever import MockRetriever


def _make_zh_case() -> ClinicalCase:
    return ClinicalCase(
        case_id="pipeline_zh_001",
        transcript=[
            Turn(speaker="doctor", text="你最近怎么样？", turn_id=0),
            Turn(speaker="patient", text="我头疼，心情很低落", turn_id=1),
            Turn(speaker="doctor", text="睡眠怎么样？", turn_id=2),
            Turn(speaker="patient", text="失眠，晚上睡不着", turn_id=3),
        ],
        language="zh",
        dataset="test",
    )


def _make_en_case() -> ClinicalCase:
    return ClinicalCase(
        case_id="pipeline_en_001",
        transcript=[
            Turn(speaker="doctor", text="How are you?", turn_id=0),
            Turn(speaker="patient", text="I feel depressed and tired", turn_id=1),
            Turn(speaker="doctor", text="Any other symptoms?", turn_id=2),
            Turn(speaker="patient", text="I can't concentrate", turn_id=3),
        ],
        language="en",
        dataset="test",
    )


def _make_mock_llm() -> MagicMock:
    mock = MagicMock()
    mock.compute_prompt_hash.return_value = "test_hash"
    mock.generate.return_value = json.dumps({
        "symptoms": [
            {"text": "头疼", "turn_id": 1, "symptom_type": "somatic"},
            {"text": "心情很低落", "turn_id": 1, "symptom_type": "emotional"},
            {"text": "失眠", "turn_id": 3, "symptom_type": "somatic"},
        ]
    }, ensure_ascii=False)
    return mock


class TestEvidencePipeline:
    def test_full_pipeline_zh(self, tmp_path):
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "extract_symptoms_zh.jinja").write_text(
            "Extract: {% for t in turns %}{{ t.text }}{% endfor %}",
            encoding="utf-8",
        )
        (prompts_dir / "somatization_fallback_zh.jinja").write_text(
            "Map: {{ symptom_text }}", encoding="utf-8"
        )

        pipeline = EvidencePipeline(
            llm_client=_make_mock_llm(),
            retriever=MockRetriever(),
            target_disorders=["F32"],
            prompts_dir=str(prompts_dir),
            min_confidence=0.0,
        )
        brief = pipeline.extract(_make_zh_case())
        assert brief.case_id == "pipeline_zh_001"
        assert brief.language == "zh"
        assert len(brief.symptom_spans) == 3
        assert len(brief.disorder_evidence) == 1
        assert brief.disorder_evidence[0].disorder_code == "F32"

        somatic_span = next(span for span in brief.symptom_spans if span.text == "头疼")
        assert somatic_span.expression_type == "somatized_expression"
        assert somatic_span.normalized_concept == "头疼"
        assert "F32.C6" in somatic_span.candidate_criteria
        assert somatic_span.mapping_confidence > 0.0
        assert somatic_span.cache_metadata["candidate_count"] >= 1

    def test_pipeline_en_no_somatization(self, tmp_path):
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "extract_symptoms_en.jinja").write_text(
            "Extract: {% for t in turns %}{{ t.text }}{% endfor %}",
            encoding="utf-8",
        )

        mock_llm = MagicMock()
        mock_llm.compute_prompt_hash.return_value = "test_hash"
        mock_llm.generate.return_value = json.dumps({
            "symptoms": [
                {"text": "depressed", "turn_id": 1, "symptom_type": "emotional"},
            ]
        })

        pipeline = EvidencePipeline(
            llm_client=mock_llm,
            retriever=MockRetriever(),
            target_disorders=["F32"],
            somatization_enabled=True,  # enabled but skipped for English
            prompts_dir=str(prompts_dir),
            min_confidence=0.0,
        )
        brief = pipeline.extract(_make_en_case())
        assert brief.language == "en"
        assert len(brief.disorder_evidence) == 1

    def test_pipeline_multiple_disorders(self, tmp_path):
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "extract_symptoms_zh.jinja").write_text(
            "Extract: {% for t in turns %}{{ t.text }}{% endfor %}",
            encoding="utf-8",
        )
        (prompts_dir / "somatization_fallback_zh.jinja").write_text(
            "Map: {{ symptom_text }}", encoding="utf-8"
        )

        pipeline = EvidencePipeline(
            llm_client=_make_mock_llm(),
            retriever=MockRetriever(),
            target_disorders=["F32", "F41.1"],
            prompts_dir=str(prompts_dir),
            min_confidence=0.0,
        )
        brief = pipeline.extract(_make_zh_case())
        assert len(brief.disorder_evidence) == 2
        codes = {de.disorder_code for de in brief.disorder_evidence}
        assert codes == {"F32", "F41.1"}

    def test_pipeline_no_extractor(self, tmp_path):
        """Extractor disabled: still retrieves evidence via criteria matching."""
        pipeline = EvidencePipeline(
            llm_client=MagicMock(),
            retriever=MockRetriever(),
            target_disorders=["F32"],
            extractor_enabled=False,
            somatization_enabled=False,
            min_confidence=0.0,
        )
        brief = pipeline.extract(_make_zh_case())
        assert brief.case_id == "pipeline_zh_001"
        assert len(brief.symptom_spans) == 0  # No extraction
        assert len(brief.disorder_evidence) == 1  # Still matches criteria

    def test_auto_scope_without_targets_uses_all_supported(self):
        pipeline = EvidencePipeline(
            llm_client=MagicMock(),
            retriever=MockRetriever(),
            extractor_enabled=False,
            somatization_enabled=False,
            min_confidence=0.0,
        )
        brief = pipeline.extract(_make_en_case())
        assert brief.scope_policy == "all_supported"
        assert "F32" in brief.target_disorders
        assert "F41.1" in brief.target_disorders
        assert len(brief.disorder_evidence) == len(brief.target_disorders)

    def test_manual_scope_requires_explicit_targets(self):
        pipeline = EvidencePipeline(
            llm_client=MagicMock(),
            retriever=MockRetriever(),
            scope_policy="manual",
            extractor_enabled=False,
            somatization_enabled=False,
            min_confidence=0.0,
        )
        brief = pipeline.extract(_make_en_case())
        assert brief.disorder_evidence == []
        assert len(brief.failures) == 1
        assert brief.failures[0].code == "scope_resolution_failed"

    def test_triage_scope_accepts_runtime_candidates(self):
        pipeline = EvidencePipeline(
            llm_client=MagicMock(),
            retriever=MockRetriever(),
            scope_policy="triage",
            extractor_enabled=False,
            somatization_enabled=False,
            min_confidence=0.0,
        )
        brief = pipeline.extract(_make_en_case(), target_disorders=["F32", "F41.1"])
        assert brief.scope_policy == "triage"
        assert brief.target_disorders == ["F32", "F41.1"]
        assert len(brief.disorder_evidence) == 2

    def test_pipeline_with_reranking_enabled(self):
        pipeline = EvidencePipeline(
            llm_client=MagicMock(),
            retriever=MockRetriever(),
            scope_policy="manual",
            target_disorders=["F32"],
            rerank_enabled=True,
            extractor_enabled=False,
            somatization_enabled=False,
            min_confidence=0.0,
        )
        brief = pipeline.extract(_make_en_case())
        assert brief.disorder_evidence
        criterion_evidence = brief.disorder_evidence[0].criteria_evidence[0]
        assert getattr(criterion_evidence, "evidence_signals")["reranked"] is True
