#!/usr/bin/env python3
"""Fine-tune a smaller model on criterion checker SFT data using LoRA.

Uses HuggingFace transformers + peft (LoRA) to fine-tune Qwen2.5-7B
(or similar) on the criterion checker dataset prepared by prepare_sft_dataset.py.

Prerequisites:
    pip install transformers peft datasets accelerate bitsandbytes trl

Usage:
    python scripts/finetune_checker.py \
        --train-file data/sft/criterion_checker_train.jsonl \
        --val-file data/sft/criterion_checker_val.jsonl \
        --output-dir outputs/finetune/criterion_checker_lora \
        [--model-name Qwen/Qwen2.5-7B-Instruct] \
        [--epochs 3] [--batch-size 4] [--lr 2e-4]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_jsonl(path: Path) -> list[dict]:
    """Load JSONL file into list of dicts."""
    examples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


def format_chat_template(
    example: dict, tokenizer, max_length: int = 8192
) -> dict:
    """Format a messages-list example using the model's chat template.

    Returns tokenized input_ids + labels with prompt tokens masked.
    Uses response-boundary detection in the full tokenized sequence
    to avoid misalignment from special tokens (e.g., <think>).

    Background: The previous implementation tokenized the user message
    separately (messages[0] only with add_generation_prompt=True) and
    used len(prompt_tokens) as the mask boundary. With Qwen3-8B this
    causes eval_loss NaN because the chat template injects <think> blocks
    and system special tokens that shift the token count between a
    standalone prompt tokenization and the full-conversation tokenization.
    When prompt_len overshoots the actual assistant-start position, every
    response token is masked (-100), the model computes loss over zero
    valid targets, and the resulting loss is NaN/inf.

    Fix: tokenize the prompt-only prefix using the same template
    (apply_chat_template on all non-assistant messages with
    add_generation_prompt=True), then validate alignment by comparing
    token IDs against the full sequence. Fall back to an assistant-header
    search if alignment diverges by more than 20%.
    """
    messages = example["messages"]

    # Tokenize the full conversation
    full_text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=False
    )
    full_tokens = tokenizer(
        full_text,
        truncation=True,
        max_length=max_length,
        return_tensors=None,
    )

    # Find the assistant response boundary by tokenizing prompt-only
    # and matching token IDs in the full sequence.
    # Use the conversation up to (but not including) the assistant response.
    prompt_messages = []
    for msg in messages:
        if msg["role"] == "assistant":
            break
        prompt_messages.append(msg)

    prompt_text = tokenizer.apply_chat_template(
        prompt_messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    prompt_tokens = tokenizer(
        prompt_text,
        truncation=True,
        max_length=max_length,
        return_tensors=None,
    )

    # Find the best alignment point: scan for where prompt tokens end
    # in the full sequence. Use token-level matching with fallback.
    prompt_ids = prompt_tokens["input_ids"]
    full_ids = full_tokens["input_ids"]

    # Primary: direct length comparison (works when tokenization is consistent)
    prompt_len = len(prompt_ids)

    # Validation: check that the prompt tokens actually match the start
    # of the full sequence. If not, use a search-based approach.
    match_len = 0
    for i in range(min(prompt_len, len(full_ids))):
        if prompt_ids[i] == full_ids[i]:
            match_len += 1
        else:
            break

    if match_len < prompt_len * 0.8:
        # Significant mismatch -- fall back to searching for the assistant
        # header token pattern in the full sequence.
        # Common patterns: "assistant\n" or "<|im_start|>assistant"
        assistant_header = tokenizer.encode(
            "assistant", add_special_tokens=False
        )
        # Search for assistant header in full_ids after a reasonable offset
        search_start = max(len(full_ids) // 4, 10)
        prompt_len = len(full_ids)  # default: mask everything (safe fallback)
        for i in range(search_start, len(full_ids) - len(assistant_header)):
            if full_ids[i:i + len(assistant_header)] == assistant_header:
                # Found assistant header -- prompt ends right after it
                # Skip the header + any newline token
                prompt_len = i + len(assistant_header)
                # Skip trailing newline if present
                nl_tokens = tokenizer.encode("\n", add_special_tokens=False)
                if (prompt_len < len(full_ids) and nl_tokens and
                        full_ids[prompt_len] == nl_tokens[0]):
                    prompt_len += 1
                break
    else:
        # Good match -- use the prompt length directly
        prompt_len = match_len

    # Create labels: -100 for prompt tokens, actual ids for response
    labels = [-100] * prompt_len + full_ids[prompt_len:]

    # Ensure labels length matches input_ids
    if len(labels) < len(full_ids):
        labels = labels + [-100] * (len(full_ids) - len(labels))
    elif len(labels) > len(full_ids):
        labels = labels[:len(full_ids)]

    # Sanity check: at least some tokens should be non-masked
    non_masked = sum(1 for l in labels if l != -100)
    if non_masked == 0:
        logger.warning(
            "All tokens masked -- label alignment failed for example. "
            "Falling back to masking only first 20%% of tokens."
        )
        fallback_len = len(full_ids) // 5
        labels = [-100] * fallback_len + full_ids[fallback_len:]

    full_tokens["labels"] = labels
    return full_tokens


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fine-tune criterion checker with LoRA"
    )
    parser.add_argument(
        "--train-file",
        type=Path,
        default=PROJECT_ROOT / "data" / "sft" / "criterion_checker_train.jsonl",
        help="Training JSONL file",
    )
    parser.add_argument(
        "--val-file",
        type=Path,
        default=PROJECT_ROOT / "data" / "sft" / "criterion_checker_val.jsonl",
        help="Validation JSONL file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "finetune" / "criterion_checker_lora",
        help="Output directory for adapter weights",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="Qwen/Qwen2.5-7B-Instruct",
        help="Base model name or path",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=3,
        help="Number of training epochs",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help="Per-device train batch size",
    )
    parser.add_argument(
        "--gradient-accumulation-steps",
        type=int,
        default=4,
        help="Gradient accumulation steps (effective batch = batch_size * this)",
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=2e-4,
        help="Learning rate",
    )
    parser.add_argument(
        "--lora-r",
        type=int,
        default=16,
        help="LoRA rank",
    )
    parser.add_argument(
        "--lora-alpha",
        type=int,
        default=32,
        help="LoRA alpha",
    )
    parser.add_argument(
        "--lora-dropout",
        type=float,
        default=0.05,
        help="LoRA dropout",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=8192,
        help="Maximum sequence length",
    )
    parser.add_argument(
        "--bf16",
        action="store_true",
        default=True,
        help="Use bf16 mixed precision (default: True)",
    )
    parser.add_argument(
        "--load-in-4bit",
        action="store_true",
        default=False,
        help="Load base model in 4-bit quantization (QLoRA)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed",
    )
    args = parser.parse_args()

    # Validate input files exist
    if not args.train_file.exists():
        logger.error("Train file not found: %s", args.train_file)
        logger.error(
            "Run scripts/prepare_sft_dataset.py first to generate training data."
        )
        sys.exit(1)
    if not args.val_file.exists():
        logger.error("Val file not found: %s", args.val_file)
        sys.exit(1)

    # ---------- Import heavy dependencies ----------
    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, TaskType, get_peft_model
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            TrainingArguments,
            Trainer,
            DataCollatorForSeq2Seq,
        )
    except ImportError as e:
        logger.error(
            "Missing dependency: %s\n"
            "Install with: pip install transformers peft datasets "
            "accelerate bitsandbytes trl",
            e,
        )
        sys.exit(1)

    # ---------- Load data ----------
    logger.info("Loading training data from %s", args.train_file)
    train_data = load_jsonl(args.train_file)
    logger.info("Loading validation data from %s", args.val_file)
    val_data = load_jsonl(args.val_file)
    logger.info("Train: %d examples, Val: %d examples", len(train_data), len(val_data))

    # ---------- Load tokenizer ----------
    logger.info("Loading tokenizer: %s", args.model_name)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_name,
        trust_remote_code=True,
        padding_side="right",
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ---------- Load model ----------
    logger.info("Loading model: %s", args.model_name)
    model_kwargs = {
        "trust_remote_code": True,
        "torch_dtype": torch.bfloat16 if args.bf16 else torch.float16,
        "device_map": "auto",
    }

    if args.load_in_4bit:
        logger.info("Using 4-bit quantization (QLoRA)")
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16 if args.bf16 else torch.float16,
            bnb_4bit_use_double_quant=True,
        )
        model_kwargs["quantization_config"] = bnb_config

    model = AutoModelForCausalLM.from_pretrained(args.model_name, **model_kwargs)

    # ---------- Configure LoRA ----------
    logger.info(
        "Configuring LoRA: r=%d, alpha=%d, dropout=%.2f",
        args.lora_r, args.lora_alpha, args.lora_dropout,
    )
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=["q_proj", "v_proj"],
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    model.enable_input_require_grads()
    model.print_trainable_parameters()

    # ---------- Tokenize datasets ----------
    logger.info("Tokenizing datasets (max_length=%d)...", args.max_length)

    def tokenize_fn(example):
        return format_chat_template(example, tokenizer, args.max_length)

    train_dataset = Dataset.from_list(train_data)
    val_dataset = Dataset.from_list(val_data)

    train_dataset = train_dataset.map(
        tokenize_fn,
        remove_columns=train_dataset.column_names,
        num_proc=4,
        desc="Tokenizing train",
    )
    val_dataset = val_dataset.map(
        tokenize_fn,
        remove_columns=val_dataset.column_names,
        num_proc=4,
        desc="Tokenizing val",
    )

    # ---------- Training arguments ----------
    effective_batch = args.batch_size * args.gradient_accumulation_steps
    logger.info(
        "Training config: epochs=%d, batch=%d, grad_accum=%d, effective_batch=%d, lr=%s",
        args.epochs, args.batch_size, args.gradient_accumulation_steps,
        effective_batch, args.lr,
    )

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        weight_decay=0.01,
        bf16=args.bf16,
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=50,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        report_to="none",
        seed=args.seed,
        dataloader_num_workers=2,
        gradient_checkpointing=True,
        remove_unused_columns=False,
    )

    # ---------- Data collator ----------
    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        padding=True,
        return_tensors="pt",
    )

    # ---------- Trainer ----------
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        data_collator=data_collator,
        tokenizer=tokenizer,
    )

    # ---------- Train ----------
    logger.info("Starting training...")
    trainer.train()

    # ---------- Save ----------
    logger.info("Saving adapter weights to %s", output_dir)
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    # Save training config for reproducibility
    config_path = output_dir / "sft_config.json"
    config_dict = {
        "model_name": args.model_name,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "lora_dropout": args.lora_dropout,
        "target_modules": ["q_proj", "v_proj"],
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "gradient_accumulation_steps": args.gradient_accumulation_steps,
        "effective_batch_size": effective_batch,
        "learning_rate": args.lr,
        "max_length": args.max_length,
        "bf16": args.bf16,
        "load_in_4bit": args.load_in_4bit,
        "seed": args.seed,
        "train_examples": len(train_data),
        "val_examples": len(val_data),
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_dict, f, indent=2)

    logger.info("Training complete!")
    logger.info("Adapter weights: %s", output_dir)
    logger.info("Config: %s", config_path)
    logger.info("")
    logger.info("To load the adapter for inference:")
    logger.info("  from peft import PeftModel")
    logger.info("  model = AutoModelForCausalLM.from_pretrained('%s')", args.model_name)
    logger.info("  model = PeftModel.from_pretrained(model, '%s')", output_dir)


if __name__ == "__main__":
    main()
