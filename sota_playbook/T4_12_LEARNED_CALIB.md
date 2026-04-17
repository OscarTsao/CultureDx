# T4-CALIB-LEARNED：Learned Calibrator with LightGBM LambdaRank

## 動機

你 paper_narrative_v2.md 的 C1 指出：**Detection ceiling 82%，但 Top-1 僅 51.5%，30pp gap 來自 ranking 錯誤，不是 detection 錯誤**。

你目前的 Calibrator 是 `heuristic-v2`（rule-based），根據 met_count/required_count 做 proportion-based ranking。這個規則很好但沒有從資料學習：
- 當兩個 disorder 都 confirmed，誰該排第一？heuristic 不知道
- 不同 class 的 precision 天生就不一樣，heuristic 不知道
- Transcript 語意特徵（例如主訴是「擔心」vs「情緒低落」）heuristic 沒用到

**LightGBM LambdaRank** 是專門為 learning-to-rank 設計的算法：
- 訓練目標是直接 optimize NDCG@3（= Top-3 accuracy 類似指標）
- Input：pairwise features (disorder A vs disorder B)
- Output：每個 (case, disorder) 的 ranking score

## 假設

Train LightGBM LambdaRank on LingxiDiag-16K train split，用 logic_engine + checker 輸出的 features 作為 input。預期：
- 12c_Top1 +2-3pp
- 12c_Top3 +3-4pp（LambdaRank 的主力）
- F1_macro 可能小升（如果 ranking 改善讓 low-freq 進 top-3 的機會提高）

## 技術設計

### Feature Engineering

對每個 case 的每個候選 disorder，產生一個 feature vector:

```python
def extract_calibrator_features(case, disorder_code, checker_output, logic_engine_output):
    return {
        # Checker signals
        "met_count": checker_output.met_count,
        "total_count": checker_output.total_count,
        "met_ratio": checker_output.met_count / max(checker_output.total_count, 1),
        "n_insufficient_evidence": sum(1 for c in checker_output.criteria if c.status == "insufficient_evidence"),
        "avg_criterion_confidence": np.mean([c.confidence for c in checker_output.criteria]),
        
        # Logic engine signals
        "meets_threshold": int(logic_engine_output.meets_threshold),
        "confirmation_type_soft": int(logic_engine_output.confirmation_type == "soft"),
        
        # Disorder prior
        "disorder_freq_in_train": CLASS_FREQ[disorder_code],  # e.g., F32 = 0.348
        "is_low_freq": int(disorder_code in LOW_FREQ_CLASSES),
        
        # Somatization hits
        "n_somatic_keywords_matched": count_somatic_keywords(case.transcript, disorder_code),
        
        # Transcript meta
        "transcript_length": len(case.transcript),
        "n_turns": case.transcript.count("医生") + case.transcript.count("患者"),
        
        # Diagnostician prior (from ranked_codes)
        "diagnostician_rank": rank_in_diagnostician(disorder_code, case),  # 1, 2, 3, ...
        "diagnostician_top1": int(case.diagnostician_top1 == disorder_code),
        
        # Disorder-specific
        "is_F32_with_somatic_evidence": int(disorder_code == "F32" and has_somatic(case)),
        "is_F41_without_worry_keyword": int(disorder_code.startswith("F41") and not has_worry(case)),
        # ... more class-specific features
    }
```

### Training

```python
import lightgbm as lgb

# Labels: for each (case, disorder) pair, label = 1 if disorder is in gold, else 0
# Group: cases

train_data = lgb.Dataset(
    X_train_features,  # shape (N_pairs, D_features)
    label=y_train_labels,  # shape (N_pairs,), 1 or 0
    group=train_group_sizes,  # [num_candidates_per_case, ...]
)

params = {
    "objective": "lambdarank",
    "metric": "ndcg",
    "eval_at": [1, 3],
    "learning_rate": 0.05,
    "num_leaves": 31,
    "max_depth": -1,
    "lambda_l2": 1.0,
    "verbose": -1,
}

gbm = lgb.train(params, train_data, num_boost_round=500, early_stopping_rounds=50)

# Inference: rank disorders within each case by gbm.predict()
```

### Integration

```python
# src/culturedx/diagnosis/calibrator.py
class LearnedCalibrator(Calibrator):
    def __init__(self, model_path: str):
        import lightgbm as lgb
        self.model = lgb.Booster(model_file=model_path)
    
    def rank(self, case, confirmed_results, rejected_results):
        # Extract features for all confirmed + rejected
        all_candidates = confirmed_results + rejected_results
        features = np.array([
            extract_calibrator_features(case, r.disorder_code, ...) 
            for r in all_candidates
        ])
        
        scores = self.model.predict(features)
        ranked = sorted(zip(all_candidates, scores), key=lambda x: -x[1])
        return [r for r, s in ranked]
```

## 訓練資料來源

三種選擇：

1. **Bootstrap from factorial_b on train split**：跑 factorial_b 在 14000 train cases，得到 checker outputs + logic engine outputs，這些作為 LightGBM features，gold 作為 label。**這個方案成本最高（要跑 14000 cases LLM inference）**，但資料品質最高。

2. **Use checker outputs from existing factorial_b validation run + cross-val**：只有 1000 cases，train set 很小，可能 overfit。

3. **Synthetic bootstrap**：從 LoRA checker 輸出（更快、更便宜），但需要先有 LoRA checker ready。

建議選 **(1)**：花 8 小時跑一次 14000 cases 產生 training features，之後 LightGBM 訓練 5 分鐘，inference 毫秒。

## 成功判準

- 12c_Top1 ≥ 0.55（baseline 0.531）
- 12c_Top3 ≥ 0.63
- F1_macro 不降

## 輸出

- `outputs/learned_calibrator/lgbm_lambdarank.txt`
- `results/validation/t4_learned_calib/`

## 風險

- Feature engineering 是 art，可能 iterate 幾輪才找到對的 features
- 在 train split 上表現好，val 上不一定（overfit）
- LightGBM 難解釋（相比 heuristic 的 rule-based）→ 論文要加 feature importance 分析

## 和其他 track 的關係

T4-CALIB-LEARNED 可以和 T3-TFIDF-STACK 或 T3-LORA-CLF 疊加：
- 用 Learned Calibrator 提升 CultureDx-DtV 單系統的 Top-1/Top-3
- 然後把這個強化版 DtV 丟進 ensemble
