"""P0-B: Post-hoc comorbid cap replay on t1_diag_topk predictions.

Reads t1_diag_topk/predictions.jsonl, applies stricter comorbid filtering
based on met_ratio thresholds, and re-evaluates.
"""
import json, sys, os
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from culturedx.eval.lingxidiag_paper import (
    compute_table4_metrics, pred_to_parent_list, gold_to_parent_list, to_paper_parent,
)


def load_preds(path):
    with open(path) as f:
        return [json.loads(l) for l in f]


def apply_comorbid_cap(preds, min_ratio_pct=0.85, primary_min_ratio=0.8):
    """Cap comorbid: only keep if comorbid met_ratio >= primary_ratio * min_ratio_pct
    AND primary met_ratio >= primary_min_ratio.
    """
    results = []
    for p in preds:
        dt = p.get("decision_trace") or {}
        rco = dt.get("raw_checker_outputs", [])
        
        primary = p.get("primary_diagnosis", "")
        comorbid = p.get("comorbid_diagnoses", [])
        
        if not comorbid or not rco:
            results.append(dict(p))
            continue
        
        # Build met_ratio map
        ratio_map = {}
        for co in rco:
            code = co.get("disorder_code", "")
            ratio_map[code] = co.get("met_ratio", 0)
            parent = code.split(".")[0]
            if parent not in ratio_map or co.get("met_ratio", 0) > ratio_map[parent]:
                ratio_map[parent] = co.get("met_ratio", 0)
        
        primary_ratio = ratio_map.get(primary, ratio_map.get(primary.split(".")[0], 0))
        
        filtered_comorbid = []
        for c in comorbid:
            c_ratio = ratio_map.get(c, ratio_map.get(c.split(".")[0], 0))
            if primary_ratio >= primary_min_ratio and c_ratio >= primary_ratio * min_ratio_pct:
                filtered_comorbid.append(c)
        
        new_p = dict(p)
        new_p["comorbid_diagnoses"] = filtered_comorbid
        results.append(new_p)
    
    return results


def eval_preds(preds):
    cases = []
    for p in preds:
        gold_str = ";".join(p.get("gold_diagnoses", []))
        codes = [c for c in [p["primary_diagnosis"]] + (p.get("comorbid_diagnoses") or []) if c]
        cases.append({"DiagnosisCode": gold_str, "_pred_codes": codes})
    return compute_table4_metrics(cases, lambda c: pred_to_parent_list(c["_pred_codes"]))


def avg_labels(preds):
    return sum(1 + len(p.get("comorbid_diagnoses") or []) for p in preds) / len(preds)


if __name__ == "__main__":
    pred_path = "results/validation/t1_diag_topk/predictions.jsonl"
    preds = load_preds(pred_path)
    
    # Baseline (no cap)
    base_m = eval_preds(preds)
    print(f"Original t1_diag_topk: Overall={base_m['Overall']:.4f}  Acc={base_m['12class_Acc']:.4f}  "
          f"Top1={base_m['12class_Top1']:.4f}  F1m={base_m['12class_F1_macro']:.4f}  "
          f"avg_labels={avg_labels(preds):.2f}")
    print()
    
    # Sweep
    print(f"{'Config':<35} {'Ov':>7} {'Acc':>6} {'T1':>6} {'T3':>6} {'Fm':>6} {'Fw':>6} {'AvgL':>5}")
    print("-" * 85)
    
    best_ov = 0
    best_cfg = ""
    best_preds = None
    
    for primary_min in [0.5, 0.6, 0.7, 0.8, 0.9]:
        for ratio_pct in [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0]:
            capped = apply_comorbid_cap(preds, min_ratio_pct=ratio_pct, primary_min_ratio=primary_min)
            m = eval_preds(capped)
            al = avg_labels(capped)
            cfg = f"pmin={primary_min:.1f} rpct={ratio_pct:.2f}"
            ov = m["Overall"]
            if ov > best_ov:
                best_ov = ov
                best_cfg = cfg
                best_m = dict(m)
                best_preds = capped
            # Only print interesting ones
            if al < 1.5 and ov > 0.51:
                print(f"{cfg:<35} {ov:>7.4f} {m['12class_Acc']:>6.3f} {m['12class_Top1']:>6.3f} {m['12class_Top3']:>6.3f} {m['12class_F1_macro']:>6.3f} {m['12class_F1_weighted']:>6.3f} {al:>5.2f}")
    
    # Also try: drop ALL comorbid (single label only)
    single = [{**p, "comorbid_diagnoses": []} for p in preds]
    m_single = eval_preds(single)
    al_single = avg_labels(single)
    print(f"{'NO COMORBID (single label)':<35} {m_single['Overall']:>7.4f} {m_single['12class_Acc']:>6.3f} {m_single['12class_Top1']:>6.3f} {m_single['12class_Top3']:>6.3f} {m_single['12class_F1_macro']:>6.3f} {m_single['12class_F1_weighted']:>6.3f} {al_single:>5.2f}")
    
    if m_single["Overall"] > best_ov:
        best_ov = m_single["Overall"]
        best_cfg = "single_label"
        best_m = m_single
        best_preds = single
    
    print(f"\nBest: {best_cfg}  Overall={best_ov:.4f}")
    print(f"vs baseline 05: {best_ov - 0.527:+.4f}")
    
    # Save best
    outdir = Path("results/validation/t1_diag_topk_capped")
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / "predictions.jsonl", "w") as f:
        for p in best_preds:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    with open(outdir / "metrics.json", "w") as f:
        json.dump({"table4": best_m, "config": best_cfg, "avg_labels": avg_labels(best_preds)}, f, indent=2)
    print(f"Saved to {outdir}")
