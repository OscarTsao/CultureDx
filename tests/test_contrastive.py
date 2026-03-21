"""Tests for contrastive criterion disambiguation."""
from __future__ import annotations

import hashlib
import json

import pytest

from culturedx.core.models import CheckerOutput, CriterionResult
from culturedx.ontology.shared_criteria import (
    SharedCriterionPair,
    apply_attribution,
    apply_attributions_to_checker_output,
    get_shared_pairs,
)


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestSharedCriteriaRegistry:
    """Tests for the shared criteria registry."""

    def test_f32_f41_1_returns_four_pairs(self):
        pairs = get_shared_pairs("F32", "F41.1")
        assert len(pairs) == 4

    def test_symmetry(self):
        """get_shared_pairs(A, B) == get_shared_pairs(B, A)."""
        pairs_ab = get_shared_pairs("F32", "F41.1")
        pairs_ba = get_shared_pairs("F41.1", "F32")
        assert pairs_ab == pairs_ba

    def test_no_overlap_returns_empty(self):
        assert get_shared_pairs("F32", "F20") == []
        assert get_shared_pairs("F20", "F41.1") == []

    def test_all_pairs_have_hints(self):
        pairs = get_shared_pairs("F32", "F41.1")
        for p in pairs:
            assert p.disambiguation_hint_en, f"Missing EN hint for {p.symptom_domain}"
            assert p.disambiguation_hint_zh, f"Missing ZH hint for {p.symptom_domain}"

    def test_symptom_domains_are_unique(self):
        pairs = get_shared_pairs("F32", "F41.1")
        domains = [p.symptom_domain for p in pairs]
        assert len(domains) == len(set(domains))

    def test_pair_criteria_match_icd10(self):
        """Verify criterion IDs exist in the real ICD-10 ontology."""
        from culturedx.ontology.icd10 import get_disorder_criteria

        pairs = get_shared_pairs("F32", "F41.1")
        f32_criteria = get_disorder_criteria("F32")
        f41_criteria = get_disorder_criteria("F41.1")
        for p in pairs:
            assert p.criterion_a in f32_criteria, f"F32.{p.criterion_a} not in ontology"
            assert p.criterion_b in f41_criteria, f"F41.1.{p.criterion_b} not in ontology"


# ---------------------------------------------------------------------------
# Confidence-gated downgrade tests
# ---------------------------------------------------------------------------


class TestApplyAttribution:
    """Tests for the confidence-gated downgrade logic."""

    @pytest.fixture
    def base_criterion(self) -> CriterionResult:
        return CriterionResult(
            criterion_id="C4",
            status="met",
            evidence="睡不好觉",
            confidence=0.85,
        )

    def test_both_attribution_no_change(self, base_criterion):
        result = apply_attribution(base_criterion, 0.90, "both", "F32")
        assert result is base_criterion

    def test_primary_matches_this_disorder_no_change(self, base_criterion):
        result = apply_attribution(base_criterion, 0.90, "F32", "F32")
        assert result is base_criterion

    def test_high_confidence_full_downgrade(self, base_criterion):
        result = apply_attribution(base_criterion, 0.85, "F41.1", "F32")
        assert result.status == "insufficient_evidence"
        assert result.confidence == pytest.approx(0.85 * 0.3)

    def test_high_confidence_boundary_at_0_8(self, base_criterion):
        result = apply_attribution(base_criterion, 0.80, "F41.1", "F32")
        assert result.status == "insufficient_evidence"
        assert result.confidence == pytest.approx(0.85 * 0.3)

    def test_medium_confidence_partial_downgrade(self, base_criterion):
        result = apply_attribution(base_criterion, 0.70, "F41.1", "F32")
        assert result.status == "met"
        assert result.confidence == pytest.approx(0.85 * 0.5)

    def test_medium_confidence_boundary_at_0_6(self, base_criterion):
        result = apply_attribution(base_criterion, 0.60, "F41.1", "F32")
        assert result.status == "met"
        assert result.confidence == pytest.approx(0.85 * 0.5)

    def test_low_confidence_minimal_adjustment(self, base_criterion):
        result = apply_attribution(base_criterion, 0.50, "F41.1", "F32")
        assert result.status == "met"
        assert result.confidence == pytest.approx(0.85 * 0.8)

    def test_low_confidence_boundary_at_0_59(self, base_criterion):
        result = apply_attribution(base_criterion, 0.59, "F41.1", "F32")
        assert result.status == "met"
        assert result.confidence == pytest.approx(0.85 * 0.8)

    def test_evidence_preserved_on_downgrade(self, base_criterion):
        result = apply_attribution(base_criterion, 0.85, "F41.1", "F32")
        assert result.evidence == "睡不好觉"
        assert result.criterion_id == "C4"


# ---------------------------------------------------------------------------
# Deduplication tests
# ---------------------------------------------------------------------------


class TestDeduplication:
    """Tests for per-criterion-id deduplication in contrastive application."""

    def test_b1_dedup_highest_confidence_wins(self):
        """F41.1.B1 targeted by two attributions — only highest confidence applied."""
        checker_output = CheckerOutput(
            disorder="F41.1",
            criteria=[
                CriterionResult(criterion_id="A", status="met", confidence=0.85),
                CriterionResult(criterion_id="B1", status="met", confidence=0.80),
                CriterionResult(criterion_id="B2", status="met", confidence=0.85),
                CriterionResult(criterion_id="B3", status="met", confidence=0.90),
                CriterionResult(criterion_id="B4", status="met", confidence=0.85),
            ],
            criteria_met_count=5,
            criteria_required=4,
        )
        # Two attributions both target F41.1.B1 (psychomotor + fatigue)
        # Dedup: highest confidence (0.85) wins -> full downgrade
        attribution_map = {
            ("F41.1", "B1"): (0.85, "F32"),
            ("F41.1", "B3"): (0.70, "F32"),
        }
        result = apply_attributions_to_checker_output(checker_output, attribution_map)
        b1 = next(c for c in result.criteria if c.criterion_id == "B1")
        assert b1.status == "insufficient_evidence"
        assert b1.confidence == pytest.approx(0.80 * 0.3)
        b3 = next(c for c in result.criteria if c.criterion_id == "B3")
        assert b3.status == "met"
        assert b3.confidence == pytest.approx(0.90 * 0.5)
        # met count: A, B2, B3, B4 = 4 (B1 downgraded)
        assert result.criteria_met_count == 4

    def test_unaffected_criteria_unchanged(self):
        checker_output = CheckerOutput(
            disorder="F32",
            criteria=[
                CriterionResult(criterion_id="B1", status="met", confidence=0.90),
                CriterionResult(criterion_id="B2", status="met", confidence=0.85),
                CriterionResult(criterion_id="C4", status="met", confidence=0.80),
            ],
            criteria_met_count=3,
            criteria_required=4,
        )
        # Only C4 is in the attribution map
        attribution_map = {("F32", "C4"): (0.85, "F41.1")}
        result = apply_attributions_to_checker_output(checker_output, attribution_map)
        b1 = next(c for c in result.criteria if c.criterion_id == "B1")
        assert b1.status == "met"
        assert b1.confidence == 0.90
        c4 = next(c for c in result.criteria if c.criterion_id == "C4")
        assert c4.status == "insufficient_evidence"
        assert result.criteria_met_count == 2


# ---------------------------------------------------------------------------
# ContrastiveCheckerAgent tests
# ---------------------------------------------------------------------------


class MockLLMForContrastive:
    """Minimal mock LLM for testing ContrastiveCheckerAgent."""

    model = "mock"

    def __init__(self, response_json: dict):
        self._response = json.dumps(response_json)

    @staticmethod
    def compute_prompt_hash(source: str) -> str:
        return hashlib.sha256(source.encode()).hexdigest()[:16]

    def generate(self, prompt: str, **kwargs) -> str:
        return self._response


class TestContrastiveCheckerAgent:
    """Tests for the ContrastiveCheckerAgent."""

    def test_parses_valid_attribution(self):
        from culturedx.agents.base import AgentInput
        from culturedx.agents.contrastive_checker import ContrastiveCheckerAgent

        llm = MockLLMForContrastive({
            "attributions": [
                {
                    "symptom_domain": "concentration",
                    "primary_attribution": "F41.1",
                    "attribution_confidence": 0.82,
                    "reasoning": "worry-driven",
                },
                {
                    "symptom_domain": "sleep",
                    "primary_attribution": "F32",
                    "attribution_confidence": 0.75,
                    "reasoning": "rumination-driven",
                },
            ]
        })
        agent = ContrastiveCheckerAgent(llm, "prompts/agents")
        pairs = get_shared_pairs("F32", "F41.1")[:2]
        agent_input = AgentInput(
            transcript_text="test transcript",
            language="zh",
            extra={
                "shared_pairs": pairs,
                "checker_evidence": {
                    "F32_C4": {"status": "met", "evidence": "注意力差", "confidence": 0.85},
                    "F41.1_B3": {"status": "met", "evidence": "担心", "confidence": 0.80},
                    "F32_C6": {"status": "met", "evidence": "失眠", "confidence": 0.80},
                    "F41.1_B4": {"status": "met", "evidence": "睡不着", "confidence": 0.85},
                },
                "disorder_names": {"F32": "抑郁发作", "F41.1": "广泛性焦虑障碍"},
            },
        )
        output = agent.run(agent_input)
        assert output.parsed is not None
        assert len(output.parsed["attributions"]) == 2
        assert output.parsed["attributions"][0]["primary_attribution"] == "F41.1"
        assert output.parsed["attributions"][1]["primary_attribution"] == "F32"

    def test_returns_none_on_parse_failure(self):
        from culturedx.agents.base import AgentInput
        from culturedx.agents.contrastive_checker import ContrastiveCheckerAgent

        llm = MockLLMForContrastive({"bad": "response"})
        agent = ContrastiveCheckerAgent(llm, "prompts/agents")
        pairs = get_shared_pairs("F32", "F41.1")[:1]
        agent_input = AgentInput(
            transcript_text="test",
            language="zh",
            extra={
                "shared_pairs": pairs,
                "checker_evidence": {},
                "disorder_names": {},
            },
        )
        output = agent.run(agent_input)
        assert output.parsed is None

    def test_returns_none_on_empty_pairs(self):
        from culturedx.agents.base import AgentInput
        from culturedx.agents.contrastive_checker import ContrastiveCheckerAgent

        llm = MockLLMForContrastive({"attributions": []})
        agent = ContrastiveCheckerAgent(llm, "prompts/agents")
        agent_input = AgentInput(
            transcript_text="test",
            language="zh",
            extra={"shared_pairs": [], "checker_evidence": {}, "disorder_names": {}},
        )
        output = agent.run(agent_input)
        assert output.parsed is None
