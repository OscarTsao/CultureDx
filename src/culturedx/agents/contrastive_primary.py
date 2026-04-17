"""R4 Contrastive Primary agent.

Triggers after logic_engine when specified disorder pairs are both confirmed.
Performs explicit LLM-based primary diagnosis disambiguation.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jinja2

logger = logging.getLogger(__name__)


def load_prompt_template(prompt_name: str, prompts_dir: Path) -> jinja2.Template:
    """Load a jinja2 template from prompts/agents/."""
    template_path = prompts_dir / f"{prompt_name}.jinja"
    if not template_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {template_path}")

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(prompts_dir)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template(f"{prompt_name}.jinja")


def get_best_checker_for_parent(
    raw_checker_outputs: List[Dict[str, Any]],
    parent_code: str,
    to_paper_parent_fn,
) -> Optional[Dict[str, Any]]:
    """Return checker output for best subcode of parent_code."""
    candidates = []
    for item in raw_checker_outputs:
        code = item.get("disorder_code") or ""
        if to_paper_parent_fn(code) == parent_code:
            candidates.append(item)
    if not candidates:
        return None
    return max(candidates, key=lambda x: x.get("criteria_met_count", 0))


DISORDER_NAMES_ZH = {
    "F20": "精神分裂症",
    "F31": "双相情感障碍",
    "F32": "抑郁发作",
    "F39": "未特定的心境障碍",
    "F41": "其他焦虑障碍",
    "F41.0": "惊恐障碍",
    "F41.1": "广泛性焦虑障碍",
    "F41.2": "焦虑抑郁混合状态",
    "F42": "强迫性障碍",
    "F43": "应激相关障碍",
    "F45": "躯体形式障碍",
    "F51": "非器质性睡眠障碍",
    "F98": "起病于童年的行为和情绪障碍",
    "Z71": "寻求咨询",
}


def run_contrastive_primary(
    *,
    llm_runtime,
    prompt_template: jinja2.Template,
    transcript_text: str,
    disorder_a: str,
    disorder_b: str,
    checker_a: Dict[str, Any],
    checker_b: Dict[str, Any],
    llm_config: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Run contrastive disambiguation LLM call.

    Args:
      llm_runtime: the project's LLM runtime (async caller)
      prompt_template: loaded jinja2 template
      transcript_text: patient-doctor dialogue
      disorder_a, disorder_b: parent codes (e.g. "F32", "F41")
      checker_a, checker_b: raw_checker_outputs entries for best subcode
      llm_config: temperature, max_tokens, etc.

    Returns:
      dict with keys: primary_diagnosis, confidence, differential_reasoning
      or None on failure
    """
    try:
        prompt_text = prompt_template.render(
            transcript_summary=transcript_text,
            disorder_a=disorder_a,
            disorder_b=disorder_b,
            checker_a=checker_a,
            checker_b=checker_b,
            disorder_names=DISORDER_NAMES_ZH,
        )
    except Exception as exc:
        logger.error(f"Failed to render contrastive prompt: {exc}")
        return None

    try:
        raw = llm_runtime.generate(prompt_text, language="zh")
        raw = raw.strip()

        # Strip markdown code blocks if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        result = json.loads(raw)

        # Validate
        if "primary_diagnosis" not in result or "confidence" not in result:
            logger.warning(f"Contrastive response missing required fields: {raw[:200]}")
            return None

        # Clean primary_diagnosis to parent code
        primary = str(result["primary_diagnosis"]).strip()
        if primary not in (disorder_a, disorder_b):
            logger.warning(f"Contrastive returned invalid primary: {primary}")
            return None

        return {
            "primary_diagnosis": primary,
            "confidence": float(result.get("confidence", 0.0)),
            "primary_evidence": result.get("primary_evidence", ""),
            "secondary_consideration": result.get("secondary_consideration", ""),
            "differential_reasoning": result.get("differential_reasoning", ""),
        }
    except json.JSONDecodeError as exc:
        logger.error(f"Failed to parse contrastive JSON: {exc} | raw: {raw[:300]}")
        return None
    except Exception as exc:
        logger.error(f"Contrastive LLM call failed: {exc}")
        return None


def apply_contrastive_primary(
    *,
    logic_confirmed_codes: List[str],
    ranked_codes: List[str],
    raw_checker_outputs: List[Dict[str, Any]],
    transcript_text: str,
    current_primary: str,
    trigger_pairs: List[Tuple[str, str]],
    confidence_threshold: float,
    llm_runtime,
    prompt_template: jinja2.Template,
    llm_config: Dict[str, Any],
    to_paper_parent_fn,
) -> Tuple[str, List[str], Dict[str, Any]]:
    """Apply contrastive override if trigger conditions met.

    Returns:
      (new_primary, new_ranked_codes, contrastive_trace_dict)
    """
    confirmed_parents = {
        to_paper_parent_fn(c) for c in logic_confirmed_codes
    }
    confirmed_parents.discard("")
    confirmed_parents.discard(None)

    trace = {"triggered": False, "overridden": False}

    for pair in trigger_pairs:
        pa, pb = pair
        if pa in confirmed_parents and pb in confirmed_parents:
            trace["triggered"] = True
            trace["trigger_pair"] = list(pair)

            checker_a = get_best_checker_for_parent(raw_checker_outputs, pa, to_paper_parent_fn)
            checker_b = get_best_checker_for_parent(raw_checker_outputs, pb, to_paper_parent_fn)

            if not (checker_a and checker_b):
                trace["skipped"] = "missing_checker_data"
                break

            result = run_contrastive_primary(
                llm_runtime=llm_runtime,
                prompt_template=prompt_template,
                transcript_text=transcript_text,
                disorder_a=pa, disorder_b=pb,
                checker_a=checker_a, checker_b=checker_b,
                llm_config=llm_config,
            )

            if result is None:
                trace["skipped"] = "contrastive_failed"
                break

            chosen_parent = result["primary_diagnosis"]
            confidence = result["confidence"]

            trace["chosen_parent"] = chosen_parent
            trace["confidence"] = confidence
            trace["reasoning"] = result.get("differential_reasoning", "")

            if confidence < confidence_threshold:
                trace["skipped"] = f"confidence_below_threshold ({confidence:.2f} < {confidence_threshold})"
                break

            # Check if override is needed
            current_parent = to_paper_parent_fn(current_primary)
            if current_parent == chosen_parent:
                trace["skipped"] = "already_matches"
                break

            # Find specific subcode in ranked_codes for chosen_parent
            chosen_in_ranked = [c for c in ranked_codes if to_paper_parent_fn(c) == chosen_parent]
            if chosen_in_ranked:
                new_primary = chosen_in_ranked[0]
                new_ranked = chosen_in_ranked + [
                    c for c in ranked_codes if to_paper_parent_fn(c) != chosen_parent
                ]
            else:
                # Fallback: use .9 subcode
                new_primary = chosen_parent + ".9" if len(chosen_parent) == 3 else chosen_parent
                new_ranked = [new_primary] + ranked_codes

            trace["overridden"] = True
            trace["old_primary"] = current_primary
            trace["new_primary"] = new_primary

            logger.info(
                f"Contrastive override: {current_primary} -> {new_primary} "
                f"(conf={confidence:.2f})"
            )
            return new_primary, new_ranked, trace

    return current_primary, ranked_codes, trace
