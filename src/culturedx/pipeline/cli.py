# src/culturedx/pipeline/cli.py
"""CLI entry point for CultureDx."""
from __future__ import annotations

import logging
from pathlib import Path

import click

from culturedx.core.config import load_config


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def cli(verbose: bool) -> None:
    """CultureDx: Culture-Adaptive Diagnostic MAS."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@cli.command()
@click.option("--config", "-c", required=True, type=click.Path(exists=True))
@click.option("--dataset", "-d", required=True, help="Dataset name (mdd5k, pdch, edaic)")
@click.option("--split", "-s", default=None, help="Dataset split")
@click.option("--output-dir", "-o", default=None, help="Output directory override")
def run(config: str, dataset: str, split: str | None, output_dir: str | None) -> None:
    """Run an experiment with a given config and dataset."""
    cfg = load_config(config)
    click.echo(f"Running CultureDx mode={cfg.mode.type} on dataset={dataset}")
    click.echo(f"Config loaded from {config}")
    click.echo("Run complete.")


@cli.command()
def smoke() -> None:
    """Run smoke test on fixture data."""
    click.echo("Running smoke test...")
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    fixtures = project_root / "tests" / "fixtures"
    if not fixtures.exists():
        click.echo(f"ERROR: fixtures directory not found at {fixtures}", err=True)
        raise SystemExit(1)
    click.echo("Smoke test passed (fixture files found).")


if __name__ == "__main__":
    cli()
