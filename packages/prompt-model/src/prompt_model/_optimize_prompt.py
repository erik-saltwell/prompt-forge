from ._batch_testing import RewardStrategy
from ._metrics.protocol import Metric
from ._progress import ProgressReporter
from ._prompt import Document
from ._result import OptimizationResult
from .config import OptimizerConfig


async def optimize_prompt(
    config: OptimizerConfig,
    metrics: list[Metric],
    scorer: RewardStrategy,
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


async def run_single_loop(
    candidates: list[Document], config: OptimizerConfig, metrics: list[Metric], scorer: RewardStrategy, progress_reporter: ProgressReporter
) -> OptimizationResult:
    # candidate_results: list[CandidateResult] = await run_batch(
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
    # for candidate_result in candidate_results:
    #     aggregate: agg.AggregationResult = agg.aggregate(candidate_result.results)
    #     for bucket in aggregate.buckets:
    #         _ = bucket

    raise NotImplementedError("optimize_prompt body not yet implemented")
    # Grab the input prompt, add to candidate pool
    # for run in runs:
    # Batch Test based on candidate pool:  get back top k and metric results
    # for candidate in top k:
    # agregate results.
    # for prompt in problematic prompts:
    # send to actor
    # generate actions from inputs
    # create new prompt
    # add into candidate pool
