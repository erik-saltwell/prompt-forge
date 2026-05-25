import argparse
import asyncio
import sys
from pathlib import Path

import structlog
from prompt_model import optimize_prompt
from prompt_model.config import EvalCase, OptimizerConfig

from prompt_forge.metrics import GenericLLMJudgeMetric
from prompt_forge.settings import PromptForgeSettings

_log = structlog.get_logger()


def load_eval_cases(eval_data_dir: str | None) -> list[EvalCase]:
    cases = []
    if not eval_data_dir:
        return cases
    p = Path(eval_data_dir)
    if not p.is_dir():
        _log.warning("Eval data dir not found or not a directory", path=eval_data_dir)
        return cases

    for f in p.glob("*"):
        if f.is_file():
            content = f.read_text(encoding="utf-8")
            cases.append(EvalCase(input=content))
    return cases


async def amain() -> None:
    parser = argparse.ArgumentParser(description="prompt-forge CLI")
    parser.add_argument("input", type=Path, help="Path to the initial prompt markdown file.")
    parser.add_argument("output", type=Path, help="Path to write the optimized prompt markdown file.")
    parser.add_argument("--settings", type=Path, required=True, help="Path to a YAML configuration file.")

    args = parser.parse_args()

    initial_prompt = args.input.read_text(encoding="utf-8")

    if not args.settings.exists():
        parser.error(f"Settings file not found at {args.settings}")

    settings = PromptForgeSettings.load(args.settings)

    eval_cases = load_eval_cases(settings.eval_data_dir)
    if not eval_cases:
        _log.warning("No evaluation cases loaded. Optimization requires at least one eval case.")

    config = OptimizerConfig(
        seed_prompt=initial_prompt,
        eval_cases=eval_cases,
        target_llm=settings.target_llm,
        actor_llm=settings.actor_llm,
        judge_llm=settings.judge_llm,
        iterations=settings.iterations,
        early_stop_patience=settings.early_stop_patience,
        max_llm_concurrency=settings.max_llm_concurrency,
        top_k_per_iteration=settings.top_k_per_iteration,
        floor=settings.floor,
        ucb_budget=settings.ucb_budget,
        seed_warmup_pulls=settings.seed_warmup_pulls,
        max_children_per_parent=settings.max_children_per_parent,
        min_improvement_delta=settings.min_improvement_delta,
        exploration_bonus=settings.exploration_bonus,
        error_budget=settings.error_budget,
        seed=settings.seed,
    )

    metrics = []
    for mc in settings.metrics:
        metrics.append(GenericLLMJudgeMetric(name=mc.name, description=mc.description, rubric=mc.rubric, judge_llm=settings.judge_llm))

    if not metrics:
        parser.error("No metrics configured in settings.yaml. At least one metric is required.")

    print(f"Starting optimization with {len(eval_cases)} eval cases and {len(metrics)} metrics...")

    result = await optimize_prompt(
        config=config,
        metrics=metrics,
    )

    print(f"Optimization finished in {result.iterations_run} iterations. Best score: {result.best_score:.4f}")
    args.output.write_text(result.best_prompt, encoding="utf-8")
    print(f"Optimized prompt written to {args.output}")


def main() -> int:
    try:
        asyncio.run(amain())
        return 0
    except Exception as e:
        _log.error("Optimization failed", error=str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
