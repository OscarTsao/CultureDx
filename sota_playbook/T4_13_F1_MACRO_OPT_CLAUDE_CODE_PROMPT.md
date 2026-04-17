# T4-F1-OPT：Claude Code 執行 Prompt

```
你在 CultureDx repo。目標：加一層 post-hoc per-class score boost calibration 來直接 optimize F1_macro。用 half of val 做 calibration，另 half 評估，避免 test contamination。

完整設計：T4_13_F1_MACRO_OPT.md。

此實驗全 post-hoc，不重跑 LLM，應該 < 1 小時完成。

STEP 1：切分 val set
- 讀 results/validation/factorial_b_improved_noevidence/predictions.jsonl (N=1000)
- 隨機切 500/500 (seed=42)
- 500 作 calibration set, 500 作 held-out test set
- 儲存 indices 到 data/processed/f1_calib_split.json

STEP 2：Grid search per-class offset
- 新增 scripts/f1_macro_offset_sweep.py
- 對每個 class 的 offset ∈ {-0.2, -0.1, 0, 0.1, 0.2, 0.3, 0.4} sweep
- 總組合太多（7^12），所以用 coordinate descent:
  - 初始 offsets = all 0
  - 每個 epoch，對每個 class 獨立 sweep 找最佳 offset，其他 class 固定
  - 重複直到收斂 (max 5 epochs)
- 在 calibration set 上 compute F1_macro, 選最大

STEP 3：Apply offsets + eval on held-out
- 把 best offsets 存到 outputs/f1_macro_calibration/offsets.json
- 對 held-out 500 cases apply offsets，重新 rank，取得 new predictions
- 用 src/culturedx/eval/lingxidiag_paper.py 評估
- 對比原 factorial_b 在相同 500 cases 上的 metrics
- 印出 per-class F1 改善

STEP 4：Robustness check
- 用 5 個不同 random seed 重做 STEP 1-3
- 看 offsets 是否穩定
- 看 held-out F1_macro gain 是否穩定（std ≤ 2pp 算 robust）

STEP 5：若 robust，apply 到 full N=1000
- 重要：此時完整 val (1000) 已經有部分資訊洩漏（calibration 用了 500 cases）
- 為了正式報告，需要「用 train bootstrap 重新學一次 offsets」：
  - scripts/f1_macro_offset_from_train.py
  - 用 factorial_b on train split（如果有）或 cross-validation 學 offsets
- 然後 apply 到 full val 作為正式結果

STEP 6：Combine with ensemble
- 把 per-class offsets 也 apply 到 T2-RRF 的 fused scores
- 看是否能在 ensemble 上再 +F1_macro

驗收：
- calibration set F1_macro 提升 ≥ +5pp
- held-out F1_macro 提升 ≥ +3pp（train-test transfer）
- F1_weighted 不降
- Top-1 下降 ≤ 3pp
- Offsets 穩健（5-seed std ≤ 2pp）

報告：
- best offsets 表
- per-class F1 before/after
- Top-1, Top-3 變化（可能略降）
```
