# T11-MULTI-BACKBONE：Claude Code 執行 Prompt

```
你在 CultureDx repo。目標：把 CultureDx factorial_b pipeline 跑在至少 2 個不同 model family 的 backbone 上，做 multi-backbone ensemble。

完整設計：T11_20_MULTI_BACKBONE.md。

優先跑：Qwen3-32B-AWQ + Baichuan-M3（都 open-source, AWQ 量化）。
Optional：DeepSeek-V3.2（需要 API）、Claude-Haiku-4.5（需 API 配額）。

STEP 1：準備 backbone configs
- configs/model_pools/qwen3_32b.yaml (已有)
- 新增 configs/model_pools/baichuan_m3.yaml:
  llm:
    provider: vllm
    model: baichuan-inc/Baichuan-M3-235B-Instruct-AWQ
    base_url: http://localhost:8002/v1
    max_tokens: 2048
- 可選 configs/model_pools/deepseek_v3.yaml for DeepSeek API

STEP 2：部署 second vLLM server
- Baichuan-M3 需要另一個 vLLM instance on port 8002
- 或者 sequential 跑（先 Qwen3，再切換 model）

STEP 3：跑每個 backbone N=1000
- for backbone in qwen3_32b baichuan_m3; do
    uv run culturedx run -c configs/base.yaml \
      -c configs/model_pools/$backbone.yaml \
      -c configs/v2.4_final.yaml \
      -c configs/overlays/checker_v2_improved.yaml \
      -d lingxidiag16k -n 1000 \
      -o results/validation/multi_backbone/$backbone
  done
- 確保 predictions.jsonl 的 case_id 一致（for ensemble）

STEP 4：Per-backbone Profile
- 新增 scripts/analyze_backbone_profile.py
- 對每個 backbone 計算 per-class F1
- 找出各 backbone 的 strength class
- 輸出 paper/tables/backbone_profile.md

STEP 5：Uniform RRF Ensemble
- 擴充 scripts/run_ensemble.py 支援 multi-backbone 輸入
- 對 2-3 個 backbone 的 ranked lists 做 RRF (k=60, uniform weights)
- 評估 12c metrics

STEP 6：Class-Aware RRF
- 用 validation set 的 50% 當 calibration set，算出 per-backbone per-class F1
- 另 50% 當 test set
- 對 test set 做 class-aware weighted RRF
- 比較 uniform vs class-aware

STEP 7：Combine with existing ensemble
- 把 multi-backbone ensemble 的 output 加入 T3-TFIDF-STACK 的 4-way ensemble，變 5-way: qwen3_32b + baichuan_m3 + qwen3_8b_dtv + tfidf + factorial_b
- Weights sweep, 找最佳

驗收：
- 2-backbone 的 uniform RRF 在 F1_macro 提升 ≥ +1pp vs Qwen3 single
- Per-backbone profile 顯示 Baichuan-M3 在 F20/F31 至少 F1 +0.1（預期 medical-tuned 能抓這些少見但重要的 class）
- Class-aware RRF 比 uniform 再 +0.5-1pp F1_macro

如果你沒有第二個 GPU 跑兩個 vLLM，可以 sequential 跑：
- 先跑 Qwen3-32B 1000 cases
- 關掉 vLLM，切到 Baichuan-M3 再跑 1000 cases
- 兩天時間，然後 ensemble

Baichuan-M3-235B 很大，可能 OOM。fallback 到 Baichuan-M3-32B 或 Baichuan-M2-32B（paper 有 baseline）。

報告：每 backbone metric、2-way ensemble、class-aware 改善。
```
