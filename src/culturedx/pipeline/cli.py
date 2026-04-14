# src/culturedx/pipeline/cli.py
"""CLI entry point for CultureDx."""
from __future__ import annotations

import logging
from pathlib import Path

import click

from culturedx.core.config import load_config
from culturedx.pipeline.reproducibility import apply_global_seed


def _create_configured_llm(cfg, llm_cfg):
    """Build an LLM client from a config section without changing defaults."""
    from culturedx.llm import create_llm_client

    return create_llm_client(
        provider=llm_cfg.provider,
        base_url=llm_cfg.base_url,
        model=llm_cfg.model_id,
        temperature=llm_cfg.temperature,
        top_k=llm_cfg.top_k,
        max_tokens=getattr(llm_cfg, "max_tokens", 2048),
        timeout=cfg.request_timeout_sec,
        cache_path=Path(cfg.cache_dir) / "llm_cache.db",
        disable_thinking=getattr(llm_cfg, "disable_thinking", True),
        max_concurrent=getattr(llm_cfg, "max_concurrent", 4),
        seed=getattr(cfg, "seed", None),
        context_window=getattr(llm_cfg, "context_window", None),
    )


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
    apply_global_seed(cfg.seed)

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

    # 3. Create LLM clients
    llm = _create_configured_llm(cfg, cfg.llm)
    checker_llm = _create_configured_llm(cfg, cfg.checker_llm) if cfg.checker_llm else None

    # 4. Create evidence pipeline (optional)
    evidence_pipeline = None
    if with_evidence:
        click.echo("Evidence extraction: ENABLED")
        from culturedx.evidence.pipeline import EvidencePipeline
        from culturedx.evidence.retriever_factory import create_retriever

        retriever = create_retriever(cfg.evidence.retriever)
        click.echo(f"Retriever: {cfg.evidence.retriever.name}")
        evidence_scope_policy = cfg.evidence.scope_policy
        if evidence_scope_policy == "auto":
            evidence_scope_policy = (
                "manual" if cfg.mode.target_disorders else "all_supported"
            )
        click.echo(f"Evidence scope policy: {evidence_scope_policy}")
        evidence_pipeline = EvidencePipeline(
            llm_client=llm,
            retriever=retriever,
            target_disorders=cfg.mode.target_disorders,
            scope_policy=evidence_scope_policy,
            somatization_enabled=cfg.evidence.somatization.enabled,
            somatization_mode=cfg.evidence.somatization.mode,
            rerank_enabled=cfg.evidence.rerank_enabled,
            rerank_top_n=cfg.evidence.rerank_top_n,
            top_k=cfg.evidence.top_k_final,
            min_confidence=cfg.evidence.min_confidence,
            negation_mode=cfg.evidence.negation_mode,
        )

    # 5. Create mode
    mode_type = cfg.mode.type
    click.echo(f"Mode: {mode_type}")

    # Load CaseRetriever only when retrieval is enabled in config
    case_retriever = None
    if cfg.retrieval.enabled:
        case_index_path = Path("data/cache/train_case_index.faiss")
        case_meta_path = Path("data/cache/train_case_metadata.json")
        if case_index_path.exists() and case_meta_path.exists():
            try:
                from culturedx.retrieval.case_retriever import CaseRetriever
                case_retriever = CaseRetriever(case_index_path, case_meta_path)
                click.echo(f"RAG enabled: loaded {case_index_path}")
            except ImportError:
                click.echo("Warning: retrieval enabled but faiss/case_retriever not installed")
            except Exception as e:
                click.echo(f"Warning: CaseRetriever failed to load: {e}")
        else:
            click.echo("Warning: retrieval enabled but FAISS index not found")

    if mode_type == "hied":
        from culturedx.modes.hied import HiEDMode
        mode_kwargs = dict(
            llm_client=llm,
            target_disorders=cfg.mode.target_disorders,
            scope_policy=cfg.mode.scope_policy,
            execution_mode=cfg.mode.execution_mode,
            diagnose_then_verify=cfg.mode.diagnose_then_verify,
            contrastive_enabled=cfg.mode.contrastive_enabled,
            prompt_variant=cfg.mode.prompt_variant,
            calibrator_mode=cfg.mode.calibrator_mode,
            calibrator_artifact_path=cfg.mode.calibrator_artifact_path,
            force_prediction=cfg.mode.force_prediction,
        )
        if checker_llm is not None:
            mode_kwargs["checker_llm_client"] = checker_llm
        if case_retriever is not None:
            mode_kwargs["case_retriever"] = case_retriever
        mode = HiEDMode(**mode_kwargs)
    elif mode_type == "psycot":
        from culturedx.modes.psycot import PsyCoTMode
        mode_kwargs = dict(
            llm_client=llm,
            target_disorders=cfg.mode.target_disorders,
            prompt_variant=cfg.mode.prompt_variant,
            force_prediction=cfg.mode.force_prediction,
        )
        if checker_llm is not None:
            mode_kwargs["checker_llm_client"] = checker_llm
        mode = PsyCoTMode(**mode_kwargs)
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
        mode_kwargs = dict(
            llm_client=llm,
            target_disorders=cfg.mode.target_disorders,
            prompt_variant=cfg.mode.prompt_variant,
        )
        if case_retriever is not None:
            mode_kwargs["case_retriever"] = case_retriever
        mode = SingleModelMode(**mode_kwargs)

    if cfg.mode.target_disorders:
        click.echo(f"Target disorders: {', '.join(cfg.mode.target_disorders)}")
    if mode_type == "hied":
        click.echo(f"HiED scope policy: {cfg.mode.scope_policy}")
        click.echo(f"HiED execution mode: {cfg.mode.execution_mode}")

    # 6. Run experiment
    base_output = output_dir or cfg.output_dir
    if output_dir:
        # Explicit output dir: use as-is
        run_dir = Path(output_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
    else:
        # Auto-generate timestamped run dir
        run_dir = ExperimentRunner.create_run_dir(base_output, cfg.mode.type, dataset)

    # Use case-level parallelism when vLLM continuous batching is available
    max_cases_in_flight = getattr(cfg.llm, "max_concurrent", 1)
    if cfg.llm.provider == "vllm":
        # vLLM handles concurrent requests efficiently via continuous batching
        max_cases_in_flight = max(max_cases_in_flight, 4)

    runner = ExperimentRunner(
        mode=mode,
        output_dir=run_dir,
        evidence_pipeline=evidence_pipeline,
        max_cases_in_flight=max_cases_in_flight,
    )

    click.echo(f"Output directory: {run_dir}")
    click.echo(f"Running CultureDx mode={cfg.mode.type} on {len(cases)} cases...")

    # Save run metadata
    runner.save_run_info(
        config_dict=cfg.model_dump(),
        dataset_name=dataset,
        num_cases=len(cases),
        mode_type=cfg.mode.type,
        case_ids=[case.case_id for case in cases],
        runtime_context={
            "config_paths": list(config),
            "data_path": effective_data_path,
            "split": split,
            "limit": limit,
            "with_evidence": with_evidence,
            "seed": cfg.seed,
        },
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
    from culturedx.pipeline.sweep import SweepCondition, SweepRunner, build_ablation_conditions

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

    # Create LLM clients
    llm = _create_configured_llm(cfg, cfg.llm)
    checker_llm = _create_configured_llm(cfg, cfg.checker_llm) if cfg.checker_llm else None

    # --- Sweep acceleration: shared caches across conditions ---
    # 1. Create shared retriever (avoid reloading BGE-M3 per condition)
    shared_retriever = None
    embedding_cache = None
    brief_cache = None
    any_evidence = any(c.with_evidence for c in conditions)
    if any_evidence:
        from culturedx.evidence.embedding_cache import EmbeddingCache
        from culturedx.evidence.brief_cache import EvidenceBriefCache
        from culturedx.evidence.retriever_factory import create_retriever

        embedding_cache = EmbeddingCache()
        brief_cache = EvidenceBriefCache()
        shared_retriever = create_retriever(
            cfg.evidence.retriever, embedding_cache=embedding_cache
        )
        click.echo("Sweep acceleration: shared retriever + embedding cache + brief cache")

    # 2. Smart condition ordering: no-evidence first (primes LLM cache)
    def _condition_sort_key(c: SweepCondition) -> tuple:
        # no_evidence < evidence, hied first (most cache-generative)
        mode_order = {"hied": 0, "psycot": 1, "specialist": 2, "debate": 3, "single": 4}
        return (
            0 if not c.with_evidence else 1,
            mode_order.get(c.mode_type, 9),
            0 if not c.with_somatization else 1,
        )
    conditions = sorted(conditions, key=_condition_sort_key)
    click.echo("Condition execution order (optimized for LLM cache):")
    for i, c in enumerate(conditions):
        click.echo(f"  {i+1}. {c.name}")

    def run_fn(condition: SweepCondition, cases_list: list) -> tuple:
        """Execute a single sweep condition and return (results, metrics)."""
        from culturedx.pipeline.runner import ExperimentRunner

        # Create mode for this condition
        mode_type = condition.mode_type
        if mode_type == "hied":
            from culturedx.modes.hied import HiEDMode
            mode_kwargs = dict(
                llm_client=llm,
                target_disorders=condition.target_disorders,
                scope_policy=cfg.mode.scope_policy,
                execution_mode=cfg.mode.execution_mode,
                diagnose_then_verify=cfg.mode.diagnose_then_verify,
                contrastive_enabled=cfg.mode.contrastive_enabled,
                prompt_variant=cfg.mode.prompt_variant,
                calibrator_mode=cfg.mode.calibrator_mode,
                calibrator_artifact_path=cfg.mode.calibrator_artifact_path,
                force_prediction=cfg.mode.force_prediction,
            )
            if checker_llm is not None:
                mode_kwargs["checker_llm_client"] = checker_llm
            mode = HiEDMode(**mode_kwargs)
        elif mode_type == "psycot":
            from culturedx.modes.psycot import PsyCoTMode
            mode_kwargs = dict(
                llm_client=llm,
                target_disorders=condition.target_disorders,
                prompt_variant=cfg.mode.prompt_variant,
                force_prediction=cfg.mode.force_prediction,
            )
            if checker_llm is not None:
                mode_kwargs["checker_llm_client"] = checker_llm
            mode = PsyCoTMode(**mode_kwargs)
        elif mode_type == "mas":
            from culturedx.modes.mas import MASMode
            mode = MASMode(llm_client=llm, target_disorders=condition.target_disorders)
        elif mode_type == "specialist":
            from culturedx.modes.specialist import SpecialistMode
            mode = SpecialistMode(llm_client=llm, target_disorders=condition.target_disorders)
        elif mode_type == "debate":
            from culturedx.modes.debate import DebateMode
            mode = DebateMode(llm_client=llm)
        else:
            from culturedx.modes.single import SingleModelMode
            mode = SingleModelMode(
                llm_client=llm,
                target_disorders=cfg.mode.target_disorders,
                prompt_variant=cfg.mode.prompt_variant,
            )

        # Create evidence pipeline using shared retriever + caches
        evidence_pipeline = None
        if condition.with_evidence and shared_retriever is not None:
            from culturedx.evidence.pipeline import EvidencePipeline

            evidence_scope_policy = cfg.evidence.scope_policy
            if evidence_scope_policy == "auto":
                evidence_scope_policy = (
                    "manual"
                    if (condition.target_disorders or cfg.mode.target_disorders)
                    else "all_supported"
                )
            evidence_pipeline = EvidencePipeline(
                llm_client=llm,
                retriever=shared_retriever,
                target_disorders=condition.target_disorders or cfg.mode.target_disorders,
                scope_policy=evidence_scope_policy,
                somatization_enabled=condition.with_somatization,
                somatization_mode=cfg.evidence.somatization.mode,
                rerank_enabled=cfg.evidence.rerank_enabled,
                rerank_top_n=cfg.evidence.rerank_top_n,
                top_k=cfg.evidence.top_k_final,
                min_confidence=cfg.evidence.min_confidence,
                negation_mode=cfg.evidence.negation_mode,
                brief_cache=brief_cache,
            )

        # Run through ExperimentRunner
        cond_dir = Path(output_dir) / f"ablation_{dataset}" / condition.name
        cond_dir.mkdir(parents=True, exist_ok=True)
        runner = ExperimentRunner(
            mode=mode,
            output_dir=cond_dir,
            evidence_pipeline=evidence_pipeline,
        )
        results = runner.run(cases_list)

        # Evaluate if ground truth available
        has_labels = any(c.diagnoses for c in cases_list)
        if has_labels:
            metrics = runner.evaluate(results, cases_list)
        else:
            metrics = {}

        return results, metrics

    # Run sweep with run_fn
    runner = SweepRunner(base_output_dir=output_dir)
    report = runner.run_sweep(
        conditions, cases, run_fn=run_fn, sweep_name=f"ablation_{dataset}",
    )

    click.echo(f"Sweep complete. {len(report.results)} conditions executed.")
    if report.results:
        click.echo("\nResults summary:")
        for r in report.results:
            dx_metrics = r.metrics.get("diagnosis", {})
            top1 = dx_metrics.get("top1_accuracy", "N/A")
            f1 = dx_metrics.get("macro_f1", "N/A")
            click.echo(
                f"  {r.condition.name:30s} top1={top1}  f1={f1}  "
                f"dx={r.num_diagnosed}  abstain={r.num_abstained}  "
                f"time={r.duration_sec:.1f}s"
            )
    click.echo(f"Report: {output_dir}")


if __name__ == "__main__":
    cli()
