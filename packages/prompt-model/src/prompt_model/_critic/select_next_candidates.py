from __future__ import annotations

import asyncio

from .._candidate import Candidate
from .._metrics import Metric
from ..config import EvalCase, LiteLLMConfig
from .candidate_evaluator import evaluate_candidate
from .candidate_picker import pick_next_ucb
from .composite_scorer import CompositeScorer
from .selection_data import _SelectionData


class TooManyEvaluationErrorsError(RuntimeError):
    pass


async def process_floor(
    candidates: list[_SelectionData],
    floor_size: int,
    inputs: list[EvalCase],
    execution_config: LiteLLMConfig,
    metrics: list[Metric],
    scorer: CompositeScorer,
    max_errors: int,
) -> int:
    error_count: int = 0
    round_candidates: list[_SelectionData] = [c for c in candidates if c.has_cases and c.completed_tests_this_run < floor_size]
    while round_candidates:
        tasks: list[asyncio.Task[None]] = []
        for candidate in round_candidates:
            tasks.append(
                asyncio.create_task(
                    evaluate_candidate(
                        selection_data=candidate,
                        inputs=inputs,
                        execution_config=execution_config,
                        metrics=metrics,
                        scorer=scorer,
                    )
                )
            )

        results: list[None | BaseException] = await asyncio.gather(*tasks, return_exceptions=True)
        error_count += sum(isinstance(r, BaseException) for r in results)
        if error_count > max_errors:
            msg = f"Exceeded max evaluation errors: {error_count} > {max_errors}"
            raise TooManyEvaluationErrorsError(msg)
        round_candidates = [c for c in candidates if c.has_cases and c.completed_tests_this_run < floor_size]

    return error_count


async def process_ucb(
    candidates: list[_SelectionData],
    ucb_budget: int,
    inputs: list[EvalCase],
    execution_config: LiteLLMConfig,
    metrics: list[Metric],
    scorer: CompositeScorer,
    max_errors: int,
    error_count: int,
    exploration_bonus: float,
) -> int:
    successful_pulls: int = 0
    total_errors: int = error_count
    while successful_pulls < ucb_budget:
        candidate: _SelectionData | None = pick_next_ucb(candidates, exploration_bonus)
        if candidate is None:
            break

        try:
            await evaluate_candidate(
                selection_data=candidate,
                inputs=inputs,
                execution_config=execution_config,
                metrics=metrics,
                scorer=scorer,
            )
        except Exception as exc:
            total_errors += 1
            if total_errors > max_errors:
                msg = f"Exceeded max evaluation errors: {total_errors} > {max_errors}"
                raise TooManyEvaluationErrorsError(msg) from exc
            continue

        successful_pulls += 1

    return total_errors


async def select_top_candidates(
    candidates: list[Candidate],
    inputs: list[EvalCase],
    exploration_bonus: float,
    floor_size: int,
    ucb_budget: int,
    max_errors: int,
    execution_config: LiteLLMConfig,
    metrics: list[Metric],
    scorer: CompositeScorer,
) -> tuple[list[Candidate], int]:
    selection_data: list[_SelectionData] = [_SelectionData(candidate) for candidate in candidates]
    floor_errors: int = await process_floor(selection_data, floor_size, inputs, execution_config, metrics, scorer, max_errors)
    total_errors: int = await process_ucb(
        selection_data, ucb_budget, inputs, execution_config, metrics, scorer, max_errors, floor_errors, exploration_bonus
    )
    for selection in selection_data:
        selection.integrate_results_into_candidate()
    return [selection.candidate for selection in selection_data], total_errors
