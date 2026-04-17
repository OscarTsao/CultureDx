# T5-REVIVE-MASTER：Claude Code 執行 Prompt

```
你在 CultureDx repo，main-v2.4-refactor 分支。目標：把 master 分支已經實作過但 v2.4 refactor 砍掉的 8 個功能性組件 cherry-pick 回來，分三個子實驗評估（T5a Pairwise Ranker, T5b Contrastive Checker, T5c Temporal+Negation）。

完整設計：T5_14_REVIVE_MASTER.md。

這是個複雜、分階段實驗。請嚴格按步驟。

===== 前置：確認 master artifacts =====

STEP 0：掃描 master 分支現存 artifacts
- git log master -- src/culturedx/diagnosis/pairwise_ranker.py
- git log master -- src/culturedx/agents/contrastive_checker.py
- git log master -- src/culturedx/evidence/temporal.py
- git log master -- src/culturedx/evidence/negation.py
- git log master -- src/culturedx/ontology/shared_criteria.py
- git log master -- src/culturedx/ontology/demographic_priors.py
- git log master -- scripts/train_ranker_lightgbm.py
- git log master -- scripts/extract_ranker_features.py
- git log master -- scripts/calibrate_confidence.py
- git log master -- scripts/simulate_v11_on_v10.py
- git log master -- outputs/ranker_features/  # 這個決定 T5a 要不要重跑 feature extraction

印出每個檔案最後 commit hash 和日期。

===== T5a：Pairwise Ranker =====

STEP 1：Cherry-pick 組件
- git show master:src/culturedx/diagnosis/pairwise_ranker.py > src/culturedx/diagnosis/pairwise_ranker.py
- git show master:src/culturedx/ontology/shared_criteria.py > src/culturedx/ontology/shared_criteria.py
- git show master:scripts/train_ranker_lightgbm.py > scripts/train_ranker_lightgbm.py
- git show master:scripts/extract_ranker_features.py > scripts/extract_ranker_features.py

STEP 2：檢查 interface 相容性
- 讀 src/culturedx/diagnosis/pairwise_ranker.py，看它 import 了哪些 v2.4 可能已改的類別
- 特別檢查 CheckerOutput, CriterionResult schema (src/culturedx/core/models.py)
- 如果有不相容欄位，建 compat layer: src/culturedx/compat/pairwise_ranker_adapter.py
- 目標：不改 pairwise_ranker.py，只加 adapter

STEP 3：準備 training features
- 先查 outputs/ranker_features/ 是否存在（master git log 看 commit）
- 如果存在：直接跳到 STEP 4
- 如果不存在：
  (a) 先跑 factorial_b on train split 產生 predictions.jsonl + checker outputs
  (b) 用 scripts/extract_ranker_features.py 抽取 features
  
  指令：
  uv run culturedx run -c configs/base.yaml -c configs/vllm_awq.yaml -c configs/v2.4_final.yaml -c configs/overlays/checker_v2_improved.yaml -d lingxidiag16k --split train -n 14000 -o outputs/factorial_b_train_bootstrap
  
  注意：這一步會跑 8-10h。若時間急，可先用 N=3000 pilot.

STEP 4：訓練 LightGBM pairwise ranker
- uv run python scripts/train_ranker_lightgbm.py --features outputs/ranker_features/lingxidiag_train.csv --output outputs/pairwise_ranker/lgbm_weights.json
- 檢查 5-fold CV 的 NDCG@1 和 NDCG@3
- 存 weights 到 outputs/pairwise_ranker/

STEP 5：整合到 v2.4 pipeline
- 修改 src/culturedx/modes/hied.py
- 在 calibrator 後 comorbidity 前加一個 optional pairwise_rerank step
- config 參數：mode.pairwise_reranker.enabled + model_path

STEP 6：Config + eval
- 新增 configs/overlays/t5a_pairwise.yaml
- uv run culturedx run ... -c configs/overlays/t5a_pairwise.yaml -n 1000 -o results/validation/t5a_pairwise
- 對比 factorial_b metrics

驗收 T5a：
- 12c_Top1 ≥ 0.545 (+1.5pp from 0.531)
- 12c_Top3 ≥ 0.57
- F1_macro 不降

===== T5b：Contrastive Checker (Stage 2.5) =====

STEP 7：Cherry-pick
- git show master:src/culturedx/agents/contrastive_checker.py > src/culturedx/agents/contrastive_checker.py
- 找到對應 prompt template：
  git log master -- prompts/agents/ | grep -i contrastive
  把 prompt template 也 cherry-pick

STEP 8：Schema 相容
- contrastive_checker 產出 "attribution" 結果
- 需要在 CheckerOutput 加入可選的 attribution_adjusted_met_count 欄位
- 或加 compat adapter

STEP 9：整合到 HiED pipeline
- 觸發條件：confirmed 中同時有 F32 和 F41/F41.1
- 調用 ContrastiveChecker 對 shared criteria 做 attribution
- 把 attribution 結果 pipe 給 logic_engine，調整 met_count
- 修改順序：criterion_checker → **contrastive_checker** → logic_engine → calibrator

STEP 10：Config + eval
- configs/overlays/t5b_contrastive.yaml
- mode.contrastive.enabled: true
- mode.contrastive.trigger: ["F32+F41", "F32+F41.1"]
- 跑 N=1000 validation -> results/validation/t5b_contrastive

驗收 T5b：
- F32 precision ≥ 0.55 (baseline 0.523)
- F41 recall ≥ 0.55 (baseline 0.511)
- F32+F41 combined F1 +3pp

===== T5c：Temporal + Negation =====

STEP 11：Cherry-pick
- git show master:src/culturedx/evidence/temporal.py > src/culturedx/evidence/temporal.py
- git show master:src/culturedx/evidence/negation.py > src/culturedx/evidence/negation.py

STEP 12：安裝依賴
- 在 pyproject.toml 加 optional dependency group 'temporal':
  [project.optional-dependencies]
  temporal = ["ChineseTimeNLP", "stanza"]
- uv sync --extra temporal
- 第一次跑 stanza 會下載 zh model (~1GB)，先單獨跑一次 smoke 確認下載完成

STEP 13：整合到 criterion_checker 前處理
- 修改 src/culturedx/agents/criterion_checker.py
- 在生成 prompt 前，對 transcript 跑 temporal.extract_durations() 和 negation.mark_negated_spans()
- 把時長資訊注入 prompt 的 meta block（例如「患者述症狀已持續 8 個月」）
- 把 negated spans 用 <neg></neg> 標記起來，提醒 LLM 不要把被否認的症狀判為 met

STEP 14：Config + eval
- configs/overlays/t5c_temporal.yaml
- mode.preprocessing.temporal_extraction: true
- mode.preprocessing.negation_marking: true
- 跑 N=1000 -> results/validation/t5c_temporal

驗收 T5c：
- F41.1 Criterion A met 比率從 31% 升至 ≥ 42%
- F32 false positives 下降（precision +2pp）
- Top-1 不降

===== T5-all：三者組合 =====

STEP 15：全部啟用
- configs/overlays/t5_all_revived.yaml：同時啟用 pairwise_reranker + contrastive + temporal
- 跑 N=1000 -> results/validation/t5_all_revived

STEP 16：Ablation 報告
- 產出 results/validation/t5_all_revived/ablation.md
- 比較：
  - factorial_b (baseline)
  - +T5a only
  - +T5b only
  - +T5c only
  - +T5a+T5b
  - +T5a+T5b+T5c (full)
- 報告每一步 Δ

驗收 T5 全部：
- 12c_Acc ≥ 0.45
- 12c_Top1 ≥ 0.56
- 12c_Top3 ≥ 0.60
- F1_macro ≥ 0.22
- F32/F41 F1 各 +3pp

如果 T5a 沒改進，跳過 T5b（contrastive 依賴 ranker 可靠的 F32/F41 scoring）。
如果 T5c 的 temporal 依賴安裝有困難，skip negation，只做 temporal。

報告：
1. 三階段各自 metrics + 組合 metrics
2. 遇到的 compat issues 和 workaround
3. 哪個 revived component 最 impactful
```
