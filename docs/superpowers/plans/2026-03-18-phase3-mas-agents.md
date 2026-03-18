# Phase 3: Multi-Agent System Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the multi-agent diagnostic system that coordinates criterion-checking and differential diagnosis agents to outperform single-model baselines on Chinese psychiatric diagnosis.

**Architecture:** Two-agent pipeline with genuine asymmetry. A CriterionCheckerAgent evaluates per-disorder criteria against evidence (structured, focused). A DifferentialDiagnosisAgent synthesizes across disorders for final diagnosis (holistic, clinical judgment). A MASMode orchestrator coordinates the flow: candidate selection → parallel criterion checking → differential synthesis → DiagnosisResult.

**Tech Stack:** Python 3.11+, Jinja2 (prompts), OllamaClient (LLM), existing EvidenceBrief/CheckerOutput/CriterionResult data structures.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/culturedx/agents/criterion_checker.py` | CriterionCheckerAgent: per-disorder criteria evaluation |
| `src/culturedx/agents/differential.py` | DifferentialDiagnosisAgent: cross-disorder synthesis |
| `src/culturedx/modes/mas.py` | MASMode orchestrator |
| `prompts/agents/criterion_checker_zh.jinja` | Chinese criterion checking prompt |
| `prompts/agents/criterion_checker_en.jinja` | English criterion checking prompt |
| `prompts/agents/differential_zh.jinja` | Chinese differential diagnosis prompt |
| `prompts/agents/differential_en.jinja` | English differential diagnosis prompt |
| `configs/mas.yaml` | MAS mode config overlay |
| `tests/test_criterion_checker.py` | CriterionCheckerAgent tests |
| `tests/test_differential.py` | DifferentialDiagnosisAgent tests |
| `tests/test_mas_mode.py` | MASMode orchestrator tests |

---

## Chunk 1: CriterionCheckerAgent

### Task 1: Criterion Checker Prompts

**Files:**
- Create: `prompts/agents/criterion_checker_zh.jinja`
- Create: `prompts/agents/criterion_checker_en.jinja`

- [ ] **Step 1: Create Chinese criterion checker prompt**

Create `prompts/agents/criterion_checker_zh.jinja`:
```
你是一位精神科诊断标准评估专家。你的任务是评估以下临床证据是否满足 {{ disorder_code }} ({{ disorder_name }}) 的各项ICD-10诊断标准。

## 诊断标准

{% for crit in criteria %}
### {{ crit.id }}
{{ crit.text_zh }}
类型: {{ crit.type }}

相关证据:
{% if crit.evidence %}
{% for e in crit.evidence %}
- Turn {{ e.turn_id }}: "{{ e.text }}" (置信度: {{ "%.2f"|format(e.confidence) }})
{% endfor %}
{% else %}
无直接相关证据。
{% endif %}

{% endfor %}

## 诊断阈值
- 所需核心标准数: {{ threshold.get('min_core', 'N/A') }}
- 所需总标准数: {{ threshold.get('min_total', 'N/A') }}
- 病程要求: {{ threshold.get('duration_weeks', threshold.get('duration_months', 'N/A')) }}

## 输出要求

请逐一评估每项标准，以JSON格式输出：
{
  "criteria": [
    {
      "criterion_id": "B1",
      "status": "met|not_met|insufficient_evidence",
      "evidence_summary": "简述支持或不支持的证据",
      "confidence": 0.0到1.0
    }
  ],
  "criteria_met_count": 总满足数,
  "threshold_met": true或false,
  "reasoning": "简述是否达到诊断阈值"
}
```

Create `prompts/agents/criterion_checker_en.jinja`:
```
You are a psychiatric diagnostic criteria evaluation expert. Your task is to assess whether the clinical evidence satisfies the ICD-10 diagnostic criteria for {{ disorder_code }} ({{ disorder_name }}).

## Diagnostic Criteria

{% for crit in criteria %}
### {{ crit.id }}
{{ crit.text }}
Type: {{ crit.type }}

Relevant evidence:
{% if crit.evidence %}
{% for e in crit.evidence %}
- Turn {{ e.turn_id }}: "{{ e.text }}" (confidence: {{ "%.2f"|format(e.confidence) }})
{% endfor %}
{% else %}
No directly relevant evidence.
{% endif %}

{% endfor %}

## Diagnostic Threshold
- Required core criteria: {{ threshold.get('min_core', 'N/A') }}
- Required total criteria: {{ threshold.get('min_total', 'N/A') }}
- Duration requirement: {{ threshold.get('duration_weeks', threshold.get('duration_months', 'N/A')) }}

## Output Requirements

Evaluate each criterion and respond in JSON format:
{
  "criteria": [
    {
      "criterion_id": "B1",
      "status": "met|not_met|insufficient_evidence",
      "evidence_summary": "brief summary of supporting or opposing evidence",
      "confidence": 0.0 to 1.0
    }
  ],
  "criteria_met_count": total_met,
  "threshold_met": true or false,
  "reasoning": "brief assessment of whether diagnostic threshold is met"
}
```

- [ ] **Step 2: Commit prompts**

```bash
git add prompts/agents/criterion_checker_zh.jinja prompts/agents/criterion_checker_en.jinja
git commit -m "feat: criterion checker agent bilingual prompts"
```

### Task 2: CriterionCheckerAgent Implementation

**Files:**
- Create: `src/culturedx/agents/criterion_checker.py`
- Test: `tests/test_criterion_checker.py`

- [ ] **Step 1: Write tests**

Create `tests/test_criterion_checker.py`:

```python
# tests/test_criterion_checker.py
"""Tests for CriterionCheckerAgent."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from jinja2 import DictLoader, Environment

from culturedx.agents.criterion_checker import CriterionCheckerAgent
from culturedx.core.models import (
    CriterionEvidence,
    DisorderEvidence,
    EvidenceBrief,
    SymptomSpan,
    CheckerOutput,
)


@pytest.fixture
def mock_llm():
    client = MagicMock()
    client.model = "test-model"
    client.compute_prompt_hash.return_value = "hash123"
    return client


@pytest.fixture
def sample_disorder_evidence():
    """F32 evidence with 2 criteria matched."""
    return DisorderEvidence(
        disorder_code="F32",
        disorder_name="Depressive episode",
        criteria_evidence=[
            CriterionEvidence(
                criterion_id="F32.B1",
                spans=[SymptomSpan(text="情绪低落", turn_id=1, symptom_type="emotional")],
                confidence=0.85,
            ),
            CriterionEvidence(
                criterion_id="F32.B2",
                spans=[SymptomSpan(text="什么都没兴趣", turn_id=2, symptom_type="emotional")],
                confidence=0.78,
            ),
            CriterionEvidence(
                criterion_id="F32.C6",
                spans=[SymptomSpan(text="失眠", turn_id=1, symptom_type="somatic", is_somatic=True)],
                confidence=0.72,
            ),
        ],
    )


class TestCriterionCheckerAgent:
    def test_check_returns_checker_output(self, mock_llm, sample_disorder_evidence):
        """Agent returns a CheckerOutput with parsed criteria results."""
        mock_llm.generate.return_value = json.dumps({
            "criteria": [
                {"criterion_id": "B1", "status": "met", "evidence_summary": "低落情绪", "confidence": 0.9},
                {"criterion_id": "B2", "status": "met", "evidence_summary": "兴趣减退", "confidence": 0.8},
                {"criterion_id": "C6", "status": "met", "evidence_summary": "失眠", "confidence": 0.7},
            ],
            "criteria_met_count": 3,
            "threshold_met": True,
            "reasoning": "满足核心标准2项，总标准3项",
        })
        agent = CriterionCheckerAgent(llm_client=mock_llm, prompts_dir="/tmp")
        agent._env = Environment(loader=DictLoader({
            "criterion_checker_zh.jinja": "{{ disorder_code }}",
            "criterion_checker_en.jinja": "{{ disorder_code }}",
        }))
        output = agent.check(
            disorder_code="F32",
            disorder_evidence=sample_disorder_evidence,
            language="zh",
        )
        assert isinstance(output, CheckerOutput)
        assert output.disorder == "F32"
        assert output.criteria_met_count == 3
        assert len(output.criteria) == 3
        assert output.criteria[0].status == "met"

    def test_check_parse_failure_returns_empty(self, mock_llm, sample_disorder_evidence):
        """Parse failure returns CheckerOutput with zero met count."""
        mock_llm.generate.return_value = "I cannot evaluate this."
        agent = CriterionCheckerAgent(llm_client=mock_llm, prompts_dir="/tmp")
        agent._env = Environment(loader=DictLoader({
            "criterion_checker_zh.jinja": "{{ disorder_code }}",
        }))
        output = agent.check(
            disorder_code="F32",
            disorder_evidence=sample_disorder_evidence,
            language="zh",
        )
        assert isinstance(output, CheckerOutput)
        assert output.criteria_met_count == 0
        assert output.criteria == []

    def test_check_unsupported_language(self, mock_llm, sample_disorder_evidence):
        """Unsupported language returns empty CheckerOutput."""
        agent = CriterionCheckerAgent(llm_client=mock_llm, prompts_dir="/tmp")
        agent._env = Environment(loader=DictLoader({}))
        output = agent.check(
            disorder_code="F32",
            disorder_evidence=sample_disorder_evidence,
            language="ko",
        )
        assert output.criteria_met_count == 0

    def test_builds_criteria_context(self, mock_llm, sample_disorder_evidence):
        """Verify the agent builds proper criteria context from ontology + evidence."""
        mock_llm.generate.return_value = json.dumps({
            "criteria": [], "criteria_met_count": 0,
            "threshold_met": False, "reasoning": "no",
        })
        agent = CriterionCheckerAgent(llm_client=mock_llm, prompts_dir="/tmp")
        agent._env = Environment(loader=DictLoader({
            "criterion_checker_zh.jinja": "{% for crit in criteria %}{{ crit.id }},{% endfor %}",
        }))
        output = agent.check(
            disorder_code="F32",
            disorder_evidence=sample_disorder_evidence,
            language="zh",
        )
        # Verify LLM was called (prompt was rendered)
        mock_llm.generate.assert_called_once()
        prompt = mock_llm.generate.call_args[0][0]
        # Prompt should contain criterion IDs from the ontology
        assert "A," in prompt or "B1," in prompt  # ontology criteria
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/user/YuNing/CultureDx && uv run pytest tests/test_criterion_checker.py -v 2>&1
```

- [ ] **Step 3: Implement CriterionCheckerAgent**

Create `src/culturedx/agents/criterion_checker.py`:

```python
# src/culturedx/agents/criterion_checker.py
"""Criterion checker agent: evaluates per-disorder ICD-10 criteria against evidence."""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.core.models import (
    CheckerOutput,
    CriterionResult,
    DisorderEvidence,
)
from culturedx.llm.json_utils import extract_json_from_response
from culturedx.ontology.icd10 import (
    get_disorder_criteria,
    get_disorder_name,
    get_criterion_text,
)

logger = logging.getLogger(__name__)


class CriterionCheckerAgent:
    """Evaluate whether evidence satisfies ICD-10 criteria for a disorder."""

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/agents",
    ) -> None:
        self.llm = llm_client
        self._env = Environment(
            loader=FileSystemLoader(str(prompts_dir)),
            keep_trailing_newline=True,
        )

    def check(
        self,
        disorder_code: str,
        disorder_evidence: DisorderEvidence,
        language: str = "zh",
    ) -> CheckerOutput:
        """Check criteria for a single disorder against evidence.

        Args:
            disorder_code: ICD-10 code (e.g., "F32").
            disorder_evidence: Evidence matched to this disorder's criteria.
            language: Language code ("zh" or "en").

        Returns:
            CheckerOutput with per-criterion results and met counts.
        """
        if language not in ("zh", "en"):
            logger.warning("Unsupported language '%s' for checker, skipping", language)
            return CheckerOutput(disorder=disorder_code)

        # Build criteria context from ontology + evidence
        criteria_context = self._build_criteria_context(
            disorder_code, disorder_evidence, language
        )
        if not criteria_context["criteria"]:
            return CheckerOutput(disorder=disorder_code)

        # Render prompt
        template_name = f"criterion_checker_{language}.jinja"
        template = self._env.get_template(template_name)
        prompt = template.render(
            disorder_code=disorder_code,
            disorder_name=criteria_context["disorder_name"],
            criteria=criteria_context["criteria"],
            threshold=criteria_context["threshold"],
        )

        source, _, _ = self._env.loader.get_source(self._env, template_name)
        prompt_hash = self.llm.compute_prompt_hash(source)

        # Call LLM
        raw = self.llm.generate(prompt, prompt_hash=prompt_hash, language=language)
        parsed = extract_json_from_response(raw)

        if parsed is None or not isinstance(parsed, dict):
            logger.warning("Checker parse failed for %s", disorder_code)
            return CheckerOutput(disorder=disorder_code)

        return self._parse_output(disorder_code, parsed)

    def _build_criteria_context(
        self,
        disorder_code: str,
        disorder_evidence: DisorderEvidence,
        language: str,
    ) -> dict:
        """Build criteria context merging ontology definitions with evidence."""
        ontology_criteria = get_disorder_criteria(disorder_code)
        if ontology_criteria is None:
            return {"criteria": [], "threshold": {}, "disorder_name": disorder_code}

        # Build evidence lookup: criterion_id -> CriterionEvidence
        evidence_map = {}
        for ce in disorder_evidence.criteria_evidence:
            evidence_map[ce.criterion_id] = ce

        criteria_list = []
        for crit_id, crit_info in ontology_criteria.items():
            full_id = f"{disorder_code}.{crit_id}"
            text_key = "text_zh" if language == "zh" else "text"
            crit_text = crit_info.get(text_key, crit_info.get("text", ""))

            # Get matched evidence for this criterion
            ce = evidence_map.get(full_id)
            evidence_entries = []
            if ce:
                for span in ce.spans:
                    evidence_entries.append({
                        "text": span.text,
                        "turn_id": span.turn_id,
                        "confidence": ce.confidence,
                    })

            criteria_list.append({
                "id": crit_id,
                "text": crit_info.get("text", ""),
                "text_zh": crit_info.get("text_zh", ""),
                "type": crit_info.get("type", ""),
                "evidence": evidence_entries,
            })

        # Get threshold from ontology (stored at disorder level)
        from culturedx.ontology.icd10 import _load
        disorders = _load()["disorders"]
        disorder_data = disorders.get(disorder_code, {})
        threshold = disorder_data.get("threshold", {})

        disorder_name = get_disorder_name(disorder_code, language) or disorder_code

        return {
            "criteria": criteria_list,
            "threshold": threshold,
            "disorder_name": disorder_name,
        }

    @staticmethod
    def _parse_output(disorder_code: str, parsed: dict) -> CheckerOutput:
        """Parse LLM JSON response into CheckerOutput."""
        criteria = []
        for c in parsed.get("criteria", []):
            if not isinstance(c, dict):
                continue
            status = c.get("status", "insufficient_evidence")
            if status not in ("met", "not_met", "insufficient_evidence"):
                status = "insufficient_evidence"
            criteria.append(
                CriterionResult(
                    criterion_id=c.get("criterion_id", ""),
                    status=status,
                    evidence=c.get("evidence_summary"),
                    confidence=float(c.get("confidence", 0.0)),
                )
            )

        met_count = parsed.get("criteria_met_count", 0)
        if not isinstance(met_count, int):
            met_count = sum(1 for c in criteria if c.status == "met")

        # Get required count from ontology threshold
        from culturedx.ontology.icd10 import _load
        disorders = _load()["disorders"]
        disorder_data = disorders.get(disorder_code, {})
        threshold = disorder_data.get("threshold", {})
        required = threshold.get("min_total", threshold.get("min_symptoms", 0))

        return CheckerOutput(
            disorder=disorder_code,
            criteria=criteria,
            criteria_met_count=met_count,
            criteria_required=required,
        )
```

- [ ] **Step 4: Run tests**

```bash
cd /home/user/YuNing/CultureDx && uv run pytest tests/test_criterion_checker.py -v 2>&1
```

- [ ] **Step 5: Commit**

```bash
git add src/culturedx/agents/criterion_checker.py tests/test_criterion_checker.py
git commit -m "feat: CriterionCheckerAgent with per-disorder criteria evaluation"
```

### Task 3: DifferentialDiagnosisAgent Prompts

**Files:**
- Create: `prompts/agents/differential_zh.jinja`
- Create: `prompts/agents/differential_en.jinja`

- [ ] **Step 1: Create bilingual differential diagnosis prompts**

Create `prompts/agents/differential_zh.jinja`:
```
你是一位精神科鉴别诊断专家。根据以下各候选障碍的标准评估结果，做出最终的鉴别诊断。

## 候选障碍评估结果

{% for result in checker_results %}
### {{ result.disorder_code }} {{ result.disorder_name }}
满足标准数: {{ result.met_count }} / 所需: {{ result.required }}
阈值是否达到: {{ "是" if result.threshold_met else "否" }}

满足的标准:
{% for c in result.met_criteria %}
- {{ c.criterion_id }}: {{ c.evidence_summary }} (置信度: {{ "%.2f"|format(c.confidence) }})
{% endfor %}

未满足的标准:
{% for c in result.unmet_criteria %}
- {{ c.criterion_id }}: {{ c.reason }}
{% endfor %}

{% endfor %}

## 鉴别诊断要求

请综合考虑以下因素做出最终诊断：
1. 哪些障碍达到了诊断阈值？
2. 是否存在共病？（多个障碍同时达到阈值）
3. 如果多个障碍接近阈值，哪个证据最充分？
4. 排除原则：某些障碍互斥（如双相障碍排除单相抑郁）

以JSON格式输出：
{
  "primary_diagnosis": "ICD-10编码（如F32）",
  "comorbid_diagnoses": ["其他达到阈值的共病编码"],
  "confidence": 0.0到1.0,
  "reasoning": "鉴别诊断理由，说明为何选择主诊断及排除其他",
  "decision": "diagnosis或abstain"
}

如果证据不足以做出任何诊断，请将decision设为"abstain"。
```

Create `prompts/agents/differential_en.jinja`:
```
You are a psychiatric differential diagnosis expert. Based on the criterion evaluation results below, make the final differential diagnosis.

## Candidate Disorder Evaluation Results

{% for result in checker_results %}
### {{ result.disorder_code }} {{ result.disorder_name }}
Criteria met: {{ result.met_count }} / Required: {{ result.required }}
Threshold met: {{ "Yes" if result.threshold_met else "No" }}

Met criteria:
{% for c in result.met_criteria %}
- {{ c.criterion_id }}: {{ c.evidence_summary }} (confidence: {{ "%.2f"|format(c.confidence) }})
{% endfor %}

Unmet criteria:
{% for c in result.unmet_criteria %}
- {{ c.criterion_id }}: {{ c.reason }}
{% endfor %}

{% endfor %}

## Differential Diagnosis Requirements

Make your final diagnosis considering:
1. Which disorders meet diagnostic threshold?
2. Is there comorbidity? (multiple disorders meeting threshold)
3. If multiple disorders are near threshold, which has strongest evidence?
4. Exclusion rules: some disorders are mutually exclusive (e.g., bipolar excludes unipolar depression)

Respond in JSON format:
{
  "primary_diagnosis": "ICD-10 code (e.g., F32)",
  "comorbid_diagnoses": ["other comorbid codes meeting threshold"],
  "confidence": 0.0 to 1.0,
  "reasoning": "differential diagnosis reasoning",
  "decision": "diagnosis or abstain"
}

If evidence is insufficient for any diagnosis, set decision to "abstain".
```

- [ ] **Step 2: Commit**

```bash
git add prompts/agents/differential_zh.jinja prompts/agents/differential_en.jinja
git commit -m "feat: differential diagnosis agent bilingual prompts"
```

### Task 4: DifferentialDiagnosisAgent Implementation

**Files:**
- Create: `src/culturedx/agents/differential.py`
- Test: `tests/test_differential.py`

- [ ] **Step 1: Write tests**

Create `tests/test_differential.py`:

```python
# tests/test_differential.py
"""Tests for DifferentialDiagnosisAgent."""
import json
import pytest
from unittest.mock import MagicMock
from jinja2 import DictLoader, Environment

from culturedx.agents.differential import DifferentialDiagnosisAgent
from culturedx.core.models import CheckerOutput, CriterionResult, DiagnosisResult


@pytest.fixture
def mock_llm():
    client = MagicMock()
    client.model = "test-model"
    client.compute_prompt_hash.return_value = "hash456"
    return client


@pytest.fixture
def checker_outputs():
    """Two disorders: F32 meets threshold, F41.1 does not."""
    return [
        CheckerOutput(
            disorder="F32",
            criteria=[
                CriterionResult(criterion_id="B1", status="met", evidence="低落情绪", confidence=0.9),
                CriterionResult(criterion_id="B2", status="met", evidence="兴趣减退", confidence=0.8),
                CriterionResult(criterion_id="C6", status="met", evidence="失眠", confidence=0.7),
                CriterionResult(criterion_id="C1", status="met", evidence="注意力差", confidence=0.6),
                CriterionResult(criterion_id="A", status="not_met", evidence=None, confidence=0.3),
            ],
            criteria_met_count=4,
            criteria_required=4,
        ),
        CheckerOutput(
            disorder="F41.1",
            criteria=[
                CriterionResult(criterion_id="A", status="met", evidence="紧张", confidence=0.5),
                CriterionResult(criterion_id="B1", status="not_met", evidence=None, confidence=0.2),
            ],
            criteria_met_count=1,
            criteria_required=4,
        ),
    ]


class TestDifferentialDiagnosisAgent:
    def test_diagnose_returns_result(self, mock_llm, checker_outputs):
        mock_llm.generate.return_value = json.dumps({
            "primary_diagnosis": "F32",
            "comorbid_diagnoses": [],
            "confidence": 0.85,
            "reasoning": "F32 meets threshold with 4 criteria met",
            "decision": "diagnosis",
        })
        agent = DifferentialDiagnosisAgent(llm_client=mock_llm, prompts_dir="/tmp")
        agent._env = Environment(loader=DictLoader({
            "differential_zh.jinja": "{{ checker_results }}",
            "differential_en.jinja": "{{ checker_results }}",
        }))
        result = agent.diagnose(
            case_id="test_001",
            checker_outputs=checker_outputs,
            language="zh",
        )
        assert isinstance(result, DiagnosisResult)
        assert result.primary_diagnosis == "F32"
        assert result.confidence == 0.85
        assert result.decision == "diagnosis"
        assert result.mode == "mas"
        assert result.criteria_results == checker_outputs

    def test_diagnose_with_comorbid(self, mock_llm, checker_outputs):
        mock_llm.generate.return_value = json.dumps({
            "primary_diagnosis": "F32",
            "comorbid_diagnoses": ["F41.1"],
            "confidence": 0.75,
            "reasoning": "Both meet threshold",
            "decision": "diagnosis",
        })
        agent = DifferentialDiagnosisAgent(llm_client=mock_llm, prompts_dir="/tmp")
        agent._env = Environment(loader=DictLoader({
            "differential_zh.jinja": "test",
        }))
        result = agent.diagnose("test_001", checker_outputs, language="zh")
        assert result.comorbid_diagnoses == ["F41.1"]

    def test_diagnose_abstain(self, mock_llm, checker_outputs):
        mock_llm.generate.return_value = json.dumps({
            "primary_diagnosis": None,
            "comorbid_diagnoses": [],
            "confidence": 0.2,
            "reasoning": "Insufficient evidence",
            "decision": "abstain",
        })
        agent = DifferentialDiagnosisAgent(llm_client=mock_llm, prompts_dir="/tmp")
        agent._env = Environment(loader=DictLoader({
            "differential_zh.jinja": "test",
        }))
        result = agent.diagnose("test_001", checker_outputs, language="zh")
        assert result.decision == "abstain"
        assert result.primary_diagnosis is None

    def test_parse_failure_returns_abstain(self, mock_llm, checker_outputs):
        mock_llm.generate.return_value = "I cannot diagnose."
        agent = DifferentialDiagnosisAgent(llm_client=mock_llm, prompts_dir="/tmp")
        agent._env = Environment(loader=DictLoader({
            "differential_zh.jinja": "test",
        }))
        result = agent.diagnose("test_001", checker_outputs, language="zh")
        assert result.decision == "abstain"

    def test_unsupported_language(self, mock_llm, checker_outputs):
        agent = DifferentialDiagnosisAgent(llm_client=mock_llm, prompts_dir="/tmp")
        agent._env = Environment(loader=DictLoader({}))
        result = agent.diagnose("test_001", checker_outputs, language="ko")
        assert result.decision == "abstain"
```

- [ ] **Step 2: Implement DifferentialDiagnosisAgent**

Create `src/culturedx/agents/differential.py`:

```python
# src/culturedx/agents/differential.py
"""Differential diagnosis agent: cross-disorder synthesis for final diagnosis."""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.core.models import CheckerOutput, DiagnosisResult
from culturedx.llm.json_utils import extract_json_from_response
from culturedx.ontology.icd10 import get_disorder_name

logger = logging.getLogger(__name__)


class DifferentialDiagnosisAgent:
    """Synthesize checker outputs into a final differential diagnosis."""

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/agents",
    ) -> None:
        self.llm = llm_client
        self._env = Environment(
            loader=FileSystemLoader(str(prompts_dir)),
            keep_trailing_newline=True,
        )

    def diagnose(
        self,
        case_id: str,
        checker_outputs: list[CheckerOutput],
        language: str = "zh",
    ) -> DiagnosisResult:
        """Make differential diagnosis from checker outputs.

        Args:
            case_id: Case identifier.
            checker_outputs: Results from CriterionCheckerAgent per disorder.
            language: Language code ("zh" or "en").

        Returns:
            DiagnosisResult with final diagnosis and reasoning.
        """
        if language not in ("zh", "en"):
            logger.warning("Unsupported language '%s' for differential", language)
            return self._abstain(case_id, checker_outputs, language)

        # Build checker results context for the prompt
        checker_context = self._build_checker_context(checker_outputs, language)

        template_name = f"differential_{language}.jinja"
        template = self._env.get_template(template_name)
        prompt = template.render(checker_results=checker_context)

        source, _, _ = self._env.loader.get_source(self._env, template_name)
        prompt_hash = self.llm.compute_prompt_hash(source)

        raw = self.llm.generate(prompt, prompt_hash=prompt_hash, language=language)
        parsed = extract_json_from_response(raw)

        if parsed is None or not isinstance(parsed, dict):
            logger.warning("Differential parse failed for case %s", case_id)
            return self._abstain(case_id, checker_outputs, language)

        return self._parse_result(case_id, parsed, checker_outputs, prompt_hash, language)

    def _build_checker_context(
        self, checker_outputs: list[CheckerOutput], language: str
    ) -> list[dict]:
        """Build structured context for the differential prompt."""
        results = []
        for co in checker_outputs:
            disorder_name = get_disorder_name(co.disorder, language) or co.disorder
            met = [c for c in co.criteria if c.status == "met"]
            unmet = [c for c in co.criteria if c.status != "met"]

            results.append({
                "disorder_code": co.disorder,
                "disorder_name": disorder_name,
                "met_count": co.criteria_met_count,
                "required": co.criteria_required,
                "threshold_met": co.criteria_met_count >= co.criteria_required > 0,
                "met_criteria": [
                    {
                        "criterion_id": c.criterion_id,
                        "evidence_summary": c.evidence or "",
                        "confidence": c.confidence,
                    }
                    for c in met
                ],
                "unmet_criteria": [
                    {
                        "criterion_id": c.criterion_id,
                        "reason": c.evidence or "No supporting evidence",
                    }
                    for c in unmet
                ],
            })
        return results

    def _parse_result(
        self,
        case_id: str,
        parsed: dict,
        checker_outputs: list[CheckerOutput],
        prompt_hash: str,
        language: str,
    ) -> DiagnosisResult:
        """Parse LLM response into DiagnosisResult."""
        decision = parsed.get("decision", "diagnosis")
        if decision not in ("diagnosis", "abstain"):
            decision = "diagnosis"

        return DiagnosisResult(
            case_id=case_id,
            primary_diagnosis=parsed.get("primary_diagnosis"),
            comorbid_diagnoses=parsed.get("comorbid_diagnoses", []),
            confidence=float(parsed.get("confidence", 0.0)),
            decision=decision,
            criteria_results=checker_outputs,
            mode="mas",
            model_name=self.llm.model,
            prompt_hash=prompt_hash,
            language_used=language,
        )

    def _abstain(
        self, case_id: str, checker_outputs: list[CheckerOutput], language: str
    ) -> DiagnosisResult:
        """Return an abstain result."""
        return DiagnosisResult(
            case_id=case_id,
            primary_diagnosis=None,
            confidence=0.0,
            decision="abstain",
            criteria_results=checker_outputs,
            mode="mas",
            model_name=self.llm.model,
            prompt_hash="",
            language_used=language,
        )
```

- [ ] **Step 3: Run tests**

```bash
cd /home/user/YuNing/CultureDx && uv run pytest tests/test_differential.py -v 2>&1
```

- [ ] **Step 4: Commit**

```bash
git add src/culturedx/agents/differential.py tests/test_differential.py
git commit -m "feat: DifferentialDiagnosisAgent with cross-disorder synthesis"
```

---

## Chunk 2: MAS Orchestrator

### Task 5: MASMode Orchestrator

**Files:**
- Create: `src/culturedx/modes/mas.py`
- Test: `tests/test_mas_mode.py`

- [ ] **Step 1: Write tests**

Create `tests/test_mas_mode.py`:

```python
# tests/test_mas_mode.py
"""Tests for MASMode orchestrator."""
import json
import pytest
from unittest.mock import MagicMock, patch
from jinja2 import DictLoader, Environment

from culturedx.modes.mas import MASMode
from culturedx.core.models import (
    ClinicalCase,
    Turn,
    EvidenceBrief,
    DisorderEvidence,
    CriterionEvidence,
    SymptomSpan,
    DiagnosisResult,
)


@pytest.fixture
def mock_llm():
    client = MagicMock()
    client.model = "test-model"
    client.compute_prompt_hash.return_value = "hashmas"
    return client


@pytest.fixture
def sample_case_zh():
    return ClinicalCase(
        case_id="mas_test_001",
        transcript=[
            Turn(speaker="doctor", text="你好，最近怎么样？", turn_id=0),
            Turn(speaker="patient", text="情绪低落，失眠", turn_id=1),
        ],
        language="zh",
        dataset="test",
        diagnoses=["F32"],
    )


@pytest.fixture
def sample_evidence():
    return EvidenceBrief(
        case_id="mas_test_001",
        language="zh",
        disorder_evidence=[
            DisorderEvidence(
                disorder_code="F32",
                disorder_name="抑郁发作",
                criteria_evidence=[
                    CriterionEvidence(
                        criterion_id="F32.B1",
                        spans=[SymptomSpan(text="情绪低落", turn_id=1, symptom_type="emotional")],
                        confidence=0.85,
                    ),
                ],
            ),
            DisorderEvidence(
                disorder_code="F41.1",
                disorder_name="广泛性焦虑障碍",
                criteria_evidence=[],
            ),
        ],
    )


class TestMASMode:
    def test_diagnose_end_to_end(self, mock_llm, sample_case_zh, sample_evidence):
        """Full pipeline: evidence -> check -> differential -> result."""
        # First call: checker for F32
        # Second call: checker for F41.1
        # Third call: differential
        mock_llm.generate.side_effect = [
            json.dumps({
                "criteria": [
                    {"criterion_id": "B1", "status": "met", "evidence_summary": "低落", "confidence": 0.9},
                ],
                "criteria_met_count": 1,
                "threshold_met": False,
                "reasoning": "only 1 met",
            }),
            json.dumps({
                "criteria": [],
                "criteria_met_count": 0,
                "threshold_met": False,
                "reasoning": "no evidence",
            }),
            json.dumps({
                "primary_diagnosis": "F32",
                "comorbid_diagnoses": [],
                "confidence": 0.7,
                "reasoning": "Best match despite subthreshold",
                "decision": "diagnosis",
            }),
        ]
        mode = MASMode(llm_client=mock_llm, prompts_dir="/tmp")
        # Override environments for testing
        mock_env = Environment(loader=DictLoader({
            "criterion_checker_zh.jinja": "check {{ disorder_code }}",
            "criterion_checker_en.jinja": "check {{ disorder_code }}",
            "differential_zh.jinja": "diff {{ checker_results }}",
            "differential_en.jinja": "diff {{ checker_results }}",
        }))
        mode._checker._env = mock_env
        mode._differential._env = mock_env

        result = mode.diagnose(sample_case_zh, evidence=sample_evidence)
        assert isinstance(result, DiagnosisResult)
        assert result.primary_diagnosis == "F32"
        assert result.mode == "mas"
        assert result.case_id == "mas_test_001"
        assert len(result.criteria_results) == 2  # checked 2 disorders

    def test_diagnose_without_evidence(self, mock_llm, sample_case_zh):
        """Without evidence, uses default target disorders."""
        mock_llm.generate.side_effect = [
            json.dumps({
                "criteria": [], "criteria_met_count": 0,
                "threshold_met": False, "reasoning": "none",
            }),
            json.dumps({
                "criteria": [], "criteria_met_count": 0,
                "threshold_met": False, "reasoning": "none",
            }),
            json.dumps({
                "primary_diagnosis": None,
                "comorbid_diagnoses": [],
                "confidence": 0.1,
                "reasoning": "No evidence",
                "decision": "abstain",
            }),
        ]
        mode = MASMode(
            llm_client=mock_llm,
            prompts_dir="/tmp",
            target_disorders=["F32", "F41.1"],
        )
        mock_env = Environment(loader=DictLoader({
            "criterion_checker_zh.jinja": "check",
            "differential_zh.jinja": "diff",
        }))
        mode._checker._env = mock_env
        mode._differential._env = mock_env

        result = mode.diagnose(sample_case_zh, evidence=None)
        assert result.decision == "abstain"
        assert mock_llm.generate.call_count == 3  # 2 checkers + 1 differential

    def test_uses_evidence_disorders(self, mock_llm, sample_case_zh, sample_evidence):
        """MASMode should check disorders from evidence brief, not defaults."""
        mock_llm.generate.side_effect = [
            json.dumps({"criteria": [], "criteria_met_count": 0, "threshold_met": False, "reasoning": ""}),
            json.dumps({"criteria": [], "criteria_met_count": 0, "threshold_met": False, "reasoning": ""}),
            json.dumps({"primary_diagnosis": None, "comorbid_diagnoses": [], "confidence": 0.1, "reasoning": "", "decision": "abstain"}),
        ]
        mode = MASMode(llm_client=mock_llm, prompts_dir="/tmp")
        mock_env = Environment(loader=DictLoader({
            "criterion_checker_zh.jinja": "check",
            "differential_zh.jinja": "diff",
        }))
        mode._checker._env = mock_env
        mode._differential._env = mock_env

        result = mode.diagnose(sample_case_zh, evidence=sample_evidence)
        # Should have checked F32 and F41.1 from evidence
        assert len(result.criteria_results) == 2
```

- [ ] **Step 2: Implement MASMode**

Create `src/culturedx/modes/mas.py`:

```python
# src/culturedx/modes/mas.py
"""Multi-Agent System mode orchestrator."""
from __future__ import annotations

import logging
from pathlib import Path

from culturedx.agents.criterion_checker import CriterionCheckerAgent
from culturedx.agents.differential import DifferentialDiagnosisAgent
from culturedx.core.models import (
    ClinicalCase,
    DiagnosisResult,
    DisorderEvidence,
    EvidenceBrief,
)
from culturedx.modes.base import BaseModeOrchestrator

logger = logging.getLogger(__name__)


class MASMode(BaseModeOrchestrator):
    """Multi-Agent System orchestrator: criterion checking + differential diagnosis.

    Pipeline:
    1. Identify candidate disorders (from evidence or defaults)
    2. CriterionCheckerAgent evaluates each disorder's criteria
    3. DifferentialDiagnosisAgent synthesizes for final diagnosis
    """

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/agents",
        target_disorders: list[str] | None = None,
    ) -> None:
        self.llm = llm_client
        self.target_disorders = target_disorders or ["F32", "F41.1"]
        self._checker = CriterionCheckerAgent(
            llm_client=llm_client, prompts_dir=prompts_dir
        )
        self._differential = DifferentialDiagnosisAgent(
            llm_client=llm_client, prompts_dir=prompts_dir
        )

    def diagnose(
        self, case: ClinicalCase, evidence: EvidenceBrief | None = None
    ) -> DiagnosisResult:
        """Run the full MAS diagnostic pipeline."""
        # 1. Determine candidate disorders
        disorders_to_check = self._get_candidate_disorders(evidence)
        logger.info(
            "MAS checking %d disorders for case %s: %s",
            len(disorders_to_check), case.case_id, disorders_to_check,
        )

        # 2. Build evidence map for quick lookup
        evidence_map = self._build_evidence_map(evidence)

        # 3. Run CriterionCheckerAgent per disorder
        checker_outputs = []
        for disorder_code in disorders_to_check:
            disorder_evidence = evidence_map.get(
                disorder_code,
                DisorderEvidence(
                    disorder_code=disorder_code,
                    disorder_name=disorder_code,
                ),
            )
            output = self._checker.check(
                disorder_code=disorder_code,
                disorder_evidence=disorder_evidence,
                language=case.language,
            )
            checker_outputs.append(output)
            logger.info(
                "  %s: %d/%d criteria met",
                disorder_code, output.criteria_met_count, output.criteria_required,
            )

        # 4. DifferentialDiagnosisAgent for final verdict
        result = self._differential.diagnose(
            case_id=case.case_id,
            checker_outputs=checker_outputs,
            language=case.language,
        )
        return result

    def _get_candidate_disorders(
        self, evidence: EvidenceBrief | None
    ) -> list[str]:
        """Get disorders to check from evidence or defaults."""
        if evidence and evidence.disorder_evidence:
            return [de.disorder_code for de in evidence.disorder_evidence]
        return list(self.target_disorders)

    @staticmethod
    def _build_evidence_map(
        evidence: EvidenceBrief | None,
    ) -> dict[str, DisorderEvidence]:
        """Build disorder_code -> DisorderEvidence lookup."""
        if not evidence or not evidence.disorder_evidence:
            return {}
        return {de.disorder_code: de for de in evidence.disorder_evidence}
```

- [ ] **Step 3: Run tests**

```bash
cd /home/user/YuNing/CultureDx && uv run pytest tests/test_mas_mode.py -v 2>&1
```

- [ ] **Step 4: Commit**

```bash
git add src/culturedx/modes/mas.py tests/test_mas_mode.py
git commit -m "feat: MASMode orchestrator with checker + differential pipeline"
```

### Task 6: MAS Config and CLI Integration

**Files:**
- Create: `configs/mas.yaml`
- Modify: `src/culturedx/core/config.py`
- Modify: `src/culturedx/pipeline/cli.py`

- [ ] **Step 1: Create MAS config overlay**

Create `configs/mas.yaml`:
```yaml
mode:
  name: mas
  type: mas

evidence:
  enabled: true
  retriever:
    name: mock
  somatization:
    enabled: true
    llm_fallback: true
  min_confidence: 0.1
```

- [ ] **Step 2: Add MAS target_disorders to ModeConfig**

Modify `src/culturedx/core/config.py` — add `target_disorders` to `ModeConfig`:

Replace:
```python
class ModeConfig(BaseModel):
    name: str = "single"
    type: str = "single"
    variants: list[str] | None = None
```

With:
```python
class ModeConfig(BaseModel):
    name: str = "single"
    type: str = "single"
    variants: list[str] | None = None
    target_disorders: list[str] | None = None
```

- [ ] **Step 3: Update CLI to support MAS mode**

Modify `src/culturedx/pipeline/cli.py` — update the `run` command to print MAS info:

Replace:
```python
    if with_evidence:
        click.echo("Evidence extraction: ENABLED")
    click.echo(f"Running CultureDx mode={cfg.mode.type} on dataset={dataset}")
```

With:
```python
    if with_evidence:
        click.echo("Evidence extraction: ENABLED")
    if cfg.mode.type == "mas":
        disorders = cfg.mode.target_disorders or ["F32", "F41.1"]
        click.echo(f"MAS mode: checking {len(disorders)} disorders")
    click.echo(f"Running CultureDx mode={cfg.mode.type} on dataset={dataset}")
```

- [ ] **Step 4: Run full test suite**

```bash
cd /home/user/YuNing/CultureDx && uv run pytest -q 2>&1
```

- [ ] **Step 5: Commit**

```bash
git add configs/mas.yaml src/culturedx/core/config.py src/culturedx/pipeline/cli.py
git commit -m "feat: MAS config, target_disorders, and CLI integration"
```

### Task 7: Update CLAUDE.md and agents __init__

**Files:**
- Modify: `CLAUDE.md`
- Modify: `src/culturedx/agents/__init__.py`

- [ ] **Step 1: Update agents __init__.py**

Write `src/culturedx/agents/__init__.py`:
```python
"""CultureDx diagnostic agents."""
```

- [ ] **Step 2: Update CLAUDE.md**

Add to the Package Architecture table (after `modes/single.py`):
```
| agents/criterion_checker.py | CriterionCheckerAgent: per-disorder ICD-10 criteria evaluation |
| agents/differential.py | DifferentialDiagnosisAgent: cross-disorder differential synthesis |
| modes/mas.py | MASMode: 2-agent orchestrator (checker → differential) |
| data/adapters/lingxidiag16k.py | LingxiDiag-16K adapter (14K Chinese dialogues) |
| data/adapters/mdd5k.py | MDD5kAdapter + MDD5kRawAdapter (925 patients) |
```

Add to Key Invariants:
```
10. MAS pipeline: per-disorder criterion check → differential synthesis → DiagnosisResult
11. CriterionCheckerAgent uses ICD-10 thresholds (min_core, min_total, duration)
12. Adapters registered in data/adapters/__init__.py, accessible via get_adapter()
```

- [ ] **Step 3: Run full test suite**

```bash
cd /home/user/YuNing/CultureDx && uv run pytest -q 2>&1
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md src/culturedx/agents/__init__.py
git commit -m "docs: update CLAUDE.md with Phase 3 MAS agents and dataset adapters"
```
