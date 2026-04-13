"""Unified multi-backbone evaluation for CultureDx DtV.

Supports: anthropic, openai, deepseek, gemini, vllm, cerebras, sambanova (local)
Runs: Single + DtV + dedicated 2c/4c → Full Table 4

Usage:
  python scripts/run_api_backbone.py \
    --provider anthropic --model claude-sonnet-4-6 \
    --max-cases 200 --output-dir outputs/ceiling/claude-sonnet
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from culturedx.data.adapters.lingxidiag16k import LingxiDiag16kAdapter
from culturedx.eval.lingxidiag_paper import (
    PAPER_2_CLASSES,
    PAPER_4_CLASSES,
    PAPER_12_CLASSES,
    classify_2class_from_raw,
    classify_2class_prediction,
    classify_4class_from_raw,
    compute_singlelabel_metrics,
    compute_multilabel_metrics,
    gold_to_parent_list,
    pred_to_parent_list,
    to_paper_parent,
)
from culturedx.llm.json_utils import extract_json_from_response

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("api_backbone")

# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPT_DIR = PROJECT_ROOT / "prompts"

jinja_env = Environment(
    loader=FileSystemLoader([
        str(PROMPT_DIR / "agents"),
        str(PROMPT_DIR / "single"),
        str(PROMPT_DIR / "paper_static"),
    ]),
    keep_trailing_newline=True,
)

# Disorder names for diagnostician prompt
DISORDER_NAMES = {
    "F20": "精神分裂症",
    "F22": "持久性妄想性障碍",
    "F31": "双相情感障碍",
    "F32": "抑郁发作",
    "F33": "复发性抑郁障碍",
    "F39": "未特指的心境障碍",
    "F40": "恐惧性焦虑障碍",
    "F41.0": "惊恐障碍",
    "F41.1": "广泛性焦虑障碍",
    "F42": "强迫症",
    "F43.1": "创伤后应激障碍",
    "F43.2": "适应障碍",
    "F45": "躯体形式障碍",
    "F51": "非器质性睡眠障碍",
    "F98": "其他行为和情绪障碍",
    "Z71": "咨询",
}

PROVIDER_CONFIG = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
        "sdk": "openai",
        "max_concurrent": 20,
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "api_key_env": "CEREBRAS_API_KEY",
        "default_model": "llama-3.3-70b",
        "sdk": "openai",
        "max_concurrent": 5,
    },
    "sambanova": {
        "base_url": "https://api.sambanova.ai/v1",
        "api_key_env": "SAMBANOVA_API_KEY",
        "default_model": "Meta-Llama-3.3-70B-Instruct",
        "sdk": "openai",
        "max_concurrent": 5,
    },
    "gemini": {
        "base_url": None,
        "api_key_env": "GEMINI_API_KEY",
        "default_model": "gemini-2.5-flash",
        "sdk": "google",
        "max_concurrent": 3,
    },
    "anthropic": {
        "base_url": None,
        "api_key_env": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-6",
        "sdk": "anthropic",
        "max_concurrent": 5,
    },
    "openai": {
        "base_url": None,
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "gpt-5.4",
        "sdk": "openai",
        "max_concurrent": 5,
    },
    "vllm": {
        "base_url": "http://localhost:8000/v1",
        "api_key_env": None,
        "default_model": "auto",
        "sdk": "openai",
        "max_concurrent": 8,
    },
    "claude-cli": {
        "base_url": None,
        "api_key_env": None,
        "default_model": "sonnet",
        "sdk": "cli",
        "max_concurrent": 4,
    },
    "codex-cli": {
        "base_url": None,
        "api_key_env": None,
        "default_model": "gpt-5.4",
        "sdk": "cli",
        "max_concurrent": 2,
    },
}

# Target disorders for triage → diagnostician → checker
TARGET_DISORDERS = [
    "F20", "F31", "F32", "F39", "F41.0", "F41.1",
    "F42", "F43.1", "F43.2", "F45", "F51", "F98",
]

# Triage category → disorder code mapping
TRIAGE_TO_DISORDERS = {
    "mood": ["F31", "F32", "F39"],
    "anxiety": ["F41.0", "F41.1", "F42"],
    "stress": ["F43.1", "F43.2"],
    "somatoform": ["F45"],
    "psychotic": ["F20"],
    "sleep": ["F51"],
}


def render_prompt(template_name: str, **kwargs) -> str:
    tmpl = jinja_env.get_template(template_name)
    return tmpl.render(**kwargs)


# ---------------------------------------------------------------------------
# LLM Provider Abstraction
# ---------------------------------------------------------------------------

class LLMProvider:
    def __init__(
        self,
        provider: str,
        model: str,
        base_url: str | None = None,
        api_key: str | None = None,
        max_concurrent: int = 4,
        reasoning_effort: str | None = None,
    ):
        self.provider = provider
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.reasoning_effort = reasoning_effort
        self.max_concurrent = max_concurrent
        self.call_count = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self._client = None

    def _get_openai_client(self):
        if self._client is None:
            from openai import OpenAI
            cfg = PROVIDER_CONFIG.get(self.provider, {})
            base = self.base_url or cfg.get("base_url")
            kwargs = {}
            if base:
                kwargs["base_url"] = base
            if self.api_key:
                kwargs["api_key"] = self.api_key
            else:
                env_key = cfg.get("api_key_env")
                if env_key:
                    kwargs["api_key"] = os.environ.get(env_key, "")
                elif self.provider == "vllm":
                    kwargs["api_key"] = "not-needed"
            self._client = OpenAI(**kwargs)
        return self._client

    def call(self, system_prompt: str, user_prompt: str, max_retries: int = 3) -> str:
        self.call_count += 1
        for attempt in range(max_retries):
            try:
                return self._call_once(system_prompt, user_prompt)
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    logger.warning("LLM call failed (attempt %d/%d): %s. Retrying in %ds",
                                   attempt + 1, max_retries, e, wait)
                    time.sleep(wait)
                else:
                    logger.error("LLM call failed after %d attempts: %s", max_retries, e)
                    raise

    def _call_once(self, system_prompt: str, user_prompt: str) -> str:
        if self.provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key) if self.api_key else anthropic.Anthropic()
            resp = client.messages.create(
                model=self.model,
                max_tokens=2048,
                temperature=0.0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            self.input_tokens += resp.usage.input_tokens
            self.output_tokens += resp.usage.output_tokens
            return resp.content[0].text

        elif self.provider in ("openai", "deepseek", "vllm", "cerebras", "sambanova"):
            client = self._get_openai_client()
            extra = {}
            if self.provider == "vllm":
                extra["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
            resp = client.chat.completions.create(
                model=self.model,
                max_tokens=2048,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                **extra,
            )
            if resp.usage:
                self.input_tokens += resp.usage.prompt_tokens or 0
                self.output_tokens += resp.usage.completion_tokens or 0
            return resp.choices[0].message.content

        elif self.provider == "gemini":
            import google.generativeai as genai
            key = self.api_key or os.environ.get("GOOGLE_API_KEY", "")
            genai.configure(api_key=key)
            model = genai.GenerativeModel(
                self.model, system_instruction=system_prompt
            )
            resp = model.generate_content(
                user_prompt,
                generation_config={"temperature": 0, "max_output_tokens": 2048},
            )
            return resp.text

        elif self.provider == "claude-cli":
            env = os.environ.copy()
            env.pop("CLAUDECODE", None)
            combined = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
            proc = subprocess.run(
                ["claude", "-p", "--model", self.model,
                 "--output-format", "text", "--no-session-persistence"],
                input=combined, env=env, capture_output=True, text=True, timeout=180,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"claude-cli error: {proc.stderr[:500]}")
            return proc.stdout.strip()

        elif self.provider == "codex-cli":
            combined = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
            proc = subprocess.run(
                ["codex", "exec", "-m", self.model]
                + (["-c", f'model_reasoning_effort="{self.reasoning_effort}"'] if self.reasoning_effort else [])
                + ["-"],
                input=combined, capture_output=True, text=True, timeout=180,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"codex-cli error: {proc.stderr[:500]}")
            # Parse codex exec output: last non-empty line before "tokens used" is the response
            lines = proc.stdout.strip().split("\n")
            # Find content between "codex\n" marker and "tokens used"
            response_lines = []
            in_response = False
            for line in lines:
                if line.strip() == "codex":
                    in_response = True
                    continue
                if line.strip().startswith("tokens used"):
                    break
                if in_response:
                    response_lines.append(line)
            if response_lines:
                return "\n".join(response_lines).strip()
            # Fallback: return last non-empty line
            for line in reversed(lines):
                if line.strip():
                    return line.strip()
            return proc.stdout.strip()

        raise ValueError(f"Unknown provider: {self.provider}")

    def cost_estimate(self) -> float:
        """Rough USD cost estimate."""
        rates = {
            "claude-opus-4-6": (15.0, 75.0),
            "claude-sonnet-4-6": (3.0, 15.0),
            "claude-haiku-4-5": (0.80, 4.0),
            "gpt-5.4": (2.50, 10.0),
            "deepseek-chat": (0.27, 1.10),
            "gemini-2.5-flash": (0.15, 0.60),
            "sonnet": (3.0, 15.0),
            "opus": (15.0, 75.0),
            "haiku": (0.80, 4.0),
        }
        in_rate, out_rate = rates.get(self.model, (1.0, 5.0))
        return (self.input_tokens * in_rate + self.output_tokens * out_rate) / 1_000_000


# ---------------------------------------------------------------------------
# Transcript builder
# ---------------------------------------------------------------------------

def build_transcript(case_dict: dict, max_chars: int = 20000) -> str:
    """Build transcript text from case dict (LingxiDiag16k format)."""
    convos = case_dict.get("Conversation", [])
    if isinstance(convos, str):
        return convos[:max_chars]
    lines = []
    for turn in convos:
        if isinstance(turn, dict):
            speaker = turn.get("speaker", turn.get("role", "Unknown"))
            text = turn.get("text", turn.get("content", ""))
            lines.append(f"{speaker}: {text}")
        elif isinstance(turn, str):
            lines.append(turn)
    full = "\n".join(lines)
    if len(full) <= max_chars:
        return full
    half = max_chars // 2
    return full[:half] + "\n\n[... 中间部分省略 ...]\n\n" + full[-half:]


# ---------------------------------------------------------------------------
# Pipeline: Single 12-class
# ---------------------------------------------------------------------------

def run_single_12class(provider: LLMProvider, transcript: str) -> list[str]:
    """Zero-shot 12-class diagnosis."""
    prompt = render_prompt("zero_shot_zh.jinja", transcript_text=transcript[:12000])
    raw = provider.call("", prompt)
    return _parse_single_response(raw)


def _parse_single_response(raw: str) -> list[str]:
    parsed = extract_json_from_response(raw)
    if not parsed or not isinstance(parsed, dict):
        return ["Others"]
    primary = parsed.get("primary_diagnosis", "")
    comorbid = parsed.get("comorbid_diagnoses", [])
    if isinstance(comorbid, str):
        comorbid = [comorbid]
    codes = [primary] + [c for c in comorbid if c]
    return pred_to_parent_list(codes)


# ---------------------------------------------------------------------------
# Pipeline: DtV (Triage → Diagnostician → Checker → Decision)
# ---------------------------------------------------------------------------

def run_triage(provider: LLMProvider, transcript: str) -> list[str]:
    """Triage to narrow candidate disorders."""
    prompt = render_prompt(
        "triage_zh.jinja",
        transcript_text=transcript[:12000],
        chief_complaint=None,
        age=None,
        gender=None,
        evidence_summary=None,
    )
    raw = provider.call("", prompt)
    parsed = extract_json_from_response(raw)
    if not parsed or not isinstance(parsed, dict):
        return TARGET_DISORDERS  # fallback: all

    categories = parsed.get("categories", [])
    codes = []
    seen = set()
    for cat in sorted(categories, key=lambda c: -c.get("confidence", 0) if isinstance(c, dict) else 0):
        if not isinstance(cat, dict):
            continue
        cat_name = cat.get("category", "")
        for code in TRIAGE_TO_DISORDERS.get(cat_name, []):
            if code not in seen:
                seen.add(code)
                codes.append(code)

    # Always include F32, F41.1, F98 as common
    for fallback in ["F32", "F41.1", "F98"]:
        if fallback not in seen:
            codes.append(fallback)

    return codes if codes else TARGET_DISORDERS


def run_diagnostician(
    provider: LLMProvider, transcript: str, candidate_codes: list[str]
) -> list[str]:
    """Diagnostician: rank candidates by clinical likelihood."""
    prompt = render_prompt(
        "diagnostician_zh.jinja",
        transcript_text=transcript[:20000],
        candidate_disorders=candidate_codes,
        disorder_names=DISORDER_NAMES,
    )
    raw = provider.call("", prompt)
    parsed = extract_json_from_response(raw)
    if not parsed or not isinstance(parsed, dict):
        return candidate_codes[:3]

    ranked = parsed.get("ranked_diagnoses", [])
    if isinstance(ranked, str):
        ranked = []
    codes = []
    for entry in ranked:
        code = entry.get("code", "") if isinstance(entry, dict) else str(entry)
        if code and code not in codes:
            codes.append(code)
    return codes if codes else candidate_codes[:3]


def run_checker(
    provider: LLMProvider, transcript: str, disorder_code: str
) -> tuple[bool, dict]:
    """Criterion checker: verify one disorder. Returns (confirmed, criteria_output)."""
    # Load criteria from ontology
    criteria = _load_criteria(disorder_code)
    if not criteria:
        return False, {}

    prompt = render_prompt(
        "criterion_checker_zh.jinja",
        disorder_code=disorder_code,
        disorder_name=DISORDER_NAMES.get(disorder_code, disorder_code),
        transcript_text=transcript[:20000],
        criteria=criteria,
        evidence_summary=None,
    )
    raw = provider.call("", prompt)
    parsed = extract_json_from_response(raw)
    if not parsed or not isinstance(parsed, dict):
        return False, {}

    criteria_results = parsed.get("criteria", [])
    met_count = sum(1 for c in criteria_results if isinstance(c, dict) and c.get("status") == "met")
    total = len(criteria_results)

    # Simple threshold: >50% criteria met → confirmed
    confirmed = met_count > total * 0.5 if total > 0 else False
    return confirmed, {"met": met_count, "total": total, "results": criteria_results}


_CRITERIA_CACHE = None

def _load_criteria(disorder_code: str) -> dict:
    """Load ICD-10 criteria for a disorder."""
    global _CRITERIA_CACHE
    if _CRITERIA_CACHE is None:
        criteria_path = PROJECT_ROOT / "src" / "culturedx" / "ontology" / "data" / "icd10_criteria.json"
        try:
            with open(criteria_path, encoding="utf-8") as f:
                _CRITERIA_CACHE = json.load(f)
        except FileNotFoundError:
            logger.warning("Criteria file not found: %s", criteria_path)
            return {}

    disorders = _CRITERIA_CACHE.get("disorders", {})
    if isinstance(disorders, dict):
        disorder = disorders.get(disorder_code, {})
    else:
        # Legacy list format
        disorder = next((d for d in disorders if isinstance(d, dict) and d.get("code") == disorder_code), {})
    if not disorder:
        return {}
    criteria = {}
    for c in disorder.get("criteria", []):
        if not isinstance(c, dict):
            continue
        cid = c.get("id", c.get("criterion_id", ""))
        criteria[cid] = {
            "type": c.get("type", ""),
            "text_zh": c.get("text_zh", c.get("description_zh", c.get("text", ""))),
        }
    return criteria


# ---------------------------------------------------------------------------
# Ablation: RareClassSpecialist
# ---------------------------------------------------------------------------

RARE_SPECIALIST_PROMPT = """你是一位资深精神科会诊医生。初诊医生已判断该患者的主诊断为 {primary_code}。

请仔细审查对话记录，判断是否应改为以下少见诊断之一：
- F39（未特指心境障碍）：心境障碍但资料不足以明确
- F51（非器质性睡眠障碍）：主诉是失眠/嗜睡（非伴随症状）
- F98（儿童青少年行为障碍）：未成年人发育期行为问题
- Z71（咨询）：寻求心理咨询/生活指导
- F20（精神分裂症）：持续性妄想、幻听、思维破裂
- F31（双相情感障碍）：有躁狂/轻躁狂发作证据
- F42（强迫症）：反复侵入性思维和/或强迫行为
- F43（应激相关障碍）：症状与近期创伤/应激事件相关
- F45（躯体形式障碍）：反复躯体症状无器质性原因

对话记录：
{transcript}

如果应改判，输出：{{"override": true, "new_code": "ICD代码"}}
如果维持原判断，输出：{{"override": false}}
仅输出JSON。"""


def run_rare_specialist(
    provider: LLMProvider, transcript: str, primary_code: str
) -> str | None:
    """Call rare-class specialist. Returns override code or None."""
    prompt = RARE_SPECIALIST_PROMPT.format(
        primary_code=primary_code, transcript=transcript[:20000]
    )
    raw = provider.call("", prompt)
    parsed = extract_json_from_response(raw)
    if parsed and isinstance(parsed, dict) and parsed.get("override"):
        new_code = parsed.get("new_code", "")
        if new_code:
            logger.info("RareSpecialist override: %s -> %s", primary_code, new_code)
            return new_code
    return None


# ---------------------------------------------------------------------------
# Ablation: Ensemble Diagnostician (Borda count)
# ---------------------------------------------------------------------------

def ensemble_diagnostician(
    rankings_a: list[str], rankings_b: list[str]
) -> list[str]:
    """Merge two diagnostician rankings using Borda count."""
    scores: dict[str, int] = {}
    n = max(len(rankings_a), len(rankings_b))
    for rank, code in enumerate(rankings_a):
        scores[code] = scores.get(code, 0) + (n - rank)
    for rank, code in enumerate(rankings_b):
        scores[code] = scores.get(code, 0) + (n - rank)
    merged = sorted(scores, key=lambda c: -scores[c])
    return merged


def run_dtv_12class(
    provider: LLMProvider,
    transcript: str,
    skip_triage: bool = False,
    rare_specialist: bool = False,
    checker_provider: LLMProvider | None = None,
    ensemble_provider: LLMProvider | None = None,
) -> tuple[list[str], dict]:
    """Full DtV pipeline. Returns (predictions, trace)."""
    trace = {}

    # Step 1: Triage (optional)
    if skip_triage:
        triage_codes = TARGET_DISORDERS
        trace["triage"] = "skipped"
    else:
        triage_codes = run_triage(provider, transcript)
        trace["triage"] = triage_codes

    # Step 2: Diagnostician ranking (with optional ensemble)
    ranked = run_diagnostician(provider, transcript, triage_codes)
    trace["diagnostician_ranked"] = ranked

    if ensemble_provider is not None:
        ranked_b = run_diagnostician(ensemble_provider, transcript, triage_codes)
        trace["diagnostician_ranked_b"] = ranked_b
        ranked = ensemble_diagnostician(ranked, ranked_b)
        trace["diagnostician_ensemble"] = ranked

    # Step 2.5: RareClassSpecialist (optional)
    if rare_specialist and ranked:
        top1_code = ranked[0]
        # Only trigger for over-represented classes
        if to_paper_parent(top1_code) in ("F32", "F41"):
            override = run_rare_specialist(provider, transcript, top1_code)
            if override:
                trace["rare_specialist"] = {"from": top1_code, "to": override}
                # Insert override as new top-1
                ranked = [override] + [c for c in ranked if c != override]
            else:
                trace["rare_specialist"] = {"from": top1_code, "to": None}

    # Step 3: Checker verification (top-2)
    ck_provider = checker_provider if checker_provider is not None else provider
    top2 = ranked[:2]
    checker_results = {}
    confirmed = []
    for code in top2:
        ok, details = run_checker(ck_provider, transcript, code)
        checker_results[code] = {"confirmed": ok, **details}
        if ok:
            confirmed.append(code)
    trace["checker"] = checker_results
    trace["confirmed"] = confirmed

    # Step 4: Decision (same logic as hied.py DtV)
    top1 = ranked[0] if ranked else "Others"
    top2_code = ranked[1] if len(ranked) > 1 else None

    primary = top1
    comorbid: list[str] = []
    veto = False

    if top1 in confirmed:
        if top2_code and top2_code in confirmed:
            comorbid = [top2_code]
    elif top2_code and top2_code in confirmed:
        primary = top2_code
        veto = True
    # else: keep top1 as primary (unconfirmed)

    trace["primary"] = primary
    trace["comorbid"] = comorbid
    trace["veto"] = veto

    result = [to_paper_parent(primary)]
    for c in comorbid:
        p = to_paper_parent(c)
        if p not in result:
            result.append(p)
    return result if result else ["Others"], trace


# ---------------------------------------------------------------------------
# Pipeline: Dedicated 2c / 4c
# ---------------------------------------------------------------------------

def run_2class(provider: LLMProvider, transcript: str) -> str:
    prompt = render_prompt("binary_zh.jinja", transcript_text=transcript[:12000])
    raw = provider.call("", prompt)
    parsed = extract_json_from_response(raw)
    if parsed and isinstance(parsed, dict):
        diag = parsed.get("diagnosis", "")
        if diag in {"Depression", "Anxiety"}:
            return diag
    # Fallback: keyword search
    if "depression" in raw.lower() or "抑郁" in raw:
        return "Depression"
    if "anxiety" in raw.lower() or "焦虑" in raw:
        return "Anxiety"
    return "Other"


def run_4class(provider: LLMProvider, transcript: str) -> str:
    prompt = render_prompt("fourclass_zh.jinja", transcript_text=transcript[:12000])
    raw = provider.call("", prompt)
    parsed = extract_json_from_response(raw)
    if parsed and isinstance(parsed, dict):
        diag = parsed.get("diagnosis", "")
        if diag in {"Depression", "Anxiety", "Mixed", "Others"}:
            return diag
    return "Others"


def run_merged_2c4c(provider: LLMProvider, transcript: str) -> tuple[str, str]:
    """Merged 2-class + 4-class in one call. Returns (binary_pred, fourclass_pred)."""
    prompt = """你是一位经验丰富的精神科医生。请阅读以下对话后回答两个问题：

1. 二分类：该患者更可能患有抑郁症(Depression)还是焦虑症(Anxiety)？
2. 四分类：Depression / Anxiety / Mixed / Others

## 对话记录
""" + transcript[:12000] + """

## 输出要求
仅输出JSON：
{"binary": "Depression", "fourclass": "Mixed"}"""
    raw = provider.call("", prompt)
    parsed = extract_json_from_response(raw)
    if parsed and isinstance(parsed, dict):
        binary = parsed.get("binary", "Other")
        fourclass = parsed.get("fourclass", "Others")
        if binary not in {"Depression", "Anxiety"}:
            binary = "Other"
        if fourclass not in {"Depression", "Anxiety", "Mixed", "Others"}:
            fourclass = "Others"
        return binary, fourclass
    return "Other", "Others"


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------

def compute_full_table4(
    cases: list[dict],
    preds_12: list[list[str]],
    preds_2c: dict[int, str],
    preds_4c: list[str],
    mode: str,
) -> dict:
    """Compute full Table 4 from predictions."""
    import numpy as np

    gold_12, pred_12 = [], []
    gold_2, pred_2 = [], []
    gold_4, pred_4 = [], []

    for i, case in enumerate(cases):
        raw_code = str(case.get("DiagnosisCode", "") or "")

        # 12-class
        gold_parents = gold_to_parent_list(raw_code)
        gold_12.append(gold_parents)
        pred_12.append(preds_12[i])

        # 4-class
        gold_4_label = classify_4class_from_raw(raw_code)
        pred_p = preds_12[i][0] if preds_12[i] else "Others"
        pred_ps = set(preds_12[i])
        if "F32" in pred_ps and "F41" in pred_ps:
            pred_4_from_12 = "Mixed"
        elif pred_p == "F32":
            pred_4_from_12 = "Depression"
        elif pred_p == "F41":
            pred_4_from_12 = "Anxiety"
        else:
            pred_4_from_12 = "Others"
        gold_4.append(gold_4_label)
        # Use dedicated 4c if available, else fold from 12c
        pred_4.append(preds_4c[i] if preds_4c else pred_4_from_12)

        # 2-class
        gold_2_label = classify_2class_from_raw(raw_code)
        if gold_2_label is not None:
            if i in preds_2c:
                pred_2.append(preds_2c[i])
            else:
                pred_2.append(classify_2class_prediction(pred_p))
            gold_2.append(gold_2_label)

    m2 = compute_singlelabel_metrics(gold_2, pred_2, PAPER_2_CLASSES) if gold_2 else {}
    m4 = compute_singlelabel_metrics(gold_4, pred_4, PAPER_4_CLASSES)
    m12 = compute_multilabel_metrics(gold_12, pred_12, PAPER_12_CLASSES)

    table4 = {
        "2class_Acc": m2.get("accuracy"),
        "2class_F1_macro": m2.get("macro_f1"),
        "2class_F1_weighted": m2.get("weighted_f1"),
        "4class_Acc": m4.get("accuracy"),
        "4class_F1_macro": m4.get("macro_f1"),
        "4class_F1_weighted": m4.get("weighted_f1"),
        "12class_Acc": m12.get("accuracy"),
        "12class_Top1": m12.get("top1_accuracy"),
        "12class_Top3": m12.get("top3_accuracy"),
        "12class_F1_macro": m12.get("macro_f1"),
        "12class_F1_weighted": m12.get("weighted_f1"),
        "2class_n": m2.get("n", 0),
        "4class_n": m4.get("n", 0),
        "12class_n": m12.get("n", 0),
    }
    vals = [float(v) for k, v in table4.items() if not k.endswith("_n") and v is not None]
    table4["Overall"] = float(np.mean(vals)) if vals else None
    return table4


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------

def evaluate_backbone(
    provider: LLMProvider,
    cases: list[dict],
    max_cases: int,
    output_dir: Path,
    skip_single: bool = False,
    skip_dtv: bool = False,
    skip_triage: bool = False,
    start_case_index: int = 0,
    merge_2c4c: bool = False,
    rare_specialist: bool = False,
    checker_provider: LLMProvider | None = None,
    ensemble_provider: LLMProvider | None = None,
):
    output_dir.mkdir(parents=True, exist_ok=True)
    all_cases = cases[start_case_index:]
    eval_cases = all_cases[:max_cases] if max_cases > 0 else all_cases
    n = len(eval_cases)

    logger.info("Evaluating %s/%s on %d cases", provider.provider, provider.model, n)

    # Load checkpoint if exists
    checkpoint_path = output_dir / "checkpoint.jsonl"
    completed = _load_checkpoint(checkpoint_path)
    start_idx = len(completed)
    if start_idx > 0:
        logger.info("Resuming from checkpoint: %d/%d done", start_idx, n)

    results = completed
    results_lock = Lock()
    done_count = [start_idx]  # mutable counter for threads

    max_workers = min(provider.max_concurrent, 16)
    logger.info("Using %d concurrent workers", max_workers)

    def process_case(i):
        case = eval_cases[i]
        case_id = case.get("ConversationID", case.get("patient_id", i))
        transcript = build_transcript(case)
        t0 = time.time()

        result = {
            "case_index": i,
            "case_id": case_id,
            "DiagnosisCode": case.get("DiagnosisCode", ""),
        }

        # Single 12-class
        if not skip_single:
            try:
                single_pred = run_single_12class(provider, transcript)
            except Exception as e:
                logger.error("Case %d single failed: %s", i, e)
                single_pred = ["Others"]
            result["single_pred"] = single_pred

        # DtV 12-class
        if not skip_dtv:
            try:
                dtv_pred, dtv_trace = run_dtv_12class(
                    provider, transcript,
                    skip_triage=skip_triage,
                    rare_specialist=rare_specialist,
                    checker_provider=checker_provider,
                    ensemble_provider=ensemble_provider,
                )
            except Exception as e:
                logger.error("Case %d DtV failed: %s\n%s", i, e, traceback.format_exc())
                dtv_pred = ["Others"]
                dtv_trace = {"error": str(e)}
            result["dtv_pred"] = dtv_pred
            result["dtv_trace"] = dtv_trace

        # Dedicated 2c + 4c (merged or separate)
        if merge_2c4c:
            try:
                pred_2c_raw, pred_4c = run_merged_2c4c(provider, transcript)
            except Exception as e:
                logger.error("Case %d merged 2c4c failed: %s", i, e)
                pred_2c_raw, pred_4c = "Other", "Others"
            gold_2c = classify_2class_from_raw(str(case.get("DiagnosisCode", "") or ""))
            if gold_2c is not None:
                result["pred_2c"] = pred_2c_raw
                result["gold_2c"] = gold_2c
            result["pred_4c"] = pred_4c
        else:
            gold_2c = classify_2class_from_raw(str(case.get("DiagnosisCode", "") or ""))
            if gold_2c is not None:
                try:
                    pred_2c = run_2class(provider, transcript)
                except Exception as e:
                    logger.error("Case %d 2c failed: %s", i, e)
                    pred_2c = "Other"
                result["pred_2c"] = pred_2c
                result["gold_2c"] = gold_2c

            try:
                pred_4c = run_4class(provider, transcript)
            except Exception as e:
                logger.error("Case %d 4c failed: %s", i, e)
                pred_4c = "Others"
            result["pred_4c"] = pred_4c

        elapsed = time.time() - t0
        result["elapsed_sec"] = round(elapsed, 1)
        return i, result

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_case, i): i for i in range(start_idx, n)}
        pending_results = {}

        for future in as_completed(futures):
            idx, result = future.result()
            with results_lock:
                pending_results[idx] = result
                # Flush in order
                while done_count[0] in pending_results:
                    results.append(pending_results.pop(done_count[0]))
                    done_count[0] += 1
                completed_so_far = done_count[0]

                logger.info(
                    "[%d/%d] case=%s single=%s dtv=%s 2c=%s 4c=%s (%.1fs, $%.3f cumul)",
                    completed_so_far, n, result.get("case_id", "?"),
                    result.get("single_pred", "-"),
                    result.get("dtv_pred", "-"),
                    result.get("pred_2c", "-"),
                    result.get("pred_4c", "-"),
                    result.get("elapsed_sec", 0),
                    provider.cost_estimate(),
                )

                if completed_so_far % 10 == 0:
                    _save_checkpoint(results, checkpoint_path)

    # Final save
    _save_checkpoint(results, checkpoint_path)

    # Compute metrics
    _compute_and_save_metrics(results, eval_cases, provider, output_dir,
                              skip_single=skip_single, skip_dtv=skip_dtv)


def _compute_and_save_metrics(
    results: list[dict],
    eval_cases: list[dict],
    provider: LLMProvider,
    output_dir: Path,
    skip_single: bool = False,
    skip_dtv: bool = False,
):
    import numpy as np
    n = len(results)

    def collect(pred_key):
        preds_12 = [r.get(pred_key, ["Others"]) for r in results]
        preds_2c = {i: r["pred_2c"] for i, r in enumerate(results) if "pred_2c" in r}
        preds_4c = [r.get("pred_4c", "Others") for r in results]
        return compute_full_table4(eval_cases[:n], preds_12, preds_2c, preds_4c, pred_key)

    output = {
        "model": provider.model,
        "provider": provider.provider,
        "n_cases": n,
        "meta": {
            "total_calls": provider.call_count,
            "input_tokens": provider.input_tokens,
            "output_tokens": provider.output_tokens,
            "cost_estimate_usd": round(provider.cost_estimate(), 2),
        },
    }

    if not skip_single:
        output["single"] = collect("single_pred")
    if not skip_dtv:
        output["dtv"] = collect("dtv_pred")

    # Delta
    if "single" in output and "dtv" in output:
        delta = {}
        for k in output["single"]:
            if k.endswith("_n"):
                continue
            sv = output["single"].get(k)
            dv = output["dtv"].get(k)
            if sv is not None and dv is not None:
                delta[k] = round(dv - sv, 4)
        output["delta"] = delta

    # Save
    out_path = output_dir / "table4_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    logger.info("Saved results to %s", out_path)

    # Print summary
    _print_summary(output)


def _print_summary(output: dict):
    def fmt(v):
        return f"{v:.3f}" if v is not None else "N/A"

    print(f"\n{'='*70}")
    print(f"Model: {output['model']} ({output['provider']})")
    print(f"Cases: {output['n_cases']}")
    print(f"Calls: {output['meta']['total_calls']}, "
          f"Cost: ${output['meta']['cost_estimate_usd']:.2f}")
    print(f"{'='*70}")

    for mode in ["single", "dtv"]:
        m = output.get(mode)
        if not m:
            continue
        print(f"\n  {mode.upper()}:")
        print(f"    2c: Acc={fmt(m.get('2class_Acc'))} F1m={fmt(m.get('2class_F1_macro'))} "
              f"F1w={fmt(m.get('2class_F1_weighted'))} (n={m.get('2class_n', 0)})")
        print(f"    4c: Acc={fmt(m.get('4class_Acc'))} F1m={fmt(m.get('4class_F1_macro'))} "
              f"F1w={fmt(m.get('4class_F1_weighted'))} (n={m.get('4class_n', 0)})")
        print(f"   12c: Acc={fmt(m.get('12class_Acc'))} Top1={fmt(m.get('12class_Top1'))} "
              f"Top3={fmt(m.get('12class_Top3'))} F1m={fmt(m.get('12class_F1_macro'))} "
              f"F1w={fmt(m.get('12class_F1_weighted'))} (n={m.get('12class_n', 0)})")
        print(f"    Overall={fmt(m.get('Overall'))}")

    if "delta" in output:
        d = output["delta"]
        print(f"\n  DELTA (DtV - Single):")
        print(f"    Overall: {d.get('Overall', 0):+.3f}")
        for k in ["12class_Acc", "12class_Top1", "12class_Top3",
                   "12class_F1_macro", "4class_Acc", "2class_Acc"]:
            if k in d:
                print(f"    {k}: {d[k]:+.3f}")


# ---------------------------------------------------------------------------
# Checkpointing
# ---------------------------------------------------------------------------

def _save_checkpoint(results: list[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _load_checkpoint(path: Path) -> list[dict]:
    if not path.exists():
        return []
    results = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))
    return results


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_cases(data_path: str, split: str) -> list[dict]:
    """Load LingxiDiag16k cases as raw dicts."""
    raw_path = Path(data_path) / f"{split}.json"
    if raw_path.exists():
        with open(raw_path, encoding="utf-8") as f:
            return json.load(f)
    # Fallback: use adapter
    adapter = LingxiDiag16kAdapter(data_path)
    clinical_cases = adapter.load(split=split)
    return [
        {
            "ConversationID": c.case_id,
            "DiagnosisCode": (c.metadata or {}).get("diagnosis_code_full", c.diagnoses[0] if c.diagnoses else ""),
            "Conversation": [{"speaker": t.speaker, "text": t.text} for t in c.transcript],
        }
        for c in clinical_cases
    ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Multi-backbone CultureDx DtV evaluation")
    parser.add_argument("--provider", required=True,
                        choices=["anthropic", "openai", "deepseek", "gemini", "vllm",
                                 "cerebras", "sambanova", "claude-cli", "codex-cli"],
                        help="LLM provider")
    parser.add_argument("--model", required=True, help="Model name/ID")
    parser.add_argument("--base-url", default=None, help="API base URL (for vllm/deepseek)")
    parser.add_argument("--api-key", default=None, help="API key override")
    parser.add_argument("--data-path", default="data/raw/lingxidiag16k",
                        help="Path to LingxiDiag16k data")
    parser.add_argument("--split", default="validation", help="Dataset split")
    parser.add_argument("--max-cases", type=int, default=200,
                        help="Max cases (0=all, default=200 for cost control)")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--skip-single", action="store_true", help="Skip single baseline")
    parser.add_argument("--skip-dtv", action="store_true", help="Skip DtV pipeline")
    parser.add_argument("--skip-triage", action="store_true",
                        help="Skip triage step in DtV (diagnostician ranks all 12 candidates)")
    parser.add_argument("--start-index", type=int, default=0,
                        help="Start from this case index (for split runs)")
    parser.add_argument("--merge-2c4c", action="store_true",
                        help="Merge 2c+4c into one LLM call (saves 1 call per case)")
    parser.add_argument("--reasoning-effort", default=None,
                        help="Reasoning effort for codex-cli (low/medium/high/xhigh)")
    parser.add_argument("--concurrent", type=int, default=4,
                        help="Max concurrent API calls (reserved for future async)")
    # Night 2 ablation flags
    parser.add_argument("--rare-specialist", action="store_true",
                        help="Enable RareClassSpecialist after diagnostician")
    parser.add_argument("--checker-base-url", default=None,
                        help="Base URL for separate checker model (Mixed Checker ablation)")
    parser.add_argument("--checker-model", default=None,
                        help="Model name for separate checker (Mixed Checker ablation)")
    parser.add_argument("--ensemble", action="store_true",
                        help="Enable Ensemble Diagnostician (Borda count)")
    parser.add_argument("--ensemble-base-url", default=None,
                        help="Base URL for ensemble second model")
    parser.add_argument("--ensemble-model", default=None,
                        help="Model name for ensemble second model")
    args = parser.parse_args()

    provider = LLMProvider(
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        max_concurrent=args.concurrent,
        reasoning_effort=getattr(args, 'reasoning_effort', None),
    )

    cases = load_cases(args.data_path, args.split)
    logger.info("Loaded %d cases from %s/%s", len(cases), args.data_path, args.split)

    # Build optional ablation providers
    checker_provider = None
    if args.checker_base_url and args.checker_model:
        checker_provider = LLMProvider(
            provider=args.provider,
            model=args.checker_model,
            base_url=args.checker_base_url,
            api_key="not-needed" if args.provider == "vllm" else args.api_key,
            max_concurrent=args.concurrent,
        )

    ensemble_provider = None
    if args.ensemble and args.ensemble_base_url and args.ensemble_model:
        ensemble_provider = LLMProvider(
            provider=args.provider,
            model=args.ensemble_model,
            base_url=args.ensemble_base_url,
            api_key="not-needed" if args.provider == "vllm" else args.api_key,
            max_concurrent=args.concurrent,
        )

    evaluate_backbone(
        provider=provider,
        cases=cases,
        max_cases=args.max_cases,
        output_dir=Path(args.output_dir),
        skip_single=args.skip_single,
        skip_dtv=args.skip_dtv,
        skip_triage=args.skip_triage,
        start_case_index=args.start_index,
        merge_2c4c=args.merge_2c4c,
        rare_specialist=args.rare_specialist,
        checker_provider=checker_provider,
        ensemble_provider=ensemble_provider,
    )


if __name__ == "__main__":
    main()
