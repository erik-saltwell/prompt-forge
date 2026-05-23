from ._metrics.protocol import Metric
from ._progress import ProgressReporter
from ._result import OptimizationResult
from .config import OptimizerConfig


async def optimize_prompt(
    config: OptimizerConfig,
    metrics: list[Metric],
    #    scorer: RewardStrategy,
    progress_reporter: ProgressReporter = None,
) -> OptimizationResult:
    """Optimize a prompt against a set of evaluation cases. See docs/public-facade.md."""
    # initial_candidate: Document = parse_from_string(config.seed_prompt)
    # candidates: list[Document] = [initial_candidate]
    # await run_batch(
    #     candidates=candidates,
    #     cases=config.eval_cases,
    #     metrics=metrics,
    #     target_config=config.target_llm,
    #     reward_strategy=scorer,
    #     floor=config.floor,
    #     ucb_budget=config.ucb_budget,
    #     top_k=config.top_k_per_iteration,
    #     max_concurrency=6,
    #     exploration_bonus=config.exploration_bonus,
    #     error_budget=config.error_budget,
    #     seed=3141,
    # )
    raise NotImplementedError()
