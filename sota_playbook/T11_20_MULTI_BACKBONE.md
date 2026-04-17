# T11-MULTI-BACKBONE：跨 Model Family Ensemble

## 動機

你的 CultureDx 目前全靠 Qwen3-32B-AWQ 一個 backbone。Paper Table 4 的各 LLM baseline 在 12c 不同 metric 上表現差異很大：
- Qwen3-32B: Acc 0.241, Top-1 0.470
- Claude-Haiku-4.5: Acc 0.395, Top-1 0.478
- GPT-5-Mini: Acc 0.409, Top-1 0.487
- DeepSeek-V3.2: Acc 0.323, Top-1 0.438
- Baichuan-M3-235B (medical-tuned): Acc 0.254, Top-1 0.393

每個 model 有不同的 failure mode。**用 3-4 個不同 family 的 model 各跑 CultureDx，然後 ensemble**，可以再壓一點 variance。

Master 分支的 `scripts/analyze_vllm_sweep.py` 和 `multi-backbone orchestration` 暗示你已經做過類似實驗，可以復用。

## 假設

Ensemble CultureDx on multiple backbones:
- **Qwen3-32B-AWQ** (primary, 你已優化)
- **Baichuan-M3-235B** (medical-tuned, 可能抓得到 F20/F31 等複雜 psychiatric case)
- **DeepSeek-V3.2** (general strong)
- **Claude-Haiku-4.5** (via API, 有配額才加)

預期不同 backbone 在不同 class 強：
- Qwen3: overall 穩
- Baichuan-M3: medical 專業
- DeepSeek-V3.2: strong reasoning

RRF ensemble 後：Top-1 +1-2pp, Top-3 +2-3pp, F1_macro +2pp。

## 技術設計

### Step 1：Backbone Infrastructure

你需要能讓同一個 CultureDx pipeline 切換不同 backbone：

```yaml
# configs/model_pools/qwen3_32b.yaml
llm:
  provider: vllm
  model: Qwen/Qwen3-32B-AWQ
  base_url: http://localhost:8001/v1
  max_tokens: 2048

# configs/model_pools/baichuan_m3.yaml
llm:
  provider: vllm
  model: baichuan-inc/Baichuan-M3-235B-Instruct  # or AWQ version
  base_url: http://localhost:8002/v1
```

然後分別跑：

```bash
for backbone in qwen3_32b baichuan_m3 deepseek_v3_2; do
    uv run culturedx run \
      -c configs/base.yaml \
      -c configs/model_pools/$backbone.yaml \
      -c configs/v2.4_final.yaml \
      -c configs/overlays/checker_v2_improved.yaml \
      -d lingxidiag16k -n 1000 \
      -o results/validation/multi_backbone/$backbone
done
```

### Step 2：Per-backbone Profile

每個 backbone 跑完後，產出 per-class F1 breakdown：

```python
# scripts/analyze_backbone_profile.py
"""Which backbone is best at which class?"""

for backbone, predictions in backbones.items():
    per_class_f1 = compute_per_class(predictions)
    print(f"{backbone}: F32 {per_class_f1['F32']:.3f}, F41 {per_class_f1['F41']:.3f}, ...")

# Output expected pattern:
# Qwen3-32B: F32 0.65, F41 0.58, F43 0.0, F98 0.0, ...
# Baichuan-M3: F32 0.58, F41 0.56, F20 0.45, F31 0.38, ...  # better on complex psychiatric
# DeepSeek-V3.2: F32 0.62, F41 0.55, F39 0.15, Z71 0.20, ...  # better on Others/Z71
```

### Step 3：Class-Aware Backbone Weights

如果每個 backbone 在不同 class 強，可以做 **class-specific backbone weighting**：

```python
# For each (case, class), weight each backbone's prediction by its F1 on that class
# (computed from calibration set, not test)

class_weights = {
    "F32": {"qwen3": 0.65, "baichuan": 0.58, "deepseek": 0.62},
    "F41": {"qwen3": 0.58, "baichuan": 0.56, "deepseek": 0.55},
    "F20": {"qwen3": 0.10, "baichuan": 0.45, "deepseek": 0.12},
    # ...
}

def class_aware_rrf(rankings_per_backbone, class_weights):
    scores = defaultdict(float)
    for backbone, ranking in rankings_per_backbone.items():
        for rank, code in enumerate(ranking):
            parent = to_paper_parent(code)
            weight = class_weights.get(parent, {}).get(backbone, 1.0)
            scores[code] += weight / (60 + rank + 1)
    return sorted(scores.items(), key=lambda x: -x[1])
```

### Step 4：評估 vs RRF (uniform)

做 ablation：
- Uniform RRF (3-4 backbones, equal weight)
- Class-aware RRF
- Per-backbone standalone

## 計算成本

每個 backbone 跑 N=1000 需要 3-8 小時（depending on model size + vLLM throughput）。
- Qwen3-32B-AWQ: 3 小時（quantized, fast）
- Baichuan-M3-235B: 5-8 小時（大 model）
- DeepSeek-V3.2: 需要 access，可能需要 API（Claude/OpenAI）

**建議**：先只用 Qwen3-32B-AWQ + Baichuan-M3 兩個 open-source models 驗證概念。API-based models 如 Claude-Haiku-4.5 太貴，只在最後的 cherry-on-top 實驗用（N=200 足夠）。

## 成功判準

- 2-backbone ensemble 在 Top-1 / Top-3 比 Qwen3-32B-only 提升 ≥ 1pp
- Per-backbone profile 顯示至少 2 class 在 Baichuan-M3 上比 Qwen3 顯著強（e.g., F20/F31）
- Class-aware RRF 比 uniform RRF 在 F1_macro 多 +1pp

## 論文敘事

Multi-backbone 可以當 ablation 不是核心 claim。論文可以加一段：

> "Our CultureDx framework is backbone-agnostic. To test robustness, we evaluated the same pipeline with three different open-source LLMs as backbones: Qwen3-32B-AWQ, Baichuan-M3-235B, and DeepSeek-V3.2. All three backbones produced comparable 12c accuracy (within 3pp), confirming that the improvements come from the pipeline architecture rather than a specific model. The final ensemble of three backbones reached [result], +X pp above any single backbone."

## 輸出

- `results/validation/multi_backbone/qwen3_32b/`
- `results/validation/multi_backbone/baichuan_m3/`
- `results/validation/multi_backbone/deepseek/`
- `results/validation/t11_multi_backbone_ensemble/`
- `paper/tables/backbone_profile.md`
