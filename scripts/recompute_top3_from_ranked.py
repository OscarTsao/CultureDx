"""P0-A: Recompute Top-3 using diagnostician ranked_codes[:3] instead of primary+comorbid.

For each run with predictions.jsonl, if decision_trace.diagnostician_ranked exists,
use ranked_codes[:3] as the top-3 prediction set. This better reflects the system's
candidate coverage than the finalized 1-2 label output.
"""
import json, os, sys, copy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from culturedx.eval.lingxidiag_paper import (
    gold_to_parent_list, pred_to_parent_list, to_paper_parent,
    compute_table4_metrics,
)


def recompute_for_run(run_dir: str) -> dict | None:
    pred_path = os.path.join(run_dir, "predictions.jsonl")
    metrics_path = os.path.join(run_dir, "metrics.json")
    
    if not os.path.exists(pred_path) or not os.path.exists(metrics_path):
        return None
    
    preds = []
    with open(pred_path) as f:
        for line in f:
            preds.append(json.loads(line))
    
    if not preds:
        return None
    
    # Check if ranked_codes available
    sample = preds[0]
    dt = sample.get("decision_trace") or {}
    ranked = dt.get("diagnostician_ranked", [])
    if not ranked:
        # Try alternate location
        diag = dt.get("diagnostician", {})
        if isinstance(diag, dict):
            ranked = diag.get("ranked_codes", [])
    
    if not ranked:
        return None  # no ranked_codes in this run
    
    # Recompute Top-3 using ranked_codes[:3]
    top3_hits = 0
    top1_hits = 0
    n = len(preds)
    
    for p in preds:
        dt = p.get("decision_trace") or {}
        ranked = dt.get("diagnostician_ranked", [])
        if not ranked:
            diag = dt.get("diagnostician", {})
            if isinstance(diag, dict):
                ranked = diag.get("ranked_codes", [])
        
        gold_str = ";".join(p.get("gold_diagnoses", []))
        gold_parents = set(gold_to_parent_list(gold_str))
        
        # Top-3 from ranked_codes
        ranked_parents = [to_paper_parent(c) for c in ranked[:3]]
        if set(ranked_parents) & gold_parents:
            top3_hits += 1
        
        # Top-1 from ranked_codes (for comparison)
        if ranked_parents and ranked_parents[0] in gold_parents:
            top1_hits += 1
    
    return {
        "top3_from_ranked": round(top3_hits / n, 4),
        "top1_from_ranked": round(top1_hits / n, 4),
        "n": n,
    }


if __name__ == "__main__":
    base_dirs = [
        "results/validation",
        "results/external",
    ]
    
    results = {}
    
    for base in base_dirs:
        if not os.path.exists(base):
            continue
        for run_name in sorted(os.listdir(base)):
            run_dir = os.path.join(base, run_name)
            if not os.path.isdir(run_dir):
                continue
            
            r = recompute_for_run(run_dir)
            if r is None:
                continue
            
            # Load existing metrics
            metrics_path = os.path.join(run_dir, "metrics.json")
            with open(metrics_path) as f:
                metrics = json.load(f)
            
            t4 = metrics.get("table4", metrics)
            old_top3 = t4.get("12class_Top3", 0)
            old_top1 = t4.get("12class_Top1", 0)
            
            results[run_name] = {
                "old_top3": old_top3,
                "new_top3": r["top3_from_ranked"],
                "delta_top3": round(r["top3_from_ranked"] - old_top3, 4),
                "old_top1": old_top1,
                "new_top1_ranked": r["top1_from_ranked"],
            }
            
            # Write back: preserve original as table4_primary_only, update table4
            if "table4" in metrics:
                if "table4_primary_only" not in metrics:
                    metrics["table4_primary_only"] = copy.deepcopy(metrics["table4"])
                metrics["table4"]["12class_Top3_ranked"] = r["top3_from_ranked"]
                metrics["table4"]["12class_Top1_ranked"] = r["top1_from_ranked"]
            
            with open(metrics_path, "w") as f:
                json.dump(metrics, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print(f"{'Run':<35} {'Old Top3':>8} {'Ranked Top3':>11} {'Δ':>6}")
    print("-" * 65)
    for name, r in sorted(results.items(), key=lambda x: -x[1]["new_top3"]):
        d = r["delta_top3"]
        flag = " ←" if d > 0.01 else ""
        print(f"{name:<35} {r['old_top3']:>8.3f} {r['new_top3']:>11.3f} {d:>+6.3f}{flag}")
    
    print(f"\nUpdated {len(results)} metrics.json files with 12class_Top3_ranked field")
