#!/bin/bash
# post_hoc_analyze_all.sh — Apply Stage 2-5 + oracle + q4 confusion
# to all runs from the queue.

set -e

REPO_ROOT="${REPO_ROOT:-$(pwd)}"
cd "$REPO_ROOT"

RUNS=(
    r6_combined
    r7_triage_top8
    r20_nos_variant
    r21_evidence_stacked
    r16_bypass_logic
    r13_qwen3_8b
)

# Also pick up any r14_* (backbone-specific name)
for d in results/validation/r14_*/; do
    [ -d "$d" ] && RUNS+=("$(basename $d)")
done

echo "========================================================"
echo "Post-hoc analysis for ${#RUNS[@]} runs"
echo "========================================================"

for run in "${RUNS[@]}"; do
    run_dir="results/validation/$run"
    if [ ! -d "$run_dir" ]; then
        echo "SKIP: $run (directory not found)"
        continue
    fi

    echo ""
    echo "--- Analyzing $run ---"

    # Stage 2-5 post-hoc pipeline (if available)
    if [ -f scripts/run_final_combined.py ]; then
        python3 scripts/run_final_combined.py \
            --dtv-run "$run_dir" \
            --tfidf-run results/validation/tfidf_baseline \
            --output-dir "${run_dir}_final" \
            --fit-offsets 2>&1 | tail -20
    fi

    # Oracle analysis
    if [ -f scripts/oracle_analysis.py ]; then
        python3 scripts/oracle_analysis.py --run-dir "$run_dir" 2>&1 | tail -30
    fi

    # Q4 F41/F32 confusion
    python3 << EOF
import json
import sys
from pathlib import Path
sys.path.insert(0, 'src')

try:
    from culturedx.eval.lingxidiag_paper import to_paper_parent, gold_to_parent_list
except Exception as e:
    print(f"Import error: {e}")
    sys.exit(0)

run_dir = Path("$run_dir")
pred_path = run_dir / "predictions.jsonl"
if not pred_path.exists():
    print(f"No predictions.jsonl in {run_dir}")
    sys.exit(0)

records = [json.loads(l) for l in open(pred_path)]
n = len(records)

both_conf = 0
f41_to_f32 = 0
f32_to_f41 = 0

for r in records:
    dt = r.get('decision_trace') or {}
    if not isinstance(dt, dict):
        continue
    confirmed = set()
    for c in (dt.get('logic_engine_confirmed_codes') or []):
        c = str(c)
        if c.startswith('F32'): confirmed.add('F32')
        elif c.startswith('F41'): confirmed.add('F41')

    if 'F32' not in confirmed or 'F41' not in confirmed:
        continue
    both_conf += 1

    golds = set()
    for g in (r.get('gold_diagnoses') or []):
        g = str(g)
        if g.startswith('F32'): golds.add('F32')
        elif g.startswith('F41'): golds.add('F41')

    primary = str(r.get('primary_diagnosis') or '')
    pp = 'F32' if primary.startswith('F32') else ('F41' if primary.startswith('F41') else 'other')

    if 'F41' in golds and 'F32' not in golds and pp == 'F32':
        f41_to_f32 += 1
    elif 'F32' in golds and 'F41' not in golds and pp == 'F41':
        f32_to_f41 += 1

ratio = f41_to_f32 / max(1, f32_to_f41)
print(f"F41/F32 confusion for $run:")
print(f"  Both confirmed: {both_conf}/{n} ({both_conf/n*100:.1f}%)")
print(f"  F41->F32 error: {f41_to_f32}")
print(f"  F32->F41 error: {f32_to_f41}")
print(f"  Asymmetry ratio: {ratio:.2f}x")
print(f"  (LingxiDiag ref: 9.4x, MDD-5k ref: 10.1x)")
EOF

done

echo ""
echo "========================================================"
echo "All post-hoc analysis complete"
echo "========================================================"
