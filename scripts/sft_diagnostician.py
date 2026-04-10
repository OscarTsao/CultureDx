#!/usr/bin/env python3
"""Fine-tune Qwen3-8B as diagnostician using LoRA.

Usage:
    python scripts/sft_diagnostician.py \
        --train-file data/sft/diagnostician/train.jsonl \
        --val-file data/sft/diagnostician/val.jsonl \
        --output-dir outputs/sft/diagnostician_qwen3_8b \
        [--model-name Qwen/Qwen3-8B] \
        [--epochs 3] [--batch-size 4] [--lr 2e-5]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, TaskType
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_jsonl(path: str) -> list[dict]:
    examples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                examples.append(json.loads(line))
    return examples


def preprocess_fn(examples, tokenizer, max_length=4096):
    """Tokenize chat messages with proper label masking."""
    input_ids_list = []
    labels_list = []
    attention_mask_list = []

    for messages in examples["messages"]:
        # Apply chat template
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False,
        )

        # Tokenize full conversation
        full = tokenizer(
            text,
            max_length=max_length,
            truncation=True,
            padding=False,
            return_tensors=None,
        )

        input_ids = full["input_ids"]
        attention_mask = full["attention_mask"]

        # Build labels: mask user/system tokens with -100, only train on assistant response
        # Find where assistant response starts by tokenizing just the user part
        user_text = tokenizer.apply_chat_template(
            messages[:1],  # just the user message
            tokenize=False,
            add_generation_prompt=True,  # includes the assistant prompt start
        )
        user_tokens = tokenizer(
            user_text,
            max_length=max_length,
            truncation=True,
            padding=False,
            return_tensors=None,
        )
        user_len = len(user_tokens["input_ids"])

        labels = [-100] * user_len + input_ids[user_len:]
        # Ensure same length
        labels = labels[:len(input_ids)]

        input_ids_list.append(input_ids)
        labels_list.append(labels)
        attention_mask_list.append(attention_mask)

    return {
        "input_ids": input_ids_list,
        "labels": labels_list,
        "attention_mask": attention_mask_list,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-file", required=True)
    parser.add_argument("--val-file", required=True)
    parser.add_argument("--output-dir", default="outputs/sft/diagnostician_qwen3_8b")
    parser.add_argument("--model-name", default="Qwen/Qwen3-8B")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=4096)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--warmup-ratio", type=float, default=0.05)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    train_data = load_jsonl(args.train_file)
    val_data = load_jsonl(args.val_file)
    logger.info("Train: %d, Val: %d", len(train_data), len(val_data))

    # Load tokenizer
    logger.info("Loading tokenizer: %s", args.model_name)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_name,
        trust_remote_code=True,
        padding_side="right",
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Load model with 4-bit quantization for memory efficiency
    logger.info("Loading model: %s (4-bit quantized)", args.model_name)
    from transformers import BitsAndBytesConfig
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        quantization_config=bnb_config,
        dtype=torch.bfloat16,
        trust_remote_code=True,
        device_map="auto",
    )
    model.config.use_cache = False

    # LoRA config
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Prepare datasets
    train_ds = Dataset.from_list(train_data)
    val_ds = Dataset.from_list(val_data)

    train_ds = train_ds.map(
        lambda batch: preprocess_fn(batch, tokenizer, args.max_length),
        batched=True,
        batch_size=100,
        remove_columns=train_ds.column_names,
        desc="Tokenizing train",
    )
    val_ds = val_ds.map(
        lambda batch: preprocess_fn(batch, tokenizer, args.max_length),
        batched=True,
        batch_size=100,
        remove_columns=val_ds.column_names,
        desc="Tokenizing val",
    )

    logger.info("Train tokens: %d examples", len(train_ds))
    logger.info("Val tokens: %d examples", len(val_ds))

    # Token length stats
    train_lens = [len(ids) for ids in train_ds["input_ids"]]
    import numpy as np
    logger.info("Token lengths: mean=%.0f, p50=%.0f, p95=%.0f, max=%d",
                np.mean(train_lens), np.median(train_lens),
                np.percentile(train_lens, 95), max(train_lens))

    # Training args
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        warmup_steps=int(args.warmup_ratio * 17208 / (args.batch_size * args.grad_accum)),
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        logging_steps=50,
        eval_strategy="steps",
        eval_steps=500,
        save_strategy="steps",
        save_steps=500,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        bf16=True,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        dataloader_num_workers=4,
        report_to="none",
        remove_unused_columns=False,
    )

    # Data collator
    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        padding=True,
        max_length=args.max_length,
        pad_to_multiple_of=8,
    )

    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=data_collator,
        processing_class=tokenizer,
    )

    # Train
    logger.info("Starting training...")
    trainer.train()

    # Save
    logger.info("Saving model to %s", output_dir)
    trainer.save_model(str(output_dir / "final"))
    tokenizer.save_pretrained(str(output_dir / "final"))

    # Save training metrics
    metrics = trainer.evaluate()
    logger.info("Final eval metrics: %s", metrics)
    with open(output_dir / "training_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    logger.info("Done!")


if __name__ == "__main__":
    main()
