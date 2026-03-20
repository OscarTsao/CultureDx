from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from culturedx.eval.calibration import compute_calibration
from culturedx.eval.statistical_tests import mcnemar_test


ROOT = Path(__file__).resolve().parents[1]
SWEEPS_DIR = ROOT / "outputs" / "sweeps"
TABLE_WIDTH = 100
PRIMARY_TARGETS = {"F32", "F41"}


@dataclass(frozen=True)
class DatasetSpec:
    key: str
    label: str
    baseline_default: Path
    baseline_pattern: str
    v10_pattern: str


@dataclass(frozen=True)
class PredictionRecord:
    case_id: str
    primary_diagnosis: str | None
    confidence: float | None
    decision: str | None


@dataclass(frozen=True)
class SweepData:
    dataset: DatasetSpec
    sweep_dir: Path
    case_order: list[str]
    gold_map: dict[str, list[str]]
    mode_predictions: dict[str, dict[str, PredictionRecord]]


@dataclass(frozen=True)
class SystemMetrics:
    top1_accuracy: float
    abstention_rate: float
    f41_to_f32_rate: float | None
    ece: float | None
    correct_flags: list[bool]
    supports: dict[str, int]
    recalls: dict[str, float | None]


@dataclass(frozen=True)
class ChangeRecord:
    case_id: str
    gold_label: str
    baseline_prediction: str
    baseline_correct: bool
    v10_prediction: str
    v10_correct: bool
    status: str


DATASETS: dict[str, DatasetSpec] = {
    "lingxi": DatasetSpec(
        key="lingxi",
        label="LingxiDiag",
        baseline_default=SWEEPS_DIR / "lingxidiag_3mode_crossval_20260320_195057",
        baseline_pattern="lingxidiag_3mode_crossval_*",
        v10_pattern="v10_lingxidiag*",
    ),
    "mdd": DatasetSpec(
        key="mdd",
        label="MDD-5k",
        baseline_default=SWEEPS_DIR / "n200_3mode_20260320_131920",
        baseline_pattern="n200_3mode_*",
        v10_pattern="v10_mdd5k*",
    ),
}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def parent_code(code: str | None) -> str | None:
    return code.split(".", 1)[0] if code else None


def gold_parent_codes(labels: Iterable[str]) -> set[str]:
    parents: set[str] = set()
    for label in labels:
        parent = parent_code(label)
        if parent is not None:
            parents.add(parent)
    return parents


def gold_primary(labels: Sequence[str]) -> str | None:
    return parent_code(labels[0]) if labels else None


def is_abstention(prediction: PredictionRecord | None) -> bool:
    return (
        prediction is None
        or prediction.primary_diagnosis is None
        or prediction.decision == "abstain"
    )


def prediction_parent(prediction: PredictionRecord | None) -> str | None:
    return None if is_abstention(prediction) else parent_code(prediction.primary_diagnosis)


def prediction_label(prediction: PredictionRecord | None) -> str:
    return "ABSTAIN" if is_abstention(prediction) else prediction.primary_diagnosis or "ABSTAIN"


def top1_correct(prediction: PredictionRecord | None, gold_labels: Sequence[str]) -> bool:
    pred_parent = prediction_parent(prediction)
    return pred_parent is not None and pred_parent in gold_parent_codes(gold_labels)


def rel_path(path: Path | None) -> str:
    if path is None:
        return "N/A"
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def warn(message: str) -> None:
    print(f"Warning: {message}")


def hr(char: str = "═", width: int = TABLE_WIDTH) -> None:
    print(char * width)


def section(title: str) -> None:
    print()
    hr("═")
    print(f"  {title}")
    hr("═")


def subsection(title: str) -> None:
    print()
    hr("─", 80)
    print(f"  {title}")
    hr("─", 80)


def print_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    right_align: set[int] | None = None,
) -> None:
    right_align = right_align or set()
    matrix = [list(headers), *[list(row) for row in rows]]
    widths = [max(len(str(row[i])) for row in matrix) for i in range(len(headers))]

    def fmt_row(row: Sequence[str]) -> str:
        cells: list[str] = []
        for idx, value in enumerate(row):
            text = str(value)
            cells.append(text.rjust(widths[idx]) if idx in right_align else text.ljust(widths[idx]))
        return "│ " + " │ ".join(cells) + " │"

    top = "┌─" + "─┬─".join("─" * width for width in widths) + "─┐"
    mid = "├─" + "─┼─".join("─" * width for width in widths) + "─┤"
    bot = "└─" + "─┴─".join("─" * width for width in widths) + "─┘"
    print(f"  {top}")
    print(f"  {fmt_row(headers)}")
    print(f"  {mid}")
    for row in rows:
        print(f"  {fmt_row(row)}")
    print(f"  {bot}")


def fmt_pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:.1f}%"


def fmt_pp_delta(baseline: float | None, v10: float | None) -> str:
    return "N/A" if baseline is None or v10 is None else f"{(v10 - baseline) * 100:+.1f} pp"


def fmt_float(value: float | None, decimals: int = 3) -> str:
    return "N/A" if value is None else f"{value:.{decimals}f}"


def fmt_float_delta(baseline: float | None, v10: float | None) -> str:
    return "N/A" if baseline is None or v10 is None else f"{v10 - baseline:+.3f}"


def fmt_p_value(value: float) -> str:
    return "<1e-4" if value < 0.0001 else f"{value:.4f}"


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def as_path(value: str | None) -> Path | None:
    return Path(value).expanduser().resolve() if value else None


def find_latest_sweep(pattern: str) -> Path | None:
    candidates = [path for path in SWEEPS_DIR.glob(pattern) if path.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))


def resolve_dir(spec: DatasetSpec, kind: str, override: Path | None) -> Path | None:
    if override is not None:
        return override
    if kind == "baseline" and spec.baseline_default.is_dir():
        return spec.baseline_default
    pattern = spec.baseline_pattern if kind == "baseline" else spec.v10_pattern
    return find_latest_sweep(pattern)


def load_sweep(spec: DatasetSpec, sweep_dir: Path) -> SweepData:
    case_list = load_json(sweep_dir / "case_list.json")
    cases = case_list.get("cases", [])
    case_order = [str(case["case_id"]) for case in cases]
    gold_map = {
        str(case["case_id"]): [str(label) for label in case.get("diagnoses", [])]
        for case in cases
    }
    mode_predictions: dict[str, dict[str, PredictionRecord]] = {}
    for child in sorted(sweep_dir.iterdir()):
        if not child.is_dir() or not child.name.endswith("_no_evidence"):
            continue
        raw_path = child / "predictions.json"
        if not raw_path.is_file():
            continue
        raw = load_json(raw_path)
        mode = child.name.removesuffix("_no_evidence")
        mode_predictions[mode] = {
            str(entry["case_id"]): PredictionRecord(
                case_id=str(entry["case_id"]),
                primary_diagnosis=entry.get("primary_diagnosis"),
                confidence=entry.get("confidence"),
                decision=entry.get("decision"),
            )
            for entry in raw.get("predictions", [])
        }
    return SweepData(spec, sweep_dir, case_order, gold_map, mode_predictions)


def reconcile_cases(
    baseline: SweepData,
    v10: SweepData,
) -> tuple[list[str], dict[str, list[str]]]:
    baseline_ids = set(baseline.case_order)
    v10_ids = set(v10.case_order)
    shared = [case_id for case_id in baseline.case_order if case_id in v10_ids]
    if baseline_ids - v10_ids:
        warn(
            f"{baseline.dataset.label}: {len(baseline_ids - v10_ids)} baseline cases are "
            "missing in V10; using the shared subset."
        )
    if v10_ids - baseline_ids:
        warn(
            f"{baseline.dataset.label}: {len(v10_ids - baseline_ids)} V10 cases are missing "
            "in baseline; using the shared subset."
        )
    gold_map: dict[str, list[str]] = {}
    mismatches = 0
    for case_id in shared:
        base_gold = baseline.gold_map.get(case_id, [])
        v10_gold = v10.gold_map.get(case_id, [])
        if base_gold != v10_gold:
            mismatches += 1
        gold_map[case_id] = base_gold or v10_gold
    if mismatches:
        warn(
            f"{baseline.dataset.label}: {mismatches} shared cases have mismatched gold labels; "
            "baseline labels were used."
        )
    return shared, gold_map


def compute_metrics(
    case_order: Sequence[str],
    gold_map: dict[str, list[str]],
    predictions: dict[str, PredictionRecord],
    mode_name: str,
) -> SystemMetrics:
    correct_flags: list[bool] = []
    confidences: list[float] = []
    calibration_correct: list[bool] = []
    supports = {"F32": 0, "F41": 0, "others": 0}
    hits = {"F32": 0, "F41": 0, "others": 0}
    abstentions = 0
    f41_total = 0
    f41_to_f32 = 0

    for case_id in case_order:
        gold_labels = gold_map[case_id]
        primary_gold = gold_primary(gold_labels)
        prediction = predictions.get(case_id)
        pred_parent = prediction_parent(prediction)
        correct = top1_correct(prediction, gold_labels)
        correct_flags.append(correct)

        if is_abstention(prediction):
            abstentions += 1
        elif prediction is not None and prediction.confidence is not None:
            confidences.append(float(prediction.confidence))
            calibration_correct.append(correct)

        if primary_gold == "F32":
            supports["F32"] += 1
            hits["F32"] += int(pred_parent == "F32")
        elif primary_gold == "F41":
            supports["F41"] += 1
            hits["F41"] += int(pred_parent == "F41")
            f41_total += 1
            f41_to_f32 += int(pred_parent == "F32")
        else:
            supports["others"] += 1
            hits["others"] += int(pred_parent is not None and pred_parent not in PRIMARY_TARGETS)

    recalls = {
        group: (hits[group] / supports[group]) if supports[group] else None
        for group in supports
    }
    ece = None
    if confidences:
        ece = compute_calibration(confidences, calibration_correct, mode=mode_name).ece
    return SystemMetrics(
        top1_accuracy=sum(correct_flags) / len(case_order) if case_order else 0.0,
        abstention_rate=abstentions / len(case_order) if case_order else 0.0,
        f41_to_f32_rate=(f41_to_f32 / f41_total) if f41_total else None,
        ece=ece,
        correct_flags=correct_flags,
        supports=supports,
        recalls=recalls,
    )


def build_change_records(
    case_order: Sequence[str],
    gold_map: dict[str, list[str]],
    baseline_predictions: dict[str, PredictionRecord],
    v10_predictions: dict[str, PredictionRecord],
) -> list[ChangeRecord]:
    changes: list[ChangeRecord] = []
    for case_id in case_order:
        baseline_pred = baseline_predictions.get(case_id)
        v10_pred = v10_predictions.get(case_id)
        if prediction_label(baseline_pred) == prediction_label(v10_pred):
            continue
        gold_labels = gold_map[case_id]
        baseline_correct = top1_correct(baseline_pred, gold_labels)
        v10_correct = top1_correct(v10_pred, gold_labels)
        if not baseline_correct and v10_correct:
            status = "improved"
        elif baseline_correct and not v10_correct:
            status = "regressed"
        elif baseline_correct and v10_correct:
            status = "correct->correct"
        else:
            status = "wrong->wrong"
        changes.append(
            ChangeRecord(
                case_id=case_id,
                gold_label=", ".join(gold_labels) if gold_labels else "UNK",
                baseline_prediction=prediction_label(baseline_pred),
                baseline_correct=baseline_correct,
                v10_prediction=prediction_label(v10_pred),
                v10_correct=v10_correct,
                status=status,
            )
        )
    priority = {"improved": 0, "regressed": 1, "wrong->wrong": 2, "correct->correct": 3}
    return sorted(changes, key=lambda item: (priority[item.status], item.case_id))


def print_mode_tables(
    baseline_metrics: SystemMetrics,
    v10_metrics: SystemMetrics,
    mcnemar_result: dict[str, Any],
) -> None:
    metric_rows = [
        [
            "Top-1 accuracy",
            fmt_pct(baseline_metrics.top1_accuracy),
            fmt_pct(v10_metrics.top1_accuracy),
            fmt_pp_delta(baseline_metrics.top1_accuracy, v10_metrics.top1_accuracy),
        ]
    ]
    for group in ("F32", "F41", "others"):
        label = "others" if group == "others" else group
        support = baseline_metrics.supports[group]
        metric_rows.append(
            [
                f"Recall {label} (n={support})",
                fmt_pct(baseline_metrics.recalls[group]),
                fmt_pct(v10_metrics.recalls[group]),
                fmt_pp_delta(baseline_metrics.recalls[group], v10_metrics.recalls[group]),
            ]
        )
    metric_rows.extend(
        [
            [
                f"F41 -> F32 rate (n={baseline_metrics.supports['F41']})",
                fmt_pct(baseline_metrics.f41_to_f32_rate),
                fmt_pct(v10_metrics.f41_to_f32_rate),
                fmt_pp_delta(
                    baseline_metrics.f41_to_f32_rate,
                    v10_metrics.f41_to_f32_rate,
                ),
            ],
            [
                "Abstention rate",
                fmt_pct(baseline_metrics.abstention_rate),
                fmt_pct(v10_metrics.abstention_rate),
                fmt_pp_delta(baseline_metrics.abstention_rate, v10_metrics.abstention_rate),
            ],
            [
                "ECE (non-abstain)",
                fmt_float(baseline_metrics.ece),
                fmt_float(v10_metrics.ece),
                fmt_float_delta(baseline_metrics.ece, v10_metrics.ece),
            ],
        ]
    )
    print_table(["Metric", "Baseline", "V10", "Delta"], metric_rows, right_align={1, 2, 3})
    print()
    print_table(
        ["χ²", "p-value", "Baseline-only", "V10-only", "Significant"],
        [[
            fmt_float(mcnemar_result["statistic"]),
            fmt_p_value(mcnemar_result["p_value"]),
            str(mcnemar_result["n_a_only"]),
            str(mcnemar_result["n_b_only"]),
            yes_no(bool(mcnemar_result["significant"])),
        ]],
        right_align={0, 1, 2, 3},
    )


def print_change_tables(changes: Sequence[ChangeRecord]) -> None:
    counts = {"improved": 0, "regressed": 0, "wrong->wrong": 0, "correct->correct": 0}
    for change in changes:
        counts[change.status] += 1
    print()
    print_table(
        ["Summary", "Count"],
        [
            ["Changed predictions", str(len(changes))],
            ["Improved", str(counts["improved"])],
            ["Regressed", str(counts["regressed"])],
            ["Wrong -> wrong", str(counts["wrong->wrong"])],
            ["Correct -> correct", str(counts["correct->correct"])],
        ],
        right_align={1},
    )
    if not changes:
        print("\n  No changed predictions.")
        return
    print()
    print_table(
        ["Case ID", "Gold", "Baseline", "Base OK", "V10", "V10 OK", "Status"],
        [
            [
                change.case_id,
                change.gold_label,
                change.baseline_prediction,
                yes_no(change.baseline_correct),
                change.v10_prediction,
                yes_no(change.v10_correct),
                change.status,
            ]
            for change in changes
        ],
    )


def analyze_dataset(
    spec: DatasetSpec,
    baseline_dir: Path | None,
    v10_dir: Path | None,
    requested_mode: str | None,
) -> bool:
    if baseline_dir is None or not baseline_dir.is_dir():
        warn(f"{spec.label}: baseline sweep directory was not found.")
        return False
    if v10_dir is None or not v10_dir.is_dir():
        warn(
            f"{spec.label}: no V10 sweep directory found for pattern "
            f"{spec.v10_pattern!r}; skipping."
        )
        return False

    baseline = load_sweep(spec, baseline_dir)
    v10 = load_sweep(spec, v10_dir)
    if not baseline.mode_predictions:
        warn(f"{spec.label}: baseline sweep has no *_no_evidence predictions; skipping.")
        return False
    if not v10.mode_predictions:
        warn(f"{spec.label}: V10 sweep has no *_no_evidence predictions; skipping.")
        return False
    case_order, gold_map = reconcile_cases(baseline, v10)
    if not case_order:
        warn(f"{spec.label}: no shared cases between baseline and V10; skipping.")
        return False

    section(spec.label)
    print(f"  Baseline: {rel_path(baseline_dir)}")
    print(f"  V10:      {rel_path(v10_dir)}")
    print(f"  Cases:    {len(case_order)} shared cases")

    mode_names = [requested_mode] if requested_mode else sorted(
        set(baseline.mode_predictions) | set(v10.mode_predictions)
    )
    analyzed_any_mode = False
    for mode_name in mode_names:
        if mode_name not in baseline.mode_predictions:
            warn(f"{spec.label}: mode {mode_name!r} is missing in baseline; skipping.")
            continue
        if mode_name not in v10.mode_predictions:
            warn(f"{spec.label}: mode {mode_name!r} is missing in V10; skipping.")
            continue

        analyzed_any_mode = True
        subsection(f"{spec.label} - {mode_name}")
        baseline_predictions = baseline.mode_predictions[mode_name]
        v10_predictions = v10.mode_predictions[mode_name]
        baseline_metrics = compute_metrics(case_order, gold_map, baseline_predictions, mode_name)
        v10_metrics = compute_metrics(case_order, gold_map, v10_predictions, mode_name)
        mcnemar_result = mcnemar_test(
            baseline_metrics.correct_flags,
            v10_metrics.correct_flags,
            alpha=0.05,
        )
        print_mode_tables(baseline_metrics, v10_metrics, mcnemar_result)
        print()
        print("  Case-change analysis uses the raw top-1 prediction code.")
        print("  Recall groups use the gold primary label (first diagnosis).")
        print_change_tables(
            build_change_records(case_order, gold_map, baseline_predictions, v10_predictions)
        )

    if not analyzed_any_mode:
        warn(f"{spec.label}: no comparable modes were available.")
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare V10 sweep results against baseline sweeps."
    )
    parser.add_argument("--baseline-lingxi", type=str, help="Override LingxiDiag baseline dir.")
    parser.add_argument("--baseline-mdd", type=str, help="Override MDD-5k baseline dir.")
    parser.add_argument("--v10-lingxi", type=str, help="Override V10 LingxiDiag dir.")
    parser.add_argument("--v10-mdd", type=str, help="Override V10 MDD-5k dir.")
    parser.add_argument(
        "--dataset",
        choices=["lingxi", "mdd", "both"],
        default="both",
        help="Which dataset to analyze.",
    )
    parser.add_argument("--mode", type=str, help="Restrict analysis to a single mode.")
    args = parser.parse_args()

    dataset_keys = ["lingxi", "mdd"] if args.dataset == "both" else [args.dataset]
    baseline_overrides = {
        "lingxi": as_path(args.baseline_lingxi),
        "mdd": as_path(args.baseline_mdd),
    }
    v10_overrides = {
        "lingxi": as_path(args.v10_lingxi),
        "mdd": as_path(args.v10_mdd),
    }
    baseline_dirs = {
        key: resolve_dir(DATASETS[key], "baseline", baseline_overrides[key])
        for key in dataset_keys
    }
    v10_dirs = {
        key: resolve_dir(DATASETS[key], "v10", v10_overrides[key])
        for key in dataset_keys
    }

    section("V10 VS BASELINE SWEEP COMPARISON")
    for key in dataset_keys:
        spec = DATASETS[key]
        print(f"  {spec.label} baseline: {rel_path(baseline_dirs[key])}")
        print(f"  {spec.label} V10:      {rel_path(v10_dirs[key])}")

    analyzed_any = False
    for key in dataset_keys:
        analyzed_any = analyze_dataset(
            DATASETS[key],
            baseline_dirs[key],
            v10_dirs[key],
            args.mode,
        ) or analyzed_any

    if not analyzed_any:
        print()
        print("No comparable baseline/V10 sweep pairs were available.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
