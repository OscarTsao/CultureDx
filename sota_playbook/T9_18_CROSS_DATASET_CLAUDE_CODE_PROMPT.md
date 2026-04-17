# T9-CROSS-DATASET：Claude Code 執行 Prompt

```
你在 CultureDx repo，main-v2.4-refactor 分支。目標：在 MDD-5k、LingxiDiag-16K test split、(optional) LingxiDiag-Clinical、(optional) E-DAIC 四個資料集上跑最終 CultureDx system，產出跨資料集驗證結果。這是論文主結果以外的必要實驗，證明 system 不 overfit 到 LingxiDiag validation split。

完整設計：T9_18_CROSS_DATASET.md。

STEP 1：LingxiDiag-16K test split 評估（優先級最高）
- 這是你**論文主結果必須在 test 上跑的**，val 只是 dev set
- 指令：uv run culturedx run -c configs/base.yaml -c configs/vllm_awq.yaml -c configs/v2.4_final.yaml -c configs/overlays/checker_v2_improved.yaml -d lingxidiag16k --data-path data/raw/lingxidiag16k --split test -n 1000 -o results/test/lingxidiag_test_factorial_b
- 然後跑最終 ensemble 系統（例如 t3_tfidf_stack）在 test split
- 輸出 12c metrics + per-class F1
- 對比 validation 的結果（overfit check：val vs test 差距 ≤ 2pp）

STEP 2：MDD-5k 跨資料集驗證
- 先檢查：uv run culturedx run ... -d mdd5k -n 50 -o outputs/smoke_mdd5k 能跑起來
- 如果 adapter 有問題，從 master cherry-pick src/culturedx/data/adapters/mdd5k.py
- Full N=500 跑兩個系統：
  - factorial_b
  - 最終 ensemble
- 輸出 results/cross/mdd5k_factorial_b, results/cross/mdd5k_final_ensemble

STEP 3：MDD-5k 12c label mapping 確認
- MDD-5k 的 label schema 不是 12c ICD，檢查 adapter 怎麼 mapping
- 如果只有 4-class label，需要把 12c evaluation 改成 4-class eval（抑鬱/焦慮/混合/其他）
- 或看 paper_narrative_v2.md 以前怎麼做的

STEP 4：評估 somatization mapping 在 MDD-5k 的效果
- Ablation：MDD-5k 上 with/without somatization
- 預期：MDD-5k 上 somatization 中性或略負（因為已經 explicit）
- 這是 culture-adaptive claim 的 key evidence

STEP 5：(Optional) LingxiDiag-Clinical
- 如果能拿到資料，跑一次 factorial_b
- Paper Table 7 有 baseline 數字，直接對比

STEP 6：(Optional) E-DAIC 英文資料集
- 你 master 有 scripts/preprocess_edaic.py
- 目標：證明 CultureDx 在英文 dataset 也 competitive（至少和 single LLM baseline 差不多）
- 這是論文 cross-lingual generalization claim

STEP 7：Compile table
- scripts/compile_cross_dataset_table.py
- 輸出 paper/tables/cross_dataset_results.md
- 格式：
  | Dataset | Method | 12c_Acc | Top1 | Top3 | F1_m | F1_w |
  | LingxiDiag val | factorial_b | 0.432 | 0.531 | 0.554 | 0.202 | 0.449 |
  | LingxiDiag val | final | ... | ... | ... | ... | ... |
  | LingxiDiag test | factorial_b | ... | ... |
  | LingxiDiag test | final | ... | ... |
  | MDD-5k | factorial_b | ... | ... |
  | MDD-5k | final | ... | ... |

驗收：
- LingxiDiag test F1_macro 和 val 差距 ≤ 2pp
- MDD-5k 上 factorial_b 的 Top-1 vs single LLM baseline（如果有 paper 數字）至少持平
- 跨 dataset metric std ≤ 5pp

注意：LingxiDiag-16K 通常 train/val/test 都 release 了，test split 分數才是論文正式成績。必須跑！
```
