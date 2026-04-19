#!/bin/bash
# cleanup.sh — Phase 0 repo cleanup
#
# Executes the housekeeping steps from WHOLE_REPO_REVIEW.md:
#   Tier 1: Safe housekeeping (pycache, backups)
#   Tier 2: Reorganize scripts/
#   Tier 4: Archive old config overlays
#   Tier 5: Move planning docs to docs/planning/
#   Tier 7: Commit untracked files, remove deprecated versions
#
# Tier 3 (archive old results) is interactive — handled separately.
# Tier 6 (CLI seed fix) is patched separately via fix_cli_seed.patch.
#
# Creates a new branch `chore/pre-queue-cleanup` for the changes.

set -e

REPO_ROOT="${REPO_ROOT:-$(pwd)}"
cd "$REPO_ROOT"

if ! grep -q "culturedx" pyproject.toml 2>/dev/null; then
    echo "ERROR: not in CultureDx repo root"
    exit 1
fi

BRANCH=$(git branch --show-current)
if [ "$BRANCH" != "main-v2.4-refactor" ]; then
    echo "ERROR: must start from main-v2.4-refactor (currently on $BRANCH)"
    exit 1
fi

git pull --ff-only origin main-v2.4-refactor
git checkout -B chore/pre-queue-cleanup

echo "========================================================"
echo "Tier 1 — Safe housekeeping"
echo "========================================================"
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
rm -f prompts/agents/*.backup prompts/agents/*.jinja.backup
echo "  Removed __pycache__, *.pyc, *.backup"

echo ""
echo "========================================================"
echo "Tier 7 — Commit useful untracked files"
echo "========================================================"

for f in \
    ANALYSIS_PHASE0.md \
    results/validation/t1_diag_topk/oracle_analysis.json \
    scripts/oracle_analysis.py \
    scripts/q4_v2_f41_f32.py \
    scripts/q7_learned_ranker_v2.py \
    scripts/q7b_ablation.py \
    scripts/q7cde_ablation.py \
    scripts/q7f_candidate_generator.py \
; do
    if [ -f "$f" ]; then
        git add "$f"
        echo "  + $f"
    fi
done

# Remove deprecated duplicates
for f in \
    scripts/q2_oracle_ranker_on_confirmed.py \
    scripts/q4_f41_f32_analysis.py \
    scripts/q4_f41_f32_confusion.py \
; do
    if [ -f "$f" ]; then
        rm "$f"
        echo "  - $f (deprecated)"
    fi
done

echo ""
echo "========================================================"
echo "Tier 2 — Reorganize scripts/"
echo "========================================================"

mkdir -p scripts/eval scripts/analysis scripts/training scripts/legacy scripts/runners

move_if_exists() {
    local src="$1"
    local dest="$2"
    if [ -f "$src" ]; then
        git mv "$src" "$dest" 2>/dev/null || mv "$src" "$dest"
        echo "  $src -> $dest"
    fi
}

# Eval/post-hoc
for f in run_final_combined.py recompute_top3_from_ranked.py \
         t1_comorbid_cap_replay.py bootstrap_ci_final.py \
         compute_table4.py build_results_table.py; do
    move_if_exists "scripts/$f" "scripts/eval/$f"
done

# Analysis
for f in oracle_analysis.py q4_v2_f41_f32.py q7_learned_ranker_v2.py \
         q7b_ablation.py q7cde_ablation.py q7f_candidate_generator.py \
         extract_ranker_features.py r4_oracle_simulation.py; do
    move_if_exists "scripts/$f" "scripts/analysis/$f"
done

# Training
for f in train_tfidf_baseline.py train_ranker_lightgbm.py calibrate_confidence.py; do
    move_if_exists "scripts/$f" "scripts/training/$f"
done

# Runners
for f in run_multi_backbone.sh run_api_backbone.py run_full_eval.py; do
    move_if_exists "scripts/$f" "scripts/runners/$f"
done

# Legacy
for f in ablation_sweep.py bootstrap_ci.py lowfreq_boost_sweep.py \
         f1_macro_offset_sweep.py replay_others_fallback.py \
         paper_results.py run_ensemble.py r4_integration_plan.py; do
    move_if_exists "scripts/$f" "scripts/legacy/$f"
done

echo ""
echo "========================================================"
echo "Tier 4 — Archive old config overlays"
echo "========================================================"

mkdir -p configs/legacy/overlays

for f in checker_per_class.yaml checker_v2_improved.yaml \
         t1_f43_trigger.yaml t1_nos_routing.yaml \
         t5b_contrastive.yaml verifier_on.yaml; do
    move_if_exists "configs/overlays/$f" "configs/legacy/overlays/$f"
done

echo ""
echo "========================================================"
echo "Tier 5 — Organize planning docs"
echo "========================================================"

mkdir -p docs/planning

for d in tier1_tracks sota_playbook phase0_deliverable; do
    if [ -d "$d" ]; then
        git mv "$d" "docs/planning/$d" 2>/dev/null || mv "$d" "docs/planning/$d"
        echo "  $d -> docs/planning/$d"
    fi
done

# Move top-level analysis markdown
if [ -f ANALYSIS_PHASE0.md ] && [ -f docs/planning/phase0_deliverable/ANALYSIS_PHASE0.md ]; then
    rm ANALYSIS_PHASE0.md  # duplicate
fi

echo ""
echo "========================================================"
echo "Summary of changes"
echo "========================================================"
git status --short | head -50
echo ""
echo "Total files changed: $(git status --short | wc -l)"

echo ""
echo "========================================================"
echo "Verification: imports still work?"
echo "========================================================"
if uv run python -c "import culturedx.modes.hied; print('hied OK'); import culturedx.pipeline.cli; print('cli OK')" 2>&1 | grep -q "OK"; then
    echo "  Imports pass"
else
    echo "  WARNING: some imports may be broken"
fi

echo ""
echo "========================================================"
echo "Cleanup complete. Next steps:"
echo ""
echo "1. Review changes:"
echo "     git diff --stat HEAD"
echo ""
echo "2. Apply CLI patches:"
echo "     cd $REPO_ROOT"
echo "     patch -p1 < master_cleanup/fix_cli_seed.patch"
echo "     patch -p1 < master_cleanup/fix_test_triage.patch"
echo ""
echo "3. (Optional) Apply R16 patch if you want to run R16:"
echo "     patch -p1 < master_cleanup/r16_bypass_logic_engine.patch"
echo ""
echo "4. Run tests:"
echo "     uv run pytest tests/ -q"
echo ""
echo "5. Commit:"
echo "     git add -A"
echo "     git commit -m 'chore: pre-queue cleanup + CLI seed fix + test update'"
echo ""
echo "6. Optional Tier 3 (archive old results):"
echo "     ./master_cleanup/scripts/archive_legacy_results.sh"
echo ""
echo "7. Start the 7-run queue:"
echo "     ./master_cleanup/scripts/run_queue_revised.sh"
echo "========================================================"
