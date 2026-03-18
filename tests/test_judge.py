"""Tests for JudgeAgent."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from culturedx.agents.base import AgentInput, AgentOutput
from culturedx.agents.judge import JudgeAgent

# Absolute path so tests work regardless of cwd
PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "agents"


class FakeLLM:
    def __init__(self, response: str = "{}"):
        self.model = "test-model"
        self.response = response

    def generate(self, prompt: str, **kwargs) -> str:
        return self.response

    def compute_prompt_hash(self, template_source: str) -> str:
        return "test-hash"


def make_input(
    specialist_opinions: list[dict] | None = None,
    language: str = "zh",
    case_id: str = "test-001",
) -> AgentInput:
    return AgentInput(
        transcript_text="Doctor: 你好\nPatient: 我情绪低落",
        language=language,
        extra={
            "specialist_opinions": specialist_opinions or [],
            "case_id": case_id,
        },
    )


class TestJudgeAgent:
    def test_empty_opinions_returns_none(self):
        llm = FakeLLM()
        agent = JudgeAgent(llm_client=llm, prompts_dir=PROMPTS_DIR)
        inp = make_input(specialist_opinions=[])
        result = agent.run(inp)
        assert result.parsed is None

    def test_single_diagnosis(self):
        response = json.dumps({
            "primary_diagnosis": "F32",
            "comorbid_diagnoses": [],
            "confidence": 0.85,
            "decision": "diagnosis",
            "reasoning": "Clear depressive episode",
        })
        llm = FakeLLM(response=response)
        agent = JudgeAgent(llm_client=llm, prompts_dir=PROMPTS_DIR)
        opinions = [
            {"disorder_code": "F32", "confidence": 0.9, "reasoning": "Meets criteria"},
        ]
        inp = make_input(specialist_opinions=opinions)
        result = agent.run(inp)
        assert result.parsed["primary_diagnosis"] == "F32"
        assert result.parsed["decision"] == "diagnosis"
        assert result.parsed["confidence"] == 0.85

    def test_comorbid_diagnosis(self):
        response = json.dumps({
            "primary_diagnosis": "F32",
            "comorbid_diagnoses": ["F41.1"],
            "confidence": 0.8,
            "decision": "diagnosis",
        })
        llm = FakeLLM(response=response)
        agent = JudgeAgent(llm_client=llm, prompts_dir=PROMPTS_DIR)
        opinions = [
            {"disorder_code": "F32", "confidence": 0.9, "reasoning": "Depression"},
            {"disorder_code": "F41.1", "confidence": 0.7, "reasoning": "GAD"},
        ]
        inp = make_input(specialist_opinions=opinions)
        result = agent.run(inp)
        assert result.parsed["primary_diagnosis"] == "F32"
        assert "F41.1" in result.parsed["comorbid_diagnoses"]

    def test_abstain_decision(self):
        response = json.dumps({
            "primary_diagnosis": None,
            "confidence": 0.2,
            "decision": "abstain",
        })
        llm = FakeLLM(response=response)
        agent = JudgeAgent(llm_client=llm, prompts_dir=PROMPTS_DIR)
        opinions = [
            {"disorder_code": "F32", "confidence": 0.3, "reasoning": "Unclear"},
        ]
        inp = make_input(specialist_opinions=opinions)
        result = agent.run(inp)
        assert result.parsed["decision"] == "abstain"
        assert result.parsed["primary_diagnosis"] is None

    def test_confidence_clamped(self):
        response = json.dumps({
            "primary_diagnosis": "F32",
            "confidence": 1.5,
            "decision": "diagnosis",
        })
        llm = FakeLLM(response=response)
        agent = JudgeAgent(llm_client=llm, prompts_dir=PROMPTS_DIR)
        opinions = [
            {"disorder_code": "F32", "confidence": 0.9, "reasoning": "Test"},
        ]
        inp = make_input(specialist_opinions=opinions)
        result = agent.run(inp)
        assert result.parsed["confidence"] == 1.0

    def test_invalid_json_response(self):
        llm = FakeLLM(response="This is not JSON at all")
        agent = JudgeAgent(llm_client=llm, prompts_dir=PROMPTS_DIR)
        opinions = [
            {"disorder_code": "F32", "confidence": 0.9, "reasoning": "Test"},
        ]
        inp = make_input(specialist_opinions=opinions)
        result = agent.run(inp)
        assert result.parsed["decision"] == "abstain"
        assert result.parsed["confidence"] == 0.0

    def test_english_language(self):
        response = json.dumps({
            "primary_diagnosis": "F32",
            "confidence": 0.75,
            "decision": "diagnosis",
        })
        llm = FakeLLM(response=response)
        agent = JudgeAgent(llm_client=llm, prompts_dir=PROMPTS_DIR)
        opinions = [
            {"disorder_code": "F32", "confidence": 0.8, "reasoning": "Depression"},
        ]
        inp = make_input(specialist_opinions=opinions, language="en")
        result = agent.run(inp)
        assert result.parsed["language_used"] == "en"

    def test_comorbid_not_list_coerced(self):
        response = json.dumps({
            "primary_diagnosis": "F32",
            "comorbid_diagnoses": "F41.1",
            "confidence": 0.8,
            "decision": "diagnosis",
        })
        llm = FakeLLM(response=response)
        agent = JudgeAgent(llm_client=llm, prompts_dir=PROMPTS_DIR)
        opinions = [
            {"disorder_code": "F32", "confidence": 0.9, "reasoning": "Test"},
        ]
        inp = make_input(specialist_opinions=opinions)
        result = agent.run(inp)
        assert result.parsed["comorbid_diagnoses"] == []
