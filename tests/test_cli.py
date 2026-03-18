# tests/test_cli.py
"""Tests for CLI entry point."""
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from culturedx.pipeline.cli import cli


class TestCLI:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "CultureDx" in result.output

    def test_smoke(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["smoke"])
        assert result.exit_code == 0
        assert "Smoke test" in result.output

    def test_run_with_evidence_flag(self, tmp_path):
        runner = CliRunner()
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(
            "seed: 42\noutput_dir: " + str(tmp_path / "outputs") + "\nmode:\n  name: single\n  type: single\n"
        )

        mock_adapter = MagicMock()
        mock_adapter.load.return_value = []
        mock_get_adapter = MagicMock(return_value=mock_adapter)

        mock_runner_instance = MagicMock()
        mock_runner_instance.run.return_value = []
        mock_runner_cls = MagicMock(return_value=mock_runner_instance)

        with (
            patch("culturedx.data.adapters.get_adapter", mock_get_adapter),
            patch("culturedx.llm.client.OllamaClient", MagicMock()),
            patch("culturedx.evidence.pipeline.EvidencePipeline", MagicMock()),
            patch("culturedx.evidence.retriever.MockRetriever", MagicMock()),
            patch("culturedx.modes.single.SingleModelMode", MagicMock()),
            patch("culturedx.pipeline.runner.ExperimentRunner", mock_runner_cls),
        ):
            result = runner.invoke(
                cli,
                [
                    "run",
                    "-c", str(config_file),
                    "-d", "mdd5k",
                    "--with-evidence",
                    "--data-path", "/home/user/YuNing/CultureDx/tests/fixtures/mdd5k_sample.json",
                ],
            )

        assert result.exit_code == 0, result.output
        assert "Evidence extraction: ENABLED" in result.output
