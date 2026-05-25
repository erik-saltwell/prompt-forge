from __future__ import annotations

import asyncio
import time

import structlog

from .._llm import acomplete
from .._metrics import Metric, MetricResult
from .._utils.identity import candidate_id_of
from ..config import EvalCase, LiteLLMConfig
from .composite_scorer import CompositeScorer
from .selection_data import _SelectionData

_log = structlog.get_logger()


async def _evaluate_one_metric(
    metric: Metric,
    prompt_text: str,
    eval_input: str,
    output: str,
    ground_truth: str | None,
) -> MetricResult:
    structlog.contextvars.bind_contextvars(metric_name=metric.name)
    start: float = time.monotonic()
    outcome: str = "error"
    error_type: str | None = None
    error_message: str | None = None
    score_val: float | None = None
    signal_count: int = 0
    try:
        result: MetricResult = await metric.evaluate(prompt_text, eval_input, output, ground_truth)
        score_val = result.score
        signal_count = len(result.signals)
        outcome = "success"
        return result
    except BaseException as exc:
        error_type = type(exc).__name__
        error_message = str(exc)
        raise
    finally:
        _log.info(
            "metric_evaluation",
            outcome=outcome,
            error_type=error_type,
            error_message=error_message,
            score=score_val,
            signal_count=signal_count,
            has_ground_truth=ground_truth is not None,
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        structlog.contextvars.unbind_contextvars("metric_name")


async def evaluate_candidate(
    selection_data: _SelectionData,
    inputs: list[EvalCase],
    execution_config: LiteLLMConfig,
    metrics: list[Metric],
    scorer: CompositeScorer,
) -> None:
    if not metrics:
        raise ValueError("evaluate_candidate requires at least one metric")
    if not selection_data.has_cases:
        raise ValueError("evaluate candidate requires a candidate with untested inputs")

    complete: bool = False
    case_id: int = selection_data.start_evaluation()

    candidate_id: str = candidate_id_of(selection_data.candidate.prompt)
    structlog.contextvars.bind_contextvars(candidate_id=candidate_id, case_id=case_id)
    start: float = time.monotonic()
    outcome: str = "error"
    error_type: str | None = None
    error_message: str | None = None
    num_validation_errors: int = 0
    num_transport_errors: int = 0
    mean_score: float | None = None

    try:
        prompt_text: str = selection_data.candidate.prompt.to_markdown()
        eval_case: EvalCase = inputs[case_id]
        output: str = await acomplete(prompt_text, eval_case.input, execution_config, log_name="candidate_evaluator")
        raw_results: list[MetricResult | BaseException] = await asyncio.gather(
            *(_evaluate_one_metric(m, prompt_text, eval_case.input, output, eval_case.ground_truth) for m in metrics),
            return_exceptions=True,
        )
        metric_results: list[MetricResult] = []
        for result in raw_results:
            if isinstance(result, BaseException):
                exc_name: str = type(result).__name__
                if "Validation" in exc_name or exc_name == "ValidationError":
                    num_validation_errors += 1
                else:
                    num_transport_errors += 1
                raise result
            metric_results.append(result)
        score: float
        if not metric_results:
            score = 1.0
        else:
            score = scorer.compute(metric_results)
        mean_score = score
        selection_data.complete_evaluation(metric_results, score)
        complete = True
        outcome = "success"
    except BaseException as exc:
        error_type = type(exc).__name__
        error_message = str(exc)
        raise
    finally:
        _log.info(
            "critic_evaluation",
            outcome=outcome,
            error_type=error_type,
            error_message=error_message,
            num_metrics=len(metrics),
            num_validation_errors=num_validation_errors,
            num_transport_errors=num_transport_errors,
            mean_score=mean_score,
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        structlog.contextvars.unbind_contextvars("candidate_id", "case_id")
        if not complete:
            selection_data.rollback_evaluation(case_id)
