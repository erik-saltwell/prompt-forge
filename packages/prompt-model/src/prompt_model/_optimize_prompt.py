from __future__ import annotations

import asyncio
import random
import time
import uuid
from collections import defaultdict

import structlog

from ._actor._redaction import RedactionStrategy
from ._actor._render_prompt_strategy import RenderPromptStrategy
from ._actor._signal_rendering_strategy import SignalRenderingStrategy
from ._actor.revise import StructuralCleanupPredicate, revise
from ._candidate import Candidate
from ._critic.composite_scorer import CompositeScorer, MeanScorer
from ._critic.select_next_candidates import select_top_candidates
from ._llm._concurrency import set_llm_concurrency
from ._metrics import Metric, MetricResult
from ._progress import ProgressEvent, ProgressReporter, RunProgress, StepProgress, TaskProgress
from ._prompt import Document, parse_from_string
from ._result import CandidateSummary, OptimizationResult
from .config import OptimizerConfig
from .config.strategies import (
    make_prompt_render_strategy,
    make_redaction_strategy,
    make_signal_render_strategy,
    make_structural_cleanup_predicate,
)

_DEFAULT_SCORER: CompositeScorer = MeanScorer()
_log = structlog.get_logger()


async def optimize_prompt(
    config: OptimizerConfig,
    metrics: list[Metric],
    scorer: CompositeScorer = _DEFAULT_SCORER,
    progress_reporter: ProgressReporter = None,
    *,
    redaction_strategy: RedactionStrategy | None = None,
    prompt_render_strategy: RenderPromptStrategy | None = None,
    signal_rendering_strategy: SignalRenderingStrategy | None = None,
    structural_cleanup_predicate: StructuralCleanupPredicate | None = None,
) -> OptimizationResult:
    """Optimize a prompt against a set of evaluation cases. See docs/orchestration.md."""
    if not metrics:
        raise ValueError("optimize_prompt requires at least one metric")
    if not config.eval_cases:
        raise ValueError("optimize_prompt requires at least one eval case")

    # Resolve strategies: explicit kwargs take precedence; fall back to config-driven factories.
    resolved_redaction: RedactionStrategy = redaction_strategy or make_redaction_strategy(config.redaction_strategy)
    resolved_prompt_render: RenderPromptStrategy = prompt_render_strategy or make_prompt_render_strategy(config.prompt_render_strategy)
    resolved_signal_render: SignalRenderingStrategy = signal_rendering_strategy or make_signal_render_strategy(config.signal_render_strategy)
    resolved_structural: StructuralCleanupPredicate = structural_cleanup_predicate or make_structural_cleanup_predicate(config.structural_cleanup)

    if config.seed is not None:
        random.seed(config.seed)

    n_cases: int = len(config.eval_cases)
    floor: int = min(config.floor, n_cases)
    warmup: int = min(config.seed_warmup_pulls, n_cases)

    run_id: str = f"run_{uuid.uuid4().hex[:12]}"
    structlog.contextvars.bind_contextvars(run_id=run_id)
    start_time: float = time.monotonic()

    seed_doc: Document = parse_from_string(config.seed_prompt)
    _log.info(
        "optimize_run.start",
        n_eval_cases=n_cases,
        n_iterations=config.iterations,
        metric_names=[m.name for m in metrics],
        floor=floor,
        warmup=warmup,
        target_model=getattr(config.target_llm, "model", None),
        actor_model=getattr(config.actor_llm, "model", None),
        structural_model=getattr(config.structural_llm, "model", None) if config.structural_llm is not None else None,
    )

    iterations_run: int = 0
    total_errors: int = 0
    outcome: str = "error"
    error_type: str | None = None
    error_message: str | None = None
    best_score: float = 0.0

    try:
        with set_llm_concurrency(config.max_llm_concurrency):
            pool, total_errors, iterations_run, best_score = await _run_optimization_body(
                config=config,
                metrics=metrics,
                scorer=scorer,
                progress_reporter=progress_reporter,
                redaction_strategy=resolved_redaction,
                prompt_render_strategy=resolved_prompt_render,
                signal_rendering_strategy=resolved_signal_render,
                structural_cleanup_predicate=resolved_structural,
                seed_doc=seed_doc,
                n_cases=n_cases,
                floor=floor,
                warmup=warmup,
            )
        outcome = "success"
        return _build_result(pool, floor, config.top_k_per_iteration, iterations_run, total_errors)
    except BaseException as exc:
        error_type = type(exc).__name__
        error_message = str(exc)
        raise
    finally:
        _log.info(
            "optimize_run",
            outcome=outcome,
            error_type=error_type,
            error_message=error_message,
            iterations_run=iterations_run,
            total_errors=total_errors,
            best_score=best_score,
            duration_ms=int((time.monotonic() - start_time) * 1000),
        )
        structlog.contextvars.unbind_contextvars("run_id")


async def _run_optimization_body(
    *,
    config: OptimizerConfig,
    metrics: list[Metric],
    scorer: CompositeScorer,
    progress_reporter: ProgressReporter,
    redaction_strategy: RedactionStrategy,
    prompt_render_strategy: RenderPromptStrategy,
    signal_rendering_strategy: SignalRenderingStrategy,
    structural_cleanup_predicate: StructuralCleanupPredicate,
    seed_doc: Document,
    n_cases: int,
    floor: int,
    warmup: int,
) -> tuple[list[Candidate], int, int, float]:
    pool: list[Candidate] = [Candidate(prompt=seed_doc, case_ids=list(range(n_cases)))]
    pool, bootstrap_errors = await select_top_candidates(
        candidates=pool,
        inputs=config.eval_cases,
        exploration_bonus=config.exploration_bonus,
        floor_size=warmup,
        ucb_budget=0,
        max_errors=config.error_budget,
        execution_config=config.target_llm,
        metrics=metrics,
        scorer=scorer,
    )

    iterations_run: int = 0
    total_errors: int = bootstrap_errors
    best_history: list[float] = []

    for iteration in range(1, config.iterations + 1):
        survivors: list[Candidate] = _select_survivors(pool, floor, config.top_k_per_iteration)
        if not survivors:
            break

        structlog.contextvars.bind_contextvars(round=iteration)
        try:
            _log.info("round.start", survivor_count=len(survivors), pool_size_in=len(pool))

            await _emit(progress_reporter, iteration, config.iterations, "revise", 1, best_history, total_errors)

            revise_results: list[list[Document]] = await asyncio.gather(
                *(
                    revise(
                        survivor,
                        feedback_llm_config=config.actor_llm,
                        structural_llm_config=config.structural_llm,
                        max_children=config.max_children_per_parent,
                        redaction_strategy=redaction_strategy,
                        prompt_render_strategy=prompt_render_strategy,
                        signal_rendering_strategy=signal_rendering_strategy,
                        structural_cleanup_predicate=structural_cleanup_predicate,
                    )
                    for survivor in survivors
                )
            )
            children_docs: list[Document] = [doc for docs in revise_results for doc in docs]

            if not children_docs:
                iterations_run += 1
                break

            children: list[Candidate] = [Candidate(prompt=doc, case_ids=list(range(n_cases))) for doc in children_docs]

            await _emit(progress_reporter, iteration, config.iterations, "evaluate", 2, best_history, total_errors)

            pool, iter_errors = await select_top_candidates(
                candidates=survivors + children,
                inputs=config.eval_cases,
                exploration_bonus=config.exploration_bonus,
                floor_size=floor,
                ucb_budget=config.ucb_budget,
                max_errors=config.error_budget,
                execution_config=config.target_llm,
                metrics=metrics,
                scorer=scorer,
            )
            total_errors += iter_errors
            iterations_run += 1

            best_history.append(_pool_best_score(pool, floor))
            if _should_early_stop(best_history, config.early_stop_patience, config.min_improvement_delta):
                break
        finally:
            structlog.contextvars.unbind_contextvars("round")

    best_score: float = _pool_best_score(pool, floor)
    return pool, total_errors, iterations_run, best_score


def _select_survivors(pool: list[Candidate], floor: int, top_k: int) -> list[Candidate]:
    floored: list[Candidate] = [c for c in pool if c.tested_count >= floor]
    floored.sort(key=lambda c: c.mean_score, reverse=True)
    return floored[:top_k]


def _pool_best_score(pool: list[Candidate], floor: int) -> float:
    floored: list[Candidate] = [c for c in pool if c.tested_count >= floor]
    if not floored:
        return 0.0
    return max(c.mean_score for c in floored)


def _should_early_stop(history: list[float], patience: int, min_delta: float) -> bool:
    if len(history) <= patience:
        return False
    improvement: float = history[-1] - history[-1 - patience]
    return improvement < min_delta


def _per_metric_means(results: list[MetricResult]) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for r in results:
        grouped[r.metric_name].append(r.score)
    return {name: sum(scores) / len(scores) for name, scores in grouped.items()}


def _build_result(pool: list[Candidate], floor: int, top_k: int, iterations_run: int, total_errors: int) -> OptimizationResult:
    floored: list[Candidate] = [c for c in pool if c.tested_count >= floor]
    floored.sort(key=lambda c: c.mean_score, reverse=True)

    if not floored:
        return OptimizationResult(
            best_prompt="",
            best_score=0.0,
            best_metrics={},
            top_k=[],
            iterations_run=iterations_run,
            total_errors=total_errors,
        )

    top: list[Candidate] = floored[:top_k]
    summaries: list[CandidateSummary] = [
        CandidateSummary(
            prompt=c.prompt.to_markdown(),
            score=c.mean_score,
            metrics=_per_metric_means(c.results),
        )
        for c in top
    ]
    best: Candidate = top[0]
    return OptimizationResult(
        best_prompt=best.prompt.to_markdown(),
        best_score=best.mean_score,
        best_metrics=_per_metric_means(best.results),
        top_k=summaries,
        iterations_run=iterations_run,
        total_errors=total_errors,
    )


async def _emit(
    reporter: ProgressReporter,
    current_run: int,
    total_runs: int,
    step_name: str,
    step_id: int,
    best_history: list[float],
    errors_so_far: int,
) -> None:
    if reporter is None:
        return
    best: float | None = best_history[-1] if best_history else None
    delta: float | None = None
    if len(best_history) >= 2:
        delta = best_history[-1] - best_history[-2]
    event: ProgressEvent = ProgressEvent(
        run_progress=RunProgress(total_runs=total_runs, current_run=current_run),
        step_progress=StepProgress(current_step_name=step_name, current_step_id=step_id, total_steps=2),
        task_progress=TaskProgress(current_task_name=step_name, current_task_id=1, total_tasks=1),
        best_score=best,
        best_score_delta=delta,
        errors_so_far=errors_so_far,
    )
    await reporter(event)
