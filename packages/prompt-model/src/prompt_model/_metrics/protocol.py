from __future__ import annotations

from typing import ClassVar, Protocol, runtime_checkable

from .result import MetricResult


class MissingGroundTruthError(Exception):
    """Raised by a Metric whose `evaluate` requires `ground_truth` when it is `None`.

    The harness treats this as a configuration or coding error: the metric suite and
    evaluation cases are incompatible, so the failure is surfaced rather than skipped."""


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
