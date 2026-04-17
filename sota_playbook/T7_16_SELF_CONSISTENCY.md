# T7-SELF-CONSISTENCY：Self-Consistency Sampling

## 背景

Self-consistency (Wang et al., 2022) 是一個幾乎無腦的 LLM accuracy booster：
- 用 temperature > 0 多次 sample 同一個 prompt
- 取 majority vote 作為最終答案
- 對複雜推理任務（如數學、診斷）典型提升 5-15% accuracy

你目前 CultureDx 是 `temperature=0.0`（greedy），**單次取樣**。這在 paper baseline 中很常見，但 self-consistency 在 diagnostic 類任務已被廣泛證實有效：
- Chen et al., Universal Self-Consistency, ICLR 2024
- Aggarwal et al., "Let's Sample Step by Step", EMNLP 2023

## 假設

對 Diagnostician 和 Criterion Checker 改用：
- `temperature=0.3` or `0.5`
- `n=5` samples per call
- Diagnostician: majority vote of top-1 predictions
- Criterion Checker: average predicted met probability per criterion; threshold at 0.5

預期：
- Top-1 +2-3pp（從 0.531 → 0.55+）
- Top-3 +1-2pp
- **成本：每個 case × 5 次 LLM calls，大約是 factorial_b 5 倍時間**

為了控制成本，**只對 diagnostician 做 self-consistency，checker 維持 temperature=0**。這樣只多 5× diagnostician LLM calls，total 時間約 1.5-2× factorial_b。

## 技術設計

### Strategy A：Diagnostician Self-Consistency Only

對每個 case：
1. 跑 factorial_b 正常流程（checker + logic engine + calibrator）得到 top-5 candidates
2. **針對 Diagnostician 的 ranking step**，用 temperature=0.5, n=5 重複跑
3. 對每個候選，統計在 5 個 sample 中被排進 top-1 的次數（0-5）
4. 最終 primary = 得票最多的 candidate；tie 用原 calibrator score 破

### Strategy B：Full Pipeline Self-Consistency

對每個 case：
1. 用 temperature=0.5, n=5 跑整個 factorial_b（diagnostician + checker + logic + calibrator）
2. 對 5 個 ranked lists 做 RRF fusion（你之前做 ensemble 已實作）
3. Top-1 = RRF fusion top-1

Strategy B 效果最好但成本最高（5× all LLM calls, ~5× 時間）。

### Strategy C：Per-Criterion Checker Self-Consistency

對每個 criterion：
1. 用 temperature=0.3, n=3 跑 checker，得到 3 個 met/not_met 判斷
2. 取 majority vote 當 criterion 最終結果（不看 probability，看 3 次中有幾次 "met"）

這個對 criterion accuracy 應該有 +3-5pp 提升（criterion accuracy 高 → end-to-end 好），但代價是 3× checker LLM calls（checker 本來就是最貴的階段）。

### 建議：A + C 組合

- Diagnostician: n=5, temp=0.5
- Checker: n=3, temp=0.3
- Logic engine / Calibrator: deterministic, 單次
- Total overhead: ~4× factorial_b 時間

### Budget Consideration

- Factorial_b on N=1000 val 約需 4-6 小時
- +Self-consistency: 約 16-24 小時
- 如果 GPU 時間有限，先試 N=200 smoke 看效果，再決定是否做 full 1000

## 實作 sketch

### 檔案 1：`src/culturedx/agents/self_consistency.py`

```python
"""Self-consistency wrapper for LLM-based agents."""
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable

@dataclass
class SCConfig:
    enabled: bool = False
    n_samples: int = 5
    temperature: float = 0.5
    aggregation: str = "majority"  # "majority" or "average"

class SelfConsistencyWrapper:
    def __init__(self, agent, config: SCConfig):
        self.agent = agent
        self.config = config
    
    def run_with_consistency(self, input_, extract_vote_fn: Callable):
        """Run agent n times and aggregate votes."""
        if not self.config.enabled:
            return [self.agent.run(input_)]
        
        outputs = []
        for i in range(self.config.n_samples):
            # Modify LLM client temperature for this call
            with self.agent.llm.override(temperature=self.config.temperature, seed=i):
                out = self.agent.run(input_)
            outputs.append(out)
        return outputs
    
    @staticmethod
    def aggregate_ranked_lists(outputs, top_k=5):
        """Aggregate multiple ranked lists via RRF."""
        scores = Counter()
        for out in outputs:
            ranked = getattr(out, "ranked_codes", [])
            for rank, code in enumerate(ranked[:top_k]):
                scores[code] += 1.0 / (60 + rank + 1)
        return [c for c, _ in scores.most_common()]
```

### 檔案 2：整合到 HiED pipeline

```python
# In src/culturedx/modes/hied.py
class HiEDMode:
    def __init__(self, ..., sc_diag_config: SCConfig = None, sc_checker_config: SCConfig = None):
        self.diagnostician_sc = SelfConsistencyWrapper(self.diagnostician, sc_diag_config)
        self.checker_sc = SelfConsistencyWrapper(self.checker, sc_checker_config)
    
    def diagnose(self, case):
        # Diagnostician with self-consistency
        diag_outputs = self.diagnostician_sc.run_with_consistency(case, extract_vote_fn=...)
        aggregated_ranking = SelfConsistencyWrapper.aggregate_ranked_lists(diag_outputs)
        
        # Checker with self-consistency (per criterion)
        checker_outputs = []
        for disorder in top_k:
            checker_samples = self.checker_sc.run_with_consistency(disorder, ...)
            # Aggregate per-criterion met/not_met
            aggregated_checker = SelfConsistencyWrapper.aggregate_checker_outputs(checker_samples)
            checker_outputs.append(aggregated_checker)
        
        # Logic engine + calibrator (deterministic)
        ...
```

### 檔案 3：Config

```yaml
# configs/overlays/t7_self_consistency.yaml
mode:
  self_consistency:
    diagnostician:
      enabled: true
      n_samples: 5
      temperature: 0.5
    checker:
      enabled: true
      n_samples: 3
      temperature: 0.3
```

## 成功判準

- 12c_Acc ≥ 0.45 (+2pp from 0.432)
- 12c_Top1 ≥ 0.55 (+2pp)
- Top-3 ≥ 0.58
- F1_macro ≥ 0.22

如果 Strategy A + C 在 N=200 smoke 沒顯示 +1pp Top-1，基本可放棄（self-consistency 應該 consistent 顯示 improvement）。

## 成本 / 效益

- ROI: 中等。4× 時間換 +2pp Top-1 是典型比率，符合 self-consistency 文獻報告。
- 如果時間有限，這個可以 skip，優先做 T3-TFIDF-STACK / T5-REVIVE-MASTER。
- 如果時間充裕，這個是**穩賺**的 improvement，建議納入最終 pipeline。

## 延伸

- **Hybrid self-consistency**：對 high-confidence cases 用 n=1（快），low-confidence cases 用 n=5（準）
- 這需要先 calibrate 一個 confidence model（可用 factorial_b 單次 run 的 margin）

## 輸出

- `results/validation/t7_sc_diag_only/`（僅 diagnostician）
- `results/validation/t7_sc_full/`（diag + checker）

## 論文 Contribution

- Self-consistency 在 psychiatric diagnosis 的 ablation（第一篇做此實驗於這個 benchmark）
- Supports "robustness via sampling" narrative
