"""Bootstrap 95% CI for all paper-relevant metrics.

Compares CultureDx configs against paper SOTA point estimates.
Reports: mean, 95% CI [lo, hi], and whether CI lower bound > paper SOTA.
"""
import json, sys, os
import numpy as np
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from culturedx.eval.lingxidiag_paper import (
    gold_to_parent_list, pred_to_parent_list, to_paper_parent,
)
from sklearn.metrics import f1_score
from sklearn.preprocessing import MultiLabelBinarizer

PAPER_CLASSES = ["F20","F31","F32","F39","F41","F42","F43","F45","F51","F98","Z71","Others"]
PAPER_SOTA = {"Acc": 0.409, "Top1": 0.496, "Top3": 0.645, "F1m": 0.295, "F1w": 0.520}


def load_eval_data(pred_path, metrics_v2_path=None):
    """Load predictions and extract gold/pred pairs."""
    records = []
    with open(pred_path) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            r = json.loads(line)
            
            gold_str = ";".join(r.get("gold_diagnoses", []))
            golds = gold_to_parent_list(gold_str) or ["Others"]
            
            primary = r.get("primary_diagnosis")
            comorbid = r.get("comorbid_diagnoses") or []
            codes = [c for c in [primary] + comorbid if c]
            pred_pri = pred_to_parent_list(codes) or ["Others"]
            
            # Ranked Top-3
            dt = r.get("decision_trace") or {}
            ranked = []
            diag = dt.get("diagnostician")
            if isinstance(diag, dict):
                ranked = diag.get("ranked_codes") or []
            if not ranked:
                ranked = dt.get("diagnostician_ranked") or []
            
            ordered = []
            if primary: ordered.append(primary)
            for rc in ranked:
                if rc and rc not in ordered: ordered.append(rc)
            for c in comorbid:
                if c and c not in ordered: ordered.append(c)
            pred_t3 = pred_to_parent_list(ordered) or ["Others"]
            
            records.append({"golds": golds, "pred_pri": pred_pri, "pred_t3": pred_t3})
    
    return records


def compute_metrics(records, indices=None):
    """Compute 5 key 12c metrics on a subset of records."""
    if indices is not None:
        subset = [records[i] for i in indices]
    else:
        subset = records
    
    n = len(subset)
    if n == 0:
        return {"Acc": 0, "Top1": 0, "Top3": 0, "F1m": 0, "F1w": 0}
    
    exact = sum(1 for r in subset if set(r["pred_pri"]) == set(r["golds"])) / n
    top1 = sum(1 for r in subset if r["pred_pri"] and r["pred_pri"][0] in set(r["golds"])) / n
    top3 = sum(1 for r in subset if set(r["pred_t3"][:3]) & set(r["golds"])) / n
    
    mlb = MultiLabelBinarizer(classes=PAPER_CLASSES)
    y_true = mlb.fit_transform([r["golds"] for r in subset])
    y_pred = mlb.transform([r["pred_pri"] for r in subset])
    f1m = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    f1w = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))
    
    return {"Acc": exact, "Top1": top1, "Top3": top3, "F1m": f1m, "F1w": f1w}


def bootstrap_ci(records, n_boot=10000, seed=42, alpha=0.05):
    """Bootstrap 95% CI for each metric."""
    rng = np.random.RandomState(seed)
    n = len(records)
    
    boot_metrics = {k: [] for k in ["Acc", "Top1", "Top3", "F1m", "F1w"]}
    
    for _ in range(n_boot):
        idx = rng.randint(0, n, size=n)
        m = compute_metrics(records, idx)
        for k in boot_metrics:
            boot_metrics[k].append(m[k])
    
    results = {}
    for k in boot_metrics:
        arr = np.array(boot_metrics[k])
        lo = np.percentile(arr, 100 * alpha / 2)
        hi = np.percentile(arr, 100 * (1 - alpha / 2))
        results[k] = {"mean": float(np.mean(arr)), "lo": float(lo), "hi": float(hi), "std": float(np.std(arr))}
    
    return results


if __name__ == "__main__":
    configs = {
        "t4_f1_opt": "results/validation/t4_f1_opt/predictions.jsonl",
        "t3_tfidf_stack": "results/validation/t3_tfidf_stack/predictions.jsonl",
        "factorial_b": "results/validation/factorial_b_improved_noevidence/predictions.jsonl",
        "05_baseline": "results/validation/05_dtv_v2_rag/predictions.jsonl",
        "t1_topk_fixed": "results/validation/t1_diag_topk_comorbid_fixed/predictions.jsonl",
    }
    
    all_results = {}
    
    for name, path in configs.items():
        if not os.path.exists(path):
            print(f"SKIP {name}: {path} not found")
            continue
        
        print(f"\n{'='*70}")
        print(f"  Bootstrap CI: {name}")
        print(f"{'='*70}")
        
        records = load_eval_data(path)
        point = compute_metrics(records)
        ci = bootstrap_ci(records, n_boot=10000)
        
        print(f"{'Metric':<8} {'Point':>8} {'95% CI':>18} {'Paper':>8} {'CI lo > Paper?':>15}")
        print("-" * 65)
        
        for k in ["Acc", "Top1", "Top3", "F1m", "F1w"]:
            p = point[k]
            c = ci[k]
            sota = PAPER_SOTA[k]
            beats = "✅ YES" if c["lo"] > sota else "❌ no"
            print(f"{k:<8} {p:>8.4f} [{c['lo']:>7.4f}, {c['hi']:>7.4f}] {sota:>8.3f} {beats:>15}")
        
        all_results[name] = {"point": point, "ci": ci}
    
    # Save
    outdir = Path("results/validation/bootstrap_ci")
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / "bootstrap_ci.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved to {outdir}/bootstrap_ci.json")
