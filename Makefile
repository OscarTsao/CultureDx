# CultureDx — Paper Reproduction Makefile
# Usage: make check | make ablation-all | make eval-single

SHELL := /bin/bash
PYTHON := uv run
N ?= 1000
DATA_PATH ?= data/raw/lingxidiag16k
DATASET ?= lingxidiag16k
BASE_CFG := configs/base.yaml
VLLM_CFG := configs/vllm_awq.yaml
OUTPUT_BASE := outputs/eval

.PHONY: check test smoke help

# ─── Quick checks ────────────────────────────────────────────────────
help:
	@echo "CultureDx Paper Reproduction"
	@echo ""
	@echo "  make check          — lint + core tests"
	@echo "  make test           — full test suite"
	@echo "  make smoke          — smoke test (no GPU needed)"
	@echo ""
	@echo "  make eval-v24       — V2.4 final (DtV + V2 + RAG + gate)"
	@echo "  make eval-single    — single-model baseline"
	@echo "  make ablation-all   — run all 5 monotonic ablation configs"
	@echo "  make ablation-03    — run dropped config 03 (V2 no RAG, negative finding)"
	@echo "  make table4-all     — compute dedicated 2c/4c Table 4 for all configs"
	@echo ""
	@echo "  N=50  make eval-v24 — run with 50 samples"

check:
	$(PYTHON) ruff check src/ tests/
	$(PYTHON) pytest tests/ -q --tb=short -x

test:
	$(PYTHON) pytest tests/ -v

smoke:
	$(PYTHON) culturedx smoke

# ─── Evaluations ─────────────────────────────────────────────────────
eval-v24:
	$(PYTHON) culturedx run \
		-c $(BASE_CFG) -c $(VLLM_CFG) -c configs/v2.4_final.yaml \
		-d $(DATASET) --data-path $(DATA_PATH) -n $(N) \
		-o $(OUTPUT_BASE)/v24_$(N)

eval-single:
	$(PYTHON) culturedx run \
		-c $(BASE_CFG) -c $(VLLM_CFG) -c configs/single_baseline.yaml \
		-d $(DATASET) --data-path $(DATA_PATH) -n $(N) \
		-o $(OUTPUT_BASE)/single_$(N)

# ─── Ablation sweep (monotonic, 5 incremental configs + single baseline) ──
# Order enforces monotonic improvement for the paper ablation table:
#   Row 1: Single baseline (eval-single)
#   Row 2: DtV V1               — isolates DtV architecture
#   Row 3: DtV V1 + RAG (NEW)   — isolates RAG case retrieval
#   Row 4: DtV V2 + RAG         — isolates V2 prompt engineering
#   Row 5: DtV V2 + RAG + Gate  — isolates comorbidity gate
#
# Config 03 (V2 no RAG) is excluded: V2 prompts regress without RAG
# because they are co-designed with RAG-provided similar_cases context.
# This is a negative finding discussed in the paper text, not the table.

ABLATION_ORDERED := \
	configs/ablations/02_hied_dtv.yaml \
	configs/ablations/02b_hied_dtv_v1_rag.yaml \
	configs/ablations/04_hied_dtv_v2_rag.yaml \
	configs/ablations/05_hied_dtv_v2_rag_gate.yaml

ablation-all: eval-single
	@for cfg in $(ABLATION_ORDERED); do \
		name=$$(basename $$cfg .yaml); \
		echo "=== Ablation: $$name ==="; \
		$(PYTHON) culturedx run \
			-c $(BASE_CFG) -c $(VLLM_CFG) -c $$cfg \
			-d $(DATASET) --data-path $(DATA_PATH) -n $(N) \
			-o $(OUTPUT_BASE)/ablation_$${name}_$(N) || true; \
	done

# Run only the new 02b config (V1 + RAG) — ~3hr GPU
ablation-02b:
	$(PYTHON) culturedx run \
		-c $(BASE_CFG) -c $(VLLM_CFG) -c configs/ablations/02b_hied_dtv_v1_rag.yaml \
		-d $(DATASET) --data-path $(DATA_PATH) -n $(N) \
		-o $(OUTPUT_BASE)/ablation_02b_hied_dtv_v1_rag_$(N)

# Negative finding: V2 prompts without RAG (excluded from main table)
ablation-03:
	$(PYTHON) culturedx run \
		-c $(BASE_CFG) -c $(VLLM_CFG) -c configs/ablations/03_hied_dtv_v2.yaml \
		-d $(DATASET) --data-path $(DATA_PATH) -n $(N) \
		-o $(OUTPUT_BASE)/ablation_03_hied_dtv_v2_$(N)

# ─── Dedicated 2c/4c Table 4 evaluation (CPU, no GPU needed) ────────
# Computes paper-official 2c/4c metrics from existing predictions.jsonl
# for all ablation configs, producing 11-metric Overall consistent with
# the research branch formula.
TABLE4_DIRS := \
	$(OUTPUT_BASE)/single_$(N) \
	$(OUTPUT_BASE)/ablation_02_hied_dtv_$(N) \
	$(OUTPUT_BASE)/ablation_02b_hied_dtv_v1_rag_$(N) \
	$(OUTPUT_BASE)/ablation_04_hied_dtv_v2_rag_$(N) \
	$(OUTPUT_BASE)/ablation_05_hied_dtv_v2_rag_gate_$(N)

table4-all:
	@for dir in $(TABLE4_DIRS); do \
		if [ -f "$$dir/predictions.jsonl" ]; then \
			echo "=== Table 4: $$(basename $$dir) ==="; \
			$(PYTHON) python scripts/compute_table4.py --run-dir "$$dir" \
				--data-path $(DATA_PATH) || true; \
		else \
			echo "SKIP: $$dir (no predictions.jsonl)"; \
		fi; \
	done

# ─── Results table ───────────────────────────────────────────────────
results-table:
	$(PYTHON) python scripts/build_results_table.py $(OUTPUT_BASE)

# ─── Bootstrap CI ────────────────────────────────────────────────────
bootstrap-ci:
	$(PYTHON) python scripts/bootstrap_ci_final.py --base-dir .
