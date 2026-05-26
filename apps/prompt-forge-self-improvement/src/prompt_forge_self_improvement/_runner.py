"""Generic optimization runner for any registered target."""

from __future__ import annotations

from pathlib import Path

import structlog
from prompt_model import Metric, OptimizationResult, optimize_prompt
from prompt_model.config import LiteLLMConfig, OptimizerConfig

from ._registry import TargetConfig

_log = structlog.get_logger()


async def run_target(
    target: TargetConfig,
    output_path: Path,
    model: str,
    iterations: int,
    concurrency: int,
) -> OptimizationResult:
    """Load a target's seed prompt and eval cases, optimize, and write the result."""
    seed_prompt: str = target.seed_prompt_loader()
    eval_cases = target.eval_case_loader()

    if not eval_cases:
        raise ValueError(f"Target '{target.name}' returned no evaluation cases.")

    llm_cfg = LiteLLMConfig(model=model)
    metrics: list[Metric] = target.metrics_factory(llm_cfg)

    _log.info(
        "starting_optimization",
        target=target.name,
        model=model,
        iterations=iterations,
        concurrency=concurrency,
        eval_cases=len(eval_cases),
        metrics=len(metrics),
    )

    # Allow a generous number of transient evaluation errors per iteration phase.
    # At high concurrency, LLM judge ValidationErrors and occasional rate-limit
    # responses can fail individual evaluations; the optimizer can still make progress
    # as long as enough evaluations succeed.  Budget = number of eval cases gives
    # the same resilience ceiling regardless of dataset size.
    error_budget: int = len(eval_cases)

    config = OptimizerConfig(
        seed_prompt=seed_prompt,
        eval_cases=eval_cases,
        target_llm=llm_cfg,
        actor_llm=llm_cfg,
        judge_llm=llm_cfg,
        iterations=iterations,
        max_llm_concurrency=concurrency,
        error_budget=error_budget,
    )

    result: OptimizationResult = await optimize_prompt(config=config, metrics=metrics)

    output_path.write_text(result.best_prompt, encoding="utf-8")
    _log.info(
        "optimization_complete",
        target=target.name,
        iterations_run=result.iterations_run,
        best_score=result.best_score,
        output=str(output_path),
    )
    return result
