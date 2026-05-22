import asyncio
import random
from typing import Any

from .._llm import acomplete
from .._metrics import Metric, MetricResult
from .._prompt import Document
from ..config import LiteLLMConfig
from ._input_pool import InputPool
from ._ucb import ArmStats, pick_arm
from .case import EvalCase
from .result import CandidateResult
from .reward import RewardStrategy


class BatchTestingErrorBudgetExceeded(Exception):
    """Raised when total metric/target failures exceed the caller-supplied error budget."""


class _CandidateState:
    __slots__ = ("metric_results", "pool", "stats", "successful_pulls")

    def __init__(self, num_inputs: int, rng: random.Random) -> None:
        self.pool: InputPool = InputPool(num_inputs, rng)
        self.stats: ArmStats = ArmStats()
        self.metric_results: list[MetricResult] = []
        self.successful_pulls: int = 0


def _build_messages(prompt_md: str, input_text: str) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": prompt_md},
        {"role": "user", "content": input_text},
    ]


async def _execute_pull(
    *,
    candidate: Document,
    case: EvalCase,
    metrics: list[Metric],
    target_config: LiteLLMConfig,
) -> list[MetricResult]:
    prompt_md: str = candidate.to_markdown()
    output: str = await acomplete(target_config, _build_messages(prompt_md, case.input))
    coros = [m.evaluate(prompt_md, case.input, output, case.ground_truth) for m in metrics]
    results: list[MetricResult] = list(await asyncio.gather(*coros))
    return results


async def _pull_and_record(
    *,
    state: _CandidateState,
    candidate: Document,
    case: EvalCase,
    metrics: list[Metric],
    target_config: LiteLLMConfig,
    reward_strategy: RewardStrategy,
) -> bool:
    """Run one pull. Decrements virtual_pulls when done. Returns True on success, False on failure."""
    try:
        results: list[MetricResult] = await _execute_pull(
            candidate=candidate,
            case=case,
            metrics=metrics,
            target_config=target_config,
        )
        reward: float = reward_strategy.compute(results)
        state.metric_results.extend(results)
        state.stats.record(reward)
        state.successful_pulls += 1
        return True
    except Exception:
        return False
    finally:
        state.stats.virtual_pulls -= 1


async def run_batch(
    candidates: list[Document],
    cases: list[EvalCase],
    metrics: list[Metric],
    target_config: LiteLLMConfig,
    reward_strategy: RewardStrategy,
    *,
    floor: int,
    ucb_budget: int,
    top_k: int | None,
    max_concurrency: int,
    exploration_bonus: float,
    error_budget: int,
    seed: int | None,
) -> list[CandidateResult]:
    if not candidates:
        return []
    if not cases:
        raise ValueError("run_batch requires at least one EvalCase")
    if not metrics:
        raise ValueError("run_batch requires at least one Metric")
    if floor < 0 or ucb_budget < 0 or max_concurrency < 1 or error_budget < 0 or exploration_bonus < 0:
        raise ValueError("Invalid numeric knob: floor/ucb_budget/error_budget must be >= 0, max_concurrency >= 1")

    effective_floor: int = min(floor, len(cases))
    rng: random.Random = random.Random(seed)
    states: list[_CandidateState] = [_CandidateState(len(cases), random.Random(rng.random())) for _ in candidates]

    semaphore: asyncio.Semaphore = asyncio.Semaphore(max_concurrency)
    error_count: int = 0
    error_lock: asyncio.Lock = asyncio.Lock()
    abort_event: asyncio.Event = asyncio.Event()

    async def _dispatch(candidate_idx: int, case_idx: int) -> None:
        nonlocal error_count
        try:
            ok: bool = await _pull_and_record(
                state=states[candidate_idx],
                candidate=candidates[candidate_idx],
                case=cases[case_idx],
                metrics=metrics,
                target_config=target_config,
                reward_strategy=reward_strategy,
            )
            if not ok:
                async with error_lock:
                    error_count += 1
                    if error_count > error_budget:
                        abort_event.set()
        finally:
            semaphore.release()

    async def _launch(candidate_idx: int, case_idx: int) -> asyncio.Task[None]:
        await semaphore.acquire()
        if abort_event.is_set():
            semaphore.release()
            raise BatchTestingErrorBudgetExceeded(f"Aborted: error count exceeded budget of {error_budget}")
        states[candidate_idx].stats.virtual_pulls += 1
        return asyncio.create_task(_dispatch(candidate_idx, case_idx))

    tasks: list[asyncio.Task[None]] = []

    try:
        # Floor phase: every candidate gets `effective_floor` distinct inputs.
        for ci, state in enumerate(states):
            for _ in range(effective_floor):
                if not state.pool.has_remaining():
                    break
                case_idx: int = state.pool.take()
                tasks.append(await _launch(ci, case_idx))

        # UCB phase: spend `ucb_budget` extras on the most promising arms.
        remaining_budget: int = ucb_budget
        while remaining_budget > 0:
            if abort_event.is_set():
                break
            eligible: list[tuple[int, ArmStats]] = [(i, s.stats) for i, s in enumerate(states) if s.pool.has_remaining()]
            if not eligible:
                break
            total_pulls: int = sum(s.stats.pulls + s.stats.virtual_pulls for s in states)
            chosen: int = pick_arm(eligible, total_pulls, exploration_bonus, rng_tiebreak=rng.randrange(1 << 30))
            case_idx_chosen: int = states[chosen].pool.take()
            remaining_budget -= 1
            tasks.append(await _launch(chosen, case_idx_chosen))

        if tasks:
            await asyncio.gather(*tasks)
    finally:
        # Drain anything still pending.
        pending: list[asyncio.Task[None]] = [t for t in tasks if not t.done()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    if abort_event.is_set():
        raise BatchTestingErrorBudgetExceeded(f"Aborted: {error_count} errors exceeded budget of {error_budget}")

    # Selection.
    eligible_results: list[tuple[float, int, _CandidateState]] = [
        (state.stats.mean, idx, state) for idx, state in enumerate(states) if state.successful_pulls >= effective_floor
    ]
    eligible_results.sort(key=lambda triple: (-triple[0], triple[1]))
    if top_k is not None:
        eligible_results = eligible_results[:top_k]

    return [CandidateResult(prompt=candidates[idx], results=state.metric_results) for _, idx, state in eligible_results]
