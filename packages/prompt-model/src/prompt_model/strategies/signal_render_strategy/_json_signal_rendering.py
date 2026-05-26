from __future__ import annotations

from typing import ClassVar

from ..._metrics._aggregator import AggregatedNodeBucket
from ._resources import load_rendering_resource


class JsonSignalRenderingStrategy:
    """Renders the bucket as pretty-printed JSON via Pydantic."""

    format_snippet_resource: ClassVar[str] = "json"

    def describe_format(self) -> str:
        return load_rendering_resource(self.format_snippet_resource)

    def render(self, bucket: AggregatedNodeBucket) -> str:
        return bucket.model_dump_json(indent=2)
