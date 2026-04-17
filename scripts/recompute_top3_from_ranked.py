#!/usr/bin/env python3
"""Phase 0-A (v3): Surgically patch 12class_Top3 using ranked_codes.

This version reads each run's existing metrics.json and ONLY updates two fields:
  - 12class_Top3: recomputed using decision_trace.diagnostician.ranked_codes[:3]
  - Overall: recomputed as mean of the (patched) 11 Table-4 values

Leaves 2-class / 4-class metrics untouched (those need raw DiagnosisCode from
parquet which isn't available in predictions.jsonl). Leaves 12c_Acc / Top1 /
F1_macro / F1_weighted untouched (those use primary+comorbid, not ranked).

Rationale: Paper's Top-3 metric asks "is a correct diagnosis in the system's
top-3 candidate list". DtV's diagnostician produces a ranked candidate list
that is the natural input to this metric; using only the finalized
primary+comorbid output (which is 1-2 items for DtV) understates the metric.

Usage:
  python3 scripts/recompute_top3_from_ranked.py --all-runs results/validation
  python3 scripts/recompute_top3_from_ranked.py --run-dir results/validation/t1_diag_topk
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from culturedx.eval.lingxidiag_paper import (
    pred_to_parent_list,
    gold_to_parent_list,
)

logger = logging.getLogger(__name__)


def extract_ranked_codes(rec: dict) -> list[str]:
    dt = rec.get("decision_trace") or {}
    if isinstance(dt, dict):
        diag = dt.get("diagnostician")
        if isinstance(diag, dict):
            ranked = diag.get("ranked_codes")
            if ranked:
                return [c for c in ranked if c]
        ranked = dt.get("diagnostician_ranked")
        if ranked:
            return [c for c in ranked if c]
    for key in ("ranked_codes", "ranked_diagnoses"):
        v = rec.get(key)
        if v:
            if isinstance(v[0], str):
                return [c for c in v if c]
            if isinstance(v[0], dict):
                return [item.get("code", "") for item in v if item.get("code")]
    return []


def build_top3_codes(rec: dict) -> list[str]:
    """Top-3 list: primary first, then ranked (dedup), then comorbid (dedup)."""
    primary = rec.get("primary_diagnosis")
    ranked = extract_ranked_codes(rec)
    comorbid = rec.get("comorbid_diagnoses") or []

    ordered = []
    if primary:
        ordered.append(primary)
    for r in ranked:
        if r not in ordered:
            ordered.append(r)
    for c in comorbid:
        if c not in ordered:
            ordered.append(c)
    return pred_to_parent_list(ordered)


def compute_top3(run_dir: Path) -> tuple[float, float, int, int]:
    """Returns (top3_primary_only, top3_with_ranked, n, n_with_ranked)."""
    pred_path = run_dir / "predictions.jsonl"
    hits_pri = 0
    hits_rank = 0
    n = 0
    n_with_ranked = 0
    with pred_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)

            # Gold parsing: reconstruct DiagnosisCode from gold_diagnoses field
            golds_raw = rec.get("gold_diagnoses") or []
            dx_code = ",".join(str(g) for g in golds_raw if g)
            golds = set(gold_to_parent_list(dx_code))
            if not golds:
                golds = {"Others"}

            # Method A: primary+comorbid only (canonical)
            primary = rec.get("primary_diagnosis")
            comorbid = rec.get("comorbid_diagnoses") or []
            codes_pri = pred_to_parent_list(
                ([primary] if primary else []) + list(comorbid)
            )
            if set(codes_pri[:3]) & golds:
                hits_pri += 1

            # Method B: include ranked_codes
            codes_rank = build_top3_codes(rec)
            if set(codes_rank[:3]) & golds:
                hits_rank += 1

            ranked = extract_ranked_codes(rec)
            if len(ranked) >= 2:
                n_with_ranked += 1
            n += 1

    return (
        hits_pri / n if n else 0.0,
        hits_rank / n if n else 0.0,
        n,
        n_with_ranked,
    )


def patch_metrics_json(run_dir: Path, write: bool = True) -> dict | None:
    metrics_path = run_dir / "metrics.json"
    if not metrics_path.exists():
        logger.warning("No metrics.json in %s", run_dir)
        return None

    try:
        metrics = json.loads(metrics_path.read_text())
    except json.JSONDecodeError as e:
        logger.warning("Corrupt metrics.json in %s: %s", run_dir, e)
        return None

    table4 = metrics.get("table4")
    if not isinstance(table4, dict):
        logger.warning("No table4 in %s/metrics.json", run_dir)
        return None

    top3_pri, top3_rank, n, n_with_ranked = compute_top3(run_dir)

    # Build patched table4
    table4_new = dict(table4)
    table4_new["12class_Top3"] = top3_rank

    # Recompute Overall (mean of all non-_n fields except Overall itself)
    vals = [
        float(v)
        for k, v in table4_new.items()
        if not k.endswith("_n") and k != "Overall" and v is not None
    ]
    table4_new["Overall"] = sum(vals) / len(vals) if vals else None

    patched = {
        "n_cases": n,
        "n_cases_with_ranked_codes": n_with_ranked,
        "pct_with_ranked": round(n_with_ranked / n * 100, 1) if n else 0,
        "note": (
            "Top-3 uses diagnostician's ranked_codes[:3] when available; "
            "all other metrics unchanged from metrics.json."
        ),
        "top3_primary_only_recomputed": top3_pri,
        "top3_ranked_recomputed": top3_rank,
        "top3_original_from_metrics_json": table4.get("12class_Top3"),
        "table4_original": table4,
        "table4": table4_new,
    }

    if write:
        out_path = run_dir / "metrics_v2.json"
        out_path.write_text(json.dumps(patched, indent=2, ensure_ascii=False))
        logger.info("Wrote %s", out_path)

    return patched


def summarise(report: dict, name: str) -> str:
    t_o = report["table4_original"]
    t_n = report["table4"]
    d3 = (t_n["12class_Top3"] - t_o["12class_Top3"]) * 100
    dov = (t_n["Overall"] - t_o["Overall"]) * 100
    cov = report["pct_with_ranked"]
    return (
        f"{name:<36} "
        f"cov={cov:5.1f}% | "
        f"Top-3 {t_o['12class_Top3']:.3f} -> {t_n['12class_Top3']:.3f} "
        f"(Δ{d3:+5.1f}pp) | "
        f"Overall {t_o['Overall']:.3f} -> {t_n['Overall']:.3f} "
        f"(Δ{dov:+.2f}pp)"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path)
    ap.add_argument("--all-runs", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.run_dir:
        report = patch_metrics_json(args.run_dir, write=not args.dry_run)
        if report:
            print(summarise(report, args.run_dir.name))
        return

    if args.all_runs:
        rows = []
        for sub in sorted(args.all_runs.iterdir()):
            if not sub.is_dir() or not (sub / "predictions.jsonl").exists():
                continue
            try:
                report = patch_metrics_json(sub, write=not args.dry_run)
                if report:
                    rows.append((sub.name, report))
            except Exception as e:
                logger.warning("Skipping %s: %s", sub.name, e)

        rows.sort(key=lambda r: -r[1]["table4"]["Overall"])
        print(f"{'Run':<36} {'cov':>7} | {'Top-3':<34} {'Overall':<28}")
        print("-" * 115)
        for name, report in rows:
            print(summarise(report, name))
        return

    ap.print_help()


if __name__ == "__main__":
    main()
