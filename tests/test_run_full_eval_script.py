"""Tests for scripts/run_full_eval.py helper behavior."""
from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "run_full_eval.py"
SPEC = importlib.util.spec_from_file_location("run_full_eval_script", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_normalize_model_name_list_defaults_and_dedupes():
    default_model = "Qwen/Qwen3-32B-AWQ"
    assert MODULE.normalize_model_name_list(None, default_model) == [default_model]
    assert MODULE.normalize_model_name_list(
        "Qwen/Qwen3-32B-AWQ, QuantTrio/Qwen3.5-35B-A3B-AWQ, Qwen/Qwen3-32B-AWQ",
        default_model,
    ) == [
        "Qwen/Qwen3-32B-AWQ",
        "QuantTrio/Qwen3.5-35B-A3B-AWQ",
    ]


def test_resolve_model_output_dir_uses_subdirs_for_multi_model_runs(tmp_path: Path):
    model_names = [
        "Qwen/Qwen3-32B-AWQ",
        "QuantTrio/Qwen3.5-35B-A3B-AWQ",
    ]

    assert MODULE.resolve_model_output_dir(
        tmp_path,
        ["Qwen/Qwen3-32B-AWQ"],
        "Qwen/Qwen3-32B-AWQ",
    ) == tmp_path
    assert MODULE.resolve_model_output_dir(
        tmp_path,
        model_names,
        "QuantTrio/Qwen3.5-35B-A3B-AWQ",
    ) == tmp_path / "quanttrio-qwen3-5-35b-a3b-awq"
