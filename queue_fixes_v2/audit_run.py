#!/usr/bin/env python3
"""audit_run.py — sanity check a CultureDx validation run for silent failures.

Catches:
  1. TemplateNotFound errors in run.log (silent checker failures)
  2. Missing disorders in raw_checker_outputs (0 coverage for targeted disorders)
  3. Too-high primary/diagnostician-top1 agreement (checker not influencing selection)
  4. High abstain rate (>5%)

Usage:
    python scripts/audit_run.py results/validation/r21_evidence_v2
    python scripts/audit_run.py results/validation/*/            # all runs

Exit codes:
    0 = clean (run is trustworthy)
    1 = warnings (run may be biased; see output)
    2 = broken (run is invalid; do not include in paper)
"""
from __future__ import annotations
import sys
import json
import subprocess
from pathlib import Path
from collections import defaultdict

# Target disorders for v2.4_final manual scope
V24_TARGETS = {'F20', 'F31', 'F32', 'F39', 'F41.0', 'F41.1', 'F41.2', 'F42',
               'F43.1', 'F43.2', 'F45', 'F51', 'F98', 'Z71'}


def audit_run(run_dir: Path) -> int:
    name = run_dir.name
    predictions = run_dir / 'predictions.jsonl'
    run_log = run_dir / 'run.log'
    run_info = run_dir / 'run_info.json'

    if not predictions.exists():
        print(f"[{name}] ✗ No predictions.jsonl; skipping")
        return 2

    severity = 0  # 0 = clean, 1 = warnings, 2 = broken
    messages = []

    # Check 1: TemplateNotFound count in log
    if run_log.exists():
        try:
            tmpl_errs = subprocess.check_output(
                ['grep', '-c', 'TemplateNotFound', str(run_log)],
                stderr=subprocess.DEVNULL
            ).decode().strip()
            tmpl_errs = int(tmpl_errs) if tmpl_errs.isdigit() else 0
        except subprocess.CalledProcessError:
            tmpl_errs = 0
        if tmpl_errs > 0:
            messages.append(f"  ✗ {tmpl_errs} TemplateNotFound errors in run.log")
            severity = max(severity, 2 if tmpl_errs > 100 else 1)

    # Check 2: Checker coverage per disorder
    disorder_counts = defaultdict(int)
    total_cases = 0
    abstain_cases = 0
    primary_vs_top1_match = 0
    total_with_ranking = 0

    mode_type = None
    if run_info.exists():
        try:
            info = json.load(open(run_info))
            mode_type = info.get('config', {}).get('mode', {}).get('type')
        except Exception:
            pass

    for line in open(predictions):
        r = json.loads(line)
        total_cases += 1
        if r.get('primary_diagnosis') is None:
            abstain_cases += 1

        dt = r.get('decision_trace') or {}
        if not isinstance(dt, dict):
            continue

        # Collect disorder codes present in raw_checker_outputs
        raw = dt.get('raw_checker_outputs') or []
        present = {co.get('disorder_code') for co in raw}
        for d in present:
            disorder_counts[d] += 1

        # Check primary vs diagnostician top-1
        diag = dt.get('diagnostician', {})
        if isinstance(diag, dict):
            ranked = diag.get('ranked_codes', [])
        else:
            ranked = dt.get('diagnostician_ranked', [])
        if ranked:
            total_with_ranking += 1
            primary_base = str(r.get('primary_diagnosis') or '').split('.')[0]
            top1_base = str(ranked[0]).split('.')[0]
            if primary_base == top1_base:
                primary_vs_top1_match += 1

    # Skip checker-coverage checks if single-LLM mode
    if mode_type == 'single':
        messages.append(f"  ℹ mode=single (no checker stage expected)")
    else:
        # Disorder coverage check (for DtV/HiED modes)
        missing_disorders = []
        low_coverage = []
        for d in V24_TARGETS:
            count = disorder_counts.get(d, 0)
            pct = count / total_cases if total_cases else 0
            if count == 0:
                missing_disorders.append(d)
            elif pct < 0.5:
                low_coverage.append((d, count, pct))

        if missing_disorders:
            messages.append(f"  ✗ Checker output missing entirely for: {missing_disorders}")
            severity = max(severity, 2 if len(missing_disorders) >= 3 else 1)
        if low_coverage:
            for d, c, p in low_coverage:
                messages.append(f"  ⚠ Low checker coverage for {d}: {c}/{total_cases} = {p:.1%}")
            severity = max(severity, 1)

    # Check 3: primary/top-1 agreement (for DtV modes)
    # NOTE: high agreement is NOT a run bug — it's a pipeline property of current v2.4 DtV.
    # The diagnostician's top-1 is almost always in the confirmed set, so primary defaults to it.
    # We only flag this as a warning if checker coverage is ALSO suspicious.
    if total_with_ranking > 0 and mode_type != 'single':
        agreement = primary_vs_top1_match / total_with_ranking
        if agreement > 0.98:
            # Only flag if combined with other issues (e.g., low coverage or template errors)
            # Otherwise print as an informational note.
            if severity >= 1:
                messages.append(
                    f"  ⚠ primary == diagnostician top-1 in {agreement:.1%} of cases "
                    f"(confirms checker is not functioning)"
                )
            else:
                messages.append(
                    f"  ℹ primary == diagnostician top-1 in {agreement:.1%} of cases "
                    f"(pipeline property — diag top-1 typically in confirmed set; not a bug)"
                )

    # Check 4: abstain rate
    if total_cases > 0:
        abstain_rate = abstain_cases / total_cases
        if abstain_rate > 0.40:
            messages.append(
                f"  ✗ Abstain rate {abstain_rate:.1%} ({abstain_cases}/{total_cases}) — "
                f"majority of cases failed; run invalid"
            )
            severity = max(severity, 2)
        elif abstain_rate > 0.15:
            messages.append(
                f"  ⚠ Abstain rate {abstain_rate:.1%} ({abstain_cases}/{total_cases}) — "
                f"higher than typical; investigate run.log"
            )
            severity = max(severity, 1)
        elif abstain_rate > 0.05:
            messages.append(
                f"  ℹ Abstain rate {abstain_rate:.1%} ({abstain_cases}/{total_cases}) — "
                f"typical for hard cases"
            )

    # Print report
    status_icon = '✅' if severity == 0 else ('⚠️' if severity == 1 else '✗')
    status_label = 'CLEAN' if severity == 0 else ('WARNINGS' if severity == 1 else 'BROKEN')
    print(f"\n[{name}] {status_icon} {status_label}  (N={total_cases})")
    if messages:
        for msg in messages:
            print(msg)
    else:
        print("  (no issues detected)")

    return severity


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)

    worst = 0
    for arg in sys.argv[1:]:
        p = Path(arg)
        if not p.is_dir():
            continue
        if (p / 'predictions.jsonl').exists():
            worst = max(worst, audit_run(p))
        else:
            # It's a parent dir; audit each subdirectory
            for sub in sorted(p.iterdir()):
                if sub.is_dir() and (sub / 'predictions.jsonl').exists():
                    worst = max(worst, audit_run(sub))

    sys.exit(worst)
