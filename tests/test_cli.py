# tests/test_cli.py
"""Tests for CLI entry point."""
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
            "seed: 42\noutput_dir: outputs\nmode:\n  name: single\n  type: single\n"
        )
        result = runner.invoke(
            cli, ["run", "-c", str(config_file), "-d", "mdd5k", "--with-evidence"]
        )
        assert result.exit_code == 0
        assert "Evidence extraction: ENABLED" in result.output
