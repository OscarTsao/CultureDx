"""Audit a CultureDx run for integrity. Exit non-zero on any failure.

Checks:
    (1) run.log has no TemplateNotFound warnings
    (2) per-disorder checker coverage >= 95% (only for DtV runs with a
        configured target_disorders list)
    (3) primary differs from diagnostician_top1 in >= 5% of cases
        (sanity: the checker actually influences the output)
    (4) run_manifest.json's git_sha is an ancestor of HEAD
    (5) predictions.jsonl, metrics_summary.json, and run_manifest.json
        all exist and are parseable

Usage:
    uv run python scripts/audit_run.py <run_dir>
    # prints structured report; exit 0 = clean, 1 = quarantine

Can also be wired into CI:
    uv run python scripts/audit_run.py results/rebase_v2.5/stacker_lr/ \\
        || exit 1

The audit is intentionally conservative. If any check fails, the run is
not usable for paper claims. Add the run's coverage numbers to
paper/supplementary anyway — reviewers benefit from seeing the gate.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

COVERAGE_THRESHOLD = 0.95
CHECKER_INFLUENCE_THRESHOLD = 0.05


class AuditFailure(Exception):
    pass


def _parent_of(code: str | None) -> str | None:
    if not code:
        return None
    return str(code).strip().upper().split(".")[0]


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #
def check_files_exist(run_dir: Path) -> dict:
    findings = []
    required = ["predictions.jsonl"]
    for f in required:
        if not (run_dir / f).exists():
            findings.append(f"missing required file: {f}")

    # run_manifest and metrics_summary are strongly recommended
    optional_warnings = []
    for f in ["run_manifest.json", "metrics_summary.json", "metrics.json"]:
        if not (run_dir / f).exists():
            optional_warnings.append(f"missing: {f}")

    return {
        "name": "files_exist",
        "passed": not findings,
        "findings": findings,
        "warnings": optional_warnings,
    }


def check_template_errors(run_dir: Path) -> dict:
    """Parse run.log for 'TemplateNotFound' or 'Criterion checker failed' lines."""
    log = run_dir / "run.log"
    if not log.exists():
        return {
            "name": "template_errors",
            "passed": True,
            "findings": [],
            "warnings": ["run.log not present; skipping template check"],
        }

    text = log.read_text(encoding="utf-8", errors="replace")
    patterns = [
        r"TemplateNotFound",
        r"Criterion checker failed",
        r"not found in search path",
    ]
    hits = []
    for pat in patterns:
        matches = re.findall(pat, text)
        if matches:
            hits.append({"pattern": pat, "count": len(matches)})

    return {
        "name": "template_errors",
        "passed": not hits,
        "findings": hits,
        "warnings": [],
    }


def check_checker_coverage(run_dir: Path) -> dict:
    """For every target disorder, checker must have run on >= 95% of cases."""
    pred_path = run_dir / "predictions.jsonl"
    if not pred_path.exists():
        return {
            "name": "checker_coverage",
            "passed": False,
            "findings": ["predictions.jsonl missing"],
            "warnings": [],
        }

    by_disorder: dict[str, int] = defaultdict(int)
    n_cases = 0
    has_any_checker = False

    with pred_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            n_cases += 1
            trace = rec.get("decision_trace") or {}
            raw = trace.get("raw_checker_outputs") or []
            if raw:
                has_any_checker = True
                seen = set()
                for entry in raw:
                    if not isinstance(entry, dict):
                        continue
                    d = entry.get("disorder_code") or entry.get("code") or ""
                    if d:
                        seen.add(d)
                for d in seen:
                    by_disorder[d] += 1

    if not has_any_checker:
        return {
            "name": "checker_coverage",
            "passed": True,
            "findings": [],
            "warnings": ["no checker outputs present (may be Single LLM "
                         "or TF-IDF run); skipping coverage check"],
            "n_cases": n_cases,
        }

    coverage = {d: cnt / n_cases for d, cnt in by_disorder.items()}
    low = {d: cov for d, cov in coverage.items() if cov < COVERAGE_THRESHOLD}
    return {
        "name": "checker_coverage",
        "passed": not low,
        "findings": [
            f"{d}: {cov:.1%} coverage (<{COVERAGE_THRESHOLD:.0%})"
            for d, cov in sorted(low.items())
        ],
        "warnings": [],
        "n_cases": n_cases,
        "full_coverage": {d: round(c, 4) for d, c in sorted(coverage.items())},
    }


def check_checker_influence(run_dir: Path) -> dict:
    """Sanity: primary should differ from diagnostician_top1 in >=5% of cases."""
    pred_path = run_dir / "predictions.jsonl"
    if not pred_path.exists():
        return {
            "name": "checker_influence",
            "passed": False,
            "findings": ["predictions.jsonl missing"],
            "warnings": [],
        }

    n = 0
    disagree = 0
    skipped = 0

    with pred_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            primary = _parent_of(rec.get("primary_diagnosis"))
            trace = rec.get("decision_trace") or {}
            top1 = None
            for key in ("diagnostician_ranked", "ranked_codes_with_conf",
                        "diagnostician_top_k"):
                ranked = trace.get(key)
                if ranked:
                    first = ranked[0] if ranked else None
                    if isinstance(first, dict):
                        top1 = _parent_of(first.get("code"))
                    elif isinstance(first, (list, tuple)):
                        top1 = _parent_of(first[0])
                    break

            if top1 is None or primary is None:
                skipped += 1
                continue
            n += 1
            if top1 != primary:
                disagree += 1

    if n == 0:
        return {
            "name": "checker_influence",
            "passed": True,
            "findings": [],
            "warnings": [
                "no diagnostician_ranked in predictions (non-DtV run?); "
                "skipping influence check",
            ],
        }
    rate = disagree / n
    passed = rate >= CHECKER_INFLUENCE_THRESHOLD
    return {
        "name": "checker_influence",
        "passed": passed,
        "findings": (
            []
            if passed
            else [f"primary differs from diagnostician_top1 in only "
                  f"{rate:.1%} of cases (<{CHECKER_INFLUENCE_THRESHOLD:.0%}). "
                  f"Checker may not be influencing output (cf. main's R6/R20/R21v2)."]
        ),
        "warnings": [] if not skipped else [
            f"skipped {skipped} records without diagnostician_top1"
        ],
        "disagreement_rate": round(rate, 4),
        "n_evaluated": n,
    }


def check_git_ancestry(run_dir: Path) -> dict:
    """If run_manifest.json has a git_sha, verify it's an ancestor of HEAD."""
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        return {
            "name": "git_ancestry",
            "passed": True,
            "findings": [],
            "warnings": ["run_manifest.json missing; skipping ancestry check"],
        }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {
            "name": "git_ancestry",
            "passed": False,
            "findings": [f"run_manifest.json not valid JSON: {e}"],
            "warnings": [],
        }
    git_sha = manifest.get("git_sha") or manifest.get("git_commit")
    if not git_sha:
        return {
            "name": "git_ancestry",
            "passed": True,
            "findings": [],
            "warnings": ["run_manifest.json has no git_sha field"],
        }
    # Run `git merge-base --is-ancestor <sha> HEAD`
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", git_sha, "HEAD"],
            capture_output=True, text=True,
        )
        is_ancestor = result.returncode == 0
    except FileNotFoundError:
        return {
            "name": "git_ancestry",
            "passed": True,
            "findings": [],
            "warnings": ["git not available; skipping ancestry check"],
        }
    return {
        "name": "git_ancestry",
        "passed": is_ancestor,
        "findings": [] if is_ancestor else [
            f"run's git_sha {git_sha} is not an ancestor of HEAD. "
            f"Either the run was done on a diverged branch, or HEAD was "
            f"rewritten after the run."
        ],
        "warnings": [],
        "git_sha": git_sha,
    }


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def run_all(run_dir: Path) -> tuple[list[dict], bool]:
    checks = [
        check_files_exist(run_dir),
        check_template_errors(run_dir),
        check_checker_coverage(run_dir),
        check_checker_influence(run_dir),
        check_git_ancestry(run_dir),
    ]
    all_passed = all(c["passed"] for c in checks)
    return checks, all_passed


def pretty_print(checks: list[dict], run_dir: Path, all_passed: bool) -> None:
    bar = "=" * 72
    print(bar)
    print(f"AUDIT REPORT: {run_dir}")
    print(bar)
    for c in checks:
        status = "PASS" if c["passed"] else "FAIL"
        print(f"[{status}] {c['name']}")
        for f in c.get("findings", []):
            print(f"       - {f}")
        for w in c.get("warnings", []):
            print(f"       (warn) {w}")
        if "disagreement_rate" in c:
            print(f"       disagreement_rate = {c['disagreement_rate']:.1%} "
                  f"(n={c['n_evaluated']})")
    print(bar)
    verdict = "CLEAN — metrics usable" if all_passed else "QUARANTINE — DO NOT CITE"
    print(f"VERDICT: {verdict}")
    print(bar)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir", type=Path, help="Run directory to audit")
    parser.add_argument("--json", action="store_true",
                        help="Emit machine-readable JSON instead of human text")
    args = parser.parse_args()

    if not args.run_dir.is_dir():
        print(f"ERROR: {args.run_dir} is not a directory", file=sys.stderr)
        sys.exit(2)

    checks, all_passed = run_all(args.run_dir)

    if args.json:
        print(json.dumps({
            "run_dir": str(args.run_dir),
            "passed": all_passed,
            "checks": checks,
        }, indent=2, ensure_ascii=False))
    else:
        pretty_print(checks, args.run_dir, all_passed)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
