# CultureDx 12c SOTA Playbook — 完整實驗路線圖

**目標**：在 LingxiDiag-16K 的全部 5 個 12c 指標上全面超越所有 paper baselines（含 TF-IDF + LR）。

**當前處境**（vs paper Table 4 SOTA）：

| Metric | Paper SOTA | CultureDx 目前最佳 | Gap |
|---|---|---|---|
| 12c_Acc | 0.409 (GPT-5-Mini) | 0.432 (factorial_b) | **+2.3pp** ✅ |
| 12c_Top1 | 0.496 (TF-IDF+LR) | 0.531 (factorial_b) | **+3.5pp** ✅ |
| 12c_Top3 | 0.645 (TF-IDF+LR) | 0.644 (qwen3_8b_dtv) | −0.1pp |
| 12c_m_F1 | 0.295 (TF-IDF+LR) | 0.202 (factorial_b) | **−9.3pp** ❌ |
| 12c_w_F1 | 0.520 (TF-IDF+LR) | 0.453 (05_dtv_v2_rag) | **−6.7pp** ❌ |
| Overall | 0.533 (TF-IDF+LR) | 0.527 (05_dtv_v2_rag) | −0.6pp |

**核心戰略**：必須同時解決「low-frequency class coverage」（影響 F1_macro/F1_weighted）與「Top-3 多樣性」（影響 Top-3），才能全面超越 TF-IDF+LR。

---

## 嘗試方向一覽（共 13 個 experiment tracks）

每個 track 有獨立的 design doc、config、prompt 改動清單，以及給 Claude Code 使用的 execution prompt。

### Tier 1 — Prompt/Config Only（低成本，建議全部跑）

1. **T1-NOS**：NOS routing rule（讓 LLM 在不確定時回 F39/F41.9/F45.9）
2. **T1-OTHERS**：Others fallback in logic engine
3. **T1-F43TRIG**：F43 應激事件觸發器
4. **T1-SUBCODE**：Diagnostician prompt 加入完整 subcode 描述（對齊官方 prompt）
5. **T1-MAXDX**：強制輸出 1-2 個 diagnosis（對齊官方 `mostly one but no more than two` 規則）

### Tier 2 — Ensemble（中成本，需要 fusion code）

6. **T2-RRF**：Triple RRF Ensemble（factorial_b + qwen3_8b_dtv + 05_dtv_v2_rag）
7. **T2-LOWFREQ**：Low-frequency class soft voting（對 F43/F45/F51/F98/Z71/Others 特殊處理）
8. **T2-CONTRAST**：F32↔F41 contrastive re-ranking

### Tier 3 — Training / Fine-tuning（高成本，最高回報）

9. **T3-TFIDF-STACK**：TF-IDF + LR 作為 4th ensemble member（直接吸收 supervised 的優勢）
10. **T3-LORA-CLF**：Qwen3-8B LoRA end-to-end 12c classifier（SFT on train split）
11. **T3-LORA-CHECKER**：Criterion Checker LoRA（SFT criterion_accuracy +20pp）

### Tier 4 — Architecture Change（實驗性）

12. **T4-CALIB-LEARNED**：Learned calibrator（LightGBM LambdaRank on train split features）
13. **T4-F1-OPT**：F1-macro optimization layer（class-weighted re-ranking）

### Tier 5 — Revive Master Branch Components（低成本高回報）

14. **T5-REVIVE-MASTER**：Cherry-pick 8 個 master 分支已實作但 v2.4 丟掉的組件（pairwise ranker, contrastive checker, temporal reasoning, negation detection）

### Tier 6 — Retrieval Upgrade

15. **T6-OFFICIAL-RAG**：採用官方 Diagnostic Guidelines PDF + Qwen3-Embedding-8B FAISS index（從 LingxiDiagBench repo）取代/補充 historical case retrieval

### Tier 7 — Sampling Strategy

16. **T7-SELF-CONSISTENCY**：Diagnostician + Checker 加入 temperature > 0 的 n-sample 投票

### Tier 8 — Paper-ready Holdout Evaluation（必做）

17. **T8-TEST-SPLIT-EVAL**：在 LingxiDiag-16K test split (N=1000) 跑最終 frozen 系統，產生 paper-ready 結果

---

## 建議執行順序

**Week 1**（Prompt-only，預計 +7-10pp F1_macro）：
- 跑完 T1-NOS, T1-OTHERS, T1-F43TRIG, T1-MAXDX 四個實驗
- 每個都在 N=1000 validation 上單獨驗證

**Week 2**（Ensemble，預計 Top-3 +10pp, F1_macro +3pp）：
- T2-RRF 建立 baseline
- T2-LOWFREQ 處理長尾
- T2-CONTRAST 解決 F32/F41

**Week 2.5**（Revive，低成本高回報）：
- T5-REVIVE-MASTER 分三階段（pairwise ranker / contrastive / temporal）

**Week 3**（Training + Retrieval，決定性一擊）：
- 優先 T3-TFIDF-STACK（最快，直接吸收 TF-IDF 優勢）
- T6-OFFICIAL-RAG（官方 guidelines 補 low-freq class）
- 視時間追加 T3-LORA-CLF

**Week 4**（Sampling + Architecture，如果還有時間）：
- T7-SELF-CONSISTENCY
- T4-CALIB-LEARNED
- T4-F1-OPT

**Week 5**：**T8-TEST-SPLIT-EVAL（必做，paper-ready holdout）**

**Week 6**：動態 benchmark 評估（DYNAMIC_BENCHMARK_PLAN.md）

**Week 7+**：論文撰寫（依 PAPER_NARRATIVE_RECOMMENDATIONS.md）

---

## 實驗產出格式

每個 track 會產出：
- `<N>_<name>.md`：完整實驗設計文件（給你讀）
- `<N>_<name>_CLAUDE_CODE_PROMPT.md`：可直接貼給 Claude Code 的執行 prompt

所有實驗都在同一個 baseline (factorial_b) 上做比較，跑在同一 N=1000 validation split 上，確保 apples-to-apples。

## Baseline 固定事項（所有實驗共通）

- Dataset: lingxidiag16k validation split
- N: 1000
- Model: Qwen/Qwen3-32B-AWQ via vLLM
- Seed: 42
- Metric tool: `src/culturedx/eval/lingxidiag_paper.py`
- 輸出路徑: `results/validation/<experiment_id>/`

每次新實驗都需要包含 t-test / bootstrap CI vs factorial_b，看是否 significant。

---

## 補充文件（非實驗 track）

- `DYNAMIC_BENCHMARK_PLAN.md`：靜態實驗跑完後的 Dynamic benchmark 評估方案（含完整 Claude Code prompt）
- `PAPER_NARRATIVE_RECOMMENDATIONS.md`：論文敘事三方案（SOTA-focused / Culture-adaptive / Hybrid）+ reference 列表 + target venue
- `MASTER_ABLATION_COMPILE.md`：所有實驗跑完後自動 compile 成 paper-ready Table 1/2/3 的 script

## 完整 Track 清單與預期效益

| Track | 設計 | Prompt | 預期效益 |
|---|---|---|---|
| T1-NOS | ✅ | ✅ | F1_macro +5pp |
| T1-OTHERS | ✅ | ✅ | F1_macro +2pp (Others class 0→0.25) |
| T1-F43TRIG | ✅ | ✅ | F1_macro +3pp (F43 class 0→0.4) |
| T1-SUBCODE | ✅ | ✅ | Top-3 +3pp |
| T1-MAXDX | ✅ | ✅ | 12c_Acc +2pp |
| T2-RRF | ✅ | ✅ | Top-3 到 0.63+, 所有 metric 溫和升級 |
| T2-LOWFREQ | ✅ | ✅ | F1_macro +5pp, 低頻 class 大升 |
| T2-CONTRAST | ✅ | ✅ | F32/F41 F1 +5pp |
| T3-TFIDF-STACK | ✅ | ✅ | 全 5 metric 全面超越 paper SOTA ⭐ |
| T3-LORA-CLF | ✅ | ✅ | 再 +1-2pp（可選） |
| T3-LORA-CHECKER | ✅ | ✅ | 12c_Acc +2pp（接 master LoRA） |
| T4-LEARNED-CALIB | ✅ | ✅ | Top-1 +2pp, Top-3 +3pp |
| T4-F1-OPT | ✅ | ✅ | F1_macro +3pp（最後微調） |
| **T5-REVIVE-MASTER** | ✅ | ✅ | Top-1 +3pp, F32/F41 F1 +3pp (cherry-pick 8 個 master 組件) |
| **T6-OFFICIAL-RAG** | ✅ | ✅ | F1_macro +3-5pp（low-freq class 強化，需 Qwen3-Embedding-8B） |
| **T7-SELF-CONSISTENCY** | ✅ | ✅ | Top-1 +2pp（時間成本 4×） |
| **T8-TEST-SPLIT-EVAL** | ✅ | ✅ | ⚠ 必做 — paper-ready holdout evaluation |

| **T9-CROSS-DATASET** | ✅ | ✅ | 跨資料集 validity — 論文第二個 dataset 必做 |
| **T10-SELF-DISTILLATION** | ✅ | ✅ | 比 T3-LORA-CLF 再 +1-2pp，可解釋性強化 |
| **T11-MULTI-BACKBONE** | ✅ | ✅ | +1pp Top-1（加 Baichuan-M3 medical model） |
| **T12-TOT-HARD-CASES** | ✅ | ✅ | Top-1 +1.5pp via Tree-of-Thoughts on ~25% 困難 cases |

**最小可行 SOTA 路徑（推薦）**：T1-NOS + T1-OTHERS + T2-RRF + T3-TFIDF-STACK。預期這 4 個就能讓所有 12c metric 全面 SOTA。

**Paper-ready 完整路徑**：上述 4 個 + T5-REVIVE-MASTER + T6-OFFICIAL-RAG + T7-SELF-CONSISTENCY + **T8-TEST-SPLIT-EVAL（必做）** + **T9-CROSS-DATASET（必做）**。滿足 SOTA + 論文可信度（test split + cross-dataset 雙重驗證）。

**Exhaustive 路徑（全部 21 tracks）**：上述 + T1-F43/SUBCODE/MAXDX + T2-LOWFREQ/CONTRAST + T3-LORA-* + T4-* + T10/T11/T12。預期 best ensemble 能在 5 個 12c metric 全面超越所有 paper baselines 至少 +1pp margin，但需 6-8 週密集實驗。

---

## 建議執行優先級矩陣

| 週次 | Tracks | 耗時 | 累積預期效益 |
|---|---|---|---|
| W1（**必做**） | T1-NOS, T1-OTHERS, T2-RRF, T3-TFIDF-STACK | 4-5 天 | 全 5 個 12c metric 全面 SOTA |
| W2（**必做**） | T8-TEST-SPLIT-EVAL, T9-CROSS-DATASET | 3-4 天 | Paper-ready validity |
| W3（高回報） | T5-REVIVE-MASTER, T7-SELF-CONSISTENCY | 5-7 天 | +2-3pp 鞏固 margin |
| W4（論文需要） | T6-OFFICIAL-RAG, T2-CONTRAST, T12-TOT | 5-7 天 | Ablation 支撐 + qualitative cases |
| W5（加分項） | T10-DISTILL, T11-MULTI-BACKBONE, T3-LORA-* | 7-10 天 | 最終推分 + bonus claims |
| W6（可選） | T4-LEARNED-CALIB, T4-F1-OPT, T1-F43/SUBCODE/MAXDX | 5-7 天 | 精細 calibration + prompt 補強 |
| W7 | Dynamic Benchmark | 1 週 | End-to-end consultation claim |
| W8+ | 論文撰寫 | 全週 | 依 PAPER_NARRATIVE_RECOMMENDATIONS.md |
