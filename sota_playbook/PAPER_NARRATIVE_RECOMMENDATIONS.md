# 論文 Narrative 建議

**執行時機**：靜態實驗跑完、最終架構定案後，開始寫論文前。

## 核心張力

你舊的 paper narrative（`docs/paper_narrative_v2.md`）是圍繞 **"Detection ≠ Ranking: Decomposing the Optimization Paradox"** 展開的，強調：
- MAS 本身不一定比 single LLM 好（Bedi 2025 Optimization Paradox）
- CultureDx 的 hybrid MAS + deterministic logic engine 能打破這個 paradox
- 文化適應（somatization mapping）是 unique contribution
- 核心是「可解釋性 + 文化適應」而非「跑分 SOTA」

但你現在走的是**全面跑分 SOTA** 的路線：
- 在 LingxiDiag-16K 上挑戰所有 12c metric 超越 TF-IDF+LR
- Ensemble 是推分數的主武器
- LoRA fine-tuning 是補 class balance 的武器

**這兩個 narrative 有衝突**：如果 ensemble TF-IDF+LR 是主要貢獻，那「culture-adaptive MAS with interpretability」就會被 reviewer 質疑「那是 TF-IDF 的功勞」。

## 三種 Narrative 方案

### 方案 A：SOTA-focused

**論文題目**（示意）：  
"Beyond Frontier Models: A Hybrid Multi-Agent System for Chinese Psychiatric Differential Diagnosis"

**主要 Claim**：
1. **C1**：在 LingxiDiag-16K 所有 5 個 12c metric 全面 SOTA（第一個做到的 method）
2. **C2**：用 open-source Qwen3-32B + 輕量 ensemble 贏過所有 frontier models（GPT-5-Mini, Claude-Haiku-4.5, Grok-4.1-Fast）
3. **C3**：Ensemble recipe：DtV MAS + TF-IDF + class-aware voting 的 complementary strengths
4. **C4**：可解釋性作為 side benefit（有 criterion-level evidence chain）

**優點**：賣點清楚，數字漂亮
**缺點**：「你靠 TF-IDF 吃飯」的質疑難避

### 方案 B：Culture-adaptive focused

**論文題目**：  
"CultureDx: A Culture-Adaptive Multi-Agent System for Chinese Psychiatric Differential Diagnosis with Criterion-Level Interpretability"

**主要 Claim**：
1. **C1**：Chinese clinical narratives 的 somatization 是 LLM 診斷最大障礙（B1/B2 detection 13-29%）
2. **C2**：Somatization mapper + deterministic logic engine 解決了這個問題（+19.7pp F41 recall）
3. **C3**：CultureDx 在 12c_Acc 和 Top-1 上單系統 SOTA，勝過 frontier models
4. **C4**：其他 metric 要贏需要 TF-IDF stack（as engineering pragmatic choice）

**優點**：narrative 清楚、主張 original、不被 TF-IDF 搶風采  
**缺點**：主結果表格上 F1_macro 在單系統上輸 TF-IDF，可能影響賣點強度

### 方案 C：分層 narrative (推薦)

**論文題目**：  
"Culture-Adaptive Multi-Agent Diagnosis with Criterion-Level Interpretability: Achieving State-of-the-Art on LingxiDiag-16K"

**結構**：
- 主敘事：culture-adaptive MAS + interpretability（方案 B 的核心）
- 次敘事：hybrid ensemble 補強 class balance → SOTA（方案 A 的資源）
- 核心區隔：**CultureDx-Core (MAS only)** vs **CultureDx-Full (MAS + TF-IDF stack)**

**主結果表設計**：

| Method | 12c_Acc | Top-1 | Top-3 | F1_m | F1_w | Overall |
|---|---|---|---|---|---|---|
| TF-IDF+LR | 0.268 | 0.496 | 0.645 | **0.295** | **0.520** | 0.533 |
| GPT-5-Mini | **0.409** | 0.487 | 0.505 | 0.188 | 0.418 | 0.504 |
| Grok-4.1-Fast | 0.351 | 0.465 | 0.495 | 0.195 | 0.409 | 0.521 |
| ... other paper baselines ... |
| **CultureDx-Core (MAS)** | 0.432 | 0.531 | 0.620 | 0.265 | 0.480 | 0.535 |
| **CultureDx-Full (MAS+Stack)** | **0.445** | **0.548** | **0.670** | **0.308** | **0.528** | **0.565** |

主結果可以讓讀者看到：
- CultureDx-Core (只用 DtV MAS) 已經在 12c_Acc / Top-1 / Overall 上贏過所有 baselines
- CultureDx-Full (加 TF-IDF) 讓 F1_macro/F1_w 也贏
- Core 是「我們的貢獻」，Full 是「實務組合」

**Claim 架構**：
- **C1 - Culture-adaptive MAS primary contribution**：CultureDx-Core 在 Acc/Top-1/Overall 超越 paper SOTA 和所有 frontier models (1st principle result)
- **C2 - Interpretability**：criterion-level evidence chain for every prediction
- **C3 - Pragmatic stacking**：TF-IDF 作為 orthogonal supervised signal，stack 後在所有 metric 上 SOTA
- **C4 - Somatization mechanism study**：ablation 顯示 somatization mapping 對 F41 recall 貢獻 +19.7pp
- **C5 - Dynamic benchmark**：Core system 接到 APA-Guided Doctor Agent 後，Dynamic setting 也 SOTA

這樣 TF-IDF 是 "helpful add-on" 不是 "main contribution"。

## 論文結構建議

### Section 1: Introduction
- 全球精神疾病負擔 → AI 輔助診斷需求
- 中文門診的兩大挑戰：somatization 表達 + criterion overlap
- Optimization Paradox (Bedi 2025)：純 LLM-based MAS 可能 < single LLM
- 研究問題：如何設計 culture-adaptive MAS 既避開 paradox 又達 SOTA？

### Section 2: Related Work
- Psychiatric MAS: MAGI, MoodAngels, MedAgent-Pro, MDAgents (全部 LLM-only, 有 paradox)
- Chinese psychiatric NLP: LingxiDiag, MDD-5k, PsyCoTalk (dataset, not MAS)
- Somatization in Chinese psychiatry: Kleinman 1982, Parker 2001, Ryder 2008
- Learning to Rank & ensemble for clinical NLP

### Section 3: Method
- 3.1 Problem formulation (12-class ICD-10 multi-label on Chinese transcripts)
- 3.2 **CultureDx-Core architecture**: Diagnose-then-Verify (DtV) pipeline
  - Diagnostician (LLM) → Criterion Checker (LLM) → Logic Engine (deterministic) → Calibrator → Comorbidity Resolver
  - **Innovation**：deterministic logic engine breaks LLM→LLM error compounding
  - **Innovation**：somatization mapper for Chinese clinical idioms
- 3.3 **CultureDx-Full with ensemble stack**：explain ensemble as engineering pragmatic choice
- 3.4 Implementation details (Qwen3-32B-AWQ, vLLM, prompt templates)

### Section 4: Experiments
- 4.1 Dataset: LingxiDiag-16K
- 4.2 Baselines: paper Table 4 所有 16 個 baseline + our CultureDx-Core + CultureDx-Full
- 4.3 Main Results (Static)
- 4.4 Main Results (Dynamic) — if done
- 4.5 Ablation: somatization mapping / logic engine / ensemble components

### Section 5: Analysis
- 5.1 Error decomposition: Detection vs Ranking
- 5.2 Per-class analysis (focus on F32/F41 confusion & somatization effect)
- 5.3 Cross-dataset validation: MDD-5k / LingxiDiag-Clinical

### Section 6: Discussion
- Implications for clinical decision support
- Why deterministic logic engine works: avoids compound error
- Culture-adaptive as a broader principle (not just Chinese)

### Section 7: Limitations & Future Work
- Temporal reasoning (Criterion A 長期擔憂) remains weak
- Dynamic benchmark 相對靜態仍有 gap
- 需要更多跨文化驗證 (Japanese, Korean etc.)

## Must-cite References (保留原 v2 narrative 的)

1. **Bedi et al. (2025)**. "The Optimization Paradox." — for paradox framing
2. **Xu et al. (2026)**. LingxiDiagBench. — main benchmark
3. **Yin et al. (2025)**. MDD-5k. — cross-dataset validation
4. **Kleinman (1982)**. Neurasthenia and Somatization. — somatization theory
5. **Parker et al. (2001)**. Chinese somatization. — cross-cultural evidence
6. **Ryder et al. (2008)**. Distress somatization in China. — more evidence
7. **Sun et al. (2025)**. MAGI (ACL 2025). — related MAS
8. **Qin et al. (2025)**. MedAgent-Pro (ICLR 2026). — medical MAS baseline
9. **MoodAngels (NeurIPS 2025)**. — RAG-enhanced mood diagnosis
10. **Kim et al. (2024)**. MDAgents (NeurIPS 2024). — general medical MAS

## Target Venue 建議

- **KDD 2027** (LingxiDiag 論文就投 KDD'26，和你 alignment 好)
- **ACL 2027** (NLP + mental health 角度)
- **NAACL 2027 / EMNLP 2027** (NLP + clinical application)
- **AAAI 2027** (AI + medicine)
- **npj Digital Medicine** (journal, cross-disciplinary, but expected lower impact than top-tier conferences)

建議先衝 KDD/ACL，若 rejection 降級到 NAACL/EMNLP。
