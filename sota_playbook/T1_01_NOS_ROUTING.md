# T1-NOS：NOS Routing Rule

## 問題

你的 `diagnostician_v2_zh.jinja` 開頭雖然有「症状严重程度或细节不明确时，优先选择未特指(NOS)代码」，但整個 prompt 的「第1步主訴識別」和「第2步核心症狀群辨識」把 F39、F41.9、F45.9 等 NOS 代碼邊緣化了。候選列表也沒明確列出 F41.9、F45.9、F51.9、F43.9 這些 NOS subcodes。

結果：F39 gold=60, 預測回來只有 14；F45 gold=8, 預測 3；F43 gold=11, 預測 0。

**官方 LingxiDiag prompt 的 NOS 指令**（from paper p.17 Appendix C.3.3）：

> 注意：(1) 问诊对话为初次问诊，在症状严重程度和细节不可判断的时候，请推荐未特指的icd code。

這條規則直接讓 LLM 把「不明確」路由到 NOS code，避免被其他明確 disorder 吸收。

## 假設

在 diagnostician prompt 裡加入結構化 NOS routing rules，並在 candidate_disorders 裡加入所有 NOS subcodes，預期：

- F39 recall: 3% → 30%+
- F41.9/F45.9/F51.9/F43.9: 從 0 救起
- F1_macro: 0.202 → 0.26+
- F1_weighted: 0.449 → 0.47+

## 預期風險

- F32 recall 可能會略降（因為有些 borderline F32 會被路由到 F39）
- Top-1 accuracy 可能持平或微降（NOS code 的 precision 通常不高）
- **此實驗是 F1_macro 優化，不是 Top-1 優化**

## 技術改動

### 檔案 1：`prompts/agents/diagnostician_v2_zh.jinja`

新增「第 0 步：NOS 判定」，作為第一個 pre-check：

```jinja
**第0步：NOS 初篩（優先判定）**

在進入具體疾患鑑別前，先判斷是否適用 NOS（未特指）代碼。以下情境應優先輸出 NOS code：

(a) 症狀明顯存在情緒/焦慮/軀體問題，但強度、持續時間、或具體症狀群不完整 → 使用 F39（未特指心境障礙）
(b) 有焦慮症狀但不符合 F41.0/F41.1 任一的完整標準 → 使用 F41.9（未特指焦慮）
(c) 有軀體抱怨但不符合 F45.0-F45.4 任一 → 使用 F45.9
(d) 有失眠但未達 F51.0 嚴重度標準 → 使用 F51.9
(e) 有應激源但症狀不足以達 F43.1/F43.2 → 使用 F43.9
(f) 僅為諮詢、健康教育、生活方式指導，無明確精神疾患 → 使用 Z71
(g) 症狀完全不符合任何 F20-Z71 分類 → 使用 "Others"

⚠ 判定原則：當你「接近確診 F32 但缺少核心症狀 1-2 項」時，不要強行給 F32，改給 F39。
⚠ 對初次門診而言，「寧可給 NOS，也不要給錯的 specific code」是安全原則。
```

### 檔案 2：`src/culturedx/core/targets.py`（或等價處）

把 14 個 target_disorders 擴充為 18 個：

```yaml
target_disorders:
  - F20
  - F31
  - F32
  - F39        # already
  - F41.0
  - F41.1
  - F41.2
  - F41.9      # NEW — NOS for anxiety
  - F42
  - F43.1
  - F43.2
  - F43.9      # NEW — NOS for stress
  - F45
  - F45.9      # NEW — NOS for somatoform
  - F51
  - F51.9      # NEW — NOS for sleep
  - F98
  - Z71
```

### 檔案 3：`src/culturedx/ontology/icd10.py`（或等價處）

為新增的 NOS subcodes 加入 criteria threshold。建議使用 **lenient threshold**：只要同父類的任何 B/C 標準有 1-2 項 met 就算 NOS 符合。

```python
NOS_LENIENT_RULES = {
    "F41.9": {"min_met": 1, "any_of": ["B1", "B2", "B3", "B4"]},  # any anxiety symptom
    "F43.9": {"min_met": 1, "any_of": ["A", "B1", "B3"]},  # stress source + any reaction
    "F45.9": {"min_met": 1, "any_of": ["C1", "C2", "C3"]},  # any somatic
    "F51.9": {"min_met": 1, "any_of": ["A", "D"]},  # sleep issue + any distress
}
```

### 檔案 4：`configs/overlays/t1_nos_routing.yaml`（新檔）

```yaml
# Overlay: T1-NOS Routing — expand NOS subcodes, update diagnostician prompt
mode:
  target_disorders:
    - F20
    - F31
    - F32
    - F39
    - F41.0
    - F41.1
    - F41.2
    - F41.9
    - F42
    - F43.1
    - F43.2
    - F43.9
    - F45
    - F45.9
    - F51
    - F51.9
    - F98
    - Z71
  prompt_variant: v2_nos  # new prompt variant
  checker_prompt_variant: v2_improved  # keep factorial_b's winning checker
```

## 輸出路徑

`results/validation/t1_nos/`

## 成功判準

- F1_macro 從 0.202 → ≥ 0.25（+5pp 以上）
- F1_weighted 從 0.449 → ≥ 0.47（+2pp 以上）
- Top-1 下降不超過 2pp（從 0.531 → ≥ 0.51）
- Bootstrap CI 在 F1_macro 上顯示 significant improvement (p < 0.05)

## Per-class 檢核（跑完後必做）

```python
# 檢核 F39, F41.9, F45.9, F51.9, F43.9 是否至少有一些預測
pred_dist = Counter(primary_diagnoses)
assert pred_dist["F39"] > 10, "F39 should now be predicted for borderline cases"
assert pred_dist["F41.9"] > 0 or pred_dist["F41"] > 0
```
