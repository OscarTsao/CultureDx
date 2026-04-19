# src/culturedx/core/config.py
"""Pydantic configuration models with OmegaConf YAML loading."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from omegaconf import OmegaConf
from pydantic import BaseModel, ConfigDict


class LLMConfig(BaseModel):
    provider: str = "ollama"
    model_id: str = "qwen3:14b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.0
    top_k: int = 1
    max_retries: int = 3
    disable_thinking: bool = True
    max_concurrent: int = 4
    max_tokens: int = 2048
    context_window: int | None = None


class EvalConfig(BaseModel):
    binary_threshold_phq8: int = 10
    binary_threshold_hamd17: int = 8
    bootstrap_resamples: int = 10000


class ModeConfig(BaseModel):
    name: str = "single"
    type: str = "single"
    variants: list[str] | None = None
    target_disorders: list[str] | None = None
    scope_policy: str = "auto"
    execution_mode: str = "auto"
    diagnose_then_verify: bool = False
    contrastive_enabled: bool = False
    evidence_verification: bool = False
    triage_metadata_fields: list[str] | None = None
    checker_prompt_variant: str | None = None  # None=same as prompt_variant  # None=all, []=none
    per_disorder_checker_variants: dict[str, str] | None = None  # per-disorder prompt variant overrides
    prompt_variant: str = ""
    calibrator_mode: str = "heuristic-v2"  # "heuristic-v2" or "learned"
    calibrator_artifact_path: str | None = None
    force_prediction: bool = False
    stress_detection_enabled: bool = False
    contrastive_primary_enabled: bool = False
    contrastive_primary_prompt: str = "contrastive_primary_zh"
    bypass_logic_engine: bool = False  # R16 ablation hook


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


class RetrieverConfig(BaseModel):
    name: str = "mock"  # mock, bge-m3, qwen3-embedding, nv-embed-v2
    model_id: str = ""
    embedding_dim: int = 1024
    max_length: int = 512
    batch_size: int = 32
    cache_dir: str = "data/cache/retriever"
    device: str = "auto"
    mode_weights: tuple[float, float, float] = (0.4, 0.2, 0.4)  # (dense, sparse, colbert)


class SomatizationConfig(BaseModel):
    enabled: bool = True
    mode: str = "ontology-only"  # "ontology-only", "ontology+llm", "llm-only"
    llm_fallback: bool = True  # deprecated — use mode instead


class EvidenceConfig(BaseModel):
    enabled: bool = True
    scope_policy: str = "auto"
    retriever: RetrieverConfig = RetrieverConfig()
    somatization: SomatizationConfig = SomatizationConfig()
    negation_mode: str = "clause-rule"  # "clause-rule" or "stanza-dep"
    top_k_retrieval: int = 20
    top_k_final: int = 10
    min_confidence: float = 0.1
    rerank_enabled: bool = False
    rerank_top_n: int = 5


class RetrievalConfig(BaseModel):
    """RAG case retrieval (FAISS index) settings."""
    enabled: bool = False
    top_k: int = 5
    balanced_per_class: bool = True
    level: int = 1  # 1=label-only, 2=key evidence snippets
    output_level: int = 1  # 1=label-only, 3=label+EMR fields from train cases


class CultureDxConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    seed: int = 42
    output_dir: str = "outputs/runs"
    cache_dir: str = "data/cache"
    log_level: str = "INFO"
    request_timeout_sec: int = 300
    mode: ModeConfig = ModeConfig()
    llm: LLMConfig = LLMConfig()
    checker_llm: LLMConfig | None = None
    eval: EvalConfig = EvalConfig()
    dataset: DatasetConfig = DatasetConfig()
    evidence: EvidenceConfig = EvidenceConfig()
    retrieval: RetrievalConfig = RetrievalConfig()


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
