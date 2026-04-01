"""Tests for somatization benchmark schema, baselines, and review tooling."""
from __future__ import annotations

import json

import pytest

from culturedx.core.models import ClinicalCase, SymptomSpan, Turn
from culturedx.evidence.somatization_benchmark import (
    CurrentSomatizationModuleBaseline,
    ExactOntologySomatizationBaseline,
    FuzzyOntologySomatizationBaseline,
    build_adjudication_records,
    evaluate_somatization_predictions,
    export_adjudication_records,
    generate_review_queue,
    save_review_queue,
)
from culturedx.evidence.somatization_dataset import (
    SomatizationBenchmarkExample,
    build_annotation_examples_from_spans,
    export_somatization_dataset_csv,
    import_somatization_dataset_csv,
    load_somatization_dataset,
    save_somatization_dataset,
)


FIXTURE_PATH = "tests/fixtures/somatization_benchmark_demo.jsonl"


class TestSomatizationDataset:
    def test_load_demo_fixture(self):
        dataset = load_somatization_dataset(FIXTURE_PATH)
        assert len(dataset.examples) == 6
        assert dataset.examples[0].example_id == "demo-001"

    def test_split_filter(self):
        dataset = load_somatization_dataset(FIXTURE_PATH, split="gold")
        assert len(dataset.examples) == 3
        assert all(example.split == "gold" for example in dataset.examples)

    def test_invalid_schema_raises(self, tmp_path):
        bad = tmp_path / "bad.jsonl"
        bad.write_text(
            json.dumps(
                {
                    "text": "",
                    "expression_type": "direct_symptom",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError):
            load_somatization_dataset(bad)

    def test_duplicate_example_ids_raise(self, tmp_path):
        bad = tmp_path / "dupe.jsonl"
        payload = {
            "example_id": "dup-001",
            "text": "我最近胸闷。",
            "span_text": "胸闷",
            "span_start": 3,
            "span_end": 5,
            "expression_type": "somatized_expression",
            "source_dataset": "demo",
            "source_id": "case-x",
            "language": "zh",
        }
        bad.write_text(
            json.dumps(payload, ensure_ascii=False)
            + "\n"
            + json.dumps(payload, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="duplicate somatization example_id"):
            load_somatization_dataset(bad)

    def test_round_trip_csv_and_jsonl(self, tmp_path):
        dataset = load_somatization_dataset(FIXTURE_PATH)
        csv_path = tmp_path / "demo.csv"
        jsonl_path = tmp_path / "demo.jsonl"
        export_somatization_dataset_csv(dataset, csv_path)
        imported = import_somatization_dataset_csv(csv_path)
        save_somatization_dataset(imported, jsonl_path)
        reloaded = load_somatization_dataset(jsonl_path)
        assert len(reloaded.examples) == len(dataset.examples)
        assert reloaded.examples[0].example_id == dataset.examples[0].example_id

    def test_build_annotation_examples_from_spans(self):
        case = ClinicalCase(
            case_id="anno-001",
            transcript=[Turn(speaker="patient", text="我最近胸口发闷，睡不着。", turn_id=1)],
            language="zh",
            dataset="demo",
        )
        spans = [
            SymptomSpan(text="胸口发闷", turn_id=1, symptom_type="somatic", is_somatic=True),
            SymptomSpan(text="睡不着", turn_id=1, symptom_type="somatic", is_somatic=True),
        ]
        dataset = build_annotation_examples_from_spans(case, spans)
        assert len(dataset.examples) == 2
        assert dataset.examples[0].split == "annotation_pool"
        assert dataset.examples[0].source_id == "anno-001"

    def test_build_annotation_examples_preserves_expression_type(self):
        case = ClinicalCase(
            case_id="anno-002",
            transcript=[Turn(speaker="patient", text="我没有胸口发闷。", turn_id=1)],
            language="zh",
            dataset="demo",
        )
        spans = [
            SymptomSpan(
                text="胸口发闷",
                turn_id=1,
                symptom_type="somatic",
                is_somatic=True,
                expression_type="negated",
                normalized_concept="胸闷",
                candidate_criteria=["F41.1.B2"],
            ),
        ]
        dataset = build_annotation_examples_from_spans(case, spans)
        assert dataset.examples[0].expression_type == "negated"
        assert dataset.examples[0].normalized_concept == "胸闷"


class TestSomatizationBaselines:
    def test_exact_baseline_hits_exact_concept(self):
        dataset = load_somatization_dataset(FIXTURE_PATH)
        example = next(ex for ex in dataset.examples if ex.example_id == "demo-003")
        prediction = ExactOntologySomatizationBaseline().predict(example)
        assert prediction.predicted_concept == "胸闷"
        assert "F41.1.B2" in prediction.candidate_criterion_ids

    def test_fuzzy_baseline_recovers_non_exact_surface_form(self):
        dataset = load_somatization_dataset(FIXTURE_PATH)
        example = next(ex for ex in dataset.examples if ex.example_id == "demo-001")
        prediction = FuzzyOntologySomatizationBaseline(top_k=3).predict(example)
        assert prediction.predicted_concept == "胸口发闷"
        assert "胸口发闷" in prediction.candidate_concepts

    def test_current_mapper_emits_structured_fields(self):
        dataset = load_somatization_dataset(FIXTURE_PATH)
        example = next(ex for ex in dataset.examples if ex.example_id == "demo-001")
        prediction = CurrentSomatizationModuleBaseline().predict(example)
        assert prediction.predicted_concept == "胸口发闷"
        assert prediction.confidence is not None
        assert prediction.rationale

    def test_evaluate_predictions_returns_expected_metrics(self):
        dataset = load_somatization_dataset(FIXTURE_PATH)
        predictions = FuzzyOntologySomatizationBaseline(top_k=3).predict_all(dataset.examples)
        metrics = evaluate_somatization_predictions(dataset, predictions, top_k=3)
        assert metrics["num_examples"] == 6
        assert "exact_concept_accuracy" in metrics
        assert "label_metrics" in metrics
        assert "error_records" in metrics


class TestSomatizationReviewTools:
    def test_review_queue_prioritizes_disagreement(self):
        dataset = load_somatization_dataset(FIXTURE_PATH)
        exact = ExactOntologySomatizationBaseline().predict_all(dataset.examples)
        fuzzy = FuzzyOntologySomatizationBaseline(top_k=3).predict_all(dataset.examples)
        queue = generate_review_queue(
            dataset,
            {
                "exact": exact,
                "fuzzy": fuzzy,
            },
            production_failures={"demo-001": ["somatization_abstain"]},
        )
        assert queue
        assert queue[0].review_reasons
        assert any(item.example_id == "demo-001" for item in queue)

    def test_review_queue_export_jsonl_and_csv(self, tmp_path):
        dataset = load_somatization_dataset(FIXTURE_PATH)
        fuzzy = FuzzyOntologySomatizationBaseline(top_k=3).predict_all(dataset.examples)
        queue = generate_review_queue(dataset, {"fuzzy": fuzzy})
        jsonl_path = tmp_path / "review_queue.jsonl"
        csv_path = tmp_path / "review_queue.csv"
        save_review_queue(queue, jsonl_path)
        save_review_queue(queue, csv_path)
        assert jsonl_path.read_text(encoding="utf-8").strip()
        assert csv_path.read_text(encoding="utf-8").splitlines()[0].startswith("example_id,")

    def test_adjudication_export_jsonl_and_csv(self, tmp_path):
        dataset = load_somatization_dataset(FIXTURE_PATH)
        predictions = FuzzyOntologySomatizationBaseline(top_k=3).predict_all(dataset.examples)
        records = build_adjudication_records(dataset, predictions)
        jsonl_path = tmp_path / "adjudication.jsonl"
        csv_path = tmp_path / "adjudication.csv"
        export_adjudication_records(records, jsonl_path)
        export_adjudication_records(records, csv_path)
        assert jsonl_path.exists()
        assert csv_path.exists()
        assert jsonl_path.read_text(encoding="utf-8").strip()
        assert csv_path.read_text(encoding="utf-8").splitlines()[0].startswith("example_id,")

    def test_loader_generates_deterministic_example_id_when_missing(self, tmp_path):
        path = tmp_path / "missing_id.jsonl"
        path.write_text(
            json.dumps(
                {
                    "text": "我最近胸闷。",
                    "span_text": "胸闷",
                    "span_start": 3,
                    "span_end": 5,
                    "normalized_concept": "胸闷",
                    "candidate_criterion_ids": ["F41.1.B2"],
                    "expression_type": "somatized_expression",
                    "source_dataset": "demo",
                    "source_id": "case-x",
                    "language": "zh",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        dataset = load_somatization_dataset(path)
        assert dataset.examples[0].example_id.startswith("demo-")
