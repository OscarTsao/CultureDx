#!/usr/bin/env python3
"""Multi-method probe runner.

Dispatches by --method to one of:
  b1a — Two-diagnostician ensemble (Borda vote on Qwen3 + X ranked lists)
  b1b — Comorbidity specialist (X decides yes/no comorbid given case+primary)
  b2  — Replace checker (X re-runs criterion checking on Qwen3's top-5)
  b3a — Primary-fix agent (X reviews Qwen3's primary, may revise)
  b3b — Meta-reasoning, no transcript (X decides primary from structured signals only)

Inputs (per case): existing Qwen3 predictions from a chosen source dir.
Outputs (per case): JSON with revised primary/comorbid/reasoning.
Final output: predictions.jsonl in the same schema as canonical, plus a metrics summary.
"""
from __future__ import annotations
import argparse, json, sys, time, urllib.request, urllib.error
from pathlib import Path
from collections import Counter, defaultdict

REPO = Path("/home/user/YuNing/CultureDx")
VLLM_BASE = "http://localhost:8000/v1"

DOMAIN_PAIRS = {
    "F32": ["F41"], "F41": ["F32", "F42"], "F42": ["F41"],
    "F33": ["F41"], "F51": ["F32", "F41"], "F98": ["F41"],
}

def base_code(c): return c.split(".")[0] if c else c
def base_set(codes): return set(base_code(c) for c in codes)

def load_jsonl(p): 
    with open(p) as f: 
        return [json.loads(l) for l in f if l.strip()]

def load_lingxi_text(case_id):
    """Load Lingxi case text (cleaned_text from parquet)."""
    import pandas as pd
    fp = REPO / "data/raw/lingxidiag16k/data/validation-00000-of-00001.parquet"
    if not hasattr(load_lingxi_text, "_cache"):
        df = pd.read_parquet(fp)
        load_lingxi_text._cache = {str(r["patient_id"]): r["cleaned_text"] for _, r in df.iterrows()}
    return load_lingxi_text._cache.get(str(case_id), "")

def load_mdd_text(case_id):
    fp = REPO / f"data/raw/mdd5k_repo/MDD_5k/{case_id}.json"
    if not fp.exists(): return ""
    try:
        data = json.loads(fp.read_text())
    except Exception: return ""
    turns = []
    if isinstance(data, list):
        for blk in data:
            conv = blk.get("conversation", []) if isinstance(blk, dict) else []
            for t in conv:
                d = t.get("doctor",""); p = t.get("patient","")
                if d: turns.append(f"医生：{d}")
                if p: turns.append(f"患者：{p}")
    return "\n".join(turns)

def get_case_text(rec, dataset):
    cid = str(rec["case_id"])
    if dataset == "lingxidiag16k":
        return load_lingxi_text(cid)
    elif "mdd" in dataset:
        return load_mdd_text(cid)
    return ""

def truncate_text(text, max_chars=4000):
    if len(text) <= max_chars: return text
    return text[:max_chars//2] + "\n...[truncated]...\n" + text[-max_chars//3:]

def call_llm(messages, model, max_tokens=400, temperature=0.0):
    payload = {
        "model": model, "messages": messages,
        "temperature": temperature, "top_p": 1.0, "max_tokens": max_tokens,
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(f"{VLLM_BASE}/chat/completions", data=body, headers={"Content-Type": "application/json"})
    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                d = json.loads(resp.read().decode())
            return d["choices"][0]["message"]["content"], d["choices"][0].get("finish_reason")
        except Exception as e:
            last_err = e
            time.sleep(2 + attempt)
    return f"ERROR: {last_err}", "error"

def parse_json_from_text(text):
    """Extract JSON object from LLM response (handles ```json blocks etc)."""
    import re
    m = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if not m: return None
    try: return json.loads(m.group())
    except Exception: return None


# ===== B1a — Two-diagnostician Borda ensemble =====

def borda_combine(rank_a, rank_b):
    """Combine two ranked lists via Borda count (top of each gets max points)."""
    scores = defaultdict(float)
    for i, c in enumerate(rank_a or []):
        scores[base_code(c)] += (5 - i) * 1.0
    for i, c in enumerate(rank_b or []):
        scores[base_code(c)] += (5 - i) * 1.0
    return sorted(scores.keys(), key=lambda c: -scores[c])

def run_b1a(qwen3_preds_path, x_preds_path, out_path, model_x):
    """B1a: Borda ensemble — both Qwen3 and X ran independently as Diagnostician.
    Inputs are two prediction files."""
    q_recs = load_jsonl(qwen3_preds_path)
    x_recs = load_jsonl(x_preds_path)
    x_by_id = {str(r["case_id"]): r for r in x_recs}
    out_recs = []
    for q in q_recs:
        cid = str(q["case_id"])
        x = x_by_id.get(cid)
        if not x:
            out_recs.append(q); continue
        rank_q = q.get("decision_trace", {}).get("diagnostician_ranked", [])
        rank_x = x.get("decision_trace", {}).get("diagnostician_ranked", [])
        combined = borda_combine(rank_q, rank_x)
        new_primary = combined[0] if combined else q.get("primary_diagnosis")
        out = dict(q)
        out["primary_diagnosis"] = new_primary
        out["comorbid_diagnoses"] = []
        out.setdefault("decision_trace", {})["b1a_combined_ranked"] = combined
        out["decision_trace"]["b1a_qwen3_ranked"] = rank_q
        out["decision_trace"]["b1a_x_ranked"] = rank_x
        out["decision_trace"]["b1a_x_model"] = model_x
        out_recs.append(out)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for r in out_recs: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[b1a] wrote {len(out_recs)} to {out_path}")


# ===== B1b — Comorbidity specialist =====

B1B_PROMPT = """You are a clinical comorbidity specialist. Given a patient case and a primary diagnosis,
your ONLY task is to decide whether the patient has a SECOND, INDEPENDENT psychiatric disorder
that requires its own treatment beyond what the primary covers.

CASE:
{case_text}

Primary diagnosis already determined: {primary}

The diagnostic pipeline has confirmed these candidate codes via criterion-checking: {confirmed}

Default to "no comorbid" unless the case shows clear, independent symptoms beyond what the primary explains.

Respond in this exact JSON format:
{{
  "comorbid": "<single ICD code, MUST be one of {pair_options}>" or null,
  "reason": "<≤30字 justification>"
}}

/no_think"""

def run_b1b(qwen3_preds_path, dataset, out_path, model_x):
    q_recs = load_jsonl(qwen3_preds_path)
    out_recs = []
    n_emit = 0
    for i, q in enumerate(q_recs):
        cid = str(q["case_id"])
        primary = q.get("primary_diagnosis", "")
        primary_b = base_code(primary)
        pair_options = DOMAIN_PAIRS.get(primary_b, [])
        if not pair_options:
            # No valid pair — default no comorbid
            out = dict(q); out["comorbid_diagnoses"] = []
            out_recs.append(out); continue
        case_text = truncate_text(get_case_text(q, dataset))
        if not case_text:
            out = dict(q); out["comorbid_diagnoses"] = []
            out_recs.append(out); continue
        confirmed = q.get("decision_trace", {}).get("logic_engine_confirmed_codes", [])
        prompt = B1B_PROMPT.format(case_text=case_text, primary=primary, confirmed=confirmed, pair_options=pair_options)
        text, fr = call_llm([{"role": "user", "content": prompt}], model_x, max_tokens=200)
        parsed = parse_json_from_text(text) or {}
        c = parsed.get("comorbid")
        comorbid_emit = []
        if isinstance(c, str) and c.strip().lower() not in ("null", "none", ""):
            cb = base_code(c.strip())
            if cb in pair_options:
                comorbid_emit = [c.strip()]
                n_emit += 1
        out = dict(q)
        out["comorbid_diagnoses"] = comorbid_emit
        out.setdefault("decision_trace", {})["b1b_x_response"] = text[:300]
        out["decision_trace"]["b1b_x_model"] = model_x
        out_recs.append(out)
        if (i+1) % 50 == 0:
            print(f"[b1b] {i+1}/{len(q_recs)} processed, emit so far: {n_emit}")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for r in out_recs: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[b1b] wrote {len(out_recs)} to {out_path}, total emits: {n_emit}/{len(out_recs)}")


# ===== B2 — Replace checker (partial replay) =====

B2_CHECKER_PROMPT = """You are a clinical criterion-checker for ICD-10 disorder {disorder_code} ({disorder_name}).

CASE:
{case_text}

For the candidate disorder {disorder_code}, evaluate which criteria are met.
The standard criteria for {disorder_code} are conventionally:
- A: core symptom present ≥2 weeks
- B: at least 2 secondary symptoms
- C: functional impairment present
- D: not better explained by another disorder

Respond in this exact JSON format:
{{
  "met_count": <integer 0-4>,
  "total": 4,
  "met_ratio": <met_count/4 as decimal>,
  "criteria": [
    {{"id": "A", "status": "met|not_met|insufficient_evidence", "confidence": <0-1>}},
    {{"id": "B", "status": "...", "confidence": ...}},
    {{"id": "C", "status": "...", "confidence": ...}},
    {{"id": "D", "status": "...", "confidence": ...}}
  ]
}}

/no_think"""

DISORDER_NAMES = {
    "F20": "schizophrenia", "F31": "bipolar", "F32": "depressive episode",
    "F33": "recurrent depression", "F39": "mood disorder NOS",
    "F41.0": "panic disorder", "F41.1": "GAD", "F41.2": "mixed anx-dep",
    "F42": "OCD", "F43.1": "PTSD", "F43.2": "adjustment", "F45": "somatic",
    "F51": "non-organic sleep", "F98": "childhood behavior", "Z71": "counseling",
}

def run_b2(qwen3_preds_path, dataset, out_path, model_x):
    """B2: Replace Checker — for each case, re-run criterion check on Qwen3's top-5 with model X."""
    q_recs = load_jsonl(qwen3_preds_path)
    out_recs = []
    for i, q in enumerate(q_recs):
        cid = str(q["case_id"])
        case_text = truncate_text(get_case_text(q, dataset))
        if not case_text:
            out_recs.append(q); continue
        ranked = q.get("decision_trace", {}).get("diagnostician_ranked", [])[:5]
        new_checker_outputs = []
        new_confirmed = []
        for code in ranked:
            prompt = B2_CHECKER_PROMPT.format(
                disorder_code=code,
                disorder_name=DISORDER_NAMES.get(base_code(code), code),
                case_text=case_text,
            )
            text, fr = call_llm([{"role": "user", "content": prompt}], model_x, max_tokens=300)
            parsed = parse_json_from_text(text) or {}
            mc = int(parsed.get("met_count", 0)) if isinstance(parsed.get("met_count"), (int, float)) else 0
            mr = float(parsed.get("met_ratio", mc/4.0))
            new_checker_outputs.append({"disorder_code": code, "met_count": mc, "met_ratio": mr})
            if mr >= 1.0 or mc >= 4:  # confirmed threshold
                new_confirmed.append(code)
        # Apply BETA-2b primary-only on new confirmed_codes (rank-0 stays Qwen3's)
        primary = ranked[0] if ranked else q.get("primary_diagnosis")
        out = dict(q)
        out["primary_diagnosis"] = primary
        out["comorbid_diagnoses"] = []
        out.setdefault("decision_trace", {})["b2_x_checker_outputs"] = new_checker_outputs
        out["decision_trace"]["b2_x_confirmed_codes"] = new_confirmed
        out["decision_trace"]["b2_x_model"] = model_x
        out["decision_trace"]["logic_engine_confirmed_codes"] = new_confirmed  # overlay for post-hoc replay
        out_recs.append(out)
        if (i+1) % 25 == 0:
            print(f"[b2] {i+1}/{len(q_recs)}")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for r in out_recs: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[b2] wrote {len(out_recs)} to {out_path}")


# ===== B3a — Primary-fix agent =====

B3A_PROMPT = """You are a senior psychiatrist reviewing the diagnostic pipeline's tentative primary diagnosis.

CASE:
{case_text}

Pipeline output:
- Diagnostician's ranked candidates: {ranked}
- Criterion-checker confirmed disorders (those with ≥4/4 criteria met): {confirmed}
- Pipeline's tentative primary: {primary}

Question: is the tentative primary correct, or should it be revised to a different candidate from the top-3?

Respond in this exact JSON:
{{
  "revised_primary": "<ICD code from top-3>",
  "changed": <true|false>,
  "reason": "<≤30字>"
}}

/no_think"""

def run_b3a(qwen3_preds_path, dataset, out_path, model_x):
    q_recs = load_jsonl(qwen3_preds_path)
    out_recs = []
    n_changed = 0
    for i, q in enumerate(q_recs):
        case_text = truncate_text(get_case_text(q, dataset))
        if not case_text:
            out_recs.append(q); continue
        ranked = q.get("decision_trace", {}).get("diagnostician_ranked", [])[:5]
        confirmed = q.get("decision_trace", {}).get("logic_engine_confirmed_codes", [])
        primary = q.get("primary_diagnosis", ranked[0] if ranked else "")
        prompt = B3A_PROMPT.format(case_text=case_text, ranked=ranked, confirmed=confirmed, primary=primary)
        text, fr = call_llm([{"role": "user", "content": prompt}], model_x, max_tokens=200)
        parsed = parse_json_from_text(text) or {}
        rp = parsed.get("revised_primary")
        new_primary = primary
        if isinstance(rp, str) and rp.strip() in ranked[:3]:
            new_primary = rp.strip()
            if new_primary != primary: n_changed += 1
        out = dict(q)
        out["primary_diagnosis"] = new_primary
        out["comorbid_diagnoses"] = []
        out.setdefault("decision_trace", {})["b3a_x_response"] = text[:300]
        out["decision_trace"]["b3a_x_model"] = model_x
        out_recs.append(out)
        if (i+1) % 50 == 0:
            print(f"[b3a] {i+1}/{len(q_recs)} processed, changes so far: {n_changed}")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for r in out_recs: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[b3a] wrote {len(out_recs)} to {out_path}, changed: {n_changed}")


# ===== B3b — Meta-reasoning, no transcript =====

B3B_PROMPT = """You are a meta-reasoning agent. You have NO ACCESS to the patient's case description.
You see ONLY structured signals already extracted by other agents.

Diagnostician (LLM) ranked the candidates as:
  rank-1: {r1}
  rank-2: {r2}
  rank-3: {r3}
  rank-4: {r4}
  rank-5: {r5}

Criterion-checker met ratios (per disorder, 0-1+):
{met_ratios}

Logic engine confirmed disorders (≥4/4 criteria met): {confirmed}

Top-3 reasoning notes from the Diagnostician (≤30 chars each):
{reasoning}

Based on these aggregated signals only, decide the most likely primary diagnosis.
You may pick any code from the Diagnostician's top-5.

Respond in this exact JSON:
{{
  "primary": "<ICD code from top-5>",
  "reason": "<≤30字, signal-based justification>"
}}

/no_think"""

def run_b3b(qwen3_preds_path, out_path, model_x):
    q_recs = load_jsonl(qwen3_preds_path)
    out_recs = []
    n_changed = 0
    for i, q in enumerate(q_recs):
        ranked = q.get("decision_trace", {}).get("diagnostician_ranked", [])[:5]
        if len(ranked) < 1:
            out_recs.append(q); continue
        # Pad to 5
        rp = ranked + ["(none)"] * (5 - len(ranked))
        confirmed = q.get("decision_trace", {}).get("logic_engine_confirmed_codes", [])
        rco = q.get("decision_trace", {}).get("raw_checker_outputs", [])
        met_ratios = "\n".join([f"  {x['disorder_code']}: {x.get('met_ratio', 0):.2f}" for x in rco])
        reasoning = q.get("decision_trace", {}).get("diagnostician_reasoning", [])[:3]
        reasoning_str = "\n".join([f"  {ranked[i] if i < len(ranked) else '?'}: {r}" for i, r in enumerate(reasoning)])
        prompt = B3B_PROMPT.format(
            r1=rp[0], r2=rp[1], r3=rp[2], r4=rp[3], r5=rp[4],
            met_ratios=met_ratios, confirmed=confirmed, reasoning=reasoning_str,
        )
        text, fr = call_llm([{"role": "user", "content": prompt}], model_x, max_tokens=200)
        parsed = parse_json_from_text(text) or {}
        rp_pick = parsed.get("primary")
        primary = q.get("primary_diagnosis", ranked[0])
        new_primary = primary
        if isinstance(rp_pick, str) and rp_pick.strip() in ranked:
            new_primary = rp_pick.strip()
            if new_primary != primary: n_changed += 1
        out = dict(q)
        out["primary_diagnosis"] = new_primary
        out["comorbid_diagnoses"] = []
        out.setdefault("decision_trace", {})["b3b_x_response"] = text[:300]
        out["decision_trace"]["b3b_x_model"] = model_x
        out_recs.append(out)
        if (i+1) % 50 == 0:
            print(f"[b3b] {i+1}/{len(q_recs)} processed, changes so far: {n_changed}")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for r in out_recs: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[b3b] wrote {len(out_recs)} to {out_path}, changed: {n_changed}")


# ===== Main =====

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--method", required=True, choices=["b1a", "b1b", "b2", "b3a", "b3b"])
    p.add_argument("--qwen3-preds", required=True, help="Qwen3 predictions.jsonl path")
    p.add_argument("--x-preds", default=None, help="X predictions.jsonl (only for b1a)")
    p.add_argument("--dataset", default="lingxidiag16k", help="Dataset name (for case text loading)")
    p.add_argument("--model-x", required=True, help="Model X HF id (used as label, served by current vLLM)")
    p.add_argument("--out", required=True, help="Output predictions.jsonl path")
    args = p.parse_args()

    if args.method == "b1a":
        if not args.x_preds:
            sys.exit("--x-preds required for b1a")
        run_b1a(args.qwen3_preds, args.x_preds, args.out, args.model_x)
    elif args.method == "b1b":
        run_b1b(args.qwen3_preds, args.dataset, args.out, args.model_x)
    elif args.method == "b2":
        run_b2(args.qwen3_preds, args.dataset, args.out, args.model_x)
    elif args.method == "b3a":
        run_b3a(args.qwen3_preds, args.dataset, args.out, args.model_x)
    elif args.method == "b3b":
        run_b3b(args.qwen3_preds, args.out, args.model_x)


if __name__ == "__main__":
    main()
