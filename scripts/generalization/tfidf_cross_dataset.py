"""Cross-dataset TF-IDF + Logistic Regression degradation experiment.

Train a TF-IDF + One-vs-Rest Logistic Regression baseline on each dataset's
training split, then evaluate it on both held-out test splits to quantify
cross-dataset degradation.

LingxiDiag-16K uses the checked-in train/validation parquet files.
MDD-5k does not ship a checked-in train/test split in this branch, so this
script creates a deterministic 80/20 split stratified by the primary
paper-level parent label.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.culturedx.eval.lingxidiag_paper import PAPER_12_CLASSES, compute_table4_metrics
from src.culturedx.postproc.ensemble_gate import paper_parent

LINGXI_TRAIN_PATH = ROOT / "data/raw/lingxidiag16k/data/train-00000-of-00001.parquet"
LINGXI_TEST_PATH = ROOT / "data/raw/lingxidiag16k/data/validation-00000-of-00001.parquet"
MDD_ROOT = ROOT / "data/raw/mdd5k_repo"

RESULTS_DIR = ROOT / "results/generalization"
PREDICTIONS_ROOT = RESULTS_DIR / "tfidf"
RESULTS_PATH = RESULTS_DIR / "tfidf_cross_dataset.json"

MDD_TEST_SIZE = 0.20
MDD_RANDOM_SEED = 42
COMORBID_THRESHOLD = 0.30

CLASS_SET = set(PAPER_12_CLASSES)


@dataclass(frozen=True)
class Example:
    case_id: str
    dataset: str
    text: str
    raw_label_code: str
    gold_labels: list[str]


def paper_label(code: str | None) -> str:
    parent = paper_parent(code)
    return parent if parent in CLASS_SET else "Others"


def map_gold_codes(raw_code: str) -> list[str]:
    extracted: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[;,；，]", str(raw_code or "").strip().upper()):
        normalized = part.strip()
        if not normalized:
            continue
        parent = paper_label(normalized)
        if parent in seen or parent == "Others":
            continue
        seen.add(parent)
        extracted.append(parent)
    return extracted if extracted else ["Others"]


def load_lingxi_examples(path: Path, split_name: str) -> list[Example]:
    df = pd.read_parquet(path)
    examples: list[Example] = []
    for _, row in df.iterrows():
        text = str(row.get("cleaned_text", "") or "").strip()
        if not text:
            continue
        examples.append(
            Example(
                case_id=str(row["patient_id"]),
                dataset="lingxidiag16k",
                text=text,
                raw_label_code=str(row.get("DiagnosisCode", "") or ""),
                gold_labels=map_gold_codes(str(row.get("DiagnosisCode", "") or "")),
            )
        )

    if not examples:
        raise ValueError(f"No usable LingxiDiag-16K examples found in {path} ({split_name}).")
    return examples


def dialogue_file_to_text(path: Path) -> str:
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)

    parts: list[str] = []
    for entry in raw:
        for pair in entry.get("conversation", []):
            doctor_text = str(pair.get("doctor", "") or "").strip()
            patient_text = str(pair.get("patient", "") or "").strip()
            if doctor_text:
                parts.append(f"医生：{doctor_text}")
            if patient_text:
                parts.append(f"患者：{patient_text}")
    return "\n".join(parts).strip()


def load_mdd_pool(repo_root: Path) -> list[Example]:
    dialogue_dir = repo_root / "MDD_5k"
    labels_dir = repo_root / "Label"
    patient_files = sorted(dialogue_dir.glob("patient_*.json"))
    if not patient_files:
        raise FileNotFoundError(f"No patient dialogue files found in {dialogue_dir}")

    examples: list[Example] = []
    missing_labels: list[str] = []
    for patient_file in patient_files:
        case_id = patient_file.stem
        label_file = labels_dir / f"{case_id}_label.json"
        if not label_file.exists():
            missing_labels.append(case_id)
            continue

        text = dialogue_file_to_text(patient_file)
        if not text:
            continue

        with open(label_file, encoding="utf-8") as handle:
            label_payload = json.load(handle)
        raw_label_code = str(label_payload.get("ICD_Code", "") or "")

        examples.append(
            Example(
                case_id=case_id,
                dataset="mdd5k",
                text=text,
                raw_label_code=raw_label_code,
                gold_labels=map_gold_codes(raw_label_code),
            )
        )

    if missing_labels:
        raise ValueError(
            f"MDD-5k dialogue/label mismatch: missing labels for {len(missing_labels)} files, "
            f"first few: {missing_labels[:5]}"
        )
    if not examples:
        raise ValueError(f"No usable MDD-5k examples found in {dialogue_dir}")
    return examples


def split_mdd_examples(examples: list[Example]) -> tuple[list[Example], list[Example], dict[str, Any]]:
    indices = list(range(len(examples)))
    primary_labels = [example.gold_labels[0] for example in examples]
    train_idx, test_idx = train_test_split(
        indices,
        test_size=MDD_TEST_SIZE,
        random_state=MDD_RANDOM_SEED,
        stratify=primary_labels,
    )
    train_examples = [examples[idx] for idx in sorted(train_idx)]
    test_examples = [examples[idx] for idx in sorted(test_idx)]
    split_meta = {
        "strategy": "deterministic_stratified_primary_parent",
        "seed": MDD_RANDOM_SEED,
        "test_size": MDD_TEST_SIZE,
        "stratify_label": "gold_labels[0]",
    }
    return train_examples, test_examples, split_meta


def build_multilabel_targets(labels: list[list[str]]) -> tuple[np.ndarray, MultiLabelBinarizer]:
    mlb = MultiLabelBinarizer(classes=list(PAPER_12_CLASSES))
    return mlb.fit_transform(labels), mlb


def fit_model(train_examples: list[Example]) -> tuple[TfidfVectorizer, OneVsRestClassifier, MultiLabelBinarizer]:
    vectorizer = TfidfVectorizer(
        max_features=10_000,
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
        analyzer="char_wb",
        sublinear_tf=True,
    )
    x_train = vectorizer.fit_transform(example.text for example in train_examples)
    y_train, mlb = build_multilabel_targets([example.gold_labels for example in train_examples])

    classifier = OneVsRestClassifier(
        LogisticRegression(
            max_iter=2000,
            solver="lbfgs",
            class_weight="balanced",
        ),
        n_jobs=-1,
    )
    classifier.fit(x_train, y_train)
    return vectorizer, classifier, mlb


def predict_examples(
    vectorizer: TfidfVectorizer,
    classifier: OneVsRestClassifier,
    mlb: MultiLabelBinarizer,
    test_examples: list[Example],
) -> list[dict[str, Any]]:
    x_test = vectorizer.transform(example.text for example in test_examples)
    proba = classifier.predict_proba(x_test)
    classes = list(mlb.classes_)

    records: list[dict[str, Any]] = []
    for idx, example in enumerate(test_examples):
        scores = proba[idx]
        ranked_indices = np.argsort(-scores)
        ranked_codes = [classes[class_idx] for class_idx in ranked_indices]
        ranked_scores = [round(float(scores[class_idx]), 6) for class_idx in ranked_indices]

        primary = ranked_codes[0]
        comorbid: list[str] = []
        if len(ranked_codes) > 1 and ranked_scores[1] >= COMORBID_THRESHOLD:
            comorbid.append(ranked_codes[1])

        records.append(
            {
                "case_id": example.case_id,
                "dataset": example.dataset,
                "gold_diagnoses": example.gold_labels,
                "gold_label_code_raw": example.raw_label_code,
                "primary_diagnosis": primary,
                "comorbid_diagnoses": comorbid,
                "ranked_codes": ranked_codes,
                "proba_scores": ranked_scores,
            }
        )

    return records


def compute_metrics(test_examples: list[Example], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    cases = [
        {
            "case_id": example.case_id,
            "DiagnosisCode": example.raw_label_code,
            "_pred_idx": idx,
        }
        for idx, example in enumerate(test_examples)
    ]

    def get_prediction(case: dict[str, Any]) -> list[str]:
        record = predictions[case["_pred_idx"]]
        return [record["primary_diagnosis"], *record["comorbid_diagnoses"]]

    return compute_table4_metrics(cases, get_prediction)


def save_predictions(
    train_dataset: str,
    test_dataset: str,
    predictions: list[dict[str, Any]],
) -> Path:
    combo_dir = PREDICTIONS_ROOT / f"train_{train_dataset}_test_{test_dataset}"
    combo_dir.mkdir(parents=True, exist_ok=True)
    path = combo_dir / "predictions.jsonl"
    with open(path, "w", encoding="utf-8") as handle:
        for record in predictions:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def dataset_summary(examples: list[Example]) -> dict[str, Any]:
    label_counts = {label: 0 for label in PAPER_12_CLASSES}
    for example in examples:
        for label in example.gold_labels:
            label_counts[label] += 1
    return {
        "size": len(examples),
        "label_counts": label_counts,
    }


def format_metric(value: float | int | None) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.4f}"


def print_matrix(results: dict[str, dict[str, Any]]) -> None:
    train_datasets = ["lingxidiag16k", "mdd5k"]
    test_datasets = ["lingxidiag16k", "mdd5k"]

    print()
    print("=" * 84)
    print("Cross-dataset TF-IDF+LR degradation matrix (Overall)")
    print("=" * 84)
    print(f"{'Train/Test':<24}{'LingxiDiag-16K':>18}{'MDD-5k':>18}")
    for train_dataset in train_datasets:
        combo_lingxi = results[f"{train_dataset}__lingxidiag16k"]["metrics"]["Overall"]
        combo_mdd = results[f"{train_dataset}__mdd5k"]["metrics"]["Overall"]
        label = "LingxiDiag-16K" if train_dataset == "lingxidiag16k" else "MDD-5k"
        print(f"{label:<24}{format_metric(combo_lingxi):>18}{format_metric(combo_mdd):>18}")

    print()
    print("Per-combination detail")
    print("-" * 84)
    for combo_key, payload in results.items():
        metrics = payload["metrics"]
        print(
            f"{combo_key:<28} "
            f"Overall={format_metric(metrics['Overall'])}  "
            f"Top1={format_metric(metrics['12class_Top1'])}  "
            f"F1_macro={format_metric(metrics['12class_F1_macro'])}  "
            f"n={int(metrics['12class_n'])}"
        )


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    PREDICTIONS_ROOT.mkdir(parents=True, exist_ok=True)

    print("=" * 84)
    print("TF-IDF + Logistic Regression cross-dataset degradation")
    print("=" * 84)

    print("\n[1/5] Loading LingxiDiag-16K splits ...")
    lingxi_train = load_lingxi_examples(LINGXI_TRAIN_PATH, "train")
    lingxi_test = load_lingxi_examples(LINGXI_TEST_PATH, "validation")
    print(f"  Lingxi train: {len(lingxi_train)}")
    print(f"  Lingxi test : {len(lingxi_test)}")

    print("\n[2/5] Loading MDD-5k pool and creating deterministic split ...")
    mdd_pool = load_mdd_pool(MDD_ROOT)
    mdd_train, mdd_test, mdd_split_meta = split_mdd_examples(mdd_pool)
    print(f"  MDD pool : {len(mdd_pool)}")
    print(f"  MDD train: {len(mdd_train)}")
    print(f"  MDD test : {len(mdd_test)}")
    print(
        "  Split    : "
        f"{mdd_split_meta['strategy']} seed={mdd_split_meta['seed']} "
        f"test_size={mdd_split_meta['test_size']}"
    )

    dataset_train_splits = {
        "lingxidiag16k": lingxi_train,
        "mdd5k": mdd_train,
    }
    dataset_test_splits = {
        "lingxidiag16k": lingxi_test,
        "mdd5k": mdd_test,
    }

    print("\n[3/5] Fitting one model per training dataset ...")
    trained_models: dict[str, tuple[TfidfVectorizer, OneVsRestClassifier, MultiLabelBinarizer]] = {}
    for dataset_name, train_examples in dataset_train_splits.items():
        vectorizer, classifier, mlb = fit_model(train_examples)
        trained_models[dataset_name] = (vectorizer, classifier, mlb)
        print(
            f"  {dataset_name:<14} train_n={len(train_examples):>5} "
            f"vocab={len(vectorizer.vocabulary_):>5}"
        )

    print("\n[4/5] Evaluating 2x2 train/test combinations ...")
    results: dict[str, dict[str, Any]] = {}
    for train_dataset, model_bundle in trained_models.items():
        vectorizer, classifier, mlb = model_bundle
        for test_dataset, test_examples in dataset_test_splits.items():
            combo_key = f"{train_dataset}__{test_dataset}"
            predictions = predict_examples(vectorizer, classifier, mlb, test_examples)
            metrics = compute_metrics(test_examples, predictions)
            predictions_path = save_predictions(train_dataset, test_dataset, predictions)
            results[combo_key] = {
                "train_dataset": train_dataset,
                "test_dataset": test_dataset,
                "metrics": metrics,
                "predictions_path": str(predictions_path.relative_to(ROOT)),
            }
            print(
                f"  {combo_key:<24} "
                f"Overall={format_metric(metrics['Overall'])} "
                f"Top1={format_metric(metrics['12class_Top1'])} "
                f"F1_macro={format_metric(metrics['12class_F1_macro'])}"
            )

    matrix_overall = {
        train_dataset: {
            test_dataset: results[f"{train_dataset}__{test_dataset}"]["metrics"]["Overall"]
            for test_dataset in dataset_test_splits
        }
        for train_dataset in dataset_train_splits
    }
    matrix_top1 = {
        train_dataset: {
            test_dataset: results[f"{train_dataset}__{test_dataset}"]["metrics"]["12class_Top1"]
            for test_dataset in dataset_test_splits
        }
        for train_dataset in dataset_train_splits
    }
    matrix_macro_f1 = {
        train_dataset: {
            test_dataset: results[f"{train_dataset}__{test_dataset}"]["metrics"]["12class_F1_macro"]
            for test_dataset in dataset_test_splits
        }
        for train_dataset in dataset_train_splits
    }
    degradation = {
        "lingxidiag16k_in_to_mdd5k_out_overall_drop": (
            matrix_overall["lingxidiag16k"]["lingxidiag16k"]
            - matrix_overall["lingxidiag16k"]["mdd5k"]
        ),
        "mdd5k_in_to_lingxidiag16k_out_overall_drop": (
            matrix_overall["mdd5k"]["mdd5k"]
            - matrix_overall["mdd5k"]["lingxidiag16k"]
        ),
    }

    payload = {
        "paper_classes": list(PAPER_12_CLASSES),
        "model": {
            "tfidf": {
                "max_features": 10_000,
                "ngram_range": [1, 2],
                "min_df": 2,
                "max_df": 0.95,
                "analyzer": "char_wb",
                "sublinear_tf": True,
            },
            "classifier": {
                "type": "OneVsRestClassifier(LogisticRegression)",
                "class_weight": "balanced",
                "max_iter": 2000,
                "solver": "lbfgs",
                "comorbid_threshold": COMORBID_THRESHOLD,
            },
        },
        "split_notes": {
            "lingxidiag16k": {
                "train_split": str(LINGXI_TRAIN_PATH.relative_to(ROOT)),
                "test_split": str(LINGXI_TEST_PATH.relative_to(ROOT)),
            },
            "mdd5k": {
                "source_root": str(MDD_ROOT.relative_to(ROOT)),
                **mdd_split_meta,
            },
        },
        "datasets": {
            "lingxidiag16k_train": dataset_summary(lingxi_train),
            "lingxidiag16k_test": dataset_summary(lingxi_test),
            "mdd5k_train": dataset_summary(mdd_train),
            "mdd5k_test": dataset_summary(mdd_test),
        },
        "results": results,
        "matrix_overall": matrix_overall,
        "matrix_12class_top1": matrix_top1,
        "matrix_12class_f1_macro": matrix_macro_f1,
        "degradation_overall": degradation,
    }

    with open(RESULTS_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    print("\n[5/5] Saved results")
    print(f"  Summary    : {RESULTS_PATH.relative_to(ROOT)}")
    print(f"  Predictions: {PREDICTIONS_ROOT.relative_to(ROOT)}")
    print_matrix(results)


if __name__ == "__main__":
    main()
