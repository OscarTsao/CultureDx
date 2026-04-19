#!/usr/bin/env python3
"""R4 Contrastive Primary Disambiguation — integration module.

Designed to slot into hied.py AFTER logic_engine and BEFORE calibrator.

Trigger logic:
  - ONLY when logic_engine_confirmed_codes contains BOTH F32 and F41 (parent-level)
  - In the baseline t1_diag_topk run, this applies to 689/1000 cases (68.9%)
  - Targets the 160 F41→F32 ranking errors (17 F32→F41 inverse)

Integration point:
  - After: logic_engine.evaluate(all_checker_outputs)
  - Before: calibrator scores candidates
  - Effect: if contrastive agent chooses F41 with confidence > threshold,
    override diagnostician's ranked_codes to put F41 at position 1

Pseudo-code (what needs to go into hied.py):

    confirmed_parents = {to_paper_parent(c) for c in logic_confirmed_codes}

    if "F32" in confirmed_parents and "F41" in confirmed_parents:
        # Extract checker outputs for F32* and F41*
        f32_checker = best_checker(raw_checker_outputs, "F32")
        f41_checker = best_checker(raw_checker_outputs, "F41")

        # Run contrastive agent
        contrastive_result = await llm.call(
            prompt="contrastive_primary_zh",
            variables={
                "transcript_summary": transcript,
                "disorder_a": "F32",
                "disorder_b": "F41",
                "checker_a": f32_checker,
                "checker_b": f41_checker,
                "disorder_names": {"F32": "抑郁发作", "F41": "其他焦虑障碍"},
            }
        )
        primary_choice = contrastive_result["primary_diagnosis"]  # "F32" or "F41"
        confidence = contrastive_result["confidence"]

        # Override ranked_codes if confident
        if confidence >= contrastive_confidence_threshold:  # default 0.70
            ranked_codes = [primary_choice] + [
                c for c in ranked_codes
                if to_paper_parent(c) != primary_choice
            ]
            # Also update primary_diagnosis
            primary_diagnosis = primary_choice

    # Continue with existing pipeline (calibrator, gate, etc.)

Expected impact (based on Q4 finding):
  - 160 F41→F32 errors: if contrastive agent correctly identifies F41 in half
    of these (80 cases), Top-1 improves ~8pp
  - 17 F32→F41 errors: if contrastive agent correctly identifies F32, small gain
  - Net expected: +5 to +10pp Top-1, +5 to +15pp F1_macro

Risks:
  - Extra LLM call on 689 cases adds ~25% to inference time
  - If contrastive agent itself has F32 bias, no improvement
  - May over-flip F32→F41 on genuine F32 cases
"""
from __future__ import annotations


# ===================================================================
# Config file: configs/overlays/r4_contrastive_primary.yaml
# ===================================================================

CONFIG_YAML = """
# R4: Primary-level Contrastive Disambiguation for F41/F32
# Triggers after logic_engine when both F41 and F32 are confirmed
mode:
  contrastive_primary_enabled: true
  contrastive_primary_trigger_pairs:
    - ["F32", "F41"]
  contrastive_primary_confidence_threshold: 0.70
  contrastive_primary_prompt: contrastive_primary_zh
"""


# ===================================================================
# Integration into src/culturedx/modes/hied.py
# ===================================================================

# Add imports:
# from culturedx.agents.contrastive_primary import run_contrastive_primary

# In the pipeline method, after logic_engine call and before final primary selection:

INTEGRATION_SNIPPET = '''
# --- R4: Primary-level Contrastive Disambiguation ---
if getattr(self.cfg.mode, "contrastive_primary_enabled", False):
    trigger_pairs = self.cfg.mode.get("contrastive_primary_trigger_pairs", [["F32", "F41"]])
    threshold = self.cfg.mode.get("contrastive_primary_confidence_threshold", 0.70)

    confirmed_parents = {
        to_paper_parent(c) for c in logic_engine_confirmed_codes
    }

    for pair in trigger_pairs:
        pa, pb = pair
        if pa in confirmed_parents and pb in confirmed_parents:
            # Get best checker output for each parent
            checker_a = _best_checker_for_parent(raw_checker_outputs, pa)
            checker_b = _best_checker_for_parent(raw_checker_outputs, pb)

            if checker_a and checker_b:
                contrastive_result = await self._run_contrastive_primary(
                    transcript=transcript_text,
                    disorder_a=pa, disorder_b=pb,
                    checker_a=checker_a, checker_b=checker_b,
                )

                if contrastive_result:
                    chosen = contrastive_result.get("primary_diagnosis")
                    conf = float(contrastive_result.get("confidence", 0))

                    if chosen in (pa, pb) and conf >= threshold:
                        # Log the override
                        self.logger.info(
                            f"Contrastive override: {primary_diagnosis} -> {chosen} (conf={conf:.2f})"
                        )
                        # Reorder ranked_codes
                        chosen_in_ranked = [c for c in ranked_codes if to_paper_parent(c) == chosen]
                        if chosen_in_ranked:
                            new_ranked = chosen_in_ranked + [
                                c for c in ranked_codes if to_paper_parent(c) != chosen
                            ]
                            ranked_codes = new_ranked
                            primary_diagnosis = chosen_in_ranked[0]

                        # Save to decision_trace for analysis
                        decision_trace["contrastive_primary"] = {
                            "trigger_pair": pair,
                            "chosen": chosen,
                            "confidence": conf,
                            "reasoning": contrastive_result.get("differential_reasoning", ""),
                            "overridden": True,
                        }
                    else:
                        decision_trace["contrastive_primary"] = {
                            "trigger_pair": pair,
                            "chosen": chosen,
                            "confidence": conf,
                            "overridden": False,
                            "reason": "below_threshold" if conf < threshold else "invalid_choice",
                        }
            break  # only handle first trigger pair
'''


# ===================================================================
# Helper function for picking best checker output per parent
# ===================================================================

BEST_CHECKER_SNIPPET = '''
def _best_checker_for_parent(raw_checker_outputs, parent_code):
    """Return the checker output for the best-matching subcode of parent_code.

    E.g. for parent='F41', compare F41.0, F41.1, F41.2 outputs and pick the one
    with highest criteria_met_count.
    """
    candidates = []
    for item in raw_checker_outputs:
        code = item.get("disorder_code") or ""
        if to_paper_parent(code) == parent_code:
            candidates.append(item)
    if not candidates:
        return None
    return max(candidates, key=lambda x: x.get("criteria_met_count", 0))
'''


# ===================================================================
# Output for easy copy-paste
# ===================================================================

if __name__ == "__main__":
    print("=" * 72)
    print("R4 Integration Package")
    print("=" * 72)
    print()
    print("Files to add to repo:")
    print("  1. prompts/agents/contrastive_primary_zh.jinja  (provided separately)")
    print("  2. configs/overlays/r4_contrastive_primary.yaml")
    print("  3. src/culturedx/agents/contrastive_primary.py  (new module)")
    print("  4. Modify src/culturedx/modes/hied.py (add integration snippet)")
    print()
    print("Config YAML:")
    print(CONFIG_YAML)
    print()
    print("Integration snippet for hied.py (paste after logic_engine call):")
    print(INTEGRATION_SNIPPET)
