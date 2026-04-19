"""Diagnostician agent: holistic ranking over candidate disorders."""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from culturedx.agents.base import AgentInput, AgentOutput, BaseAgent
from culturedx.llm.json_utils import extract_json_from_response

logger = logging.getLogger(__name__)

# One-line ICD-10 core descriptions for each supported disorder.
# Injected into the v2 diagnostician prompt so the LLM doesn't rely
# solely on parametric knowledge (which is weak for rare classes).
DISORDER_DESCRIPTIONS: dict[str, str] = {
    "F20": "持续性妄想、幻听、思维松弛/破裂、情感淡漠",
    "F22": "持续妄想障碍，无精神分裂症完整特征",
    "F31": "既往或目前存在躁狂/轻躁狂发作与抑郁发作的交替或混合",
    "F32": "情绪持续低落、兴趣/愉快感下降、精力不足；可轻/中/重度；无既往躁狂/轻躁狂",
    "F33": "复发性抑郁发作，需有明确既往独立发作证据且间隔≥2个月",
    "F39": "存在心境障碍证据，但资料不足以明确归入抑郁或双相等具体亚型",
    "F40": "恐惧症：对特定情境/物体的过度恐惧与回避",
    "F41": "焦虑障碍：过度担忧、紧张不安、自主神经症状",
    "F41.1": "过度担忧、紧张不安、心悸、胸闷、出汗、眩晕；与特定情境无关",
    "F42": "反复强迫观念/行为，自知过度但难以抵抗",
    "F43": "与明确应激事件有关；急性应激反应、PTSD或适应障碍",
    "F45": "反复躯体症状，检查难以找到足以解释的器质性原因",
    "F51": "失眠、嗜睡、梦魇等；非器质性原因；睡眠问题为主要主诉并致显著困扰",
    "F98": "多见于儿童期起病，以发育期特异表现为主（遗尿/口吃/进食等）",
    "Z71": "主要需要咨询服务而非特定疾病治疗",

    "F41.0": "反复突发的严重焦虑（恐慌发作），伴心悸、窒息感、胸痛、眩晕；不限于特定情境",
    "F41.2": "同时存在焦虑和抑郁症状，但均未达到独立诊断标准；常伴自主神经症状",
    "F43.1": "创伤后应激障碍：重大创伤后反复闪回、噩梦、回避、高警觉",
    "F43.2": "适应障碍：明确应激事件后出现情绪/行为困难，通常在事件后1个月内起病",
    "Z71": "心理咨询：主要寻求建议或指导，无明确精神障碍症状模式",

    "F41.9": "未特指焦虑障碍：存在焦虑症状但不符合广泛性焦虑(F41.1)或惊恐障碍(F41.0)的完整标准",
    "F43.9": "未特指严重应激反应：有应激源但症状不足以诊断PTSD(F43.1)或适应障碍(F43.2)",
    "F45.9": "未特指躯体形式障碍：有躯体化症状但不符合具体躯体形式障碍亚型",
    "F51.9": "未特指非器质性睡眠障碍：存在睡眠问题但不符合具体睡眠障碍亚型标准",
}


class DiagnosticianAgent(BaseAgent):
    """Rank candidate diagnoses using holistic clinical judgment."""

    def __init__(
        self,
        llm_client,
        prompts_dir: str | Path = "prompts/agents",
    ) -> None:
        self.llm = llm_client
        self.prompts_dir = Path(prompts_dir)
        self._env = Environment(
            loader=FileSystemLoader(str(self.prompts_dir)),
            keep_trailing_newline=True,
        )

    @staticmethod
    def _clip_text_middle(text: str, max_chars: int) -> str:
        """Head/tail trim already-formatted transcript text to a char budget."""
        if len(text) <= max_chars:
            return text
        head_budget = int(max_chars * 0.6)
        tail_budget = max_chars - head_budget
        marker = "\n[...对话中间部分省略 / middle turns omitted...]\n"
        return text[:head_budget] + marker + text[-tail_budget:]

    def _max_prompt_chars(self) -> int:
        context_window = int(getattr(self.llm, "context_window", None) or 16384)
        max_tokens = int(getattr(self.llm, "max_tokens", 2048) or 2048)
        input_budget_tokens = max(768, context_window - max_tokens - 512)
        return int(input_budget_tokens * 1.8)

    def run(self, input: AgentInput) -> AgentOutput:
        """Rank candidate disorders for the case transcript."""
        extra = input.extra or {}
        candidate_disorders = list(extra.get("candidate_disorders", []))
        disorder_names = dict(extra.get("disorder_names", {}))

        prompt_variant = extra.get("prompt_variant", "")
        if prompt_variant == "v2_somatization" and input.language == "zh":
            template_name = "diagnostician_v2_somatization_zh.jinja"
        elif prompt_variant == "v2_nos" and input.language == "zh":
            template_name = "diagnostician_v2_nos_zh.jinja"
        elif prompt_variant in ("v2", "v2diag") and input.language == "zh":
            template_name = "diagnostician_v2_zh.jinja"
        else:
            template_name = f"diagnostician_{input.language}.jinja"
        template = self._env.get_template(template_name)
        # Pass similar cases if available (from CaseRetriever)
        similar_cases = extra.get("similar_cases", None)
        transcript_text = input.transcript_text
        prompt = template.render(
            transcript_text=transcript_text,
            candidate_disorders=candidate_disorders,
            disorder_names=disorder_names,
            disorder_descriptions=DISORDER_DESCRIPTIONS,
            similar_cases=similar_cases,
        )
        max_prompt_chars = self._max_prompt_chars()
        if len(prompt) > max_prompt_chars:
            overflow = len(prompt) - max_prompt_chars
            clipped_chars = max(1400, len(transcript_text) - overflow - 256)
            transcript_text = self._clip_text_middle(transcript_text, clipped_chars)
            prompt = template.render(
                transcript_text=transcript_text,
                candidate_disorders=candidate_disorders,
                disorder_names=disorder_names,
                disorder_descriptions=DISORDER_DESCRIPTIONS,
                similar_cases=similar_cases,
            )

        source, _, _ = self._env.loader.get_source(self._env, template_name)
        prompt_hash = self.llm.compute_prompt_hash(source)

        raw = self.llm.generate(prompt, prompt_hash=prompt_hash, language=input.language)
        parsed = extract_json_from_response(raw)
        result = self._parse_ranking(parsed, candidate_disorders)

        return AgentOutput(
            raw_response=raw,
            parsed=result,
            model_name=self.llm.model,
            prompt_hash=prompt_hash,
        )

    def _parse_ranking(
        self,
        parsed: dict | list | None,
        candidate_disorders: list[str],
    ) -> dict:
        """Parse ranked diagnoses from the LLM response."""
        if not parsed or not isinstance(parsed, dict):
            return {
                "ranked_codes": [],
                "reasoning": [],
            }

        ranked = parsed.get("ranked_diagnoses", [])
        if not isinstance(ranked, list):
            logger.warning("Diagnostician parse failure: ranked_diagnoses is not a list")
            return {
                "ranked_codes": [],
                "reasoning": [],
            }

        allowed_codes = set(candidate_disorders)
        # Build normalization map: parent code → child code in candidate list
        # e.g. F41 → F41.1 if F41.1 is in candidates but F41 is not
        _code_norm: dict[str, str] = {}
        for c in candidate_disorders:
            parent = c.split(".")[0]
            if parent not in allowed_codes:
                _code_norm[parent] = c

        ranked_codes: list[str] = []
        reasoning: list[str] = []
        seen_codes: set[str] = set()

        for item in ranked:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code", "")).strip()
            if not code:
                continue
            # Normalize parent codes to their child variant
            code = _code_norm.get(code, code)
            if code not in allowed_codes:
                logger.warning(
                    "Diagnostician returned unknown code %s, skipping",
                    code,
                )
                continue
            if code in seen_codes:
                continue
            seen_codes.add(code)
            ranked_codes.append(code)
            reasoning.append(str(item.get("reasoning", "")).strip())

        return {
            "ranked_codes": ranked_codes,
            "reasoning": reasoning,
        }
