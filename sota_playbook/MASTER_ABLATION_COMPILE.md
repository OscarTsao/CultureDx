# Master Ablation Compile Script

**執行時機**：所有 T1-T4 實驗跑完後，產出 paper-ready Table 1 / Table 2。

## 功能

自動掃描 `results/validation/` 下所有 experiment directories，compile 成：
- Table 1: Main results — 對比 paper baselines
- Table 2: Ablation — CultureDx 內部組件 impact
- Table 3: Per-class F1 breakdown

## Script 設計

```python
# scripts/compile_ablation_table.py

"""Auto-compile paper-ready ablation tables from results/validation/."""

import json
from pathlib import Path
from typing import Dict, Any

# Paper Table 4 SOTA baselines (LingxiDiag-16K)
PAPER_BASELINES = {
    'TF-IDF + SVM':       {'12c_Acc': 0.308, '12c_Top1': 0.481, '12c_Top3': 0.566, '12c_m_F1': 0.242, '12c_w_F1': 0.482, 'Overall': 0.507},
    'TF-IDF + RF':        {'12c_Acc': 0.315, '12c_Top1': 0.377, '12c_Top3': 0.403, '12c_m_F1': 0.122, '12c_w_F1': 0.382, 'Overall': 0.458},
    'TF-IDF + LR':        {'12c_Acc': 0.268, '12c_Top1': 0.496, '12c_Top3': 0.645, '12c_m_F1': 0.295, '12c_w_F1': 0.520, 'Overall': 0.533},
    'Qwen3-1.7B':         {'12c_Acc': 0.145, '12c_Top1': 0.460, '12c_Top3': 0.545, '12c_m_F1': 0.162, '12c_w_F1': 0.394, 'Overall': 0.448},
    'Baichuan-M2-32B':    {'12c_Acc': 0.232, '12c_Top1': 0.376, '12c_Top3': 0.489, '12c_m_F1': 0.136, '12c_w_F1': 0.378, 'Overall': 0.461},
    'Baichuan-M3-235B':   {'12c_Acc': 0.254, '12c_Top1': 0.393, '12c_Top3': 0.514, '12c_m_F1': 0.143, '12c_w_F1': 0.396, 'Overall': 0.476},
    'Qwen3-4B':           {'12c_Acc': 0.021, '12c_Top1': 0.475, '12c_Top3': 0.637, '12c_m_F1': 0.168, '12c_w_F1': 0.422, 'Overall': 0.474},
    'Qwen3-8B':           {'12c_Acc': 0.012, '12c_Top1': 0.459, '12c_Top3': 0.599, '12c_m_F1': 0.177, '12c_w_F1': 0.420, 'Overall': 0.473},
    'GPT-OSS-20B':        {'12c_Acc': 0.259, '12c_Top1': 0.463, '12c_Top3': 0.523, '12c_m_F1': 0.181, '12c_w_F1': 0.408, 'Overall': 0.479},
    'Kimi-K2-Think':      {'12c_Acc': 0.335, '12c_Top1': 0.427, '12c_Top3': 0.468, '12c_m_F1': 0.155, '12c_w_F1': 0.379, 'Overall': 0.484},
    'DeepSeek-V3.2':      {'12c_Acc': 0.323, '12c_Top1': 0.438, '12c_Top3': 0.489, '12c_m_F1': 0.164, '12c_w_F1': 0.408, 'Overall': 0.501},
    'GPT-5-Mini':         {'12c_Acc': 0.409, '12c_Top1': 0.487, '12c_Top3': 0.505, '12c_m_F1': 0.188, '12c_w_F1': 0.418, 'Overall': 0.504},
    'Gemini-3-Flash':     {'12c_Acc': 0.172, '12c_Top1': 0.492, '12c_Top3': 0.574, '12c_m_F1': 0.197, '12c_w_F1': 0.439, 'Overall': 0.510},
    'Qwen3-32B':          {'12c_Acc': 0.241, '12c_Top1': 0.470, '12c_Top3': 0.566, '12c_m_F1': 0.188, '12c_w_F1': 0.431, 'Overall': 0.506},
    'Claude-Haiku-4.5':   {'12c_Acc': 0.395, '12c_Top1': 0.478, '12c_Top3': 0.501, '12c_m_F1': 0.199, '12c_w_F1': 0.412, 'Overall': 0.516},
    'Grok-4.1-Fast':      {'12c_Acc': 0.351, '12c_Top1': 0.465, '12c_Top3': 0.495, '12c_m_F1': 0.195, '12c_w_F1': 0.409, 'Overall': 0.521},
}

# Known CultureDx experiment paths
CULTUREDX_EXPERIMENTS = {
    'CultureDx factorial_b': 'results/validation/factorial_b_improved_noevidence/metrics.json',
    'CultureDx qwen3_8b_dtv': 'results/validation/multi_backbone/qwen3_8b_dtv/metrics.json',
    'CultureDx 05_dtv_v2_rag': 'results/validation/05_dtv_v2_rag/metrics.json',
    'CultureDx +T1-NOS': 'results/validation/t1_nos/metrics.json',
    'CultureDx +T1-OTHERS': 'results/validation/t1_others/metrics.json',
    'CultureDx +T1-F43TRIG': 'results/validation/t1_f43trig/metrics.json',
    'CultureDx +T1-SUBCODE': 'results/validation/t1_subcode/metrics.json',
    'CultureDx +T1-MAXDX': 'results/validation/t1_maxdx/metrics.json',
    'CultureDx +T1-COMBINED': 'results/validation/t1_combined/metrics.json',
    'CultureDx T2-RRF (3-way)': 'results/validation/t2_rrf/metrics.json',
    'CultureDx T2-RRF+LowFreq': 'results/validation/t2_lowfreq/metrics.json',
    'CultureDx T2-CONTRAST': 'results/validation/t2_contrast/metrics.json',
    'CultureDx T3-TFIDF-STACK (4-way)': 'results/validation/t3_tfidf_stack/metrics.json',
    'CultureDx T3-LORA-CLF': 'results/validation/t3_lora_clf/metrics.json',
    'CultureDx T3-LORA-CHECKER': 'results/validation/t3_lora_checker/metrics.json',
    'CultureDx T4-LEARNED-CALIB': 'results/validation/t4_learned_calib/metrics.json',
    'CultureDx T4-F1-OPT': 'results/validation/t4_f1_opt/metrics.json',
    'CultureDx Final (all)': 'results/validation/culturedx_final/metrics.json',
}

METRICS_ORDER = ['12c_Acc', '12c_Top1', '12c_Top3', '12c_m_F1', '12c_w_F1', 'Overall']


def load_metrics(path: str) -> Dict[str, float]:
    """Load metrics.json and normalize key names."""
    p = Path(path)
    if not p.exists():
        return None
    with open(p) as f:
        data = json.load(f)
    
    # Normalize different key formats
    out = {}
    for m in METRICS_ORDER:
        # Try multiple key variants
        for k_variant in [m, m.replace('12c_', '12class_'), m.replace('_', '-')]:
            if k_variant in data:
                out[m] = data[k_variant]
                break
    return out


def format_cell(val: float, is_bold: bool = False, is_underline: bool = False) -> str:
    """Format a metric cell with Markdown emphasis."""
    if val is None:
        return '—'
    s = f"{val:.3f}"
    if is_bold:
        s = f"**{s}**"
    if is_underline:
        s = f"__{s}__"
    return s


def compile_table_main():
    """Table 1: Main results, all methods x all metrics."""
    # Load all methods
    rows = []
    # Paper baselines
    for name, m in PAPER_BASELINES.items():
        rows.append((name, m, 'paper'))
    
    # CultureDx experiments (only include successful ones)
    for name, path in CULTUREDX_EXPERIMENTS.items():
        m = load_metrics(path)
        if m:
            rows.append((name, m, 'culturedx'))
    
    # Find best/second-best per metric
    best = {m: max((r[1].get(m, 0) for r in rows), default=0) for m in METRICS_ORDER}
    second_best = {}
    for m in METRICS_ORDER:
        vals = sorted(set(r[1].get(m, 0) for r in rows), reverse=True)
        second_best[m] = vals[1] if len(vals) > 1 else 0
    
    # Print markdown table
    header = '| Method | ' + ' | '.join(METRICS_ORDER) + ' |'
    sep = '|---|' + '|'.join(['---'] * len(METRICS_ORDER)) + '|'
    print(header)
    print(sep)
    
    for name, m, kind in rows:
        cells = [name]
        for metric in METRICS_ORDER:
            val = m.get(metric)
            is_bold = val == best[metric]
            is_underline = val == second_best[metric]
            cells.append(format_cell(val, is_bold, is_underline))
        print('| ' + ' | '.join(cells) + ' |')


def compile_table_ablation():
    """Table 2: Ablation — only CultureDx experiments, incremental."""
    rows = []
    for name, path in CULTUREDX_EXPERIMENTS.items():
        m = load_metrics(path)
        if m:
            rows.append((name, m))
    
    # Sort by Overall descending
    rows.sort(key=lambda x: -x[1].get('Overall', 0))
    
    # Compare each to factorial_b baseline
    baseline = next((m for n, m in rows if 'factorial_b' in n), None)
    if not baseline:
        return
    
    print('| Method | 12c_Acc | Δ | Top-1 | Δ | Top-3 | Δ | F1_m | Δ | F1_w | Δ | Overall | Δ |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    
    for name, m in rows:
        cells = [name]
        for metric in METRICS_ORDER:
            val = m.get(metric, 0)
            delta = val - baseline.get(metric, 0)
            cells.append(f"{val:.3f}")
            cells.append(f"{'+' if delta >= 0 else ''}{delta*100:.1f}")
        print('| ' + ' | '.join(cells) + ' |')


def compile_gap_analysis():
    """Gap analysis: CultureDx final vs paper SOTA."""
    final_m = load_metrics('results/validation/culturedx_final/metrics.json')
    if not final_m:
        print("No final system metrics yet — run the final ensemble first.")
        return
    
    paper_sota = {m: max(v.get(m, 0) for v in PAPER_BASELINES.values()) for m in METRICS_ORDER}
    
    print('## Final Gap Analysis: CultureDx vs Paper SOTA')
    print()
    print('| Metric | Paper SOTA | CultureDx Final | Gap |')
    print('|---|---|---|---|')
    for metric in METRICS_ORDER:
        sota = paper_sota[metric]
        ours = final_m.get(metric, 0)
        gap = ours - sota
        status = '✅' if gap > 0 else ('=' if abs(gap) < 0.005 else '❌')
        print(f"| {metric} | {sota:.3f} | {ours:.3f} | {'+' if gap >= 0 else ''}{gap*100:.1f}pp {status} |")


if __name__ == '__main__':
    print('=' * 60)
    print('# Table 1: Main Results')
    print('=' * 60)
    compile_table_main()
    
    print()
    print('=' * 60)
    print('# Table 2: CultureDx Ablation (Δ vs factorial_b baseline)')
    print('=' * 60)
    compile_table_ablation()
    
    print()
    print('=' * 60)
    compile_gap_analysis()
```

## 使用方式

```bash
# 在所有實驗跑完後
cd ~/CultureDx
python scripts/compile_ablation_table.py > paper/tables/compiled_main_results.md
```

## Output Schema 確認

這個 script 依賴 `results/validation/{exp_id}/metrics.json` 的固定格式。確保所有實驗輸出都有：

```json
{
  "12c_Acc": 0.432,
  "12c_Top1": 0.531,
  "12c_Top3": 0.554,
  "12c_m_F1": 0.202,
  "12c_w_F1": 0.449,
  "Overall": 0.523
}
```

建議實驗跑完後新增 `scripts/standardize_metrics.py`，把所有 experiment dir 的 metrics 統一成這個 schema。

## 延伸

加入統計檢定：
- McNemar's test: CultureDx Final vs TF-IDF+LR per-case
- Bootstrap CI: 每個指標的 95% CI
- 只有 significant improvement (p < 0.05) 的 metric 在主表加 * 標記
