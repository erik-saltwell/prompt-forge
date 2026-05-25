from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import structlog
from structlog.typing import EventDict, Processor, WrappedLogger

trace_file = None

COMMON_LOG_FIELDS: list[str] = [
    "timestamp",
    "level",
    "event",
    "logger",
    "run_id",
    "round",
    "parent_candidate_id",
    "candidate_id",
    "bucket_id",
    "case_id",
    "metric_name",
    "floor",
    "warmup",
]


def make_field_ordering_processor(
    first_fields: Sequence[str],
    *,
    sort_remaining: bool = True,
) -> Processor:
    """Return a structlog processor that puts selected fields first,
    then appends remaining fields alphabetically or in existing order.
    """

    first_fields_tuple: tuple[str, ...] = tuple(first_fields)

    def order_fields(
        _logger: WrappedLogger,
        _method_name: str,
        event_dict: EventDict,
    ) -> EventDict:
        ordered: dict[str, Any] = {}

        for key in first_fields_tuple:
            if key in event_dict:
                ordered[key] = event_dict[key]

        remaining_keys: list[str] = [key for key in event_dict if key not in ordered]

        if sort_remaining:
            remaining_keys = sorted(remaining_keys)

        for key in remaining_keys:
            ordered[key] = event_dict[key]

        return ordered

    return order_fields


def initialize_tracing(tracefile_path: Path, indent: int | None = None) -> None:
    """Configure structlog to write JSON-lines events to `tracefile_path`.

    Call once at process startup. Library code emits via structlog.get_logger()
    and inherits this config. Without this call, prompt_model is silent.
    """
    global trace_file
    trace_file = open(tracefile_path, "a", encoding="utf-8")
    json_renderer: Processor
    if indent is not None:
        json_renderer = structlog.processors.JSONRenderer(indent=indent, sort_keys=False)
    else:
        json_renderer = structlog.processors.JSONRenderer(sort_keys=False)

    ordering_processor: Processor = make_field_ordering_processor(COMMON_LOG_FIELDS)

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.dict_tracebacks,
        ordering_processor,
        json_renderer,
    ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.WriteLoggerFactory(trace_file),
    )
