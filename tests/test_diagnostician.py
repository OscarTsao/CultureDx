"""Tests for DiagnosticianAgent."""
from __future__ import annotations

import json
from dataclasses import dataclass

from culturedx.agents.base import AgentInput
from culturedx.agents.diagnostician import DiagnosticianAgent


@dataclass
class MockLLM:
    model: str = "test-model"
    response: str = ""
    max_tokens: int = 512
    context_window: int | None = None
    last_prompt: str = ""

    @staticmethod
    def compute_prompt_hash(text: str) -> str:
        return "testhash"

    def generate(self, prompt: str, prompt_hash: str = "", language: str = "zh") -> str:
        self.last_prompt = prompt
        return self.response


def test_diagnostician_ranks_candidates(tmp_path):
    prompts_dir = tmp_path / "agents"
    prompts_dir.mkdir()
    (prompts_dir / "diagnostician_en.jinja").write_text(
        "Candidates: {% for code in candidate_disorders %}{{ code }} {% endfor %}\n"
        "Transcript: {{ transcript_text }}\n",
        encoding="utf-8",
    )
    (prompts_dir / "diagnostician_zh.jinja").write_text(
        "候选: {% for code in candidate_disorders %}{{ code }} {% endfor %}\n"
        "对话: {{ transcript_text }}\n",
        encoding="utf-8",
    )

    response = json.dumps(
        {
            "ranked_diagnoses": [
                {"code": "F41.1", "reasoning": "anxiety symptoms dominate"},
                {"code": "F32", "reasoning": "depressive symptoms are secondary"},
            ]
        }
    )
    agent = DiagnosticianAgent(llm_client=MockLLM(response=response), prompts_dir=prompts_dir)
    output = agent.run(
        AgentInput(
            transcript_text="Patient reports worry and tension.",
            language="en",
            extra={
                "candidate_disorders": ["F32", "F41.1", "F42"],
                "disorder_names": {
                    "F32": "Depressive episode",
                    "F41.1": "Generalized anxiety disorder",
                    "F42": "Obsessive-compulsive disorder",
                },
            },
        )
    )

    assert output.parsed["ranked_codes"] == ["F41.1", "F32"]
    assert output.parsed["reasoning"] == [
        "anxiety symptoms dominate",
        "depressive symptoms are secondary",
    ]


def test_diagnostician_rejects_out_of_scope_codes(tmp_path):
    prompts_dir = tmp_path / "agents"
    prompts_dir.mkdir()
    (prompts_dir / "diagnostician_en.jinja").write_text(
        "Candidates: {% for code in candidate_disorders %}{{ code }} {% endfor %}",
        encoding="utf-8",
    )
    (prompts_dir / "diagnostician_zh.jinja").write_text(
        "候选: {% for code in candidate_disorders %}{{ code }} {% endfor %}",
        encoding="utf-8",
    )

    response = json.dumps(
        {
            "ranked_diagnoses": [
                {"code": "F99", "reasoning": "invalid"},
            ]
        }
    )
    agent = DiagnosticianAgent(llm_client=MockLLM(response=response), prompts_dir=prompts_dir)
    output = agent.run(
        AgentInput(
            transcript_text="test",
            language="en",
            extra={"candidate_disorders": ["F32", "F41.1"]},
        )
    )

    assert output.parsed["ranked_codes"] == []
    assert output.parsed["reasoning"] == []


def test_diagnostician_truncates_prompt_for_small_context(tmp_path):
    prompts_dir = tmp_path / "agents"
    prompts_dir.mkdir()
    template = (
        "Candidates: {% for code in candidate_disorders %}{{ code }} {% endfor %}\n"
        "Transcript: {{ transcript_text }}\n"
    )
    (prompts_dir / "diagnostician_en.jinja").write_text(template, encoding="utf-8")
    (prompts_dir / "diagnostician_zh.jinja").write_text(template, encoding="utf-8")

    llm = MockLLM(
        response=json.dumps({"ranked_diagnoses": [{"code": "F32", "reasoning": "ok"}]}),
        max_tokens=256,
        context_window=1024,
    )
    agent = DiagnosticianAgent(llm_client=llm, prompts_dir=prompts_dir)
    long_transcript = "Patient reports worry. " * 1200
    agent.run(
        AgentInput(
            transcript_text=long_transcript,
            language="en",
            extra={"candidate_disorders": ["F32"]},
        )
    )

    assert llm.last_prompt
    assert len(llm.last_prompt) < len("Candidates: F32 \nTranscript: " + long_transcript + "\n")
    assert "omitted" in llm.last_prompt
