#!/usr/bin/env python3
"""Retrospective comorbidity analysis on existing prediction files.

Loads predictions from sweep directories, computes comorbidity metrics
and optionally 4-class accuracy for LingxiDiag.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.eval.metrics import compute_comorbidity_metrics, normalize_code_list


def predict_four_class(primary: str | None, comorbid: list[str]) -> str:
    """Map primary + comorbid codes to LingxiDiag 4-class label."""
    all_codes = [c for c in [primary] + (comorbid or []) if c]
    has_dep = any(c.startswith("F32") or c.startswith("F33") for c in all_codes)
    has_anx = any(c.startswith("F40") or c.startswith("F41") for c in all_codes)
    if has_dep and has_anx:
        return "Mixed"
    if has_dep:
        return "Depression"
    if has_anx:
        return "Anxiety"
    return "Other"


def gold_four_class(diagnoses: list[str]) -> str:
    """Map gold ICD-10 codes to 4-class label."""
    has_dep = any(c.startswith("F32") or c.startswith("F33") for c in diagnoses)
    has_anx = any(c.startswith("F40") or c.startswith("F41") for c in diagnoses)
    if has_dep and has_anx:
        return "Mixed"
    if has_dep:
        return "Depression"
    if has_anx:
        return "Anxiety"
    return "Other"


def load_predictions(pred_path: Path) -> list[dict]:
    """Load predictions from JSON file."""
    with open(pred_path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "predictions" in data:
        return data["predictions"]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unknown predictions format in {pred_path}")


def load_gold_labels(dataset: str, data_path: str | None = None) -> dict[str, list[str]]:
    """Load gold labels keyed by case_id."""
    from culturedx.data.adapters import get_adapter
    
    paths = {
        "lingxidiag16k": "data/raw/lingxidiag16k",
        "mdd5k_raw": "data/raw/mdd5k_repo",
        "mdd5k": "data/raw/mdd5k_repo",
        "edaic": "data/raw/daic_explain/edaic_processed.json",
    }
    effective_path = data_path or paths.get(dataset)
    if not effective_path:
        raise ValueError(f"No data path for dataset '{dataset}'. Use --data-path.")
    
    adapter = get_adapter(dataset, effective_path)
    cases = adapter.load()
    return {c.case_id: c.diagnoses for c in cases}


def analyze_one(pred_path: Path, gold_map: dict[str, list[str]], dataset: str, four_class: bool, save: bool) -> dict:
    """Analyze one predictions file."""
    preds_raw = load_predictions(pred_path)
    
    preds = []
    golds = []
    four_class_preds = []
    four_class_golds = []
    skipped = 0
    
    for p in preds_raw:
        cid = p["case_id"]
        if cid not in gold_map:
            skipped += 1
            continue
        gold_dx = gold_map[cid]
        if not gold_dx:
            skipped += 1
            continue
        
        pred_dx = [p["primary_diagnosis"]] if p.get("primary_diagnosis") else ["unknown"]
        pred_dx += p.get("comorbid_diagnoses", [])
        
        preds.append(pred_dx)
        golds.append(gold_dx)
        
        if four_class:
            four_class_preds.append(predict_four_class(p.get("primary_diagnosis"), p.get("comorbid_diagnoses", [])))
            four_class_golds.append(gold_four_class(gold_dx))
    
    if not preds:
        return {"error": "No valid predictions with gold labels"}
    
    # Comorbidity metrics
    metrics = compute_comorbidity_metrics(preds, golds, normalize="parent")
    metrics["n_evaluated"] = len(preds)
    metrics["n_skipped"] = skipped
    
    # 4-class accuracy
    if four_class and four_class_preds:
        correct = sum(1 for p, g in zip(four_class_preds, four_class_golds) if p == g)
        metrics["four_class_accuracy"] = correct / len(four_class_preds)
        metrics["four_class_n"] = len(four_class_preds)
        
        # Per-class breakdown
        classes = ["Depression", "Anxiety", "Mixed", "Other"]
        for cls in classes:
            tp = sum(1 for p, g in zip(four_class_preds, four_class_golds) if p == cls and g == cls)
            fp = sum(1 for p, g in zip(four_class_preds, four_class_golds) if p == cls and g != cls)
            fn = sum(1 for p, g in zip(four_class_preds, four_class_golds) if p != cls and g == cls)
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            metrics[f"four_class_{cls.lower()}_precision"] = round(precision, 4)
            metrics[f"four_class_{cls.lower()}_recall"] = round(recall, 4)
            metrics[f"four_class_{cls.lower()}_f1"] = round(f1, 4)
    
    if save:
        out_path = pred_path.parent / "comorbidity_metrics.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        print(f"  Saved: {out_path}")
    
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Retrospective comorbidity analysis")
    parser.add_argument("--sweep-dirs", nargs="+", required=True, help="Sweep output directories")
    parser.add_argument("--dataset", required=True, help="Dataset name for gold labels")
    parser.add_argument("--data-path", default=None, help="Override dataset path")
    parser.add_argument("--four-class", action="store_true", help="Compute 4-class accuracy (LingxiDiag)")
    parser.add_argument("--save", action="store_true", help="Save comorbidity_metrics.json per condition")
    args = parser.parse_args()
    
    # Load gold labels once
    gold_map = load_gold_labels(args.dataset, args.data_path)
    print(f"Loaded {len(gold_map)} gold labels for dataset '{args.dataset}'")
    
    # Find all prediction files
    for sweep_dir_pattern in args.sweep_dirs:
        sweep_dir = Path(sweep_dir_pattern)
        if not sweep_dir.exists():
            print(f"WARNING: {sweep_dir} not found, skipping")
            continue
        
        # Check for condition subdirectories
        condition_dirs = [d for d in sweep_dir.iterdir() if d.is_dir() and (d / "predictions.json").exists()]
        if not condition_dirs:
            # Maybe predictions.json is at sweep level
            if (sweep_dir / "predictions.json").exists():
                condition_dirs = [sweep_dir]
        
        if not condition_dirs:
            print(f"WARNING: No predictions.json found in {sweep_dir}")
            continue
        
        print(f"\n{'='*60}")
        print(f"Sweep: {sweep_dir.name}")
        print(f"{'='*60}")
        
        for cond_dir in sorted(condition_dirs):
            pred_path = cond_dir / "predictions.json"
            print(f"\n  Condition: {cond_dir.name}")
            metrics = analyze_one(pred_path, gold_map, args.dataset, args.four_class, args.save)
            
            if "error" in metrics:
                print(f"  ERROR: {metrics['error']}")
                continue
            
            print(f"  N evaluated: {metrics['n_evaluated']}, skipped: {metrics['n_skipped']}")
            print(f"  Hamming accuracy:     {metrics.get('hamming_accuracy', 0):.4f}")
            print(f"  Subset accuracy:      {metrics.get('subset_accuracy', 0):.4f}")
            print(f"  Comorbid detect F1:   {metrics.get('comorbidity_detection_f1', 0):.4f}")
            print(f"  Label coverage:       {metrics.get('label_coverage', 0):.4f}")
            print(f"  Label precision:      {metrics.get('label_precision', 0):.4f}")
            print(f"  Avg predicted labels: {metrics.get('avg_predicted_labels', 0):.2f}")
            print(f"  Avg gold labels:      {metrics.get('avg_gold_labels', 0):.2f}")
            
            if "four_class_accuracy" in metrics:
                print(f"\n  4-class accuracy:  {metrics['four_class_accuracy']:.4f} (baseline: 0.430)")
                for cls in ["depression", "anxiety", "mixed", "other"]:
                    p = metrics.get(f"four_class_{cls}_precision", 0)
                    r = metrics.get(f"four_class_{cls}_recall", 0)
                    f1 = metrics.get(f"four_class_{cls}_f1", 0)
                    print(f"    {cls:12s}  P={p:.3f}  R={r:.3f}  F1={f1:.3f}")


if __name__ == "__main__":
    main()
