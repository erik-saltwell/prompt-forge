"""End-to-end GoEmotions benchmark: optimize, then score against the test set.

Mirrors the CJ benchmark's pipeline (settings from benchmark-settings.yaml;
NoRedaction + JsonRenderPromptStrategy + NeverCleanup), swapping in the
GoEmotions seed prompt, data loader, and per-case multi-label F1 metric.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from prompt_model import OptimizationResult, ProgressEvent, optimize_prompt
from prompt_model.config import OptimizerConfig
from prompt_model.strategies import (
    JsonRenderPromptStrategy,
    NeverCleanup,
    NoRedactionStrategy,
)
from prompt_model_metrics.benchmarking import GoEmotionsMultiLabelF1

from .data import load_initial_prompt, load_split
from .headline import HeadlineReport, evaluate_prompt

# SCULPT paper reports GoEmotions macro-F1 numbers; the exact split sizes differ
# from ours (we sample down for tractability), so these are reference points
# rather than strict pass criteria.
SCULPT_PUBLISHED_INITIAL_MACRO_F1: float = 32.5
SCULPT_PUBLISHED_OPTIMIZED_MACRO_F1: float = 42.8


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    initial: HeadlineReport
    optimized: HeadlineReport
    result: OptimizationResult


async def _stdout_progress(event: ProgressEvent) -> None:
    score: str = f"{event.best_score:.4f}" if event.best_score is not None else "-"
    delta: str = f"{event.best_score_delta:+.4f}" if event.best_score_delta is not None else "-"
    errors: int = event.errors_so_far or 0
    print(
        f"  [iter {event.run_progress.current_run:>2}/{event.run_progress.total_runs:>2} "
        f"| {event.step_progress.current_step_name:<10} "
        f"| best={score} Δ={delta} errors={errors}]",
        flush=True,
    )


async def run_ge_benchmark(*, max_concurrency: int | None = None, iterations: int | None = None) -> BenchmarkReport:
    """Run the full GoEmotions pipeline."""
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
    print(f"      Initial macro F1: {initial_headline.macro_f1 * 100:.2f}", file=sys.stderr, flush=True)

    print(
        f"[2/3] Optimizing on {len(config.eval_cases)} train+val cases (up to {config.iterations} iterations)...",
        file=sys.stderr,
        flush=True,
    )
    result: OptimizationResult = await optimize_prompt(
        config,
        metrics=[GoEmotionsMultiLabelF1(judge_llm=config.judge_llm)],
        progress_reporter=_stdout_progress,
        redaction_strategy=NoRedactionStrategy(),
        prompt_render_strategy=JsonRenderPromptStrategy(),
        structural_cleanup_decider=NeverCleanup(),
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
    print(f"      Optimized macro F1: {optimized_headline.macro_f1 * 100:.2f}", file=sys.stderr, flush=True)

    return BenchmarkReport(initial=initial_headline, optimized=optimized_headline, result=result)


def format_report(report: BenchmarkReport) -> str:
    init_macro: float = report.initial.macro_f1 * 100
    opt_macro: float = report.optimized.macro_f1 * 100
    init_micro: float = report.initial.micro_f1 * 100
    opt_micro: float = report.optimized.micro_f1 * 100
    init_weighted: float = report.initial.weighted_f1 * 100
    opt_weighted: float = report.optimized.weighted_f1 * 100
    init_exact: float = report.initial.exact_match_accuracy * 100
    opt_exact: float = report.optimized.exact_match_accuracy * 100

    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("GoEmotions — multi-label benchmark")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"{'':30}{'Macro F1':>12}{'Micro F1':>12}{'Weighted F1':>14}{'Exact':>10}")
    lines.append(f"{'Initial prompt':30}{init_macro:>12.2f}{init_micro:>12.2f}{init_weighted:>14.2f}{init_exact:>10.2f}")
    lines.append(f"{'Optimized prompt':30}{opt_macro:>12.2f}{opt_micro:>12.2f}{opt_weighted:>14.2f}{opt_exact:>10.2f}")
    lines.append(f"{'SCULPT published initial':30}{SCULPT_PUBLISHED_INITIAL_MACRO_F1:>12.2f}{'-':>12}{'-':>14}{'-':>10}")
    lines.append(f"{'SCULPT published optimized':30}{SCULPT_PUBLISHED_OPTIMIZED_MACRO_F1:>12.2f}{'-':>12}{'-':>14}{'-':>10}")
    lines.append("")
    lines.append(f"Delta vs SCULPT optimized (macro F1): {opt_macro - SCULPT_PUBLISHED_OPTIMIZED_MACRO_F1:+.2f}")
    lines.append(f"Iterations run:            {report.result.iterations_run}")
    lines.append(f"Total optimizer errors:    {report.result.total_errors}")
    lines.append(f"Empty-prediction cases:    initial={report.initial.n_unparseable}, optimized={report.optimized.n_unparseable}")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Optimized prompt:")
    lines.append("-" * 70)
    lines.append(report.result.best_prompt)
    return "\n".join(lines)
