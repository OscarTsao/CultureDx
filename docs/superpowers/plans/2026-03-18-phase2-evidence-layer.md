---

# CultureDx Phase 2: Evidence Layer — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the culture-aware evidence extraction pipeline — symptom span extraction, BGE-M3 retrieval, Chinese somatization mapper with ontology, criteria matching, and Evidence Brief assembly — enabling evidence-grounded single-model diagnosis.

**Architecture:** LLM-based symptom extraction identifies symptom mentions from transcript turns. Chinese somatic complaints are mapped to psychiatric criteria via a somatization ontology (CCMD-3/CMeKG-inspired) with LLM fallback. BGE-M3 dense retrieval matches transcript sentences to diagnostic criteria per disorder. Evidence is assembled per-disorder per-criterion into an EvidenceBrief consumed by all MAS modes. Evidence quality metrics (criterion coverage, evidence precision) enable ablation analysis.

**Tech Stack:** Python 3.11+, sentence-transformers (BGE-M3, optional dep), Jinja2, httpx (Ollama), existing LLM cache, pytest

**Spec:** `docs/superpowers/specs/2026-03-18-culturedx-design.md` (§2 Evidence Extractor, §6 Evidence Quality Metrics)

**Phase 1 Baseline:** 52 tests, 18 commits on master. All Phase 2 builds on existing `src/culturedx/` package.

---

## File Map

### New Files (Phase 2)

| File | Responsibility |
|---|---|
| `src/culturedx/evidence/__init__.py` | Evidence subpackage |
| `src/culturedx/evidence/extractor.py` | LLM-based symptom span extraction from transcript turns |
| `src/culturedx/evidence/somatization.py` | Chinese somatization mapper (ontology lookup + LLM fallback) |
| `src/culturedx/evidence/retriever.py` | BaseRetriever ABC + MockRetriever + BGEM3Retriever |
| `src/culturedx/evidence/criteria_matcher.py` | Per-criterion evidence retrieval via dense retriever |
| `src/culturedx/evidence/brief.py` | Evidence Brief assembly from matched evidence |
| `src/culturedx/evidence/pipeline.py` | End-to-end evidence extraction orchestrator |
| `src/culturedx/ontology/__init__.py` | Ontology subpackage |
| `src/culturedx/ontology/icd10.py` | ICD-10 criterion definitions loader + lookup |
| `src/culturedx/ontology/symptom_map.py` | Somatization ontology loader + symptom lookup |
| `src/culturedx/ontology/data/icd10_criteria.json` | ICD-10 criterion text for disorders in scope |
| `src/culturedx/ontology/data/somatization_map.json` | Chinese somatic symptom → criterion mapping |
| `src/culturedx/eval/evidence_metrics.py` | Criterion coverage, evidence precision |
| `configs/evidence.yaml` | Evidence pipeline config overlay |
| `prompts/evidence/extract_symptoms_zh.jinja` | Chinese symptom extraction prompt |
| `prompts/evidence/extract_symptoms_en.jinja` | English symptom extraction prompt |
| `prompts/evidence/somatization_fallback_zh.jinja` | Somatization LLM fallback prompt |
| `prompts/single/zero_shot_evidence_zh.jinja` | Chinese zero-shot + evidence prompt |
| `prompts/single/zero_shot_evidence_en.jinja` | English zero-shot + evidence prompt |
| `tests/test_extractor.py` | Symptom span extraction tests |
| `tests/test_somatization.py` | Somatization mapper tests |
| `tests/test_retriever.py` | Retriever abstraction tests |
| `tests/test_criteria_matcher.py` | Criteria matcher tests |
| `tests/test_brief.py` | Evidence Brief assembly tests |
| `tests/test_evidence_pipeline.py` | Evidence pipeline orchestrator tests |
| `tests/test_evidence_metrics.py` | Evidence quality metrics tests |
| `tests/test_single_evidence.py` | Single-model + evidence tests |
| `tests/fixtures/icd10_criteria_sample.json` | Test fixture: subset of ICD-10 criteria |

### Modified Files (Phase 2)

| File | Changes |
|---|---|
| `src/culturedx/core/config.py` | Add EvidenceConfig, RetrieverConfig, SomatizationConfig |
| `src/culturedx/core/models.py` | Add DisorderEvidence, restructure EvidenceBrief, add fields to SymptomSpan |
| `src/culturedx/modes/single.py` | Render evidence in prompt when provided |
| `src/culturedx/pipeline/runner.py` | Wire evidence pipeline into run loop |
| `src/culturedx/pipeline/cli.py` | Add --with-evidence flag |
| `pyproject.toml` | Add sentence-transformers optional dependency |
| `tests/test_models.py` | Update EvidenceBrief tests for new structure |
| `CLAUDE.md` | Document Phase 2 modules |

---

## Chunk 1: Evidence Foundation

### Task 1: Evidence config models

**Files:**
- Modify: `src/culturedx/core/config.py`
- Create: `configs/evidence.yaml`
- Test: `tests/test_config.py` (add tests)

- [ ] **Step 1: Write failing tests for evidence config**

Add to `tests/test_config.py`:

```python
class TestEvidenceConfig:
    def test_evidence_config_defaults(self):
        from culturedx.core.config import EvidenceConfig
        cfg = EvidenceConfig()
        assert cfg.retriever.name == "mock"
        assert cfg.somatization.enabled is True
        assert cfg.top_k_retrieval == 20
        assert cfg.top_k_final == 10

    def test_retriever_config(self):
        from culturedx.core.config import RetrieverConfig
        cfg = RetrieverConfig(name="bge-m3", model_id="BAAI/bge-m3")
        assert cfg.embedding_dim == 1024
        assert cfg.device == "auto"

    def test_culturedx_config_has_evidence(self):
        from culturedx.core.config import CultureDxConfig
        cfg = CultureDxConfig()
        assert hasattr(cfg, "evidence")
        assert cfg.evidence.retriever.name == "mock"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py::TestEvidenceConfig -v`
Expected: FAIL (EvidenceConfig not defined)

- [ ] **Step 3: Implement evidence config models**

Add to `src/culturedx/core/config.py` before `CultureDxConfig`:

```python
class RetrieverConfig(BaseModel):
    name: str = "mock"  # mock, bge-m3, qwen3-embedding, nv-embed-v2
    model_id: str = ""
    embedding_dim: int = 1024
    max_length: int = 512
    batch_size: int = 32
    cache_dir: str = "data/cache/retriever"
    device: str = "auto"


class SomatizationConfig(BaseModel):
    enabled: bool = True
    ontology_path: str = "src/culturedx/ontology/data/somatization_map.json"
    llm_fallback: bool = True


class EvidenceConfig(BaseModel):
    enabled: bool = True
    retriever: RetrieverConfig = RetrieverConfig()
    somatization: SomatizationConfig = SomatizationConfig()
    top_k_retrieval: int = 20
    top_k_final: int = 10
    min_confidence: float = 0.1
```

Add `evidence` field to `CultureDxConfig`:

```python
class CultureDxConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    # ... existing fields ...
    evidence: EvidenceConfig = EvidenceConfig()
```

- [ ] **Step 4: Create evidence.yaml config overlay**

Create `configs/evidence.yaml`:

```yaml
evidence:
  enabled: true
  retriever:
    name: bge-m3
    model_id: BAAI/bge-m3
    embedding_dim: 1024
    max_length: 512
    batch_size: 32
    cache_dir: data/cache/retriever
    device: auto
  somatization:
    enabled: true
    ontology_path: src/culturedx/ontology/data/somatization_map.json
    llm_fallback: true
  top_k_retrieval: 20
  top_k_final: 10
  min_confidence: 0.1
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/culturedx/core/config.py configs/evidence.yaml tests/test_config.py
git commit -m "feat: evidence config models (RetrieverConfig, SomatizationConfig, EvidenceConfig)"
```

---

### Task 2: Restructure EvidenceBrief and SymptomSpan models

**Files:**
- Modify: `src/culturedx/core/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for new model structure**

Add to `tests/test_models.py`:

```python
# Add DisorderEvidence to the existing import at top of test_models.py:
# from culturedx.core.models import ..., DisorderEvidence

class TestDisorderEvidence:
    def test_create_disorder_evidence(self):
        ce = CriterionEvidence(
            criterion_id="F32.A1",
            spans=[SymptomSpan(text="情绪低落", turn_id=1, symptom_type="mood")],
            confidence=0.9,
        )
        de = DisorderEvidence(
            disorder_code="F32",
            disorder_name="Depressive episode",
            criteria_evidence=[ce],
        )
        assert de.disorder_code == "F32"
        assert len(de.criteria_evidence) == 1

    def test_evidence_brief_with_disorders(self):
        brief = EvidenceBrief(
            case_id="test_001",
            language="zh",
            symptom_spans=[
                SymptomSpan(
                    text="头疼", turn_id=1, symptom_type="somatic", is_somatic=True
                ),
            ],
            disorder_evidence=[
                DisorderEvidence(disorder_code="F32", disorder_name="Depressive episode"),
            ],
        )
        assert len(brief.symptom_spans) == 1
        assert brief.symptom_spans[0].is_somatic is True
        assert len(brief.disorder_evidence) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models.py::TestDisorderEvidence -v`
Expected: FAIL (DisorderEvidence not defined, is_somatic not a field)

- [ ] **Step 3: Update models**

Modify `src/culturedx/core/models.py`:

Add `is_somatic` field to `SymptomSpan`:

```python
@dataclass
class SymptomSpan:
    """An extracted symptom mention from the transcript."""

    text: str
    turn_id: int
    symptom_type: str  # "somatic", "emotional", "behavioral", "cognitive"
    mapped_criterion: str | None = None
    is_somatic: bool = False
```

Add `DisorderEvidence` dataclass BEFORE `EvidenceBrief` (between `CriterionEvidence` and `EvidenceBrief`):

```python
@dataclass
class DisorderEvidence:
    """Evidence collected for a single candidate disorder."""

    disorder_code: str  # e.g., "F32"
    disorder_name: str  # e.g., "Depressive episode"
    criteria_evidence: list[CriterionEvidence] = field(default_factory=list)
```

Add `symptom_spans` and `disorder_evidence` to `EvidenceBrief`:

```python
@dataclass
class EvidenceBrief:
    """Assembled evidence brief for a case, per criterion per disorder."""

    case_id: str
    language: str
    symptom_spans: list[SymptomSpan] = field(default_factory=list)
    disorder_evidence: list[DisorderEvidence] = field(default_factory=list)
    criteria_evidence: list[CriterionEvidence] = field(default_factory=list)
```

Note: Keep `criteria_evidence` for backward compatibility with Phase 1 tests. The new `disorder_evidence` is the primary structure for Phase 2+.

- [ ] **Step 4: Update existing EvidenceBrief tests**

The existing `TestEvidenceBrief` tests in `tests/test_models.py` use `criteria_evidence` — they still pass since we kept that field. No changes needed.

- [ ] **Step 5: Run all model tests**

Run: `uv run pytest tests/test_models.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/culturedx/core/models.py tests/test_models.py
git commit -m "feat: add DisorderEvidence model, add is_somatic to SymptomSpan"
```

---

### Task 3: ICD-10 criteria ontology

**Files:**
- Create: `src/culturedx/ontology/__init__.py`
- Create: `src/culturedx/ontology/data/icd10_criteria.json`
- Create: `src/culturedx/ontology/icd10.py`
- Create: `tests/fixtures/icd10_criteria_sample.json`
- Create: `tests/test_icd10_ontology.py`

- [ ] **Step 1: Create ontology package init**

Create `src/culturedx/ontology/__init__.py` (empty file).

- [ ] **Step 2: Create ICD-10 criteria data file**

Create `src/culturedx/ontology/data/icd10_criteria.json` with criterion definitions for all 13 disorders in scope: F20, F22, F31, F32, F33, F40, F41.0, F41.1, F42, F43.1, F43.2, F45, F51.

Each disorder entry has: `name`, `name_zh`, `category`, `criteria` dict (with `text`, `text_zh`, `type` per criterion), and `threshold` rules.

See the full JSON content in the spec reference below. Key entries include:

- **F32** (Depressive episode): 10 criteria (A, B1-B3, C1-C7), threshold: min_core=2, min_total=4
- **F41.1** (GAD): 5 criteria (A, B1-B4), threshold: min_symptoms=4, duration=6 months
- **F45** (Somatoform): 5 criteria (A, B, C1-C3), threshold: min_somatic_groups=2
- **F20** (Schizophrenia): 8 criteria (A1-A4, B1-B4), threshold: min_first_rank=1 or min_other=2
- All other disorders with appropriate criteria and thresholds

- [ ] **Step 3: Write failing tests for ICD-10 loader**

Create `tests/test_icd10_ontology.py`:

```python
"""Tests for ICD-10 criteria ontology."""
import pytest
from culturedx.ontology.icd10 import (
    load_criteria,
    get_disorder_criteria,
    get_criterion_text,
    list_disorders,
)


class TestICD10Ontology:
    def test_load_criteria(self):
        data = load_criteria()
        assert "F32" in data
        assert "F41.1" in data

    def test_list_disorders(self):
        disorders = list_disorders()
        assert "F32" in disorders
        assert "F45" in disorders
        assert len(disorders) >= 12

    def test_get_disorder_criteria(self):
        criteria = get_disorder_criteria("F32")
        assert criteria is not None
        assert "B1" in criteria
        assert criteria["B1"]["text"]
        assert criteria["B1"]["text_zh"]

    def test_get_criterion_text(self):
        text_en = get_criterion_text("F32", "B1", language="en")
        assert "depressed mood" in text_en.lower()
        text_zh = get_criterion_text("F32", "B1", language="zh")
        assert "抑郁" in text_zh

    def test_unknown_disorder(self):
        criteria = get_disorder_criteria("F99.9")
        assert criteria is None

    def test_unknown_criterion(self):
        text = get_criterion_text("F32", "Z99", language="en")
        assert text is None
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/test_icd10_ontology.py -v`
Expected: FAIL (module not found)

- [ ] **Step 5: Implement ICD-10 ontology loader**

Create `src/culturedx/ontology/icd10.py`:

```python
"""ICD-10 diagnostic criteria definitions and lookup."""
from __future__ import annotations

import json
from pathlib import Path

_CRITERIA_PATH = Path(__file__).parent / "data" / "icd10_criteria.json"
_CACHE: dict | None = None


def _load() -> dict:
    global _CACHE
    if _CACHE is None:
        with open(_CRITERIA_PATH, encoding="utf-8") as f:
            _CACHE = json.load(f)
    return _CACHE


def load_criteria() -> dict:
    """Return the full disorder-keyed criteria dict."""
    return _load()["disorders"]


def list_disorders() -> list[str]:
    """Return all disorder codes."""
    return list(load_criteria().keys())


def get_disorder_criteria(disorder_code: str) -> dict | None:
    """Return criteria dict for a disorder, or None if not found."""
    return load_criteria().get(disorder_code, {}).get("criteria")


def get_criterion_text(
    disorder_code: str, criterion_id: str, language: str = "en"
) -> str | None:
    """Return criterion text in the specified language, or None."""
    criteria = get_disorder_criteria(disorder_code)
    if criteria is None or criterion_id not in criteria:
        return None
    key = "text_zh" if language == "zh" else "text"
    return criteria[criterion_id].get(key)


def get_disorder_name(disorder_code: str, language: str = "en") -> str | None:
    """Return disorder name in the specified language, or None."""
    disorders = load_criteria()
    if disorder_code not in disorders:
        return None
    key = "name_zh" if language == "zh" else "name"
    return disorders[disorder_code].get(key)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_icd10_ontology.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/culturedx/ontology/ tests/test_icd10_ontology.py
git commit -m "feat: ICD-10 criteria ontology with 13 disorders in scope"
```

---

### Task 4: Somatization ontology data and loader

**Files:**
- Create: `src/culturedx/ontology/data/somatization_map.json`
- Create: `src/culturedx/ontology/symptom_map.py`
- Create: `tests/test_symptom_map.py`

- [ ] **Step 1: Create somatization mapping data**

Create `src/culturedx/ontology/data/somatization_map.json` with ~38 Chinese somatic symptom to psychiatric criterion mappings. Each entry has: `criteria` (list of ICD-10 criterion IDs) and `category` (pain, sleep, cardiovascular, respiratory, appetite, fatigue, gastrointestinal, autonomic, motor, cognitive, emotional).

Key mappings include:
- "头疼"/"头痛" → F32.C6, F41.1.B1, F45.C1
- "失眠"/"睡不着" → F32.C6, F51.A
- "心慌"/"心悸" → F41.0.B1, F41.1.B2
- "胸闷" → F41.0.B2, F41.1.B2, F45.C2
- "没有食欲"/"食欲不振" → F32.C7
- "全身无力"/"疲劳" → F32.B3, F41.1.B1
- "肚子疼"/"腹痛" → F45.C1

- [ ] **Step 2: Write failing tests for symptom map loader**

Create `tests/test_symptom_map.py`:

```python
"""Tests for somatization symptom map."""
import pytest
from culturedx.ontology.symptom_map import (
    load_somatization_map,
    lookup_symptom,
    get_criteria_for_symptom,
)


class TestSymptomMap:
    def test_load_map(self):
        data = load_somatization_map()
        assert "头疼" in data
        assert "失眠" in data

    def test_lookup_known_symptom(self):
        result = lookup_symptom("头疼")
        assert result is not None
        assert "criteria" in result
        assert "F32.C6" in result["criteria"]

    def test_lookup_unknown_symptom(self):
        result = lookup_symptom("未知症状xyz")
        assert result is None

    def test_get_criteria_for_symptom(self):
        criteria = get_criteria_for_symptom("失眠")
        assert isinstance(criteria, list)
        assert "F32.C6" in criteria
        assert "F51.A" in criteria

    def test_get_criteria_unknown(self):
        criteria = get_criteria_for_symptom("不存在的症状")
        assert criteria == []

    def test_all_entries_have_criteria(self):
        data = load_somatization_map()
        for symptom, entry in data.items():
            assert "criteria" in entry, f"{symptom} missing criteria"
            assert len(entry["criteria"]) > 0, f"{symptom} has empty criteria"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_symptom_map.py -v`
Expected: FAIL (module not found)

- [ ] **Step 4: Implement symptom map loader**

Create `src/culturedx/ontology/symptom_map.py`:

```python
"""Somatization symptom ontology: Chinese somatic expressions to criteria mapping."""
from __future__ import annotations

import json
from pathlib import Path

_MAP_PATH = Path(__file__).parent / "data" / "somatization_map.json"
_CACHE: dict | None = None


def _load() -> dict:
    global _CACHE
    if _CACHE is None:
        with open(_MAP_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        _CACHE = raw["mappings"]
    return _CACHE


def load_somatization_map() -> dict:
    """Return the full symptom-to-criteria mapping dict."""
    return _load()


def lookup_symptom(symptom_text: str) -> dict | None:
    """Look up a symptom in the ontology. Returns entry dict or None."""
    return _load().get(symptom_text)


def get_criteria_for_symptom(symptom_text: str) -> list[str]:
    """Return list of criterion IDs mapped to this symptom, or empty list."""
    entry = lookup_symptom(symptom_text)
    return entry["criteria"] if entry else []
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_symptom_map.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/culturedx/ontology/data/somatization_map.json src/culturedx/ontology/symptom_map.py tests/test_symptom_map.py
git commit -m "feat: somatization ontology with 38 Chinese somatic-to-criterion mappings"
```

---

### Task 5: Symptom span extractor

**Files:**
- Create: `src/culturedx/evidence/__init__.py`
- Create: `src/culturedx/evidence/extractor.py`
- Create: `prompts/evidence/extract_symptoms_zh.jinja`
- Create: `prompts/evidence/extract_symptoms_en.jinja`
- Create: `tests/test_extractor.py`

- [ ] **Step 1: Create evidence package init**

Create `src/culturedx/evidence/__init__.py` (empty file).

- [ ] **Step 2: Create extraction prompt templates**

Create `prompts/evidence/extract_symptoms_zh.jinja` — Chinese symptom extraction prompt instructing LLM to output JSON with `symptoms` list of `{text, turn_id, symptom_type}`.

Create `prompts/evidence/extract_symptoms_en.jinja` — English version.

symptom_type values: "somatic", "emotional", "behavioral", "cognitive".

- [ ] **Step 3: Write failing tests**

Create `tests/test_extractor.py` with 4 tests:
- `test_extract_symptoms_zh`: Mock LLM returns 2 symptoms, verify SymptomSpan list
- `test_extract_symptoms_en`: Mock LLM returns 1 English symptom
- `test_extract_handles_bad_json`: LLM returns non-JSON, verify empty list
- `test_somatic_flag_set_for_somatic_type`: Verify `is_somatic=True` for somatic type, False otherwise

Each test uses `MagicMock` for the LLM client with `generate.return_value = json.dumps(...)`.

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/test_extractor.py -v`
Expected: FAIL (module not found)

- [ ] **Step 5: Implement symptom extractor**

Create `src/culturedx/evidence/extractor.py`:

```python
"""LLM-based symptom span extraction from clinical transcripts."""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.core.models import ClinicalCase, SymptomSpan
from culturedx.llm.json_utils import extract_json_from_response

logger = logging.getLogger(__name__)


class SymptomExtractor:
    """Extract symptom spans from transcript turns using an LLM."""

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/evidence",
    ) -> None:
        self.llm = llm_client
        self._env = Environment(
            loader=FileSystemLoader(str(prompts_dir)),
            keep_trailing_newline=True,
        )

    def extract(self, case: ClinicalCase) -> list[SymptomSpan]:
        """Extract symptom mentions from the transcript."""
        template_name = f"extract_symptoms_{case.language}.jinja"
        template = self._env.get_template(template_name)

        prompt = template.render(turns=case.transcript)
        source, _, _ = self._env.loader.get_source(self._env, template_name)
        prompt_hash = self.llm.compute_prompt_hash(source)

        raw = self.llm.generate(
            prompt, prompt_hash=prompt_hash, language=case.language
        )
        parsed = extract_json_from_response(raw)

        if parsed is None or not isinstance(parsed, dict):
            logger.warning("Failed to parse symptoms for case %s", case.case_id)
            return []

        symptoms = parsed.get("symptoms", [])
        spans = []
        for s in symptoms:
            if not isinstance(s, dict):
                continue
            text = s.get("text", "")
            if not text:
                continue
            stype = s.get("symptom_type", "unknown")
            spans.append(
                SymptomSpan(
                    text=text,
                    turn_id=s.get("turn_id", -1),
                    symptom_type=stype,
                    is_somatic=(stype == "somatic"),
                )
            )
        return spans
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_extractor.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/culturedx/evidence/ prompts/evidence/ tests/test_extractor.py
git commit -m "feat: LLM-based symptom span extractor with bilingual prompts"
```

---

## Chunk 2: Retrieval and Matching

### Task 6: Retriever abstraction (BaseRetriever + MockRetriever + BGEM3Retriever)

**Files:**
- Create: `src/culturedx/evidence/retriever.py`
- Create: `tests/test_retriever.py`
- Modify: `pyproject.toml` (optional retrieval deps)

- [ ] **Step 1: Add optional retrieval dependency to pyproject.toml**

Add `retrieval = ["sentence-transformers>=3.0"]` to `[project.optional-dependencies]`.

- [ ] **Step 2: Write failing tests for retriever**

Create `tests/test_retriever.py` with tests for:
- `TestRetrievalResult`: creation, sortability by score
- `TestMockRetriever`: returns results, top_k limits, empty sentences, turn_ids preserved

All tests use `MockRetriever` only (no sentence-transformers needed).

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_retriever.py -v`
Expected: FAIL (module not found)

- [ ] **Step 4: Implement retriever module**

Create `src/culturedx/evidence/retriever.py` with:
- `RetrievalResult` dataclass (text, turn_id, score)
- `BaseRetriever` ABC with `retrieve(query, sentences, top_k, turn_ids)` method
- `MockRetriever`: deterministic hash-based scoring for tests
- `BGEM3Retriever`: lazy-loads sentence-transformers, encodes query + sentences, cosine similarity, returns top-k. Raises `ImportError` with helpful message if sentence-transformers not installed.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_retriever.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/culturedx/evidence/retriever.py tests/test_retriever.py pyproject.toml
git commit -m "feat: retriever abstraction with MockRetriever and BGEM3Retriever"
```

---

### Task 7: Somatization mapper

**Files:**
- Create: `src/culturedx/evidence/somatization.py`
- Create: `prompts/evidence/somatization_fallback_zh.jinja`
- Create: `tests/test_somatization.py`

- [ ] **Step 1: Create somatization fallback prompt**

Create `prompts/evidence/somatization_fallback_zh.jinja` — prompt that asks LLM to map a Chinese somatic symptom to psychiatric criteria, outputting JSON `{mapped_criteria: [...], reasoning: "..."}`.

- [ ] **Step 2: Write failing tests**

Create `tests/test_somatization.py` with 5 tests:
- `test_ontology_lookup_known`: "头疼" maps to F32.C6
- `test_ontology_lookup_unknown_no_fallback`: unknown symptom returns None without LLM
- `test_non_somatic_skipped`: emotional symptoms skip mapping
- `test_llm_fallback`: unknown somatic symptom triggers LLM call
- `test_map_all_spans`: batch mapping of mixed spans

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_somatization.py -v`
Expected: FAIL (module not found)

- [ ] **Step 4: Implement somatization mapper**

Create `src/culturedx/evidence/somatization.py`:
- `SomatizationMapper(llm_client, llm_fallback, prompts_dir)`
- `map_span(span, context)`: ontology lookup first, LLM fallback for unknown somatic spans
- Import: `from dataclasses import replace` (used to create new SymptomSpan copies)
- `map_all(spans, context)`: batch mapping
- Uses `dataclasses.replace()` to create new SymptomSpan with `mapped_criterion` set
- `mapped_criterion` is comma-joined criterion IDs string (e.g., "F32.C6,F41.1.B1")

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_somatization.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/culturedx/evidence/somatization.py prompts/evidence/somatization_fallback_zh.jinja tests/test_somatization.py
git commit -m "feat: somatization mapper with ontology lookup and LLM fallback"
```

---

### Task 8: Criteria matcher

**Files:**
- Create: `src/culturedx/evidence/criteria_matcher.py`
- Create: `tests/test_criteria_matcher.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_criteria_matcher.py` with 4 tests:
- `test_match_single_criterion`: retrieves evidence for one criterion
- `test_match_for_disorder`: matches all criteria for F32
- `test_somatization_boost`: somatization map boosts relevant sentence scores
- `test_empty_sentences`: returns empty CriterionEvidence

All tests use `MockRetriever`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_criteria_matcher.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement criteria matcher**

Create `src/culturedx/evidence/criteria_matcher.py`:
- Imports: `from culturedx.ontology.icd10 import get_disorder_criteria, get_criterion_text`
- `_SOMATIZATION_BOOST = 0.15` module-level constant
- `CriteriaMatcher(retriever, top_k, min_score)`
- `match_criterion(criterion_text, sentences, turn_ids, criterion_id, somatization_map)`: calls retriever, applies somatization boost via `dataclasses.replace(r, score=min(1.0, r.score + boost))` (no in-place mutation), converts to CriterionEvidence
- `match_for_disorder(disorder_code, sentences, turn_ids, language, somatization_map)`: loads criteria from `ontology.icd10`, matches each criterion

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_criteria_matcher.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/culturedx/evidence/criteria_matcher.py tests/test_criteria_matcher.py
git commit -m "feat: criteria matcher with per-disorder retrieval and somatization boost"
```

---

### Task 9: Evidence Brief assembler

**Files:**
- Create: `src/culturedx/evidence/brief.py`
- Create: `tests/test_brief.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_brief.py` with 4 tests:
- `test_assemble_single_disorder`: one disorder with criteria
- `test_assemble_multiple_disorders`: F32 + F41.1
- `test_assemble_with_symptom_spans`: includes extracted spans
- `test_filter_by_min_confidence`: respects min_confidence threshold

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_brief.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement brief assembler**

Create `src/culturedx/evidence/brief.py`:
- `EvidenceBriefAssembler(min_confidence)`
- `assemble(case_id, language, symptom_spans, criteria_results)`: takes disorder_code -> CriterionEvidence list dict, wraps in DisorderEvidence, returns EvidenceBrief
- Uses `ontology.icd10.get_disorder_name()` for human-readable names

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_brief.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/culturedx/evidence/brief.py tests/test_brief.py
git commit -m "feat: Evidence Brief assembler with per-disorder structure"
```

---

### Task 10: Evidence pipeline orchestrator

**Files:**
- Create: `src/culturedx/evidence/pipeline.py`
- Create: `tests/test_evidence_pipeline.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_evidence_pipeline.py` with 4 tests:
- `test_full_pipeline_zh`: Chinese case → extract symptoms → somatize → match → brief
- `test_pipeline_en_no_somatization`: English case, somatization disabled
- `test_pipeline_multiple_disorders`: F32 + F41.1 target disorders
- `test_pipeline_no_extractor`: extractor_enabled=False, still retrieves evidence

All tests use MockRetriever and MagicMock LLM client.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_evidence_pipeline.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement evidence pipeline**

Create `src/culturedx/evidence/pipeline.py`:
- `EvidencePipeline(llm_client, retriever, target_disorders, extractor_enabled, somatization_enabled, somatization_llm_fallback, top_k, min_confidence, prompts_dir)`
- `extract(case)`: orchestrates full pipeline:
  1. Extract patient turn sentences
  2. Symptom span extraction (if enabled)
  3. Somatization mapping (Chinese only, if enabled)
  4. Build somatization boost map
  5. Criteria matching per target disorder
  6. Assemble EvidenceBrief
- `_build_somatization_boost_map(spans, sentences)`: maps criterion_id -> sentence indices with somatization mappings

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_evidence_pipeline.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -q`
Expected: ALL PASS (Phase 1 + Phase 2 tests)

- [ ] **Step 6: Commit**

```bash
git add src/culturedx/evidence/pipeline.py tests/test_evidence_pipeline.py
git commit -m "feat: evidence pipeline orchestrator with full extraction flow"
```

---

## Chunk 3: Metrics and Integration

### Task 11: Evidence quality metrics

**Files:**
- Create: `src/culturedx/eval/evidence_metrics.py`
- Create: `tests/test_evidence_metrics.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_evidence_metrics.py` with tests for:
- `TestCriterionCoverage`: full coverage (1.0), partial coverage (0.5), empty brief (0.0)
- `TestEvidencePrecision`: all relevant (1.0), no gold (0.0)
- `TestComputeEvidenceQuality`: returns dict with both metrics

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_evidence_metrics.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement evidence quality metrics**

Create `src/culturedx/eval/evidence_metrics.py`:
- `criterion_coverage(brief, gold_criteria)`: fraction of gold criteria with at least one evidence span
- `evidence_precision(brief, gold_criteria)`: fraction of extracted evidence criteria matching gold
- `compute_evidence_quality_metrics(brief, gold_criteria)`: returns both

`gold_criteria` type: `dict[str, list[str]]` mapping disorder_code -> list of criterion_ids.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_evidence_metrics.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/culturedx/eval/evidence_metrics.py tests/test_evidence_metrics.py
git commit -m "feat: evidence quality metrics (criterion coverage, evidence precision)"
```

---

### Task 12: Evidence-enhanced prompts and single mode update

**Files:**
- Create: `prompts/single/zero_shot_evidence_zh.jinja`
- Create: `prompts/single/zero_shot_evidence_en.jinja`
- Modify: `src/culturedx/modes/single.py`
- Create: `tests/test_single_evidence.py`

- [ ] **Step 1: Create evidence-enhanced prompt templates**

Create bilingual evidence templates that extend zero-shot prompts with a "Extracted Symptom Evidence" section rendering `evidence.disorder_evidence` with per-criterion spans, turn IDs, and confidence scores.

- [ ] **Step 2: Update SingleModelMode to select evidence template**

In `src/culturedx/modes/single.py`, change template selection in `diagnose()`:
```python
if evidence and evidence.disorder_evidence:
    template_name = f"zero_shot_evidence_{lang}.jinja"
else:
    template_name = f"zero_shot_{lang}.jinja"
```

- [ ] **Step 3: Write failing tests for evidence mode**

Create `tests/test_single_evidence.py` with 3 tests using DictLoader:
- `test_with_evidence_uses_evidence_template`: verify prompt contains disorder code
- `test_without_evidence_uses_base_template`: verify base template used
- `test_empty_evidence_uses_base_template`: empty disorder_evidence falls back

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/test_single_evidence.py -v`
Expected: FAIL

- [ ] **Step 5: Apply the single mode changes**

- [ ] **Step 6: Run all tests to verify they pass**

Run: `uv run pytest tests/test_single_evidence.py tests/test_single_mode.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add prompts/single/zero_shot_evidence_zh.jinja prompts/single/zero_shot_evidence_en.jinja src/culturedx/modes/single.py tests/test_single_evidence.py
git commit -m "feat: evidence-enhanced single-model mode with bilingual templates"
```

---

### Task 13: Runner and CLI integration

**Files:**
- Modify: `src/culturedx/pipeline/runner.py`
- Modify: `src/culturedx/pipeline/cli.py`
- Modify: `tests/test_cli.py` (add evidence CLI test)

- [ ] **Step 1: Update ExperimentRunner to support evidence pipeline**

Add import at top of `src/culturedx/pipeline/runner.py`:
```python
from culturedx.evidence.pipeline import EvidencePipeline
```

Add `evidence_pipeline` parameter to `__init__`:
```python
def __init__(
    self,
    mode: BaseModeOrchestrator,
    output_dir: str | Path,
    evidence_pipeline: EvidencePipeline | None = None,
) -> None:
    self.mode = mode
    self.output_dir = Path(output_dir)
    self.output_dir.mkdir(parents=True, exist_ok=True)
    self.evidence_pipeline = evidence_pipeline
```

Update `run()` to extract evidence:
```python
def run(self, cases: list[ClinicalCase]) -> list[DiagnosisResult]:
    results = []
    for i, case in enumerate(cases):
        logger.info("Processing case %d/%d: %s", i + 1, len(cases), case.case_id)
        evidence = None
        if self.evidence_pipeline is not None:
            evidence = self.evidence_pipeline.extract(case)
        result = self.mode.diagnose(case, evidence=evidence)
        results.append(result)
    self._save_predictions(results)
    return results
```

Note: When `evidence_pipeline` is None, `evidence` stays None, which is backward-compatible with the existing `diagnose(case, evidence=None)` signature. Existing tests in `test_single_mode.py` pass without changes.

- [ ] **Step 2: Update CLI with --with-evidence flag**

Add `@click.option("--with-evidence", is_flag=True)` to the `run` command. Echo "Evidence extraction: ENABLED" when the flag is set.

- [ ] **Step 3: Add CLI test for evidence flag**

Add `test_run_with_evidence_flag` to `tests/test_cli.py`:
```python
def test_run_with_evidence_flag(tmp_path):
    from click.testing import CliRunner
    runner = CliRunner()
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text("seed: 42\noutput_dir: outputs\nmode:\n  name: single\n  type: single\n")
    result = runner.invoke(cli, ["run", "-c", str(config_file), "-d", "mdd5k", "--with-evidence"])
    assert result.exit_code == 0
    assert "Evidence extraction: ENABLED" in result.output
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/culturedx/pipeline/runner.py src/culturedx/pipeline/cli.py tests/test_cli.py
git commit -m "feat: wire evidence pipeline into runner and CLI (--with-evidence flag)"
```

---

### Task 14: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md with Phase 2 modules**

Add evidence layer modules to Package Architecture table, add new key invariants (somatization mapper, evidence brief structure, retriever optional dep), add new commands (`--with-evidence`, `uv pip install -e ".[retrieval]"`).

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with Phase 2 evidence layer modules"
```

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -q`
Expected: ALL PASS (Phase 1 + Phase 2 combined)

---
