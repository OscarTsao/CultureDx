#!/usr/bin/env python3
"""Cross-lingual evidence gap analysis across the 18-condition sweep.

Compares evidence vs no_evidence vs no_somatization on LingxiDiag (Chinese)
and MDD-5k (Chinese-translated), quantifying where evidence grounding helps
and where it hurts.

Usage:
    uv run python scripts/analyze_evidence_gap.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LINGXI_SWEEP = PROJECT_ROOT / "outputs" / "sweeps" / "final_lingxidiag_20260323_131847"
MDD5K_SWEEP = PROJECT_ROOT / "outputs" / "sweeps" / "final_mdd5k_20260324_120113"

OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_JSON = OUTPUT_DIR / "evidence_gap_analysis.json"
OUTPUT_MD = OUTPUT_DIR / "evidence_gap_analysis.md"

MODES = ["hied", "psycot", "single"]
EVIDENCE_VARIANTS = ["no_evidence", "bge-m3_evidence", "bge-m3_no_somatization"]

DATASETS = {
    "LingxiDiag": LINGXI_SWEEP,
    "MDD-5k": MDD5K_SWEEP,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def normalize_icd(code: str) -> str:
    """F41.1 -> F41, F32.901 -> F32."""
    return code.split(".")[0]


def load_case_list(sweep_dir: Path) -> dict[str, list[str]]:
    """Return {case_id: [gold_labels_parent_normalized]}."""
    data = json.loads((sweep_dir / "case_list.json").read_text(encoding="utf-8"))
    result: dict[str, list[str]] = {}
    for case in data["cases"]:
        result[case["case_id"]] = [normalize_icd(d) for d in case["diagnoses"]]
    return result


def load_predictions(sweep_dir: Path, condition: str) -> dict[str, dict]:
    """Return {case_id: prediction_record} for a condition."""
    pred_file = sweep_dir / condition / "predictions.json"
    data = json.loads(pred_file.read_text(encoding="utf-8"))
    return {p["case_id"]: p for p in data["predictions"]}


def load_metrics(sweep_dir: Path, condition: str) -> dict:
    """Return metrics dict for a condition."""
    metrics_file = sweep_dir / condition / "metrics.json"
    return json.loads(metrics_file.read_text(encoding="utf-8"))


def pred_labels(pred: dict) -> list[str]:
    """Extract ordered list of predicted diagnoses (parent-normalized)."""
    raw_primary = pred.get("primary_diagnosis")
    if raw_primary is None:
        # Abstained or failed prediction
        return ["ABSTAIN"]
    primary = normalize_icd(raw_primary)
    comorbids = [
        normalize_icd(c) for c in pred.get("comorbid_diagnoses", []) if c is not None
    ]
    # Deduplicate while preserving order
    seen = {primary}
    result = [primary]
    for c in comorbids:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result


def is_top1_correct(pred_list: list[str], gold_list: list[str]) -> bool:
    """Top-1 accuracy: primary prediction matches any gold label."""
    return pred_list[0] in set(gold_list) if pred_list else False


def is_top3_correct(pred_list: list[str], gold_list: list[str]) -> bool:
    """Top-3 accuracy: any of top-3 predictions matches any gold label."""
    return bool(set(pred_list[:3]) & set(gold_list))


def primary_gold(gold_list: list[str]) -> str:
    """Return the first gold label (primary diagnosis)."""
    return gold_list[0] if gold_list else "unknown"


# ---------------------------------------------------------------------------
# 1. Evidence delta analysis
# ---------------------------------------------------------------------------
def compute_evidence_deltas(datasets: dict[str, Path]) -> dict:
    """Compute delta(evidence vs no_evidence) and delta(evidence vs no_somatization)."""
    results: dict[str, dict] = {}

    for ds_name, sweep_dir in datasets.items():
        results[ds_name] = {}
        for mode in MODES:
            cond_ev = f"{mode}_bge-m3_evidence"
            cond_no = f"{mode}_no_evidence"
            cond_ns = f"{mode}_bge-m3_no_somatization"

            m_ev = load_metrics(sweep_dir, cond_ev)
            m_no = load_metrics(sweep_dir, cond_no)
            m_ns = load_metrics(sweep_dir, cond_ns)

            mp_ev = m_ev["metrics_parent_normalized"]
            mp_no = m_no["metrics_parent_normalized"]
            mp_ns = m_ns["metrics_parent_normalized"]

            delta_ev_no = {
                k: round(mp_ev[k] - mp_no[k], 4) for k in mp_ev
            }
            delta_ev_ns = {
                k: round(mp_ev[k] - mp_ns[k], 4) for k in mp_ev
            }

            results[ds_name][mode] = {
                "evidence": mp_ev,
                "no_evidence": mp_no,
                "no_somatization": mp_ns,
                "delta_evidence_vs_no_evidence": delta_ev_no,
                "delta_evidence_vs_no_somatization": delta_ev_ns,
            }

    return results


# ---------------------------------------------------------------------------
# 2. Per-disorder breakdown
# ---------------------------------------------------------------------------
def compute_per_disorder_accuracy(
    datasets: dict[str, Path],
) -> dict:
    """Per-disorder top-1 accuracy for each condition."""
    results: dict[str, dict] = {}

    for ds_name, sweep_dir in datasets.items():
        gold_map = load_case_list(sweep_dir)
        results[ds_name] = {}

        for mode in MODES:
            results[ds_name][mode] = {}
            for variant in EVIDENCE_VARIANTS:
                condition = f"{mode}_{variant}"
                preds = load_predictions(sweep_dir, condition)

                disorder_correct: dict[str, int] = defaultdict(int)
                disorder_total: dict[str, int] = defaultdict(int)

                for case_id, gold_list in gold_map.items():
                    if case_id not in preds:
                        continue
                    pred = preds[case_id]
                    pl = pred_labels(pred)
                    pg = primary_gold(gold_list)

                    disorder_total[pg] += 1
                    if is_top1_correct(pl, gold_list):
                        disorder_correct[pg] += 1

                disorder_acc: dict[str, dict] = {}
                for d in sorted(disorder_total.keys()):
                    total = disorder_total[d]
                    correct = disorder_correct[d]
                    disorder_acc[d] = {
                        "correct": correct,
                        "total": total,
                        "accuracy": round(correct / total, 4) if total > 0 else 0.0,
                    }

                results[ds_name][mode][variant] = disorder_acc

    return results


# ---------------------------------------------------------------------------
# 3. Flip analysis
# ---------------------------------------------------------------------------
def compute_flip_analysis(datasets: dict[str, Path]) -> dict:
    """Compare evidence vs no_evidence prediction flips per case."""
    results: dict[str, dict] = {}

    for ds_name, sweep_dir in datasets.items():
        gold_map = load_case_list(sweep_dir)
        results[ds_name] = {}

        for mode in MODES:
            cond_ev = f"{mode}_bge-m3_evidence"
            cond_no = f"{mode}_no_evidence"

            preds_ev = load_predictions(sweep_dir, cond_ev)
            preds_no = load_predictions(sweep_dir, cond_no)

            good_flips: dict[str, int] = defaultdict(int)
            bad_flips: dict[str, int] = defaultdict(int)
            stable_correct: dict[str, int] = defaultdict(int)
            stable_wrong: dict[str, int] = defaultdict(int)
            total_by_disorder: dict[str, int] = defaultdict(int)

            for case_id, gold_list in gold_map.items():
                if case_id not in preds_ev or case_id not in preds_no:
                    continue

                pl_ev = pred_labels(preds_ev[case_id])
                pl_no = pred_labels(preds_no[case_id])

                correct_ev = is_top1_correct(pl_ev, gold_list)
                correct_no = is_top1_correct(pl_no, gold_list)
                pg = primary_gold(gold_list)

                total_by_disorder[pg] += 1

                if correct_no and correct_ev:
                    stable_correct[pg] += 1
                elif not correct_no and correct_ev:
                    good_flips[pg] += 1
                elif correct_no and not correct_ev:
                    bad_flips[pg] += 1
                else:
                    stable_wrong[pg] += 1

            all_disorders = sorted(total_by_disorder.keys())
            flip_breakdown: dict[str, dict] = {}
            for d in all_disorders:
                flip_breakdown[d] = {
                    "total": total_by_disorder[d],
                    "good_flips_wrong_to_right": good_flips.get(d, 0),
                    "bad_flips_right_to_wrong": bad_flips.get(d, 0),
                    "stable_correct": stable_correct.get(d, 0),
                    "stable_wrong": stable_wrong.get(d, 0),
                }

            total_good = sum(good_flips.values())
            total_bad = sum(bad_flips.values())
            total_stable_c = sum(stable_correct.values())
            total_stable_w = sum(stable_wrong.values())
            total_cases = sum(total_by_disorder.values())

            results[ds_name][mode] = {
                "summary": {
                    "total_cases": total_cases,
                    "good_flips": total_good,
                    "bad_flips": total_bad,
                    "stable_correct": total_stable_c,
                    "stable_wrong": total_stable_w,
                    "net_flip": total_good - total_bad,
                },
                "by_disorder": flip_breakdown,
            }

    return results


# ---------------------------------------------------------------------------
# 4. Somatization contribution
# ---------------------------------------------------------------------------
def compute_somatization_contribution(datasets: dict[str, Path]) -> dict:
    """Compare evidence vs no_somatization to isolate somatization effect."""
    results: dict[str, dict] = {}

    for ds_name, sweep_dir in datasets.items():
        gold_map = load_case_list(sweep_dir)
        results[ds_name] = {}

        for mode in MODES:
            cond_ev = f"{mode}_bge-m3_evidence"
            cond_ns = f"{mode}_bge-m3_no_somatization"

            preds_ev = load_predictions(sweep_dir, cond_ev)
            preds_ns = load_predictions(sweep_dir, cond_ns)

            ev_correct = 0
            ns_correct = 0
            total = 0

            ev_disorder_correct: dict[str, int] = defaultdict(int)
            ns_disorder_correct: dict[str, int] = defaultdict(int)
            disorder_total: dict[str, int] = defaultdict(int)

            good_flips: dict[str, int] = defaultdict(int)
            bad_flips: dict[str, int] = defaultdict(int)

            for case_id, gold_list in gold_map.items():
                if case_id not in preds_ev or case_id not in preds_ns:
                    continue

                pl_ev = pred_labels(preds_ev[case_id])
                pl_ns = pred_labels(preds_ns[case_id])
                pg = primary_gold(gold_list)
                total += 1
                disorder_total[pg] += 1

                c_ev = is_top1_correct(pl_ev, gold_list)
                c_ns = is_top1_correct(pl_ns, gold_list)

                if c_ev:
                    ev_correct += 1
                    ev_disorder_correct[pg] += 1
                if c_ns:
                    ns_correct += 1
                    ns_disorder_correct[pg] += 1

                if not c_ns and c_ev:
                    good_flips[pg] += 1
                elif c_ns and not c_ev:
                    bad_flips[pg] += 1

            all_disorders = sorted(disorder_total.keys())
            per_disorder: dict[str, dict] = {}
            for d in all_disorders:
                dt = disorder_total[d]
                ev_acc = ev_disorder_correct.get(d, 0) / dt if dt > 0 else 0.0
                ns_acc = ns_disorder_correct.get(d, 0) / dt if dt > 0 else 0.0
                per_disorder[d] = {
                    "total": dt,
                    "evidence_accuracy": round(ev_acc, 4),
                    "no_somatization_accuracy": round(ns_acc, 4),
                    "somatization_delta_pp": round((ev_acc - ns_acc) * 100, 2),
                    "good_flips": good_flips.get(d, 0),
                    "bad_flips": bad_flips.get(d, 0),
                }

            ev_acc_overall = ev_correct / total if total > 0 else 0.0
            ns_acc_overall = ns_correct / total if total > 0 else 0.0

            results[ds_name][mode] = {
                "summary": {
                    "total_cases": total,
                    "evidence_top1": round(ev_acc_overall, 4),
                    "no_somatization_top1": round(ns_acc_overall, 4),
                    "somatization_delta_pp": round(
                        (ev_acc_overall - ns_acc_overall) * 100, 2
                    ),
                    "total_good_flips": sum(good_flips.values()),
                    "total_bad_flips": sum(bad_flips.values()),
                },
                "by_disorder": per_disorder,
            }

    return results


# ---------------------------------------------------------------------------
# 5. Generate markdown report
# ---------------------------------------------------------------------------
def generate_markdown(
    deltas: dict,
    per_disorder: dict,
    flips: dict,
    somatization: dict,
) -> str:
    """Generate a readable markdown summary."""
    lines: list[str] = []
    lines.append("# Cross-Lingual Evidence Gap Analysis")
    lines.append("")
    lines.append("18-condition sweep: 3 modes x 3 evidence variants x 2 datasets.")
    lines.append("")

    # --- Section 1: Evidence delta summary ---
    lines.append("## 1. Evidence Delta Summary (parent-normalized Top-1)")
    lines.append("")
    lines.append(
        "| Dataset | Mode | No Evidence | + Evidence | + Ev (no somat) "
        "| Delta(ev-no) | Delta(ev-ns) |"
    )
    lines.append(
        "|---------|------|-------------|------------|-----------------|"
        "--------------|--------------|"
    )

    for ds_name in ["LingxiDiag", "MDD-5k"]:
        for mode in MODES:
            d = deltas[ds_name][mode]
            no_ev = d["no_evidence"]["top1_accuracy"]
            ev = d["evidence"]["top1_accuracy"]
            ns = d["no_somatization"]["top1_accuracy"]
            delta_ev_no = d["delta_evidence_vs_no_evidence"]["top1_accuracy"]
            delta_ev_ns = d["delta_evidence_vs_no_somatization"]["top1_accuracy"]

            sign_eno = "+" if delta_ev_no >= 0 else ""
            sign_ens = "+" if delta_ev_ns >= 0 else ""

            lines.append(
                f"| {ds_name} | {mode} | {no_ev:.3f} | {ev:.3f} | {ns:.3f} "
                f"| {sign_eno}{delta_ev_no * 100:.1f}pp "
                f"| {sign_ens}{delta_ev_ns * 100:.1f}pp |"
            )

    lines.append("")

    # --- Section 1b: Average deltas ---
    lines.append("### Average delta across modes")
    lines.append("")
    lines.append(
        "| Dataset | Avg Delta(evidence vs none) Top-1 "
        "| Avg Delta(evidence vs no_somat) Top-1 |"
    )
    lines.append(
        "|---------|-----------------------------------"
        "|---------------------------------------|"
    )
    for ds_name in ["LingxiDiag", "MDD-5k"]:
        avg_delta_eno = sum(
            deltas[ds_name][m]["delta_evidence_vs_no_evidence"]["top1_accuracy"]
            for m in MODES
        ) / len(MODES)
        avg_delta_ens = sum(
            deltas[ds_name][m]["delta_evidence_vs_no_somatization"]["top1_accuracy"]
            for m in MODES
        ) / len(MODES)
        s1 = "+" if avg_delta_eno >= 0 else ""
        s2 = "+" if avg_delta_ens >= 0 else ""
        lines.append(
            f"| {ds_name} | {s1}{avg_delta_eno * 100:.1f}pp "
            f"| {s2}{avg_delta_ens * 100:.1f}pp |"
        )
    lines.append("")

    # --- Section 2: Per-disorder accuracy (HiED, the primary mode) ---
    lines.append("## 2. Per-Disorder Top-1 Accuracy (HiED mode)")
    lines.append("")

    for ds_name in ["LingxiDiag", "MDD-5k"]:
        lines.append(f"### {ds_name}")
        lines.append("")
        lines.append(
            "| Disorder | N | No Evidence | + Evidence "
            "| + Ev (no somat) | Delta(ev-no) |"
        )
        lines.append(
            "|----------|---|-------------|------------"
            "|-----------------|--------------|"
        )

        pd_data = per_disorder[ds_name]["hied"]
        all_d: set[str] = set()
        for variant in EVIDENCE_VARIANTS:
            all_d.update(pd_data[variant].keys())

        for disorder in sorted(all_d):
            no_ev = pd_data["no_evidence"].get(disorder, {})
            ev = pd_data["bge-m3_evidence"].get(disorder, {})
            ns = pd_data["bge-m3_no_somatization"].get(disorder, {})

            n = no_ev.get("total", ev.get("total", 0))
            if n == 0:
                continue
            acc_no = no_ev.get("accuracy", 0.0)
            acc_ev = ev.get("accuracy", 0.0)
            acc_ns = ns.get("accuracy", 0.0)
            delta = acc_ev - acc_no

            sign = "+" if delta >= 0 else ""
            lines.append(
                f"| {disorder} | {n} | {acc_no:.3f} | {acc_ev:.3f} "
                f"| {acc_ns:.3f} | {sign}{delta * 100:.1f}pp |"
            )
        lines.append("")

    # --- Section 3: Flip analysis ---
    lines.append("## 3. Prediction Flip Analysis (evidence vs no_evidence)")
    lines.append("")
    lines.append(
        "Good flip = wrong->right with evidence. "
        "Bad flip = right->wrong with evidence."
    )
    lines.append("")

    lines.append("### Summary")
    lines.append("")
    lines.append(
        "| Dataset | Mode | Good Flips | Bad Flips "
        "| Net | Stable Correct | Stable Wrong |"
    )
    lines.append(
        "|---------|------|------------|-----------|"
        "-----|----------------|--------------|"
    )
    for ds_name in ["LingxiDiag", "MDD-5k"]:
        for mode in MODES:
            s = flips[ds_name][mode]["summary"]
            lines.append(
                f"| {ds_name} | {mode} | {s['good_flips']} | {s['bad_flips']} "
                f"| {s['net_flip']:+d} | {s['stable_correct']} | {s['stable_wrong']} |"
            )
    lines.append("")

    # Flip detail by disorder (HiED only, both datasets)
    lines.append("### Per-disorder flips (HiED mode)")
    lines.append("")
    for ds_name in ["LingxiDiag", "MDD-5k"]:
        lines.append(f"#### {ds_name}")
        lines.append("")
        lines.append("| Disorder | N | Good | Bad | Net | Stable-R | Stable-W |")
        lines.append("|----------|---|------|-----|-----|----------|----------|")
        by_d = flips[ds_name]["hied"]["by_disorder"]
        for disorder in sorted(by_d.keys()):
            dd = by_d[disorder]
            net = dd["good_flips_wrong_to_right"] - dd["bad_flips_right_to_wrong"]
            lines.append(
                f"| {disorder} | {dd['total']} "
                f"| {dd['good_flips_wrong_to_right']} "
                f"| {dd['bad_flips_right_to_wrong']} "
                f"| {net:+d} "
                f"| {dd['stable_correct']} "
                f"| {dd['stable_wrong']} |"
            )
        lines.append("")

    # --- Section 4: Somatization contribution ---
    lines.append("## 4. Somatization Mapper Contribution")
    lines.append("")
    lines.append(
        "Compares full evidence (with somatization) vs evidence "
        "without somatization mapper."
    )
    lines.append("")

    lines.append("### Summary")
    lines.append("")
    lines.append(
        "| Dataset | Mode | Ev+Somat Top-1 | Ev-Somat Top-1 "
        "| Somat Delta | Good Flips | Bad Flips |"
    )
    lines.append(
        "|---------|------|----------------|---------------- "
        "|-------------|------------|-----------|"
    )
    for ds_name in ["LingxiDiag", "MDD-5k"]:
        for mode in MODES:
            s = somatization[ds_name][mode]["summary"]
            sign = "+" if s["somatization_delta_pp"] >= 0 else ""
            lines.append(
                f"| {ds_name} | {mode} "
                f"| {s['evidence_top1']:.3f} "
                f"| {s['no_somatization_top1']:.3f} "
                f"| {sign}{s['somatization_delta_pp']:.1f}pp "
                f"| {s['total_good_flips']} "
                f"| {s['total_bad_flips']} |"
            )
    lines.append("")

    # Per-disorder somatization (HiED)
    lines.append("### Per-disorder somatization effect (HiED mode)")
    lines.append("")
    for ds_name in ["LingxiDiag", "MDD-5k"]:
        lines.append(f"#### {ds_name}")
        lines.append("")
        lines.append(
            "| Disorder | N | Ev+Somat | Ev-Somat | Delta | Good | Bad |"
        )
        lines.append(
            "|----------|---|----------|----------|-------|------|-----|"
        )
        by_d = somatization[ds_name]["hied"]["by_disorder"]
        for disorder in sorted(by_d.keys()):
            dd = by_d[disorder]
            sign = "+" if dd["somatization_delta_pp"] >= 0 else ""
            lines.append(
                f"| {disorder} | {dd['total']} "
                f"| {dd['evidence_accuracy']:.3f} "
                f"| {dd['no_somatization_accuracy']:.3f} "
                f"| {sign}{dd['somatization_delta_pp']:.1f}pp "
                f"| {dd['good_flips']} "
                f"| {dd['bad_flips']} |"
            )
        lines.append("")

    # --- Section 5: Key findings ---
    lines.append("## 5. Key Findings")
    lines.append("")

    lingxi_hied_delta = (
        deltas["LingxiDiag"]["hied"]["delta_evidence_vs_no_evidence"]["top1_accuracy"]
    )
    mdd5k_hied_delta = (
        deltas["MDD-5k"]["hied"]["delta_evidence_vs_no_evidence"]["top1_accuracy"]
    )
    lingxi_somat_delta = (
        somatization["LingxiDiag"]["hied"]["summary"]["somatization_delta_pp"]
    )
    mdd5k_somat_delta = (
        somatization["MDD-5k"]["hied"]["summary"]["somatization_delta_pp"]
    )

    lines.append(
        f"1. **Evidence helps LingxiDiag but hurts MDD-5k (HiED Top-1):** "
        f"LingxiDiag {lingxi_hied_delta*100:+.1f}pp, "
        f"MDD-5k {mdd5k_hied_delta*100:+.1f}pp."
    )

    lingxi_avg = sum(
        deltas["LingxiDiag"][m]["delta_evidence_vs_no_evidence"]["top1_accuracy"]
        for m in MODES
    ) / len(MODES)
    mdd5k_avg = sum(
        deltas["MDD-5k"][m]["delta_evidence_vs_no_evidence"]["top1_accuracy"]
        for m in MODES
    ) / len(MODES)
    lines.append(
        f"2. **Average across modes:** "
        f"LingxiDiag {lingxi_avg*100:+.1f}pp, MDD-5k {mdd5k_avg*100:+.1f}pp."
    )

    lines.append(
        f"3. **Somatization mapper (HiED):** "
        f"LingxiDiag {lingxi_somat_delta:+.1f}pp, "
        f"MDD-5k {mdd5k_somat_delta:+.1f}pp."
    )

    lingxi_net = flips["LingxiDiag"]["hied"]["summary"]["net_flip"]
    mdd5k_net = flips["MDD-5k"]["hied"]["summary"]["net_flip"]
    lines.append(
        f"4. **Net prediction flips (HiED evidence vs none):** "
        f"LingxiDiag {lingxi_net:+d}, MDD-5k {mdd5k_net:+d}."
    )

    # Identify most helped/hurt disorders
    lines.append("")
    lines.append("### Disorders most affected by evidence (HiED, |delta| >= 5pp)")
    lines.append("")
    lines.append("| Dataset | Disorder | N | Delta(ev-no) | Direction |")
    lines.append("|---------|----------|---|--------------|-----------|")
    for ds_name in ["LingxiDiag", "MDD-5k"]:
        pd_data = per_disorder[ds_name]["hied"]
        all_d: set[str] = set()
        for v in EVIDENCE_VARIANTS:
            all_d.update(pd_data[v].keys())
        for disorder in sorted(all_d):
            no_ev = pd_data["no_evidence"].get(disorder, {})
            ev = pd_data["bge-m3_evidence"].get(disorder, {})
            n = no_ev.get("total", 0)
            if n < 3:
                continue
            acc_no = no_ev.get("accuracy", 0.0)
            acc_ev = ev.get("accuracy", 0.0)
            delta = acc_ev - acc_no
            if abs(delta) >= 0.05:
                direction = "HELPED" if delta > 0 else "HURT"
                lines.append(
                    f"| {ds_name} | {disorder} | {n} "
                    f"| {delta*100:+.1f}pp | {direction} |"
                )
    lines.append("")

    # Top-3 gap
    lines.append("### Top-3 accuracy gap")
    lines.append("")
    lines.append(
        "| Dataset | Mode | No Evidence Top-3 | + Evidence Top-3 | Delta |"
    )
    lines.append(
        "|---------|------|-------------------|------------------|-------|"
    )
    for ds_name in ["LingxiDiag", "MDD-5k"]:
        for mode in MODES:
            d = deltas[ds_name][mode]
            no_t3 = d["no_evidence"]["top3_accuracy"]
            ev_t3 = d["evidence"]["top3_accuracy"]
            delta_t3 = d["delta_evidence_vs_no_evidence"]["top3_accuracy"]
            sign = "+" if delta_t3 >= 0 else ""
            lines.append(
                f"| {ds_name} | {mode} | {no_t3:.3f} "
                f"| {ev_t3:.3f} | {sign}{delta_t3*100:.1f}pp |"
            )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    # Validate paths
    for ds_name, sweep_dir in DATASETS.items():
        if not sweep_dir.exists():
            print(f"ERROR: sweep directory not found: {sweep_dir}", file=sys.stderr)
            sys.exit(1)
        for mode in MODES:
            for variant in EVIDENCE_VARIANTS:
                condition = f"{mode}_{variant}"
                cond_dir = sweep_dir / condition
                if not cond_dir.exists():
                    print(
                        f"ERROR: condition directory not found: {cond_dir}",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                for fname in ["predictions.json", "metrics.json"]:
                    if not (cond_dir / fname).exists():
                        print(
                            f"ERROR: missing {fname} in {cond_dir}",
                            file=sys.stderr,
                        )
                        sys.exit(1)

    print("Computing evidence deltas...")
    deltas = compute_evidence_deltas(DATASETS)

    print("Computing per-disorder accuracy...")
    per_disorder = compute_per_disorder_accuracy(DATASETS)

    print("Computing flip analysis...")
    flips = compute_flip_analysis(DATASETS)

    print("Computing somatization contribution...")
    somatization = compute_somatization_contribution(DATASETS)

    # Assemble full results
    full_results = {
        "evidence_deltas": deltas,
        "per_disorder_accuracy": per_disorder,
        "flip_analysis": flips,
        "somatization_contribution": somatization,
    }

    # Save JSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(full_results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Saved JSON: {OUTPUT_JSON}")

    # Generate and save markdown
    md = generate_markdown(deltas, per_disorder, flips, somatization)
    OUTPUT_MD.write_text(md, encoding="utf-8")
    print(f"Saved markdown: {OUTPUT_MD}")

    # Print headline findings
    print("\n" + "=" * 70)
    print("HEADLINE FINDINGS")
    print("=" * 70)
    for ds_name in ["LingxiDiag", "MDD-5k"]:
        print(f"\n--- {ds_name} ---")
        for mode in MODES:
            d = deltas[ds_name][mode]
            delta_eno = d["delta_evidence_vs_no_evidence"]["top1_accuracy"]
            delta_ens = d["delta_evidence_vs_no_somatization"]["top1_accuracy"]
            print(
                f"  {mode:8s}  ev-vs-no: {delta_eno*100:+5.1f}pp  "
                f"somat-contrib: {delta_ens*100:+5.1f}pp"
            )
        s = somatization[ds_name]["hied"]["summary"]
        print(
            f"  Somatization mapper (HiED): "
            f"{s['somatization_delta_pp']:+.1f}pp"
        )

    hied_lingxi = flips["LingxiDiag"]["hied"]["summary"]
    hied_mdd5k = flips["MDD-5k"]["hied"]["summary"]
    print(
        f"\nHiED Flips: LingxiDiag good={hied_lingxi['good_flips']} "
        f"bad={hied_lingxi['bad_flips']} net={hied_lingxi['net_flip']:+d}"
    )
    print(
        f"HiED Flips: MDD-5k    good={hied_mdd5k['good_flips']} "
        f"bad={hied_mdd5k['bad_flips']} net={hied_mdd5k['net_flip']:+d}"
    )


if __name__ == "__main__":
    main()
