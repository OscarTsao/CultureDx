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
    from culturedx.pipeline.runner import ExperimentRunner

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
        model=cfg.dataset.name or "qwen3:14b",
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
        from culturedx.evidence.retriever_factory import create_retriever

        retriever = create_retriever(cfg.evidence.retriever)
        click.echo(f"Retriever: {cfg.evidence.retriever.name}")
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
    mode_type = cfg.mode.type
    click.echo(f"Mode: {mode_type}")

    if mode_type == "hied":
        from culturedx.modes.hied import HiEDMode
        mode = HiEDMode(
            llm_client=llm,
            target_disorders=cfg.mode.target_disorders,
        )
    elif mode_type == "psycot":
        from culturedx.modes.psycot import PsyCoTMode
        mode = PsyCoTMode(
            llm_client=llm,
            target_disorders=cfg.mode.target_disorders,
        )
    elif mode_type == "mas":
        from culturedx.modes.mas import MASMode
        mode = MASMode(
            llm_client=llm,
            target_disorders=cfg.mode.target_disorders,
        )
    elif mode_type == "specialist":
        from culturedx.modes.specialist import SpecialistMode
        mode = SpecialistMode(
            llm_client=llm,
            target_disorders=cfg.mode.target_disorders,
        )
    elif mode_type == "debate":
        from culturedx.modes.debate import DebateMode
        mode = DebateMode(
            llm_client=llm,
        )
    else:
        from culturedx.modes.single import SingleModelMode
        mode = SingleModelMode(llm_client=llm)

    if cfg.mode.target_disorders:
        click.echo(f"Target disorders: {', '.join(cfg.mode.target_disorders)}")

    # 6. Run experiment
    base_output = output_dir or cfg.output_dir
    if output_dir:
        # Explicit output dir: use as-is
        run_dir = Path(output_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
    else:
        # Auto-generate timestamped run dir
        run_dir = ExperimentRunner.create_run_dir(base_output, cfg.mode.type, dataset)

    runner = ExperimentRunner(
        mode=mode,
        output_dir=run_dir,
        evidence_pipeline=evidence_pipeline,
    )

    click.echo(f"Output directory: {run_dir}")
    click.echo(f"Running CultureDx mode={cfg.mode.type} on {len(cases)} cases...")

    # Save run metadata
    runner.save_run_info(
        config_dict=cfg.model_dump(),
        dataset_name=dataset,
        num_cases=len(cases),
        mode_type=cfg.mode.type,
    )

    results = runner.run(cases)

    # 7. Evaluate
    has_labels = any(c.diagnoses for c in cases)
    if has_labels:
        metrics = runner.evaluate(results, cases)
        click.echo(f"Evaluation metrics: {metrics}")
    else:
        click.echo("No ground truth labels found; skipping evaluation.")

    click.echo(f"Predictions saved to {run_dir}/predictions.jsonl")
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


@cli.command()
@click.option("--config", "-c", required=True, multiple=True, type=click.Path(exists=True))
@click.option("--dataset", "-d", required=True, help="Dataset name")
@click.option("--data-path", default=None, help="Override dataset path")
@click.option("--modes", "-m", default=None, help="Comma-separated modes (default: all)")
@click.option("--output-dir", "-o", default="outputs/sweeps", help="Sweep output directory")
@click.option("--limit", "-n", default=None, type=int, help="Limit cases per condition")
@click.option("--dry-run", is_flag=True, help="Plan sweep without executing")
def sweep(
    config: tuple[str, ...],
    dataset: str,
    data_path: str | None,
    modes: str | None,
    output_dir: str,
    limit: int | None,
    dry_run: bool,
) -> None:
    """Run ablation sweep across modes and conditions."""
    from culturedx.pipeline.sweep import SweepRunner, build_ablation_conditions

    # Load config
    if len(config) == 1:
        cfg = load_config(config[0])
    else:
        cfg = load_config(config[0], overrides=list(config[1:]))

    # Parse modes
    mode_list = modes.split(",") if modes else None

    # Build conditions
    conditions = build_ablation_conditions(
        modes=mode_list,
        target_disorders=cfg.mode.target_disorders,
    )

    click.echo(f"Sweep: {len(conditions)} conditions")
    for c in conditions:
        click.echo(f"  - {c.name} (mode={c.mode_type}, evidence={c.with_evidence}, somat={c.with_somatization})")

    if dry_run:
        click.echo("Dry run complete. No experiments executed.")
        return

    # Load dataset
    from culturedx.data.adapters import get_adapter

    effective_data_path = data_path or cfg.dataset.data_path
    if not effective_data_path:
        click.echo("ERROR: No data path.", err=True)
        raise SystemExit(1)

    adapter = get_adapter(dataset, effective_data_path)
    cases = adapter.load()
    if limit:
        cases = cases[:limit]
    click.echo(f"Loaded {len(cases)} cases.")

    # Run sweep
    runner = SweepRunner(base_output_dir=output_dir)
    report = runner.run_sweep(conditions, cases, sweep_name=f"ablation_{dataset}")

    click.echo(f"Sweep complete. {len(report.results)} conditions executed.")
    click.echo(f"Report: {output_dir}")


if __name__ == "__main__":
    cli()
