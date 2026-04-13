"""Tests for temporal evidence propagation into checker prompts."""
from __future__ import annotations

import threading

from culturedx.agents.base import AgentOutput
from culturedx.core.models import ClinicalCase, EvidenceBrief, Turn
from culturedx.evidence.temporal import TemporalFeatures, TemporalMatch
from culturedx.modes.base import case_execution_context
from culturedx.modes.hied import HiEDMode


class FakeLLM:
    """Minimal fake LLM for mode construction."""

    def __init__(self, model: str = "test-model", max_concurrent: int = 1):
        self.model = model
        self.max_concurrent = max_concurrent

    def compute_prompt_hash(self, template_source: str) -> str:
        return "test-hash"


class CapturingChecker:
    """Checker stub that records AgentInput payloads."""

    def __init__(self):
        self.inputs = []

    def run(self, agent_input):
        self.inputs.append(agent_input)
        return AgentOutput(
            parsed={
                "disorder": "F41.1",
                "criteria": [],
                "criteria_met_count": 0,
                "criteria_required": 1,
            }
        )


class ThreadRecordingChecker:
    """Checker stub that records which thread executed each disorder."""

    def __init__(self):
        self.thread_ids: list[int] = []

    def run(self, agent_input):
        self.thread_ids.append(threading.get_ident())
        return AgentOutput(
            parsed={
                "disorder": agent_input.extra["disorder_code"],
                "criteria": [],
                "criteria_met_count": 0,
                "criteria_required": 1,
            }
        )


def _make_case() -> ClinicalCase:
    return ClinicalCase(
        case_id="temporal-001",
        transcript=[
            Turn(speaker="doctor", text="最近怎么了？", turn_id=1),
            Turn(speaker="patient", text="我一直很焦虑，差不多八个月了。", turn_id=2),
        ],
        language="zh",
        dataset="test",
    )


def test_hied_builds_temporal_summary_into_checker_evidence():
    mode = HiEDMode(
        llm_client=FakeLLM(),
        target_disorders=["F41.1"],
    )
    capturing_checker = CapturingChecker()
    temporal_features = TemporalFeatures(
        matches=[
            TemporalMatch(
                category="explicit_duration",
                text="八个月",
                turn_id=2,
                estimated_months=8.0,
            )
        ],
        duration_confidence=0.9,
        estimated_months=8.0,
        meets_6month_criterion=True,
        reasoning="明确提到持续八个月。",
    )
    evidence = EvidenceBrief(
        case_id="temporal-001",
        language="zh",
        temporal_features=temporal_features,
    )

    evidence_map = mode._build_evidence_map(evidence)
    mode._parallel_check_criteria(
        checker=capturing_checker,
        disorder_codes=["F41.1"],
        transcript_text=mode._build_transcript_text(_make_case()),
        evidence_map=evidence_map,
        lang="zh",
        checker_llm_client=mode.checker_llm,
    )

    assert "F41.1" in evidence_map
    assert evidence_map["F41.1"]["temporal_summary"] == temporal_features.summary_zh()
    assert capturing_checker.inputs[0].evidence is not None
    assert capturing_checker.inputs[0].evidence["temporal_summary"] == temporal_features.summary_zh()


