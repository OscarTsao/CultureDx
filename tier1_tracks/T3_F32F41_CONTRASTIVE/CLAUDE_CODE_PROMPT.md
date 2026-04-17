# T3-F32F41-CONTRASTIVE Claude Code Execution Prompt

**前置條件**：T1 已完成並 commit（在 branch `t1-diag-topk` 或已 merge 回 main）。
T3 基於 T1 的 all_checker_outputs 變更，單獨執行無效。

複製以下整段貼到本機 Claude Code session。

---

```
我要執行 CultureDx 的 T3-F32F41-CONTRASTIVE 修改。這是基於 error taxonomy 發現 F32↔F41 ranking 錯誤佔 IN_TOP3_NOT_TOP1 的 109/151 (72%)。

T1 已完成 (diagnostician top-5 + logic on all_checker_outputs + primary scan top-5)。T3 在 T1 基礎上加入 F32 vs F41 專用對比判斷。

## Step 1: 切新 branch (from T1 branch)

git checkout t1-diag-topk  # or wherever T1 is
git checkout -b t3-f32f41-contrastive

## Step 2: 建立新 prompt 檔案

建立 prompts/agents/f32_f41_contrastive_zh.jinja，內容如下：

---START OF FILE---
你是精神科鉴别诊断专家。以下 case 同时符合 F32（抑郁障碍）和 F41（焦虑障碍）的诊断标准。
请根据临床证据，判断哪个是**主诊断**（primary）、哪个是共病（comorbid 或不存在）。

## 临床对话

{{ transcript_text }}

## F32（抑郁）checker 结果

符合 criteria: {{ f32_met }} / {{ f32_total }}
主要症状证据（前 3 条）：
{% for ev in f32_evidence %}- {{ ev }}
{% endfor %}

## F41（焦虑）checker 结果

符合 criteria: {{ f41_met }} / {{ f41_total }}
主要症状证据（前 3 条）：
{% for ev in f41_evidence %}- {{ ev }}
{% endfor %}

## 鉴别要点

- **F32 核心**：持续 ≥2 周的情绪低落 + 兴趣丧失 + 精力减退（至少 2 项持续存在）
- **F41 核心**：过度担忧多个领域 ≥6 月 + **自主神经症状**（心慌、胸闷、出汗、口干、头晕）
- **关键鉴别**：
  - 主诉是心情不好、兴趣下降 → 更可能 F32 primary
  - 主诉是担忧、紧张、心慌、胸闷 → 更可能 F41 primary
  - 如两者都明显但焦虑是近期反应性的 → F32 primary, F41 comorbid
  - 如抑郁是焦虑长期后继发的 → F41 primary, F32 comorbid

## 输出

请严格按以下 JSON 格式输出，不要其他文字：

{
  "primary": "F32" 或 "F41",
  "comorbid_present": true 或 false,
  "reasoning": "30 字以内说明"
}

若两者都明显但无法分辨主次（真正共病且权重相当），选 primary 为症状证据数更多的那个。
---END OF FILE---

## Step 3: 在 hied.py 加入 _run_f32_f41_contrastive method

開啟 src/culturedx/modes/hied.py。

在 HiedMode class 的 `_parallel_check_criteria` method 附近（約 line 400-500 之間，找個 coherent 位置），新增 method：

```python
    def _run_f32_f41_contrastive(
        self,
        transcript_text: str,
        f32_output,
        f41_output,
        lang: str,
    ) -> tuple[str, bool]:
        """T3: Run F32 vs F41 contrastive LLM call.
        Returns (primary_code, comorbid_present).
        Falls back to higher-met_ratio disorder if LLM fails.
        """
        from jinja2 import Environment, FileSystemLoader
        from culturedx.llm.json_utils import extract_json_from_response

        f32_ratio = f32_output.criteria_met_count / max(f32_output.criteria_required, 1)
        f41_ratio = f41_output.criteria_met_count / max(f41_output.criteria_required, 1)
        default = ("F32", True) if f32_ratio >= f41_ratio else (f41_output.disorder, True)

        try:
            env = Environment(loader=FileSystemLoader(str(self.prompts_dir)))
            template_name = f"f32_f41_contrastive_{lang}.jinja"
            template = env.get_template(template_name)

            def top_evidence(co, n=3):
                evs = []
                for cr in co.criteria[:n]:
                    if cr.status == "met" and cr.evidence:
                        evs.append(f"{cr.criterion_id}: {cr.evidence[:80]}")
                return evs

            prompt = template.render(
                transcript_text=transcript_text[:4000],
                f32_met=f32_output.criteria_met_count,
                f32_total=f32_output.criteria_required,
                f32_evidence=top_evidence(f32_output),
                f41_met=f41_output.criteria_met_count,
                f41_total=f41_output.criteria_required,
                f41_evidence=top_evidence(f41_output),
            )

            source, _, _ = env.loader.get_source(env, template_name)
            prompt_hash = self.llm.compute_prompt_hash(source)

            raw = self.llm.generate(prompt, prompt_hash=prompt_hash, language=lang)
            parsed = extract_json_from_response(raw)

            if not parsed or not isinstance(parsed, dict):
                return default

            primary = parsed.get("primary", "").strip().upper()
            comorbid_present = bool(parsed.get("comorbid_present", True))

            if primary == "F32":
                return ("F32", comorbid_present)
            elif primary == "F41":
                return (f41_output.disorder, comorbid_present)
            else:
                return default
        except Exception as e:
            logger.warning(f"F32/F41 contrastive failed, falling back: {e}")
            return default
```

## Step 4: 整合到 DtV primary selection

找到 T1 修改過的 primary selection 結尾（大約是新的 comorbid loop 結束之後，但在 `stage_timings["total"]` 之前）。

在 comorbid 的 for loop 結束之後，加入：

```python
        # T3: F32↔F41 Contrastive Re-ranking
        # Trigger when both F32 and F41 (any subcode) are in confirmed_set
        f32_confirmed = "F32" in confirmed_set
        f41_confirmed = any(c.startswith("F41") for c in confirmed_set)

        if f32_confirmed and f41_confirmed:
            f32_co = next((co for co in all_checker_outputs if co.disorder == "F32"), None)
            f41_co = next(
                (co for co in all_checker_outputs if co.disorder.startswith("F41")),
                None,
            )

            if f32_co and f41_co:
                contrastive_start = time.monotonic()
                cont_primary_code, cont_comorbid_present = self._run_f32_f41_contrastive(
                    transcript_text, f32_co, f41_co, lang,
                )
                stage_timings["f32_f41_contrastive"] = time.monotonic() - contrastive_start

                original_primary = primary
                swap_made = False

                # Check if contrastive disagrees with current primary
                primary_is_f32 = primary == "F32"
                primary_is_f41 = primary.startswith("F41")
                cont_says_f32 = cont_primary_code == "F32"
                cont_says_f41 = cont_primary_code.startswith("F41")

                if primary_is_f41 and cont_says_f32:
                    primary = "F32"
                    comorbid = [f41_co.disorder] if cont_comorbid_present else []
                    swap_made = True
                elif primary_is_f32 and cont_says_f41:
                    primary = f41_co.disorder
                    comorbid = ["F32"] if cont_comorbid_present else []
                    swap_made = True

                if swap_made:
                    logger.info(
                        "Case %s: F32/F41 contrastive override: %s -> %s",
                        case.case_id, original_primary, primary,
                    )

                decision_trace["f32_f41_contrastive"] = {
                    "triggered": True,
                    "original_primary": original_primary,
                    "contrastive_result": cont_primary_code,
                    "comorbid_present": cont_comorbid_present,
                    "override_applied": swap_made,
                }
```

## Step 5: Smoke test

```bash
uv run culturedx run \
  -c configs/base.yaml \
  -c configs/vllm_awq.yaml \
  -c configs/v2.4_final.yaml \
  -d lingxidiag16k \
  --data-path data/raw/lingxidiag16k \
  -n 50 \
  --run-name t3_smoke_n50
```

驗證 contrastive 有觸發：

```bash
python3 -c "
import json
triggered = 0
override = 0
with open('results/validation/t3_smoke_n50/predictions.jsonl') as f:
    for line in f:
        r = json.loads(line)
        c = r.get('decision_trace', {}).get('f32_f41_contrastive')
        if c:
            triggered += 1
            if c['override_applied']:
                override += 1
print(f'Contrastive triggered: {triggered}/50')
print(f'Override applied: {override}')
"
```

成功標準：triggered > 5 (至少 10% trigger rate)。若 0 triggered，表示 confirmed_set 沒有同時包含 F32 和 F41，debug logic engine 邏輯。

## Step 6: Full run N=1000

```bash
uv run culturedx run \
  -c configs/base.yaml \
  -c configs/vllm_awq.yaml \
  -c configs/v2.4_final.yaml \
  -d lingxidiag16k \
  --data-path data/raw/lingxidiag16k \
  -n 1000 \
  --run-name t1_t3_combined_n1000 \
  2>&1 | tee outputs/t1_t3_combined_n1000.log
```

預計時間：T1 的 3.5-4 小時 + T3 的 +5-10 min = ~4 小時

## Step 7: 比較三版 metrics

```bash
for run in factorial_b_improved_noevidence t1_diag_topk_n1000 t1_t3_combined_n1000; do
    echo "=== $run ==="
    python3 -c "
import json
try:
    d = json.load(open('results/validation/$run/metrics_summary.json'))
    t = d['metrics']['table4']
    for k in ['12class_Acc','12class_Top1','12class_Top3','12class_F1_macro','12class_F1_weighted']:
        print(f'  {k}: {t[k]:.3f}')
except FileNotFoundError:
    print('  (not run yet)')
"
done
```

## Step 8: 重跑 error taxonomy

```bash
sed -i.bak 's|results/validation/factorial_b_improved_noevidence|results/validation/t1_t3_combined_n1000|g' scripts/error_taxonomy_v24.py
python3 scripts/error_taxonomy_v24.py > results/validation/t1_t3_combined_n1000/error_taxonomy_report.txt
mv scripts/error_taxonomy_v24.py.bak scripts/error_taxonomy_v24.py
cat results/validation/t1_t3_combined_n1000/error_taxonomy_report.txt
```

**成功標準**：
- IN_TOP3_NOT_TOP1 從 T1 的 ~150 → <100（救回 ~50 個 F41↔F32 錯誤）
- F41 per-class recall >55%
- 12c_Top1 >= 0.58
- 12c_F1_macro >= 0.26

## Step 9: 分析 contrastive 的 precision

```bash
python3 -c "
import json, sys
sys.path.insert(0, 'src')
from culturedx.eval.lingxidiag_paper import to_paper_parent

overrides = {'f32_to_f41': [], 'f41_to_f32': []}
with open('results/validation/t1_t3_combined_n1000/predictions.jsonl') as f:
    for line in f:
        r = json.loads(line)
        c = r.get('decision_trace', {}).get('f32_f41_contrastive', {})
        if not c.get('override_applied'): continue
        orig = to_paper_parent(c['original_primary'])
        new = to_paper_parent(r['primary_diagnosis'])
        golds = [to_paper_parent(g) for g in r.get('gold_diagnoses', [])]
        hit = new in golds
        key = 'f32_to_f41' if orig == 'F32' else 'f41_to_f32'
        overrides[key].append({'gold': golds[0], 'hit': hit})

for direction, cases in overrides.items():
    hits = sum(1 for c in cases if c['hit'])
    n = len(cases)
    print(f'{direction}: {hits}/{n} ({hits/n*100:.1f}% correct)')
"
```

期望：兩個方向的 override 準確率都 >65%。若某方向 <50% 表示 contrastive LLM 偏向那個方向導致誤判。

## Step 10: Commit

```bash
git add prompts/agents/f32_f41_contrastive_zh.jinja src/culturedx/modes/hied.py
git commit -m "T3: F32↔F41 contrastive re-ranking for dual-confirmed cases

When logic_engine confirms both F32 and F41, run dedicated LLM call to
decide which is primary. Triggered based on T1's all_checker_outputs
evaluation which exposes both disorders simultaneously.

Attacks IN_TOP3_NOT_TOP1 (13.8% of errors, 109 F32↔F41 cases).
Expected: F41 recall +10pp, Top-1 +4pp."
```

請開始執行 Step 1。
```

---

## 額外說明

如果 T1 已跑完的 predictions.jsonl 顯示 F32 和 F41 confirmed 同時出現的比例 < 20%，T3 觸發會很少。那時要先調低 logic engine threshold 讓 confirm 更 aggressive，或把 trigger 條件改成 "F32 和 F41 都在 top-3 ranked_codes"。

先看 T1 跑完後的 decision_trace 數據再決定。
