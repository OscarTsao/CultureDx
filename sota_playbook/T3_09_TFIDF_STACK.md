# T3-TFIDF-STACK：TF-IDF + LR 作為 Ensemble 第 4 Member

## 核心洞察

**TF-IDF + LR 是論文 Table 4 中在 12c_Top1/Top-3/F1_macro/F1_weighted/Overall 五個指標中拿下四個 SOTA 的方法**（唯一 12c_Acc 輸給 GPT-5-Mini）。它贏的關鍵只有一個：**它在 train split (14000 cases) 上監督訓練過**，LLM baselines 都是 zero-shot。

與其花大錢做 LoRA fine-tune Qwen3 去吸收這個優勢，**最經濟的做法是直接把 TF-IDF + LR 當 ensemble 的第 4 個 member**。你的 DtV pipeline 提供 criterion-level 的可解釋性 + low-freq class coverage，TF-IDF 提供 class frequency 校準 + Top-3 多樣性。

## 假設

Ensemble `[factorial_b, qwen3_8b_dtv, 05_dtv_v2_rag, TF-IDF+LR]` 四個系統：

- factorial_b: 最強 12c_Acc 0.432, Top-1 0.531
- qwen3_8b_dtv: 最強 12c_Top3 0.644
- 05_dtv_v2_rag: 最強 F1_weighted 0.453
- **TF-IDF+LR: 最強 F1_macro 0.295, F1_weighted 0.520**

TF-IDF 的 strengths 正好補 LLM systems 的 weakness：
- TF-IDF 的 Top-3 0.645 是因為它的 predict_proba 分佈更平均
- TF-IDF 的 F1_macro 0.295 是因為它在 train 看過所有 12 類的頻率，不會只預測 F32/F41
- LLM 的 12c_Acc 0.43 比 TF-IDF 的 0.27 高，是因為 LLM 能做 criterion-level reasoning

RRF 合併四個系統的 Top-k，預期**五個指標同時超越每個單一 source**。

## 技術改動

### Step 1：實作 TF-IDF + LR baseline

```python
# scripts/train_tfidf_baseline.py
"""Train TF-IDF + LR on LingxiDiag-16K train split, aligned with paper."""
import json
import pickle
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer

TWELVE_CLASS_LABELS = ['F20', 'F31', 'F32', 'F39', 'F41', 'F42', 'F43', 'F45', 'F51', 'F98', 'Z71', 'Others']

# Use paper-aligned config
TFIDF_CONFIG = {
    "max_features": 10000,
    "ngram_range": (1, 2),
    "min_df": 2,
    "max_df": 0.95,
    "token_pattern": r'(?u)\b\w+\b',
}

def to_paper_parent_list(code_str: str) -> list[str]:
    """Convert raw DiagnosisCode to paper parent labels."""
    import re
    out = []
    for part in re.split(r'[;,]', code_str.upper().strip()):
        part = part.strip()
        if not part: continue
        m = re.search(r'F(\d{2})', part)
        if 'Z71' in part:
            out.append('Z71')
        elif m:
            parent = f'F{m.group(1)}'
            out.append(parent if parent in TWELVE_CLASS_LABELS else 'Others')
    return list(dict.fromkeys(out)) or ['Others']

def load_lingxidiag_json(path: str):
    with open(path) as f:
        data = json.load(f)
    texts = []
    labels = []
    for case in data:
        # Assume dialog text is in 'conversation' or 'dialogue' field
        conv = case.get('conversation') or case.get('dialogue') or case.get('text')
        if isinstance(conv, list):
            text = '\n'.join(f"{t.get('role','')}:{t.get('content','')}" for t in conv)
        else:
            text = str(conv)
        texts.append(text)
        code = case.get('DiagnosisCode') or case.get('diagnosis_code') or ''
        labels.append(to_paper_parent_list(code))
    return texts, labels

def main():
    TRAIN_JSON = 'data/raw/lingxidiag16k/LingxiDiag-16K_train_data.json'
    VAL_JSON = 'data/raw/lingxidiag16k/LingxiDiag-16K_validation_data.json'
    
    X_train_text, y_train = load_lingxidiag_json(TRAIN_JSON)
    X_val_text, y_val = load_lingxidiag_json(VAL_JSON)
    
    mlb = MultiLabelBinarizer(classes=TWELVE_CLASS_LABELS)
    y_train_bin = mlb.fit_transform(y_train)
    y_val_bin = mlb.transform(y_val)
    
    vec = TfidfVectorizer(**TFIDF_CONFIG)
    X_train = vec.fit_transform(X_train_text)
    X_val = vec.transform(X_val_text)
    
    clf = OneVsRestClassifier(LogisticRegression(max_iter=2000, C=1.0))
    clf.fit(X_train, y_train_bin)
    
    # Save artifacts
    out = Path('outputs/tfidf_baseline')
    out.mkdir(parents=True, exist_ok=True)
    with open(out / 'vectorizer.pkl', 'wb') as f:
        pickle.dump(vec, f)
    with open(out / 'classifier.pkl', 'wb') as f:
        pickle.dump(clf, f)
    with open(out / 'mlb.pkl', 'wb') as f:
        pickle.dump(mlb, f)
    
    # Predict on val — get predict_proba for ranking
    probas = clf.predict_proba(X_val)  # shape (N, 12)
    
    predictions = []
    for i in range(len(y_val)):
        # Top-k codes by proba
        class_probs = list(zip(TWELVE_CLASS_LABELS, probas[i]))
        class_probs.sort(key=lambda x: -x[1])
        
        top_k = [c for c, _ in class_probs[:10]]
        
        # Binarize top-2 where proba > threshold (paper uses default threshold 0.5 but we can tune)
        preds = [c for c, p in class_probs if p >= 0.3][:2]
        if not preds:
            preds = [top_k[0]]
        
        predictions.append({
            'case_id': f'tfidf_val_{i:04d}',
            'gold_diagnoses': y_val[i],
            'primary_diagnosis': preds[0],
            'comorbid_diagnoses': preds[1:2],
            'top10_codes': top_k,
            'proba_scores': {c: float(p) for c, p in class_probs},
            'model_name': 'TF-IDF+LR',
        })
    
    with open(out / 'predictions.jsonl', 'w') as f:
        for p in predictions:
            f.write(json.dumps(p, ensure_ascii=False) + '\n')
    
    # Compute and log metrics
    from culturedx.eval.lingxidiag_paper import compute_table4_metrics
    # ... evaluate ...

if __name__ == '__main__':
    main()
```

### Step 2：擴充 RRF ensemble 支援 TF-IDF

在 `scripts/run_ensemble.py` 讀入 TF-IDF 的 `top10_codes`：

```python
systems = [
    ("factorial_b", "results/validation/factorial_b_improved_noevidence/predictions.jsonl"),
    ("qwen3_8b_dtv", "results/validation/multi_backbone/qwen3_8b_dtv/predictions.jsonl"),
    ("dtv_v2_rag", "results/validation/05_dtv_v2_rag/predictions.jsonl"),
    ("tfidf_lr", "outputs/tfidf_baseline/predictions.jsonl"),
]

weights_grid = [
    [1.0, 1.0, 1.0, 1.0],          # equal
    [1.2, 1.0, 1.0, 1.5],          # favor factorial_b + TF-IDF
    [1.0, 1.0, 1.0, 2.0],          # heavy TF-IDF
    [1.5, 0.8, 0.8, 1.5],          # favor the two 'specialists'
    [1.2, 1.2, 0.8, 1.2],          # balanced
]
```

### Step 3：Case ID alignment

這裡有個關鍵工程問題：**TF-IDF 的 case_id 要和你 DtV 系統對齊**。DtV 系統用的是 dataset 原本的 case_id，TF-IDF 如果我用 `tfidf_val_0000` 這種序號就對不上。必須讀同一份 `LingxiDiag-16K_validation_data.json` 按相同順序產生 predictions 並用相同 case_id。

## Pros

- 最便宜的 SOTA 推進：TF-IDF 訓練 < 5 分鐘、inference < 1 分鐘
- 直接吸收 paper SOTA 的所有優勢
- 實作風險低（sklearn 成熟）

## Cons / 論文敘事風險

- 「我的方法是 DtV MAS + TF-IDF ensemble」這個 story 可能讓 reviewers 覺得「你的 MAS 沒贏，是 TF-IDF 在救」
- **解決方式**：論文主結果表分兩行
  - Row A：CultureDx-DtV (LLM-only)  
  - Row B：CultureDx-DtV + TF-IDF stack  
  讓兩者的貢獻都可見。Row A 如果能在 12c_Acc/Top-1 贏所有 baselines（已經做到），Row B 用來刷全面 SOTA。

## 成功判準

- 12c_Acc ≥ 0.44
- 12c_Top1 ≥ 0.53
- 12c_Top3 ≥ 0.66（SOTA 0.645）
- 12c_F1_macro ≥ 0.30（SOTA 0.295）
- 12c_F1_weighted ≥ 0.52（SOTA 0.520）
- Overall ≥ 0.54（SOTA 0.533）

## 輸出路徑

- `outputs/tfidf_baseline/`：TF-IDF 訓練 artifacts
- `results/validation/t3_tfidf_stack/`：4-way ensemble final
