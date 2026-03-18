# CultureDx Phase 1: Foundation — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the project skeleton with core data models, config system, LLM client, three dataset adapters (MDD-5k, PDCH, E-DAIC), basic evaluation metrics, single-model baseline mode, and CLI — producing a working end-to-end smoke test.

**Architecture:** Pydantic config models loaded from layered YAML (OmegaConf). Dataset adapters normalize heterogeneous sources to a unified `ClinicalCase` dataclass. Single-model mode sends transcript + optional evidence to Ollama, parses structured JSON, produces `DiagnosisResult`. Metrics compute accuracy, F1, MAE for evaluation.

**Tech Stack:** Python 3.11+, uv, Pydantic v2, OmegaConf, Jinja2, httpx (Ollama), SQLite (cache), DuckDB (analytics), pytest, click

**Spec:** `docs/superpowers/specs/2026-03-18-culturedx-design.md`

---

## File Map

### New Files (Phase 1)

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package definition, dependencies, test config |
| `CLAUDE.md` | Project guidance for Claude Code |
| `.gitignore` | Ignore data/raw, outputs, cache, __pycache__ |
| `configs/base.yaml` | Global defaults (seeds, timeouts, output paths) |
| `configs/paths.yaml` | Local data/cache/output roots |
| `configs/datasets/mdd5k.yaml` | MDD-5k adapter config |
| `configs/datasets/pdch.yaml` | PDCH adapter config |
| `configs/datasets/edaic.yaml` | E-DAIC adapter config |
| `configs/datasets/label_mapping.yaml` | MDD-5k → 12-category mapping (deferred to Phase 3) |
| `configs/modes/single.yaml` | Single-model baseline config |
| `configs/model_pools/default.yaml` | Default model pool definitions |
| `src/culturedx/__init__.py` | Package init with version |
| `src/culturedx/core/__init__.py` | Core subpackage |
| `src/culturedx/core/models.py` | Turn, ClinicalCase, EvidenceBrief, CriterionResult, DiagnosisResult |
| `src/culturedx/core/config.py` | Pydantic config models for all YAML fields |
| `src/culturedx/core/registry.py` | Model pool registry |
| `src/culturedx/data/__init__.py` | Data subpackage |
| `src/culturedx/data/adapters/__init__.py` | Adapter subpackage |
| `src/culturedx/data/adapters/base.py` | BaseDatasetAdapter ABC |
| `src/culturedx/data/adapters/mdd5k.py` | MDD-5k → ClinicalCase |
| `src/culturedx/data/adapters/pdch.py` | PDCH → ClinicalCase |
| `src/culturedx/data/adapters/edaic.py` | E-DAIC → ClinicalCase |
| `src/culturedx/data/splits.py` | Train/val/test split management |
| `src/culturedx/llm/__init__.py` | LLM subpackage |
| `src/culturedx/llm/client.py` | OllamaClient with httpx |
| `src/culturedx/llm/cache.py` | SQLite-backed response cache |
| `src/culturedx/llm/json_utils.py` | Extract JSON from LLM responses |
| `src/culturedx/agents/__init__.py` | Agents subpackage |
| `src/culturedx/agents/base.py` | BaseAgent ABC |
| `src/culturedx/modes/__init__.py` | Modes subpackage |
| `src/culturedx/modes/base.py` | BaseModeOrchestrator ABC |
| `src/culturedx/modes/single.py` | Single-model baseline mode |
| `src/culturedx/eval/__init__.py` | Eval subpackage |
| `src/culturedx/eval/metrics.py` | Accuracy, F1, MAE, Pearson r, AURC |
| `src/culturedx/pipeline/__init__.py` | Pipeline subpackage |
| `src/culturedx/pipeline/runner.py` | ExperimentRunner |
| `src/culturedx/pipeline/cli.py` | Click CLI entry point |
| `prompts/single/zero_shot_zh.jinja` | Chinese zero-shot diagnosis prompt |
| `prompts/single/zero_shot_en.jinja` | English zero-shot diagnosis prompt |
| `prompts/CHANGELOG.md` | Prompt version tracking |
| `tests/__init__.py` | Test package |
| `tests/conftest.py` | Shared fixtures |
| `tests/fixtures/mdd5k_sample.json` | 3 synthetic MDD-5k cases |
| `tests/fixtures/pdch_sample.json` | 2 synthetic PDCH cases |
| `tests/fixtures/edaic_sample.json` | 2 synthetic E-DAIC cases |
| `tests/test_models.py` | Core data model tests |
| `tests/test_config.py` | Config loading tests |
| `tests/test_adapters.py` | Dataset adapter tests |
| `tests/test_json_utils.py` | JSON extraction tests |
| `tests/test_cache.py` | LLM cache tests |
| `tests/test_metrics.py` | Metrics computation tests |
| `tests/test_single_mode.py` | Single-model mode tests |
| `tests/test_cli.py` | CLI smoke test |

---

## Chunk 1: Project Scaffold & Core Models

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/culturedx/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "culturedx"
version = "0.1.0"
description = "Culture-Adaptive Diagnostic MAS with Evidence Grounding"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0",
    "omegaconf>=2.3",
    "httpx>=0.27",
    "jinja2>=3.1",
    "click>=8.1",
    "duckdb>=1.0",
    "numpy>=1.26",
    "scipy>=1.12",
    "scikit-learn>=1.4",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
]

[project.scripts]
culturedx = "culturedx.pipeline.cli:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/culturedx"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
markers = [
    "integration: marks tests requiring Ollama",
    "slow: marks slow tests",
]
```

- [ ] **Step 2: Create .gitignore**

```
__pycache__/
*.pyc
*.egg-info/
dist/
.venv/
data/raw/
data/cache/
outputs/
*.db
*.sqlite
.env
```

- [ ] **Step 3: Create src/culturedx/__init__.py**

```python
"""CultureDx: Culture-Adaptive Diagnostic MAS with Evidence Grounding."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Create all __init__.py files for subpackages**

Create empty `__init__.py` in: `src/culturedx/core/`, `src/culturedx/data/`, `src/culturedx/data/adapters/`, `src/culturedx/llm/`, `src/culturedx/agents/`, `src/culturedx/modes/`, `src/culturedx/eval/`, `src/culturedx/pipeline/`, `tests/`

Also create `src/culturedx/core/registry.py` stub:
```python
"""Model pool registry (Phase 2+)."""
```

- [ ] **Step 5: Initialize uv and verify**

Run: `cd /home/user/YuNing/CultureDx && uv sync`
Expected: Dependencies installed, `.venv` created

- [ ] **Step 5b: Create README.md**

```markdown
# CultureDx

Culture-Adaptive Diagnostic MAS with Evidence Grounding.
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore README.md src/ tests/__init__.py
git commit -m "feat: project scaffold with pyproject.toml and package structure"
```

---

### Task 2: Core data models

**Files:**
- Create: `src/culturedx/core/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for core models**

```python
# tests/test_models.py
"""Tests for core data models."""
import pytest
from culturedx.core.models import (
    Turn,
    ClinicalCase,
    SymptomSpan,
    CriterionEvidence,
    EvidenceBrief,
    CriterionResult,
    CheckerOutput,
    DiagnosisResult,
)


class TestTurn:
    def test_create_turn(self):
        t = Turn(speaker="doctor", text="How are you feeling?", turn_id=0)
        assert t.speaker == "doctor"
        assert t.turn_id == 0

    def test_turn_is_patient(self):
        t = Turn(speaker="patient", text="I feel sad", turn_id=1)
        assert t.is_patient is True
        t2 = Turn(speaker="doctor", text="Tell me more", turn_id=2)
        assert t2.is_patient is False


class TestClinicalCase:
    def test_create_clinical_case(self):
        turns = [
            Turn(speaker="doctor", text="How are you?", turn_id=0),
            Turn(speaker="patient", text="Not good", turn_id=1),
        ]
        case = ClinicalCase(
            case_id="test_001",
            transcript=turns,
            language="zh",
            dataset="mdd5k",
            transcript_format="dialogue",
            coding_system="icd10",
            diagnoses=["F32"],
            severity=None,
            comorbid=False,
            suicide_risk=None,
            metadata=None,
        )
        assert case.case_id == "test_001"
        assert case.language == "zh"
        assert len(case.transcript) == 2

    def test_patient_turns_only(self):
        turns = [
            Turn(speaker="doctor", text="Q1", turn_id=0),
            Turn(speaker="patient", text="A1", turn_id=1),
            Turn(speaker="doctor", text="Q2", turn_id=2),
            Turn(speaker="patient", text="A2", turn_id=3),
        ]
        case = ClinicalCase(
            case_id="t",
            transcript=turns,
            language="zh",
            dataset="mdd5k",
            transcript_format="dialogue",
            coding_system="icd10",
            diagnoses=["F32"],
        )
        patient_turns = case.patient_turns()
        assert len(patient_turns) == 2
        assert all(t.is_patient for t in patient_turns)

    def test_is_comorbid(self):
        case = ClinicalCase(
            case_id="t",
            transcript=[],
            language="zh",
            dataset="mdd5k",
            transcript_format="dialogue",
            coding_system="icd10",
            diagnoses=["F32", "F41.1"],
            comorbid=True,
        )
        assert case.comorbid is True
        assert len(case.diagnoses) == 2


class TestEvidenceBrief:
    def test_create_evidence_brief(self):
        evidence = CriterionEvidence(
            criterion_id="F32.A1",
            spans=[
                SymptomSpan(text="I feel sad", turn_id=1, symptom_type="mood"),
            ],
            confidence=0.85,
        )
        brief = EvidenceBrief(
            case_id="test_001",
            language="zh",
            criteria_evidence=[evidence],
        )
        assert len(brief.criteria_evidence) == 1
        assert brief.criteria_evidence[0].confidence == 0.85

    def test_empty_brief(self):
        brief = EvidenceBrief(case_id="t", language="en", criteria_evidence=[])
        assert len(brief.criteria_evidence) == 0


class TestDiagnosisResult:
    def test_diagnosis_with_confidence(self):
        result = DiagnosisResult(
            case_id="test_001",
            primary_diagnosis="F32",
            comorbid_diagnoses=["F41.1"],
            confidence=0.82,
            decision="diagnosis",
            criteria_results=[],
            mode="hied",
            model_name="qwen3:14b",
            language_used="zh",
        )
        assert result.decision == "diagnosis"
        assert result.language_used == "zh"
        assert result.confidence == 0.82
        assert result.comorbid_diagnoses == ["F41.1"]

    def test_abstain_result(self):
        result = DiagnosisResult(
            case_id="t",
            primary_diagnosis=None,
            comorbid_diagnoses=[],
            confidence=0.15,
            decision="abstain",
            criteria_results=[],
            mode="single",
            model_name="qwen3:14b",
        )
        assert result.decision == "abstain"
        assert result.primary_diagnosis is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/YuNing/CultureDx && uv run pytest tests/test_models.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement core models**

```python
# src/culturedx/core/models.py
"""Core data models for CultureDx."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Turn:
    """A single dialogue turn in a clinical transcript."""

    speaker: str
    text: str
    turn_id: int

    @property
    def is_patient(self) -> bool:
        return self.speaker.lower() in ("patient", "participant", "p")


@dataclass
class ClinicalCase:
    """A normalized clinical case from any dataset."""

    case_id: str
    transcript: list[Turn]
    language: str  # "zh" | "en"
    dataset: str
    transcript_format: str = "dialogue"  # "dialogue" | "monologue" | "clinical_structured"
    coding_system: str = "icd10"  # "icd10" | "icd11" | "dsm5" | "ccmd3"

    # Ground truth (evaluation only)
    diagnoses: list[str] = field(default_factory=list)
    severity: dict | None = None
    comorbid: bool = False
    suicide_risk: int | None = None
    metadata: dict | None = None

    def patient_turns(self) -> list[Turn]:
        """Return only patient/participant turns."""
        return [t for t in self.transcript if t.is_patient]


@dataclass
class SymptomSpan:
    """An extracted symptom mention from the transcript."""

    text: str
    turn_id: int
    symptom_type: str  # "mood", "somatic", "cognitive", etc.
    mapped_criterion: str | None = None  # Set by somatization mapper


@dataclass
class CriterionEvidence:
    """Evidence collected for a single diagnostic criterion."""

    criterion_id: str  # e.g. "F32.A1"
    spans: list[SymptomSpan] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class EvidenceBrief:
    """Assembled evidence brief for a case, per criterion per disorder."""

    case_id: str
    language: str
    criteria_evidence: list[CriterionEvidence] = field(default_factory=list)


@dataclass
class CriterionResult:
    """Result of checking a single criterion."""

    criterion_id: str
    status: Literal["met", "not_met", "insufficient_evidence"]
    evidence: str | None = None
    confidence: float = 0.0


@dataclass
class CheckerOutput:
    """Output from a criterion checker agent for one disorder."""

    disorder: str  # ICD-10 code e.g. "F32"
    criteria: list[CriterionResult] = field(default_factory=list)
    criteria_met_count: int = 0
    criteria_required: int = 0


@dataclass
class DiagnosisResult:
    """Final diagnosis output from any MAS mode."""

    case_id: str
    primary_diagnosis: str | None
    comorbid_diagnoses: list[str] = field(default_factory=list)
    confidence: float = 0.0
    decision: Literal["diagnosis", "abstain"] = "diagnosis"
    criteria_results: list[CheckerOutput] = field(default_factory=list)
    mode: str = ""  # "hied", "psycot", "specialist", "debate", "single"
    model_name: str = ""
    prompt_hash: str = ""  # SHA-256 of prompt template used
    language_used: str = ""  # "zh" or "en"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/YuNing/CultureDx && uv run pytest tests/test_models.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/user/YuNing/CultureDx
git add src/culturedx/core/models.py tests/test_models.py
git commit -m "feat: core data models (Turn, ClinicalCase, EvidenceBrief, DiagnosisResult)"
```

---

### Task 3: Config system

**Files:**
- Create: `src/culturedx/core/config.py`
- Create: `configs/base.yaml`
- Create: `configs/paths.yaml`
- Create: `configs/modes/single.yaml`
- Create: `configs/model_pools/default.yaml`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for config**

```python
# tests/test_config.py
"""Tests for config loading."""
import pytest
from pathlib import Path
from culturedx.core.config import (
    CultureDxConfig,
    DatasetConfig,
    ModeConfig,
    ModelPoolConfig,
    load_config,
)


CONFIGS_DIR = Path(__file__).parent.parent / "configs"


class TestConfigModels:
    def test_dataset_config(self):
        cfg = DatasetConfig(
            name="mdd5k",
            language="zh",
            coding_system="icd10",
            transcript_format="dialogue",
            data_path="data/raw/mdd5k",
            split_strategy="stratified",
        )
        assert cfg.language == "zh"

    def test_mode_config(self):
        cfg = ModeConfig(name="single", type="single")
        assert cfg.type == "single"

    def test_model_pool_config(self):
        cfg = ModelPoolConfig(
            name="qwen3-14b",
            provider="ollama",
            model_id="qwen3:14b",
            role="reasoner",
        )
        assert cfg.provider == "ollama"


class TestLoadConfig:
    def test_load_base_config(self):
        cfg = load_config(CONFIGS_DIR / "base.yaml")
        assert cfg.seed == 42
        assert cfg.output_dir is not None

    def test_load_with_mode_overlay(self):
        cfg = load_config(
            CONFIGS_DIR / "base.yaml",
            overrides=[CONFIGS_DIR / "modes" / "single.yaml"],
        )
        assert cfg.mode.type == "single"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/YuNing/CultureDx && uv run pytest tests/test_config.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Create config YAML files**

`configs/base.yaml`:
```yaml
seed: 42
output_dir: outputs/runs
cache_dir: data/cache
log_level: INFO
request_timeout_sec: 300

mode:
  name: single
  type: single

llm:
  provider: ollama
  base_url: http://localhost:11434
  temperature: 0.0
  top_k: 1
  max_retries: 3

eval:
  binary_threshold_phq8: 10
  binary_threshold_hamd17: 8
  bootstrap_resamples: 10000
```

`configs/paths.yaml`:
```yaml
data_dir: data
raw_dir: data/raw
processed_dir: data/processed
cache_dir: data/cache
output_dir: outputs
```

`configs/modes/single.yaml`:
```yaml
mode:
  name: single
  type: single
  variants:
    - zero_shot
    - zero_shot_evidence
    - few_shot
    - few_shot_evidence
```

`configs/model_pools/default.yaml`:
```yaml
pools:
  worker:
    - name: qwen3-4b
      provider: ollama
      model_id: "qwen3:4b"
      role: worker
  reasoner:
    - name: qwen3-14b
      provider: ollama
      model_id: "qwen3:14b"
      role: reasoner
  judge:
    - name: qwen3-32b
      provider: ollama
      model_id: "qwen3:32b"
      role: judge
```

- [ ] **Step 4: Implement config module**

```python
# src/culturedx/core/config.py
"""Pydantic configuration models with OmegaConf YAML loading."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from omegaconf import OmegaConf
from pydantic import BaseModel, ConfigDict


class LLMConfig(BaseModel):
    provider: str = "ollama"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.0
    top_k: int = 1
    max_retries: int = 3


class EvalConfig(BaseModel):
    binary_threshold_phq8: int = 10
    binary_threshold_hamd17: int = 8
    bootstrap_resamples: int = 10000


class ModeConfig(BaseModel):
    name: str = "single"
    type: str = "single"
    variants: list[str] | None = None


class DatasetConfig(BaseModel):
    name: str = ""
    language: str = "zh"
    coding_system: str = "icd10"
    transcript_format: str = "dialogue"
    data_path: str = ""
    split_strategy: str = "stratified"


class ModelPoolConfig(BaseModel):
    name: str = ""
    provider: str = "ollama"
    model_id: str = ""
    role: str = ""


class CultureDxConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    seed: int = 42
    output_dir: str = "outputs/runs"
    cache_dir: str = "data/cache"
    log_level: str = "INFO"
    request_timeout_sec: int = 300
    mode: ModeConfig = ModeConfig()
    llm: LLMConfig = LLMConfig()
    eval: EvalConfig = EvalConfig()
    dataset: DatasetConfig = DatasetConfig()


def load_config(
    base_path: str | Path,
    overrides: list[str | Path] | None = None,
) -> CultureDxConfig:
    """Load config from base YAML with optional overlay files."""
    base = OmegaConf.load(str(base_path))
    if overrides:
        for override_path in overrides:
            overlay = OmegaConf.load(str(override_path))
            base = OmegaConf.merge(base, overlay)
    plain = OmegaConf.to_container(base, resolve=True)
    return CultureDxConfig(**plain)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/user/YuNing/CultureDx && uv run pytest tests/test_config.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
cd /home/user/YuNing/CultureDx
git add src/culturedx/core/config.py configs/ tests/test_config.py
git commit -m "feat: config system with Pydantic models and OmegaConf YAML loading"
```

---

### Task 4: JSON utils

**Files:**
- Create: `src/culturedx/llm/json_utils.py`
- Create: `tests/test_json_utils.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_json_utils.py
"""Tests for JSON extraction from LLM responses."""
import pytest
from culturedx.llm.json_utils import extract_json_from_response


class TestExtractJson:
    def test_pure_json(self):
        text = '{"diagnosis": "F32", "confidence": 0.9}'
        result = extract_json_from_response(text)
        assert result["diagnosis"] == "F32"

    def test_json_in_markdown_block(self):
        text = 'Here is my analysis:\n```json\n{"diagnosis": "F32"}\n```\nDone.'
        result = extract_json_from_response(text)
        assert result["diagnosis"] == "F32"

    def test_json_embedded_in_text(self):
        text = 'The result is {"diagnosis": "F41.1", "score": 5} as shown.'
        result = extract_json_from_response(text)
        assert result["diagnosis"] == "F41.1"

    def test_no_json_returns_none(self):
        text = "I cannot provide a diagnosis."
        result = extract_json_from_response(text)
        assert result is None

    def test_malformed_json_returns_none(self):
        text = '{"diagnosis": "F32", confidence: 0.9}'
        result = extract_json_from_response(text)
        assert result is None

    def test_json_array(self):
        text = '[{"criterion": "A1", "status": "met"}]'
        result = extract_json_from_response(text)
        assert isinstance(result, list)
        assert result[0]["criterion"] == "A1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/YuNing/CultureDx && uv run pytest tests/test_json_utils.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement JSON utils**

```python
# src/culturedx/llm/json_utils.py
"""Extract structured JSON from LLM text responses."""
from __future__ import annotations

import json
import re


def extract_json_from_response(text: str) -> dict | list | None:
    """Extract the first valid JSON object or array from LLM output.

    Tries in order:
    1. Parse the entire text as JSON
    2. Extract from markdown code block
    3. Find first { } or [ ] balanced substring
    """
    text = text.strip()

    # Try full parse
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Try markdown code block
    md_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if md_match:
        try:
            return json.loads(md_match.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            pass

    # Try finding first balanced JSON
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == "\\":
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == start_char:
                depth += 1
            elif c == end_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except (json.JSONDecodeError, ValueError):
                        break
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/YuNing/CultureDx && uv run pytest tests/test_json_utils.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/user/YuNing/CultureDx
git add src/culturedx/llm/json_utils.py tests/test_json_utils.py
git commit -m "feat: JSON extraction utility for LLM responses"
```

---

### Task 5: LLM cache

**Files:**
- Create: `src/culturedx/llm/cache.py`
- Create: `tests/test_cache.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cache.py
"""Tests for SQLite LLM response cache."""
import pytest
from pathlib import Path
from culturedx.llm.cache import LLMCache


@pytest.fixture
def cache(tmp_path):
    with LLMCache(tmp_path / "test_cache.db") as c:
        yield c


class TestLLMCache:
    def test_get_miss(self, cache):
        result = cache.get("ollama", "model", "prompt_hash", "zh", "input")
        assert result is None

    def test_put_and_get(self, cache):
        cache.put("ollama", "model", "prompt_hash", "zh", "input", "output_text")
        result = cache.get("ollama", "model", "prompt_hash", "zh", "input")
        assert result == "output_text"

    def test_different_prompt_hash_miss(self, cache):
        cache.put("ollama", "model", "hash_a", "zh", "input", "output_a")
        result = cache.get("ollama", "model", "hash_b", "zh", "input")
        assert result is None

    def test_different_model_miss(self, cache):
        cache.put("ollama", "model_a", "hash", "zh", "input", "output_a")
        result = cache.get("ollama", "model_b", "hash", "zh", "input")
        assert result is None

    def test_different_language_miss(self, cache):
        cache.put("ollama", "model", "hash", "zh", "input", "output_zh")
        result = cache.get("ollama", "model", "hash", "en", "input")
        assert result is None

    def test_overwrite(self, cache):
        cache.put("ollama", "model", "hash", "zh", "input", "old")
        cache.put("ollama", "model", "hash", "zh", "input", "new")
        result = cache.get("ollama", "model", "hash", "zh", "input")
        assert result == "new"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/YuNing/CultureDx && uv run pytest tests/test_cache.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement LLM cache**

```python
# src/culturedx/llm/cache.py
"""SQLite-backed LLM response cache."""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path


class LLMCache:
    """Cache LLM responses keyed by (provider, model, prompt_hash, language, input_hash)."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache ("
            "  provider TEXT, model TEXT, prompt_hash TEXT, language TEXT,"
            "  input_hash TEXT, response TEXT,"
            "  PRIMARY KEY (provider, model, prompt_hash, language, input_hash)"
            ")"
        )
        self._conn.commit()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @staticmethod
    def _hash_input(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(
        self, provider: str, model: str, prompt_hash: str, language: str, input_text: str
    ) -> str | None:
        input_hash = self._hash_input(input_text)
        row = self._conn.execute(
            "SELECT response FROM cache "
            "WHERE provider=? AND model=? AND prompt_hash=? AND language=? AND input_hash=?",
            (provider, model, prompt_hash, language, input_hash),
        ).fetchone()
        return row[0] if row else None

    def put(
        self,
        provider: str,
        model: str,
        prompt_hash: str,
        language: str,
        input_text: str,
        response: str,
    ) -> None:
        input_hash = self._hash_input(input_text)
        self._conn.execute(
            "INSERT OR REPLACE INTO cache "
            "(provider, model, prompt_hash, language, input_hash, response) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (provider, model, prompt_hash, language, input_hash, response),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/user/YuNing/CultureDx && uv run pytest tests/test_cache.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/user/YuNing/CultureDx
git add src/culturedx/llm/cache.py tests/test_cache.py
git commit -m "feat: SQLite-backed LLM response cache"
```

---

## Chunk 2: LLM Client, Dataset Adapters & Test Fixtures

### Task 6: LLM client

**Files:**
- Create: `src/culturedx/llm/client.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write failing tests (in conftest + test file)**

```python
# tests/conftest.py
"""Shared test fixtures."""
import pytest
from pathlib import Path
from culturedx.core.models import Turn, ClinicalCase


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_case_zh():
    """A minimal Chinese clinical case for testing."""
    return ClinicalCase(
        case_id="test_zh_001",
        transcript=[
            Turn(speaker="doctor", text="你最近感觉怎么样?", turn_id=0),
            Turn(speaker="patient", text="我经常头疼，睡不着觉，心情很低落", turn_id=1),
            Turn(speaker="doctor", text="这种情况持续多久了?", turn_id=2),
            Turn(speaker="patient", text="大概两个多月了，每天都很难受", turn_id=3),
        ],
        language="zh",
        dataset="mdd5k",
        transcript_format="dialogue",
        coding_system="icd10",
        diagnoses=["F32"],
    )


@pytest.fixture
def sample_case_en():
    """A minimal English clinical case for testing."""
    return ClinicalCase(
        case_id="test_en_001",
        transcript=[
            Turn(speaker="interviewer", text="How have you been feeling?", turn_id=0),
            Turn(speaker="participant", text="Pretty bad, I can't sleep and I lost interest in everything", turn_id=1),
        ],
        language="en",
        dataset="edaic",
        transcript_format="dialogue",
        coding_system="dsm5",
        diagnoses=[],
        severity={"phq8_total": 16},
        metadata={"binary": 1},
    )


class MockLLMResponse:
    """Mock for httpx response."""

    def __init__(self, json_data):
        self._json = json_data
        self.status_code = 200

    def json(self):
        return self._json

    def raise_for_status(self):
        pass
```

- [ ] **Step 2: Write LLM client tests**

```python
# tests/test_llm_client.py
"""Tests for Ollama LLM client."""
import pytest
from unittest.mock import patch, MagicMock
from culturedx.llm.client import OllamaClient


class TestOllamaClient:
    def test_create_client(self):
        client = OllamaClient(
            base_url="http://localhost:11434",
            model="qwen3:14b",
            temperature=0.0,
        )
        assert client.model == "qwen3:14b"

    @patch("culturedx.llm.client.httpx.post")
    def test_generate(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": '{"diagnosis": "F32"}'}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        client = OllamaClient(
            base_url="http://localhost:11434",
            model="qwen3:14b",
        )
        result = client.generate("Diagnose this patient")
        assert "F32" in result
        mock_post.assert_called_once()

    def test_prompt_hash(self):
        client = OllamaClient(
            base_url="http://localhost:11434",
            model="qwen3:14b",
        )
        h1 = client.compute_prompt_hash("prompt_a")
        h2 = client.compute_prompt_hash("prompt_b")
        h3 = client.compute_prompt_hash("prompt_a")
        assert h1 != h2
        assert h1 == h3
```

- [ ] **Step 3: Implement LLM client**

```python
# src/culturedx/llm/client.py
"""Ollama LLM client with caching and prompt hashing."""
from __future__ import annotations

import hashlib
from pathlib import Path

import httpx

from culturedx.llm.cache import LLMCache


class OllamaClient:
    """Client for Ollama API with response caching."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen3:14b",
        temperature: float = 0.0,
        top_k: int = 1,
        timeout: int = 300,
        cache_path: str | Path | None = None,
        provider: str = "ollama",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.provider = provider
        self.temperature = temperature
        self.top_k = top_k
        self.timeout = timeout
        self._cache = LLMCache(cache_path) if cache_path else None

    @staticmethod
    def compute_prompt_hash(prompt_text: str) -> str:
        """SHA-256 hash of a prompt template for cache keying."""
        return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:16]

    def generate(
        self,
        prompt: str,
        prompt_hash: str = "",
        language: str = "zh",
    ) -> str:
        """Send prompt to Ollama and return response text."""
        if not prompt_hash:
            prompt_hash = self.compute_prompt_hash(prompt)

        # Check cache
        if self._cache:
            cached = self._cache.get(self.provider, self.model, prompt_hash, language, prompt)
            if cached is not None:
                return cached

        # Call Ollama
        response = httpx.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "top_k": self.top_k,
                },
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        text = response.json()["response"]

        # Store in cache
        if self._cache:
            self._cache.put(self.provider, self.model, prompt_hash, language, prompt, text)

        return text
```

- [ ] **Step 4: Run tests**

Run: `cd /home/user/YuNing/CultureDx && uv run pytest tests/test_llm_client.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/user/YuNing/CultureDx
git add src/culturedx/llm/client.py tests/conftest.py tests/test_llm_client.py
git commit -m "feat: Ollama LLM client with caching and prompt hashing"
```

---

### Task 7: Test fixtures

**Files:**
- Create: `tests/fixtures/mdd5k_sample.json`
- Create: `tests/fixtures/pdch_sample.json`
- Create: `tests/fixtures/edaic_sample.json`

- [ ] **Step 1: Create MDD-5k fixture**

```json
[
  {
    "case_id": "mdd5k_001",
    "dialogue": [
      {"speaker": "doctor", "text": "你好，请问你最近有什么不舒服的地方吗？"},
      {"speaker": "patient", "text": "医生，我最近两个月一直失眠，头疼，什么都不想做。"},
      {"speaker": "doctor", "text": "情绪方面呢？"},
      {"speaker": "patient", "text": "心情一直很低落，对什么都没兴趣了。"}
    ],
    "diagnosis": ["F32"],
    "diagnosis_text": "Depressive episode"
  },
  {
    "case_id": "mdd5k_002",
    "dialogue": [
      {"speaker": "doctor", "text": "你来看诊是因为什么问题呢？"},
      {"speaker": "patient", "text": "我总是很紧张，心跳加速，胸闷。"},
      {"speaker": "doctor", "text": "这种状况持续多久了？"},
      {"speaker": "patient", "text": "半年多了，有时候突然会很害怕，觉得自己要死了。"}
    ],
    "diagnosis": ["F41.0"],
    "diagnosis_text": "Panic disorder"
  },
  {
    "case_id": "mdd5k_003",
    "dialogue": [
      {"speaker": "doctor", "text": "你主要有哪些症状？"},
      {"speaker": "patient", "text": "我情绪很低落，经常想哭，而且总是担心各种事情。"},
      {"speaker": "doctor", "text": "睡眠怎么样？"},
      {"speaker": "patient", "text": "睡不好，经常半夜醒来，白天也紧张得不行。"}
    ],
    "diagnosis": ["F32", "F41.1"],
    "diagnosis_text": "Depressive episode with generalized anxiety"
  }
]
```

- [ ] **Step 2: Create PDCH fixture**

```json
[
  {
    "case_id": "pdch_001",
    "dialogue": [
      {"speaker": "doctor", "text": "你最近心情怎么样？"},
      {"speaker": "patient", "text": "很不好，整天都没有精神。"},
      {"speaker": "doctor", "text": "睡眠情况呢？"},
      {"speaker": "patient", "text": "入睡困难，经常凌晨三四点就醒了。"}
    ],
    "hamd17": {"item1": 2, "item2": 1, "item3": 1, "item4": 2, "item5": 1, "item6": 1, "item7": 2, "item8": 0, "item9": 0, "item10": 1, "item11": 1, "item12": 0, "item13": 1, "item14": 0, "item15": 1, "item16": 1, "item17": 0},
    "hamd17_total": 15
  },
  {
    "case_id": "pdch_002",
    "dialogue": [
      {"speaker": "doctor", "text": "你来看什么问题？"},
      {"speaker": "patient", "text": "就是有点睡不好，其他还好。"}
    ],
    "hamd17": {"item1": 0, "item2": 0, "item3": 0, "item4": 1, "item5": 0, "item6": 0, "item7": 0, "item8": 0, "item9": 0, "item10": 0, "item11": 0, "item12": 0, "item13": 0, "item14": 0, "item15": 0, "item16": 0, "item17": 0},
    "hamd17_total": 1
  }
]
```

- [ ] **Step 3: Create E-DAIC fixture**

```json
[
  {
    "case_id": "edaic_001",
    "dialogue": [
      {"speaker": "interviewer", "text": "How have you been feeling lately?"},
      {"speaker": "participant", "text": "Not great. I've been feeling really down and I can't seem to enjoy anything anymore."},
      {"speaker": "interviewer", "text": "How about your sleep?"},
      {"speaker": "participant", "text": "Terrible. I wake up at 3am every night and can't get back to sleep."}
    ],
    "phq8": {"item1": 2, "item2": 3, "item3": 2, "item4": 2, "item5": 1, "item6": 1, "item7": 1, "item8": 0},
    "phq8_total": 12,
    "phq8_binary": 1
  },
  {
    "case_id": "edaic_002",
    "dialogue": [
      {"speaker": "interviewer", "text": "How have you been doing?"},
      {"speaker": "participant", "text": "Pretty good actually. Work is going well and I've been exercising regularly."}
    ],
    "phq8": {"item1": 0, "item2": 0, "item3": 0, "item4": 0, "item5": 0, "item6": 0, "item7": 0, "item8": 0},
    "phq8_total": 0,
    "phq8_binary": 0
  }
]
```

- [ ] **Step 4: Commit**

```bash
cd /home/user/YuNing/CultureDx
mkdir -p tests/fixtures
git add tests/fixtures/
git commit -m "feat: test fixtures for MDD-5k, PDCH, and E-DAIC"
```

---

### Task 8: Dataset adapters

**Files:**
- Create: `src/culturedx/data/adapters/base.py`
- Create: `src/culturedx/data/adapters/mdd5k.py`
- Create: `src/culturedx/data/adapters/pdch.py`
- Create: `src/culturedx/data/adapters/edaic.py`
- Create: `configs/datasets/mdd5k.yaml`
- Create: `configs/datasets/pdch.yaml`
- Create: `configs/datasets/edaic.yaml`
- Create: `tests/test_adapters.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_adapters.py
"""Tests for dataset adapters."""
import json
import pytest
from pathlib import Path
from culturedx.data.adapters.base import BaseDatasetAdapter
from culturedx.data.adapters.mdd5k import MDD5kAdapter
from culturedx.data.adapters.pdch import PDCHAdapter
from culturedx.data.adapters.edaic import EDAICAdapter


FIXTURES = Path(__file__).parent / "fixtures"


class TestMDD5kAdapter:
    def test_load_fixture(self):
        adapter = MDD5kAdapter(data_path=FIXTURES / "mdd5k_sample.json")
        cases = adapter.load()
        assert len(cases) == 3
        assert cases[0].language == "zh"
        assert cases[0].coding_system == "icd10"
        assert cases[0].dataset == "mdd5k"
        assert cases[0].diagnoses == ["F32"]

    def test_comorbid_case(self):
        adapter = MDD5kAdapter(data_path=FIXTURES / "mdd5k_sample.json")
        cases = adapter.load()
        comorbid = cases[2]
        assert comorbid.comorbid is True
        assert len(comorbid.diagnoses) == 2

    def test_transcript_has_turns(self):
        adapter = MDD5kAdapter(data_path=FIXTURES / "mdd5k_sample.json")
        cases = adapter.load()
        assert len(cases[0].transcript) == 4
        assert cases[0].transcript[0].speaker == "doctor"


class TestPDCHAdapter:
    def test_load_fixture(self):
        adapter = PDCHAdapter(data_path=FIXTURES / "pdch_sample.json")
        cases = adapter.load()
        assert len(cases) == 2
        assert cases[0].language == "zh"
        assert cases[0].severity is not None
        assert cases[0].severity["hamd17_total"] == 15

    def test_binary_label(self):
        adapter = PDCHAdapter(data_path=FIXTURES / "pdch_sample.json", binary_threshold=8)
        cases = adapter.load()
        assert cases[0].metadata["binary"] == 1  # total=15 >= 8
        assert cases[1].metadata["binary"] == 0  # total=1 < 8


class TestEDAICAdapter:
    def test_load_fixture(self):
        adapter = EDAICAdapter(data_path=FIXTURES / "edaic_sample.json")
        cases = adapter.load()
        assert len(cases) == 2
        assert cases[0].language == "en"
        assert cases[0].coding_system == "dsm5"
        assert cases[0].severity["phq8_total"] == 12

    def test_binary_label(self):
        adapter = EDAICAdapter(data_path=FIXTURES / "edaic_sample.json")
        cases = adapter.load()
        assert cases[0].metadata["binary"] == 1  # total=12 >= 10
        assert cases[1].metadata["binary"] == 0  # total=0 < 10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/YuNing/CultureDx && uv run pytest tests/test_adapters.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement base adapter**

```python
# src/culturedx/data/adapters/base.py
"""Base dataset adapter interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from culturedx.core.models import ClinicalCase


class BaseDatasetAdapter(ABC):
    """Abstract base for all dataset adapters."""

    def __init__(self, data_path: str | Path, **kwargs) -> None:
        self.data_path = Path(data_path)

    @abstractmethod
    def load(self, split: str | None = None) -> list[ClinicalCase]:
        """Load and normalize dataset to ClinicalCase list."""
        ...
```

- [ ] **Step 4: Implement MDD-5k adapter**

```python
# src/culturedx/data/adapters/mdd5k.py
"""MDD-5k dataset adapter."""
from __future__ import annotations

import json
from pathlib import Path

from culturedx.core.models import ClinicalCase, Turn
from culturedx.data.adapters.base import BaseDatasetAdapter


class MDD5kAdapter(BaseDatasetAdapter):
    """Adapter for MDD-5k: Chinese multi-disorder diagnostic dialogues."""

    def load(self, split: str | None = None) -> list[ClinicalCase]:
        with open(self.data_path, encoding="utf-8") as f:
            raw = json.load(f)

        cases = []
        for item in raw:
            turns = [
                Turn(
                    speaker=turn["speaker"],
                    text=turn["text"],
                    turn_id=i,
                )
                for i, turn in enumerate(item["dialogue"])
            ]
            diagnoses = item["diagnosis"]
            cases.append(
                ClinicalCase(
                    case_id=item["case_id"],
                    transcript=turns,
                    language="zh",
                    dataset="mdd5k",
                    transcript_format="dialogue",
                    coding_system="icd10",
                    diagnoses=diagnoses,
                    comorbid=len(diagnoses) > 1,
                    metadata={"diagnosis_text": item.get("diagnosis_text", "")},
                )
            )
        return cases
```

- [ ] **Step 5: Implement PDCH adapter**

```python
# src/culturedx/data/adapters/pdch.py
"""PDCH dataset adapter."""
from __future__ import annotations

import json
from pathlib import Path

from culturedx.core.models import ClinicalCase, Turn
from culturedx.data.adapters.base import BaseDatasetAdapter


class PDCHAdapter(BaseDatasetAdapter):
    """Adapter for PDCH: Chinese depression consultations with HAMD-17."""

    def __init__(self, data_path: str | Path, binary_threshold: int = 8, **kwargs) -> None:
        super().__init__(data_path, **kwargs)
        self.binary_threshold = binary_threshold

    def load(self, split: str | None = None) -> list[ClinicalCase]:
        with open(self.data_path, encoding="utf-8") as f:
            raw = json.load(f)

        cases = []
        for item in raw:
            turns = [
                Turn(speaker=turn["speaker"], text=turn["text"], turn_id=i)
                for i, turn in enumerate(item["dialogue"])
            ]
            total = item["hamd17_total"]
            binary = 1 if total >= self.binary_threshold else 0
            cases.append(
                ClinicalCase(
                    case_id=item["case_id"],
                    transcript=turns,
                    language="zh",
                    dataset="pdch",
                    transcript_format="dialogue",
                    coding_system="hamd17",
                    diagnoses=[],
                    severity={"hamd17": item["hamd17"], "hamd17_total": total},
                    metadata={"binary": binary},
                )
            )
        return cases
```

- [ ] **Step 6: Implement E-DAIC adapter**

```python
# src/culturedx/data/adapters/edaic.py
"""E-DAIC dataset adapter."""
from __future__ import annotations

import json
from pathlib import Path

from culturedx.core.models import ClinicalCase, Turn
from culturedx.data.adapters.base import BaseDatasetAdapter


class EDAICAdapter(BaseDatasetAdapter):
    """Adapter for E-DAIC: English depression interviews with PHQ-8."""

    def __init__(self, data_path: str | Path, binary_threshold: int = 10, **kwargs) -> None:
        super().__init__(data_path, **kwargs)
        self.binary_threshold = binary_threshold

    def load(self, split: str | None = None) -> list[ClinicalCase]:
        with open(self.data_path, encoding="utf-8") as f:
            raw = json.load(f)

        cases = []
        for item in raw:
            turns = [
                Turn(speaker=turn["speaker"], text=turn["text"], turn_id=i)
                for i, turn in enumerate(item["dialogue"])
            ]
            total = item["phq8_total"]
            binary = 1 if total >= self.binary_threshold else 0
            cases.append(
                ClinicalCase(
                    case_id=item["case_id"],
                    transcript=turns,
                    language="en",
                    dataset="edaic",
                    transcript_format="dialogue",
                    coding_system="dsm5",
                    diagnoses=[],
                    severity={"phq8": item["phq8"], "phq8_total": total},
                    metadata={"binary": binary},
                )
            )
        return cases
```

- [ ] **Step 7: Create dataset config YAMLs**

`configs/datasets/mdd5k.yaml`:
```yaml
dataset:
  name: mdd5k
  language: zh
  coding_system: icd10
  transcript_format: dialogue
  data_path: data/raw/mdd5k
  split_strategy: stratified
```

`configs/datasets/pdch.yaml`:
```yaml
dataset:
  name: pdch
  language: zh
  coding_system: hamd17
  transcript_format: dialogue
  data_path: data/raw/pdch
  split_strategy: kfold_5
```

`configs/datasets/edaic.yaml`:
```yaml
dataset:
  name: edaic
  language: en
  coding_system: dsm5
  transcript_format: dialogue
  data_path: data/raw/edaic
  split_strategy: fixed
```

- [ ] **Step 8: Run tests**

Run: `cd /home/user/YuNing/CultureDx && uv run pytest tests/test_adapters.py -v`
Expected: All tests PASS

- [ ] **Step 9: Commit**

```bash
cd /home/user/YuNing/CultureDx
git add src/culturedx/data/ tests/test_adapters.py configs/datasets/
git commit -m "feat: dataset adapters for MDD-5k, PDCH, and E-DAIC"
```

---

## Chunk 3: Metrics, Single-Model Mode, CLI & Smoke Test

### Task 9: Evaluation metrics

**Files:**
- Create: `src/culturedx/eval/metrics.py`
- Create: `tests/test_metrics.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_metrics.py
"""Tests for evaluation metrics."""
import pytest
from culturedx.eval.metrics import (
    top_k_accuracy,
    macro_f1,
    binary_f1,
    mae,
    rmse,
    pearson_r,
    compute_diagnosis_metrics,
    compute_severity_metrics,
)


class TestDiagnosisMetrics:
    def test_top1_accuracy_perfect(self):
        preds = [["F32"], ["F41.1"], ["F32"]]
        golds = [["F32"], ["F41.1"], ["F32"]]
        assert top_k_accuracy(preds, golds, k=1) == 1.0

    def test_top1_accuracy_half(self):
        preds = [["F32"], ["F41.1"]]
        golds = [["F32"], ["F32"]]
        assert top_k_accuracy(preds, golds, k=1) == 0.5

    def test_top3_accuracy(self):
        preds = [["F41.1", "F32", "F43.1"]]
        golds = [["F32"]]
        assert top_k_accuracy(preds, golds, k=3) == 1.0

    def test_macro_f1(self):
        preds = ["F32", "F32", "F41.1", "F41.1"]
        golds = ["F32", "F41.1", "F41.1", "F41.1"]
        f1 = macro_f1(preds, golds)
        assert 0.0 < f1 < 1.0  # Not perfect


class TestSeverityMetrics:
    def test_mae_perfect(self):
        preds = [10.0, 5.0, 15.0]
        golds = [10.0, 5.0, 15.0]
        assert mae(preds, golds) == 0.0

    def test_mae_known(self):
        preds = [10.0, 5.0]
        golds = [12.0, 3.0]
        assert mae(preds, golds) == 2.0

    def test_rmse_known(self):
        preds = [10.0, 5.0]
        golds = [12.0, 3.0]
        assert abs(rmse(preds, golds) - 2.0) < 1e-6  # sqrt((4+4)/2) = 2.0

    def test_pearson_r_perfect(self):
        preds = [1.0, 2.0, 3.0, 4.0, 5.0]
        golds = [1.0, 2.0, 3.0, 4.0, 5.0]
        r = pearson_r(preds, golds)
        assert abs(r - 1.0) < 1e-6

    def test_binary_f1(self):
        preds = [1, 1, 0, 0]
        golds = [1, 0, 0, 1]
        f1 = binary_f1(preds, golds)
        assert 0.0 < f1 < 1.0


class TestComputeHelpers:
    def test_compute_diagnosis_metrics(self):
        preds = [["F32"], ["F41.1"]]
        golds = [["F32"], ["F41.1"]]
        metrics = compute_diagnosis_metrics(preds, golds)
        assert "top1_accuracy" in metrics
        assert "macro_f1" in metrics
        assert metrics["top1_accuracy"] == 1.0

    def test_compute_severity_metrics(self):
        preds = [10.0, 5.0]
        golds = [12.0, 3.0]
        metrics = compute_severity_metrics(preds, golds)
        assert "mae" in metrics
        assert "pearson_r" in metrics
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/user/YuNing/CultureDx && uv run pytest tests/test_metrics.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement metrics**

```python
# src/culturedx/eval/metrics.py
"""Evaluation metrics for diagnosis and severity tasks."""
from __future__ import annotations

import numpy as np
from scipy import stats
from sklearn.metrics import f1_score


def top_k_accuracy(
    preds: list[list[str]], golds: list[list[str]], k: int = 1
) -> float:
    """Top-k accuracy: correct if any gold diagnosis is in top-k predictions."""
    correct = 0
    for pred_list, gold_list in zip(preds, golds):
        top_k_preds = set(pred_list[:k])
        if top_k_preds & set(gold_list):
            correct += 1
    return correct / len(preds) if preds else 0.0


def macro_f1(preds: list[str], golds: list[str]) -> float:
    """Macro-averaged F1 across all classes."""
    return float(f1_score(golds, preds, average="macro", zero_division=0))


def binary_f1(preds: list[int], golds: list[int]) -> float:
    """Binary F1 score (positive class)."""
    return float(f1_score(golds, preds, average="binary", zero_division=0))


def mae(preds: list[float], golds: list[float]) -> float:
    """Mean absolute error."""
    return float(np.mean(np.abs(np.array(preds) - np.array(golds))))


def rmse(preds: list[float], golds: list[float]) -> float:
    """Root mean squared error."""
    return float(np.sqrt(np.mean((np.array(preds) - np.array(golds)) ** 2)))


def pearson_r(preds: list[float], golds: list[float]) -> float:
    """Pearson correlation coefficient."""
    if len(preds) < 3:
        return 0.0
    r, _ = stats.pearsonr(preds, golds)
    return float(r)


def compute_diagnosis_metrics(
    preds: list[list[str]], golds: list[list[str]]
) -> dict:
    """Compute all diagnosis metrics."""
    # For macro F1, use primary (first) diagnosis
    primary_preds = [p[0] if p else "unknown" for p in preds]
    primary_golds = [g[0] if g else "unknown" for g in golds]
    return {
        "top1_accuracy": top_k_accuracy(preds, golds, k=1),
        "top3_accuracy": top_k_accuracy(preds, golds, k=3),
        "macro_f1": macro_f1(primary_preds, primary_golds),
    }


def compute_severity_metrics(
    preds: list[float], golds: list[float]
) -> dict:
    """Compute all severity scoring metrics."""
    return {
        "mae": mae(preds, golds),
        "rmse": rmse(preds, golds),
        "pearson_r": pearson_r(preds, golds),
        # CCC deferred to Phase 2 (requires calibrated severity predictions)
    }
```

- [ ] **Step 4: Run tests**

Run: `cd /home/user/YuNing/CultureDx && uv run pytest tests/test_metrics.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/user/YuNing/CultureDx
git add src/culturedx/eval/metrics.py tests/test_metrics.py
git commit -m "feat: evaluation metrics (top-k accuracy, macro F1, MAE, Pearson r)"
```

---

### Task 10: Base agent and mode interfaces

**Files:**
- Create: `src/culturedx/agents/base.py`
- Create: `src/culturedx/modes/base.py`

- [ ] **Step 1: Implement base agent**

```python
# src/culturedx/agents/base.py
"""Base agent interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentInput:
    """Input to any agent."""

    transcript_text: str
    evidence: dict | None = None
    language: str = "zh"
    extra: dict = field(default_factory=dict)


@dataclass
class AgentOutput:
    """Output from any agent."""

    raw_response: str = ""
    parsed: dict | None = None
    model_name: str = ""
    prompt_hash: str = ""


class BaseAgent(ABC):
    """Abstract base for all agents."""

    @abstractmethod
    def run(self, input: AgentInput) -> AgentOutput:
        ...
```

- [ ] **Step 2: Implement base mode orchestrator**

```python
# src/culturedx/modes/base.py
"""Base mode orchestrator interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from culturedx.core.models import ClinicalCase, DiagnosisResult, EvidenceBrief


class BaseModeOrchestrator(ABC):
    """Abstract base for all MAS mode orchestrators."""

    @abstractmethod
    def diagnose(
        self, case: ClinicalCase, evidence: EvidenceBrief | None = None
    ) -> DiagnosisResult:
        ...
```

- [ ] **Step 3: Commit**

```bash
cd /home/user/YuNing/CultureDx
git add src/culturedx/agents/base.py src/culturedx/modes/base.py
git commit -m "feat: base agent and mode orchestrator interfaces"
```

---

### Task 11: Single-model baseline mode

**Files:**
- Create: `src/culturedx/modes/single.py`
- Create: `prompts/single/zero_shot_zh.jinja`
- Create: `prompts/single/zero_shot_en.jinja`
- Create: `prompts/CHANGELOG.md`
- Create: `tests/test_single_mode.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_single_mode.py
"""Tests for single-model baseline mode."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from jinja2 import DictLoader, Environment
from culturedx.modes.single import SingleModelMode
from culturedx.core.models import ClinicalCase, Turn


_MOCK_TEMPLATES = {
    "zero_shot_zh.jinja": "{% for turn in transcript %}{{ turn.speaker }}: {{ turn.text }}\n{% endfor %}",
    "zero_shot_en.jinja": "{% for turn in transcript %}{{ turn.speaker }}: {{ turn.text }}\n{% endfor %}",
}


@pytest.fixture
def mock_llm():
    client = MagicMock()
    client.model = "test-model"
    client.compute_prompt_hash.return_value = "abc123"
    return client


@pytest.fixture
def mock_mode(mock_llm):
    """SingleModelMode with in-memory templates (no filesystem dependency)."""
    mode = SingleModelMode.__new__(SingleModelMode)
    mode.llm = mock_llm
    mode.prompts_dir = Path("prompts/single")
    mode._env = Environment(loader=DictLoader(_MOCK_TEMPLATES))
    return mode


class TestSingleModelMode:
    def test_diagnose_zh(self, mock_llm, sample_case_zh, mock_mode):
        mock_llm.generate.return_value = '{"primary_diagnosis": "F32", "confidence": 0.8}'
        result = mock_mode.diagnose(sample_case_zh)
        assert result.case_id == "test_zh_001"
        assert result.primary_diagnosis == "F32"
        assert result.mode == "single"
        assert result.language_used == "zh"
        mock_llm.generate.assert_called_once()

    def test_diagnose_en(self, mock_llm, sample_case_en, mock_mode):
        mock_llm.generate.return_value = '{"primary_diagnosis": "F32", "confidence": 0.7}'
        result = mock_mode.diagnose(sample_case_en)
        assert result.language_used == "en"

    def test_diagnose_parse_failure(self, mock_llm, sample_case_zh, mock_mode):
        mock_llm.generate.return_value = "I cannot diagnose this patient."
        result = mock_mode.diagnose(sample_case_zh)
        assert result.decision == "abstain"
        assert result.primary_diagnosis is None
```

- [ ] **Step 2: Create prompt templates**

`prompts/single/zero_shot_zh.jinja`:
```
你是一位精神科诊断专家。请根据以下临床对话，判断患者最可能的精神疾病诊断。

## 临床对话

{% for turn in transcript %}
{{ turn.speaker }}: {{ turn.text }}
{% endfor %}

## 输出要求

请以JSON格式输出：
{
  "primary_diagnosis": "ICD-10编码（如F32）",
  "comorbid_diagnoses": ["其他共病编码"],
  "confidence": 0.0到1.0之间的置信度,
  "reasoning": "简短的诊断理由"
}
```

`prompts/single/zero_shot_en.jinja`:
```
You are a psychiatric diagnostic expert. Based on the following clinical dialogue, determine the most likely psychiatric diagnosis for the patient.

## Clinical Dialogue

{% for turn in transcript %}
{{ turn.speaker }}: {{ turn.text }}
{% endfor %}

## Output Requirements

Respond in JSON format:
{
  "primary_diagnosis": "ICD-10 code (e.g., F32)",
  "comorbid_diagnoses": ["other comorbid codes"],
  "confidence": 0.0 to 1.0 confidence score,
  "reasoning": "brief diagnostic reasoning"
}
```

`prompts/CHANGELOG.md`:
```markdown
# Prompt Changelog

## v0.1.0 (2026-03-18)
- Initial zero-shot diagnosis prompts for Chinese and English
```

- [ ] **Step 3: Implement single-model mode**

```python
# src/culturedx/modes/single.py
"""Single-model baseline mode."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.core.models import ClinicalCase, DiagnosisResult, EvidenceBrief
from culturedx.llm.json_utils import extract_json_from_response
from culturedx.modes.base import BaseModeOrchestrator


class SingleModelMode(BaseModeOrchestrator):
    """Zero-shot or few-shot single LLM call for diagnosis."""

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/single",
    ) -> None:
        self.llm = llm_client
        self.prompts_dir = Path(prompts_dir)
        self._env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            keep_trailing_newline=True,
        )

    def diagnose(
        self, case: ClinicalCase, evidence: EvidenceBrief | None = None
    ) -> DiagnosisResult:
        lang = case.language
        template_name = f"zero_shot_{lang}.jinja"
        template = self._env.get_template(template_name)

        prompt = template.render(
            transcript=case.transcript,
            evidence=evidence,
        )
        source, _, _ = self._env.loader.get_source(self._env, template_name)
        prompt_hash = self.llm.compute_prompt_hash(source)

        raw = self.llm.generate(prompt, prompt_hash=prompt_hash, language=lang)
        parsed = extract_json_from_response(raw)

        if parsed is None:
            return DiagnosisResult(
                case_id=case.case_id,
                primary_diagnosis=None,
                confidence=0.0,
                decision="abstain",
                mode="single",
                model_name=self.llm.model,
                prompt_hash=prompt_hash,
                language_used=case.language,
            )

        return DiagnosisResult(
            case_id=case.case_id,
            primary_diagnosis=parsed.get("primary_diagnosis"),
            comorbid_diagnoses=parsed.get("comorbid_diagnoses", []),
            confidence=parsed.get("confidence", 0.0),
            decision="diagnosis",
            mode="single",
            model_name=self.llm.model,
            prompt_hash=prompt_hash,
            language_used=case.language,
        )

```

- [ ] **Step 4: Run tests**

Run: `cd /home/user/YuNing/CultureDx && uv run pytest tests/test_single_mode.py -v`
Expected: All tests PASS (may need minor adjustments to match mock setup)

- [ ] **Step 5: Commit**

```bash
cd /home/user/YuNing/CultureDx
git add src/culturedx/modes/single.py prompts/ tests/test_single_mode.py
git commit -m "feat: single-model baseline mode with zero-shot prompts"
```

---

### Task 12: Experiment runner

**Files:**
- Create: `src/culturedx/pipeline/runner.py`

- [ ] **Step 1: Implement experiment runner**

```python
# src/culturedx/pipeline/runner.py
"""Experiment runner: processes cases through a mode and evaluates."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

from culturedx.core.models import ClinicalCase, DiagnosisResult
from culturedx.eval.metrics import compute_diagnosis_metrics
from culturedx.modes.base import BaseModeOrchestrator

logger = logging.getLogger(__name__)


class ExperimentRunner:
    """Run a mode on a list of cases and collect results."""

    def __init__(
        self,
        mode: BaseModeOrchestrator,
        output_dir: str | Path,
    ) -> None:
        self.mode = mode
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(self, cases: list[ClinicalCase]) -> list[DiagnosisResult]:
        results = []
        for i, case in enumerate(cases):
            logger.info("Processing case %d/%d: %s", i + 1, len(cases), case.case_id)
            result = self.mode.diagnose(case)
            results.append(result)
        self._save_predictions(results)
        return results

    def evaluate(
        self, results: list[DiagnosisResult], cases: list[ClinicalCase]
    ) -> dict:
        """Evaluate results against ground truth."""
        metrics = {}

        # Diagnosis metrics (if cases have diagnoses)
        has_dx = [c for c in cases if c.diagnoses]
        if has_dx:
            preds = []
            golds = []
            for r, c in zip(results, cases):
                if c.diagnoses:
                    pred_dx = [r.primary_diagnosis] if r.primary_diagnosis else ["unknown"]
                    pred_dx += r.comorbid_diagnoses
                    preds.append(pred_dx)
                    golds.append(c.diagnoses)
            metrics["diagnosis"] = compute_diagnosis_metrics(preds, golds)

        # Severity metrics deferred to Phase 2 — requires structured severity output
        # from LLM, not available in single-model baseline.

        self._save_metrics(metrics)
        return metrics

    def _save_predictions(self, results: list[DiagnosisResult]) -> None:
        path = self.output_dir / "predictions.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for r in results:
                f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")

    def _save_metrics(self, metrics: dict) -> None:
        path = self.output_dir / "metrics.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
```

- [ ] **Step 2: Commit**

```bash
cd /home/user/YuNing/CultureDx
git add src/culturedx/pipeline/runner.py
git commit -m "feat: experiment runner with prediction saving and evaluation"
```

---

### Task 13: CLI entry point

**Files:**
- Create: `src/culturedx/pipeline/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Implement CLI**

```python
# src/culturedx/pipeline/cli.py
"""CLI entry point for CultureDx."""
from __future__ import annotations

import logging
from pathlib import Path

import click

from culturedx.core.config import load_config


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def cli(verbose: bool) -> None:
    """CultureDx: Culture-Adaptive Diagnostic MAS."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@cli.command()
@click.option("--config", "-c", required=True, type=click.Path(exists=True))
@click.option("--dataset", "-d", required=True, help="Dataset name (mdd5k, pdch, edaic)")
@click.option("--split", "-s", default=None, help="Dataset split")
@click.option("--output-dir", "-o", default=None, help="Output directory override")
def run(config: str, dataset: str, split: str | None, output_dir: str | None) -> None:
    """Run an experiment with a given config and dataset."""
    cfg = load_config(config)
    click.echo(f"Running CultureDx mode={cfg.mode.type} on dataset={dataset}")
    click.echo(f"Config loaded from {config}")
    # Full implementation in Phase 1 completion — wires up adapter + mode + runner
    click.echo("Run complete.")


@cli.command()
def smoke() -> None:
    """Run smoke test on fixture data."""
    click.echo("Running smoke test...")
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    fixtures = project_root / "tests" / "fixtures"
    if not fixtures.exists():
        click.echo(f"ERROR: fixtures directory not found at {fixtures}", err=True)
        raise SystemExit(1)
    click.echo("Smoke test passed (fixture files found).")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: Write CLI test**

```python
# tests/test_cli.py
"""Tests for CLI entry point."""
import pytest
from click.testing import CliRunner
from culturedx.pipeline.cli import cli


class TestCLI:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "CultureDx" in result.output

    def test_smoke(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["smoke"])
        assert result.exit_code == 0
        assert "Smoke test" in result.output
```

- [ ] **Step 3: Run tests**

Run: `cd /home/user/YuNing/CultureDx && uv run pytest tests/test_cli.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
cd /home/user/YuNing/CultureDx
git add src/culturedx/pipeline/cli.py tests/test_cli.py
git commit -m "feat: CLI entry point with run and smoke commands"
```

---

### Task 14: CLAUDE.md and final smoke test

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Create CLAUDE.md**

```markdown
# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

**CultureDx:** Culture-Adaptive Diagnostic MAS with Evidence Grounding for Chinese psychiatric differential diagnosis and comorbidity detection.

**Core thesis:** Evidence-grounded MAS outperforms single LLMs for Chinese psychiatric diagnosis because LLMs have weak parametric knowledge of Chinese clinical presentations, somatization requires explicit culture-aware mapping, and differential/comorbid diagnosis requires genuine agent asymmetry.

## Commands

```bash
# Setup
uv sync

# Run tests
uv run pytest -q
uv run pytest tests/test_models.py -v
uv run pytest -m "not integration"

# CLI
uv run culturedx --help
uv run culturedx smoke
uv run culturedx run --config configs/base.yaml --dataset mdd5k
```

## Package Architecture (src/culturedx/)

| Module | Purpose |
|--------|---------|
| core/config.py | Pydantic config models (all YAML fields) |
| core/models.py | Data structures (ClinicalCase, EvidenceBrief, DiagnosisResult) |
| data/adapters/ | Dataset adapters (MDD-5k, PDCH, E-DAIC) → ClinicalCase |
| llm/client.py | OllamaClient (temperature=0, top_k=1 = greedy) |
| llm/cache.py | SQLite-backed LLM response cache |
| llm/json_utils.py | JSON extraction from LLM responses |
| agents/base.py | BaseAgent ABC |
| modes/base.py | BaseModeOrchestrator ABC |
| modes/single.py | Single-model baseline (zero-shot/few-shot) |
| eval/metrics.py | Diagnosis and severity metrics |
| pipeline/runner.py | ExperimentRunner |
| pipeline/cli.py | Click CLI entry point |

## Key Invariants

1. All LLM calls via OllamaClient with temperature=0.0, top_k=1 (greedy)
2. LLM cache key: {model}:{prompt_hash}:{input_hash}
3. All datasets normalize to ClinicalCase dataclass
4. DiagnosisResult.decision is "diagnosis" or "abstain"
5. No gold features at inference

## Code Conventions

- PEP 8, max line length 100
- All file I/O: explicit encoding="utf-8"
- Type hints everywhere
- Tests: deterministic (fixed seeds), no GPU required, no private data
```

- [ ] **Step 2: Run full test suite**

Run: `cd /home/user/YuNing/CultureDx && uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
cd /home/user/YuNing/CultureDx
git add CLAUDE.md
git commit -m "feat: CLAUDE.md project guidance"
```

- [ ] **Step 4: Final commit with all remaining files**

```bash
cd /home/user/YuNing/CultureDx
git add -A
git status
git commit -m "feat: Phase 1 foundation complete — scaffold, models, adapters, metrics, single-model mode, CLI"
```
