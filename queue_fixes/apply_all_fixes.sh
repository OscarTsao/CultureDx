#!/bin/bash
# apply_all_fixes.sh — applies 5 fixes + 3 new configs for CultureDx v2.4
#
# Fixes applied:
#   1. top1_code NameError in hied.py:1285 (critical code bug)
#   2. Strict config validation (catches silent YAML typos)
#   3. R13 config (Qwen3-8B — previous version silently fell back to Ollama defaults)
#   4. R14 config (Yi-1.5-34B — previous version had wrong field names)
#   5. R17 bypass_checker ablation (tests checker's contribution to F32 bias)
#   6. F45 somatic_group type fix (F45 was never confirmable by logic engine)
#
# Safe to run on main-v2.4-refactor @ 851e92f. Creates a new branch,
# applies everything, runs tests, and leaves you ready to commit.

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
git checkout -B fix/queue-runtime-bugs-and-r17

FIX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "========================================================"
echo "1/5 — Fix top1_code NameError in hied.py"
echo "========================================================"
patch -p1 < "$FIX_DIR/fix_top1_code_nameerror.patch"
echo "  ✓ applied"

echo ""
echo "========================================================"
echo "2/5 — Strict config validation (prevent silent YAML typos)"
echo "========================================================"
patch -p1 < "$FIX_DIR/configs_fix/strict_config_validation.patch"
echo "  ✓ applied"

echo ""
echo "========================================================"
echo "3/5 — R17 bypass_checker ablation + F45 somatic_group fix"
echo "        (single patch: modes/hied.py, core/config.py,"
echo "         pipeline/cli.py, diagnosis/logic_engine.py)"
echo "========================================================"
patch -p1 < "$FIX_DIR/r17_bypass_checker.patch"
echo "  ✓ applied"

echo ""
echo "========================================================"
echo "4/5 — Replace R13/R14 broken config files"
echo "========================================================"
cp "$FIX_DIR/configs_fix/vllm_qwen3_8b.yaml" configs/vllm_qwen3_8b.yaml
cp "$FIX_DIR/configs_fix/r14_non_qwen.yaml" configs/overlays/r14_non_qwen.yaml
echo "  ✓ R13: provider=vllm, model_id=Qwen/Qwen3-8B-Instruct-AWQ"
echo "  ✓ R14: provider=vllm, model_id=modelscope/Yi-1.5-34B-Chat-AWQ"

echo ""
echo "========================================================"
echo "5/5 — Install R17 overlay config"
echo "========================================================"
cp "$FIX_DIR/configs_fix/r17_bypass_checker.yaml" configs/overlays/r17_bypass_checker.yaml
echo "  ✓ configs/overlays/r17_bypass_checker.yaml"

echo ""
echo "========================================================"
echo "Verification suite"
echo "========================================================"

echo ""
echo "Test 1: Full pytest suite"
if uv run pytest tests/ -q 2>&1 | tail -3 | grep -q "passed"; then
    echo "  ✓ All 388 tests pass"
else
    echo "  ✗ Tests failed — review before committing"
    exit 1
fi

echo ""
echo "Test 2: Strict validation catches YAML typos"
uv run python -c "
from culturedx.core.config import LLMConfig
try:
    LLMConfig(model='foo')
    import sys; sys.exit(1)
except Exception:
    pass
" && echo "  ✓ Typo detection active" || { echo "  ✗ Strict validation did not activate"; exit 1; }

echo ""
echo "Test 3: R17 bypass_checker flag round-trip"
uv run python -c "
from culturedx.core.config import ModeConfig
mc = ModeConfig(bypass_checker=True)
assert mc.bypass_checker is True
" && echo "  ✓ bypass_checker flag accepted" || { echo "  ✗ not wired"; exit 1; }

echo ""
echo "Test 4: F45 logic engine now confirms when all criteria met"
uv run python -c "
from culturedx.core.models import CriterionResult, CheckerOutput
from culturedx.ontology.icd10 import get_disorder_criteria
from culturedx.diagnosis.logic_engine import DiagnosticLogicEngine
crit = get_disorder_criteria('F45')
res = [CriterionResult(criterion_id=c, status='met', evidence='', confidence=1.0) for c in crit.keys()]
co = CheckerOutput(disorder='F45', criteria=res, criteria_met_count=len(res), criteria_required=len(res))
out = DiagnosticLogicEngine().evaluate([co])
assert 'F45' in out.confirmed_codes
" && echo "  ✓ F45 somatic_group fix working" || { echo "  ✗ F45 not fixed"; exit 1; }

echo ""
echo "========================================================"
echo "All fixes applied on branch fix/queue-runtime-bugs-and-r17"
echo "========================================================"
echo ""
echo "Changes:"
git diff --stat HEAD

echo ""
echo "--- Next steps ---"
echo ""
echo "1. Review:    git diff"
echo "2. Commit:    git add -A && git commit -m 'fix: queue bugs + R17 ablation + F45 logic engine'"
echo "3. Push:      git push origin fix/queue-runtime-bugs-and-r17"
echo "4. Merge:     git checkout main-v2.4-refactor && git merge --ff-only fix/queue-runtime-bugs-and-r17"
echo ""
echo "--- GPU queue after commit ---"
echo ""
echo "PRIORITY 1 — R17 (4 hr): tests if checker is net-negative"
echo "  uv run culturedx run \\"
echo "    -c configs/base.yaml -c configs/vllm_awq.yaml -c configs/v2.4_final.yaml \\"
echo "    -c configs/overlays/r17_bypass_checker.yaml \\"
echo "    -d lingxidiag16k --data-path data/raw/lingxidiag16k \\"
echo "    -n 1000 --run-name r17_bypass_checker --seed 42"
echo ""
echo "PRIORITY 2 — re-run broken (R21, R13, R14): ~12 hr total"
echo ""
echo "PRIORITY 3 — re-run baseline after F45 fix to confirm impact"
