# T5-REVIVE-MASTER：Cherry-pick Master 分支已實作但 v2.4-refactor 丟掉的組件

## 背景

V2.4 refactor 為了 paper-ready 精簡，砍掉了 master 分支已經可運作的 8 個組件。這些不是從零開發，**全部是 revive 已有代碼**，ROI 極高。

## 要 Cherry-pick 的 8 個組件

| # | 組件 | Master 檔案 | 預期效益 | 優先級 |
|---|---|---|---|---|
| 1 | Pairwise Learned Ranker | `src/culturedx/diagnosis/pairwise_ranker.py` + weights | Top-1 +1.5pp, Top-3 +1pp | ⭐⭐⭐ |
| 2 | Contrastive Checker (Stage 2.5) | `src/culturedx/agents/contrastive_checker.py` | F32/F41 F1 +3pp | ⭐⭐⭐ |
| 3 | Temporal Reasoning | `src/culturedx/evidence/temporal.py` | F41.1 Criterion A recall +10pp | ⭐⭐ |
| 4 | Negation Detection | `src/culturedx/evidence/negation.py` | Precision +1-2pp, 避免假陽性 | ⭐⭐ |
| 5 | Demographic Priors | `src/culturedx/ontology/demographic_priors.py` | F1 +0.5-1pp | ⭐ |
| 6 | Shared Criteria 標註 | `src/culturedx/ontology/shared_criteria.py` | 支援 contrastive checker | ⭐⭐⭐（組件 2 的依賴）|
| 7 | Platt Scaling Calibration | `scripts/calibrate_confidence.py` | ECE 大幅改善（論文 claim） | ⭐ |
| 8 | V11-on-V10 Simulation 框架 | `scripts/simulate_v11_on_v10.py` | post-hoc 計算新 calibrator 效果 | ⭐⭐ |

## 分階段 Revive

建議**分成 3 個子實驗**跑，每個子實驗獨立評估、互不干擾：

### T5a：Pairwise Ranker + Shared Criteria（組件 1+6）

這兩個必須一起：Pairwise Ranker 的 feature 依賴 shared_criteria.py。

**流程**：
1. `git show master:src/culturedx/diagnosis/pairwise_ranker.py > src/culturedx/diagnosis/pairwise_ranker.py`
2. `git show master:src/culturedx/ontology/shared_criteria.py > src/culturedx/ontology/shared_criteria.py`
3. Revive `scripts/train_ranker_lightgbm.py` 和 `scripts/extract_ranker_features.py`
4. 用 master 已有的 bootstrap features 或重新 extract（見下方）
5. 訓練 LightGBM ranker（比 master 的 LR 版升級）
6. 在 v2.4 calibrator 後加 pairwise re-rank step
7. Evaluate N=1000 val

**關鍵校驗**：
- Master 分支 `outputs/ranker_features/` 是否還在（14000 train cases extracted features）
- 如果還在，直接訓練 lightgbm → 5 分鐘
- 如果不在，需要重跑 factorial_b on train split 的 feature extraction（8-10h）

### T5b：Contrastive Checker (Stage 2.5)

**流程**：
1. `git show master:src/culturedx/agents/contrastive_checker.py > src/culturedx/agents/contrastive_checker.py`
2. Cherry-pick 對應 prompt template（從 master 的 `prompts/agents/`）
3. 在 v2.4 HiED pipeline 加入 Stage 2.5：
   - 在 criterion_checker 後、logic_engine 前
   - 觸發條件：任兩個 confirmed disorder 之間有 shared criteria
   - 對 F32/F41.1 的 4 個 shared criteria（concentration, sleep, psychomotor, fatigue）做 attribution：每個 symptom 主要歸屬於 F32 還是 F41
4. 把 attribution 結果 feed 給 logic engine 做 adjusted met_count

**預期效益**：解決你 paper narrative C6 的主題（F41→F32 29.7% error）。C6 claim 你已在 v10 驗證過，但 v2.4-refactor 沒把這個 fix 帶過來。

### T5c：Temporal Reasoning + Negation

**流程**：
1. Cherry-pick `temporal.py` 和 `negation.py`
2. 在 criterion_checker 輸入端加入 Temporal preprocessing：抽取「多久了」「半年」「三個月」等時長資訊注入 prompt 的 meta 區塊
3. Negation：掃 transcript 標記「否認」「沒有」scope，criterion checker 遇到負面敘述不判 met

**依賴**：需要安裝 `ChineseTimeNLP` + `stanza` (zh pipeline)。Master 有記錄安裝方式。

**預期效益**：F41.1 Criterion A (sustained worry ≥6mo) recall 從 31% 提升到 45%+。

## 執行優先順序建議

```
T5a (pairwise ranker) → T5b (contrastive) → T5c (temporal+negation)
   ↓                         ↓                         ↓
 Top-1 +1.5pp          F32/F41 F1 +3pp         F41 A recall +14pp
```

三個獨立疊加，都不衝突。

## 成功判準

T5a + T5b + T5c 全做完後：
- 12c_Acc ≥ 0.45（baseline 0.432, +1.8pp）
- 12c_Top1 ≥ 0.56（baseline 0.531, +3pp）
- 12c_Top3 ≥ 0.60（baseline 0.554, +5pp）
- F1_macro ≥ 0.22
- F32/F41 F1 各自 +3pp 以上

## 風險

1. **依賴漂移**：v2.4-refactor 可能改了 `CheckerOutput` 或 `CriterionResult` schema，master 的 component 可能不 compatible。需要 interface 適配層。
2. **Prompt 版本不匹配**：temporal/contrastive 依賴的 prompt template 可能用的是 master 的 v1 prompt，不是 v2_improved。
3. **外部套件**：temporal 需要 `ChineseTimeNLP` 和 `stanza`，這兩個加在環境裡要確認不會和 vLLM 環境衝突。

## 輸出

- `results/validation/t5a_pairwise/`
- `results/validation/t5b_contrastive/`
- `results/validation/t5c_temporal/`
- `results/validation/t5_all_revived/`（三者組合）

## 論文 Narrative 加分

T5 revive 後，你的 paper 可以多一個 claim：
- **C-revive**：「我們在 paper narrative v10 驗證過的所有改進組件，在 v2.4 pipeline 下依然生效且累加」
- 這支持 MAS 的「modular + compositional」narrative
- 反駁 reviewer 可能問「你的 DtV 是 monolithic ensemble，組件獨立貢獻不明」
