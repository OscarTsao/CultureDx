# Contrastive Criterion Disambiguation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Stage 2.5 to the HiED pipeline that re-evaluates shared ICD-10 criteria between F32 and F41.1 using an LLM contrastive agent, applying confidence-gated downgrades to break ranking ties.

**Architecture:** New ContrastiveCheckerAgent (BaseAgent subclass) fires between Stage 2 (criterion checkers) and Stage 3 (logic engine) when shared criteria are both-met across two disorders. A confidence-gated 3-tier downgrade modifies non-primary CriterionResults before passing to the logic engine.

**Tech Stack:** Python 3.11, dataclasses, Jinja2 templates, vLLM/Qwen3-32B, pytest

**Spec:** `docs/superpowers/specs/2026-03-21-contrastive-disambiguation-design.md`

---

## Chunk 1: Registry + Downgrade Logic

### Task 1: Shared Criteria Registry

**Files:**
- Create: `src/culturedx/ontology/shared_criteria.py`
- Test: `tests/test_contrastive.py`

- [ ] **Step 1: Write failing tests for registry**

Create `tests/test_contrastive.py`:

```python
"""Tests for contrastive criterion disambiguation."""
from __future__ import annotations

import pytest

from culturedx.ontology.shared_criteria import SharedCriterionPair, get_shared_pairs


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_contrastive.py::TestSharedCriteriaRegistry -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'culturedx.ontology.shared_criteria'`

- [ ] **Step 3: Implement shared_criteria.py**

Create `src/culturedx/ontology/shared_criteria.py`:

```python
"""Shared criteria registry for contrastive disambiguation between disorders."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SharedCriterionPair:
    """A pair of criteria from two disorders that evaluate the same symptom domain."""

    symptom_domain: str
    disorder_a: str
    criterion_a: str
    disorder_b: str
    criterion_b: str
    disambiguation_hint_en: str
    disambiguation_hint_zh: str


# Registry keyed by frozenset of disorder codes for order-independent lookup.
SHARED_CRITERIA: dict[frozenset[str], list[SharedCriterionPair]] = {
    frozenset({"F32", "F41.1"}): [
        SharedCriterionPair(
            symptom_domain="concentration",
            disorder_a="F32",
            criterion_a="C4",
            disorder_b="F41.1",
            criterion_b="B3",
            disambiguation_hint_en=(
                "Depressive concentration loss: linked to low mood, anhedonia, or "
                "psychomotor retardation. Patient loses interest in tasks. "
                "Anxiety concentration loss: linked to excessive worry, mind racing, "
                "or intrusive thoughts. Patient cannot focus because of worry. "
                "Key: Is poor concentration linked to low mood or to worry?"
            ),
            disambiguation_hint_zh=(
                "抑郁性注意力减退：与情绪低落、兴趣丧失或精神运动迟滞相关。"
                "患者对事物失去兴趣，无法集中注意力。"
                "焦虑性注意力减退：与过度担忧、思维奔逸或侵入性想法相关。"
                "患者因担忧而无法集中注意力。"
                "关键鉴别：注意力下降是因为情绪低落还是因为过度担忧？"
            ),
        ),
        SharedCriterionPair(
            symptom_domain="sleep",
            disorder_a="F32",
            criterion_a="C6",
            disorder_b="F41.1",
            criterion_b="B4",
            disambiguation_hint_en=(
                "Depressive insomnia: early morning awakening, rumination about past "
                "failures/guilt, hypersomnia also possible. "
                "Anxiety insomnia: difficulty falling asleep due to racing worried "
                "thoughts about future events, restless/unsatisfying sleep. "
                "Key: Is sleep disrupted by rumination (past) or worry (future)?"
            ),
            disambiguation_hint_zh=(
                "抑郁性失眠：早醒，反复回忆过去的失败/内疚，也可能出现嗜睡。"
                "焦虑性失眠：因对未来的担忧而入睡困难，睡眠不安宁、不满意。"
                "关键鉴别：睡眠障碍是因为反刍过去还是担忧未来？"
            ),
        ),
        SharedCriterionPair(
            symptom_domain="psychomotor",
            disorder_a="F32",
            criterion_a="C5",
            disorder_b="F41.1",
            criterion_b="B1",
            disambiguation_hint_en=(
                "Depressive psychomotor change: purposeless agitation (hand-wringing, "
                "pacing) OR retardation (slowed speech, reduced movement). "
                "Anxiety motor tension: tension-driven restlessness, fidgeting, "
                "inability to relax, muscle tension, hypervigilant scanning. "
                "Key: Is the agitation purposeless/distressed (depression) or "
                "tension-driven/hypervigilant (anxiety)?"
            ),
            disambiguation_hint_zh=(
                "抑郁性精神运动改变：无目的的激越（搓手、踱步）或迟滞"
                "（言语减少、动作迟缓）。"
                "焦虑性运动紧张：紧张驱动的坐立不安、无法放松、肌肉紧张、"
                "过度警觉。"
                "关键鉴别：激越是无目的的（抑郁）还是紧张驱动的（焦虑）？"
            ),
        ),
        SharedCriterionPair(
            symptom_domain="fatigue",
            disorder_a="F32",
            criterion_a="B3",
            disorder_b="F41.1",
            criterion_b="B1",
            disambiguation_hint_en=(
                "Depressive fatigue: anergic, present even after rest, no motivation, "
                "patient does not want to get out of bed. "
                "Anxiety fatigue: exhausted from sustained tension and worry, "
                "recovers with relaxation, driven by hyperarousal. "
                "Key: Is the patient fatigued even when not worrying?"
            ),
            disambiguation_hint_zh=(
                "抑郁性疲劳：即使休息后也感到疲惫、缺乏动力、什么都不想做。"
                "患者在静止状态下就感到疲倦。"
                "焦虑性疲劳：因长时间紧张和担忧而筋疲力尽，放松后可恢复。"
                "关键鉴别：患者在不担忧的时候是否仍然疲劳？"
            ),
        ),
    ],
}


def get_shared_pairs(disorder_a: str, disorder_b: str) -> list[SharedCriterionPair]:
    """Lookup shared criteria for a disorder pair. Order-independent."""
    return SHARED_CRITERIA.get(frozenset({disorder_a, disorder_b}), [])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_contrastive.py::TestSharedCriteriaRegistry -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/culturedx/ontology/shared_criteria.py tests/test_contrastive.py
git commit -m "feat: add shared criteria registry for F32/F41.1 contrastive disambiguation"
```

---

### Task 2: Confidence-Gated Downgrade Logic

**Files:**
- Modify: `tests/test_contrastive.py`
- Create: `src/culturedx/ontology/shared_criteria.py` (add `apply_attribution` function)

- [ ] **Step 1: Write failing tests for apply_attribution**

Append to `tests/test_contrastive.py`:

```python
from dataclasses import replace
from culturedx.core.models import CriterionResult
from culturedx.ontology.shared_criteria import apply_attribution


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
        assert result is base_criterion  # identity — no modification

    def test_primary_matches_this_disorder_no_change(self, base_criterion):
        result = apply_attribution(base_criterion, 0.90, "F32", "F32")
        assert result is base_criterion

    def test_high_confidence_full_downgrade(self, base_criterion):
        """attribution_confidence >= 0.8 -> insufficient_evidence, conf * 0.3."""
        result = apply_attribution(base_criterion, 0.85, "F41.1", "F32")
        assert result.status == "insufficient_evidence"
        assert result.confidence == pytest.approx(0.85 * 0.3)

    def test_high_confidence_boundary_at_0_8(self, base_criterion):
        result = apply_attribution(base_criterion, 0.80, "F41.1", "F32")
        assert result.status == "insufficient_evidence"
        assert result.confidence == pytest.approx(0.85 * 0.3)

    def test_medium_confidence_partial_downgrade(self, base_criterion):
        """0.6 <= attribution_confidence < 0.8 -> met stays, conf * 0.5."""
        result = apply_attribution(base_criterion, 0.70, "F41.1", "F32")
        assert result.status == "met"
        assert result.confidence == pytest.approx(0.85 * 0.5)

    def test_medium_confidence_boundary_at_0_6(self, base_criterion):
        result = apply_attribution(base_criterion, 0.60, "F41.1", "F32")
        assert result.status == "met"
        assert result.confidence == pytest.approx(0.85 * 0.5)

    def test_low_confidence_minimal_adjustment(self, base_criterion):
        """attribution_confidence < 0.6 -> met stays, conf * 0.8."""
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_contrastive.py::TestApplyAttribution -v`
Expected: FAIL with `ImportError: cannot import name 'apply_attribution'`

- [ ] **Step 3: Implement apply_attribution**

Add to `src/culturedx/ontology/shared_criteria.py`:

```python
from dataclasses import replace  # add at top

from culturedx.core.models import CriterionResult  # add at top


def apply_attribution(
    criterion_result: CriterionResult,
    attribution_confidence: float,
    attribution_target: str,
    this_disorder: str,
) -> CriterionResult:
    """Apply contrastive attribution to a criterion result.

    Returns the original object unchanged if this disorder is the primary
    or if the attribution is 'both'. Otherwise, applies a confidence-gated
    downgrade: high (>=0.8) full, medium (0.6-0.8) partial, low (<0.6) minimal.
    """
    if attribution_target == "both" or attribution_target == this_disorder:
        return criterion_result

    if attribution_confidence >= 0.8:
        return replace(
            criterion_result,
            status="insufficient_evidence",
            confidence=criterion_result.confidence * 0.3,
        )
    elif attribution_confidence >= 0.6:
        return replace(
            criterion_result,
            confidence=criterion_result.confidence * 0.5,
        )
    else:
        return replace(
            criterion_result,
            confidence=criterion_result.confidence * 0.8,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_contrastive.py -v`
Expected: all passed (registry + downgrade tests)

- [ ] **Step 5: Commit**

```bash
git add src/culturedx/ontology/shared_criteria.py tests/test_contrastive.py
git commit -m "feat: add confidence-gated downgrade logic for contrastive attribution"
```

---

## Chunk 2: Contrastive Agent + Prompts

### Task 3: Contrastive Checker Agent

**Files:**
- Create: `src/culturedx/agents/contrastive_checker.py`
- Create: `prompts/agents/contrastive_checker_zh.jinja`
- Create: `prompts/agents/contrastive_checker_en.jinja`
- Modify: `tests/test_contrastive.py`

- [ ] **Step 1: Write failing tests for ContrastiveCheckerAgent**

Append to `tests/test_contrastive.py`:

```python
import hashlib
import json

from culturedx.agents.base import AgentInput
from culturedx.agents.contrastive_checker import ContrastiveCheckerAgent


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
        pairs = get_shared_pairs("F32", "F41.1")[:2]  # concentration + sleep
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_contrastive.py::TestContrastiveCheckerAgent -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'culturedx.agents.contrastive_checker'`

- [ ] **Step 3: Create bilingual Jinja2 prompts**

Create `prompts/agents/contrastive_checker_zh.jinja`:

```
你是一位精神科鉴别诊断专家。你的任务是判断共享症状主要归属于哪个障碍。

## 临床对话

{{ transcript_text }}

## 共享症状评估

以下症状在两个障碍中都被标记为"满足"。请根据临床对话判断每个症状主要归属于哪个障碍。

{% for pair in shared_pairs %}
### 症状领域：{{ pair.symptom_domain }}

**{{ pair.disorder_a }} — {{ disorder_names[pair.disorder_a] }}**
标准 {{ pair.criterion_a }}：{{ checker_evidence[pair.disorder_a ~ "_" ~ pair.criterion_a].evidence | default("无证据") }}
（置信度：{{ checker_evidence[pair.disorder_a ~ "_" ~ pair.criterion_a].confidence | default(0) }}）

**{{ pair.disorder_b }} — {{ disorder_names[pair.disorder_b] }}**
标准 {{ pair.criterion_b }}：{{ checker_evidence[pair.disorder_b ~ "_" ~ pair.criterion_b].evidence | default("无证据") }}
（置信度：{{ checker_evidence[pair.disorder_b ~ "_" ~ pair.criterion_b].confidence | default(0) }}）

**鉴别要点：** {{ pair.disambiguation_hint_zh }}

{% endfor %}

## 输出要求

对每个症状领域，判断该症状主要归属于哪个障碍代码，或"both"（真正共病）。
给出你对归属判断的置信度（0.0-1.0）。

请严格按以下JSON格式输出：
{
  "attributions": [
    {
      "symptom_domain": "concentration",
      "primary_attribution": "F41.1",
      "attribution_confidence": 0.82,
      "reasoning": "患者明确将注意力问题与担忧联系起来"
    }
  ]
}
仅输出JSON，不要包含其他文字。
```

Create `prompts/agents/contrastive_checker_en.jinja`:

```
You are a psychiatric differential diagnosis specialist. Your task is to determine which disorder each shared symptom primarily belongs to.

## Clinical Transcript

{{ transcript_text }}

## Shared Symptom Evaluation

The following symptoms were marked as "met" in both disorders. Based on the clinical transcript, determine which disorder each symptom primarily belongs to.

{% for pair in shared_pairs %}
### Symptom Domain: {{ pair.symptom_domain }}

**{{ pair.disorder_a }} — {{ disorder_names[pair.disorder_a] }}**
Criterion {{ pair.criterion_a }}: {{ checker_evidence[pair.disorder_a ~ "_" ~ pair.criterion_a].evidence | default("no evidence") }}
(confidence: {{ checker_evidence[pair.disorder_a ~ "_" ~ pair.criterion_a].confidence | default(0) }})

**{{ pair.disorder_b }} — {{ disorder_names[pair.disorder_b] }}**
Criterion {{ pair.criterion_b }}: {{ checker_evidence[pair.disorder_b ~ "_" ~ pair.criterion_b].evidence | default("no evidence") }}
(confidence: {{ checker_evidence[pair.disorder_b ~ "_" ~ pair.criterion_b].confidence | default(0) }})

**Disambiguation guidance:** {{ pair.disambiguation_hint_en }}

{% endfor %}

## Output Instructions

For each symptom domain, determine which disorder code the symptom primarily belongs to, or "both" for true comorbidity.
Provide your confidence in the attribution (0.0-1.0).

Respond in exactly this JSON format:
{
  "attributions": [
    {
      "symptom_domain": "concentration",
      "primary_attribution": "F41.1",
      "attribution_confidence": 0.82,
      "reasoning": "Patient explicitly links concentration difficulty to worry cycles"
    }
  ]
}
Output JSON only. Do not include any other text.
```

- [ ] **Step 4: Implement ContrastiveCheckerAgent**

Create `src/culturedx/agents/contrastive_checker.py`:

```python
"""Contrastive checker agent: disambiguates shared criteria between disorders."""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.agents.base import AgentInput, AgentOutput, BaseAgent
from culturedx.llm.json_utils import extract_json_from_response

logger = logging.getLogger(__name__)

CONTRASTIVE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "attributions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "symptom_domain": {"type": "string"},
                    "primary_attribution": {"type": "string"},
                    "attribution_confidence": {"type": "number"},
                    "reasoning": {"type": "string"},
                },
                "required": [
                    "symptom_domain",
                    "primary_attribution",
                    "attribution_confidence",
                ],
            },
        }
    },
    "required": ["attributions"],
}


class ContrastiveCheckerAgent(BaseAgent):
    """Disambiguates shared criteria between two disorders."""

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/agents",
    ) -> None:
        self.llm = llm_client
        self.prompts_dir = Path(prompts_dir)
        self._env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            keep_trailing_newline=True,
        )

    def run(self, input: AgentInput) -> AgentOutput:
        """Evaluate shared criteria attribution between two disorders.

        Expects input.extra to contain:
            - shared_pairs: list[SharedCriterionPair]
            - checker_evidence: dict with "{disorder}_{criterion_id}" keys
            - disorder_names: dict mapping disorder_code -> name
        """
        shared_pairs = input.extra.get("shared_pairs", [])
        checker_evidence = input.extra.get("checker_evidence", {})
        disorder_names = input.extra.get("disorder_names", {})

        if not shared_pairs:
            return AgentOutput(raw_response="", parsed=None)

        # Render prompt
        template_name = f"contrastive_checker_{input.language}.jinja"
        template = self._env.get_template(template_name)
        prompt = template.render(
            transcript_text=input.transcript_text,
            shared_pairs=shared_pairs,
            checker_evidence=checker_evidence,
            disorder_names=disorder_names,
        )

        source, _, _ = self._env.loader.get_source(self._env, template_name)
        prompt_hash = self.llm.compute_prompt_hash(source)

        # Use guided JSON if available
        gen_kwargs: dict = {}
        if hasattr(self.llm, "generate"):
            import inspect
            sig = inspect.signature(self.llm.generate)
            if "json_schema" in sig.parameters:
                gen_kwargs["json_schema"] = CONTRASTIVE_JSON_SCHEMA

        raw = self.llm.generate(
            prompt, prompt_hash=prompt_hash, language=input.language, **gen_kwargs
        )

        # Parse response
        parsed = extract_json_from_response(raw)
        result = self._validate(parsed)

        return AgentOutput(
            raw_response=raw,
            parsed=result,
            model_name=self.llm.model,
            prompt_hash=prompt_hash,
        )

    @staticmethod
    def _validate(parsed: dict | list | None) -> dict | None:
        """Validate parsed JSON has the expected attributions structure."""
        if not parsed or not isinstance(parsed, dict):
            return None
        attributions = parsed.get("attributions")
        if not attributions or not isinstance(attributions, list):
            return None
        # Validate each attribution has required fields
        valid = []
        for attr in attributions:
            if not isinstance(attr, dict):
                continue
            if "symptom_domain" not in attr or "primary_attribution" not in attr:
                continue
            conf = attr.get("attribution_confidence", 0.5)
            valid.append({
                "symptom_domain": attr["symptom_domain"],
                "primary_attribution": attr["primary_attribution"],
                "attribution_confidence": max(0.0, min(1.0, float(conf))),
                "reasoning": attr.get("reasoning", ""),
            })
        if not valid:
            return None
        return {"attributions": valid}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_contrastive.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add src/culturedx/agents/contrastive_checker.py prompts/agents/contrastive_checker_zh.jinja prompts/agents/contrastive_checker_en.jinja tests/test_contrastive.py
git commit -m "feat: add ContrastiveCheckerAgent with bilingual prompts"
```

---

## Chunk 3: Pipeline Integration

### Task 4: Config + CLI Forwarding

**Files:**
- Modify: `src/culturedx/core/config.py:29-33` (ModeConfig)
- Modify: `src/culturedx/pipeline/cli.py:100-105` (run command HiEDMode construction)
- Modify: `src/culturedx/pipeline/cli.py:267-269` (sweep run_fn HiEDMode construction)
- Modify: `src/culturedx/modes/hied.py:43-51` (__init__ signature)

- [ ] **Step 1: Add contrastive_enabled to ModeConfig**

In `src/culturedx/core/config.py`, add to `ModeConfig`:

```python
class ModeConfig(BaseModel):
    name: str = "single"
    type: str = "single"
    variants: list[str] | None = None
    target_disorders: list[str] | None = None
    contrastive_enabled: bool = False
```

- [ ] **Step 2: Add contrastive_enabled parameter to HiEDMode.__init__**

In `src/culturedx/modes/hied.py`, modify `__init__`:

```python
def __init__(
    self,
    llm_client,
    prompts_dir: str | Path = "prompts/agents",
    target_disorders: list[str] | None = None,
    abstain_threshold: float = 0.3,
    comorbid_threshold: float = 0.5,
    differential_threshold: float = 0.10,
    contrastive_enabled: bool = False,
) -> None:
```

After the existing `self.comorbidity_resolver` line, add:

```python
    # Stage 2.5: Contrastive disambiguation (optional)
    self.contrastive_enabled = contrastive_enabled
    self.contrastive = None
    if self.contrastive_enabled:
        from culturedx.agents.contrastive_checker import ContrastiveCheckerAgent
        self.contrastive = ContrastiveCheckerAgent(llm_client, prompts_dir)
```

- [ ] **Step 3: Forward config in cli.py run command**

In `src/culturedx/pipeline/cli.py`, line 102-105, change:

```python
    if mode_type == "hied":
        from culturedx.modes.hied import HiEDMode
        mode = HiEDMode(
            llm_client=llm,
            target_disorders=cfg.mode.target_disorders,
            contrastive_enabled=cfg.mode.contrastive_enabled,
        )
```

- [ ] **Step 4: Forward config in cli.py sweep run_fn**

In `src/culturedx/pipeline/cli.py`, line 267-269, change:

```python
        if mode_type == "hied":
            from culturedx.modes.hied import HiEDMode
            mode = HiEDMode(
                llm_client=llm,
                target_disorders=condition.target_disorders,
                contrastive_enabled=cfg.mode.contrastive_enabled,
            )
```

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `uv run pytest tests/test_hied_e2e.py -v`
Expected: all existing tests pass (contrastive_enabled defaults to False, no behavior change)

- [ ] **Step 6: Commit**

```bash
git add src/culturedx/core/config.py src/culturedx/modes/hied.py src/culturedx/pipeline/cli.py
git commit -m "feat: add contrastive_enabled config flag and forward to HiEDMode"
```

---

### Task 5: HiED Stage 2.5 Integration

**Files:**
- Modify: `src/culturedx/modes/hied.py` (add `_run_contrastive` method, insert Stage 2.5 call)
- Modify: `tests/test_contrastive.py` (add B1 dedup test)

- [ ] **Step 1: Write failing test for B1 deduplication**

Append to `tests/test_contrastive.py`:

```python
from culturedx.core.models import CheckerOutput


class TestDeduplication:
    """Tests for per-criterion-id deduplication in contrastive application."""

    def test_b1_dedup_highest_confidence_wins(self):
        """F41.1.B1 targeted by two attributions — only highest confidence applied."""
        from culturedx.ontology.shared_criteria import apply_attributions_to_checker_output

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
        # psychomotor: confidence 0.85, target F32 -> would full-downgrade B1
        # fatigue: confidence 0.65, target F32 -> would medium-downgrade B1
        # Dedup: highest confidence (0.85) wins -> full downgrade
        attribution_map = {
            ("F41.1", "B1"): (0.85, "F32"),
            ("F41.1", "B3"): (0.70, "F32"),
        }
        result = apply_attributions_to_checker_output(checker_output, attribution_map)
        b1 = next(c for c in result.criteria if c.criterion_id == "B1")
        assert b1.status == "insufficient_evidence"
        assert b1.confidence == pytest.approx(0.80 * 0.3)
        # B3 medium downgrade
        b3 = next(c for c in result.criteria if c.criterion_id == "B3")
        assert b3.status == "met"
        assert b3.confidence == pytest.approx(0.90 * 0.5)
        # met count should be recomputed: A, B2, B3, B4 = 4 met (B1 downgraded)
        assert result.criteria_met_count == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_contrastive.py::TestDeduplication -v`
Expected: FAIL with `ImportError: cannot import name 'apply_attributions_to_checker_output'`

- [ ] **Step 3: Implement apply_attributions_to_checker_output**

Add to `src/culturedx/ontology/shared_criteria.py`:

```python
from culturedx.core.models import CheckerOutput  # add at top if not already


def apply_attributions_to_checker_output(
    checker_output: CheckerOutput,
    attribution_map: dict[tuple[str, str], tuple[float, str]],
) -> CheckerOutput:
    """Apply deduped attributions to a single CheckerOutput.

    attribution_map: {(disorder, criterion_id): (attribution_confidence, target_disorder)}
    Only entries matching this checker_output's disorder are applied.
    """
    disorder = checker_output.disorder
    new_criteria = []
    for cr in checker_output.criteria:
        key = (disorder, cr.criterion_id)
        if key in attribution_map:
            conf, target = attribution_map[key]
            new_criteria.append(apply_attribution(cr, conf, target, disorder))
        else:
            new_criteria.append(cr)
    new_met_count = sum(1 for c in new_criteria if c.status == "met")
    return replace(
        checker_output,
        criteria=new_criteria,
        criteria_met_count=new_met_count,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_contrastive.py -v`
Expected: all passed

- [ ] **Step 5: Implement _run_contrastive in hied.py**

Add imports at top of `src/culturedx/modes/hied.py`:

```python
from dataclasses import replace
```

Add the `_run_contrastive` method to `HiEDMode` class:

```python
def _run_contrastive(
    self,
    checker_outputs: list[CheckerOutput],
    transcript_text: str,
    lang: str,
) -> list[CheckerOutput]:
    """Stage 2.5: Contrastive disambiguation of shared criteria."""
    from itertools import combinations

    from culturedx.ontology.shared_criteria import (
        apply_attributions_to_checker_output,
        get_shared_pairs,
    )

    # Build disorder -> CheckerOutput index
    co_index: dict[str, CheckerOutput] = {co.disorder: co for co in checker_outputs}

    # Find shared criteria that are both-met
    all_shared_pairs = []
    checker_evidence: dict[str, dict] = {}

    for d1, d2 in combinations(co_index.keys(), 2):
        pairs = get_shared_pairs(d1, d2)
        if not pairs:
            continue

        # Build criterion lookup for each disorder
        cr_a = {cr.criterion_id: cr for cr in co_index[d1].criteria}
        cr_b = {cr.criterion_id: cr for cr in co_index[d2].criteria}

        for pair in pairs:
            crit_a = cr_a.get(pair.criterion_a)
            crit_b = cr_b.get(pair.criterion_b)
            if (
                crit_a
                and crit_b
                and crit_a.status == "met"
                and crit_b.status == "met"
            ):
                all_shared_pairs.append(pair)
                key_a = f"{pair.disorder_a}_{pair.criterion_a}"
                key_b = f"{pair.disorder_b}_{pair.criterion_b}"
                checker_evidence[key_a] = {
                    "status": crit_a.status,
                    "evidence": crit_a.evidence,
                    "confidence": crit_a.confidence,
                }
                checker_evidence[key_b] = {
                    "status": crit_b.status,
                    "evidence": crit_b.evidence,
                    "confidence": crit_b.confidence,
                }

    if not all_shared_pairs:
        return checker_outputs

    # Collect disorder names for prompt
    disorder_names = {}
    for pair in all_shared_pairs:
        for code in (pair.disorder_a, pair.disorder_b):
            if code not in disorder_names:
                disorder_names[code] = get_disorder_name(code, lang) or code

    # Call contrastive agent
    agent_input = AgentInput(
        transcript_text=transcript_text,
        language=lang,
        extra={
            "shared_pairs": all_shared_pairs,
            "checker_evidence": checker_evidence,
            "disorder_names": disorder_names,
        },
    )

    output = self.contrastive.run(agent_input)

    # Graceful fallback on failure
    if not output.parsed or not output.parsed.get("attributions"):
        logger.info("Contrastive agent returned no attributions, skipping")
        return checker_outputs

    # Build deduped attribution map: (disorder, criterion_id) -> (confidence, target)
    attribution_map: dict[tuple[str, str], tuple[float, str]] = {}
    # Index pairs by symptom_domain for lookup
    pair_by_domain = {p.symptom_domain: p for p in all_shared_pairs}

    for attr in output.parsed["attributions"]:
        domain = attr["symptom_domain"]
        pair = pair_by_domain.get(domain)
        if not pair:
            continue
        conf = attr["attribution_confidence"]
        target = attr["primary_attribution"]

        # Register for both sides of the pair
        for disorder, criterion_id in [
            (pair.disorder_a, pair.criterion_a),
            (pair.disorder_b, pair.criterion_b),
        ]:
            key = (disorder, criterion_id)
            if key not in attribution_map or conf > attribution_map[key][0]:
                attribution_map[key] = (conf, target)

    # Apply attributions to each affected CheckerOutput
    result = []
    for co in checker_outputs:
        if any(k[0] == co.disorder for k in attribution_map):
            result.append(apply_attributions_to_checker_output(co, attribution_map))
        else:
            result.append(co)

    logger.info(
        "Contrastive: %d shared pairs evaluated, %d attributions applied",
        len(all_shared_pairs),
        len(attribution_map),
    )
    return result
```

Insert Stage 2.5 call in `diagnose()`, between Stage 2 and Stage 3 (after line 119, before line 121):

```python
        # === Stage 2.5: Contrastive Disambiguation ===
        if self.contrastive_enabled and self.contrastive is not None:
            checker_outputs = self._run_contrastive(
                checker_outputs, transcript_text, lang,
            )
```

- [ ] **Step 6: Run existing tests to verify no regressions**

Run: `uv run pytest tests/test_hied_e2e.py tests/test_contrastive.py -v`
Expected: all pass (contrastive_enabled=False by default)

- [ ] **Step 7: Commit**

```bash
git add src/culturedx/ontology/shared_criteria.py src/culturedx/modes/hied.py tests/test_contrastive.py
git commit -m "feat: integrate Stage 2.5 contrastive disambiguation into HiED pipeline"
```

---

## Chunk 4: E2E Tests

### Task 6: E2E Golden Tests for Contrastive

**Files:**
- Modify: `tests/test_hied_e2e.py`

- [ ] **Step 1: Write E2E test — contrastive fires and shifts ranking**

Append to `tests/test_hied_e2e.py` inside `TestHiEDE2E` class:

```python
    # ------------------------------------------------------------------
    # Case 7: Contrastive fires — F32 criteria downgraded, F41.1 wins
    # ------------------------------------------------------------------

    def test_contrastive_shifts_ranking_to_f41_1(self):
        """When contrastive is enabled and shared criteria favor F41.1,
        F32's shared criteria get downgraded, shifting ranking toward F41.1.

        Setup:
        - F32: 6 met including C4(concentration), C5(psychomotor), C6(sleep)
        - F41.1: 5 met (all) including B1, B3, B4
        - Contrastive attributes concentration->F41.1, sleep->F41.1 (high conf)
        - After downgrade: F32 C4->insuff, C6->insuff, losing 2 met
        - F32 still confirmed (4 met >= 4 total), but lower calibrator score
        - F41.1 unchanged -> now ranks higher
        """
        f32_resp = _f32_checker_response()
        f41_resp = _f41_1_all_met_response()

        class ContrastiveMockLLM(MockLLMClient):
            def generate(self, prompt, **kwargs):
                # Detect contrastive prompt by unique marker
                if "共享症状评估" in prompt or "Shared Symptom Evaluation" in prompt:
                    return json.dumps({
                        "attributions": [
                            {
                                "symptom_domain": "concentration",
                                "primary_attribution": "F41.1",
                                "attribution_confidence": 0.85,
                                "reasoning": "worry-driven",
                            },
                            {
                                "symptom_domain": "sleep",
                                "primary_attribution": "F41.1",
                                "attribution_confidence": 0.82,
                                "reasoning": "anxiety insomnia",
                            },
                            {
                                "symptom_domain": "psychomotor",
                                "primary_attribution": "both",
                                "attribution_confidence": 0.55,
                                "reasoning": "ambiguous",
                            },
                            {
                                "symptom_domain": "fatigue",
                                "primary_attribution": "both",
                                "attribution_confidence": 0.50,
                                "reasoning": "ambiguous",
                            },
                        ]
                    })
                return super().generate(prompt, **kwargs)

        llm = ContrastiveMockLLM({"F32": f32_resp, "F41.1": f41_resp})
        mode = HiEDMode(
            llm_client=llm,
            prompts_dir=PROMPTS_DIR,
            target_disorders=["F32", "F41.1"],
            contrastive_enabled=True,
        )
        result = mode.diagnose(_make_case())
        assert result.decision == "diagnosis"
        assert result.primary_diagnosis == "F41.1"

    # ------------------------------------------------------------------
    # Case 8: Contrastive disabled — same inputs but F32 wins (V10 behavior)
    # ------------------------------------------------------------------

    def test_contrastive_disabled_f32_wins(self):
        """With contrastive_enabled=False, same case produces F32 as primary
        (original V10 behavior where F32 gets higher calibrator score due to
        more met criteria).
        """
        f32_resp = _f32_checker_response()
        f41_resp = _f41_1_all_met_response()
        llm = MockLLMClient({"F32": f32_resp, "F41.1": f41_resp})
        mode = HiEDMode(
            llm_client=llm,
            prompts_dir=PROMPTS_DIR,
            target_disorders=["F32", "F41.1"],
            contrastive_enabled=False,
        )
        result = mode.diagnose(_make_case())
        assert result.decision == "diagnosis"
        # Without contrastive, F32 has higher calibrated score
        assert result.primary_diagnosis == "F32"

    # ------------------------------------------------------------------
    # Case 9: Contrastive skipped — only one disorder confirmed
    # ------------------------------------------------------------------

    def test_contrastive_skipped_single_disorder(self):
        """Contrastive is enabled but only F32 passes checker -> no shared
        criteria are both-met -> contrastive not called -> normal F32 diagnosis.
        """
        f32_resp = _f32_checker_response()
        f41_resp = _f41_1_below_threshold_response()
        llm = MockLLMClient({"F32": f32_resp, "F41.1": f41_resp})
        mode = HiEDMode(
            llm_client=llm,
            prompts_dir=PROMPTS_DIR,
            target_disorders=["F32", "F41.1"],
            contrastive_enabled=True,
        )
        result = mode.diagnose(_make_case())
        assert result.decision == "diagnosis"
        assert result.primary_diagnosis == "F32"

    # ------------------------------------------------------------------
    # Case 10: Contrastive returns "both" — true comorbidity preserved
    # ------------------------------------------------------------------

    def test_contrastive_both_preserves_comorbidity(self):
        """When contrastive returns 'both' for all pairs, no criteria are
        downgraded -> both disorders remain confirmed with original scores.
        """
        f32_resp = _f32_checker_response()
        f41_resp = _f41_1_all_met_response()

        class BothMockLLM(MockLLMClient):
            def generate(self, prompt, **kwargs):
                if "共享症状评估" in prompt or "Shared Symptom Evaluation" in prompt:
                    return json.dumps({
                        "attributions": [
                            {"symptom_domain": d, "primary_attribution": "both",
                             "attribution_confidence": 0.90, "reasoning": "comorbid"}
                            for d in ["concentration", "sleep", "psychomotor", "fatigue"]
                        ]
                    })
                return super().generate(prompt, **kwargs)

        llm = BothMockLLM({"F32": f32_resp, "F41.1": f41_resp})
        mode = HiEDMode(
            llm_client=llm,
            prompts_dir=PROMPTS_DIR,
            target_disorders=["F32", "F41.1"],
            contrastive_enabled=True,
        )
        result = mode.diagnose(_make_case())
        assert result.decision == "diagnosis"
        # "both" means no downgrade -> same as V10 -> F32 primary
        assert result.primary_diagnosis == "F32"
        assert "F41.1" in result.comorbid_diagnoses
```

- [ ] **Step 2: Run E2E tests to verify they pass**

Run: `uv run pytest tests/test_hied_e2e.py -v`
Expected: all pass (original 6 + new 4 contrastive cases)

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest tests/ -v --ignore=tests/test_bge_m3.py`
Expected: all pass (excluding known GPU OOM test)

- [ ] **Step 4: Commit**

```bash
git add tests/test_hied_e2e.py
git commit -m "test: add E2E golden tests for contrastive disambiguation"
```

---

## Chunk 5: Final Verification

### Task 7: Integration Verification

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -q --ignore=tests/test_bge_m3.py`
Expected: all pass

- [ ] **Step 2: Verify config default is safe**

Run: `uv run python -c "from culturedx.core.config import ModeConfig; m = ModeConfig(); print(f'contrastive_enabled={m.contrastive_enabled}')"`
Expected: `contrastive_enabled=False`

- [ ] **Step 3: Verify HiED constructs with contrastive flag**

Run: `uv run python -c "
from culturedx.modes.hied import HiEDMode
class MockLLM:
    model = 'test'
    max_concurrent = 1
m = HiEDMode(MockLLM(), contrastive_enabled=True)
print(f'contrastive_enabled={m.contrastive_enabled}, agent={m.contrastive is not None}')
m2 = HiEDMode(MockLLM(), contrastive_enabled=False)
print(f'contrastive_enabled={m2.contrastive_enabled}, agent={m2.contrastive is not None}')
"`
Expected:
```
contrastive_enabled=True, agent=True
contrastive_enabled=False, agent=False
```

- [ ] **Step 4: Final commit with all files**

```bash
git add -A
git status
git commit -m "feat: complete contrastive criterion disambiguation (Stage 2.5)

Add HiED Stage 2.5 that re-evaluates shared ICD-10 criteria between
F32 and F41.1 when both are confirmed. Uses an LLM contrastive agent
with confidence-gated 3-tier downgrade to break ranking ties.

- Shared criteria registry (4 F32/F41.1 pairs with bilingual hints)
- ContrastiveCheckerAgent with guided JSON schema
- Confidence-gated downgrade: >=0.8 full, 0.6-0.8 partial, <0.6 minimal
- Per-criterion-id deduplication (F41.1.B1 appears in 2 pairs)
- Config flag contrastive_enabled (default False for safe rollout)
- 4 E2E golden tests covering: fires, disabled, skipped, comorbid"
```
