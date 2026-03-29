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
    contrastive_enabled: bool = False
    comorbid_min_ratio: float = 0.9


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


class SomatizationConfig(BaseModel):
    enabled: bool = True
    llm_fallback: bool = True


class EvidenceConfig(BaseModel):
    enabled: bool = True
    scope_policy: str = "auto"
    retriever: RetrieverConfig = RetrieverConfig()
    somatization: SomatizationConfig = SomatizationConfig()
    top_k_retrieval: int = 20
    top_k_final: int = 10
    min_confidence: float = 0.1


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
