# T9-CROSS-DATASET：MDD-5k + LingxiDiag-Clinical 跨資料集驗證

## 為什麼必要

一個高品質論文的主要結果必須在**至少 2-3 個資料集**上驗證，否則 reviewer 會質疑 overfitting 到 LingxiDiag-16K。你 master 分支已做過 MDD-5k 實驗（from paper_narrative_v2.md 的 C13），但 v2.4-refactor 還沒重跑。另外 LingxiDiag 官方還有 **LingxiDiag-Clinical (1709 real cases)** 這個資料集你完全沒試過。

## 可用資料集

### 1. MDD-5k（你已有 adapter）

- 檔案路徑：`data/raw/mdd5k/` (adapter in `src/culturedx/data/adapters/mdd5k.py`)
- 規模：5000 synthetic conversation cases (Yin et al., AAAI 2025)
- 特色：症狀描述較 explicit，少 somatization — 和 LingxiDiag 互補
- Paper C13：你系統在 MDD-5k 的 B1/B2 already 84-97% met rate（vs LingxiDiag 13-29%）
- 作用：**證明 CultureDx 並非只靠 somatization mapping 獲益**，在 explicit-description dataset 也 competitive

### 2. LingxiDiag-Clinical（paper Table 7）

- 來自 Shanghai Mental Health Center 1709 real 門診 cases
- 分佈和 LingxiDiag-16K 接近但更 authentic
- Paper Table 7 已有 16 個 baseline 的成績
- **CultureDx 目標：在 LingxiDiag-Clinical 也全面 SOTA**，強化 claim
- 訪問：可能需要申請，或從 paper 作者聯繫

### 3. E-DAIC（英文 depression 資料集）

- 你 master 有預處理（scripts/preprocess_edaic.py）
- 來源：DAIC-WOZ (Gratch et al., 2014)，英文 semi-structured 臨床訪談
- PHQ-8 + 二元 depression label
- 價值：**跨語言驗證**，CultureDx 在英文 dataset 同樣 competitive 嗎？

## 實驗矩陣

| Dataset | CultureDx-Core | CultureDx-Full | Report Format |
|---|---|---|---|
| LingxiDiag-16K validation (N=1000) | ✅ done | ✅ done | Table 1 主結果 |
| LingxiDiag-16K **test** (N=1000) | ⏳ **必做** | ⏳ **必做** | Table 1 (驗證 val overfit) |
| MDD-5k (N=200 or 500) | ⏳ 必做 | ⏳ 必做 | Table 2 跨資料集 |
| LingxiDiag-Clinical (N=1709) | ⭐ 加分 | ⭐ 加分 | Appendix Table |
| E-DAIC (N=189) | ⭐ 論文 bonus | ⭐ 論文 bonus | Appendix |

## 核心 claim 要驗證

1. **C1 cross-dataset SOTA consistency**: 在 MDD-5k 上你的 end-to-end accuracy 也超越 single LLM baseline
2. **C2 culture-adaptive 特性**: Somatization mapping 在 LingxiDiag 上助 F41 recall +21pp，在 MDD-5k 上只 +2pp（因為 MDD-5k 本來就 explicit）
3. **C3 架構不 overfit**: 同一個 config 在多 dataset 上都 robust

## 技術改動

### Step 1：確認 MDD-5k adapter 還能用

```bash
uv run culturedx run -c configs/base.yaml -c configs/vllm_awq.yaml -c configs/v2.4_final.yaml \
  -c configs/overlays/checker_v2_improved.yaml \
  -d mdd5k --data-path data/raw/mdd5k \
  -n 50 -o outputs/smoke_mdd5k
```

如果 adapter 壞了，從 master cherry-pick `src/culturedx/data/adapters/mdd5k.py`。

### Step 2：12c label mapping

MDD-5k 原本只有 4 類（抑鬱/焦慮/混合/其他），需要映射到 LingxiDiag 的 12 類：
- 抑鬱 → F32
- 焦慮 → F41
- 混合 → F32+F41 comorbid
- 其他 → Others

Paper 作者在 MDD-5k 做 12c 的時候應該有類似映射，參考 master 分支相應配置。

### Step 3：跑 full evaluations

三個 dataset 各跑一次 factorial_b baseline + 最終 ensemble:

```bash
# LingxiDiag test split
uv run culturedx run [...] --split test -n 1000 -o results/test/lingxidiag_test_factorial_b
uv run culturedx run [...] --split test -n 1000 -o results/test/lingxidiag_test_final_ensemble

# MDD-5k
uv run culturedx run [...] -d mdd5k -n 500 -o results/cross/mdd5k_factorial_b
uv run culturedx run [...] -d mdd5k -n 500 -o results/cross/mdd5k_final_ensemble
```

### Step 4：產出 cross-dataset table

```python
# scripts/compile_cross_dataset_table.py
# 對每個 dataset，compile:
# - Factor CultureDx vs paper baselines (如果有的話)
# - CultureDx 在兩個 dataset 的 metric 一致性（std ≤ 5pp 算穩定）
```

## 成功判準

- LingxiDiag test split 的 F1_macro 和 validation split 差距 ≤ 2pp（表示沒 overfit val）
- MDD-5k 上 factorial_b 或 final ensemble **仍贏過 paper 提到的 baseline**
- 跨 dataset 的 Top-1 std ≤ 5pp（表示 system robust）

## 風險

- MDD-5k 的 test benchmark 可能沒有公開的 baseline 數字可比（只能和 paper 的 internal baseline 比）
- 如果 MDD-5k 成績不好（例如 somatization mapping 反向影響），論文 claim 會被削弱
  - **應對**：這反而變成 paper 的 honest finding — somatization mapping 在 culturally-embedded text（LingxiDiag）有效，explicit text（MDD-5k）中性或無效

## 輸出

- `results/test/lingxidiag_test_*/`
- `results/cross/mdd5k_*/`
- `results/cross/lingxidiag_clinical_*/` (if accessible)
- `results/cross/edaic_*/` (optional)
- `paper/tables/cross_dataset_results.md`
