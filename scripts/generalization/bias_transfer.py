"""Compare F32/F41 asymmetry across validation and cross-dataset runs."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "results/generalization/bias_transfer_analysis.json"

RUNS = (
    (
        "LingxiDiag R16 bypass logic",
        "lingxidiag16k",
        ROOT / "results/validation/r16_bypass_logic/predictions.jsonl",
    ),
    (
        "LingxiDiag R6 combined v2",
        "lingxidiag16k",
        ROOT / "results/validation/r6_combined_v2/predictions.jsonl",
    ),
    (
        "LingxiDiag R20 NOS v2",
        "lingxidiag16k",
        ROOT / "results/validation/r20_nos_variant_v2/predictions.jsonl",
    ),
    (
        "MDD-5k T1 baseline",
        "mdd5k",
        ROOT / "results/external/mdd5k_t1_seed42/predictions.jsonl",
    ),
    (
        "MDD-5k single baseline",
        "mdd5k",
        ROOT / "results/external/mdd5k_single/predictions.jsonl",
    ),
    (
        "MDD-5k R6v2",
        "mdd5k",
        ROOT / "results/generalization/mdd5k_r6v2/predictions.jsonl",
    ),
)


def parent(code: str | None) -> str | None:
    if not code:
        return None
    return str(code).strip().upper().split(".")[0] or None


def load_predictions(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            records.append(json.loads(line))
    if not records:
        raise ValueError(f"No predictions found in {path}")
    return records


def asymmetry(preds: list[dict[str, Any]]) -> tuple[int, int, float]:
    a = 0
    b = 0
    for record in preds:
        golds = {parent(code) for code in (record.get("gold_diagnoses") or []) if parent(code)}
        predicted = parent(record.get("primary_diagnosis"))
        if "F41" in golds and "F32" not in golds and predicted == "F32":
            a += 1
        if "F32" in golds and "F41" not in golds and predicted == "F41":
            b += 1
    return a, b, a / max(b, 1)


def analyze_run(label: str, dataset: str, path: Path) -> dict[str, Any]:
    records = load_predictions(path)
    a, b, ratio = asymmetry(records)
    return {
        "label": label,
        "dataset": dataset,
        "predictions_path": str(path.relative_to(ROOT)),
        "num_predictions": len(records),
        "f41_gold_pred_f32": a,
        "f32_gold_pred_f41": b,
        "ratio": ratio,
    }


def build_analysis() -> dict[str, Any]:
    rows = [analyze_run(label, dataset, path) for label, dataset, path in RUNS]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metric": "F32/F41 asymmetry ratio = (F41 gold -> F32) / max(F32 gold -> F41, 1)",
        "runs": rows,
    }


def print_summary(analysis: dict[str, Any]) -> None:
    print("F32/F41 asymmetry comparison")
    print("condition\tdataset\tF41->F32\tF32->F41\tratio")
    for row in analysis["runs"]:
        print(
            f"{row['label']}\t{row['dataset']}\t"
            f"{row['f41_gold_pred_f32']}\t{row['f32_gold_pred_f41']}\t{row['ratio']:.3f}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    analysis = build_analysis()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(analysis, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print_summary(analysis)
    print(f"\nSaved analysis to {args.output}")


if __name__ == "__main__":
    main()
