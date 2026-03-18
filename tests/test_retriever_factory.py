"""Tests for retriever factory."""
from __future__ import annotations

import pytest

from culturedx.core.config import RetrieverConfig
from culturedx.evidence.retriever import MockRetriever
from culturedx.evidence.retriever_factory import create_retriever


class TestCreateRetriever:
    def test_mock_retriever(self):
        config = RetrieverConfig(name="mock")
        retriever = create_retriever(config)
        assert isinstance(retriever, MockRetriever)

    def test_unknown_retriever(self):
        config = RetrieverConfig(name="nonexistent")
        with pytest.raises(ValueError, match="Unknown retriever"):
            create_retriever(config)

    def test_bge_m3_import_error(self):
        """Test that bge-m3 raises ImportError if sentence-transformers not installed."""
        config = RetrieverConfig(name="bge-m3")
        # This will either work (if sentence-transformers is installed) or raise ImportError
        # We just verify the factory dispatches correctly
        try:
            retriever = create_retriever(config)
            # If it works, it should be a BGEM3Retriever
            from culturedx.evidence.retriever import BGEM3Retriever
            assert isinstance(retriever, BGEM3Retriever)
        except ImportError:
            # Expected if sentence-transformers not installed
            pass
