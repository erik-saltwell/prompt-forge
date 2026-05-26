from __future__ import annotations

from typing import Protocol

from ..._metrics._aggregator import AggregatedNodeBucket


class SignalRenderingStrategy(Protocol):
    """Renders one bucket of `IssueSignal`s as the string the actor LLM reads,
    and describes its own rendering convention via `describe_format()`.
    """

    def render(self, bucket: AggregatedNodeBucket) -> str: ...

    def describe_format(self) -> str: ...
