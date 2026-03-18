"""Tests for Evidence Brief assembler."""
import pytest

from culturedx.core.models import (
    CriterionEvidence,
    DisorderEvidence,
    EvidenceBrief,
    SymptomSpan,
)
from culturedx.evidence.brief import EvidenceBriefAssembler


class TestEvidenceBriefAssembler:
    def test_assemble_single_disorder(self):
        assembler = EvidenceBriefAssembler(min_confidence=0.0)
        criteria_results = {
            "F32": [
                CriterionEvidence(
                    criterion_id="F32.B1",
                    spans=[
                        SymptomSpan(
                            text="情绪低落", turn_id=1, symptom_type="emotional"
                        )
                    ],
                    confidence=0.85,
                ),
                CriterionEvidence(
                    criterion_id="F32.B2",
                    spans=[],
                    confidence=0.3,
                ),
            ],
        }
        brief = assembler.assemble(
            case_id="test_001",
            language="zh",
            criteria_results=criteria_results,
        )
        assert brief.case_id == "test_001"
        assert len(brief.disorder_evidence) == 1
        assert brief.disorder_evidence[0].disorder_code == "F32"
        assert len(brief.disorder_evidence[0].criteria_evidence) == 2

    def test_assemble_multiple_disorders(self):
        assembler = EvidenceBriefAssembler(min_confidence=0.0)
        criteria_results = {
            "F32": [
                CriterionEvidence(
                    criterion_id="F32.B1", spans=[], confidence=0.8
                ),
            ],
            "F41.1": [
                CriterionEvidence(
                    criterion_id="F41.1.A", spans=[], confidence=0.7
                ),
            ],
        }
        brief = assembler.assemble(
            case_id="test_002",
            language="en",
            criteria_results=criteria_results,
        )
        assert len(brief.disorder_evidence) == 2
        codes = {de.disorder_code for de in brief.disorder_evidence}
        assert codes == {"F32", "F41.1"}

    def test_assemble_with_symptom_spans(self):
        assembler = EvidenceBriefAssembler(min_confidence=0.0)
        spans = [
            SymptomSpan(
                text="头疼", turn_id=1, symptom_type="somatic", is_somatic=True
            ),
            SymptomSpan(
                text="情绪低落", turn_id=2, symptom_type="emotional"
            ),
        ]
        brief = assembler.assemble(
            case_id="test_003",
            language="zh",
            symptom_spans=spans,
        )
        assert len(brief.symptom_spans) == 2
        assert brief.symptom_spans[0].is_somatic is True

    def test_filter_by_min_confidence(self):
        assembler = EvidenceBriefAssembler(min_confidence=0.5)
        criteria_results = {
            "F32": [
                CriterionEvidence(
                    criterion_id="F32.B1", spans=[], confidence=0.8
                ),
                CriterionEvidence(
                    criterion_id="F32.B2", spans=[], confidence=0.3
                ),
                CriterionEvidence(
                    criterion_id="F32.C1", spans=[], confidence=0.1
                ),
            ],
        }
        brief = assembler.assemble(
            case_id="test_004",
            language="zh",
            criteria_results=criteria_results,
        )
        # Only F32.B1 (0.8) should survive min_confidence=0.5
        assert len(brief.disorder_evidence) == 1
        assert len(brief.disorder_evidence[0].criteria_evidence) == 1
        assert brief.disorder_evidence[0].criteria_evidence[0].confidence == 0.8
