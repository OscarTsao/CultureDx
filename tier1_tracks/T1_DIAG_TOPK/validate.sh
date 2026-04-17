#!/usr/bin/env bash
# T1 validation: run smoke test + full + error taxonomy diff
# Run from CultureDx repo root

set -e

echo "=== T1 Smoke Test N=50 ==="
uv run culturedx run \
  -c configs/base.yaml \
  -c configs/vllm_awq.yaml \
  -c configs/v2.4_final.yaml \
  -d lingxidiag16k \
  --data-path data/raw/lingxidiag16k \
  -n 50 \
  --run-name t1_smoke_n50

echo ""
echo "=== Checking ranked_codes length distribution ==="
python3 -c "
import json
from collections import Counter
lens = Counter()
with open('results/validation/t1_smoke_n50/predictions.jsonl') as f:
    for line in f:
        d = json.loads(line)
        ranked = d['decision_trace']['diagnostician']['ranked_codes']
        lens[len(ranked)] += 1
print('ranked_codes length distribution:')
for k, v in sorted(lens.items()):
    print(f'  len={k}: {v}')
total_5 = lens.get(5, 0)
total = sum(lens.values())
print(f'Percentage with len>=4: {(lens.get(5,0)+lens.get(4,0))/total*100:.1f}%')
assert total_5 >= total * 0.7, 'Expected >70% cases with ranked_codes of length 5'
print('ASSERTION OK')
"

echo ""
echo "=== Full N=1000 Run ==="
read -p "Smoke test OK, proceed with full N=1000? [y/N] " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

uv run culturedx run \
  -c configs/base.yaml \
  -c configs/vllm_awq.yaml \
  -c configs/v2.4_final.yaml \
  -d lingxidiag16k \
  --data-path data/raw/lingxidiag16k \
  -n 1000 \
  --run-name t1_diag_topk_n1000 \
  2>&1 | tee outputs/t1_diag_topk_n1000.log

echo ""
echo "=== Error Taxonomy Comparison ==="
# Temporarily modify error taxonomy script to point to new run
sed -i.bak 's|results/validation/factorial_b_improved_noevidence/predictions.jsonl|results/validation/t1_diag_topk_n1000/predictions.jsonl|g' scripts/error_taxonomy_v24.py
python3 scripts/error_taxonomy_v24.py > results/validation/t1_diag_topk_n1000/error_taxonomy_report.txt
# Restore original
mv scripts/error_taxonomy_v24.py.bak scripts/error_taxonomy_v24.py

echo ""
echo "=== BEFORE (factorial_b) ==="
python3 -c "
import json
d = json.load(open('results/validation/factorial_b_improved_noevidence/metrics_summary.json'))
t = d['metrics']['table4']
for k in ['12class_Acc','12class_Top1','12class_Top3','12class_F1_macro','12class_F1_weighted']:
    print(f'  {k}: {t[k]:.3f}')
"
echo "=== AFTER (t1_diag_topk_n1000) ==="
python3 -c "
import json
d = json.load(open('results/validation/t1_diag_topk_n1000/metrics_summary.json'))
t = d['metrics']['table4']
for k in ['12class_Acc','12class_Top1','12class_Top3','12class_F1_macro','12class_F1_weighted']:
    print(f'  {k}: {t[k]:.3f}')
"

echo ""
cat results/validation/t1_diag_topk_n1000/error_taxonomy_report.txt
