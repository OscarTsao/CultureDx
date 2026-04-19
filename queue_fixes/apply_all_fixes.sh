#!/bin/bash
# apply_all_fixes.sh — one-shot fix for the 3 queue bugs
#
# Safe to run on main-v2.4-refactor @ 851e92f. Creates a new branch,
# applies all patches/configs, runs tests, and leaves you ready to commit.

set -e

REPO_ROOT="${REPO_ROOT:-$(pwd)}"
cd "$REPO_ROOT"

if ! grep -q "culturedx" pyproject.toml 2>/dev/null; then
    echo "ERROR: not in CultureDx repo root"; exit 1
fi

BRANCH=$(git branch --show-current)
if [ "$BRANCH" != "main-v2.4-refactor" ]; then
    echo "ERROR: must start from main-v2.4-refactor (currently on $BRANCH)"; exit 1
fi

git pull --ff-only origin main-v2.4-refactor
git checkout -B fix/queue-runtime-bugs

# Locate the fix directory (wherever this script was unpacked to)
FIX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "========================================================"
echo "1/3 — Fix top1_code NameError in hied.py"
echo "========================================================"
patch -p1 < "$FIX_DIR/fix_top1_code_nameerror.patch"
echo "  ✓ applied"

echo ""
echo "========================================================"
echo "2/3 — Fix silent config validation"
echo "========================================================"
patch -p1 < "$FIX_DIR/configs_fix/strict_config_validation.patch"
echo "  ✓ applied"

echo ""
echo "========================================================"
echo "3/3 — Replace R13/R14 config files"
echo "========================================================"
cp "$FIX_DIR/configs_fix/vllm_qwen3_8b.yaml" configs/vllm_qwen3_8b.yaml
cp "$FIX_DIR/configs_fix/r14_non_qwen.yaml" configs/overlays/r14_non_qwen.yaml
echo "  ✓ R13 config (vllm_qwen3_8b.yaml): provider=vllm, model_id=Qwen/Qwen3-8B-Instruct-AWQ"
echo "  ✓ R14 config (r14_non_qwen.yaml): provider=vllm, model_id=modelscope/Yi-1.5-34B-Chat-AWQ"

echo ""
echo "========================================================"
echo "Verifying with test suite"
echo "========================================================"
if uv run pytest tests/ -q 2>&1 | tail -3 | grep -q "passed"; then
    echo "  ✓ All tests pass"
else
    echo "  ✗ Tests failed — review before committing"
    exit 1
fi

echo ""
echo "========================================================"
echo "Verifying strict validation catches typos"
echo "========================================================"
if uv run python -c "
from culturedx.core.config import LLMConfig
try:
    LLMConfig(model='foo')  # should fail
    import sys; sys.exit(1)
except Exception:
    pass
" 2>&1; then
    echo "  ✓ Strict validation works (typos now raise ValidationError)"
else
    echo "  ✗ Strict validation did not activate"
    exit 1
fi

echo ""
echo "========================================================"
echo "All fixes applied successfully on branch fix/queue-runtime-bugs"
echo "========================================================"
echo ""
echo "Summary of changes:"
git diff --stat HEAD
echo ""
echo "Next steps:"
echo "  1. Review: git diff"
echo "  2. Commit: git add -A && git commit -m 'fix: queue runtime bugs (top1_code NameError, strict config, R13/R14 configs)'"
echo "  3. Push: git push origin fix/queue-runtime-bugs"
echo "  4. Merge: git checkout main-v2.4-refactor && git merge fix/queue-runtime-bugs --ff-only"
echo ""
echo "Then re-run broken experiments:"
echo "  R21: uv run culturedx run -c configs/base.yaml -c configs/vllm_awq.yaml \\"
echo "       -c configs/v2.4_final.yaml -c configs/overlays/r21_evidence_stacked.yaml \\"
echo "       --with-evidence -d lingxidiag16k --data-path data/raw/lingxidiag16k \\"
echo "       -n 1000 --run-name r21_evidence_stacked_v2"
echo ""
echo "  R13: (restart vLLM with Qwen3-8B-Instruct-AWQ first)"
echo "       uv run culturedx run -c configs/base.yaml -c configs/vllm_qwen3_8b.yaml \\"
echo "       -c configs/v2.4_final.yaml -d lingxidiag16k --data-path data/raw/lingxidiag16k \\"
echo "       -n 1000 --run-name r13_qwen3_8b_v2"
echo ""
echo "  R14: (restart vLLM with Yi-1.5-34B-Chat-AWQ first)"
echo "       uv run culturedx run -c configs/base.yaml -c configs/v2.4_final.yaml \\"
echo "       -c configs/overlays/r14_non_qwen.yaml \\"
echo "       -d lingxidiag16k --data-path data/raw/lingxidiag16k \\"
echo "       -n 1000 --run-name r14_yi_34b"
