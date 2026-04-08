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

    def run(self, input: AgentInput) -> AgentOutput:
        """Rank candidate disorders for the case transcript."""
        extra = input.extra or {}
        candidate_disorders = list(extra.get("candidate_disorders", []))
        disorder_names = dict(extra.get("disorder_names", {}))

        prompt_variant = extra.get("prompt_variant", "")
        if prompt_variant == "v2" and input.language == "zh":
            template_name = "diagnostician_v2_zh.jinja"
        else:
            template_name = f"diagnostician_{input.language}.jinja"
        template = self._env.get_template(template_name)
        # Pass similar cases if available (from CaseRetriever)
        similar_cases = extra.get("similar_cases", None)
        prompt = template.render(
            transcript_text=input.transcript_text,
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
        ranked_codes: list[str] = []
        reasoning: list[str] = []
        seen_codes: set[str] = set()

        for item in ranked:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code", "")).strip()
            if not code:
                continue
            if code not in allowed_codes:
                logger.warning(
                    "Diagnostician returned code %s outside candidate disorders %s",
                    code,
                    candidate_disorders,
                )
                return {
                    "ranked_codes": [],
                    "reasoning": [],
                }
            if code in seen_codes:
                continue
            seen_codes.add(code)
            ranked_codes.append(code)
            reasoning.append(str(item.get("reasoning", "")).strip())

        return {
            "ranked_codes": ranked_codes,
            "reasoning": reasoning,
        }
