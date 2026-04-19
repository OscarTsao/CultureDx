#!/usr/bin/env python3
"""Phase 0-B: Post-hoc comorbid cap strategies for t1_diag_topk.

t1_diag_topk has Top-3 = 0.762 (best of any config, +11.7pp over paper SOTA 0.645)
but 12c_Acc = 0.057 due to comorbid over-prediction:
  - avg_predicted_labels = 1.848 (vs gold 1.091)
  - 848/1000 cases have comorbid
  - 500/848 comorbid are F39 (NOS "trash class")

This script writes post-hoc-modified predictions.jsonl under multiple strategies
and reports the Table-4 metrics for each. No GPU needed.

Strategies:
  A. drop_all           Drop all comorbid unconditionally
  B. drop_nos           Drop if comorbid is F39 or F98
  C. ratio_threshold    Drop if comorbid_met_ratio < primary_met_ratio * T
                        (T scanned over {0.85, 0.90, 0.95, 1.0})
  D. absolute_threshold Drop if comorbid_met_ratio < K
                        (K scanned over {0.8, 0.9, 1.0, 1.1})
  E. top_pair_only      Only keep comorbid if (primary, comorbid) is a known
                        high-frequency pair in gold (F32+F41, F41+F51, F41+F42)
  F. combined           drop_nos + absolute_threshold(0.9) + top_pair_only

For the best strategy, writes modified predictions.jsonl to
results/validation/<run>_comorbid_fixed/predictions.jsonl, then the user can
re-run recompute_top3_from_ranked.py on it to get full metrics.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from culturedx.eval.lingxidiag_paper import (
    pred_to_parent_list,
    gold_to_parent_list,
    to_paper_parent,
)


NOS_CODES = {"F39", "F98"}
TOP_GOLD_PAIRS = {
    frozenset({"F32", "F41"}),
    frozenset({"F41", "F51"}),
    frozenset({"F41", "F42"}),
    frozenset({"F32", "F51"}),
}


def get_met_ratio(rec: dict, disorder_code: str) -> float | None:
    """Look up met_ratio for a given disorder in raw_checker_outputs."""
    dt = rec.get("decision_trace") or {}
    raw = dt.get("raw_checker_outputs") or []
    target_parent = to_paper_parent(disorder_code)
    for co in raw:
        co_code = co.get("disorder_code", "")
        if to_paper_parent(co_code) == target_parent:
            return co.get("met_ratio")
    return None


def apply_strategy(rec: dict, strategy: str, param: float | None = None) -> dict:
    """Return modified record with comorbid adjusted per strategy."""
    new = copy.deepcopy(rec)
    primary = new.get("primary_diagnosis")
    comorbid = list(new.get("comorbid_diagnoses") or [])
    if not comorbid:
        return new

    if strategy == "drop_all":
        new["comorbid_diagnoses"] = []
        return new

    kept = []
    primary_parent = to_paper_parent(primary) if primary else None

    for c in comorbid:
        c_parent = to_paper_parent(c)
        keep = True

        if strategy == "drop_nos":
            if c_parent in NOS_CODES:
                keep = False

        elif strategy == "ratio_threshold":
            pri_ratio = get_met_ratio(rec, primary) if primary else None
            com_ratio = get_met_ratio(rec, c)
            if pri_ratio is None or com_ratio is None:
                keep = False  # no signal → drop by default
            elif com_ratio < pri_ratio * param:
                keep = False

        elif strategy == "absolute_threshold":
            com_ratio = get_met_ratio(rec, c)
            if com_ratio is None or com_ratio < param:
                keep = False

        elif strategy == "top_pair_only":
            pair = frozenset({primary_parent, c_parent})
            if pair not in TOP_GOLD_PAIRS:
                keep = False

        elif strategy == "combined":
            # drop_nos + absolute(>=0.9) + top_pair_only
            if c_parent in NOS_CODES:
                keep = False
            com_ratio = get_met_ratio(rec, c)
            if com_ratio is None or com_ratio < 0.9:
                keep = False
            pair = frozenset({primary_parent, c_parent})
            if pair not in TOP_GOLD_PAIRS:
                keep = False

        if keep:
            kept.append(c)

    new["comorbid_diagnoses"] = kept
    return new


def extract_ranked_codes(rec: dict) -> list[str]:
    dt = rec.get("decision_trace") or {}
    if isinstance(dt, dict):
        diag = dt.get("diagnostician")
        if isinstance(diag, dict):
            r = diag.get("ranked_codes")
            if r: return [c for c in r if c]
        r = dt.get("diagnostician_ranked")
        if r: return [c for c in r if c]
    return []


def evaluate_predictions(records: list[dict]) -> dict:
    """Compute 12c metrics (Acc/Top1/Top3/F1m/F1w) from in-memory prediction records.

    Top-3 uses ranked_codes when available (fair comparison).
    """
    from sklearn.metrics import f1_score
    from sklearn.preprocessing import MultiLabelBinarizer

    paper_classes = ["F20","F31","F32","F39","F41","F42","F43","F45","F51","F98","Z71","Others"]

    y_true = []
    y_pred_primary = []  # primary+comorbid
    y_pred_top3 = []     # primary+ranked+comorbid

    exact = 0; top1 = 0; top3 = 0
    avg_pred_labels = 0
    for rec in records:
        golds_raw = rec.get("gold_diagnoses") or []
        dx_code = ",".join(str(g) for g in golds_raw if g)
        golds = gold_to_parent_list(dx_code)
        if not golds:
            golds = ["Others"]

        primary = rec.get("primary_diagnosis")
        comorbid = rec.get("comorbid_diagnoses") or []
        codes_pri = pred_to_parent_list(
            ([primary] if primary else []) + list(comorbid)
        )
        if not codes_pri:
            codes_pri = ["Others"]

        # Top-3 list = primary + ranked + comorbid
        ranked = extract_ranked_codes(rec)
        ordered = []
        if primary: ordered.append(primary)
        for r in ranked:
            if r not in ordered: ordered.append(r)
        for c in comorbid:
            if c not in ordered: ordered.append(c)
        codes_t3 = pred_to_parent_list(ordered) or ["Others"]

        y_true.append(golds)
        y_pred_primary.append(codes_pri)
        y_pred_top3.append(codes_t3[:3])
        avg_pred_labels += len(set(codes_pri))

        if set(codes_pri) == set(golds):
            exact += 1
        if codes_pri and codes_pri[0] in set(golds):
            top1 += 1
        if set(codes_t3[:3]) & set(golds):
            top3 += 1

    n = len(records)
    mlb = MultiLabelBinarizer(classes=paper_classes)
    y_true_bin = mlb.fit_transform(y_true)
    y_pred_bin = mlb.transform(y_pred_primary)
    f1_m = f1_score(y_true_bin, y_pred_bin, average="macro", zero_division=0)
    f1_w = f1_score(y_true_bin, y_pred_bin, average="weighted", zero_division=0)

    return {
        "n": n,
        "acc": exact / n,
        "top1": top1 / n,
        "top3_with_ranked": top3 / n,
        "f1_macro": float(f1_m),
        "f1_weighted": float(f1_w),
        "avg_pred_labels": avg_pred_labels / n,
    }


def run_all_strategies(run_dir: Path):
    pred_path = run_dir / "predictions.jsonl"
    records = []
    with pred_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    strategies = [
        ("baseline", None),
        ("drop_all", None),
        ("drop_nos", None),
        ("ratio_threshold", 0.85),
        ("ratio_threshold", 0.90),
        ("ratio_threshold", 0.95),
        ("ratio_threshold", 1.00),
        ("absolute_threshold", 0.8),
        ("absolute_threshold", 0.9),
        ("absolute_threshold", 1.0),
        ("absolute_threshold", 1.1),
        ("top_pair_only", None),
        ("combined", None),
    ]

    print(f"=== {run_dir.name} Comorbid Cap Strategies ===")
    print(f"N = {len(records)}, gold avg labels = 1.091 (target)\n")
    print(
        f"{'Strategy':<28} "
        f"{'AvgLbl':>6} "
        f"{'Acc':>6} "
        f"{'Top1':>6} "
        f"{'Top3':>6} "
        f"{'F1m':>6} "
        f"{'F1w':>6}"
    )
    print("-" * 72)

    results = []
    for name, param in strategies:
        if name == "baseline":
            modded = records
            disp_name = "baseline"
        else:
            modded = [apply_strategy(r, name, param) for r in records]
            disp_name = name if param is None else f"{name}({param})"

        m = evaluate_predictions(modded)
        results.append((disp_name, m, modded))
        print(
            f"{disp_name:<28} "
            f"{m['avg_pred_labels']:>6.2f} "
            f"{m['acc']:>6.3f} "
            f"{m['top1']:>6.3f} "
            f"{m['top3_with_ranked']:>6.3f} "
            f"{m['f1_macro']:>6.3f} "
            f"{m['f1_weighted']:>6.3f}"
        )
    return results


def write_best(run_dir: Path, strategy_name: str, strategy_param, out_suffix: str = "_comorbid_fixed"):
    pred_path = run_dir / "predictions.jsonl"
    records = []
    with pred_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    modded = [apply_strategy(r, strategy_name, strategy_param) for r in records]
    out_dir = run_dir.parent / (run_dir.name + out_suffix)
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "predictions.jsonl"
    with out_path.open("w") as f:
        for r in modded:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Also save a stub metrics.json so recompute_top3 can work on it
    m = evaluate_predictions(modded)
    stub = {
        "note": f"Post-hoc modified from {run_dir.name} with comorbid strategy: "
                f"{strategy_name}({strategy_param})",
        "source_run": run_dir.name,
        "strategy": {"name": strategy_name, "param": strategy_param},
        "table4": {
            "12class_Acc": m["acc"],
            "12class_Top1": m["top1"],
            "12class_Top3": m["top3_with_ranked"],
            "12class_F1_macro": m["f1_macro"],
            "12class_F1_weighted": m["f1_weighted"],
            "12class_n": m["n"],
            # 2c/4c carried over from source if present
        },
        "avg_predicted_labels": m["avg_pred_labels"],
    }
    # Try to copy 2c/4c metrics from source
    src_metrics = run_dir / "metrics.json"
    if src_metrics.exists():
        try:
            src = json.loads(src_metrics.read_text())
            if "table4" in src:
                for k in ("2class_Acc","2class_F1_macro","2class_F1_weighted",
                         "4class_Acc","4class_F1_macro","4class_F1_weighted",
                         "2class_n","4class_n"):
                    if k in src["table4"]:
                        stub["table4"][k] = src["table4"][k]
            # Recompute Overall on full 11 values
            vals = [float(v) for k, v in stub["table4"].items()
                    if not k.endswith("_n") and v is not None]
            if vals:
                stub["table4"]["Overall"] = sum(vals) / len(vals)
        except Exception:
            pass

    (out_dir / "metrics.json").write_text(json.dumps(stub, indent=2, ensure_ascii=False))
    print(f"Wrote modified run to {out_dir}")
    return out_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, default=Path("results/validation/t1_diag_topk"))
    ap.add_argument("--write-best", action="store_true",
                    help="After exploring, write best strategy's predictions to new run dir")
    ap.add_argument("--strategy", default=None, help="Force specific strategy for --write-best")
    ap.add_argument("--param", type=float, default=None)
    args = ap.parse_args()

    results = run_all_strategies(args.run_dir)

    if args.write_best:
        if args.strategy:
            # user override
            sname = args.strategy
            sparam = args.param
        else:
            # pick best: the one that maximizes Overall-proxy
            # proxy = mean(acc, top1, top3, f1m, f1w)
            def proxy(m):
                return (m["acc"] + m["top1"] + m["top3_with_ranked"] +
                        m["f1_macro"] + m["f1_weighted"]) / 5
            best = max(results[1:], key=lambda r: proxy(r[1]))  # skip baseline
            print(f"\nBest strategy by 5-metric mean: {best[0]}")
            # parse name back into strategy + param
            if "(" in best[0]:
                sname, sp = best[0].split("(")
                sparam = float(sp.rstrip(")"))
            else:
                sname = best[0]
                sparam = None
        write_best(args.run_dir, sname, sparam)


if __name__ == "__main__":
    main()
