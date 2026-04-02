"""Tests for scripts/run_full_eval.py helper behavior."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from culturedx.core.config import CultureDxConfig, DatasetConfig


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


def test_build_case_selection_payload_records_exact_case_order():
    load_info = {
        "eval_cases": [
            type("Case", (), {"case_id": "case-2"})(),
            type("Case", (), {"case_id": "case-1"})(),
        ]
    }
    dataset_spec = {
        "output_name": "lingxidiag",
        "adapter_name": "lingxidiag16k",
        "data_path": "data/raw/lingxidiag16k",
        "split": "validation",
    }

    payload = MODULE.build_case_selection_payload(
        dataset_spec=dataset_spec,
        load_info=load_info,
        seed=42,
    )

    assert payload["dataset"] == "lingxidiag"
    assert payload["case_ids"] == ["case-2", "case-1"]
    assert payload["case_order_fingerprint"]
    assert payload["runtime_context"]["seed"] == 42


def test_resolve_dataset_spec_defaults_lingxidiag_to_validation_split():
    cfg = CultureDxConfig(
        dataset=DatasetConfig(name="lingxidiag", data_path="data/raw/lingxidiag16k")
    )

    spec = MODULE.resolve_dataset_spec("lingxidiag", cfg)

    assert spec["split"] == "validation"


def test_resolve_dataset_spec_honors_split_override():
    cfg = CultureDxConfig(
        dataset=DatasetConfig(name="lingxidiag", data_path="data/raw/lingxidiag16k")
    )

    spec = MODULE.resolve_dataset_spec("lingxidiag", cfg, split_override="validation")

    assert spec["split"] == "validation"


def test_compute_group_metrics_exact_match_is_order_sensitive():
    rows = [
        {
            "case_id": "case-1",
            "dataset": "lingxidiag",
            "DiagnosisCode": "F32.100",
            "decision": "diagnosis",
            "primary_diagnosis": "F32",
            "comorbid_diagnoses": ["F41.1"],
            "pred_eval_codes": ["F32", "F41"],
            "gold_eval_codes": ["F32"],
            "primary_correct_mapped": True,
            "top3_correct_mapped": True,
        },
        {
            "case_id": "case-2",
            "dataset": "lingxidiag",
            "DiagnosisCode": "F41.000",
            "decision": "diagnosis",
            "primary_diagnosis": "F41.1",
            "comorbid_diagnoses": [],
            "pred_eval_codes": ["F41"],
            "gold_eval_codes": ["F41"],
            "primary_correct_mapped": True,
            "top3_correct_mapped": True,
        },
    ]

    metrics = MODULE.compute_group_metrics(rows)

    assert metrics["top1_accuracy"] == 1.0
    assert metrics["exact_match"] == 0.5
    assert metrics["table4_paper_metrics"]["2class_Acc"] == 1.0
    assert metrics["table4_paper_metrics"]["12class_Acc"] == 0.5
    assert metrics["table4_paper_metrics"]["12class_Top1"] == 1.0
