#!/usr/bin/env python3
"""Compute metrics for any predictions.jsonl in standard schema.

Output: JSON with Top-1, Top-3, EM, mF1, wF1, Overall, mgEM, sgEM, emit_rate.
"""
import argparse, json, sys
from collections import defaultdict
from pathlib import Path

def base_code(c): return c.split(".")[0] if c else c
def base_set(codes): return set(base_code(c) for c in codes)

def compute(path, label=""):
    recs = [json.loads(l) for l in open(path) if l.strip()]
    n = len(recs)
    if n == 0: return {}
    top1=top3=em=two=four=n_emit=0
    sg_em=mg_em=sg_n=mg_n=0
    class_tp=defaultdict(int); class_fp=defaultdict(int); class_fn=defaultdict(int); class_support=defaultdict(int)
    FOUR={"F32":"dep","F33":"dep","F34":"dep","F39":"dep","F40":"anx","F41":"anx","F43":"anx","F42":"ocd"}
    def two_class(c): b=base_code(c); return "mood" if b.startswith("F3") else "neurotic" if b.startswith("F4") else "other"
    def four_class(c): return FOUR.get(base_code(c), "other")
    for r in recs:
        gold = r.get("gold_diagnoses", [])
        if not gold: continue
        gp = base_code(gold[0])
        gold_b = base_set(gold)
        primary_b = base_code(r["primary_diagnosis"])
        ranked = r.get("decision_trace", {}).get("diagnostician_ranked", []) or []
        top3_set = [base_code(c) for c in ranked[:3]]
        if primary_b == gp: top1 += 1
        if gp in top3_set: top3 += 1
        pred_b = {primary_b} | base_set(r.get("comorbid_diagnoses", []))
        if pred_b == gold_b: em += 1
        if len(pred_b) > 1: n_emit += 1
        if two_class(primary_b) == two_class(gp): two += 1
        if four_class(primary_b) == four_class(gp): four += 1
        if len(gold_b) == 1:
            sg_n += 1
            if pred_b == gold_b: sg_em += 1
        else:
            mg_n += 1
            if pred_b == gold_b: mg_em += 1
        class_support[gp] += 1
        if primary_b == gp: class_tp[primary_b] += 1
        else: class_fp[primary_b] += 1; class_fn[gp] += 1
    classes = sorted(set(class_support) | set(class_tp) | set(class_fp) | set(class_fn))
    f1 = {}
    for c in classes:
        tp,fp,fn = class_tp[c], class_fp[c], class_fn[c]
        if tp+fp==0 and tp+fn==0: f1[c]=0; continue
        p = tp/(tp+fp) if tp+fp else 0; rc = tp/(tp+fn) if tp+fn else 0
        f1[c] = 2*p*rc/(p+rc) if p+rc else 0
    mf1 = sum(f1.values())/len(f1) if f1 else 0
    ts = sum(class_support.values())
    wf1 = sum(f1[c]*class_support[c] for c in classes)/ts if ts else 0
    return {
        "label": label, "n": n, "emit_rate": n_emit/n,
        "top1": top1/n, "top3": top3/n, "em": em/n,
        "macro_f1": mf1, "weighted_f1": wf1,
        "overall": (top1/n+mf1+wf1)/3,
        "two_class": two/n, "four_class": four/n,
        "sgEM": sg_em/sg_n if sg_n else 0,
        "mgEM": mg_em/mg_n if mg_n else 0,
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("paths", nargs="+", help="predictions.jsonl files (label=basename)")
    p.add_argument("--out", default=None, help="optional JSON output path")
    args = p.parse_args()
    results = []
    for path in args.paths:
        label = Path(path).parent.name + "/" + Path(path).name
        r = compute(path, label=label)
        results.append(r)
        print(f"{label}: emit={100*r['emit_rate']:.1f}% Top-1={r['top1']:.4f} EM={r['em']:.4f} mgEM={r['mgEM']:.4f} sgEM={r['sgEM']:.4f}")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
