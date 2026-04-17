# T6-OFFICIAL-RAG：採用官方 Diagnostic Guidelines PDF + Qwen3-Embedding-8B

## 背景

LingxiDiagBench 官方 repo 提供了一個完整的**知識庫 + FAISS index**：

```
/tmp/LingxiDiagBench/
├── knowledge_base/
│   ├── doc/疾病诊断指南.pdf    # Chinese Psychiatric Diagnostic Guidelines
│   └── indices/
│       ├── faiss_index.index          # FAISS vector index
│       ├── faiss_index.chunks.pkl     # 492 text chunks
│       ├── faiss_index.embeddings.pkl
│       └── faiss_index.config.json    # embedding_model: Qwen/Qwen3-Embedding-8B, dim: 4096
└── src/rag/
    ├── qwen3_embedding.py
    ├── reranker.py
    └── vector_store.py
```

這個 knowledge base 是他們 APA-Guided + MRD-RAG 策略用的診斷指南檢索來源，在 paper Table 6 推升 Dynamic SOTA。

## 你目前的 RAG 層 vs 官方

| 維度 | 你的 CultureDx | 官方 LingxiDiag |
|---|---|---|
| 索引內容 | **歷史病例**（label-only, Level 1）| **診斷指南 PDF 492 chunks** |
| Embedding model | BGE-M3（dim 1024）| Qwen3-Embedding-8B（dim 4096）|
| Retrieval stages | 1 (vector only) | 2 (vector + reranker) |
| Top-k | 5 | 3 |

你用歷史病例 RAG 的問題：**對於 low-frequency class 幾乎沒東西可檢索**（F98 全 train 才 200 cases，Z71 才 100，抽 5-shot 很可能全不相關）。而診斷指南是 class-agnostic 的，對 low-freq class 同樣提供高品質訊息。

## 假設

用官方 Diagnostic Guidelines 取代/補充 historical case retrieval，用 Qwen3-Embedding-8B 取代 BGE-M3。預期：
- **low-freq class F1 全面提升**（因為有診斷指南的標準描述可參考）
- F1_macro +3-5pp
- Top-3 +2-3pp
- Criterion Checker 的 met_rate 提升（有明確 criterion 描述）

## 技術設計

### 三種 RAG 配置對比

**Config R1 — 純官方（替換）**
```
Criterion Checker prompt + Top-3 diagnostic guideline chunks → met/not_met
```

**Config R2 — 疊加（你的 Level 1 cases + 官方 guidelines）**
```
Diagnostician prompt + Top-3 similar cases + Top-3 guideline chunks → ranked
Criterion Checker + Top-3 disorder-specific guidelines → met/not_met
```

**Config R3 — Multi-stage**
```
Stage 1: Triage 用 guidelines retrieve (broad)
Stage 2: Diagnostician 用 historical cases retrieve (label-specific few-shot)
Stage 3: Checker 用 guidelines retrieve (criterion 定義)
```

建議先試 **R1** 和 **R2**，比較後定 R3。

### 改動檔案

**1. 複製官方 knowledge base**
```bash
mkdir -p data/external/lingxidiag_kb
cp -r /tmp/LingxiDiagBench/knowledge_base/doc/ data/external/lingxidiag_kb/
cp -r /tmp/LingxiDiagBench/knowledge_base/indices/ data/external/lingxidiag_kb/
```

**2. 新 Retriever Backend：`src/culturedx/evidence/guideline_retriever.py`**

```python
"""Retriever for LingxiDiag official diagnostic guidelines."""
import pickle
import json
from pathlib import Path
import faiss
import numpy as np
from transformers import AutoModel, AutoTokenizer

class GuidelineRetriever:
    def __init__(
        self,
        index_path: str = "data/external/lingxidiag_kb/indices/faiss_index.index",
        chunks_path: str = "data/external/lingxidiag_kb/indices/faiss_index.chunks.pkl",
        embedding_model: str = "Qwen/Qwen3-Embedding-8B",
        device: str = "cuda",
    ):
        self.index = faiss.read_index(index_path)
        with open(chunks_path, "rb") as f:
            self.chunks = pickle.load(f)
        self.tokenizer = AutoTokenizer.from_pretrained(embedding_model)
        self.model = AutoModel.from_pretrained(embedding_model, torch_dtype="auto", device_map=device)
        self.model.eval()
    
    @torch.no_grad()
    def embed(self, text: str) -> np.ndarray:
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512).to(self.model.device)
        outputs = self.model(**inputs)
        # Mean pooling
        emb = outputs.last_hidden_state.mean(dim=1).cpu().numpy()
        # L2 normalize
        emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)
        return emb
    
    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        q_emb = self.embed(query)
        D, I = self.index.search(q_emb, top_k)
        results = []
        for rank, (dist, idx) in enumerate(zip(D[0], I[0])):
            if idx >= 0 and idx < len(self.chunks):
                results.append({
                    "rank": rank + 1,
                    "score": float(dist),
                    "text": self.chunks[idx],
                })
        return results
    
    def retrieve_per_disorder(self, disorder_code: str, disorder_name: str, top_k: int = 3) -> list[dict]:
        """Retrieve disorder-specific guidelines (e.g., for criterion checker)."""
        query = f"{disorder_code} {disorder_name} 诊断标准"
        return self.retrieve(query, top_k=top_k)
```

**3. 整合到 Criterion Checker**

```python
# In src/culturedx/agents/criterion_checker.py
def _build_prompt(self, disorder, transcript, ...):
    # existing logic
    
    if self.use_guideline_rag:
        guidelines = self.guideline_retriever.retrieve_per_disorder(
            disorder.code, disorder.name, top_k=3
        )
        guideline_text = "\n\n".join(f"[参考段落 {g['rank']}]\n{g['text']}" for g in guidelines)
        # Inject into prompt
        ...
```

**4. 整合到 Diagnostician**

類似，在 `diagnostician_v2_zh.jinja` 加入 `{% if guideline_refs %}...{% endif %}` 區塊。

### Config

```yaml
# configs/overlays/t6_official_rag.yaml
mode:
  retrieval:
    enabled: true
    level: official_guidelines  # R1 or 'hybrid' for R2
    guideline_retriever:
      index_path: "data/external/lingxidiag_kb/indices/faiss_index.index"
      chunks_path: "data/external/lingxidiag_kb/indices/faiss_index.chunks.pkl"
      embedding_model: "Qwen/Qwen3-Embedding-8B"
      top_k: 3
```

## 資源考量

- Qwen3-Embedding-8B 需要 ~16GB VRAM
- 但只用於 inference，不跟你 Qwen3-32B-AWQ 同時 load 會 OOM
- 解法：pre-compute validation cases 的 embeddings，**offline retrieve 然後 cache**
  - 對 1000 val cases × 各需幾次 retrieve，約 3000-4000 retrievals
  - 用 Qwen3-Embedding-8B 一次跑完存快取，後續 pipeline 從快取讀

## 預期 Metric 改善

| Metric | Baseline (factorial_b) | 預期 T6-R1 | 預期 T6-R2 |
|---|---|---|---|
| 12c_Acc | 0.432 | 0.44 | 0.45 |
| Top-1 | 0.531 | 0.54 | 0.55 |
| Top-3 | 0.554 | 0.60 | 0.62 |
| F1_macro | 0.202 | 0.24 | 0.25 |
| F1_weighted | 0.449 | 0.47 | 0.48 |

## 成功判準

- 12c_Acc ≥ 0.44
- F1_macro ≥ 0.22（+2pp）
- Low-freq class（F43/F45/F98/Z71）的 F1 至少有一個 > 0.2

## 風險

1. 官方 index 是 Qwen3-Embedding-8B，重新 embed query 也要用同 model（否則 dim 和空間不匹配）→ 額外 GPU 需求
2. 診斷指南的 chunks 可能跟你的 prompt 結構格格不入 → 需要 prompt engineering
3. 檢索到的 guideline 可能和 LLM parametric knowledge 重複（因為 LLM 預訓練看過類似材料）→ 效益不如預期

## 論文 Contribution

這個 track 讓你可以 claim：
- **C-RAG**：「用官方 diagnostic knowledge 做 retrieval 對 low-freq class 有顯著提升」
- **跨 RAG config 比較**（你的 case-based vs official guidelines）是很好的 ablation

## 輸出

- `results/validation/t6_rag_r1/`
- `results/validation/t6_rag_r2/`
- `outputs/guideline_embedding_cache/`（快取的 embeddings）
