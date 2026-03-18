# tests/test_adapter_registry.py
"""Tests for adapter registry."""
import pytest

from culturedx.data.adapters import get_adapter, list_adapters
from culturedx.data.adapters.lingxidiag16k import LingxiDiag16kAdapter
from culturedx.data.adapters.mdd5k import MDD5kAdapter, MDD5kRawAdapter
from culturedx.data.adapters.pdch import PDCHAdapter
from culturedx.data.adapters.edaic import EDAICAdapter


class TestAdapterRegistry:
    def test_list_adapters(self):
        names = list_adapters()
        assert "lingxidiag16k" in names
        assert "mdd5k" in names
        assert "mdd5k_raw" in names
        assert "pdch" in names
        assert "edaic" in names

    def test_get_lingxidiag16k(self, tmp_path):
        adapter = get_adapter("lingxidiag16k", data_path=tmp_path)
        assert isinstance(adapter, LingxiDiag16kAdapter)

    def test_get_mdd5k(self, tmp_path):
        adapter = get_adapter("mdd5k", data_path=tmp_path / "data.json")
        assert isinstance(adapter, MDD5kAdapter)

    def test_get_mdd5k_raw(self, tmp_path):
        adapter = get_adapter("mdd5k_raw", data_path=tmp_path)
        assert isinstance(adapter, MDD5kRawAdapter)

    def test_get_pdch_with_kwargs(self, tmp_path):
        adapter = get_adapter("pdch", data_path=tmp_path / "data.json", binary_threshold=12)
        assert isinstance(adapter, PDCHAdapter)
        assert adapter.binary_threshold == 12

    def test_get_edaic(self, tmp_path):
        adapter = get_adapter("edaic", data_path=tmp_path / "data.json")
        assert isinstance(adapter, EDAICAdapter)

    def test_unknown_adapter(self, tmp_path):
        with pytest.raises(ValueError, match="Unknown adapter 'nonexistent'"):
            get_adapter("nonexistent", data_path=tmp_path)
