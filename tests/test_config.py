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

    def test_load_with_vllm_overlay_overrides_model(self):
        cfg = load_config(
            CONFIGS_DIR / "base.yaml",
            overrides=[CONFIGS_DIR / "vllm_awq.yaml"],
        )
        assert cfg.llm.provider == "vllm"
        assert cfg.llm.model_id == "Qwen/Qwen3-32B-AWQ"


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
