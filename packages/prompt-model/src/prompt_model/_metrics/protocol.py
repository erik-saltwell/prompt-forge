from __future__ import annotations

from typing import ClassVar, Protocol, runtime_checkable

from .result import MetricResult


class MissingGroundTruthError(Exception):
    """Raised by a Metric whose `evaluate` requires `ground_truth` when it is `None`.

    The harness catches this and skips the metric for the case, continuing the run."""


@runtime_checkable
class Metric(Protocol):
    name: ClassVar[str]
    description: ClassVar[str]

    async def evaluate(
        self,
        prompt: str,
        input: str,
        output: str,
        ground_truth: str | None,
    ) -> MetricResult: ...
