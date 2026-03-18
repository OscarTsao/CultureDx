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
@click.option("--config", "-c", required=True, multiple=True, type=click.Path(exists=True))
@click.option("--dataset", "-d", required=True, help="Dataset name (lingxidiag16k, mdd5k_raw, ...)")
@click.option("--split", "-s", default=None, help="Dataset split")
@click.option("--output-dir", "-o", default=None, help="Output directory override")
@click.option("--with-evidence", is_flag=True, help="Enable evidence extraction pipeline")
@click.option("--data-path", default=None, help="Override dataset path")
@click.option("--limit", "-n", default=None, type=int, help="Limit number of cases to process")
def run(
    config: tuple[str, ...],
    dataset: str,
    split: str | None,
    output_dir: str | None,
    with_evidence: bool,
    data_path: str | None,
    limit: int | None,
) -> None:
    """Run an experiment with a given config and dataset."""
    # 1. Load config
    if len(config) == 1:
        cfg = load_config(config[0])
    else:
        cfg = load_config(config[0], overrides=list(config[1:]))

    # 2. Load dataset
    from culturedx.data.adapters import get_adapter

    effective_data_path = data_path or cfg.dataset.data_path
    if not effective_data_path:
        click.echo("ERROR: No data path. Use --data-path or set dataset.data_path in config.", err=True)
        raise SystemExit(1)

    click.echo(f"Loading dataset '{dataset}' from {effective_data_path}...")
    adapter = get_adapter(dataset, effective_data_path)
    cases = adapter.load(split=split)
    if limit:
        cases = cases[:limit]
    click.echo(f"Loaded {len(cases)} cases.")

    # 3. Create LLM client
    from culturedx.llm.client import OllamaClient

    llm = OllamaClient(
        base_url=cfg.llm.base_url,
        model=cfg.llm.model_id,
        temperature=cfg.llm.temperature,
        top_k=cfg.llm.top_k,
        timeout=cfg.request_timeout_sec,
        cache_path=Path(cfg.cache_dir) / "llm_cache.db",
        provider=cfg.llm.provider,
    )

    # 4. Create evidence pipeline (optional)
    evidence_pipeline = None
    if with_evidence:
        click.echo("Evidence extraction: ENABLED")
        from culturedx.evidence.pipeline import EvidencePipeline
        from culturedx.evidence.retriever import MockRetriever

        retriever = MockRetriever()
        evidence_pipeline = EvidencePipeline(
            llm_client=llm,
            retriever=retriever,
            target_disorders=cfg.mode.target_disorders or ["F32", "F41.1"],
            somatization_enabled=cfg.evidence.somatization.enabled,
            somatization_llm_fallback=cfg.evidence.somatization.llm_fallback,
            top_k=cfg.evidence.top_k_final,
            min_confidence=cfg.evidence.min_confidence,
        )

    # 5. Create mode
    if cfg.mode.type == "mas":
        click.echo("MAS mode: ENABLED")
        from culturedx.modes.mas import MASMode

        mode = MASMode(
            llm_client=llm,
            target_disorders=cfg.mode.target_disorders,
        )
        if cfg.mode.target_disorders:
            click.echo(f"Target disorders: {', '.join(cfg.mode.target_disorders)}")
    else:
        from culturedx.modes.single import SingleModelMode

        mode = SingleModelMode(llm_client=llm)

    # 6. Run experiment
    from culturedx.pipeline.runner import ExperimentRunner

    effective_output = output_dir or cfg.output_dir
    runner = ExperimentRunner(
        mode=mode,
        output_dir=effective_output,
        evidence_pipeline=evidence_pipeline,
    )

    click.echo(f"Running CultureDx mode={cfg.mode.type} on {len(cases)} cases...")
    results = runner.run(cases)

    # 7. Evaluate
    has_labels = any(c.diagnoses for c in cases)
    if has_labels:
        metrics = runner.evaluate(results, cases)
        click.echo(f"Evaluation metrics: {metrics}")
    else:
        click.echo("No ground truth labels found; skipping evaluation.")

    click.echo(f"Predictions saved to {effective_output}/predictions.jsonl")
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
