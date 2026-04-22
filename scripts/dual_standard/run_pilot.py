#!/usr/bin/env python3
"""
Dual-standard pilot: run ICD-10, DSM-5, and Both modes on N cases.
Produces comparison report with Top-1, agreement rate, and disagreement examples.
"""
from __future__ import annotations

import argparse
import itertools
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

CLASSES_12 = ["F20", "F31", "F32", "F39", "F41", "F42", "F43", "F45", "F51", "F98", "Z71", "Others"]
MODE_OVERLAYS = {
    "icd10": Path("configs/overlays/standard_icd10.yaml"),
    "dsm5": Path("configs/overlays/standard_dsm5.yaml"),
    "both": Path("configs/overlays/standard_both.yaml"),
}
MAX_DISAGREEMENT_EXAMPLES = 20


def paper_parent(code: str | None) -> str:
    if not code:
        return "Others"
    parent = str(code).split(".")[0].upper()
    return parent if parent in CLASSES_12 else "Others"


def is_abstain(prediction: dict[str, Any]) -> bool:
    decision = str(prediction.get("decision", "")).strip().lower()
    return decision == "abstain" or not prediction.get("primary_diagnosis")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def stream_command(cmd: list[str], cwd: Path, log_path: Path) -> int:
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        try:
            for line in process.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                log_file.write(line)
            return process.wait()
        except KeyboardInterrupt:
            process.terminate()
            process.wait(timeout=10)
            raise


def find_run_artifact(run_dir: Path, artifact_name: str) -> Path | None:
    direct = run_dir / artifact_name
    if direct.exists():
        return direct
    matches = sorted(run_dir.rglob(artifact_name))
    return matches[0] if matches else None


def run_mode(
    mode_name: str,
    overlay_path: Path,
    dataset: str,
    data_path: str,
    n: int,
    seed: int,
    out_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    """Run culturedx pipeline with a specific overlay and return predictions."""
    mode_dir = out_dir / f"mode_{mode_name}"
    run_name = f"pilot_{mode_name}"
    run_dir = mode_dir / run_name
    mode_dir.mkdir(parents=True, exist_ok=True)
    log_path = mode_dir / "run.log"

    if run_dir.exists():
        shutil.rmtree(run_dir)

    cmd = [
        "uv",
        "run",
        "culturedx",
        "run",
        "-c",
        "configs/base.yaml",
        "-c",
        "configs/vllm_awq.yaml",
        "-c",
        "configs/v2.4_final.yaml",
        "-c",
        str(overlay_path),
        "-d",
        dataset,
        "--data-path",
        data_path,
        "-n",
        str(n),
        "--seed",
        str(seed),
        "--run-name",
        run_name,
        "-o",
        str(mode_dir),
    ]

    print(f"\n{'=' * 60}")
    print(f"Running mode: {mode_name}")
    print(f"Overlay: {overlay_path}")
    print(f"Run dir: {run_dir}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'=' * 60}\n")

    exit_code = stream_command(cmd, cwd=repo_root, log_path=log_path)
    result: dict[str, Any] = {
        "mode": mode_name,
        "overlay_path": str(overlay_path),
        "run_dir": str(run_dir),
        "log_path": str(log_path),
        "command": cmd,
        "exit_code": exit_code,
    }
    if exit_code != 0:
        result["error"] = f"mode {mode_name} failed with exit code {exit_code}"
        return result

    pred_path = find_run_artifact(run_dir, "predictions.jsonl")
    case_selection_path = find_run_artifact(run_dir, "case_selection.json")
    metrics_summary_path = find_run_artifact(run_dir, "metrics_summary.json")

    if pred_path is None:
        result["error"] = f"No predictions.jsonl found for {mode_name}"
        return result
    if case_selection_path is None:
        result["error"] = f"No case_selection.json found for {mode_name}"
        return result

    preds = load_jsonl(pred_path)
    case_selection = load_json(case_selection_path)
    metrics_summary = load_json(metrics_summary_path) if metrics_summary_path else None

    result.update(
        {
            "predictions_path": str(pred_path),
            "case_selection_path": str(case_selection_path),
            "metrics_summary_path": str(metrics_summary_path) if metrics_summary_path else None,
            "predictions": preds,
            "case_ids": [str(case_id) for case_id in case_selection.get("case_ids", [])],
            "metrics_summary": metrics_summary,
        }
    )
    return result


def compute_metrics(preds: list[dict[str, Any]], mode_name: str) -> dict[str, Any]:
    """Compute Top-1 and per-class stats."""
    correct = 0
    total = 0
    abstain_count = 0
    class_correct: Counter[str] = Counter()
    class_total: Counter[str] = Counter()
    distinct_primary_classes: set[str] = set()

    for prediction in preds:
        golds = [paper_parent(gold) for gold in prediction.get("gold_diagnoses", [])]
        pred_primary = paper_parent(prediction.get("primary_diagnosis"))
        gold = golds[0] if golds else "Others"

        total += 1
        if is_abstain(prediction):
            abstain_count += 1
        else:
            distinct_primary_classes.add(pred_primary)
        if pred_primary == gold:
            correct += 1
            class_correct[gold] += 1
        class_total[gold] += 1

    top1 = correct / max(total, 1)
    abstain_rate = abstain_count / max(total, 1)
    return {
        "mode": mode_name,
        "top1": round(top1, 4),
        "n": total,
        "correct": correct,
        "abstain_count": abstain_count,
        "abstain_rate": round(abstain_rate, 4),
        "distinct_primary_classes": sorted(distinct_primary_classes),
        "distinct_primary_class_count": len(distinct_primary_classes),
        "per_class": {
            class_name: {
                "correct": class_correct[class_name],
                "total": class_total[class_name],
                "recall": round(class_correct[class_name] / max(class_total[class_name], 1), 3),
            }
            for class_name in CLASSES_12
            if class_total[class_name] > 0
        },
        "_raw": {
            "top1": top1,
            "abstain_rate": abstain_rate,
        },
    }


def compute_agreement(
    preds_a: list[dict[str, Any]],
    preds_b: list[dict[str, Any]],
    name_a: str,
    name_b: str,
) -> dict[str, Any]:
    """Compute agreement rate on paper-parent between two mode outputs."""
    map_a = {prediction["case_id"]: paper_parent(prediction.get("primary_diagnosis")) for prediction in preds_a}
    map_b = {prediction["case_id"]: paper_parent(prediction.get("primary_diagnosis")) for prediction in preds_b}
    common = sorted(set(map_a) & set(map_b))
    agree = sum(1 for case_id in common if map_a[case_id] == map_b[case_id])
    disagree = len(common) - agree
    return {
        "pair": f"{name_a}_vs_{name_b}",
        "mode_a": name_a,
        "mode_b": name_b,
        "common_cases": len(common),
        "agree": agree,
        "disagree": disagree,
        "rate": round(agree / max(len(common), 1), 4),
    }


def build_disagreement_examples(
    mode_predictions: dict[str, list[dict[str, Any]]],
    max_examples: int = MAX_DISAGREEMENT_EXAMPLES,
) -> list[dict[str, Any]]:
    if not mode_predictions:
        return []

    by_mode_case = {
        mode_name: {prediction["case_id"]: prediction for prediction in predictions}
        for mode_name, predictions in mode_predictions.items()
    }
    common_case_ids = set.intersection(*(set(case_map) for case_map in by_mode_case.values()))
    if not common_case_ids:
        return []

    reference_mode = next(iter(mode_predictions))
    ordered_case_ids = [
        prediction["case_id"]
        for prediction in mode_predictions[reference_mode]
        if prediction["case_id"] in common_case_ids
    ]

    examples: list[dict[str, Any]] = []
    for case_id in ordered_case_ids:
        parent_by_mode = {
            mode_name: paper_parent(by_mode_case[mode_name][case_id].get("primary_diagnosis"))
            for mode_name in mode_predictions
        }
        if len(set(parent_by_mode.values())) <= 1:
            continue

        reference_prediction = by_mode_case[reference_mode][case_id]
        example = {
            "case_id": case_id,
            "gold_parent": paper_parent((reference_prediction.get("gold_diagnoses") or [None])[0]),
            "distinct_predictions": sorted(set(parent_by_mode.values())),
            "disagreement_pairs": [
                f"{mode_a}_vs_{mode_b}"
                for mode_a, mode_b in itertools.combinations(mode_predictions, 2)
                if parent_by_mode[mode_a] != parent_by_mode[mode_b]
            ],
            "predictions": {
                mode_name: {
                    "paper_parent": parent_by_mode[mode_name],
                    "primary_diagnosis": by_mode_case[mode_name][case_id].get("primary_diagnosis"),
                    "primary_diagnosis_dsm5": by_mode_case[mode_name][case_id].get("primary_diagnosis_dsm5"),
                    "decision": by_mode_case[mode_name][case_id].get("decision"),
                    "confidence": by_mode_case[mode_name][case_id].get("confidence"),
                }
                for mode_name in mode_predictions
            },
        }
        examples.append(example)
        if len(examples) >= max_examples:
            break

    return examples


def build_sanity_checks(metrics_by_mode: dict[str, dict[str, Any]]) -> dict[str, Any]:
    checks_by_mode: dict[str, dict[str, Any]] = {}
    all_passed = True
    for mode_name, metrics in metrics_by_mode.items():
        checks = {
            "top1_gt_0_20": metrics["_raw"]["top1"] > 0.20,
            "abstain_le_0_50": metrics["_raw"]["abstain_rate"] <= 0.50,
            "distinct_primary_classes_ge_3": metrics["distinct_primary_class_count"] >= 3,
        }
        passed = all(checks.values())
        all_passed = all_passed and passed
        checks_by_mode[mode_name] = {
            "passed": passed,
            "checks": checks,
            "observed": {
                "top1": metrics["top1"],
                "abstain_rate": metrics["abstain_rate"],
                "distinct_primary_class_count": metrics["distinct_primary_class_count"],
            },
        }
    return {
        "all_passed": all_passed,
        "per_mode": checks_by_mode,
    }


def strip_internal_metric_fields(metrics_by_mode: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    cleaned: dict[str, dict[str, Any]] = {}
    for mode_name, metrics in metrics_by_mode.items():
        cleaned[mode_name] = {key: value for key, value in metrics.items() if key != "_raw"}
    return cleaned


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, help="Dataset name, e.g. lingxidiag16k")
    parser.add_argument("--data-path", required=True, help="Path to dataset root")
    parser.add_argument("--n", type=int, default=100, help="Number of cases to run per mode")
    parser.add_argument("--seed", type=int, default=42, help="Seed passed to culturedx run")
    parser.add_argument("--out-dir", required=True, help="Directory to write pilot outputs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    out_dir = (repo_root / args.out_dir).resolve() if not Path(args.out_dir).is_absolute() else Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    mode_results: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    reference_case_ids: list[str] | None = None
    same_case_assertions: dict[str, Any] = {
        "passed": True,
        "reference_mode": None,
        "mismatches": [],
    }

    for mode_name, overlay_rel_path in MODE_OVERLAYS.items():
        overlay_path = (repo_root / overlay_rel_path).resolve()
        result = run_mode(
            mode_name=mode_name,
            overlay_path=overlay_path,
            dataset=args.dataset,
            data_path=args.data_path,
            n=args.n,
            seed=args.seed,
            out_dir=out_dir,
            repo_root=repo_root,
        )
        if result.get("error"):
            failures.append(
                {
                    "mode": mode_name,
                    "error": result["error"],
                    "exit_code": result.get("exit_code"),
                    "log_path": result.get("log_path"),
                    "run_dir": result.get("run_dir"),
                }
            )
            continue

        case_ids = result.get("case_ids", [])
        if reference_case_ids is None:
            reference_case_ids = case_ids
            same_case_assertions["reference_mode"] = mode_name
        elif case_ids != reference_case_ids:
            same_case_assertions["passed"] = False
            same_case_assertions["mismatches"].append(
                {
                    "mode": mode_name,
                    "expected_case_ids": reference_case_ids,
                    "observed_case_ids": case_ids,
                }
            )
        mode_results[mode_name] = result

    mode_predictions = {
        mode_name: result["predictions"]
        for mode_name, result in mode_results.items()
    }
    metrics_by_mode = {
        mode_name: compute_metrics(predictions, mode_name)
        for mode_name, predictions in mode_predictions.items()
    }
    agreements = [
        compute_agreement(mode_predictions[left], mode_predictions[right], left, right)
        for left, right in itertools.combinations(mode_predictions, 2)
    ]
    disagreement_examples = build_disagreement_examples(mode_predictions)
    sanity = build_sanity_checks(metrics_by_mode)

    report = {
        "dataset": args.dataset,
        "data_path": args.data_path,
        "n": args.n,
        "seed": args.seed,
        "modes": {
            mode_name: {
                "overlay_path": result["overlay_path"],
                "run_dir": result["run_dir"],
                "predictions_path": result["predictions_path"],
                "case_selection_path": result["case_selection_path"],
                "metrics_summary_path": result["metrics_summary_path"],
                "log_path": result["log_path"],
                "exit_code": result["exit_code"],
            }
            for mode_name, result in mode_results.items()
        },
        "per_mode_metrics": strip_internal_metric_fields(metrics_by_mode),
        "pairwise_agreement": agreements,
        "disagreement_examples": disagreement_examples,
        "sanity_assertions": {
            "same_case_selection": same_case_assertions,
            **sanity,
        },
        "failures": failures,
    }

    report_path = out_dir / "pilot_comparison.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nPilot comparison saved to", report_path)
    for mode_name, metrics in strip_internal_metric_fields(metrics_by_mode).items():
        print(
            f"  {mode_name:>5}: top1={metrics['top1']:.4f} "
            f"abstain={metrics['abstain_rate']:.4f} "
            f"distinct_classes={metrics['distinct_primary_class_count']}"
        )
    for agreement in agreements:
        print(
            f"  {agreement['pair']}: rate={agreement['rate']:.4f} "
            f"({agreement['agree']}/{agreement['common_cases']})"
        )

    should_fail = bool(failures) or not same_case_assertions["passed"] or not sanity["all_passed"]
    return 1 if should_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
