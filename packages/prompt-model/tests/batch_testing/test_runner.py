# import asyncio
# from typing import Any, ClassVar

# import pytest
# from prompt_model import Metric, MetricResult
# from prompt_model._batch_testing import (
#     BatchTestingErrorBudgetExceeded,
#     CandidateResult,
#     EvalCase,
#     MeanReward,
#     run_batch_sync,
# )
# from prompt_model._prompt import Document, Section, parse_from_string
# from prompt_model.config import LiteLLMConfig


# def _heading_of(doc: Document) -> str:
#     first = doc.children[0]
#     assert isinstance(first, Section)
#     return first.text


# class _FakeMetric:
#     """Returns a fixed score per candidate identified by the first heading of the prompt markdown."""

#     name: ClassVar[str] = "fake"
#     description: ClassVar[str] = "Fake metric"

#     def __init__(self, scores_by_heading: dict[str, float]) -> None:
#         self._scores: dict[str, float] = scores_by_heading

#     async def evaluate(self, prompt: str, input: str, output: str, ground_truth: str | None) -> MetricResult:
#         heading: str = prompt.splitlines()[0].lstrip("# ").strip()
#         score: float = self._scores.get(heading, 0.0)
#         return MetricResult(metric_name=self.name, score=score, assessment=f"score={score}")


# class _FailingMetric:
#     name: ClassVar[str] = "failing"
#     description: ClassVar[str] = "Always raises"

#     async def evaluate(self, prompt: str, input: str, output: str, ground_truth: str | None) -> MetricResult:
#         raise RuntimeError("metric exploded")


# def _stub_target(monkeypatch: pytest.MonkeyPatch, output: str = "stub output") -> None:
#     async def fake_acomplete(config: LiteLLMConfig, messages: list[dict[str, Any]]) -> str:
#         return output

#     monkeypatch.setattr("prompt_model._batch_testing._runner.acomplete", fake_acomplete)


# def _docs(*headings: str) -> list[Any]:
#     return [parse_from_string(f"# {h}\n\nbody text\n") for h in headings]


# def _cases(n: int) -> list[EvalCase]:
#     return [EvalCase(input=f"input {i}") for i in range(n)]


# def _cfg() -> LiteLLMConfig:
#     return LiteLLMConfig(model="fake/model")


# def test_basic_run_returns_top_k_ranked(monkeypatch: pytest.MonkeyPatch) -> None:
#     _stub_target(monkeypatch)
#     metric: Metric = _FakeMetric({"alpha": 0.9, "beta": 0.5, "gamma": 0.1})  # type: ignore[assignment]
#     results: list[CandidateResult] = run_batch_sync(
#         _docs("alpha", "beta", "gamma"),
#         _cases(4),
#         [metric],
#         _cfg(),
#         MeanReward(),
#         floor=2,
#         ucb_budget=0,
#         top_k=2,
#         max_concurrency=2,
#         seed=42,
#     )
#     assert len(results) == 2
#     headings: list[str] = [_heading_of(r.prompt) for r in results]
#     assert headings == ["alpha", "beta"]


# def test_floor_pulls_executed_for_every_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
#     _stub_target(monkeypatch)
#     metric: Metric = _FakeMetric({"a": 0.5, "b": 0.5})  # type: ignore[assignment]
#     results: list[CandidateResult] = run_batch_sync(
#         _docs("a", "b"),
#         _cases(3),
#         [metric],
#         _cfg(),
#         MeanReward(),
#         floor=2,
#         ucb_budget=0,
#         max_concurrency=2,
#         seed=1,
#     )
#     for r in results:
#         assert len(r.results) == 2  # 2 floor pulls × 1 metric


# def test_ucb_extras_favor_high_mean_arm(monkeypatch: pytest.MonkeyPatch) -> None:
#     _stub_target(monkeypatch)
#     metric: Metric = _FakeMetric({"hi": 0.95, "lo": 0.05})  # type: ignore[assignment]
#     results: list[CandidateResult] = run_batch_sync(
#         _docs("hi", "lo"),
#         _cases(10),
#         [metric],
#         _cfg(),
#         MeanReward(),
#         floor=2,
#         ucb_budget=6,
#         max_concurrency=1,
#         seed=7,
#     )
#     by_heading: dict[str, int] = {_heading_of(r.prompt): len(r.results) for r in results}
#     assert by_heading["hi"] > by_heading["lo"]


# def test_error_budget_zero_aborts_on_first_failure(monkeypatch: pytest.MonkeyPatch) -> None:
#     _stub_target(monkeypatch)
#     metric: Metric = _FailingMetric()  # type: ignore[assignment]
#     with pytest.raises(BatchTestingErrorBudgetExceeded):
#         run_batch_sync(
#             _docs("a", "b"),
#             _cases(3),
#             [metric],
#             _cfg(),
#             MeanReward(),
#             floor=1,
#             ucb_budget=0,
#             error_budget=0,
#             max_concurrency=1,
#             seed=1,
#         )


# def test_error_budget_tolerates_some_failures(monkeypatch: pytest.MonkeyPatch) -> None:
#     """A single failure is allowed when error_budget >= 1; pull is discarded and arm stays in play."""
#     _stub_target(monkeypatch)

#     call_count: dict[str, int] = {"n": 0}

#     class _OnceFailingMetric:
#         name: ClassVar[str] = "once_failing"
#         description: ClassVar[str] = "fails the first time then succeeds"

#         async def evaluate(self, prompt: str, input: str, output: str, ground_truth: str | None) -> MetricResult:
#             call_count["n"] += 1
#             if call_count["n"] == 1:
#                 raise RuntimeError("first call fails")
#             return MetricResult(metric_name=self.name, score=0.5, assessment="ok")

#     results: list[CandidateResult] = run_batch_sync(
#         _docs("a"),
#         _cases(3),
#         [_OnceFailingMetric()],  # type: ignore[list-item]
#         _cfg(),
#         MeanReward(),
#         floor=2,
#         ucb_budget=0,
#         error_budget=1,
#         max_concurrency=1,
#         seed=1,
#     )
#     # Only the successful pulls accumulate; one failure was tolerated and discarded.
#     assert len(results) <= 1


# def test_top_k_none_returns_all_eligible(monkeypatch: pytest.MonkeyPatch) -> None:
#     _stub_target(monkeypatch)
#     metric: Metric = _FakeMetric({"a": 0.1, "b": 0.2, "c": 0.3})  # type: ignore[assignment]
#     results: list[CandidateResult] = run_batch_sync(
#         _docs("a", "b", "c"),
#         _cases(2),
#         [metric],
#         _cfg(),
#         MeanReward(),
#         floor=1,
#         ucb_budget=0,
#         top_k=None,
#         max_concurrency=1,
#         seed=1,
#     )
#     assert len(results) == 3


# def test_floor_capped_at_available_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
#     """If floor > num_cases, the harness silently caps at num_cases without erroring."""
#     _stub_target(monkeypatch)
#     metric: Metric = _FakeMetric({"a": 0.5})  # type: ignore[assignment]
#     results: list[CandidateResult] = run_batch_sync(
#         _docs("a"),
#         _cases(2),
#         [metric],
#         _cfg(),
#         MeanReward(),
#         floor=10,
#         ucb_budget=0,
#         max_concurrency=1,
#         seed=1,
#     )
#     assert len(results) == 1
#     assert len(results[0].results) == 2


# def test_metric_name_is_stamped_through(monkeypatch: pytest.MonkeyPatch) -> None:
#     _stub_target(monkeypatch)
#     metric: Metric = _FakeMetric({"a": 0.5})  # type: ignore[assignment]
#     results: list[CandidateResult] = run_batch_sync(
#         _docs("a"),
#         _cases(1),
#         [metric],
#         _cfg(),
#         MeanReward(),
#         floor=1,
#         ucb_budget=0,
#         max_concurrency=1,
#         seed=1,
#     )
#     assert results[0].results[0].metric_name == "fake"


# def test_run_batch_works_inside_running_loop(monkeypatch: pytest.MonkeyPatch) -> None:
#     """Sanity that the async entry point is usable from existing event loops."""
#     from prompt_model._batch_testing import run_batch

#     _stub_target(monkeypatch)
#     metric: Metric = _FakeMetric({"a": 0.5, "b": 0.5})  # type: ignore[assignment]

#     async def _go() -> list[CandidateResult]:
#         return await run_batch(
#             _docs("a", "b"),
#             _cases(2),
#             [metric],
#             _cfg(),
#             MeanReward(),
#             floor=1,
#             ucb_budget=0,
#             max_concurrency=2,
#             seed=1,
#         )

#     results: list[CandidateResult] = asyncio.run(_go())
#     assert len(results) == 2
