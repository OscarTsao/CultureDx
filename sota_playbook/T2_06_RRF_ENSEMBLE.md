# T2-RRF：Triple System RRF Ensemble

## 問題

目前沒有單一系統在全部 5 個 12c 指標都是最佳：
- factorial_b: best 12c_Acc (0.432), Top-1 (0.531), F1_macro (0.202)
- qwen3_8b_dtv: best 12c_Top3 (0.644)
- 05_dtv_v2_rag: best 12c_F1_weighted (0.453)

三個系統各在不同指標優，互為互補。若能 ensemble，理論上可以逼近「在每個指標都取到最佳」。

## 假設

使用 **Reciprocal Rank Fusion (RRF)** 合併三個系統的 ranked top-k 候選。RRF 是 IR 界公認的穩健 ensemble 方法：

```
RRF_score(doc) = Σ_system 1 / (k + rank_system(doc))
```

其中 k 通常設 60（IR 領域慣例，控制 ranking decay）。

三個系統各自輸出 top-10 ranked list，合併後取新的 top-3 作為最終輸出。primary = new top-1, comorbid = new top-2（如果 met_ratio 也夠）。

**預期結果**：
- 12c_Top3 ~ 0.65+（因為 qwen3_8b_dtv 提供的多樣性被保留）
- 12c_Top1 ~ 0.55+（因為三系統在 top-1 都有一定 overlap，RRF 把這些 reinforce）
- F1_macro ~ 0.22+（因為不同系統各自抓不同 low-freq class）
- F1_weighted ~ 0.47+

## 風險

- RRF 是線性組合，可能把三個系統的系統性偏差也平均起來
- 如果三個系統都錯同一個（例如都把 F43 判成 F32），ensemble 也救不了
- 所以 RRF 後**加 T1-F43TRIG 和 T1-OTHERS 的 post-hoc rescue** 會更有效

## 技術改動

### 檔案 1：`src/culturedx/ensemble/rrf.py`（新檔）

```python
"""Reciprocal Rank Fusion for combining ranked diagnostic outputs."""
from __future__ import annotations
from collections import defaultdict
from typing import Dict, List

def rrf_fuse(
    ranked_lists: List[List[str]],
    k: int = 60,
    weights: List[float] = None,
) -> List[tuple[str, float]]:
    """Combine multiple ranked lists via Reciprocal Rank Fusion.
    
    Args:
        ranked_lists: list of ranked ICD code lists, one per system
        k: RRF constant, typically 60
        weights: optional per-system weights
    
    Returns:
        fused ranked list of (code, rrf_score) sorted descending
    """
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    
    scores = defaultdict(float)
    for i, rl in enumerate(ranked_lists):
        w = weights[i]
        for rank, code in enumerate(rl):
            scores[code] += w / (k + rank + 1)  # rank starts from 0, so +1
    
    return sorted(scores.items(), key=lambda x: -x[1])

def ensemble_predictions(
    prediction_files: List[str],
    weights: List[float] = None,
    k: int = 60,
) -> List[dict]:
    """Replay multiple predictions.jsonl files and RRF-fuse them.
    
    Args:
        prediction_files: list of paths to predictions.jsonl
        weights: optional weight per system
        k: RRF constant
    
    Returns:
        list of new prediction records with primary/comorbid from RRF
    """
    import json
    
    systems = []
    for pf in prediction_files:
        with open(pf) as f:
            preds = [json.loads(line) for line in f]
        systems.append({p["case_id"]: p for p in preds})
    
    case_ids = set(systems[0].keys())
    for s in systems[1:]:
        case_ids &= set(s.keys())
    
    fused = []
    for cid in sorted(case_ids):
        # Get each system's ranked top-10
        ranked_lists = []
        for s in systems:
            pred = s[cid]
            ranked = pred.get("decision_trace", {}).get("diagnostician", {}).get("ranked_codes", [])
            if not ranked:
                ranked = [pred["primary_diagnosis"]] + pred.get("comorbid_diagnoses", [])
            ranked_lists.append(ranked[:10])
        
        fused_scores = rrf_fuse(ranked_lists, k=k, weights=weights)
        top_codes = [c for c, s in fused_scores]
        
        gold = systems[0][cid]["gold_diagnoses"]  # same across systems
        
        fused_record = {
            "case_id": cid,
            "gold_diagnoses": gold,
            "primary_diagnosis": top_codes[0] if top_codes else "Others",
            "comorbid_diagnoses": top_codes[1:2] if len(top_codes) > 1 else [],
            "top3_codes": top_codes[:3],
            "top10_codes": top_codes[:10],
            "rrf_scores": dict(fused_scores[:10]),
            "ensemble_method": "rrf",
            "ensemble_sources": prediction_files,
        }
        fused.append(fused_record)
    
    return fused
```

### 檔案 2：`scripts/run_ensemble.py`（新檔）

```python
"""Run T2-RRF ensemble on existing predictions."""
import json
from pathlib import Path
from culturedx.ensemble.rrf import ensemble_predictions
from culturedx.eval.lingxidiag_paper import compute_table4_metrics

def main():
    systems = [
        "results/validation/factorial_b_improved_noevidence/predictions.jsonl",
        "results/validation/multi_backbone/qwen3_8b_dtv/predictions.jsonl",
        "results/validation/05_dtv_v2_rag/predictions.jsonl",
    ]
    weights_grid = [
        [1.0, 1.0, 1.0],       # equal
        [1.5, 1.0, 1.0],       # favor factorial_b
        [1.0, 1.5, 1.0],       # favor qwen3_8b (Top-3)
        [1.2, 1.2, 0.8],       # slight favor first two
    ]
    
    for w in weights_grid:
        fused = ensemble_predictions(systems, weights=w, k=60)
        # load original cases for gold labels
        cases = load_cases(...)
        metrics = compute_table4_metrics(cases, lambda c: fused_to_parents(fused, c))
        print(f"weights={w}: 12c_Acc={metrics['12class_Acc']:.3f} "
              f"Top-1={metrics['12class_Top1']:.3f} "
              f"Top-3={metrics['12class_Top3']:.3f} "
              f"F1_m={metrics['12class_F1_macro']:.3f}")

if __name__ == "__main__":
    main()
```

### 檔案 3：`configs/ensemble/t2_rrf.yaml`（新檔）

紀錄最佳 weights 與 k。

## 輸出路徑

`results/validation/t2_rrf/`

## 成功判準

- 12c_Top3 ≥ 0.64（接近 SOTA 0.645）
- 12c_Top1 ≥ 0.55
- 12c_F1_macro ≥ 0.21
- 至少 3 個 12c metric 都優於任何單一 source system

## RRF k 與 weights 調校

做 grid search：
- k ∈ {10, 30, 60, 100}
- weights: grid over simplex

如果沒改善（所有 ensemble 都打不過 factorial_b single system），那 T2-RRF 被否決，接下去只做 T2-LOWFREQ 的 fallback 方案。
