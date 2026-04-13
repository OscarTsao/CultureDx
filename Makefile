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
	@echo "  make ablation-all   — run all 6 ablation configs"
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

# ─── Ablation sweep (5 incremental configs + single baseline) ────────
ABLATION_CFGS := $(sort $(wildcard configs/ablations/*.yaml))

ablation-all: eval-single
	@for cfg in $(ABLATION_CFGS); do \
		name=$$(basename $$cfg .yaml); \
		echo "=== Ablation: $$name ==="; \
		$(PYTHON) culturedx run \
			-c $(BASE_CFG) -c $(VLLM_CFG) -c $$cfg \
			-d $(DATASET) --data-path $(DATA_PATH) -n $(N) \
			-o $(OUTPUT_BASE)/ablation_$${name}_$(N) || true; \
	done

# ─── Results table ───────────────────────────────────────────────────
results-table:
	$(PYTHON) python scripts/build_results_table.py $(OUTPUT_BASE)

# ─── Bootstrap CI ────────────────────────────────────────────────────
bootstrap-ci:
	$(PYTHON) python scripts/bootstrap_ci_final.py --base-dir .
