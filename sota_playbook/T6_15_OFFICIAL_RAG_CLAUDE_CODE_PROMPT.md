# T6-OFFICIAL-RAG：Claude Code 執行 Prompt

```
你在 CultureDx repo，main-v2.4-refactor 分支。目標：採用 LingxiDiagBench 官方的 Diagnostic Guidelines PDF knowledge base (492 chunks, FAISS index, Qwen3-Embedding-8B embeddings)，取代或疊加目前的 historical case retrieval。預期大幅提升 low-freq class 表現（因為診斷指南提供 class-agnostic 的標準描述，不像 case retrieval 對稀有類別無資料可用）。

完整設計：T6_15_OFFICIAL_RAG.md。

先決條件檢查：
- 需要 1 顆額外 GPU（~16GB）用於 Qwen3-Embedding-8B
- 或者用 CPU embedding（較慢但可行）
- 確認 /tmp/LingxiDiagBench/knowledge_base/ 存在（或從 git clone https://github.com/Lingxi-mental-health/LingxiDiagBench 重新下載）

STEP 1：複製官方 knowledge base
- mkdir -p data/external/lingxidiag_kb
- cp -r /tmp/LingxiDiagBench/knowledge_base/doc data/external/lingxidiag_kb/
- cp -r /tmp/LingxiDiagBench/knowledge_base/indices data/external/lingxidiag_kb/
- 確認 data/external/lingxidiag_kb/indices/faiss_index.index 大小合理

STEP 2：新 Retriever class
- 新增 src/culturedx/evidence/guideline_retriever.py
- 實作設計文件中的 GuidelineRetriever class
- 支援 retrieve(query, top_k) 和 retrieve_per_disorder(disorder_code, top_k)
- 用 faiss + transformers 載入 Qwen3-Embedding-8B
- 注意：Qwen3-Embedding-8B 需要指定 trust_remote_code=True

STEP 3：Pre-compute embeddings for validation set
- 寫 scripts/precompute_guideline_retrieval.py
- 對 validation 1000 cases × 需要的所有 queries（每 case 最多 12 次 retrieve = 每 disorder 一次 + overall 一次）做 batch retrieval
- 把結果快取到 outputs/guideline_retrieval_cache/val.jsonl
- Format: {"case_id": "...", "query_type": "disorder_F32", "top3": [{"text": "...", "score": ...}, ...]}

STEP 4：整合 guideline retrieval 到 Criterion Checker
- 修改 src/culturedx/agents/criterion_checker.py
- 新增 use_guideline_rag 參數
- 若啟用，在 prompt 生成時注入 top-3 disorder-specific guideline chunks
- 從快取讀（不在推理時重新 embed）

STEP 5：整合到 Diagnostician
- 修改 prompts/agents/diagnostician_v2_zh.jinja
- 加 {% if guideline_chunks %}{% for c in guideline_chunks %}... 區塊
- 修改 diagnostician.py 把 guideline_chunks 塞進 context

STEP 6：Config R1 (純 guideline, 取代 case retrieval)
- 新增 configs/overlays/t6_rag_r1_guidelines_only.yaml
- mode.retrieval.level: official_guidelines
- mode.retrieval.enabled: true
- mode.retrieval.guideline_retriever.index_path: data/external/lingxidiag_kb/indices/faiss_index.index
- mode.retrieval.use_case_rag: false

STEP 7：Config R2 (hybrid: cases + guidelines)
- configs/overlays/t6_rag_r2_hybrid.yaml
- mode.retrieval.level: hybrid
- mode.retrieval.use_case_rag: true (top 3 cases)
- mode.retrieval.use_guideline_rag: true (top 3 guidelines)

STEP 8：跑 Smoke N=100 兩個 config
- 確認兩個 config 都能跑完無 crash
- 印出第一個 case 的完整 prompt，看 guideline chunks 是否正確注入
- 如果 chunks 看起來跟診斷無關或品質差，回去看 STEP 3 是否 query 設計有問題

STEP 9：Full N=1000
- T6-R1: results/validation/t6_rag_r1
- T6-R2: results/validation/t6_rag_r2
- 對比 factorial_b (case-based RAG Level 1)

STEP 10：Per-class analysis
- 重點看 low-freq class (F43, F45, F51, F98, Z71, Others) 的 F1 是否顯著提升
- 如果 low-freq 沒升，表示 guideline chunks 對這些 class 沒幫助，debug retrieval queries

STEP 11：Ensemble with existing systems
- T6-R2 predictions 作為新 ensemble member 加入
- 跑 4-way: factorial_b + qwen3_8b_dtv + 05_dtv_v2_rag + t6_rag_r2
- 或 5-way: 加上 TF-IDF
- 跑 weights sweep

驗收：
- T6-R1: F1_macro ≥ 0.22, 至少 1 個 low-freq class F1 > 0.2
- T6-R2: F1_macro ≥ 0.24, Top-3 ≥ 0.60
- Ensemble with T6-R2 在所有 12c metric 都超越 paper SOTA

資源 notes：
- Qwen3-Embedding-8B 第一次下載約 16GB，需要 HF cache
- 若 GPU 不夠，改用 device="cpu"，retrieval 一次 1-2 秒可接受
- STEP 3 的 precompute 對 1000 cases × 12 queries = 12000 retrievals，在 GPU 上約 20 分鐘，CPU 約 2 小時

報告：
1. 官方 KB 複製成功驗證 (492 chunks, 4096 dim)
2. R1 vs R2 vs factorial_b 的 metric 對比
3. Per-class F1 breakdown，特別是 low-freq
4. 檢索品質抽樣：印 3 個 case 的 top-3 guideline chunks，看是否 relevant
```
