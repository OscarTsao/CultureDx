"""Shared helpers for MAS + TF-IDF ensemble analysis scripts."""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sklearn.metrics import f1_score
from sklearn.preprocessing import MultiLabelBinarizer

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from culturedx.eval.lingxidiag_paper import PAPER_12_CLASSES
from culturedx.postproc.ensemble_gate import EnsembleConfig, apply_ensemble, paper_parent

MAS_PATH = ROOT / "results" / "validation" / "r16_bypass_logic" / "predictions.jsonl"
TFIDF_PATH = ROOT / "outputs" / "tfidf_baseline" / "predictions.jsonl"
SPLIT_PATH = ROOT / "results" / "ensemble" / "split.json"
RESULTS_DIR = ROOT / "results" / "ensemble"
_PAPER_12_CLASS_SET = set(PAPER_12_CLASSES)


def paper_label(code: str | None) -> str:
    parent = paper_parent(code)
    return parent if parent in _PAPER_12_CLASS_SET else "Others"


def dedupe_preserving_order(codes: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for code in codes:
        if code not in seen:
            seen.add(code)
            result.append(code)
    return result


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_prediction_maps(
    mas_path: Path = MAS_PATH,
    tfidf_path: Path = TFIDF_PATH,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    mas_records = load_jsonl(mas_path)
    tfidf_records = load_jsonl(tfidf_path)
    mas_map = {str(record["case_id"]): record for record in mas_records}
    tfidf_map = {str(record["case_id"]): record for record in tfidf_records}
    if len(mas_map) != len(mas_records) or len(tfidf_map) != len(tfidf_records):
        raise ValueError("Duplicate case_id detected in input predictions.")
    if set(mas_map) != set(tfidf_map):
        missing_in_tfidf = sorted(set(mas_map) - set(tfidf_map))
        missing_in_mas = sorted(set(tfidf_map) - set(mas_map))
        raise ValueError(
            "Prediction files do not have identical case_id coverage. "
            f"missing_in_tfidf={missing_in_tfidf[:5]} missing_in_mas={missing_in_mas[:5]}"
        )
    return mas_map, tfidf_map


def load_split(path: Path = SPLIT_PATH) -> dict[str, list[str]]:
    with path.open("r", encoding="utf-8") as handle:
        split = json.load(handle)
    dev_ids = [str(case_id) for case_id in split.get("dev", [])]
    test_ids = [str(case_id) for case_id in split.get("test", [])]
    if len(dev_ids) != 500 or len(test_ids) != 500:
        raise ValueError(
            f"Expected 500 dev and 500 test ids, got {len(dev_ids)} dev and {len(test_ids)} test."
        )
    if set(dev_ids) & set(test_ids):
        raise ValueError("Dev/test split overlaps.")
    return {"dev": dev_ids, "test": test_ids}


def gold_labels(record: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for raw_code in record.get("gold_diagnoses") or []:
        parent = paper_label(raw_code)
        if parent != "Others":
            labels.append(parent)
    deduped = dedupe_preserving_order(labels)
    return deduped or ["Others"]


def predicted_labels(record: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    primary = paper_label(record.get("primary_diagnosis"))
    if primary != "Others":
        labels.append(primary)
    for raw_code in record.get("comorbid_diagnoses") or []:
        parent = paper_label(raw_code)
        if parent != "Others":
            labels.append(parent)
    deduped = dedupe_preserving_order(labels)
    return deduped or ["Others"]


def primary_gold_label(record: dict[str, Any]) -> str:
    return gold_labels(record)[0]


def primary_pred_label(record: dict[str, Any]) -> str:
    return predicted_labels(record)[0]


def top1_correct(record: dict[str, Any]) -> bool:
    return primary_pred_label(record) in set(gold_labels(record))


def case_set_f1(record: dict[str, Any]) -> float:
    gold = set(gold_labels(record))
    pred = set(predicted_labels(record))
    tp = len(gold & pred)
    if tp == 0:
        return 0.0
    return (2.0 * tp) / ((2 * tp) + len(pred - gold) + len(gold - pred))


def compute_metrics(records: list[dict[str, Any]]) -> dict[str, float | int]:
    n = len(records)
    if n == 0:
        return {"n": 0, "top1": 0.0, "f1_macro": 0.0, "f1_weighted": 0.0}

    y_true = [gold_labels(record) for record in records]
    y_pred = [predicted_labels(record) for record in records]
    top1 = sum(1 for truth, pred in zip(y_true, y_pred) if pred[0] in set(truth)) / n

    binarizer = MultiLabelBinarizer(classes=PAPER_12_CLASSES)
    y_true_bin = binarizer.fit_transform(y_true)
    y_pred_bin = binarizer.transform(y_pred)

    return {
        "n": n,
        "top1": float(top1),
        "f1_macro": float(f1_score(y_true_bin, y_pred_bin, average="macro", zero_division=0)),
        "f1_weighted": float(
            f1_score(y_true_bin, y_pred_bin, average="weighted", zero_division=0)
        ),
    }


def correct_flags(records: list[dict[str, Any]]) -> list[bool]:
    return [top1_correct(record) for record in records]


def subset_records(
    prediction_map: dict[str, dict[str, Any]],
    case_ids: list[str],
) -> list[dict[str, Any]]:
    missing = [case_id for case_id in case_ids if case_id not in prediction_map]
    if missing:
        raise KeyError(f"Missing case_ids in predictions: {missing[:5]}")
    return [prediction_map[case_id] for case_id in case_ids]


def build_ensemble_records(
    case_ids: list[str],
    mas_map: dict[str, dict[str, Any]],
    tfidf_map: dict[str, dict[str, Any]],
    config: EnsembleConfig,
) -> list[dict[str, Any]]:
    return [apply_ensemble(mas_map[case_id], tfidf_map[case_id], config) for case_id in case_ids]


def build_oracle_records(
    case_ids: list[str],
    mas_map: dict[str, dict[str, Any]],
    tfidf_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for case_id in case_ids:
        mas_record = mas_map[case_id]
        tfidf_record = tfidf_map[case_id]
        mas_case_score = case_set_f1(mas_record)
        tfidf_case_score = case_set_f1(tfidf_record)
        if mas_case_score > tfidf_case_score:
            choice = dict(mas_record)
            choice["oracle_source"] = "mas"
        else:
            choice = dict(tfidf_record)
            choice["oracle_source"] = "tfidf"
        records.append(choice)
    return records


def config_to_dict(config: EnsembleConfig) -> dict[str, Any]:
    return asdict(config)


def rule_description(name: str, config: EnsembleConfig | None = None) -> str:
    if name == "mas_only":
        return "MAS only"
    if name == "tfidf_only":
        return "TF-IDF only"
    if config is None:
        return name
    strong_classes = ",".join(config.mas_strong_classes)
    if config.rule == "v1_class_based":
        return f"MAS on {{{strong_classes}}}, TF-IDF otherwise"
    return (
        f"v2 threshold {config.tfidf_threshold_high:.2f}, "
        f"MAS strong={{{strong_classes}}}"
    )


def serialize_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    serialized: dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, float):
            serialized[key] = round(value, 6)
        else:
            serialized[key] = value
    return serialized
