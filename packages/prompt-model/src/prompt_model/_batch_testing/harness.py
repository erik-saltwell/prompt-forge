import asyncio
import math

from .._metrics import Metric
from .._prompt import Document
from ..config import LiteLLMConfig
from ._runner import run_batch as _run_batch
from .case import EvalCase
from .result import CandidateResult
from .reward import MeanReward, RewardStrategy

DEFAULT_EXPLORATION_BONUS: float = math.sqrt(2)


async def run_batch(
    candidates: list[Document],
    cases: list[EvalCase],
    metrics: list[Metric],
    target_config: LiteLLMConfig,
    reward_strategy: RewardStrategy | None = None,
    *,
    floor: int,
    ucb_budget: int,
    top_k: int | None = None,
    max_concurrency: int = 4,
    exploration_bonus: float = DEFAULT_EXPLORATION_BONUS,
    error_budget: int = 0,
    seed: int | None = None,
) -> list[CandidateResult]:
    """Evaluate candidate prompts against eval cases via UCB1-driven sampling and return the top-K ranked.

    See docs/batch-testing.md for the full contract.
    """
    strategy: RewardStrategy = reward_strategy if reward_strategy is not None else MeanReward()
    return await _run_batch(
        candidates,
        cases,
        metrics,
        target_config,
        strategy,
        floor=floor,
        ucb_budget=ucb_budget,
        top_k=top_k,
        max_concurrency=max_concurrency,
        exploration_bonus=exploration_bonus,
        error_budget=error_budget,
        seed=seed,
    )


def run_batch_sync(
    candidates: list[Document],
    cases: list[EvalCase],
    metrics: list[Metric],
    target_config: LiteLLMConfig,
    reward_strategy: RewardStrategy | None = None,
    *,
    floor: int,
    ucb_budget: int,
    top_k: int | None = None,
    max_concurrency: int = 4,
    exploration_bonus: float = DEFAULT_EXPLORATION_BONUS,
    error_budget: int = 0,
    seed: int | None = None,
) -> list[CandidateResult]:
    """Synchronous convenience wrapper around `run_batch`."""
    return asyncio.run(
        run_batch(
            candidates,
            cases,
            metrics,
            target_config,
            reward_strategy,
            floor=floor,
            ucb_budget=ucb_budget,
            top_k=top_k,
            max_concurrency=max_concurrency,
            exploration_bonus=exploration_bonus,
            error_budget=error_budget,
            seed=seed,
        )
    )
