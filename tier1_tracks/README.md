# CultureDx Tier 1 Playbook — 最終版

## Error Taxonomy 結果（factorial_b, N=1000）

| 錯誤類型 | 次數 | 佔比 | 攻擊手段 |
|---|---|---|---|
| TOP1_CORRECT | 531 | 48.7% | — |
| IN_TOP3_NOT_TOP1 | 151 | 13.8% | **T3** F32↔F41 Contrastive |
| DIAGNOSTICIAN_MISS | 324 | 29.7% | **T1** Top-K + Logic-all |
| CANDIDATE_MISS (Others) | 85 | 7.8% | ❌ 放棄（見 T2） |
| VETOED / CONFIRMED_NOT_RANKED / LOGIC_NOT_CONFIRMED / CHECKER_LOW_MET / VERIFY_NOT_SELECTED | 0 | 0% | 不用修 |

**三大結論**：
1. Checker / Logic / Calibrator / Comorbidity gate **四個 stage 全部 0 錯誤**
2. Diagnostician 99.8% case 只輸出 top-2（prompt schema bug）
3. Logic engine 只看 `checker_outputs`（top-3），不看 `all_checker_outputs`

## 三個 Track 的狀態

| Track | 狀態 | Deliverable | 預期 gain |
|---|---|---|---|
| T1-DIAG-TOPK | ✅ Ready | DESIGN.md + CLAUDE_CODE_PROMPT.md + validate.sh | F1_m +5pp, Top-1 +3pp, Top-3 +10pp |
| T2-OTHERS-FALLBACK | ❌ 放棄 | DESIGN.md 記錄放棄理由 | 0 (無可行 post-hoc 規則) |
| T3-F32F41-CONTRASTIVE | ✅ Ready | DESIGN.md + CLAUDE_CODE_PROMPT.md | Top-1 +4pp, F41 recall +10pp |

## 預期最終效益 (T1 + T3)

| Metric | Current | T1 only | T1+T3 | Paper SOTA | Status |
|---|---|---|---|---|---|
| 12c_Acc | 0.432 | 0.46 | 0.48 | 0.409 | ✅ SOTA |
| 12c_Top1 | 0.531 | 0.56 | 0.59 | 0.496 | ✅ SOTA |
| 12c_Top3 | 0.554 | 0.65 | 0.67 | 0.645 | ✅ SOTA |
| 12c_F1_macro | 0.202 | 0.25 | 0.27 | 0.295 | ⚠️ ~80% of gap closed |
| 12c_F1_weighted | 0.449 | 0.48 | 0.50 | 0.520 | ⚠️ ~80% of gap closed |
| Overall | 0.523 | 0.54 | 0.56 | 0.533 | ✅ SOTA |

**四個 metric SOTA, F1 macro/weighted 仍有 ~2pp gap**。
若 paper 要求全 5 metric SOTA，加 TF-IDF stacking 作為 safety net（另外一個 track，不在 Tier 1）。

## 執行順序

```
Day 1: 執行 T1 (~4 hr compute) + 檢查 error taxonomy
Day 2: 分析 T1 結果
       → 若 F1_m >= 0.28 跳到 paper writing
       → 否則執行 T3 (~4 hr compute)
Day 3: 分析 T3 結果 + 決定要不要加 TF-IDF
Day 4-7: Paper writing
```

## 關鍵決策 Gate

**Gate 1 (T1 跑完後)**: 看 F1_macro
- F1_m ≥ 0.28: 跳過 T3，直接寫 paper，T3 變 future work
- F1_m 0.24-0.27: 執行 T3
- F1_m < 0.24: T1 可能沒修對，debug

**Gate 2 (T3 跑完後)**: 看 5 metric 是否 SOTA
- 全 5 metric SOTA: 寫 paper，claim all-metric SOTA
- 4 metric SOTA, F1 相關差 <3pp: 寫 paper, honest framing
- 4 metric SOTA, F1 差 >3pp: 考慮加 TF-IDF stack 作為 hybrid extension

## 檔案結構

```
tier1_tracks/
├── README.md                                ← 本檔
├── T1_DIAG_TOPK/
│   ├── DESIGN.md                            完整原理 + diff 清單
│   ├── CLAUDE_CODE_PROMPT.md                貼給本機 Claude Code
│   └── validate.sh                          Smoke + full + metrics diff
├── T2_OTHERS_FALLBACK/
│   └── DESIGN.md                            放棄理由（資料分析記錄）
└── T3_F32F41_CONTRASTIVE/
    ├── DESIGN.md                            完整原理
    └── CLAUDE_CODE_PROMPT.md                貼給本機 Claude Code
```

## 接下來要做的事

1. **你**: 把 `T1_DIAG_TOPK/CLAUDE_CODE_PROMPT.md` 貼給本機 Claude Code，跑完 ~4 小時
2. **你**: 把 metrics 和 error taxonomy 結果傳回給我
3. **我**: 根據 T1 結果決定是否執行 T3，若是則幫你檢查 T3 prompt 是否需要調整
4. **你**: 跑 T3，得到最終 metrics
5. **我 + 你**: 開始寫 paper，確定 narrative

## 如果 T1 跑出來 F1_macro 已經 > 0.28

這表示 T1 的效果比預期好，可能直接 SOTA 全 5 metric。
此時：
- 不做 T3，直接進入 paper writing
- T3 作為 Discussion 或 Future Work 提出
- 論文 narrative 更強：「single minimal fix (diagnostician top-K expansion) 達到全 5 metric SOTA」

## 如果 T1 跑不動或 early fail

常見問題 + 解法都在 `T1_DIAG_TOPK/CLAUDE_CODE_PROMPT.md` 最後一段：
- Diagnostician 拒絕輸出 5 個 → 把 prompt 加強語氣
- Token 超限 → max_tokens 提到 2048
- Primary 亂跳（某些 case 明顯錯）→ 看 `primary_source` log 找問題
