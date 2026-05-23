from __future__ import annotations

import asyncio

from .._candidate import Candidate
from .._llm import acomplete
from .._metrics import EvalCase, Metric, MetricResult, MissingGroundTruthError
from ..config import LiteLLMConfig
from ..scorers import CompositeScorer


async def run_test(
    candidate: Candidate,
    inputs: list[EvalCase],
    execution_config: LiteLLMConfig,
    metrics: list[Metric],
    scorer: CompositeScorer,
) -> None:
    case_id: int = candidate.take_case_id()
    committed: bool = False
    try:
        prompt_text: str = candidate.prompt.to_markdown()
        eval_case: EvalCase = inputs[case_id]
        output: str = await acomplete(prompt_text, eval_case.input, execution_config)
        raw_results: list[MetricResult | BaseException] = await asyncio.gather(
            *(m.evaluate(prompt_text, eval_case.input, output, eval_case.ground_truth) for m in metrics),
            return_exceptions=True,
        )
        metric_results: list[MetricResult] = []
        for result in raw_results:
            if isinstance(result, MissingGroundTruthError):
                continue
            if isinstance(result, BaseException):
                raise result
            metric_results.append(result)
        score: float
        if not metric_results:
            score = 1.0
        else:
            score = scorer.compute(metric_results)
        candidate.record_result(metric_results=metric_results, reward=score)
        committed = True
    finally:
        if not committed:
            candidate.revert_case(case_id)
