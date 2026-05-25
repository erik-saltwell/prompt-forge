"""End-to-end CJ benchmark: optimize, then score against the test set.

Phase 1 config per docs/benchmarking.md:
  - GPT-4o for target, actor, judge (model strength held fixed vs SCULPT).
  - Three "cheap switches" flipped vs prompt-forge defaults:
      * RedactionStrategy   -> NoRedactionStrategy (keep everything)
      * RenderPromptStrategy -> JsonRenderPromptStrategy
      * structural cleanup  -> never_cleanup_structure
  - Everything else at prompt-forge defaults.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from prompt_model import OptimizationResult, ProgressEvent, optimize_prompt
from prompt_model._actor import (
    JsonRenderPromptStrategy,
    NoRedactionStrategy,
    never_cleanup_structure,
)
from prompt_model.config import OptimizerConfig

from .data import load_initial_prompt, load_split
from .headline import HeadlineReport, evaluate_prompt
from .metric import CausalJudgementCorrectness

SCULPT_PUBLISHED_INITIAL_F1: float = 71.1
SCULPT_PUBLISHED_OPTIMIZED_F1: float = 75.9


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    initial: HeadlineReport
    optimized: HeadlineReport
    result: OptimizationResult


async def _stdout_progress(event: ProgressEvent) -> None:
    """Single-line progress emitter — prints when entering a new run or step.

    Optimizer fires events both before and after each coarse step; we keep it
    terse: one line per (run, step) transition with best-score snapshot.
    """
    score: str = f"{event.best_score:.4f}" if event.best_score is not None else "-"
    delta: str = f"{event.best_score_delta:+.4f}" if event.best_score_delta is not None else "-"
    errors: int = event.errors_so_far or 0
    print(
        f"  [iter {event.run_progress.current_run:>2}/{event.run_progress.total_runs:>2} "
        f"| {event.step_progress.current_step_name:<10} "
        f"| best={score} Δ={delta} errors={errors}]",
        flush=True,
    )


async def run_cj_benchmark(*, max_concurrency: int | None = None, iterations: int | None = None) -> BenchmarkReport:
    """Run the full CJ Phase 1 pipeline."""
    initial_prompt: str = load_initial_prompt()
    test_cases = load_split("test")

    config: OptimizerConfig = OptimizerConfig.from_yaml(
        "benchmark-settings.yaml",
        seed_prompt=initial_prompt,
        eval_cases=load_split("train") + load_split("val"),
    )

    if iterations is not None:
        config = config.with_iterations(iterations)
    if max_concurrency is not None:
        config = config.with_max_llm_concurrency(max_concurrency)

    active_concurrency = config.max_llm_concurrency
    target_llm = config.target_llm

    print(f"[1/3] Scoring initial prompt on {len(test_cases)} test cases...", file=sys.stderr, flush=True)
    initial_headline: HeadlineReport = await evaluate_prompt(initial_prompt, test_cases, target_llm, max_concurrency=active_concurrency)
    print(f"      Initial weighted F1: {initial_headline.weighted_f1 * 100:.2f}", file=sys.stderr, flush=True)

    print(
        f"[2/3] Optimizing on {len(config.eval_cases)} train+val cases (up to {config.iterations} iterations)...",
        file=sys.stderr,
        flush=True,
    )
    result: OptimizationResult = await optimize_prompt(
        config,
        metrics=[CausalJudgementCorrectness(judge_llm=config.judge_llm)],
        progress_reporter=_stdout_progress,
        redaction_strategy=NoRedactionStrategy(),
        prompt_render_strategy=JsonRenderPromptStrategy(),
        structural_cleanup_predicate=never_cleanup_structure,
    )
    print(
        f"      Optimization done: {result.iterations_run} iterations, best_score={result.best_score:.4f}",
        file=sys.stderr,
        flush=True,
    )

    print(f"[3/3] Scoring optimized prompt on {len(test_cases)} test cases...", file=sys.stderr, flush=True)
    optimized_headline: HeadlineReport = await evaluate_prompt(
        result.best_prompt, test_cases, target_llm, max_concurrency=active_concurrency
    )
    print(f"      Optimized weighted F1: {optimized_headline.weighted_f1 * 100:.2f}", file=sys.stderr, flush=True)

    return BenchmarkReport(initial=initial_headline, optimized=optimized_headline, result=result)


def format_report(report: BenchmarkReport) -> str:
    init_f1: float = report.initial.weighted_f1 * 100
    opt_f1: float = report.optimized.weighted_f1 * 100
    init_acc: float = report.initial.accuracy * 100
    opt_acc: float = report.optimized.accuracy * 100

    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("Causal Judgement — Phase 1 benchmark")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"{'':30}{'F1 (weighted)':>20}{'Accuracy':>15}")
    lines.append(f"{'Initial prompt':30}{init_f1:>20.2f}{init_acc:>15.2f}")
    lines.append(f"{'Optimized prompt':30}{opt_f1:>20.2f}{opt_acc:>15.2f}")
    lines.append(f"{'SCULPT published initial':30}{SCULPT_PUBLISHED_INITIAL_F1:>20.2f}{'-':>15}")
    lines.append(f"{'SCULPT published optimized':30}{SCULPT_PUBLISHED_OPTIMIZED_F1:>20.2f}{'-':>15}")
    lines.append("")
    lines.append(f"Delta vs SCULPT optimized: {opt_f1 - SCULPT_PUBLISHED_OPTIMIZED_F1:+.2f}")
    lines.append(f"Iterations run:            {report.result.iterations_run}")
    lines.append(f"Total optimizer errors:    {report.result.total_errors}")
    lines.append(f"Unparseable on test set:   initial={report.initial.n_unparseable}, optimized={report.optimized.n_unparseable}")

    floor: float = SCULPT_PUBLISHED_INITIAL_F1 + 3.0
    goal_lo: float = SCULPT_PUBLISHED_OPTIMIZED_F1 - 2.0
    goal_hi: float = SCULPT_PUBLISHED_OPTIMIZED_F1 + 2.0
    lines.append("")
    lines.append(f"Pass criteria: floor >= {floor:.1f}, goal {goal_lo:.1f}-{goal_hi:.1f}")
    if opt_f1 >= goal_lo:
        verdict: str = "GOAL HIT — skip Phase 2"
    elif opt_f1 >= floor:
        verdict = "ABOVE FLOOR — proceed to Phase 2 tuning"
    else:
        verdict = "BELOW FLOOR — likely bug, do not tune"
    lines.append(f"Verdict: {verdict}")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Optimized prompt:")
    lines.append("-" * 70)
    lines.append(report.result.best_prompt)
    return "\n".join(lines)
