# Dynamic Benchmark Evaluation Plan

**執行時機**：在所有 static 實驗（T1-T4）跑完、最終 CultureDx 架構確定後再做。

## 為什麼要做 Dynamic

從 LingxiDiag 論文 Table 6（paper p.8）可見：
- 所有 model 的 dynamic 12c_Acc **都顯著低於 static**
- Dynamic SOTA: Grok-4.1-Fast + APA-Guided+MRD-RAG = **28.5%**（vs static SOTA 40.9%）
- Top-1 dynamic SOTA: Grok-4.1-Fast = 37.5%
- m_F1 dynamic SOTA: DeepSeek-V3.2 = 24.7%
- w_F1 dynamic SOTA: Grok-4.1-Fast = 25.5%

這個 dynamic setting 是「Doctor Agent 問問題 → Patient Agent 回答」的互動模式，模擬真實門診。

**你的 static 系統已經在所有 12c metric 超越了 dynamic SOTA**（甚至 factorial_b 的 0.432 比 dynamic SOTA 的 0.285 高 15pp）。把你的系統接到 Dynamic setting，順便在 Dynamic 上也刷 SOTA，是**額外 1-2 個 claim 的免費 contribution**。

## Dynamic Evaluation Protocol

按 paper § 4.2 規格：

### Setup

1. **Patient Agent**：用論文 release 的 LingxiDiag-Patient (Qwen3-32B backbone) 模擬病人
2. **Doctor Agent Strategy**：採用最強策略 APA-Guided + MRD-RAG
   - 五階段問診：Screening → Assessment → Deep-dive → Risk → Closure
   - 每階段有 mandatory/optional topics
3. **Diagnosis Agent**：這裡就是**你的 CultureDx final system**（最強的那個 static ensemble）
4. **Evaluation**：用 LLM-as-a-Judge 評估對話品質 + 用官方 12c metrics 評估診斷

### Integration Plan

```python
# scripts/run_dynamic_benchmark.py
from culturedx.dynamic import DynamicBenchmark
from culturedx.agents.doctor_apa_rag import APADoctorAgentWithRAG
from culturedx.agents.patient_lingxi import LingxiPatientAgent

# Patient: use official Patient Agent
patient = LingxiPatientAgent(model="Qwen/Qwen3-32B-AWQ")

# Doctor: use APA-Guided + MRD-RAG strategy
doctor = APADoctorAgentWithRAG(
    model="Qwen/Qwen3-32B-AWQ",
    rag_retriever=MRDRetriever(top_k=3),
    phase_config=paper_apa_phases,
)

# Diagnostician: YOUR BEST CULTUREDX SYSTEM
diagnostician = CultureDxFinal(
    config="configs/final/v3.0.yaml",  # whatever you finalize
)

benchmark = DynamicBenchmark(
    patient_agent=patient,
    doctor_agent=doctor,
    diagnostician_agent=diagnostician,
    max_turns=15,
)

results = benchmark.run(val_cases, n=200)  # paper uses smaller n for dynamic
```

### Code Sources

Doctor Agent + Patient Agent 可以從 LingxiDiagBench 官方 repo 直接 clone 使用：
- `/tmp/LingxiDiagBench/evaluation/dynamic/` 應該有這些 Agent
- 或 paper Appendix C.4, C.5 有完整 prompts 可以手動實作

## 成功判準

在 Dynamic benchmark 下：
- 12c_Acc ≥ 0.30（超越 paper Dynamic SOTA 0.285）
- 12c_Top1 ≥ 0.40（超越 paper 0.375）
- 12c_Top3 ≥ 0.45（超越 paper 0.410）
- 12c_F1_macro ≥ 0.27（超越 paper 0.256 from DeepSeek）

如果只能超越 4 個 Dynamic metric 中的 3 個，也算強 result。

## 論文加分

Dynamic result 可以支持以下 claim:
1. **端到端 real-world readiness**：你的 system 不只靜態分類強，互動式診斷也強
2. **Doctor Agent 無關性**：你的 diagnostician 接上論文的 APA-Guided Doctor Agent 後依然表現 SOTA，表示你的成功不是靠特殊問診策略
3. **跨 setting 穩定性**：Dynamic vs Static 的 gap 你比 paper baseline 小（paper 平均有 12pp gap）

## 時程

- 預計 1-2 週（含 Doctor Agent 整合 + 200 cases 跑完）
- 200 cases dynamic run，每 case 平均 10-15 turns，每 turn LLM call，預計 6-8 小時 GPU
- LLM-as-a-Judge evaluation 再加 2 小時

## Claude Code Prompt

```
你在 CultureDx repo。目標：把最終 CultureDx static system 接到 LingxiDiag Dynamic benchmark，用 APA-Guided + MRD-RAG 作為 Doctor Agent strategy，在 200 validation cases 上跑 end-to-end consultation，對比 paper Table 6 的 Dynamic SOTA。

STEP 1：Clone LingxiDiagBench repo
- git clone https://github.com/Lingxi-mental-health/LingxiDiagBench /tmp/LingxiDiagBench
- 讀 /tmp/LingxiDiagBench/evaluation/dynamic/ 下的 Patient/Doctor Agent 實作
- 如果沒有 dynamic code，從 paper Appendix C.4/C.5 手動實作 prompts

STEP 2：建立 Patient Agent
- src/culturedx/dynamic/patient.py
- 使用 LingxiDiag-Patient prompts (paper p.18)
- Backbone: Qwen3-32B-AWQ via vLLM
- Input: 患者 case profile (demographics, chief complaint, diagnosis)
- Output: 模擬病人的自然回應（短、口語化、偶爾不確定）

STEP 3：建立 Doctor Agent (APA-Guided + MRD-RAG)
- src/culturedx/dynamic/doctor_apa_rag.py
- 實作 5-phase APA strategy
- MRD-RAG: retrieve top-3 related diagnostic guidelines at each turn
- Doctor 每 turn:
  (a) decide next phase based on info collected
  (b) retrieve relevant disorder guidelines
  (c) generate next question

STEP 4：接入你的 final Diagnostician
- 當 Doctor Agent 決定 closure 或達 max_turns，把完整 dialogue history 丟給 CultureDxFinal.diagnose()
- 產生 ICD code

STEP 5：Orchestrator
- scripts/run_dynamic_benchmark.py
- 對每個 val case:
  - Initialize Patient with case profile
  - Loop: Doctor asks → Patient answers → repeat
  - After N turns or Doctor closes → CultureDx diagnose
- 存所有對話到 results/dynamic/t5_dynamic/dialogs/case_XXX.json
- 存 predictions 到 predictions.jsonl

STEP 6：LLM-as-a-Judge evaluation (paper § 4.2)
- 5 dimensions: Clinical Accuracy, Ethical Conduct, Assessment Response, Therapeutic Relationship, Communication Quality
- 用 GPT-4o 或 Qwen3-32B 作 judge（paper 用 GPT-4o）

STEP 7：Report
- 12c metrics vs paper Dynamic SOTA (Table 6 APA-Guided+MRD-RAG 那幾行)
- 並和 static 結果對比（看跨 setting gap）

驗收：
- 12c_Acc ≥ 0.30 (Dynamic)
- 12c_Top1 ≥ 0.40
- 12c_F1_macro ≥ 0.26

注意：Dynamic 跑一次 200 cases 估 6-8 小時，建議在非高峰時段跑。
```

## 備註

此 Dynamic evaluation 不是論文必需，但有做能讓你的 paper 從「single-axis benchmark improvement」升級成「comprehensive MAS evaluation」。
