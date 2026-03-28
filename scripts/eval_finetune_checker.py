#!/usr/bin/env python3
"""Evaluate fine-tuned LoRA criterion checker vs base model on val set."""
import json
import logging
import time
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
ADAPTER_PATH = "outputs/finetune/criterion_checker_lora"
VAL_FILE = "data/sft/criterion_checker_val.jsonl"
OUTPUT_FILE = "outputs/finetune/eval_results.json"


def load_val_data(path: str) -> list[dict]:
    examples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                examples.append(json.loads(line))
    return examples


def generate_response(model, tokenizer, prompt: str, max_new_tokens: int = 2048) -> str:
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.0,
            top_k=1,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
        )
    response = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    return response


def parse_checker_output(text: str) -> dict | None:
    """Try to parse criterion checker JSON output."""
    import re
    # Try to find JSON in response
    patterns = [
        r'```json\\s*(.*?)\\s*```',
        r'```\\s*(.*?)\\s*```',
        r'(\\{.*\\})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def evaluate_predictions(gold_data: list[dict], predictions: list[dict | None]) -> dict:
    """Compare predicted criterion statuses against gold."""
    total_criteria = 0
    correct_criteria = 0
    json_parse_success = 0
    total = len(gold_data)

    for gold, pred in zip(gold_data, predictions):
        if pred is None:
            continue
        json_parse_success += 1

        # Extract gold criteria from assistant message
        gold_response = gold["messages"][1]["content"]
        gold_parsed = parse_checker_output(gold_response)
        if gold_parsed is None:
            continue

        gold_criteria = {c["criterion_id"]: c["status"] for c in gold_parsed.get("criteria", [])}
        pred_criteria = {c["criterion_id"]: c["status"] for c in pred.get("criteria", [])}

        for cid, gold_status in gold_criteria.items():
            total_criteria += 1
            if pred_criteria.get(cid) == gold_status:
                correct_criteria += 1

    return {
        "total_examples": total,
        "json_parse_rate": json_parse_success / total if total else 0,
        "total_criteria": total_criteria,
        "criterion_accuracy": correct_criteria / total_criteria if total_criteria else 0,
        "correct_criteria": correct_criteria,
    }


def run_eval(model, tokenizer, val_data: list[dict], label: str) -> dict:
    logger.info("Evaluating %s on %d examples...", label, len(val_data))
    predictions = []
    t0 = time.time()
    for i, example in enumerate(val_data):
        prompt = example["messages"][0]["content"]
        response = generate_response(model, tokenizer, prompt)
        parsed = parse_checker_output(response)
        predictions.append(parsed)
        if (i + 1) % 20 == 0:
            logger.info("  %s: %d/%d done", label, i + 1, len(val_data))
    elapsed = time.time() - t0
    metrics = evaluate_predictions(val_data, predictions)
    metrics["total_seconds"] = round(elapsed, 1)
    metrics["avg_seconds_per_example"] = round(elapsed / len(val_data), 1)
    logger.info("%s results: json_parse=%.1f%%, criterion_acc=%.1f%%, time=%.0fs",
                label, metrics["json_parse_rate"] * 100,
                metrics["criterion_accuracy"] * 100, elapsed)
    return metrics


def main():
    val_data = load_val_data(VAL_FILE)
    logger.info("Loaded %d val examples", len(val_data))

    # Load base model in 4-bit
    logger.info("Loading base model: %s (4-bit)", MODEL_NAME)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )

    # Evaluate base model
    base_metrics = run_eval(base_model, tokenizer, val_data, "base")

    # Load LoRA adapter
    logger.info("Loading LoRA adapter from %s", ADAPTER_PATH)
    lora_model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
    lora_model.eval()

    # Evaluate LoRA model
    lora_metrics = run_eval(lora_model, tokenizer, val_data, "lora")

    # Summary
    results = {
        "base_model": MODEL_NAME,
        "adapter_path": ADAPTER_PATH,
        "val_examples": len(val_data),
        "base": base_metrics,
        "lora": lora_metrics,
        "improvement": {
            "json_parse_rate_delta": lora_metrics["json_parse_rate"] - base_metrics["json_parse_rate"],
            "criterion_accuracy_delta": lora_metrics["criterion_accuracy"] - base_metrics["criterion_accuracy"],
        },
    }

    Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info("="*60)
    logger.info("EVALUATION RESULTS")
    logger.info("="*60)
    logger.info("Base:  json_parse=%.1f%%  criterion_acc=%.1f%%",
                base_metrics["json_parse_rate"]*100, base_metrics["criterion_accuracy"]*100)
    logger.info("LoRA:  json_parse=%.1f%%  criterion_acc=%.1f%%",
                lora_metrics["json_parse_rate"]*100, lora_metrics["criterion_accuracy"]*100)
    logger.info("Delta: json_parse=%+.1fpp  criterion_acc=%+.1fpp",
                results["improvement"]["json_parse_rate_delta"]*100,
                results["improvement"]["criterion_accuracy_delta"]*100)
    logger.info("Saved to %s", OUTPUT_FILE)


if __name__ == "__main__":
    main()
