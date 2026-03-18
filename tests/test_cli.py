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
