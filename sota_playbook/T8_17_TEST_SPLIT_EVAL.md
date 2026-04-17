# T8-TEST-SPLIT-EVAL：在 Test Split 做正式評估

## **為什麼這是最關鍵的一個 track**

你目前所有結果都在 **validation split** 跑（N=1000）。但：

1. **LingxiDiag-16K 有明確的 test split (N=1000, 分布相同)**，paper Table 4 的所有 baselines 是**在 validation split 評估**的（paper p.3：「randomly selected 1,000 samples each for validation and testing」）
2. 論文慣例：**validation 用來調 hyperparameter，test 用來報 final metric**
3. 你所有 T1-T7 實驗都用 val 做 calibration（threshold sweep, weights grid, offset tuning...），**這本質上是用 val 做 overfitting**
4. 如果直接拿 val 分數當 paper Table 1 的 final result，reviewers 會要求 test split evaluation，你會被打回重跑
5. 更糟：若 val overfitting 嚴重，test 分數可能比 val 差 3-5pp，論文 claim 會縮水

**這個 track 不是 optional，是必做**。

## 目標

在所有調參（T1-T7）都完成後，把**最終系統**在 test split (N=1000) 跑一次，得到真正的 paper-ready 結果。

## 執行時機

**必須**在以下都完成後：
- T1 組合（NOS + OTHERS + F43TRIG + MAXDX）已定案
- T2 ensemble weights 已 fine-tune
- T3-TFIDF-STACK 已調好 weights 和 thresholds
- T4 (如果做) 的 offsets 已固定
- T5, T6, T7 整合完成

然後**一次性** freeze 整個 pipeline，**在 test split 跑一次**。

## 關鍵原則：不可 peek

測跑 test 後，**不能根據 test 結果回去調參**。這是 scientific integrity 的底線。

如果 test 結果讓你失望，你只能：
- 在 paper 裡誠實報告
- 不能回去改 hyperparameter 再跑一次 test
- 唯一合法的修改：bug fix（且 bug 和你測 test 無關）

## 技術設計

### 檔案 1：驗證 test split 存在

```bash
# 確認 data/raw/lingxidiag16k/ 裡面有 test file
ls data/raw/lingxidiag16k/
# 應該有：
# LingxiDiag-16K_train_data.json (14000 cases)
# LingxiDiag-16K_validation_data.json (1000)
# LingxiDiag-16K_test_data.json (1000)
```

如果沒有 test file，從 LingxiDiagBench 官方 repo 找（或 HuggingFace dataset）。

### 檔案 2：在 dataset adapter 裡支援 split 參數

```python
# src/culturedx/data/adapters/lingxidiag16k.py
class LingxiDiag16KAdapter:
    def load(self, path: str, split: str = "validation"):
        """Load specified split: train / validation / test."""
        file_map = {
            "train": "LingxiDiag-16K_train_data.json",
            "validation": "LingxiDiag-16K_validation_data.json",
            "test": "LingxiDiag-16K_test_data.json",
        }
        fn = file_map.get(split)
        if not fn:
            raise ValueError(f"Unknown split: {split}")
        # ...
```

確認 CLI 參數 `--split test` 能透傳。

### 檔案 3：Freeze config

建立 `configs/final/culturedx_v3_final.yaml`：

```yaml
# ** DO NOT MODIFY AFTER FIRST TEST RUN **
# Frozen on 2026-05-XX after val split tuning complete

extends:
  - configs/base.yaml
  - configs/vllm_awq.yaml
  - configs/v2.4_final.yaml
  - configs/overlays/checker_v2_improved.yaml
  - configs/overlays/t1_nos_routing.yaml
  - configs/overlays/t1_others_fallback.yaml
  - configs/overlays/t1_f43_trigger.yaml
  - configs/overlays/t5a_pairwise.yaml    # if T5 done
  - configs/overlays/t7_sc_diag.yaml      # if T7 done
mode:
  # specific hyperparameters locked at validated values
  others_fallback_threshold: 0.45  # locked from T1-OTHERS sweep
  comorbid_min_ratio: 0.85         # locked from T1-MAXDX sweep
  sc_n_samples: 5                  # from T7
  # ... etc
```

### 檔案 4：Final run script

```bash
# scripts/run_final_eval.sh
#!/bin/bash
set -euo pipefail

echo "=== FINAL TEST SPLIT EVALUATION ==="
echo "NO HYPERPARAMETER CHANGES ALLOWED AFTER THIS RUN"
read -p "Press Enter to proceed or Ctrl+C to abort..."

# Single System Run
uv run culturedx run \
    -c configs/final/culturedx_v3_final.yaml \
    -d lingxidiag16k \
    --data-path data/raw/lingxidiag16k \
    --split test \
    -n 1000 \
    --seed 42 \
    -o results/test/culturedx_v3_final

# Ensemble (if applicable)
# First run ensemble member systems on test split
# Then combine via scripts/run_ensemble.py

# Report
python scripts/compile_ablation_table.py --split test --out paper/tables/final_test_results.md
```

### 檔案 5：Ensemble 成員需要各自在 test split 跑

如果你 final system 是 ensemble（T3-TFIDF-STACK 4-way 或 5-way），每個 member system 都要在 test split 跑一次：

```bash
# Factorial_b on test
uv run culturedx run -c ... -c configs/overlays/checker_v2_improved.yaml --split test -n 1000 -o results/test/factorial_b

# Qwen3-8B DtV on test
uv run culturedx run -c ... --backbone qwen3-8b --split test -n 1000 -o results/test/qwen3_8b_dtv

# 05 DtV on test
uv run culturedx run -c ... -c configs/ablations/05_hied_dtv_v2_rag.yaml --split test -n 1000 -o results/test/05_dtv_v2_rag

# TF-IDF on test (此步需要 predict on test, 但 TF-IDF 是 fitted on train 的，所以只是 inference)
uv run python scripts/infer_tfidf.py --split test --out outputs/tfidf_baseline/test_predictions.jsonl

# Ensemble
uv run python scripts/run_ensemble.py --split test --weights <locked> --out results/test/t3_tfidf_stack_final
```

## 成功判準

在 test split 上：
- 所有 5 個 12c metric 超越 paper baseline SOTA (paper Table 4 的 best per metric)
- Val vs test gap ≤ 2pp（若 gap > 3pp，可能有 overfit，paper 要討論）

## 論文要呈現的 table

| Method | 12c_Acc | Top-1 | Top-3 | F1_m | F1_w | Overall | Split |
|---|---|---|---|---|---|---|---|
| All paper baselines | ... | ... | ... | ... | ... | ... | val |
| CultureDx-Core | ... | ... | ... | ... | ... | ... | val |
| CultureDx-Full | ... | ... | ... | ... | ... | ... | val |
| **CultureDx-Core (test)** | ... | ... | ... | ... | ... | ... | test |
| **CultureDx-Full (test)** | ... | ... | ... | ... | ... | ... | test |

Paper baselines 的 test split 分數沒公開（paper 只報 val 分），所以**你 test split 是**新的** result**。你可以：
- Option A：只報你的 test 分數，val 留作 dev-set 結果
- Option B：**跑所有 baseline 在 test split**（TF-IDF+LR 你自己能 re-train & predict，其他 LLM baselines 你沒 API access 無法重跑）

Option A 簡單。Option B 最理想但只 TF-IDF+LR 可做。

**建議折衷**：你用 val 的分數當 "dev set" results（和 paper baseline 直接比），再報 test split 的 CultureDx 分數作 "holdout evaluation"。這樣兩邊都不吃虧。

## 延伸：跨 dataset test

如果還有時間，可在以下 dataset 作 out-of-distribution test：
- LingxiDiag-Clinical (1709 real cases) — paper Table 7 有數字可比
- MDD-5k — 你有歷史結果
- E-DAIC — 你 master 分支做過英文 transfer

## 輸出

- `results/test/culturedx_v3_final/` — final single system
- `results/test/t3_tfidf_stack_final/` — final ensemble
- `paper/tables/final_test_results.md` — paper-ready table
- `paper/tables/val_vs_test_gap.md` — gap analysis

## Claude Code Prompt（短版，因為實作簡單）

```
你在 CultureDx repo。目標：freeze 最終架構後，在 LingxiDiag-16K test split (N=1000) 跑一次完整評估，產生 paper-ready final result。

背景：所有調參都已在 validation split 完成（T1-T7）。現在必須在 test split 做 holdout evaluation。**跑完 test split 後禁止修改任何 hyperparameter。**

STEP 1：確認 test split file 存在
- ls data/raw/lingxidiag16k/ | grep test
- 若不存在，從 LingxiDiagBench 官方或 HF dataset 下載

STEP 2：擴充 dataset adapter 支援 --split test
- 讀 src/culturedx/data/adapters/lingxidiag16k.py
- 若尚未支援 split 參數，加入
- 確認 CLI 的 --split 能透傳到 adapter

STEP 3：Freeze final config
- 讀 validation 上最好的 experiment 組合（我會告訴你是哪幾個）
- 整合所有 overlay 到 configs/final/culturedx_v3_final.yaml
- 加 HEADER 註解 "FROZEN ON {DATE}, DO NOT MODIFY"

STEP 4：跑每個 ensemble member on test split
- factorial_b, qwen3_8b_dtv, 05_dtv_v2_rag, TF-IDF, (+其他 T5-T7 output) 各跑一次 test
- 存 results/test/{system_name}/

STEP 5：跑 final ensemble
- 用 validation 上 tuned 的 weights (locked!)
- 輸出 results/test/culturedx_final/

STEP 6：Metrics
- 用 lingxidiag_paper.py 評估每個 system 和 ensemble
- 產出 paper/tables/final_test_results.md，格式：
  | Method | Split | 12c_Acc | Top-1 | Top-3 | F1_m | F1_w | Overall |
  每個系統兩行（val + test）

STEP 7：Val-Test gap 分析
- 若所有 metric 的 val-test gap < 2pp → 系統穩健，paper 可以直接報 test 分數
- 若 gap > 3pp → 論文加一節 "Generalization Gap Analysis" 討論 overfitting
- 特別注意：F1_macro 是最容易 overfit 的（因為 T4 optimizer 直接在 val 上 tune）

STEP 8：Bootstrap CI on test
- 用 scripts/bootstrap_ci.py on test predictions
- 報告 95% CI for each metric

報告：
1. 每個 system 的 val vs test 分數
2. Final ensemble 的 test 分數
3. 和 paper Table 4 的 gap
4. Bootstrap CI
```
