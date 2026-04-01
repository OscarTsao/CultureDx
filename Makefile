.PHONY: check test smoke

check:
	uv run pytest tests/test_cli.py tests/test_evidence_pipeline.py tests/test_calibrator.py tests/test_comorbidity.py tests/test_hied_mode.py -q

test:
	uv run pytest -q

smoke:
	uv run culturedx smoke
