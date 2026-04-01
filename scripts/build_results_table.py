#!/usr/bin/env python3
"""Build comprehensive paper results tables from the 18-condition sweep data.

Loads metrics.json from both LingxiDiag and MDD-5k sweeps, constructs
Markdown and LaTeX tables for inclusion in the paper.
"""

import json
from pathlib import Path
from collections import OrderedDict

# ── Configuration ──────────────────────────────────────────────────────
SWEEPS = OrderedDict([
    ("LingxiDiag-16k", Path("outputs/sweeps/final_lingxidiag_20260323_131847")),
    ("MDD-5k",         Path("outputs/sweeps/final_mdd5k_20260324_120113")),
])

CONDITIONS = [
    "single_no_evidence",
    "single_bge-m3_evidence",
    "single_bge-m3_no_somatization",
    "hied_no_evidence",
    "hied_bge-m3_evidence",
    "hied_bge-m3_no_somatization",
    "psycot_no_evidence",
    "psycot_bge-m3_evidence",
    "psycot_bge-m3_no_somatization",
]

# Pretty names for the paper
MODE_LABELS = {
    "single": "Single-Agent",
    "hied": "HiED (Hierarchical)",
    "psycot": "PsyCoT (Chain-of-Thought)",
}

EVIDENCE_LABELS = {
    "no_evidence": "None",
    "bge-m3_evidence": "BGE-M3",
    "bge-m3_no_somatization": "BGE-M3 (no somat.)",
}

# Metric display names and which nested dict they come from
METRICS = [
    ("Top-1 Acc", "metrics_parent_normalized", "top1_accuracy"),
    ("Top-3 Acc", "metrics_parent_normalized", "top3_accuracy"),
    ("Macro F1",  "metrics_parent_normalized", "macro_f1"),
    ("Weighted F1", "metrics_parent_normalized", "weighted_f1"),
    ("Top-1 Acc (exact)", "metrics_exact", "top1_accuracy"),
    ("Top-3 Acc (exact)", "metrics_exact", "top3_accuracy"),
    ("Macro F1 (exact)",  "metrics_exact", "macro_f1"),
    ("Weighted F1 (exact)", "metrics_exact", "weighted_f1"),
]

# ── Load data ──────────────────────────────────────────────────────────
data = {}  # (dataset, condition) -> metrics dict
for ds_name, ds_path in SWEEPS.items():
    for cond in CONDITIONS:
        mf = ds_path / cond / "metrics.json"
        with open(mf) as f:
            data[(ds_name, cond)] = json.load(f)


def parse_condition(cond):
    """Return (mode, evidence_key) from a condition name."""
    parts = cond.split("_", 1)
    return parts[0], parts[1]


def fmt(val):
    """Format a metric value as a percentage string."""
    return f"{val*100:.1f}"


def fmt_bold(val, is_best):
    """Format with bold for markdown if best in column."""
    s = fmt(val)
    return f"**{s}**" if is_best else s


# ── Identify best values per column ───────────────────────────────────
# For each (dataset, metric), find the maximum across all 9 conditions
best = {}
for ds_name in SWEEPS:
    for disp_name, nest_key, metric_key in METRICS:
        col_key = (ds_name, disp_name)
        vals = []
        for cond in CONDITIONS:
            v = data[(ds_name, cond)][nest_key][metric_key]
            vals.append(v)
        best[col_key] = max(vals)


# ── Build Markdown table ──────────────────────────────────────────────
lines = []
lines.append("# CultureDx: 18-Condition Sweep Results (N=200 per condition)")
lines.append("")
lines.append("## Table 1: Parent-Normalized Metrics")
lines.append("")

# Header
pn_metrics = [m for m in METRICS if m[1] == "metrics_parent_normalized"]
header_parts = ["| Mode | Evidence"]
for ds_name in SWEEPS:
    for disp_name, _, _ in pn_metrics:
        header_parts.append(f" {ds_name} {disp_name}")
header_parts.append(" |")
header = " |".join(header_parts)
lines.append(header)

# Separator
sep_parts = ["| :--- | :---"]
for _ in SWEEPS:
    for _ in pn_metrics:
        sep_parts.append(" ---:")
sep_parts.append(" |")
sep = " |".join(sep_parts)
lines.append(sep)

# Data rows
for cond in CONDITIONS:
    mode, ev_key = parse_condition(cond)
    row_parts = [f"| {MODE_LABELS[mode]} | {EVIDENCE_LABELS[ev_key]}"]
    for ds_name in SWEEPS:
        for disp_name, nest_key, metric_key in pn_metrics:
            v = data[(ds_name, cond)][nest_key][metric_key]
            is_best = abs(v - best[(ds_name, disp_name)]) < 1e-9
            row_parts.append(f" {fmt_bold(v, is_best)}")
    row_parts.append(" |")
    lines.append(" |".join(row_parts))

lines.append("")
lines.append("## Table 2: Exact-Match Metrics")
lines.append("")

ex_metrics = [m for m in METRICS if m[1] == "metrics_exact"]
header_parts = ["| Mode | Evidence"]
for ds_name in SWEEPS:
    for disp_name, _, _ in ex_metrics:
        header_parts.append(f" {ds_name} {disp_name}")
header_parts.append(" |")
lines.append(" |".join(header_parts))

sep_parts = ["| :--- | :---"]
for _ in SWEEPS:
    for _ in ex_metrics:
        sep_parts.append(" ---:")
sep_parts.append(" |")
lines.append(" |".join(sep_parts))

for cond in CONDITIONS:
    mode, ev_key = parse_condition(cond)
    row_parts = [f"| {MODE_LABELS[mode]} | {EVIDENCE_LABELS[ev_key]}"]
    for ds_name in SWEEPS:
        for disp_name, nest_key, metric_key in ex_metrics:
            v = data[(ds_name, cond)][nest_key][metric_key]
            is_best = abs(v - best[(ds_name, disp_name)]) < 1e-9
            row_parts.append(f" {fmt_bold(v, is_best)}")
    row_parts.append(" |")
    lines.append(" |".join(row_parts))


# ── Compact combined table for the paper body ─────────────────────────
lines.append("")
lines.append("## Table 3: Combined Results (Paper-Ready)")
lines.append("")
lines.append("Metrics are reported as percentages. Best result per column in **bold**.")
lines.append("")

all_metrics = METRICS
header_parts = ["| Mode | Evidence"]
for ds_name in SWEEPS:
    for disp_name, _, _ in all_metrics:
        short_ds = ds_name.split("-")[0] if "-" in ds_name else ds_name[:6]
        header_parts.append(f" {disp_name}")
header_parts.append(" |")

# Two-level header: dataset spanning columns
n_met = len(all_metrics)
ds_names = list(SWEEPS.keys())
span_header = f"| | | " + " | ".join(
    f" {'  |  '.join(['' for _ in range(n_met-1)])} **{ds}** " if False else f""
    for ds in ds_names
) + " |"

# Simpler approach: just label each column with DS + Metric
header_parts2 = ["| Mode | Evidence"]
for ds_name in SWEEPS:
    for disp_name, _, _ in all_metrics:
        header_parts2.append(f" {ds_name}: {disp_name}")
header_parts2.append(" |")
lines.append(" |".join(header_parts2))

sep_parts = ["| :--- | :---"]
for _ in SWEEPS:
    for _ in all_metrics:
        sep_parts.append(" ---:")
sep_parts.append(" |")
lines.append(" |".join(sep_parts))

for cond in CONDITIONS:
    mode, ev_key = parse_condition(cond)
    row_parts = [f"| {MODE_LABELS[mode]} | {EVIDENCE_LABELS[ev_key]}"]
    for ds_name in SWEEPS:
        for disp_name, nest_key, metric_key in all_metrics:
            v = data[(ds_name, cond)][nest_key][metric_key]
            is_best = abs(v - best[(ds_name, disp_name)]) < 1e-9
            row_parts.append(f" {fmt_bold(v, is_best)}")
    row_parts.append(" |")
    lines.append(" |".join(row_parts))

# ── Runtime comparison ────────────────────────────────────────────────
lines.append("")
lines.append("## Table 4: Runtime (seconds per case)")
lines.append("")
lines.append("| Mode | Evidence | LingxiDiag-16k | MDD-5k |")
lines.append("| :--- | :--- | ---: | ---: |")
for cond in CONDITIONS:
    mode, ev_key = parse_condition(cond)
    row = f"| {MODE_LABELS[mode]} | {EVIDENCE_LABELS[ev_key]}"
    for ds_name in SWEEPS:
        v = data[(ds_name, cond)]["avg_seconds_per_case"]
        row += f" | {v:.1f}"
    row += " |"
    lines.append(row)


# ── LaTeX table ───────────────────────────────────────────────────────
lines.append("")
lines.append("---")
lines.append("")
lines.append("## LaTeX Version (Parent-Normalized)")
lines.append("")
lines.append("```latex")

latex = []
n_ds = len(SWEEPS)
n_pn = len(pn_metrics)
total_cols = 2 + n_ds * n_pn
col_spec = "ll" + "r" * (n_ds * n_pn)
latex.append(r"\begin{table}[t]")
latex.append(r"\centering")
latex.append(r"\caption{CultureDx diagnostic performance across reasoning modes and evidence conditions (N=200). Metrics are parent-normalized. Best per column in \textbf{bold}.}")
latex.append(r"\label{tab:main_results}")
latex.append(r"\small")
latex.append(r"\begin{tabular}{" + col_spec + "}")
latex.append(r"\toprule")

# Multi-row header
ds_header = r" & "
for i, ds_name in enumerate(SWEEPS):
    ds_header += r" & \multicolumn{" + str(n_pn) + r"}{c}{" + ds_name.replace("-", r"\text{-}") + "}"
ds_header += r" \\"
latex.append(ds_header)

# Metric names
cmidrules = ""
start = 3
for i, ds_name in enumerate(SWEEPS):
    end = start + n_pn - 1
    cmidrules += r"\cmidrule(lr){" + f"{start}-{end}" + "} "
    start = end + 1
latex.append(cmidrules)

met_header = r"Mode & Evidence"
for ds_name in SWEEPS:
    for disp_name, _, _ in pn_metrics:
        met_header += r" & " + disp_name
met_header += r" \\"
latex.append(met_header)
latex.append(r"\midrule")

# Data rows
prev_mode = None
for cond in CONDITIONS:
    mode, ev_key = parse_condition(cond)
    if prev_mode is not None and mode != prev_mode:
        latex.append(r"\addlinespace")
    prev_mode = mode
    
    row = f"{MODE_LABELS[mode]} & {EVIDENCE_LABELS[ev_key]}"
    for ds_name in SWEEPS:
        for disp_name, nest_key, metric_key in pn_metrics:
            v = data[(ds_name, cond)][nest_key][metric_key]
            is_best = abs(v - best[(ds_name, disp_name)]) < 1e-9
            s = fmt(v)
            if is_best:
                row += r" & \textbf{" + s + "}"
            else:
                row += f" & {s}"
    row += r" \\"
    latex.append(row)

latex.append(r"\bottomrule")
latex.append(r"\end{tabular}")
latex.append(r"\end{table}")

lines.append("\n".join(latex))
lines.append("```")

# ── LaTeX exact match table ───────────────────────────────────────────
lines.append("")
lines.append("## LaTeX Version (Exact-Match)")
lines.append("")
lines.append("```latex")

latex2 = []
n_ex = len(ex_metrics)
col_spec2 = "ll" + "r" * (n_ds * n_ex)
latex2.append(r"\begin{table}[t]")
latex2.append(r"\centering")
latex2.append(r"\caption{CultureDx exact-match diagnostic performance (N=200). Best per column in \textbf{bold}.}")
latex2.append(r"\label{tab:exact_results}")
latex2.append(r"\small")
latex2.append(r"\begin{tabular}{" + col_spec2 + "}")
latex2.append(r"\toprule")

ds_header2 = r" & "
for i, ds_name in enumerate(SWEEPS):
    ds_header2 += r" & \multicolumn{" + str(n_ex) + r"}{c}{" + ds_name.replace("-", r"\text{-}") + "}"
ds_header2 += r" \\"
latex2.append(ds_header2)

cmidrules2 = ""
start = 3
for i, ds_name in enumerate(SWEEPS):
    end = start + n_ex - 1
    cmidrules2 += r"\cmidrule(lr){" + f"{start}-{end}" + "} "
    start = end + 1
latex2.append(cmidrules2)

met_header2 = r"Mode & Evidence"
for ds_name in SWEEPS:
    for disp_name, _, _ in ex_metrics:
        # Shorter label for LaTeX
        short = disp_name.replace(" (exact)", "")
        met_header2 += r" & " + short
met_header2 += r" \\"
latex2.append(met_header2)
latex2.append(r"\midrule")

prev_mode = None
for cond in CONDITIONS:
    mode, ev_key = parse_condition(cond)
    if prev_mode is not None and mode != prev_mode:
        latex2.append(r"\addlinespace")
    prev_mode = mode
    
    row = f"{MODE_LABELS[mode]} & {EVIDENCE_LABELS[ev_key]}"
    for ds_name in SWEEPS:
        for disp_name, nest_key, metric_key in ex_metrics:
            v = data[(ds_name, cond)][nest_key][metric_key]
            is_best = abs(v - best[(ds_name, disp_name)]) < 1e-9
            s = fmt(v)
            if is_best:
                row += r" & \textbf{" + s + "}"
            else:
                row += f" & {s}"
    row += r" \\"
    latex2.append(row)

latex2.append(r"\bottomrule")
latex2.append(r"\end{tabular}")
latex2.append(r"\end{table}")

lines.append("\n".join(latex2))
lines.append("```")

# ── Summary statistics ────────────────────────────────────────────────
lines.append("")
lines.append("## Key Findings")
lines.append("")

# Find best condition per dataset
for ds_name in SWEEPS:
    best_cond_pn = max(CONDITIONS, key=lambda c: data[(ds_name, c)]["metrics_parent_normalized"]["top1_accuracy"])
    best_cond_ex = max(CONDITIONS, key=lambda c: data[(ds_name, c)]["metrics_exact"]["top1_accuracy"])
    pn_v = data[(ds_name, best_cond_pn)]["metrics_parent_normalized"]["top1_accuracy"]
    ex_v = data[(ds_name, best_cond_ex)]["metrics_exact"]["top1_accuracy"]
    m1, e1 = parse_condition(best_cond_pn)
    m2, e2 = parse_condition(best_cond_ex)
    lines.append(f"- **{ds_name}** best parent-normalized Top-1: {fmt(pn_v)}% ({MODE_LABELS[m1]}, {EVIDENCE_LABELS[e1]})")
    lines.append(f"- **{ds_name}** best exact-match Top-1: {fmt(ex_v)}% ({MODE_LABELS[m2]}, {EVIDENCE_LABELS[e2]})")

# Evidence effect: average across modes for each dataset
lines.append("")
lines.append("### Evidence Effect (averaged across modes)")
lines.append("")
for ds_name in SWEEPS:
    for metric_type in ["metrics_parent_normalized", "metrics_exact"]:
        label = "Parent-Norm" if "parent" in metric_type else "Exact"
        no_ev_avg = sum(data[(ds_name, c)][metric_type]["top1_accuracy"] for c in CONDITIONS if "no_evidence" in c) / 3
        ev_avg = sum(data[(ds_name, c)][metric_type]["top1_accuracy"] for c in CONDITIONS if "bge-m3_evidence" in c and "no_somatization" not in c) / 3
        nosom_avg = sum(data[(ds_name, c)][metric_type]["top1_accuracy"] for c in CONDITIONS if "no_somatization" in c) / 3
        lines.append(f"- {ds_name} ({label}) Top-1 Acc: No Evidence={fmt(no_ev_avg)}%, BGE-M3={fmt(ev_avg)}%, No Somat.={fmt(nosom_avg)}%")

# Mode effect
lines.append("")
lines.append("### Mode Effect (averaged across evidence conditions)")
lines.append("")
for ds_name in SWEEPS:
    for metric_type in ["metrics_parent_normalized"]:
        for mode_key, mode_label in MODE_LABELS.items():
            mode_conds = [c for c in CONDITIONS if c.startswith(mode_key)]
            avg_t1 = sum(data[(ds_name, c)][metric_type]["top1_accuracy"] for c in mode_conds) / len(mode_conds)
            avg_t3 = sum(data[(ds_name, c)][metric_type]["top3_accuracy"] for c in mode_conds) / len(mode_conds)
            lines.append(f"- {ds_name} {mode_label}: Top-1={fmt(avg_t1)}%, Top-3={fmt(avg_t3)}%")

lines.append("")

# ── Write output ──────────────────────────────────────────────────────
out_path = Path("outputs/paper_results_table.md")
out_path.write_text("\n".join(lines))
print(f"Written to {out_path}")
print()
print("\n".join(lines))
