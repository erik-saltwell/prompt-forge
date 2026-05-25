from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import ClassVar

from prompt_model._candidate.candidate import Candidate
from prompt_model._metrics import MetricResult
from prompt_model._prompt import parse_from_string
from prompt_model.config import EvalCase, LiteLLMConfig

type Outcome = MetricResult | BaseException


class FakeMetric:
    """Queued-outcome metric. Each evaluate call pops the next outcome and either returns or raises."""

    name: ClassVar[str] = "fake"
    description: ClassVar[str] = "Fake metric for tests"

    def __init__(self, outcomes: list[Outcome]) -> None:
        self._outcomes: list[Outcome] = list(outcomes)
        self.calls: int = 0

    async def evaluate(self, prompt: str, input: str, output: str, ground_truth: str | None) -> MetricResult:
        self.calls += 1
        if not self._outcomes:
            raise RuntimeError("FakeMetric outcomes exhausted")
        nxt: Outcome = self._outcomes.pop(0)
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt


class RecordingMetric:
    """Records (prompt, enter_time, exit_time) for every evaluate call. Always returns the same result."""

    name: ClassVar[str] = "recording"
    description: ClassVar[str] = "Records call intervals"

    def __init__(self, score: float = 1.0, delay: float = 0.01) -> None:
        self._score: float = score
        self._delay: float = delay
        self.intervals: list[tuple[str, float, float]] = []

    async def evaluate(self, prompt: str, input: str, output: str, ground_truth: str | None) -> MetricResult:
        import asyncio

        enter: float = time.monotonic()
        await asyncio.sleep(self._delay)
        exit_: float = time.monotonic()
        self.intervals.append((prompt, enter, exit_))
        return ok_result(self._score, metric_name=self.name)


def ok_result(score: float = 1.0, metric_name: str = "fake") -> MetricResult:
    return MetricResult(metric_name=metric_name, score=score, assessment=f"score={score}")


def make_candidate(heading: str, case_count: int = 1) -> Candidate:
    """Build a Candidate whose prompt's markdown starts with the given heading."""
    return Candidate(prompt=parse_from_string(f"# {heading}\n\nbody\n"), case_ids=list(range(case_count)))


def make_cases(n: int) -> list[EvalCase]:
    return [EvalCase(input=f"input-{i}") for i in range(n)]


def fake_acomplete_factory(output: str = "stub output") -> Callable[[str, str, LiteLLMConfig], Awaitable[str]]:
    """Return an async stub for acomplete that ignores its args and returns `output`."""

    async def _stub(system_prompt: str, user_prompt: str, config: LiteLLMConfig, **kwargs: object) -> str:
        return output

    return _stub
