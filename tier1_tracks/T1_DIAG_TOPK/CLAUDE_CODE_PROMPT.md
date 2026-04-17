# T1-DIAG-TOPK Claude Code Execution Prompt

複製以下整段貼到本機 Claude Code session。Claude Code 會自動執行所有步驟。

---

```
我要執行 CultureDx 的 T1-DIAG-TOPK 修改，這是基於 error taxonomy 發現的三個 bug-like 問題修正。請嚴格按照以下步驟執行，每步驟完成後告訴我結果：

## 背景

error_taxonomy_v24.py 在 results/validation/factorial_b_improved_noevidence/ 發現：
- Diagnostician 99.8% case 只輸出 top-2（prompt schema 限制）
- Logic engine 只看 top-3 checker outputs，remaining_outputs 被丟棄
- Primary selection 從 top-3 硬選
- 導致 DIAGNOSTICIAN_MISS 佔所有錯誤 29.7%，long-tail class (F98/F43/Z71) recall = 0%

## Step 1: 切新 branch

git checkout -b t1-diag-topk
git status  # 確認乾淨

## Step 2: 修改 diagnostician prompt

開啟 prompts/agents/diagnostician_v2_zh.jinja，找到結尾的 JSON schema 段（約第 93-103 行）。

找到這段：
```
## 输出要求

请严格按照以下JSON格式输出：
{
  "ranked_diagnoses": [
    {"code": "ICD代码", "reasoning": "简要理由（包含主诉、核心症状、鉴别依据）"},
    {"code": "ICD代码", "reasoning": "简要理由"}
  ]
}
请先用中文简要分析（50-100字），必须包含：主诉是什么？核心症状指向哪个诊断？然后输出JSON。
```

替換為：
```
## 输出要求

**重要：必须输出 5 个候选诊断，按可能性从高到低排序。** 即使某些候选可能性较低也要列出，以确保下游验证能覆盖不常见的障碍。

候选排列建议：
- 前 2 名：你最确信的主诊断与鉴别诊断
- 第 3-4 名：需要排除但不是首选的可能
- 第 5 名：低频但不能完全排除的障碍（如 F98 儿童行为、F43 应激、F45 躯体化、F51 睡眠、Z71 咨询、F31 双相等）

每个候选的 reasoning 限制在 30 字以内以节省 token。

请严格按照以下JSON格式输出（必须恰好 5 个 items）：
{
  "ranked_diagnoses": [
    {"code": "ICD代码1", "reasoning": "30字以内"},
    {"code": "ICD代码2", "reasoning": "30字以内"},
    {"code": "ICD代码3", "reasoning": "30字以内"},
    {"code": "ICD代码4", "reasoning": "30字以内"},
    {"code": "ICD代码5", "reasoning": "30字以内"}
  ]
}

请先用中文简要分析（50-100字），包含：主诉是什么？核心症状指向哪个诊断？为什么需要考虑前 5 名？然后输出JSON。
```

保存，然後 `git diff prompts/agents/diagnostician_v2_zh.jinja` 確認修改正確。

## Step 3: 修改 hied.py 的 verify_codes 擴充

開啟 src/culturedx/modes/hied.py。

找到（約 line 998）：
```python
        verify_codes = ranked_codes[:3]
```

替換為：
```python
        verify_codes = ranked_codes[:5]  # T1: expand top-3 -> top-5 for long-tail coverage
```

## Step 4: 修改 logic engine 用 all_checker_outputs

繼續在 hied.py，找到（約 line 1072）：
```python
        logic_output = self.logic_engine.evaluate(checker_outputs)
```

替換為：
```python
        # T1: evaluate logic on ALL checker outputs (including remaining), not just top-3
        # This lets long-tail disorders that pass checker contribute to confirmed_set.
        logic_output = self.logic_engine.evaluate(all_checker_outputs)
```

## Step 5: 重寫 primary selection

找到這整段（約 line 1066-1108，包含 top1_code / top2_code / top3_code 的定義到 else: confidence = 0.6）：

```python
        top1_code = ranked_codes[0]
        top2_code = ranked_codes[1] if len(ranked_codes) > 1 else None
        top3_code = ranked_codes[2] if len(ranked_codes) > 2 else None

        logic_output = self.logic_engine.evaluate(all_checker_outputs)
        confirmed_set = set(logic_output.confirmed_codes)

        primary = top1_code
        comorbid: list[str] = []
        confidence = 0.8
        veto_applied = False

        if top1_code in confirmed_set:
            confidence = 0.9
            # Add best confirmed comorbid (top-2 preferred, top-3 as fallback)
            for tc in [top2_code, top3_code]:
                if tc and tc in confirmed_set:
                    comorbid.append(tc)
            comorbid = comorbid[:1]  # cap to 1 comorbid (max 2 labels, per paper protocol)
        elif top2_code and top2_code in confirmed_set:
            logger.info(
                "Case %s: DtV veto - top-1 %s not confirmed, promoting top-2 %s",
                case.case_id,
                top1_code,
                top2_code,
            )
            primary = top2_code
            confidence = 0.7
            veto_applied = True
            # top-3 can still be comorbid if confirmed
            if top3_code and top3_code in confirmed_set:
                comorbid = [top3_code]  # max 1 comorbid
        elif top3_code and top3_code in confirmed_set:
            logger.info(
                "Case %s: DtV veto - top-1 %s and top-2 %s not confirmed, promoting top-3 %s",
                case.case_id,
                top1_code,
                top2_code,
                top3_code,
            )
            primary = top3_code
            confidence = 0.6
            veto_applied = True
        else:
            confidence = 0.6
```

替換為：

```python
        # T1: Primary selection expanded from top-3 to top-5 + fallback to all confirmed
        top_ranked = ranked_codes[:5]  # up to top-5 from diagnostician
        logic_output = self.logic_engine.evaluate(all_checker_outputs)
        confirmed_set = set(logic_output.confirmed_codes)

        # Compute met_ratios once, used by both primary selection and logging
        met_ratios = {
            co.disorder: (co.criteria_met_count / max(co.criteria_required, 1))
            for co in all_checker_outputs
        }

        primary = None
        comorbid: list[str] = []
        confidence = 0.8
        veto_applied = False
        primary_source = "top1"  # for logging

        # Pass 1: prefer diagnostician ordering - first confirmed in top-5
        for idx, rc in enumerate(top_ranked):
            if rc in confirmed_set:
                primary = rc
                if idx == 0:
                    confidence = 0.9
                    primary_source = "top1"
                else:
                    confidence = 0.85 - 0.05 * idx
                    veto_applied = True
                    primary_source = f"top{idx+1}"
                break

        # Pass 2: fallback - any confirmed (outside top-5), pick by met_ratio desc
        if primary is None and confirmed_set:
            confirmed_by_ratio = sorted(
                confirmed_set,
                key=lambda c: met_ratios.get(c, 0.0),
                reverse=True,
            )
            primary = confirmed_by_ratio[0]
            confidence = 0.65
            veto_applied = True
            primary_source = "remaining_confirmed"

        # Pass 3: no confirmed at all - fall back to top-1
        if primary is None:
            primary = top_ranked[0]
            confidence = 0.55
            primary_source = "no_confirmed_fallback"

        if primary_source != "top1":
            logger.info(
                "Case %s: DtV primary from %s (top-1 %s -> primary %s)",
                case.case_id,
                primary_source,
                top_ranked[0],
                primary,
            )

        # Build comorbid list: prefer ranked order, must be confirmed and not primary
        for rc in top_ranked:
            if rc != primary and rc in confirmed_set:
                comorbid.append(rc)
                if len(comorbid) >= 1:
                    break  # max 1 comorbid per paper protocol
```

## Step 6: Smoke test (N=50)

先跑小規模確認 pipeline 沒壞：

```bash
uv run culturedx run \
  -c configs/base.yaml \
  -c configs/vllm_awq.yaml \
  -c configs/v2.4_final.yaml \
  -d lingxidiag16k \
  --data-path data/raw/lingxidiag16k \
  -n 50 \
  --run-name t1_smoke_n50
```

檢查 `results/validation/t1_smoke_n50/predictions.jsonl` 的第一筆資料：

```bash
head -1 results/validation/t1_smoke_n50/predictions.jsonl | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ranked = d['decision_trace']['diagnostician']['ranked_codes']
verify = d['decision_trace']['verify_codes']
print(f'ranked_codes len: {len(ranked)} ({ranked})')
print(f'verify_codes len: {len(verify)} ({verify})')
print(f'confirmed: {d[\"decision_trace\"][\"logic_engine_confirmed_codes\"]}')
print(f'primary: {d[\"primary_diagnosis\"]}')
"
```

**成功標準**：
- ranked_codes 長度 = 5（或至少 4）
- verify_codes 長度 = 5
- confirmed_codes 可能多於 1 個（因為現在看 all_checker_outputs）

如果任何 assertion 失敗，停下來 report 錯誤。

## Step 7: Full run (N=1000)

確認 smoke test ok 後：

```bash
uv run culturedx run \
  -c configs/base.yaml \
  -c configs/vllm_awq.yaml \
  -c configs/v2.4_final.yaml \
  -d lingxidiag16k \
  --data-path data/raw/lingxidiag16k \
  -n 1000 \
  --run-name t1_diag_topk_n1000 \
  2>&1 | tee outputs/t1_diag_topk_n1000.log
```

預計 3.5-4 小時完成。

## Step 8: 重跑 error taxonomy

```bash
# 修改 scripts/error_taxonomy_v24.py 的 PRED_PATH 指向新 run
PRED_PATH="results/validation/t1_diag_topk_n1000/predictions.jsonl" \
  python3 scripts/error_taxonomy_v24.py \
  > results/validation/t1_diag_topk_n1000/error_taxonomy_report.txt

cat results/validation/t1_diag_topk_n1000/error_taxonomy_report.txt
```

（如果 script 沒支援環境變數，直接 in-place 改 PRED_PATH string）

## Step 9: Diff metrics

```bash
echo "=== BEFORE (factorial_b) ==="
python3 -c "
import json
d = json.load(open('results/validation/factorial_b_improved_noevidence/metrics_summary.json'))
t = d['metrics']['table4']
for k in ['12class_Acc','12class_Top1','12class_Top3','12class_F1_macro','12class_F1_weighted']:
    print(f'  {k}: {t[k]:.3f}')
"
echo "=== AFTER (t1_diag_topk) ==="
python3 -c "
import json
d = json.load(open('results/validation/t1_diag_topk_n1000/metrics_summary.json'))
t = d['metrics']['table4']
for k in ['12class_Acc','12class_Top1','12class_Top3','12class_F1_macro','12class_F1_weighted']:
    print(f'  {k}: {t[k]:.3f}')
"
```

## Step 10: Commit

```bash
git add prompts/agents/diagnostician_v2_zh.jinja src/culturedx/modes/hied.py
git commit -m "T1: expand diagnostician top-K 2->5 + logic on all_checker_outputs

- Diagnostician prompt: JSON schema 2 items -> 5 items, add long-tail screening hint
- hied.py verify_codes: top-3 -> top-5
- hied.py logic_engine: evaluate(checker_outputs) -> evaluate(all_checker_outputs)
- hied.py primary selection: scan top-5 instead of top-3; fallback to any confirmed by met_ratio

Attacks DIAGNOSTICIAN_MISS (29.7% of errors) per error_taxonomy_v24.py report.
Expected: DIAG_MISS 324 -> <150, F98/F43/Z71 recall 0% -> >10%, F1_macro 0.202 -> 0.24+"
```

請開始執行 Step 1。遇到任何問題停下來回報。
```

---

## 如果遇到問題

最可能的 breakage 場景和對策：

1. **Diagnostician 拒絕輸出 5 個** → JSON parse fail: 
   - 把 prompt 加更強的語氣："如果你只想出 3 個，也必須填滿 5 個，第 4-5 名可以是排除性選項"
   - Fallback: 在 `src/culturedx/agents/diagnostician.py` 的 `_validate` 裡接受 >= 2 個

2. **Token 超限** → response truncated:
   - `configs/vllm_awq.yaml` 的 `max_tokens` 從 1536 提到 2048
   - 或者 prompt 把 reasoning 限制降到 20 字

3. **Primary 亂跳（某個 test case 明顯錯了）** → 看 `primary_source` log:
   - 如果常出現 `remaining_confirmed` → checker 對某個 long-tail class 有 false positive
   - 這種情況在 commit message 誠實記錄，T2/T3 可能要壓抑此現象

4. **Smoke test N=50 就跑很慢** → vLLM cache 全 miss:
   - 正常，不用怕，N=1000 跑下去 cache 會有約 30% hit rate
