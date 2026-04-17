"""T2-LOWFREQ: Post-hoc low-frequency class boost on RRF ensemble scores."""
import json, sys, os
import numpy as np
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from culturedx.ensemble.rrf import rrf_fuse
from culturedx.eval.lingxidiag_paper import (
    compute_table4_metrics, pred_to_parent_list, gold_to_parent_list,
    to_paper_parent,
)

LOW_FREQ_CLASSES = {"F43", "F45", "F51", "F98", "Z71", "Others", "F39", "F20", "F31"}

def load_preds(path):
    with open(path) as f:
        return {json.loads(l)["case_id"]: json.loads(l) for l in f}

def build_fused_scores(preds_map, common_ids, weights, k=30):
    """Build per-case, per-class fused RRF scores."""
    system_names = list(preds_map.keys())
    results = {}
    for cid in common_ids:
        class_scores = Counter()
        for i, name in enumerate(system_names):
            p = preds_map[name][cid]
            codes = [p["primary_diagnosis"]] + (p.get("comorbid_diagnoses") or [])
            if name == "tfidf" and "ranked_codes" in p:
                codes = p["ranked_codes"][:5]
            # Convert to parent codes
            parent_codes = []
            for c in codes:
                pc = to_paper_parent(c)
                if pc not in [pp for pp, _ in parent_codes]:
                    parent_codes.append((pc, len(parent_codes)))
            
            w = weights[i] if weights else 1.0
            for code, rank in parent_codes:
                class_scores[code] += w / (k + rank + 1)
        
        results[cid] = dict(class_scores)
    return results

def apply_boost_and_predict(fused_scores, boost_map, max_labels=1):
    """Apply per-class boost to fused scores and predict."""
    predictions = {}
    for cid, scores in fused_scores.items():
        boosted = {cls: score + boost_map.get(cls, 0) for cls, score in scores.items()}
        sorted_codes = sorted(boosted.items(), key=lambda x: -x[1])
        pred_codes = [c for c, s in sorted_codes[:max_labels]]
        predictions[cid] = pred_codes
    return predictions

def evaluate(predictions, gold_map):
    cases = []
    for cid, codes in predictions.items():
        cases.append({
            "DiagnosisCode": ";".join(gold_map[cid]),
            "_pred_codes": codes,
        })
    return compute_table4_metrics(cases, lambda c: pred_to_parent_list(c["_pred_codes"]))

if __name__ == "__main__":
    preds_map = {
        "factb": load_preds("results/validation/factorial_b_improved_noevidence/predictions.jsonl"),
        "dtv05": load_preds("results/validation/05_dtv_v2_rag/predictions.jsonl"),
        "tfidf": load_preds("outputs/tfidf_baseline/predictions.jsonl"),
    }
    common = set.intersection(*(set(v.keys()) for v in preds_map.values()))
    gold_map = {cid: preds_map["factb"][cid].get("gold_diagnoses", []) for cid in common}
    
    # Best ensemble weights from T3
    weights = [1, 1, 2.0]  # tfidf++
    fused = build_fused_scores(preds_map, common, weights, k=30)
    
    # Baseline (no boost)
    base_preds = apply_boost_and_predict(fused, {}, max_labels=1)
    base_m = evaluate(base_preds, gold_map)
    print(f"Baseline ensemble: Overall={base_m['Overall']:.4f} F1m={base_m['12class_F1_macro']:.4f} Top1={base_m['12class_Top1']:.4f}")
    
    # Sweep boost values for low-freq classes
    print(f"\n{'Boost':>6} {'Overall':>8} {'F1m':>6} {'Top1':>6} {'Acc':>6}")
    print("-" * 40)
    
    best_ov = base_m["Overall"]
    best_boost = 0
    
    for boost_val in [0.001, 0.002, 0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20]:
        boost_map = {cls: boost_val for cls in LOW_FREQ_CLASSES}
        preds = apply_boost_and_predict(fused, boost_map, max_labels=1)
        m = evaluate(preds, gold_map)
        flag = " *" if m["Overall"] > best_ov else ""
        print(f"{boost_val:>6.3f} {m['Overall']:>8.4f} {m['12class_F1_macro']:>6.4f} {m['12class_Top1']:>6.4f} {m['12class_Acc']:>6.4f}{flag}")
        if m["Overall"] > best_ov:
            best_ov = m["Overall"]
            best_boost = boost_val
            best_m = dict(m)
    
    # Also try per-class adaptive boost
    print(f"\nBest uniform boost: {best_boost} Overall={best_ov:.4f}")
    
    # Save
    outdir = Path("results/validation/t2_lowfreq")
    outdir.mkdir(parents=True, exist_ok=True)
    
    boost_map = {cls: best_boost for cls in LOW_FREQ_CLASSES}
    final_preds = apply_boost_and_predict(fused, boost_map, max_labels=1)
    final_m = evaluate(final_preds, gold_map)
    
    with open(outdir / "metrics.json", "w") as f:
        json.dump({"table4": final_m, "boost_value": best_boost}, f, indent=2)
    
    with open(outdir / "predictions.jsonl", "w") as f:
        for cid in sorted(final_preds.keys()):
            f.write(json.dumps({
                "case_id": cid,
                "gold_diagnoses": gold_map[cid],
                "primary_diagnosis": final_preds[cid][0] if final_preds[cid] else "Others",
                "comorbid_diagnoses": final_preds[cid][1:] if len(final_preds[cid]) > 1 else [],
            }, ensure_ascii=False) + "\n")
    
    print(f"\nFinal: Overall={final_m['Overall']:.4f} Δ={final_m['Overall']-base_m['Overall']:+.4f}")
    print(f"Saved to {outdir}")
