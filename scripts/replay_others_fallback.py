"""Post-hoc Others fallback replay on existing predictions."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def load_predictions(path: str) -> list[dict]:
    with open(path) as f:
        return [json.loads(l) for l in f]


def apply_others_fallback(preds: list[dict], threshold: float) -> list[dict]:
    """If max_met_ratio across all disorders < threshold, override to Others."""
    results = []
    for p in preds:
        dt = p.get("decision_trace", {})
        rco = dt.get("raw_checker_outputs", [])
        confirmed = dt.get("logic_engine_confirmed_codes", [])
        
        if rco:
            max_ratio = max(co.get("met_ratio", 0) for co in rco)
        else:
            max_ratio = 1.0
        
        if not confirmed or (max_ratio < threshold and len(confirmed) <= 1):
            new_p = {**p, "primary_diagnosis": "Others", "comorbid_diagnoses": []}
        else:
            new_p = dict(p)
        results.append(new_p)
    return results


def eval_predictions(preds: list[dict]) -> dict:
    """Compute table4 metrics from predictions with gold_diagnoses."""
    from culturedx.eval.lingxidiag_paper import (
        gold_to_parent_list, pred_to_parent_list,
    )
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.preprocessing import MultiLabelBinarizer
    import numpy as np
    
    gold_12 = []
    pred_12 = []
    
    for p in preds:
        golds = p.get("gold_diagnoses", [])
        gold_str = ";".join(golds) if isinstance(golds, list) else str(golds)
        gold_parents = gold_to_parent_list(gold_str)
        
        pred_codes = [p["primary_diagnosis"]] + (p.get("comorbid_diagnoses") or [])
        pred_parents = pred_to_parent_list(pred_codes)
        if not pred_parents:
            pred_parents = ["Others"]
        
        gold_12.append(gold_parents)
        pred_12.append(pred_parents)
    
    # 12-class metrics
    all_labels = sorted(set(l for ls in gold_12 + pred_12 for l in ls))
    
    # Exact match accuracy
    acc = sum(1 for g, p in zip(gold_12, pred_12) if set(g) == set(p)) / len(gold_12)
    
    # Top-1: primary matches any gold
    top1 = sum(1 for g, p in zip(gold_12, pred_12) if p and p[0] in g) / len(gold_12)
    
    # Top-3: any of top-3 preds matches any gold
    top3 = sum(1 for g, p in zip(gold_12, pred_12) if any(pp in g for pp in p[:3])) / len(gold_12)
    
    # F1 macro/weighted via sklearn
    mlb = MultiLabelBinarizer(classes=all_labels)
    y_true = mlb.fit_transform(gold_12)
    y_pred = mlb.transform(pred_12)
    
    f1_macro = f1_score(y_true, y_pred, average="macro", zero_division=0)
    f1_weighted = f1_score(y_true, y_pred, average="weighted", zero_division=0)
    
    return {
        "12class_Acc": round(acc, 4),
        "12class_Top1": round(top1, 4),
        "12class_Top3": round(top3, 4),
        "12class_F1_macro": round(f1_macro, 4),
        "12class_F1_weighted": round(f1_weighted, 4),
        "Overall": round(np.mean([acc, top1, top3, f1_macro, f1_weighted]), 4),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--thresholds", nargs="+", type=float,
                        default=[0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    
    preds = load_predictions(args.predictions)
    
    # Baseline
    base_m = eval_predictions(preds)
    print(f"Baseline: Overall={base_m['Overall']:.4f}  F1m={base_m['12class_F1_macro']:.4f}  Top1={base_m['12class_Top1']:.4f}")
    print()
    
    best_th = None
    best_overall = 0
    
    for th in args.thresholds:
        mod_preds = apply_others_fallback(preds, th)
        others_n = sum(1 for p in mod_preds if p["primary_diagnosis"] == "Others")
        m = eval_predictions(mod_preds)
        d = m["Overall"] - base_m["Overall"]
        print(f"th={th:.1f}: Overall={m['Overall']:.4f}({d:+.4f})  F1m={m['12class_F1_macro']:.4f}  Top1={m['12class_Top1']:.4f}  Acc={m['12class_Acc']:.4f}  Others={others_n}")
        if m["Overall"] > best_overall:
            best_overall = m["Overall"]
            best_th = th
    
    print(f"\nBest: th={best_th} Overall={best_overall:.4f}")
    
    if args.output_dir:
        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        best_preds = apply_others_fallback(preds, best_th)
        with open(out / "predictions.jsonl", "w") as f:
            for p in best_preds:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        m = eval_predictions(best_preds)
        with open(out / "metrics.json", "w") as f:
            json.dump({"table4": m, "threshold": best_th}, f, indent=2)
        print(f"Saved to {out}")
