#!/usr/bin/env python3
"""R4 Oracle simulation: what's the max improvement from F41/F32 contrastive?

Without running GPU, simulate the effect of a perfect contrastive agent by:
- For each case where both F41 and F32 are in logic_confirmed_codes,
  pretend the contrastive agent always picks correctly (oracle)
- Measure resulting Top-1 and F1_macro

This tells us the upper bound of what R4 can achieve on LingxiDiag val.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score
from sklearn.preprocessing import MultiLabelBinarizer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from culturedx.eval.lingxidiag_paper import (
    PAPER_12_CLASSES, gold_to_parent_list, to_paper_parent,
)


def load_predictions(path):
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line: records.append(json.loads(line))
    return records


def extract_ranked(rec):
    dt = rec.get("decision_trace") or {}
    if isinstance(dt, dict):
        diag = dt.get("diagnostician")
        if isinstance(diag, dict):
            r = diag.get("ranked_codes")
            if r: return [c for c in r if c]
    return []


def compute_metrics(records, eval_name):
    y_true, y_pred, top1_hits, exact = [], [], 0, 0
    for rec in records:
        golds = gold_to_parent_list(",".join(str(g) for g in (rec.get("gold_diagnoses") or []) if g))
        if not golds: golds = ["Others"]
        y_true.append(golds)

        primary = rec.get("primary_diagnosis", "")
        comorbid = rec.get("comorbid_diagnoses") or []
        pred = [to_paper_parent(primary)] if primary else ["Others"]
        pred += [to_paper_parent(c) for c in comorbid if c]
        pred = [p for p in pred if p]
        if not pred: pred = ["Others"]
        y_pred.append(pred)

        if set(pred) == set(golds): exact += 1
        if pred[0] in set(golds): top1_hits += 1

    n = len(records)
    mlb = MultiLabelBinarizer(classes=PAPER_12_CLASSES)
    yt = mlb.fit_transform(y_true)
    yp = mlb.transform(y_pred)
    f1_m = f1_score(yt, yp, average="macro", zero_division=0)
    f1_w = f1_score(yt, yp, average="weighted", zero_division=0)

    print(f"\n{eval_name}:")
    print(f"  12c_Acc:      {exact/n:.4f}")
    print(f"  12c_Top1:     {top1_hits/n:.4f}")
    print(f"  12c_F1_macro: {f1_m:.4f}")
    print(f"  12c_F1_w:     {f1_w:.4f}")
    return {"top1": top1_hits/n, "f1_m": f1_m, "f1_w": f1_w, "acc": exact/n}


def simulate_r4_oracle(records, scenario="perfect_f41_f32"):
    """Create a new predictions list with contrastive agent applied."""
    out = []
    n_triggered = 0
    n_flipped = 0
    for rec in records:
        new_rec = dict(rec)
        dt = rec.get("decision_trace") or {}
        confirmed_parents = set()
        for c in (dt.get("logic_engine_confirmed_codes") or []):
            p = to_paper_parent(c)
            if p: confirmed_parents.add(p)

        # Trigger condition
        triggered = "F32" in confirmed_parents and "F41" in confirmed_parents
        if not triggered:
            out.append(new_rec)
            continue
        n_triggered += 1

        # Oracle: if scenario is "perfect", pick whichever is in gold
        golds = set(gold_to_parent_list(",".join(
            str(g) for g in (rec.get("gold_diagnoses") or []) if g)))
        current_primary = to_paper_parent(rec.get("primary_diagnosis") or "")

        if scenario == "perfect_f41_f32":
            # Perfect oracle: if gold has F41, pick F41; if gold has F32, pick F32
            # If gold has both or neither, leave as is
            if "F41" in golds and "F32" not in golds:
                chosen_parent = "F41"
            elif "F32" in golds and "F41" not in golds:
                chosen_parent = "F32"
            else:
                out.append(new_rec)
                continue
        elif scenario == "realistic_70pct_f41":
            # Realistic: 70% accuracy on F41 cases, 95% on F32 cases
            # (reflecting that LLM contrastive agent would have some F32 bias)
            import random
            random.seed(hash(rec.get("case_id", "")) % (2**32))
            if "F41" in golds and "F32" not in golds:
                chosen_parent = "F41" if random.random() < 0.70 else "F32"
            elif "F32" in golds and "F41" not in golds:
                chosen_parent = "F32" if random.random() < 0.95 else "F41"
            else:
                out.append(new_rec)
                continue

        # Apply override: update primary and ranked_codes
        if current_primary != chosen_parent:
            n_flipped += 1
            # Find a specific subcode in ranked_codes that matches chosen_parent
            ranked = extract_ranked(rec)
            chosen_code = None
            for code in ranked:
                if to_paper_parent(code) == chosen_parent:
                    chosen_code = code
                    break
            if chosen_code is None:
                # Not in ranked; use the parent code directly
                chosen_code = chosen_parent + ".9" if chosen_parent in ("F32", "F41") else chosen_parent
            new_rec["primary_diagnosis"] = chosen_code

        out.append(new_rec)

    print(f"\nSimulation ({scenario}):")
    print(f"  Cases triggered (both F32 and F41 confirmed): {n_triggered}")
    print(f"  Cases flipped: {n_flipped}")
    return out


def main():
    run_dir = Path("results/validation/t1_diag_topk")
    records = load_predictions(run_dir / "predictions.jsonl")

    # Baseline
    baseline = compute_metrics(records, "Baseline (t1_diag_topk, no contrastive)")

    # Oracle: perfect F41/F32 disambiguation
    oracle_records = simulate_r4_oracle(records, "perfect_f41_f32")
    oracle = compute_metrics(oracle_records, "R4 ORACLE (perfect F41/F32 contrastive)")

    # Realistic: 70% F41 accuracy, 95% F32 accuracy
    realistic_records = simulate_r4_oracle(records, "realistic_70pct_f41")
    realistic = compute_metrics(realistic_records, "R4 REALISTIC (70% F41 / 95% F32 accuracy)")

    print("\n" + "=" * 72)
    print("R4 CONTRASTIVE IMPACT SUMMARY")
    print("=" * 72)
    print(f"{'Config':<35} {'Top-1':>8} {'F1_m':>8} {'F1_w':>8}")
    print("-" * 72)
    print(f"{'Baseline':<35} {baseline['top1']:>8.4f} {baseline['f1_m']:>8.4f} {baseline['f1_w']:>8.4f}")
    print(f"{'Oracle (perfect contrastive)':<35} {oracle['top1']:>8.4f} {oracle['f1_m']:>8.4f} {oracle['f1_w']:>8.4f}")
    print(f"{'Realistic (70%/95% accuracy)':<35} {realistic['top1']:>8.4f} {realistic['f1_m']:>8.4f} {realistic['f1_w']:>8.4f}")
    print(f"{'Δ Oracle vs Baseline':<35} "
          f"{(oracle['top1']-baseline['top1'])*100:>+7.2f}pp "
          f"{(oracle['f1_m']-baseline['f1_m'])*100:>+7.2f}pp "
          f"{(oracle['f1_w']-baseline['f1_w'])*100:>+7.2f}pp")
    print(f"{'Δ Realistic vs Baseline':<35} "
          f"{(realistic['top1']-baseline['top1'])*100:>+7.2f}pp "
          f"{(realistic['f1_m']-baseline['f1_m'])*100:>+7.2f}pp "
          f"{(realistic['f1_w']-baseline['f1_w'])*100:>+7.2f}pp")


if __name__ == "__main__":
    main()
