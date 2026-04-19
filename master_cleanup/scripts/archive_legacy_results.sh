#!/bin/bash
# archive_legacy_results.sh — Interactive Tier 3 cleanup
#
# Moves legacy result directories to results/legacy/validation/ and prints
# size savings. User is asked to confirm each category before moving.
#
# Recovers roughly 250 MB by archiving ~21 legacy dirs.

set -e

REPO_ROOT="${REPO_ROOT:-$(pwd)}"
cd "$REPO_ROOT"

if [ ! -d "results/validation" ]; then
    echo "ERROR: results/validation not found"
    exit 1
fi

mkdir -p results/legacy/validation

# Categories of legacy results
declare -A CATEGORIES

CATEGORIES[old_ablation_series]="01_single_baseline 02_single_rag 03_dtv_v1 04_dtv_v1_rag 05_dtv_v2_rag 06_dtv_v2_rag_gate 07_verifier_on 08_checker_per_class"
CATEGORIES[t1_early]="t1_others t1_f43trig t1_nos t1_triage_no_meta t1_diag_topk_smoke t1_diag_topk_capped t1_diag_topk_comorbid_fixed"
CATEGORIES[t2_early]="t2_lowfreq t2_rrf t2_triage_demographics"
CATEGORIES[t3_early]="t3_manual_fixed t3_tfidf_stack"
CATEGORIES[t5_contrastive]="t5b_contrastive"
CATEGORIES[factorial_old]="factorial_a_orig_evidence factorial_c_improved_evidence"
CATEGORIES[empty_markers]="multi_backbone"

# Descriptions shown to user
declare -A DESC
DESC[old_ablation_series]="Pre-T1 ablation series (01-08): old dtv_v1/v2 configs, checker variants"
DESC[t1_early]="Early T1 experiments (post-hoc variants of t1_diag_topk)"
DESC[t2_early]="T2 experiments (RRF, low-freq boost, demographics) — all superseded"
DESC[t3_early]="T3 experiments (manual fix, tfidf_stack standalone) — superseded by final_combined"
DESC[t5_contrastive]="T5b contrastive checker — negative result (superseded by R4)"
DESC[factorial_old]="factorial_a_orig_evidence, factorial_c_improved_evidence (factorial_b kept as reference)"
DESC[empty_markers]="Empty or stub directories"

# Kept (for reference): t1_diag_topk, final_combined, tfidf_baseline, bootstrap_ci,
# factorial_b_improved_noevidence, t4_f1_opt, r4_*, r11_*, r12_*, r15_no_rag,
# r18_single_llm

echo "========================================================"
echo "Interactive Tier 3 — Archive legacy results"
echo "========================================================"
echo ""
echo "Current results/validation size: $(du -sh results/validation/ | cut -f1)"
echo ""
echo "This script will ask you category-by-category whether to"
echo "move legacy result directories to results/legacy/validation/"
echo ""
echo "Kept runs (reference for paper, NOT touched):"
echo "  - final_combined (current best, 5/6 SOTA)"
echo "  - t1_diag_topk (current baseline)"
echo "  - tfidf_baseline (supervised reference)"
echo "  - bootstrap_ci (CI data)"
echo "  - factorial_b_improved_noevidence (ablation reference)"
echo "  - t4_f1_opt (F1-OPT baseline)"
echo "  - r4_contrastive_primary, r4_final (R4 negative result)"
echo "  - r11_t1_seed123, r12_t1_seed456 (for audit; known broken)"
echo "  - r15_no_rag, r18_single_llm (recent ablations)"
echo ""

total_archived=0

for cat in old_ablation_series t1_early t2_early t3_early t5_contrastive factorial_old empty_markers; do
    echo "--------------------------------------------------------"
    echo "Category: $cat"
    echo "Description: ${DESC[$cat]}"
    echo ""
    dirs=${CATEGORIES[$cat]}
    echo "Directories:"
    cat_size_kb=0
    for d in $dirs; do
        if [ -d "results/validation/$d" ]; then
            size=$(du -s "results/validation/$d" | cut -f1)
            size_h=$(du -sh "results/validation/$d" | cut -f1)
            echo "  - $d ($size_h)"
            cat_size_kb=$((cat_size_kb + size))
        fi
    done
    echo "Total for category: $((cat_size_kb / 1024)) MB"
    echo ""
    read -p "Archive this category? [y/N/s(kip)] " response
    
    if [ "$response" = "y" ] || [ "$response" = "Y" ]; then
        for d in $dirs; do
            if [ -d "results/validation/$d" ]; then
                git mv "results/validation/$d" "results/legacy/validation/$d" 2>/dev/null || \
                    mv "results/validation/$d" "results/legacy/validation/$d"
                echo "  archived: $d"
            fi
        done
        total_archived=$((total_archived + cat_size_kb))
    else
        echo "  skipped."
    fi
    echo ""
done

# Handle top-level JSON analysis files
echo "--------------------------------------------------------"
echo "JSON analysis files at results/validation/*.json"
echo "(abstention_analysis.json, factorial_decision.json, etc.)"
echo ""
json_files=$(find results/validation -maxdepth 1 -name "*.json" 2>/dev/null)
if [ -n "$json_files" ]; then
    echo "Files found:"
    echo "$json_files" | while read f; do echo "  - $f"; done
    echo ""
    read -p "Move to results/validation/analysis/? [y/N] " response
    if [ "$response" = "y" ] || [ "$response" = "Y" ]; then
        mkdir -p results/validation/analysis
        for f in $json_files; do
            git mv "$f" "results/validation/analysis/" 2>/dev/null || mv "$f" "results/validation/analysis/"
        done
        echo "  moved."
    fi
fi
echo ""

echo "========================================================"
echo "Tier 3 summary"
echo "========================================================"
echo "Archived: ~$((total_archived / 1024)) MB"
echo ""
echo "Current sizes:"
du -sh results/validation/ results/legacy/validation/ 2>/dev/null
echo ""
echo "Commit with:"
echo "  git add -A"
echo "  git commit -m 'chore: archive legacy validation results to results/legacy/'"
